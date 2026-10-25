"""Hilfsfunktionen für die Bedienung und die Ergebnisse des Colab-Notebooks.

Die fachlichen Regeln stehen in den Wörterbüchern und den Skripten der Ordner
``korpusaufbereitung``, ``src`` und ``auswertung``. Dieses Modul verändert diese
Regeln nicht. Es lädt die festgelegte Quelldatei und stellt fertige Ergebnisse
zusammen.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any
from urllib.request import Request, urlopen
import zipfile


WOERTERBUCH_DATEIEN = {
    "agrar_ernaehrung": "Woerterbuch_Agrar_Ernaehrung.json",
    "oekologie": "Woerterbuch_Oekologie.json",
    "oekonomie": "Woerterbuch_Oekonomie.json",
    "sicherheit_resilienz": "Woerterbuch_Sicherheit_und_Resilienz.json",
}
BEZEICHNUNGEN = {
    "agrar_ernaehrung": "Agrar und Ernährung",
    "oekologie": "Ökologie",
    "oekonomie": "Ökonomie",
    "sicherheit_resilienz": "Sicherheit und Resilienz",
}


def datei_sha256(datei: str | Path) -> str:
    """Liest auch große Dateien blockweise, ohne sie vollständig zu laden."""
    sha = hashlib.sha256()
    with Path(datei).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def _json_objekt(quelle: str | Path | Mapping[str, Any]) -> dict[str, Any]:
    """Liest einen technischen Ergebnisbericht oder übernimmt dessen gelesene Felder."""
    if isinstance(quelle, Mapping):
        return dict(quelle)
    daten = json.loads(Path(quelle).read_text(encoding="utf-8-sig"))
    if not isinstance(daten, dict):
        raise ValueError(f"Erwartet wird ein JSON-Objekt: {Path(quelle).name}")
    return daten


def quelle_herunterladen(
    url: str,
    ziel: str | Path,
    *,
    erwartete_bytes: int,
    erwartete_md5: str,
) -> Path:
    """Lädt die Quellen-ZIP blockweise und prüft den festgelegten Zenodo-Stand.

    Dateigröße und MD5 stammen vom Zenodo-Dateieintrag. Sie erkennen einen
    unvollständigen Download oder eine andere Datei. Die Korpusaufbereitung
    prüft zusätzlich den SHA-256-Wert der entpackten Redendatei.
    Erst nach erfolgreicher Prüfung erhält der Download seinen endgültigen Namen.
    """
    ziel = Path(ziel)
    if ziel.exists():
        raise FileExistsError(f"Die Zieldatei existiert bereits: {ziel}")
    if erwartete_bytes <= 0 or len(erwartete_md5) != 32:
        raise ValueError("Dateigröße und MD5 der festgelegten Quelle fehlen.")
    ziel.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".quelle_", suffix=".part", dir=ziel.parent)
    zwischen = Path(name)
    anzahl = 0
    meldeschritt = 10 * 1024 * 1024
    naechste_meldung = meldeschritt
    try:
        # Die Datei bleibt während des Downloads außerhalb des Arbeitsspeichers.
        anfrage = Request(url, headers={"User-Agent": "Agrarpolitik-Reproduktion/1.0"})
        with os.fdopen(descriptor, "wb") as ausgabe:
            with urlopen(anfrage, timeout=60) as antwort:
                for block in iter(lambda: antwort.read(1024 * 1024), b""):
                    anzahl += len(block)
                    if anzahl > erwartete_bytes:
                        raise ValueError("Der Download ist größer als die festgelegte Quelldatei.")
                    ausgabe.write(block)
                    if anzahl >= naechste_meldung:
                        print(f"Ausgangsreden: {anzahl / erwartete_bytes:.0%} geladen.", flush=True)
                        naechste_meldung += meldeschritt
            ausgabe.flush()
            os.fsync(ausgabe.fileno())
        if anzahl != erwartete_bytes:
            raise ValueError(f"Unvollständiger Download: {anzahl} von {erwartete_bytes} Bytes.")
        # Die Prüfung liest die gespeicherte Datei, damit auch Schreibfehler auffallen.
        if zwischen.stat().st_size != erwartete_bytes:
            raise ValueError("Die Quelldatei wurde nicht vollständig gespeichert.")
        md5 = hashlib.md5(usedforsecurity=False)
        with zwischen.open("rb") as gespeichert:
            for block in iter(lambda: gespeichert.read(1024 * 1024), b""):
                md5.update(block)
        if md5.hexdigest() != erwartete_md5.lower():
            raise ValueError("Die heruntergeladene Datei stimmt nicht mit dem festgelegten Quellenstand überein.")
        if ziel.exists():
            raise FileExistsError(f"Die Zieldatei wurde zwischenzeitlich angelegt: {ziel}")
        zwischen.rename(ziel)
    finally:
        zwischen.unlink(missing_ok=True)
    return ziel


def _zahl(wert: Any) -> str:
    """Ganze Satzzahlen werden im Bericht mit deutschem Tausenderpunkt gezeigt."""
    if isinstance(wert, int) and not isinstance(wert, bool):
        return f"{wert:,}".replace(",", ".")
    return str(wert)


def bericht_und_zip_erstellen(
    *,
    satzmaster: str | Path,
    excel: str | Path,
    laufbilanz: str | Path | Mapping[str, Any],
    manifest: str | Path | Mapping[str, Any],
    pruefung_satzmaster: str | Path | Mapping[str, Any],
    pruefung_excel: str | Path | Mapping[str, Any],
    guetemasse: str | Path,
    pruefung_validierung: str | Path,
    zielordner: str | Path,
    eingabedateien: Mapping[str, str | Path] | None = None,
    herkunft: Mapping[str, str] | None = None,
) -> dict[str, Path]:
    """Verbindet erfolgreiche Laufnachweise zu einem kurzen Text und Ergebnis-ZIP.

    Das ZIP enthält Satzmaster, Excel-Auswertung, Gütemaße, deren Rechenbericht
    und den lesbaren Gesamtbericht.
    Die große vollständige Satzbasis und Quelldateien werden nicht erneut gepackt.
    Bekannte Statuswerte und die Dateikennung des aktuellen Satzmasters werden
    geprüft, damit die Berichte eindeutig zu den vorliegenden Ergebnissen gehören.
    Der Aufrufer erstellt nach jeder neuen Berechnung einen neuen Ergebnisordner.
    """
    master, tabelle, ziel = Path(satzmaster), Path(excel), Path(zielordner)
    guete, validierungsbericht = Path(guetemasse), Path(pruefung_validierung)
    ergebnisse = (master, tabelle, guete, validierungsbericht)
    for datei in ergebnisse:
        if not datei.is_file() or datei.stat().st_size == 0:
            raise ValueError(f"Eine fertige Ergebnisdatei fehlt: {datei.name}")
    if len({datei.name for datei in ergebnisse}) != len(ergebnisse):
        raise ValueError("Die Ergebnisdateien benötigen verschiedene Dateinamen.")

    # Die Berichte stammen aus Aufbereitung, Wörterbuchanwendung und Tabellenberechnung.
    # Übereinstimmende Anzahlen und Dateikennungen verbinden sie zu einem Durchlauf.
    quelle = _json_objekt(laufbilanz)
    matching = _json_objekt(manifest)
    masterpruefung = _json_objekt(pruefung_satzmaster)
    excelpruefung = _json_objekt(pruefung_excel)
    if quelle.get("status") != "alle_Referenzpruefungen_bestanden":
        raise ValueError("Die erfolgreiche Prüfung der Korpusaufbereitung fehlt.")
    if quelle.get("dateipruefung", {}).get("status") != "gzip_und_CSV_vollstaendig_rueckgelesen":
        raise ValueError("Die vollständige Rückleseprüfung der Satzbasis fehlt.")
    if masterpruefung.get("status") != "gespeicherter_satzmaster_inhaltsgleich":
        raise ValueError("Die erfolgreiche Prüfung des Satzmasters fehlt.")
    counts = matching.get("counts", {})
    if any(not isinstance(counts.get(art), int) or isinstance(counts.get(art), bool)
           or counts[art] < 0 for art in ("eingabe_saetze", *WOERTERBUCH_DATEIEN)):
        raise ValueError("Die Wörterbuchanwendung enthält unvollständige Satzanzahlen.")
    if quelle.get("satzzeilen") != counts.get("eingabe_saetze"):
        raise ValueError("Aufbereitung und Wörterbuchanwendung beziehen sich auf verschiedene Satzanzahlen.")
    if masterpruefung.get("anzahlen") != {
        art: counts.get(art) for art in WOERTERBUCH_DATEIEN
    }:
        raise ValueError("Wörterbuchanwendung und Satzmasterprüfung enthalten verschiedene Anzahlen.")
    master_hash = datei_sha256(master)
    if matching.get("output", {}).get("sha256") != master_hash:
        raise ValueError("Das Laufprotokoll gehört nicht zur vorliegenden Satzmasterdatei.")
    satzbasis_hash = quelle.get("ausgaben_sha256", {}).get("Saetze_2018-2025.csv.gz")
    if not satzbasis_hash or matching.get("input", {}).get("sha256") != satzbasis_hash:
        raise ValueError("Die Wörterbuchanwendung verwendet nicht die nachgewiesene Satzbasis.")

    # Für Excel werden Status und Dateikennung vom Tabellenrechner übernommen.
    # Die genaue Auslegung eines Zahlenvergleichs steht in dessen eigenem Bericht.
    excel_status = excelpruefung.get("status")
    if excel_status != "tabellen_neu_berechnet":
        raise ValueError("Die erfolgreiche Berechnung der Excel-Datei fehlt.")
    caches = excelpruefung.get("exported_formula_caches", {})
    if (not isinstance(caches.get("formulas"), int)
            or caches.get("formulas", 0) <= 0
            or caches.get("matched") != caches.get("formulas")
            or caches.get("missing_caches") != 0
            or caches.get("mismatches") != 0):
        raise ValueError("Die erfolgreiche Prüfung der gespeicherten Excel-Formelergebnisse fehlt.")
    excel_hash = datei_sha256(tabelle)
    if excelpruefung.get("ausgabe_sha256") != excel_hash:
        raise ValueError("Die Excel-Prüfung gehört nicht zur vorliegenden Excel-Datei.")
    if excelpruefung.get("master_sha256") != master_hash:
        raise ValueError("Die Excel-Auswertung verwendet nicht den vorliegenden Satzmaster.")
    if excelpruefung.get("satzbasis_sha256") != satzbasis_hash:
        raise ValueError("Die Excel-Auswertung verwendet nicht die nachgewiesene Satzbasis.")
    if excelpruefung.get("plenarsaetze") != counts["eingabe_saetze"]:
        raise ValueError("Die Excel-Auswertung enthält eine abweichende Gesamtzahl an Plenarsätzen.")

    # Die Kennzahlen werden aus vorhandenen Handcodierungen berechnet. Die
    # Dateikennungen sichern den Bezug zu diesem Lauf; sie prüfen keine Codierurteile.
    validierung = _json_objekt(validierungsbericht)
    if validierung.get("status") != "validierungskennzahlen_berechnet":
        raise ValueError("Die erfolgreiche Berechnung der Validierungskennzahlen fehlt.")
    if validierung.get("master_sha256") != master_hash:
        raise ValueError("Die Validierung verwendet nicht den vorliegenden Satzmaster.")
    if validierung.get("satzbasis_sha256") != satzbasis_hash:
        raise ValueError("Die Validierung verwendet nicht die nachgewiesene Satzbasis.")
    guete_hash = datei_sha256(guete)
    if validierung.get("ausgabe_sha256") != guete_hash:
        raise ValueError("Der Validierungsbericht gehört nicht zur vorliegenden Gütemaße-Datei.")
    population = validierung.get("population", {})
    if (population.get("plenarsaetze") != counts["eingabe_saetze"]
            or population.get("ae_saetze") != counts["agrar_ernaehrung"]
            or population.get("nichttreffer") != counts["eingabe_saetze"] - counts["agrar_ernaehrung"]):
        raise ValueError("Die Validierung enthält abweichende Grundgesamtheiten.")
    if validierung.get("stichproben") != {"themen": 1000, "nichttreffer": 3000}:
        raise ValueError("Die Validierung verwendet abweichende Stichprobenumfänge.")

    bericht = ziel / "Bericht_zur_Berechnung.txt"
    archiv = ziel / "Ergebnisse.zip"
    if any(p.exists() for p in (bericht, archiv)):
        raise FileExistsError("Berechnungsbericht oder Ergebnis-ZIP ist bereits vorhanden.")
    if any(p.name in {bericht.name, archiv.name} for p in ergebnisse):
        raise ValueError("Ein Ergebnisname überschneidet sich mit dem Bericht oder Ergebnis-ZIP.")

    # Die geprüften Angaben werden lesbar zusammengefasst. Hier wird nichts neu zugeordnet.
    zeilen = [
        "BERICHT ZUR BERECHNUNG",
        "Agrarpolitik im Wandel: Plenarreden 2018–2025",
        "Erstellt (UTC): " + datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "",
        "1. Verwendete Dateien",
    ]
    for bezeichnung, wert in (herkunft or {}).items():
        zeilen.append(f"{bezeichnung}: {wert}")
    for bezeichnung, datei in (eingabedateien or {}).items():
        zeilen.append(f"{bezeichnung}: {Path(datei).name}")
    if not eingabedateien:
        zeilen.append("Aufbereitete Satzbasis: " + str(matching.get("input", {}).get("file", "nicht angegeben")))
    for art, infos in matching.get("dictionaries", {}).items():
        zeilen.append(f"Wörterbuch {BEZEICHNUNGEN.get(art, art)}: {infos.get('file', 'nicht angegeben')}")
    zeilen += [
        "",
        "2. Korpusaufbereitung",
        "Beitragseinheiten: " + _zahl(quelle.get("beitraege", "nicht angegeben")),
        "Aufbereitete Plenarsätze: " + _zahl(quelle["satzzeilen"]),
        "Technischer Vergleich: Übereinstimmung mit der festgelegten Satzbasis bestätigt.",
        "Die gespeicherte Satzdatei wurde vollständig zurückgelesen und geprüft.",
        "",
        "Plenarsätze je Jahr:",
    ]
    zeilen += [f"  {jahr}: {_zahl(anzahl)}" for jahr, anzahl in sorted(quelle.get("jahre", {}).items())]
    zeilen += ["", "3. Wörterbuchanwendung"]
    zeilen += [f"{BEZEICHNUNGEN[art]}: {_zahl(counts[art])} Sätze" for art in WOERTERBUCH_DATEIEN]
    zeilen += [
        "Mehrfachzuordnungen zwischen Themenbereichen sind möglich.",
        "Technischer Vergleich: Satzmaster stimmt in allen geprüften Feldern mit dem Analysebestand überein.",
        "Geprüfte Felder je Satz: " + _zahl(masterpruefung.get("gepruefte_felder_je_satz", "nicht angegeben")),
        "",
        "4. Excel-Auswertung",
        "Ergebnisdatei: " + tabelle.name,
        "Die Jahresgesamtzahlen wurden unmittelbar aus der aufbereiteten Satzbasis dieses Durchlaufs berechnet.",
    ]
    zeilen.append("Die gespeicherten Ergebnisse der Excel-Formeln wurden mit der Berechnung verglichen.")
    zeilen.append("Geprüfte gespeicherte Formelergebnisse: " + _zahl(caches["matched"]))
    if "neu_berechnete_eingabezellen" in excelpruefung:
        zeilen.append("Neu berechnete Eingabezellen: " + _zahl(excelpruefung["neu_berechnete_eingabezellen"]))
    zeilen += [
        "",
        "5. Validierungskennzahlen",
        "Ergebnisdatei: " + guete.name,
        "Vorhandene Handcodierungen: 1.000 A&E-Sätze und 3.000 Nichttreffer.",
        "Daraus wurden Präzision, Trefferquote und Wilson-Intervalle neu berechnet.",
        "Die hochgerechnete Trefferquote des Politikfeldfilters verwendet die Grundgesamtheiten dieses Durchlaufs.",
        "Die menschlichen Codierungen werden unverändert übernommen und nicht erneut inhaltlich beurteilt.",
        "",
        "6. Umfang der Prüfung",
        "Die technischen Vergleiche prüfen die Wiederholung des festgelegten Analyseablaufs.",
        "Sie ersetzen keine inhaltliche Validierung anhand menschlicher Kodierungen.",
        "",
        "7. Dateien im Ergebnis-ZIP",
        master.name,
        tabelle.name,
        guete.name,
        validierungsbericht.name,
        bericht.name,
        "",
        "Software: Python " + str(quelle.get("python", "nicht angegeben"))
        + "; pysbd " + str(quelle.get("pysbd", "nicht angegeben")),
        "",
        "Dateikennungen der Ergebnisse (SHA-256):",
        master.name + ": " + master_hash,
        tabelle.name + ": " + excel_hash,
        guete.name + ": " + guete_hash,
        validierungsbericht.name + ": " + datei_sha256(validierungsbericht),
        "",
    ]

    ziel.mkdir(parents=True, exist_ok=True)
    # Beide Dateien zunächst separat schreiben. Ein abgebrochener ZIP-Lauf wird
    # nicht als fertiges Paket hinterlassen. Große Dateien werden gestreamt.
    zwischen = Path(tempfile.mkdtemp(prefix=".ergebnispaket_", dir=ziel))
    try:
        textdatei = zwischen / bericht.name
        textdatei.write_text("\n".join(zeilen), encoding="utf-8")
        zipdatei = zwischen / archiv.name
        with zipfile.ZipFile(zipdatei, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as handle:
            for datei in (*ergebnisse, textdatei):
                handle.write(datei, arcname=datei.name)
        with zipfile.ZipFile(zipdatei) as handle:
            if handle.testzip() is not None:
                raise ValueError("Das Ergebnis-ZIP konnte nicht vollständig geprüft werden.")
        if bericht.exists() or archiv.exists():
            raise FileExistsError("Berechnungsbericht oder Ergebnis-ZIP wurde zwischenzeitlich angelegt.")
        os.rename(textdatei, bericht)
        os.rename(zipdatei, archiv)
    finally:
        shutil.rmtree(zwischen, ignore_errors=True)
    return {"bericht": bericht, "zip": archiv}
