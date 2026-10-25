"""Sicherheit und Resilienz: geschlossene Formen und gemeinsame Vorkommen im Satz.

Matcher.match() prüft Direkt- und Satzregeln. Lokale Ausschlüsse sperren nur
überlappende Fundstellen. Belege enthalten Positionen im Originalsatz und im
normalisierten Text. Das Ende jeder Spanne ist exklusiv.
Satzregeln verlangen je einen akzeptierten Beleg aus zwei festgelegten
Lexemgruppen im selben Satz. Sie prüfen keine grammatische Beziehung oder
Bewertung. Mehrere erfüllte Regeln erhöhen den binären Themenwert nicht.

Eingabe: Satztext und Woerterbuch_Sicherheit_und_Resilienz.json. Ausgabe:
sicherheit_resilienz als 0/1-Wert, Kategorien und Fundstellen. satzmatcher.py
ruft dieses Modul nur für bereits vom A&E-Filter ausgewählte Sätze auf.
"""
from __future__ import annotations
import difflib
import json
import os
import re
import unicodedata
from typing import Any
# Technische Kennung des mitgelieferten JSON-Schemas.
SCHEMA_VERSION = 'sr-closed-forms-1.0'

class DictionaryError(ValueError):
    """Fehlerhaftes Wörterbuch oder nicht unterstützte Schemaversion."""

def _nfkc_units(text: str) -> list[tuple[str, int, int]]:
    """Normalisiert Zeichenverbünde und erhält ihre Spannen im Originalsatz.

    Ein Umlaut kann aus einem oder mehreren Unicode-Zeichen bestehen. Deshalb
    werden zusammengehörige Zeichen gemeinsam normalisiert. Falls NFKC über
    diese Verbünde hinaus Zeichen kombiniert, ordnet ein Zeichenvergleich die
    endgültige Normalisierung ihren ursprünglichen Textabschnitten zu.
    """
    clusters: list[tuple[str, int, int]] = []
    begin = 0
    for i, char in enumerate(text):
        decomp = unicodedata.normalize('NFKD', char)
        continues = bool(decomp and unicodedata.combining(decomp[0]))
        if i and (not continues):
            clusters.append((text[begin:i], begin, i))
            begin = i
    if text:
        clusters.append((text[begin:], begin, len(text)))
    units = [(char, start, end) for cluster, start, end in clusters for char in unicodedata.normalize('NFKC', cluster)]
    intermediate = ''.join((char for char, _, _ in units))
    target = unicodedata.normalize('NFKC', text)
    if intermediate == target:
        return units
    result: list[tuple[str, int, int]] = []
    for opcode, i1, i2, j1, j2 in difflib.SequenceMatcher(None, intermediate, target, autojunk=False).get_opcodes():
        if opcode == 'equal':
            result.extend(units[i1:i2])
        elif opcode in {'replace', 'insert'}:
            if i1 < i2:
                start, end = (units[i1][1], units[i2 - 1][2])
            elif units:
                start, end = units[min(i1, len(units) - 1)][1:]
            else:
                start, end = (0, len(text))
            result.extend(((char, start, end) for char in target[j1:j2]))
    return result

def normalize_with_offsets(text: str) -> tuple[str, list[tuple[int, int]]]:
    """Liefert Normaltext und je Zeichen die ursprüngliche Spanne (Start, Ende).

    Erweiterungen wie 'ä' zu 'ae' erhalten für beide Zielzeichen dieselbe
    Ursprungsspanne. Zusammengezogener Leerraum verweist auf den gesamten
    ursprünglichen Leerraum. So bleiben Treffer im Originalsatz belegbar.
    """
    if not isinstance(text, str):
        raise TypeError('The sentence must be a string.')
    expanded: list[tuple[str, int, int]] = []
    replacements = {'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss', '‐': '-', '‑': '-', '\xad': ''}
    for char, start, end in _nfkc_units(text):
        for folded in char.casefold():
            for converted in replacements.get(folded, folded):
                expanded.append((converted, start, end))
    collapsed: list[tuple[str, int, int]] = []
    for char, start, end in expanded:
        if char.isspace():
            if collapsed and collapsed[-1][0] == ' ':
                collapsed[-1] = (' ', collapsed[-1][1], end)
            else:
                collapsed.append((' ', start, end))
        else:
            collapsed.append((char, start, end))
    return (''.join((char for char, _, _ in collapsed)), [(start, end) for _, start, end in collapsed])

def normalize(text: str) -> str:
    """Normalisiert Wörterbuchformen und Sätze nach genau denselben Regeln."""
    return normalize_with_offsets(text)[0]

def _is_joiner(char: str) -> bool:
    """Erkennt Zeichen, die als unmittelbarer Anschluss eine Wortgrenze verhindern."""
    return char.isalnum() or char in '_-' or unicodedata.category(char).startswith('M')

def _boundary_ok(text: str, start: int, end: int) -> bool:
    """Verhindert Teilworttreffer, auch an Bindestrichen und Kombinationszeichen."""
    return (start == 0 or not _is_joiner(text[start - 1])) and (end == len(text) or not _is_joiner(text[end]))

def _records(root: dict[str, Any], key: str) -> list[dict[str, Any]]:
    """Liest einen Wörterbuchabschnitt als Liste von JSON-Objekten."""
    values = root.get(key)
    if not isinstance(values, list):
        raise DictionaryError(f'{key}: expected a list.')
    if not all((isinstance(value, dict) for value in values)):
        raise DictionaryError(f'{key}: every entry must be an object.')
    return values

def _unique_ids(records: list[dict[str, Any]], name: str) -> set[str]:
    """Prüft nichtleere, eindeutige Kennungen innerhalb des übergebenen Abschnitts."""
    seen: set[str] = set()
    for record in records:
        ident = record.get('id')
        if not isinstance(ident, str) or not ident or ident.strip() != ident:
            raise DictionaryError(f'{name}: every id must be a nonempty trimmed string.')
        if ident in seen:
            raise DictionaryError(f'{name}: duplicate id {ident!r}.')
        seen.add(ident)
    return seen

def _forms(record: dict[str, Any], name: str) -> list[str]:
    """Prüft eine nichtleere Liste wörtlicher Formen ohne identische Doppeleinträge."""
    forms = record.get('forms')
    if not isinstance(forms, list) or not forms:
        raise DictionaryError(f'{name}: forms must be a nonempty list.')
    for form in forms:
        if not isinstance(form, str) or not form.strip() or form.strip() != form or (not normalize(form).strip()):
            raise DictionaryError(f'{name}: invalid literal form {form!r}.')
    if len(set(forms)) != len(forms):
        raise DictionaryError(f'{name}: a literal form is listed more than once.')
    return forms

def validate_dictionary(root: dict[str, Any]) -> None:
    """Prüft Schema, Pflichtabschnitte, eindeutige Kennungen und gültige Verweise."""
    if not isinstance(root, dict) or root.get('schema_version') != SCHEMA_VERSION:
        raise DictionaryError(f'Expected schema_version {SCHEMA_VERSION!r}.')
    categories = _records(root, 'categories')
    lexemes = _records(root, 'lexemes')
    direct = _records(root, 'direct_rules')
    cooccurrence = _records(root, 'cooccurrence_rules')
    exclusions = _records(root, 'local_exclusions')
    if not categories or not lexemes or (not (direct or cooccurrence)):
        raise DictionaryError('Categories, lexemes and at least one rule are required.')
    category_ids = _unique_ids(categories, 'categories')
    lexeme_ids = _unique_ids(lexemes, 'lexemes')
    _unique_ids(direct + cooccurrence + exclusions, 'rules and exclusions')
    for category in categories:
        if not isinstance(category.get('label'), str) or not category['label'].strip():
            raise DictionaryError(f"Category {category['id']}: missing label.")
    for lexeme in lexemes:
        if not isinstance(lexeme.get('label'), str) or not lexeme['label'].strip():
            raise DictionaryError(f"Lexeme {lexeme['id']}: missing label.")
        _forms(lexeme, lexeme['id'])
    for rule in direct + cooccurrence:
        if not isinstance(rule.get('category'), str) or rule['category'] not in category_ids:
            raise DictionaryError(f"Rule {rule['id']}: unknown category.")
    for rule in direct:
        if not isinstance(rule.get('lexeme_id'), str) or rule['lexeme_id'] not in lexeme_ids:
            raise DictionaryError(f"Rule {rule['id']}: unknown lexeme_id.")
    for rule in cooccurrence:
        for side in ('any_a', 'any_b'):
            refs = rule.get(side)
            if not isinstance(refs, list) or not refs or any((not isinstance(ref, str) or ref not in lexeme_ids for ref in refs)):
                raise DictionaryError(f"Rule {rule['id']}: invalid {side} references.")
            if len(set(refs)) != len(refs):
                raise DictionaryError(f"Rule {rule['id']}: duplicate {side} references.")
        if set(rule['any_a']) & set(rule['any_b']):
            raise DictionaryError(f"Rule {rule['id']}: both sides share a lexeme.")
    for exclusion in exclusions:
        _forms(exclusion, exclusion['id'])
        refs = exclusion.get('lexeme_ids')
        if not isinstance(refs, list) or not refs or any((not isinstance(ref, str) or ref not in lexeme_ids for ref in refs)):
            raise DictionaryError(f"Exclusion {exclusion['id']}: invalid lexeme_ids.")
        if len(set(refs)) != len(refs):
            raise DictionaryError(f"Exclusion {exclusion['id']}: duplicate lexeme_ids.")

def _compile_forms(forms: list[str]) -> tuple[re.Pattern[str], dict[str, str]]:
    """Kompiliert wörtliche Normalformen und merkt ihre Wörterbuchbezeichnungen.

    Längere Alternativen haben am gleichen Anfang Vorrang. Der Lookahead
    erlaubt anschließend weitere, auch überlappende Startpositionen.
    """
    labels: dict[str, str] = {}
    for form in forms:
        labels.setdefault(normalize(form), form)
    ordered = sorted(labels, key=lambda form: (-len(form), form))
    pattern = re.compile('(?=(' + '|'.join((re.escape(form) for form in ordered)) + ')(?![\\w-]))')
    return (pattern, labels)

def _occurrences(pattern: re.Pattern[str], text: str):
    """Liefert Fundstellen mit vollständig geprüften linken und rechten Grenzen."""
    for occurrence in pattern.finditer(text):
        start, end = occurrence.span(1)
        if _boundary_ok(text, start, end):
            yield (start, end, occurrence.group(1))

class Matcher:
    """Kompiliert das geschlossene S&R-Wörterbuch für bereits segmentierte Sätze."""

    def __init__(self, dictionary: dict[str, Any] | str | os.PathLike[str]):
        """Lädt eine geprüfte Kopie und bereitet Direkt-, Satz- und Ausschlussregeln vor."""
        if isinstance(dictionary, (str, os.PathLike)):
            with open(dictionary, 'r', encoding='utf-8-sig') as handle:
                root = json.load(handle)
        else:
            root = dictionary
        validate_dictionary(root)
        self.dictionary = json.loads(json.dumps(root, ensure_ascii=False))
        self._lexemes = [(lexeme, *_compile_forms(lexeme['forms'])) for lexeme in self.dictionary['lexemes']]
        self._exclusions = [(exclusion, *_compile_forms(exclusion['forms'])) for exclusion in self.dictionary['local_exclusions']]

    def match(self, sentence: str) -> dict[str, Any]:
        """Prüft einen Satz und liefert Themenwert, Kategorien und genaue Belege.

        Zuerst werden lokal ausgeschlossene Lexemvorkommen entfernt. Nur die verbleibenden
        Vorkommen können danach Direkt- oder Satzregeln erfüllen. Verwerfungen
        bleiben separat dokumentiert, zählen aber nicht als positiver Beleg.
        """
        text, offsets = normalize_with_offsets(sentence)
        hits: dict[str, list[dict[str, Any]]] = {}
        blocked: list[dict[str, Any]] = []
        exclusion_occurrences = []
        for exclusion, pattern, _ in self._exclusions:
            for start, end, _ in _occurrences(pattern, text):
                original_start, original_end = (offsets[start][0], offsets[end - 1][1])
                exclusion_occurrences.append((exclusion, start, end, {'id': exclusion['id'], 'start': original_start, 'end': original_end, 'surface': sentence[original_start:original_end]}))
        for lexeme, pattern, forms in self._lexemes:
            accepted = []
            for start, end, normalized_form in _occurrences(pattern, text):
                original_start, original_end = (offsets[start][0], offsets[end - 1][1])
                hit = {'lexeme_id': lexeme['id'], 'label': lexeme['label'], 'form': forms[normalized_form], 'normalized_form': normalized_form, 'surface': sentence[original_start:original_end], 'start': original_start, 'end': original_end, 'normalized_start': start, 'normalized_end': end}
                # Ein lokaler Ausschluss betrifft nur benannte Lexeme an
                # überlappenden Positionen. Andere Vorkommen bleiben zulässig.
                matches = [details for exclusion, e_start, e_end, details in exclusion_occurrences if lexeme['id'] in exclusion['lexeme_ids'] and start < e_end and (e_start < end)]
                if matches:
                    blocked.append({**hit, 'exclusion_ids': [item['id'] for item in matches], 'exclusions': matches})
                else:
                    accepted.append(hit)
            hits[lexeme['id']] = accepted
        direct_ids = []
        cooccurrence_ids = []
        evidence = []
        category_hits = set()
        for rule in self.dictionary['direct_rules']:
            matches = hits[rule['lexeme_id']]
            if matches:
                direct_ids.append(rule['id'])
                category_hits.add(rule['category'])
                evidence.append({'rule_id': rule['id'], 'category': rule['category'], 'type': 'direct', 'matches': matches})
        # Mindestens ein Beleg pro Seite genügt. Reihenfolge und Zeichenabstand
        # sind bei diesen Satzregeln keine zusätzlichen Bedingungen.
        for rule in self.dictionary['cooccurrence_rules']:
            # A und B bezeichnen die beiden Lexemgruppen dieser Satzregel.
            # Beide müssen im Satz vorkommen, etwa Lieferkette und Störung.
            matches_a = [dict(hit, side='A') for ident in rule['any_a'] for hit in hits[ident]]
            matches_b = [dict(hit, side='B') for ident in rule['any_b'] for hit in hits[ident]]
            if matches_a and matches_b:
                cooccurrence_ids.append(rule['id'])
                category_hits.add(rule['category'])
                evidence.append({'rule_id': rule['id'], 'category': rule['category'], 'type': 'sentence_cooccurrence', 'matches': matches_a + matches_b})
        return {'sicherheit_resilienz': int(bool(evidence)), 'categories': [category['id'] for category in self.dictionary['categories'] if category['id'] in category_hits], 'direct_rule_ids': direct_ids, 'cooccurrence_rule_ids': cooccurrence_ids, 'evidence': evidence, 'blocked_hits': blocked}
