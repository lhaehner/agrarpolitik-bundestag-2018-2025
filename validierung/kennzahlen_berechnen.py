#!/usr/bin/env python3
"""Gütemaße und zeitliche Blockprüfung aus den vorhandenen Handcodierungen.

Die Fall-ID verbindet Codierungen und Schlüsselblatt. (rede_id, sent_idx)
verknüpft diese Fälle mit den maschinellen Zuordnungen im Satzmaster. Die
vollständige Satzbasis liefert die Bestandsgrößen und bestätigt die Zuordnung
der beiden Stichproben zu Filtertreffern beziehungsweise Nichttreffern.

Das Programm verändert weder Codierungen noch Wörterbücher. Es verwendet
ausschließlich die Python-Standardbibliothek und schreibt eine lesbare CSV
sowie einen maschinenlesbaren Berechnungsbericht in neue Dateien.
"""

import argparse
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import posixpath
import re
from statistics import NormalDist
import xml.etree.ElementTree as ET
from zipfile import ZipFile


NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
THEMES = {
    "Ökologie": "oekologie",
    "Ökonomie": "oekonomie",
    "Sicherheit & Resilienz": "sicherheit_resilienz",
}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_xlsx(path):
    """Zellinhalte der drei vorhandenen Prüfblätter ohne Excel lesen.

    Formeln werden nicht ausgewertet: Codierungen, Schlüssel und Angaben zur
    abgeschlossenen Durchsicht müssen unmittelbar gespeicherte Werte sein.
    """
    result = {}
    with ZipFile(path) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(item.itertext()) for item in strings]
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {
            item.get("Id"): item.get("Target") for item in relationships
            if item.get("TargetMode") != "External"
        }
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        for sheet in workbook.findall("x:sheets/x:sheet", NS):
            name = sheet.get("name")
            if name not in {"Prüfung", "Schlüssel", "Hinweise"}:
                continue
            target = targets[sheet.get("{" + REL + "}id")]
            target = target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/" + target)
            cells = {}
            root = ET.fromstring(archive.read(target))
            for cell in root.findall("x:sheetData/x:row/x:c", NS):
                if cell.find("x:f", NS) is not None:
                    continue
                kind = cell.get("t")
                value = cell.find("x:v", NS)
                text = "" if value is None else value.text or ""
                if kind == "s":
                    text = shared[int(text)]
                elif kind == "inlineStr":
                    text = "".join(t.text or "" for t in cell.findall(".//x:t", NS))
                cells[cell.get("r")] = text
            result[name] = cells
    if set(result) != {"Prüfung", "Schlüssel", "Hinweise"}:
        raise ValueError(f"{Path(path).name}: Prüfung, Schlüssel oder Hinweise fehlt.")
    return result


def table_rows(cells, columns):
    """Eine Tabelle an ihren Spaltenüberschriften erkennen, nicht am Dateistand."""
    row_numbers = sorted({int(re.search(r"\d+$", address)[0]) for address in cells})
    header = next((number for number in row_numbers if cells.get(f"A{number}") == "Fall-ID"), None)
    if header is None:
        raise ValueError("Tabellenkopf Fall-ID fehlt.")
    positions = {}
    for address, text in cells.items():
        if int(re.search(r"\d+$", address)[0]) == header and text in columns:
            positions[text] = re.match(r"[A-Z]+", address)[0]
    if set(positions) != set(columns):
        raise ValueError(f"Fehlende Spalten: {sorted(set(columns) - set(positions))}")
    return [{name: cells.get(f"{column}{number}", "") for name, column in positions.items()}
            for number in row_numbers if number > header and cells.get(f"A{number}")]


def integer(value, label):
    if not re.fullmatch(r"\d+(?:\.0+)?", str(value)):
        raise ValueError(f"{label}: ungültige Ganzzahl {value!r}.")
    return int(float(value))


def text_equal(left, right):
    # Word/Excel können geschützte Leerzeichen und Zeilenumbrüche anders ablegen.
    # Wortlaut und Zeichensetzung werden nicht verändert.
    return " ".join(left.split()) == " ".join(right.split())


def read_sample(path, with_themes):
    book = read_xlsx(path)
    if not with_themes and book["Hinweise"].get("B4") != "Ja":
        raise ValueError("Die vollständige Durchsicht der Nichttreffer ist nicht bestätigt.")
    fields = ["Fall-ID", "Satz", "Agrar & Ernährung", *(THEMES if with_themes else [])]
    judgments = table_rows(book["Prüfung"], fields)
    keys = table_rows(book["Schlüssel"], ["Fall-ID", "Satz-ID", "Rede-ID", "Satzindex", "Jahr", "Dokument-ID"])
    lookup = {}
    for row in keys:
        if row["Fall-ID"] in lookup:
            raise ValueError(f"Doppelte Fall-ID im Schlüssel: {row['Fall-ID']}")
        lookup[row["Fall-ID"]] = row
    sample = {}
    seen_cases = set()
    for row in judgments:
        case = row["Fall-ID"]
        if case in seen_cases or case not in lookup:
            raise ValueError(f"Doppelte Fall-ID oder fehlender Schlüssel: {case}")
        seen_cases.add(case)
        meta = lookup[case]
        key = (meta["Rede-ID"], integer(meta["Satzindex"], case))
        if key in sample or not key[0] or meta["Satz-ID"] != f"{key[0]}:{key[1]}":
            raise ValueError(f"Doppelter oder widersprüchlicher Satzschlüssel: {case}")
        labels = {}
        for field in fields[2:]:
            if row[field] not in {"Ja", "Nein"}:
                raise ValueError(f"{case}, {field}: vollständige Ja-/Nein-Codierung erforderlich.")
            labels[field] = row[field] == "Ja"
        if not row["Satz"]:
            raise ValueError(f"{case}: Satztext fehlt.")
        sample[key] = {"case": case, "text": row["Satz"], "labels": labels,
                       "year": integer(meta["Jahr"], case), "doc_id": meta["Dokument-ID"]}
    if seen_cases != set(lookup) or not sample:
        raise ValueError("Codierungen und Schlüssel enthalten unterschiedliche oder keine Fälle.")
    return sample, book["Hinweise"]


def csv_rows(path):
    opener = gzip.open if Path(path).suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        if not {"rede_id", "sent_idx", "sent_text", "sitzung_jahr", "doc_id"}.issubset(reader.fieldnames or []):
            raise ValueError(f"{Path(path).name}: erforderliche Satzspalten fehlen.")
        yield from reader


def sentence_key(row):
    if not row["rede_id"]:
        raise ValueError("Leere Rede-ID.")
    return row["rede_id"], integer(row["sent_idx"], "Satzindex")


def check_sentence(sample, row):
    if (not text_equal(sample["text"], row["sent_text"])
            or sample["year"] != integer(row["sitzung_jahr"], "Jahr")
            or sample["doc_id"] != row["doc_id"]):
        raise ValueError(f"Satztext oder Metadaten abweichend: {sample.get('case', sentence_key(row))}")


def wilson(successes, total):
    """Zweiseitiges 95-Prozent-Wilson-Intervall eines binomialen Anteils."""
    if total <= 0 or not 0 <= successes <= total:
        raise ValueError("Wilson-Intervall benötigt 0 <= Treffer <= Umfang und Umfang > 0.")
    p = successes / total
    z = NormalDist().inv_cdf(0.975)
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    half_width = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [max(0.0, center - half_width), min(1.0, center + half_width)]


def classification_counts(sample, master, label, field):
    """Manuelle und maschinelle Zuordnung derselben Prüfsätze vergleichen."""
    counts = {"TP": 0, "FP": 0, "FN": 0, "TN": 0}
    for key, human in sample.items():
        machine = master[key]["flags"][field]
        manual = human["labels"][label]
        counts["TP" if machine and manual else "FP" if machine else "FN" if manual else "TN"] += 1
    return counts


def block_validation(sample, master):
    """Die Themenstichprobe nach Satzjahr aufteilen, ohne neue Codierung.

    Die wirtschaftlichen Anteile haben jeweils alle Prüfsätze des Blocks
    als Nenner. Sie sind Stichprobenwerte, keine Neuberechnung der Anteile
    im gesamten A&E-Korpus. Die Veränderung ist in Prozentpunkten angegeben.
    """
    if any(not 2018 <= row["year"] <= 2025 for row in sample.values()):
        raise ValueError("Die Blockprüfung setzt Satzjahre von 2018 bis 2025 voraus.")
    blocks = []
    for start, end in [(2018, 2021), (2022, 2025)]:
        subset = {key: row for key, row in sample.items() if start <= row["year"] <= end}
        if not subset:
            raise ValueError(f"Keine Prüfsätze im Zeitraum {start}–{end}.")
        themes = []
        for label, field in THEMES.items():
            counts = classification_counts(subset, master, label, field)
            relevant = counts["TP"] + counts["FN"]
            if relevant == 0:
                raise ValueError(f"{start}–{end}, {label}: keine manuell zugeordneten Prüfsätze.")
            themes.append({"themenbereich": label.replace(" & ", " und "), **counts,
                           "recall": counts["TP"] / relevant,
                           "recall_ki95": wilson(counts["TP"], relevant)})
        economy = next(theme for theme in themes if theme["themenbereich"] == "Ökonomie")
        manual = economy["TP"] + economy["FN"]
        machine = economy["TP"] + economy["FP"]
        blocks.append({"zeitraum": f"{start}–{end}", "geprueft": len(subset), "themen": themes,
                       "oekonomie": {"handcodierung_anzahl": manual, "woerterbuch_anzahl": machine,
                                     "handcodierung_anteil": manual / len(subset),
                                     "woerterbuch_anteil": machine / len(subset)}})
    first, second = blocks
    change = {"von": first["zeitraum"], "bis": second["zeitraum"]}
    for method in ["handcodierung", "woerterbuch"]:
        change[method + "_prozentpunkte"] = 100 * (
            second["oekonomie"][method + "_anteil"] - first["oekonomie"][method + "_anteil"])
    return {"bloecke": blocks, "veraenderung_oekonomie": change}


def calculate(master_path, basis_path, theme_path, recall_path):
    sample, theme_notes = read_sample(theme_path, True)
    nonhits, recall_notes = read_sample(recall_path, False)
    if set(sample) & set(nonhits):
        raise ValueError("Treffer- und Nichttrefferstichprobe überschneiden sich.")
    master = {}
    for row in csv_rows(master_path):
        key = sentence_key(row)
        if key in master or row.get("agrar_ernaehrung") != "1":
            raise ValueError("Doppelter Satzschlüssel oder Nichttreffer im A&E-Satzmaster.")
        flags = {}
        for field in THEMES.values():
            if row.get(field) not in {"0", "1"}:
                raise ValueError(f"Ungültige maschinelle Zuordnung: {key}, {field}")
            flags[field] = row[field] == "1"
        master[key] = {"text": row["sent_text"], "year": integer(row["sitzung_jahr"], "Jahr"),
                       "doc_id": row["doc_id"], "flags": flags}
        if key in sample:
            check_sentence(sample[key], row)
    if not set(sample) <= set(master) or set(nonhits) & set(master):
        raise ValueError("Stichproben passen nicht zur Treffer-/Nichttrefferauswahl des Satzmasters.")
    # Die Vollbasis wird einmal gestreamt. Nur Schlüssel des Masters und der
    # Nichttrefferstichprobe werden gespeichert; ihr Wortlaut wird abgeglichen.
    found = set()
    population = 0
    for row in csv_rows(basis_path):
        population += 1
        key = sentence_key(row)
        expected = master.get(key) or nonhits.get(key)
        if expected is not None:
            if key in found:
                raise ValueError(f"Mehrfacher Schlüssel in der Satzbasis: {key}")
            found.add(key)
            check_sentence(expected, row)
    if found != set(master) | set(nonhits):
        raise ValueError("Satzbasis enthält nicht alle Master- und Nichttrefferstichprobenschlüssel.")
    m = len(master)
    u = population - m
    # Gespeicherte Ziehungsangaben sind Kontrollen, keine Recheninputs.
    checks = [(theme_notes.get("B18"), m), (theme_notes.get("B20"), len(sample)),
              (recall_notes.get("B8"), len(nonhits)), (recall_notes.get("B20"), population),
              (recall_notes.get("B21"), m), (recall_notes.get("B22"), u)]
    if any(integer(stated, "Ziehungsangabe") != actual for stated, actual in checks):
        raise ValueError("Stichproben oder Bestandsgrößen weichen vom dokumentierten Auswahlrahmen ab.")
    themes = []
    for label, field in THEMES.items():
        counts = classification_counts(sample, master, label, field)
        tp, fp, fn = counts["TP"], counts["FP"], counts["FN"]
        themes.append({"themenbereich": label.replace(" & ", " und "), **counts,
                       "praezision": tp / (tp + fp), "praezision_ki95": wilson(tp, tp + fp),
                       "recall": tp / (tp + fn), "recall_ki95": wilson(tp, tp + fn)})
    confirmed = sum(row["labels"]["Agrar & Ernährung"] for row in sample.values())
    overlooked = sum(row["labels"]["Agrar & Ernährung"] for row in nonhits.values())
    precision = confirmed / len(sample)
    missed_fraction = overlooked / len(nonhits)
    missed_ci = wilson(overlooked, len(nonhits))
    estimated_tp = m * precision
    # Wie in Abschnitt 3.5 wird die beobachtete Trefferpräzision bei der
    # Rücktransformation als fest angenommen. Es ist kein gemeinsames Intervall
    # für die Unsicherheit beider Stichproben. Recall sinkt mit der Fehlmenge,
    # daher werden die Wilson-Grenzen in umgekehrter Reihenfolge eingesetzt.
    def recall_at(rate):
        return estimated_tp / (estimated_tp + u * rate)
    if estimated_tp <= 0:
        raise ValueError("Recall-Schätzung benötigt bestätigte A&E-Treffer.")
    field = {
        "erfasst": {"bestand": m, "geprueft": len(sample), "ae_nach_codebuch": confirmed,
                    "anteil": precision, "ki95": wilson(confirmed, len(sample))},
        "nicht_erfasst": {"bestand": u, "geprueft": len(nonhits), "ae_nach_codebuch": overlooked,
                          "anteil": missed_fraction, "ki95": missed_ci},
        "hochgerechnete_bestaetigte_treffer": estimated_tp,
        "hochgerechnete_uebersehene_saetze": u * missed_fraction,
        "recall": recall_at(missed_fraction),
        "recall_ki95": [recall_at(missed_ci[1]), recall_at(missed_ci[0])],
        "intervall_annahme": "Beobachtete Trefferpräzision bei Rücktransformation als fest angenommen.",
    }
    return {"population": {"plenarsaetze": population, "ae_saetze": m, "nichttreffer": u},
            "stichproben": {"themen": len(sample), "nichttreffer": len(nonhits)},
            "themen": themes, "politikfeld": field, "blockvalidierung": block_validation(sample, master),
            "pruefungen": {"codierungen_vollstaendig": True, "fall_und_satzschluessel_eindeutig": True,
                           "stichproben_passend_zum_filterstatus": True,
                           "satztexte_und_metadaten_abgeglichen": True,
                           "master_und_nichttreffer_in_satzbasis": True,
                           "auswahlrahmen_passend_zu_ziehungsvermerken": True}}


def write_csv(path, result):
    """Prozentwerte mit Dezimalkomma; Zählwerte bleiben separate Spalten."""
    columns = ["Bezug", "Bereich", "Kennzahl", "Bestand", "Geprüft", "TP", "FP", "FN", "TN",
               "Zähler", "Nenner", "Wert_in_Prozent", "KI95_unten_in_Prozent", "KI95_oben_in_Prozent",
               "Hochgerechnete_übersehene_Sätze", "Zeitraum", "Wert_in_Prozentpunkten"]
    records = []
    def rate_values(value, interval):
        return {name: f"{100 * number:.8f}".rstrip("0").rstrip(".").replace(".", ",")
                for name, number in zip(columns[11:14], [value, *interval])}
    for theme in result["themen"]:
        for key, label, denominator in [("praezision", "Präzision", theme["TP"] + theme["FP"]),
                                         ("recall", "Trefferquote", theme["TP"] + theme["FN"])]:
            records.append({"Bezug": "Tabelle 5", "Bereich": theme["themenbereich"], "Kennzahl": label,
                            "Geprüft": result["stichproben"]["themen"],
                            **{k: theme[k] for k in ["TP", "FP", "FN", "TN"]},
                            "Zähler": theme["TP"], "Nenner": denominator,
                            **rate_values(theme[key], theme[key + "_ki95"])})
    for key, label in [("erfasst", "vom Filter erfasst"), ("nicht_erfasst", "vom Filter nicht erfasst")]:
        field = result["politikfeld"][key]
        records.append({"Bezug": "Tabelle 6", "Bereich": label, "Kennzahl": "A&E-Anteil laut Handcodierung",
                        "Bestand": field["bestand"], "Geprüft": field["geprueft"],
                        "Zähler": field["ae_nach_codebuch"], "Nenner": field["geprueft"],
                        **rate_values(field["anteil"], field["ki95"])})
    field = result["politikfeld"]
    records.append({"Bezug": "Abschnitt 3.5", "Bereich": "Politikfeldfilter", "Kennzahl": "Geschätzte Trefferquote",
                    "Bestand": result["population"]["plenarsaetze"],
                    "Hochgerechnete_übersehene_Sätze": str(round(field["hochgerechnete_uebersehene_saetze"], 6)).replace(".", ","),
                    **rate_values(field["recall"], field["recall_ki95"])})
    for block in result["blockvalidierung"]["bloecke"]:
        for theme in block["themen"]:
            records.append({"Bezug": "Abschnitt 3.5", "Bereich": theme["themenbereich"],
                            "Kennzahl": "Trefferquote im Vierjahresblock", "Zeitraum": block["zeitraum"],
                            "Geprüft": block["geprueft"],
                            **{k: theme[k] for k in ["TP", "FP", "FN", "TN"]},
                            "Zähler": theme["TP"], "Nenner": theme["TP"] + theme["FN"],
                            **rate_values(theme["recall"], theme["recall_ki95"])})
        for method, label in [("handcodierung", "Handcodierung"), ("woerterbuch", "Wörterbuchzuordnung")]:
            records.append({"Bezug": "Abschnitt 5.4", "Bereich": "Ökonomie",
                            "Kennzahl": "Stichprobenanteil nach " + label, "Zeitraum": block["zeitraum"],
                            "Geprüft": block["geprueft"], "Zähler": block["oekonomie"][method + "_anzahl"],
                            "Nenner": block["geprueft"],
                            **rate_values(block["oekonomie"][method + "_anteil"], [])})
    change = result["blockvalidierung"]["veraenderung_oekonomie"]
    for method, label in [("handcodierung", "Handcodierung"), ("woerterbuch", "Wörterbuchzuordnung")]:
        records.append({"Bezug": "Abschnitt 5.4", "Bereich": "Ökonomie",
                        "Kennzahl": "Veränderung des Stichprobenanteils nach " + label,
                        "Zeitraum": change["von"] + " → " + change["bis"],
                        "Wert_in_Prozentpunkten": f"{change[method + '_prozentpunkte']:.8f}".rstrip("0").rstrip(".").replace(".", ",")})
    with Path(path).open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter=";")
        writer.writeheader()
        writer.writerows(records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["satzmaster", "satzbasis", "validierung-themen", "validierung-recall", "output", "report"]:
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    inputs = [args.satzmaster, args.satzbasis, args.validierung_themen, args.validierung_recall]
    outputs = [args.output, args.report]
    if len({p.resolve() for p in [*inputs, *outputs]}) != 6 or any(p.exists() for p in outputs):
        parser.error("Eingaben und Ausgaben müssen getrennt sein; Ausgabedateien dürfen noch nicht existieren.")
    result = calculate(args.satzmaster, args.satzbasis, args.validierung_themen, args.validierung_recall)
    for path in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
    result.update({"status": "validierungskennzahlen_berechnet", "master_sha256": sha256(args.satzmaster),
                   "satzbasis_sha256": sha256(args.satzbasis),
                   "validierung_themen_sha256": sha256(args.validierung_themen),
                   "validierung_recall_sha256": sha256(args.validierung_recall)})
    write_csv(args.output, result)
    result["ausgabe_sha256"] = sha256(args.output)
    with args.report.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    print(f"Validierungskennzahlen berechnet: {args.output}")
    print(f"Themenstichprobe: {result['stichproben']['themen']}; Nichttrefferstichprobe: {result['stichproben']['nichttreffer']}")
    print(f"Geschätzte Trefferquote des Politikfeldfilters: {100 * result['politikfeld']['recall']:.1f} %")


if __name__ == "__main__":
    main()
