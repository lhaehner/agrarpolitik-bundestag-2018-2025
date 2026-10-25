#!/usr/bin/env python3
"""A&E-Auswahl und Themenklassifikation für bereits segmentierte Satzdateien.

Python 3.10+, ausschließlich Standardbibliothek. Aufruf aus dem Projektordner:
    python src/satzmatcher.py --input saetze.csv \
        --dictionaries dictionaries --output lauf/Satzmaster_Agrar_Ernaehrung.csv.gz

Die Eingabe ist die vollständige aufbereitete Satzbasis.

Der Ablauf arbeitet zeilenweise: A&E-Auswahl, drei unabhängige Themenprüfungen,
Export der 0/1-Zuordnungen und ihrer Belege. Der Laufnachweis neben der CSV hält
die verwendeten Dateien mit Prüfsummen und die Anzahlen der Sätze fest.
Die Satzsegmentierung muss bereits vor dem Aufruf abgeschlossen sein.

Die Eingabe wird vollständig gelesen. In den ausgegebenen Satzmaster gelangen
ausschließlich A&E-Sätze, einschließlich ihrer Metadaten und Themenzuordnungen.
Die Programme ae_matcher, oekologie_matcher, oekonomie_matcher und sr_matcher
übernehmen die fachlichen Regeln aus den vier JSON-Wörterbüchern.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import tempfile

from ae_matcher import Matcher as AgricultureMatcher
from oekologie_matcher import EcologyMatcher
from oekonomie_matcher import Matcher as EconomyMatcher
from sr_matcher import Matcher as SecurityMatcher
from source_spans import enrich_hit, mapped_normalize

DIMENSIONS = ("oekologie", "oekonomie", "sicherheit_resilienz")
DICTIONARY_FILES = {
    "agrar_ernaehrung": "Woerterbuch_Agrar_Ernaehrung.json",
    "oekologie": "Woerterbuch_Oekologie.json",
    "oekonomie": "Woerterbuch_Oekonomie.json",
    "sicherheit_resilienz": "Woerterbuch_Sicherheit_und_Resilienz.json",
}
AE_FIELDS = [
    "agrar_ernaehrung", "agrar_ernaehrung_hit_keys_json",
    "agrar_ernaehrung_hit_forms_json", "agrar_ernaehrung_evidence_count",
    "agrar_ernaehrung_hit_forms_original_json", "agrar_ernaehrung_hits_json",
    "agrar_ernaehrung_hit_count",
]


def compact(value):
    """Serialisiert strukturierte Trefferbelege platzsparend für eine CSV-Zelle."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def sha256(path):
    """Berechnet den Fingerabdruck der Dateibytes für den technischen Laufnachweis."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def open_csv(path, mode="r", compressed=None):
    """Öffnet UTF-8-CSV mit optionaler gzip-Kompression und Unterstützung für BOM."""
    if compressed is None:
        compressed = str(path).lower().endswith(".gz")
    opener = gzip.open if compressed else open
    return opener(path, mode + "t", encoding="utf-8-sig", newline="")


class SentenceMatcher:
    """Verbindet die vier Fachmatcher mit ihren jeweils eigenen Suchregeln.

    A&E entscheidet über die Aufnahme in den Satzmaster. Die drei Themenbereiche
    werden danach unabhängig geprüft. Mehrfachzuordnungen bleiben möglich.
    Normalisierung und Ausschlusslogik werden nicht zwischen Matchern übertragen.
    """

    def __init__(self, directory):
        """Lädt vier JSONs und legt die davon abhängigen Ausgabespalten fest."""
        self.paths = {
            name: Path(directory) / filename
            for name, filename in DICTIONARY_FILES.items()
        }
        self.dictionaries = {
            name: json.loads(path.read_text(encoding="utf-8-sig"))
            for name, path in self.paths.items()
        }
        self.ae = AgricultureMatcher(self.dictionaries["agrar_ernaehrung"])
        self.eco = EcologyMatcher(self.dictionaries["oekologie"])
        self.econ = EconomyMatcher.from_path(self.paths["oekonomie"])
        self.sr = SecurityMatcher(self.dictionaries["sicherheit_resilienz"])
        self.categories = {}
        for item in self.dictionaries["oekologie"]["categories"]:
            self.categories["oekologie_K" + str(item["id"])] = ("oekologie", item["id"])
        for item in self.dictionaries["oekonomie"]["gruppen"]:
            self.categories["oekonomie_" + item["id"]] = ("oekonomie", item["id"])
        for item in self.dictionaries["sicherheit_resilienz"]["categories"]:
            self.categories["sicherheit_resilienz_" + item["id"]] = (
                "sicherheit_resilienz", item["id"])
        self.families = {
            item["id"]: "oekonomie_familie_" + item["id"]
            for item in self.dictionaries["oekonomie"]["familien"]
        }
        self.hashes = {name: sha256(path) for name, path in self.paths.items()}
        self.topic_hashes = {
            name + "_dictionary_sha256": self.hashes[name] for name in DIMENSIONS
        }
        self.fields = [
            *AE_FIELDS, *DIMENSIONS, *self.categories, *self.families.values(),
            "dimensionen_anzahl", "dimensionen_mindestens_eine",
            "oekonomie_ohne_agrardieselfamilie",
            "oekonomie_ohne_agrardieselsaetze",
            *[name + "_trefferbegriffe_json" for name in DIMENSIONS],
            *[name + "_trefferformen_json" for name in DIMENSIONS],
            *self.topic_hashes,
            *[name + "_evidence_json" for name in DIMENSIONS],
        ]

    def match(self, sentence):
        """Liefert alle Ausgabefelder für einen A&E-Satz, sonst None.

        Die Trefferlisten erklären die Zuordnung. Sie sind keine zusätzlichen
        Beobachtungen. Für jeden Themenbereich und jede Kategorie zählt der
        Satz höchstens einmal, unabhängig von der Anzahl gefundener Begriffe.
        """
        agriculture = self.ae.classify(sentence)
        if not agriculture["flag"]:
            return None
        normalized, offsets = mapped_normalize(sentence)
        hits = [
            enrich_hit(sentence, normalized, offsets, hit)
            for hit in agriculture["hits"]
        ]
        # Familienzahl und Zahl einzelner Fundstellen sind verschiedene Größen.
        result = {
            "agrar_ernaehrung": 1,
            "agrar_ernaehrung_hit_keys_json": json.dumps(
                agriculture["keys"], ensure_ascii=False),
            "agrar_ernaehrung_hit_forms_json": json.dumps(
                agriculture["forms"], ensure_ascii=False),
            "agrar_ernaehrung_evidence_count": len(agriculture["families"]),
            "agrar_ernaehrung_hit_forms_original_json": json.dumps(
                sorted({hit["original_form"] for hit in hits}), ensure_ascii=False),
            "agrar_ernaehrung_hits_json": compact(hits),
            "agrar_ernaehrung_hit_count": len(hits),
        }
        eco, econ, sr = (
            self.eco.match(sentence), self.econ.match(sentence), self.sr.match(sentence)
        )
        flags = {
            "oekologie": eco["oekologie"],
            "oekonomie": econ["oek_treffer"],
            "sicherheit_resilienz": sr["sicherheit_resilienz"],
        }
        active_categories = {
            "oekologie": eco["categories"],
            "oekonomie": econ["gruppen"],
            "sicherheit_resilienz": sr["categories"],
        }
        # Die Bezugstexte der Positionen sind bewusst explizit: Die vier
        # Fachmatcher verwenden unterschiedliche Normalisierungen.
        for field in ("hits", "rejected"):
            for hit in eco[field]:
                if eco["normalized_text"][hit["start"]:hit["end"]] != hit["form"]:
                    raise ValueError("Ökologie: ungültige normalisierte Fundstelle.")
                hit["normalized_start"] = hit.pop("start")
                hit["normalized_end"] = hit.pop("end")
        eco = {
            "offset_reference": "normalized_text; Python indices; end exclusive",
            "original_text_offsets_available": False, **eco,
        }
        econ = {
            "forms_reference": "normalisierte vollständige Tokenformen",
            "original_text_offsets_available": False,
            "local_exclusion_offset_reference":
                "oekonomie_matcher.normalize(sent_text); Python indices; end exclusive",
            **econ,
        }
        sr = {
            "offset_reference": "sent_text; Python indices; end exclusive",
            "normalized_offsets_reference": "sr_matcher.normalize(sent_text)",
            **sr,
        }
        for evidence in sr["evidence"]:
            for hit in evidence["matches"]:
                if sentence[hit["start"]:hit["end"]] != hit["surface"]:
                    raise ValueError("Sicherheit und Resilienz: ungültige Originalfundstelle.")
        sr_surfaces = sorted({
            hit["surface"] for evidence in sr["evidence"] for hit in evidence["matches"]
        })
        sr_labels = sorted({
            hit["label"] for evidence in sr["evidence"] for hit in evidence["matches"]
        })
        result.update(flags)
        result.update({
            column: int(category in active_categories[dimension])
            for column, (dimension, category) in self.categories.items()
        })
        result.update({
            column: int(family in econ["familien"])
            for family, column in self.families.items()
        })
        # Die zwei Agrardiesel-Varianten sind zusätzliche Satzkennzeichnungen:
        # Die erste erhält andere Ökonomiefamilien in einem Agrardieselsatz.
        # Die zweite setzt dessen Ökonomiewert insgesamt auf null. Keine der
        # Varianten entfernt hier Zeilen oder verändert die Grundgesamtheit.
        # G7 ist die Kennung der Kategorie Agrardiesel und Rückvergütung im
        # mitgelieferten Ökonomie-Wörterbuch.
        result.update({
            "dimensionen_anzahl": sum(flags.values()),
            "dimensionen_mindestens_eine": int(any(flags.values())),
            "oekonomie_ohne_agrardieselfamilie": int(
                bool(set(econ["familien"]) - {"agrardiesel"})),
            "oekonomie_ohne_agrardieselsaetze": int(
                bool(flags["oekonomie"]) and "G7" not in econ["gruppen"]),
            "oekologie_trefferbegriffe_json": compact(eco["labels"]),
            "oekologie_trefferformen_json": compact(
                sorted({hit["form"] for hit in eco["hits"]})),
            "oekonomie_trefferbegriffe_json": compact([
                self.econ.families[family].get("name", family)
                for family in econ["familien"]
            ]),
            "oekonomie_trefferformen_json": compact(econ["formen"]),
            "sicherheit_resilienz_trefferbegriffe_json": compact(sr_labels),
            "sicherheit_resilienz_trefferformen_json": compact(sr_surfaces),
            "oekologie_evidence_json": compact(eco),
            "oekonomie_evidence_json": compact(econ),
            "sicherheit_resilienz_evidence_json": compact(sr),
            **self.topic_hashes,
        })
        return result


def derived_field(name):
    """Erkennt berechnete Spalten, damit keine Eingabezuordnung übernommen wird.

    Der neue Satzmaster enthält ausschließlich Zuordnungen aus diesem Lauf.
    Text und Metadaten der vollständigen Satzbasis werden weiterhin übernommen.
    """
    prefixes = ("agrar_ernaehrung", *DIMENSIONS, "dimensionen")
    return any(name == prefix or name.startswith(prefix + "_") for prefix in prefixes)


def run(source, destination, dictionaries, delimiter=";"):
    """Filtert die vollständige Satzbasis und schreibt Satzmaster und Laufnachweis.

    Die Gesamtzahlen je Jahr werden vor der A&E-Auswahl ermittelt. Sie beziehen
    sich auf alle Sätze der Eingabedatei und bilden die Basis der Politikfeldanteile.
    """
    if delimiter not in {";", ",", "\t"}:
        raise ValueError("Trennzeichen muss Semikolon, Komma oder Tabulator sein.")
    source, destination = Path(source), Path(destination)
    manifest_path = destination.with_name(destination.name + ".manifest.json")
    if destination.resolve() == source.resolve():
        raise ValueError("Eingabe und Ausgabe müssen verschieden sein.")
    if destination.exists() or manifest_path.exists():
        raise FileExistsError("Ausgabe oder Laufprotokoll existiert bereits: " + str(destination))
    csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
    matcher = SentenceMatcher(dictionaries)
    totals = Counter()
    years = {}
    sentence_ids, source_ids = set(), set()
    temporary = None
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open_csv(source) as handle:
            reader = csv.DictReader(handle, delimiter=delimiter)
            source_fields = reader.fieldnames or []
            if not source_fields or len(set(source_fields)) != len(source_fields):
                raise ValueError("CSV-Kopf fehlt oder enthält doppelte Spaltennamen.")
            required = {"rede_id", "sent_idx", "sent_text", "sitzung_jahr"}
            missing = required - set(source_fields)
            if missing:
                raise ValueError("Fehlende CSV-Spalten: " + ", ".join(sorted(missing)))
            # Metadaten und Originaltext übernehmen. Berechnete Zuordnungen
            # ergeben sich vollständig aus diesem Wörterbuchlauf.
            base_fields = [key for key in source_fields if not derived_field(key)]
            if "satz_id" not in base_fields:
                base_fields.append("satz_id")
            fields = base_fields + matcher.fields
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=".satzmatcher_", suffix=".tmp", dir=destination.parent)
            os.close(descriptor)
            temporary = Path(temporary_name)
            with open_csv(temporary, "w", str(destination).lower().endswith(".gz")) as target:
                writer = csv.DictWriter(target, fieldnames=fields, delimiter=";")
                writer.writeheader()
                for row_number, row in enumerate(reader, 2):
                    if None in row or any(value is None for value in row.values()):
                        raise ValueError(f"Zeile {row_number}: unvollständige/überzählige Felder.")
                    # Doppelte Satzkennungen würden Häufigkeiten verzerren.
                    # Sowohl der natürliche Schlüssel als auch die Export-ID
                    # werden deshalb innerhalb der gesamten Eingabe geprüft.
                    identity = (row["rede_id"], row["sent_idx"])
                    if not all(value.strip() for value in identity) or identity in source_ids:
                        raise ValueError(f"Zeile {row_number}: fehlende/doppelte Satzkennung.")
                    source_ids.add(identity)
                    sentence_id = row.get("satz_id", ":".join(identity))
                    if not sentence_id.strip() or sentence_id in sentence_ids:
                        raise ValueError(f"Zeile {row_number}: fehlende/doppelte satz_id.")
                    sentence_ids.add(sentence_id)
                    if not row["sent_text"].strip() or not row["sitzung_jahr"].strip():
                        raise ValueError(f"Zeile {row_number}: Satztext oder Jahr fehlt.")
                    # Vor der A&E-Auswahl zählen: Nur bei vollständiger Eingabe
                    # entstehen so die Gesamtzahlen der Plenarsätze je Jahr.
                    totals["eingabe_saetze"] += 1
                    year_totals = years.setdefault(row["sitzung_jahr"], Counter())
                    year_totals["eingabe_saetze"] += 1
                    result = matcher.match(row["sent_text"])
                    if result is None:
                        continue
                    out = {key: row.get(key, "") for key in base_fields}
                    out["satz_id"] = sentence_id
                    out.update(result)
                    writer.writerow(out)
                    counts = {"agrar_ernaehrung": 1}
                    counts.update({name: result[name] for name in DIMENSIONS})
                    totals.update(counts)
                    year_totals.update(counts)
        if not totals["eingabe_saetze"]:
            raise ValueError("Die CSV enthält keine Sätze.")
        # Den fertigen CSV-Export erneut einlesen, bevor die Zieldatei erscheint.
        # Die temporäre Datei vermeidet einen scheinbar vollständigen Export
        # bei einem vorzeitigen Fehler in der zeilenweisen Verarbeitung.
        with open_csv(temporary, compressed=str(destination).lower().endswith(".gz")) as check:
            verified = sum(1 for _ in csv.DictReader(check, delimiter=";"))
        if verified != totals["agrar_ernaehrung"]:
            raise ValueError("Exportprüfung: abweichende Zeilenzahl.")
        # Prüfsummen kennzeichnen exakt verwendete Bytes. Bereits reine
        # Kommentaränderungen am Code erzeugen daher neue Code-Prüfsummen,
        # auch wenn sich fachliche Zuordnungen nicht ändern.
        manifest = {
            "eingabemodus": "full-corpus",
            "aussagebereich": "A&E-Auswahl innerhalb der vollständigen aufbereiteten Satzbasis.",
            "input": {"file": source.name, "sha256": sha256(source)},
            "output": {"file": destination.name, "sha256": sha256(temporary)},
            "python": platform.python_version(),
            "dictionaries": {
                name: {"file": path.name, "sha256": matcher.hashes[name]}
                for name, path in matcher.paths.items()
            },
            "code_sha256": {
                name: sha256(Path(__file__).parent / name)
                for name in (
                    "ae_matcher.py", "oekologie_matcher.py",
                    "oekonomie_matcher.py", "sr_matcher.py",
                    "source_spans.py", "satzmatcher.py",
                )
            },
            "counts": dict(totals),
            "years": {year: dict(values) for year, values in sorted(years.items())},
            "export_verified_rows": verified,
            "csv_format": "UTF-8 mit BOM; Semikolon; eine Zeile je A&E-Satz",
            "span_convention": (
                "Python-Zeichenindizes, Ende exklusiv. A&E und S&R: "
                "Original- und normalisierte Positionen. Ökologie: "
                "normalisierte Positionen. Ökonomie: Formen, nur lokale "
                "Ausschlüsse mit normalisierten Positionen."
            ),
        }
        os.replace(temporary, destination)
        temporary = None
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return manifest


def main():
    """Liest Kommandozeilenargumente und meldet Ergebnisdateien oder Eingabefehler."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True, type=Path, help="Satzdatei .csv oder .csv.gz")
    parser.add_argument("--output", required=True, type=Path, help="Neue Datei .csv oder .csv.gz")
    parser.add_argument("--dictionaries", default=Path("dictionaries"), type=Path)
    parser.add_argument("--delimiter", default=";", help="Eingabetrennzeichen; Standard: ;")
    args = parser.parse_args()
    try:
        manifest = run(args.input, args.output, args.dictionaries, args.delimiter)
    except (ValueError, KeyError, TypeError, OSError, csv.Error) as error:
        parser.exit(2, f"Fehler: {error}\n")
    print(json.dumps(manifest["counts"], ensure_ascii=False, indent=2))
    print("Satzmaster:", args.output)
    print("Laufprotokoll:", str(args.output) + ".manifest.json")


if __name__ == "__main__":
    main()
