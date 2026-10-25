#!/usr/bin/env python3
"""Prüft den neu berechneten Satzmaster gegen den festgelegten Analysebestand.

Eingaben sind der Satzmaster als CSV/gzip-CSV und referenz_satzmaster.json.
Die Referenz enthält die erwartete Spaltenfolge, einen Inhaltsfingerabdruck und
Satzanzahlen. Bei Übereinstimmung entsteht eine JSON-Datei mit dem Prüfergebnis.
Bei einer Abweichung bricht das Programm ab, ohne einen Erfolgsbericht anzulegen.

Texte, Metadaten, Kennungen, Klassifikationen und Trefferbelege müssen in den
festgelegten Prüffeldern übereinstimmen. JSON-Belege werden als Daten verglichen.
Die drei zusätzlichen Prüfsummen-Spalten der Themenwörterbücher gehören nicht
zum Inhaltsvergleich. Das Laufprotokoll der Wörterbuchanwendung enthält die
Prüfsummen der verwendeten Wörterbuchdateien.

Dies ist ein technischer Vergleich mit dem festgelegten A&E-Endbestand.
Die Prüfung ersetzt keine inhaltliche Validierung durch menschliche Kodierungen.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import gzip
import hashlib
import json
from pathlib import Path


def pruefen(satzmaster: Path, referenzdatei: Path) -> dict:
    """Vergleicht CSV-Inhalte zeilenweise über eine feste, reproduzierbare Darstellung.

    Die Referenz legt Spalten, Prüffelder, erwarteten Inhaltsfingerabdruck und
    Themensummen fest. Die Reihenfolge der Zeilen ist Bestandteil des Vergleichs.
    CSV-Verpackung (gzip/BOM) und die Reihenfolge von JSON-Objektschlüsseln dürfen
    abweichen. Die Reihenfolge von JSON-Listen und CSV-Zeilen bleibt dagegen relevant.
    """
    referenz = json.loads(referenzdatei.read_text(encoding="utf-8"))
    digest, counts = hashlib.sha256(), Counter()
    felder = referenz["prueffelder"]
    # Unkomprimierte CSV und gzip-CSV werden gleich behandelt. utf-8-sig akzeptiert
    # den optionalen BOM, der insbesondere den Import in Excel erleichtert.
    opener = gzip.open if satzmaster.suffix == ".gz" else open
    with opener(satzmaster, "rt", encoding="utf-8-sig", newline="") as datei:
        reader = csv.DictReader(datei, delimiter=";")
        if reader.fieldnames != referenz["ausgabespalten"]:
            raise ValueError("Der Satzmaster hat andere Ausgabespalten.")
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"Unvollständige CSV-Zeile: {reader.line_num}")
            # JSON-Belege als Daten vergleichen: Ein anderer Leerraum oder eine
            # andere Schlüsselreihenfolge allein bedeutet keinen anderen Treffer.
            werte = [json.loads(row[k]) if k.endswith("_json") else row[k]
                     for k in felder]
            digest.update(json.dumps(werte, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8") + b"\n")
            counts["agrar_ernaehrung"] += 1
            # Jede Zeile des gefilterten Satzmasters zählt einmal für A&E.
            # Die drei 0/1-Themenspalten werden unabhängig summiert. Überschneidungen
            # bleiben erhalten und ihre Summe ist daher keine Zahl eindeutiger Sätze.
            for thema in ("oekologie", "oekonomie", "sicherheit_resilienz"):
                counts[thema] += int(row[thema])
    beobachtet = {"satzinhalt_sha256": digest.hexdigest(), "anzahlen": dict(counts)}
    if beobachtet != referenz["erwartet"]:
        raise ValueError("Der neu erzeugte Satzmaster weicht vom Endstand ab: "
                         + json.dumps(beobachtet, ensure_ascii=False))
    return {"status": "gespeicherter_satzmaster_inhaltsgleich",
            "gepruefte_felder_je_satz": len(felder), **beobachtet}


def main():
    """Prüft einen Satzmaster und speichert bei Erfolg einen neuen Prüfbericht."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--satzmaster", type=Path, required=True)
    parser.add_argument("--referenz", type=Path,
                        default=Path(__file__).with_name("referenz_satzmaster.json"))
    parser.add_argument("--protokoll", type=Path, required=True)
    args = parser.parse_args()
    if args.protokoll.exists():
        raise FileExistsError(args.protokoll)
    # Erst nach erfolgreichem Vergleich wird das Protokoll angelegt. Vorhandene
    # Nachweise werden nicht überschrieben und Abweichungen brechen den Lauf ab.
    ergebnis = pruefen(args.satzmaster, args.referenz)
    args.protokoll.write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2)
                             + "\n", encoding="utf-8")
    print(json.dumps(ergebnis, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
