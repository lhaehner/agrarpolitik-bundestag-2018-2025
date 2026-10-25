"""Die feste Excel-Vorlage mit der Python-Standardbibliothek aktualisieren.

XLSX ist ein ZIP-Archiv mit XML-Dateien. Dieses Modul liest Zellwerte und
Formeln, ersetzt ausgewählte Werte und schreibt neu berechnete Formelresultate
in die gespeicherten Ergebnisfelder (Caches). Dadurch sind die Resultate auch
für Programme sichtbar, die Excel-Formeln nicht selbst neu berechnen.

Die Formel-Engine unterstützt gezielt den Umfang der Datengrundlage.xlsx:
SUM, COUNTIFS, IF, OR, Grundrechenarten, Vergleiche, Textverkettung und A1-Bezüge.
Sie ist kein allgemeiner Excel-Ersatz. Unbekannte Syntax/Funktionen sowie
zirkuläre Bezüge brechen die Verarbeitung ab. Normale Rechenfehler wie Division
durch null bleiben dagegen ausdrücklich als Excel-Fehlerwerte erhalten.

Die Vorlage bestimmt Layout, Tabellen und Verknüpfungen. Vorhandene Stile und
übrige ZIP-Bestandteile werden übernommen. Zeilen-/Tabellenerweiterungen und
Diagramm-Cache-Neuberechnungen sind nicht Aufgabe dieses Moduls. Die geschriebenen
Formel-Caches betreffen Arbeitsblattzellen. Excel wird zusätzlich angewiesen,
beim Öffnen vollständig neu zu rechnen.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import math
import os
from pathlib import Path
import posixpath
import re
import tempfile
import xml.etree.ElementTree as ET
import zipfile


MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"x": MAIN, "r": REL}
ET.register_namespace("x", MAIN)
ET.register_namespace("r", REL)


def _tag(name):
    return "{" + MAIN + "}" + name


class FormulaEvaluationError(ValueError):
    """Nicht unterstützte/ungültige Formel oder zyklische Zellabhängigkeit."""


class ExcelError(str):
    """Excel-Rechenfehler, der als Fehlerzelle statt als normaler Text gespeichert wird."""


def _number(text):
    """Gespeicherte XML-Zahl lesen. Leere Werte bleiben zunächst None."""
    if text is None or text == "":
        return None
    return float(text) if any(c in text.lower() for c in ".e") else int(text)


def _sheet_paths(archive):
    """Blattnamen über die internen Beziehungen ihren XML-Dateien zuordnen."""
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {}
    for relation in relationships:
        if relation.get("TargetMode") == "External":
            continue
        target = relation.get("Target", "")
        targets[relation.get("Id")] = (
            target.lstrip("/") if target.startswith("/")
            else posixpath.normpath(posixpath.join("xl", target))
        )
    return {
        sheet.get("name"): targets[sheet.get("{" + REL + "}id")]
        for sheet in workbook.find("x:sheets", NS)
    }


def _shared_strings(archive):
    """Die gemeinsame Texttabelle lesen und formatierte Textteile zusammenfügen."""
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return ["".join(t.text or "" for t in item.iter(_tag("t"))) for item in root]


def _cell_value(cell, shared):
    """Den gespeicherten Zellwert typisiert lesen, ohne eine Formel auszuführen."""
    kind = cell.get("t", "n")
    value = cell.find("x:v", NS)
    text = value.text if value is not None else None
    if kind == "inlineStr":
        inline = cell.find("x:is", NS)
        return "".join(t.text or "" for t in inline.iter(_tag("t"))) if inline is not None else ""
    if kind == "s":
        return shared[int(text)] if text is not None else ""
    if kind in ("str", "d"):
        return text or ""
    if kind == "b":
        return text == "1"
    if kind == "e":
        return ExcelError(text or "#VALUE!")
    return _number(text)


def read_workbook(path):
    """Blätter als {Blattname: {A1-Adresse: Wert_oder_Formel_mit_Gleichzeichen}} lesen.

    Formatierte Leerzellen bleiben als None erhalten. Numerisch gespeicherte
    Datumswerte bleiben Excel-Tageszahlen. Explizite ISO-Datumszellen bleiben
    Text. Bei Formeln wird der Ausdruck gelesen, nicht das gespeicherte Resultat.
    Shared-, Array- und Data-Table-Formeln werden ausdrücklich zurückgewiesen.
    """
    result = {}
    with zipfile.ZipFile(path) as archive:
        shared = _shared_strings(archive)
        for name, path_in_zip in _sheet_paths(archive).items():
            root = ET.fromstring(archive.read(path_in_zip))
            cells = {}
            for cell in root.findall("x:sheetData/x:row/x:c", NS):
                formula = cell.find("x:f", NS)
                if formula is not None:
                    if formula.get("t") in ("shared", "array", "dataTable"):
                        raise FormulaEvaluationError("Shared/array/table formulas are unsupported")
                    cells[cell.get("r").upper()] = "=" + (formula.text or "")
                else:
                    cells[cell.get("r").upper()] = _cell_value(cell, shared)
            result[name] = cells
    return result


_ADDRESS = re.compile(r"^\$?([A-Za-z]{1,3})\$?([1-9][0-9]*)$")


def _coordinates(address):
    """A1-Adresse in (Zeile, Spalte) umwandeln und Excel-Grenzen prüfen."""
    match = _ADDRESS.fullmatch(address)
    if not match:
        raise FormulaEvaluationError("Invalid cell address: " + str(address))
    column = 0
    for letter in match.group(1).upper():
        column = column * 26 + ord(letter) - 64
    row = int(match.group(2))
    if column > 16384 or row > 1048576:
        raise FormulaEvaluationError("Cell address outside Excel limits: " + address)
    return row, column


def _column_name(column):
    result = ""
    while column:
        column, remainder = divmod(column - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _canonical_address(address):
    """Bezüge für den Zugriff normalisieren, z. B. '$b$9' zu 'B9'.

    Absolut/relativ ist beim Auswerten einer festen Formel unerheblich. Dieses
    Modul verschiebt oder kopiert keine Formeln in andere Zellpositionen.
    """
    row, column = _coordinates(address)
    return _column_name(column) + str(row)


_TOKEN = re.compile(
    r'(?P<SPACE>\s+)|(?P<STRING>"(?:[^"]|"")*")|'
    r"(?P<QUOTED>'(?:[^']|'')*')|"
    r'(?P<CELL>\$?[A-Za-z]{1,3}\$?[1-9][0-9]*(?![A-Za-z0-9_]))|'
    r'(?P<NUMBER>(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[Ee][+-]?[0-9]+)?)|'
    r'(?P<IDENT>[A-Za-z_][A-Za-z0-9_.]*)|(?P<OP><=|>=|<>|[+\-*/&=<>():,!])'
)


@dataclass(frozen=True)
class Token:
    """Ein Baustein der Formel, etwa Zahl, Zelladresse oder Rechenzeichen."""
    kind: str
    text: str


class _Parser:
    """Excel-Ausdruck in einen kleinen Syntaxbaum mit fester Rangfolge zerlegen.

    Rekursiver Abstieg: Vergleich -> Verkettung -> Addition -> Multiplikation ->
    Vorzeichen -> Einzelwert/Bezug/Funktionsaufruf. Formeln werden nicht mit
    Python-eval ausgeführt. Verarbeitet wird die englische OOXML-Schreibweise
    mit Kommas als Argumenttrennern, wie sie intern in der XLSX steht.
    """
    def __init__(self, formula):
        self.tokens = []
        offset = 0
        while offset < len(formula):
            match = _TOKEN.match(formula, offset)
            if not match:
                raise FormulaEvaluationError("Unsupported formula syntax near " + repr(formula[offset:offset + 30]))
            offset = match.end()
            if match.lastgroup != "SPACE":
                self.tokens.append(Token(match.lastgroup, match.group()))
        self.tokens.append(Token("END", ""))
        self.index = 0

    def peek(self):
        return self.tokens[self.index]

    def take(self, expected=None):
        token = self.peek()
        if expected is not None and token.text != expected:
            raise FormulaEvaluationError("Expected " + repr(expected) + ", found " + repr(token.text))
        self.index += 1
        return token

    def parse(self):
        """Die vollständige Formel lesen und nicht verbrauchte Zeichen zurückweisen."""
        expression = self.comparison()
        if self.peek().kind != "END":
            raise FormulaEvaluationError("Unexpected token: " + self.peek().text)
        return expression

    def comparison(self):
        node = self.concatenation()
        while self.peek().text in ("=", "<>", "<", ">", "<=", ">="):
            operator = self.take().text
            node = ("binary", operator, node, self.concatenation())
        return node

    def concatenation(self):
        node = self.addition()
        while self.peek().text == "&":
            self.take()
            node = ("binary", "&", node, self.addition())
        return node

    def addition(self):
        node = self.multiplication()
        while self.peek().text in ("+", "-"):
            operator = self.take().text
            node = ("binary", operator, node, self.multiplication())
        return node

    def multiplication(self):
        node = self.unary()
        while self.peek().text in ("*", "/"):
            operator = self.take().text
            node = ("binary", operator, node, self.unary())
        return node

    def unary(self):
        if self.peek().text in ("+", "-"):
            return ("unary", self.take().text, self.unary())
        return self.primary()

    def primary(self):
        """Einzelwerte, Klammern, Funktionen und optional blattübergreifende Bezüge lesen."""
        token = self.take()
        if token.kind == "NUMBER":
            return ("literal", _number(token.text))
        if token.kind == "STRING":
            return ("literal", token.text[1:-1].replace('""', '"'))
        if token.text == "(":
            node = self.comparison()
            self.take(")")
            return node
        if token.kind in ("IDENT", "CELL", "QUOTED"):
            if self.peek().text == "(":
                self.take()
                arguments = []
                if self.peek().text != ")":
                    arguments.append(self.comparison())
                    while self.peek().text == ",":
                        self.take()
                        arguments.append(self.comparison())
                self.take(")")
                return ("call", token.text.upper(), tuple(arguments))
            sheet = None
            if self.peek().text == "!":
                self.take()
                sheet = token.text[1:-1].replace("''", "'") if token.kind == "QUOTED" else token.text
                token = self.take()
            elif token.kind == "IDENT" and token.text.upper() in ("TRUE", "FALSE"):
                return ("literal", token.text.upper() == "TRUE")
            if token.kind != "CELL":
                raise FormulaEvaluationError("Expected an A1 reference, found " + token.text)
            first = _canonical_address(token.text)
            if self.peek().text == ":":
                self.take()
                last = self.take()
                if last.kind != "CELL":
                    raise FormulaEvaluationError("Expected range endpoint")
                return ("range", sheet, first, _canonical_address(last.text))
            return ("ref", sheet, first)
        raise FormulaEvaluationError("Unexpected expression token: " + token.text)


@lru_cache(maxsize=100000)
def _parse_formula(formula):
    """Syntaxbaum zwischenspeichern, um identische Formeln nur einmal zu analysieren."""
    return _Parser(formula[1:] if formula.startswith("=") else formula).parse()


@dataclass(frozen=True)
class _Range:
    """Werte eines Zellbereichs samt Form für COUNTIFS-Kompatibilitätsprüfungen."""
    values: tuple
    rows: int
    columns: int


def _numeric(value):
    """Für Grundrechenarten umwandeln, leere Zellen als 0 und Fehler explizit behandeln."""
    if isinstance(value, ExcelError):
        return value
    if value is None or value == "":
        return 0
    if isinstance(value, (int, float)):
        return value
    try:
        return _number(str(value))
    except (ValueError, TypeError):
        return ExcelError("#VALUE!")


def _text(value):
    """Zellwerte für Verkettung und Textkriterien in die benötigte Textform bringen."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _compare(operator, left, right):
    """Vergleiche im benötigten Excel-Teilumfang inklusive Leerzellen/Textsorte ausführen."""
    if isinstance(left, ExcelError):
        return left
    if isinstance(right, ExcelError):
        return right
    if left is None:
        left = "" if isinstance(right, str) else 0
    if right is None:
        right = "" if isinstance(left, str) else 0
    if isinstance(left, str) and isinstance(right, str):
        left, right = left.casefold(), right.casefold()
    elif isinstance(left, str) != isinstance(right, str):
        # Excel ordnet Zahlen vor Text. Für Gleichheit wird Text nicht in Zahlen umgewandelt.
        left, right = (1 if isinstance(left, str) else 0), (1 if isinstance(right, str) else 0)
    return {"=": lambda: left == right, "<>": lambda: left != right,
            "<": lambda: left < right, ">": lambda: left > right,
            "<=": lambda: left <= right, ">=": lambda: left >= right}[operator]()


def _criterion_match(value, criterion):
    """Ein COUNTIFS-Kriterium prüfen, einschließlich Vergleich und Textplatzhaltern.

    '*' steht für beliebig viele Zeichen, '?' für ein Zeichen. '~' maskiert
    das Folgezeichen. Numerische Kriterien werden gesondert behandelt.
    """
    if isinstance(value, ExcelError) or isinstance(criterion, ExcelError):
        return False
    if criterion is None:
        criterion = 0
    operator = "="
    operand = criterion
    if isinstance(criterion, str):
        match = re.match(r"^(<=|>=|<>|=|<|>)?(.*)$", criterion, re.S)
        operator, operand = match.group(1) or "=", match.group(2)
        if operand != "":
            try:
                operand = _number(operand)
            except ValueError:
                pass
    if isinstance(operand, (int, float)):
        if value is None or value == "":
            value = 0
        elif isinstance(value, str):
            try:
                value = _number(value)
            except ValueError:
                return operator == "<>"
    elif isinstance(operand, str) and operator in ("=", "<>"):
        pattern = ""
        offset = 0
        while offset < len(operand):
            char = operand[offset]
            if char == "~" and offset + 1 < len(operand):
                offset += 1
                pattern += re.escape(operand[offset])
            else:
                pattern += ".*" if char == "*" else "." if char == "?" else re.escape(char)
            offset += 1
        matched = re.fullmatch(pattern, _text(value), re.I | re.S) is not None
        return matched if operator == "=" else not matched
    return bool(_compare(operator, value, operand))


def calc_workbook(cells):
    """Alle Zellwerte einschließlich berechneter Formeln als neue Abbildung liefern.

    Unterstützt SUM, COUNTIFS, IF, OR, + - * / &, Vergleiche, A1-Bereiche und
    blattübergreifende Bezüge. IF wertet ausschließlich den ausgewählten Zweig
    aus. Eingaben bleiben unverändert. Excel-Rechenfehler werden als ExcelError
    zurückgegeben. Nicht unterstützte Formeln und Zyklen lösen Ausnahmen aus.
    """
    sheet_lookup = {name.casefold(): name for name in cells}
    normalized = {name: {_canonical_address(address): value for address, value in values.items()}
                  for name, values in cells.items()}
    # cache vermeidet wiederholte Berechnungen. active erkennt gerade laufende
    # Abhängigkeiten und damit zirkuläre Bezüge über mehrere Zellen/Blätter.
    cache = {}
    active = set()

    def value_at(sheet, address):
        """Einen Wert bei Bedarf rekursiv berechnen und sein Resultat wiederverwenden."""
        actual_sheet = sheet_lookup.get(sheet.casefold())
        if actual_sheet is None:
            return ExcelError("#REF!")
        key = actual_sheet, address
        if key in cache:
            return cache[key]
        raw = normalized[actual_sheet].get(address)
        if not (isinstance(raw, str) and not isinstance(raw, ExcelError) and raw.startswith("=")):
            return raw
        if key in active:
            raise FormulaEvaluationError("Circular reference at " + actual_sheet + "!" + address)
        active.add(key)
        try:
            result = evaluate(_parse_formula(raw), actual_sheet)
            if isinstance(result, _Range):
                result = ExcelError("#VALUE!")
            if result is None:
                result = 0
            cache[key] = result
            return result
        except FormulaEvaluationError as exc:
            raise FormulaEvaluationError(actual_sheet + "!" + address + ": " + str(exc)) from exc
        finally:
            active.remove(key)

    def evaluate(node, sheet):
        """Syntaxbaum im Kontext des aktuellen Blatts auswerten."""
        kind = node[0]
        if kind == "literal":
            return node[1]
        if kind == "ref":
            return value_at(node[1] or sheet, node[2])
        if kind == "range":
            row1, col1 = _coordinates(node[2])
            row2, col2 = _coordinates(node[3])
            row1, row2 = sorted((row1, row2))
            col1, col2 = sorted((col1, col2))
            values = tuple(value_at(node[1] or sheet, _column_name(col) + str(row))
                           for row in range(row1, row2 + 1) for col in range(col1, col2 + 1))
            return _Range(values, row2 - row1 + 1, col2 - col1 + 1)
        if kind == "unary":
            value = _numeric(evaluate(node[2], sheet))
            return value if isinstance(value, ExcelError) or node[1] == "+" else -value
        if kind == "binary":
            operator = node[1]
            left, right = evaluate(node[2], sheet), evaluate(node[3], sheet)
            if isinstance(left, ExcelError):
                return left
            if isinstance(right, ExcelError):
                return right
            if isinstance(left, _Range) or isinstance(right, _Range):
                return ExcelError("#VALUE!")
            if operator == "&":
                return _text(left) + _text(right)
            if operator in ("=", "<>", "<", ">", "<=", ">="):
                return _compare(operator, left, right)
            left, right = _numeric(left), _numeric(right)
            if isinstance(left, ExcelError):
                return left
            if isinstance(right, ExcelError):
                return right
            if operator == "+":
                return left + right
            if operator == "-":
                return left - right
            if operator == "*":
                return left * right
            return ExcelError("#DIV/0!") if right == 0 else left / right
        function, arguments = node[1], node[2]
        # IF wird vor der allgemeinen Argumentauswertung behandelt: Ein Fehler
        # im nicht gewählten Zweig darf das Ergebnis nicht beeinflussen.
        if function == "IF":
            if len(arguments) not in (2, 3):
                raise FormulaEvaluationError("IF requires two or three arguments")
            condition = evaluate(arguments[0], sheet)
            if isinstance(condition, ExcelError):
                return condition
            if bool(condition):
                return evaluate(arguments[1], sheet)
            return evaluate(arguments[2], sheet) if len(arguments) == 3 else False
        values = [evaluate(argument, sheet) for argument in arguments]
        if function == "SUM":
            total = 0
            for value in values:
                items = value.values if isinstance(value, _Range) else (value,)
                for item in items:
                    if isinstance(item, ExcelError):
                        return item
                    if isinstance(item, (int, float)):
                        total += item
            return total
        if function == "OR":
            flattened = [item for value in values for item in (value.values if isinstance(value, _Range) else (value,))]
            for value in flattened:
                if isinstance(value, ExcelError):
                    return value
            return any(bool(value) for value in flattened if not isinstance(value, str))
        # Kriterien werden positionsweise über gleich geformte Bereiche verknüpft.
        # Jede Position trägt höchstens 1 zur Anzahl erfüllter Kriterien bei.
        if function == "COUNTIFS":
            if not values or len(values) % 2:
                raise FormulaEvaluationError("COUNTIFS requires range/criterion pairs")
            ranges, criteria = values[::2], values[1::2]
            if any(not isinstance(value, _Range) for value in ranges):
                raise FormulaEvaluationError("COUNTIFS ranges must be A1 ranges")
            if len({(value.rows, value.columns) for value in ranges}) != 1:
                return ExcelError("#VALUE!")
            for criterion in criteria:
                if isinstance(criterion, ExcelError):
                    return criterion
            return sum(all(_criterion_match(item, criterion) for item, criterion in zip(row, criteria))
                       for row in zip(*(value.values for value in ranges)))
        raise FormulaEvaluationError("Unsupported function: " + function)

    return {sheet: {address: value_at(sheet, address) for address in values}
            for sheet, values in normalized.items()}


def _set_cell(cell, raw, cached=None):
    """Zellinhalt erneuern und bei Formeln den berechneten Wert zusätzlich speichern.

    Bestehende Stilattribute bleiben erhalten. Fehler, Zahlen, Wahrheitswerte
    und Texte erhalten ihre passenden OOXML-Zelltypen.
    """
    for child in list(cell):
        if child.tag in (_tag("f"), _tag("v"), _tag("is")):
            cell.remove(child)
    cell.attrib.pop("t", None)
    is_formula = isinstance(raw, str) and not isinstance(raw, ExcelError) and raw.startswith("=")
    value = cached if is_formula else raw
    if is_formula:
        ET.SubElement(cell, _tag("f")).text = raw[1:]
    if value is None:
        return
    if isinstance(value, ExcelError):
        cell.set("t", "e")
        ET.SubElement(cell, _tag("v")).text = str(value)
    elif isinstance(value, bool):
        cell.set("t", "b")
        ET.SubElement(cell, _tag("v")).text = "1" if value else "0"
    elif isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise ValueError("XLSX numeric cells must be finite")
        ET.SubElement(cell, _tag("v")).text = repr(value)
    elif isinstance(value, str):
        if is_formula:
            cell.set("t", "str")
            ET.SubElement(cell, _tag("v")).text = value
        else:
            cell.set("t", "inlineStr")
            text = ET.SubElement(ET.SubElement(cell, _tag("is")), _tag("t"))
            text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            text.text = value
    else:
        raise TypeError("Unsupported XLSX cell value type: " + type(value).__name__)


def patch_workbook(template, output, changes):
    """Vorlage kopieren, benannte Zellen ersetzen und alle Formel-Caches erneuern.

    ``changes`` hat die Form {Blattname: {A1-Adresse: Wert_oder_Formel}}. Stile
    vorhandener Zellen und übrige ZIP-Bestandteile werden übernommen. Bestehende
    Tabellendefinitionen werden nicht vergrößert. Die Eingabe muss daher eine
    passende Vorlage sein. Rückgabe ist der Ausgabepfad.

    Zuerst wird vollständig in eine temporäre Datei geschrieben. Erst nach
    Erfolg ersetzt diese atomar das Ausgabeziel. Die Fehlerbehandlung entfernt
    eine unvollständige temporäre Datei.
    """
    # Erst die gesamte Mappe berechnen, da Formeln auch auf andere Blätter verweisen.
    cells = read_workbook(template)
    normalized_changes = {}
    for sheet, values in changes.items():
        if sheet not in cells:
            raise KeyError("Worksheet does not exist: " + sheet)
        normalized_changes[sheet] = {_canonical_address(address): value for address, value in values.items()}
        cells[sheet].update(normalized_changes[sheet])
    calculated = calc_workbook(cells)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=output.name + ".", suffix=".tmp", dir=output.parent)
    os.close(handle)
    try:
        with zipfile.ZipFile(template) as source:
            replacements = {}
            for sheet, path_in_zip in _sheet_paths(source).items():
                # Auch unveränderte Formeln können von geänderten Zählern abhängen.
                # Daher werden für jedes Blatt sämtliche Formel-Caches erneuert.
                updates = dict(normalized_changes.get(sheet, {}))
                updates.update({address: value for address, value in cells[sheet].items()
                                if isinstance(value, str) and not isinstance(value, ExcelError) and value.startswith("=")})
                if not updates:
                    continue
                root = ET.fromstring(source.read(path_in_zip))
                data = root.find("x:sheetData", NS)
                rows = {int(row.get("r")): row for row in data}
                existing = {cell.get("r"): cell for row in data for cell in row if cell.tag == _tag("c")}
                for address, value in updates.items():
                    row_number, _ = _coordinates(address)
                    if row_number not in rows:
                        rows[row_number] = ET.SubElement(data, _tag("row"), {"r": str(row_number)})
                    cell = existing.get(address)
                    if cell is None:
                        cell = ET.SubElement(rows[row_number], _tag("c"), {"r": address})
                        existing[address] = cell
                    _set_cell(cell, value, calculated[sheet][address])
                data[:] = sorted(data, key=lambda row: int(row.get("r")))
                for row in data:
                    row[:] = sorted(row, key=lambda cell: _coordinates(cell.get("r"))[1])
                dimension = root.find("x:dimension", NS)
                if dimension is not None and existing:
                    coordinates = [_coordinates(address) for address in existing]
                    dimension.set("ref", _column_name(min(c for r, c in coordinates)) + str(min(r for r, c in coordinates)) + ":" +
                                  _column_name(max(c for r, c in coordinates)) + str(max(r for r, c in coordinates)))
                replacements[path_in_zip] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            workbook = ET.fromstring(source.read("xl/workbook.xml"))
            calculation = workbook.find("x:calcPr", NS)
            if calculation is None:
                calculation = ET.SubElement(workbook, _tag("calcPr"))
            # Die eigene Berechnung deckt die vorgegebenen Arbeitsblattformeln ab.
            # Beim nächsten Öffnen soll Excel zusätzlich vollständig neu rechnen.
            calculation.set("calcMode", "auto")
            calculation.set("fullCalcOnLoad", "1")
            calculation.set("forceFullCalc", "1")
            replacements["xl/workbook.xml"] = ET.tostring(workbook, encoding="utf-8", xml_declaration=True)
            with zipfile.ZipFile(temporary, "w") as destination:
                for info in source.infolist():
                    destination.writestr(info, replacements.get(info.filename, source.read(info.filename)))
        os.replace(temporary, output)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise
    return output


def audit_formula_caches(path, *, relative_tolerance=1e-12, absolute_tolerance=1e-10):
    """Gespeicherte Formelresultate lesend mit der eigenen Neuberechnung vergleichen.

    Prüft ausschließlich Formelzellen, nicht die fachliche Herkunft ihrer
    Eingabewerte. Der Vergleich verwendet denselben Formelrechner wie der Export
    und dient damit der Kontrolle der gespeicherten Werte. Ganze Zahlen müssen
    exakt übereinstimmen. Fließkommazahlen
    werden mit den angegebenen Toleranzen verglichen. Fehlende Caches und
    Abweichungen werden samt Zelladresse gemeldet. Die XLSX bleibt unverändert.
    """
    calculated = calc_workbook(read_workbook(path))
    report = {"formulas": 0, "matched": 0, "integer_caches": 0, "float_caches": 0,
              "text_caches": 0, "missing_caches": 0, "max_absolute_error": 0.0,
              "max_relative_error": 0.0, "mismatches": []}
    with zipfile.ZipFile(path) as archive:
        shared = _shared_strings(archive)
        for sheet, path_in_zip in _sheet_paths(archive).items():
            root = ET.fromstring(archive.read(path_in_zip))
            for cell in root.findall("x:sheetData/x:row/x:c", NS):
                if cell.find("x:f", NS) is None:
                    continue
                report["formulas"] += 1
                address = cell.get("r")
                expected, actual = _cell_value(cell, shared), calculated[sheet][address]
                if cell.find("x:v", NS) is None:
                    report["missing_caches"] += 1
                    matches = False
                elif isinstance(expected, int):
                    report["integer_caches"] += 1
                    matches = isinstance(actual, (int, float)) and actual == expected
                elif isinstance(expected, float):
                    report["float_caches"] += 1
                    matches = isinstance(actual, (int, float)) and math.isclose(actual, expected, rel_tol=relative_tolerance, abs_tol=absolute_tolerance)
                    if isinstance(actual, (int, float)):
                        error = abs(actual - expected)
                        report["max_absolute_error"] = max(report["max_absolute_error"], error)
                        report["max_relative_error"] = max(report["max_relative_error"], error / max(abs(expected), 1e-300))
                else:
                    report["text_caches"] += 1
                    matches = type(actual) is type(expected) and actual == expected
                if matches:
                    report["matched"] += 1
                else:
                    report["mismatches"].append({"sheet": sheet, "cell": address, "expected": expected, "actual": actual})
    return report
