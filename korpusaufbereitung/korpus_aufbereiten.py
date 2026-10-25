#!/usr/bin/env python3
"""Erzeugt die festgelegte Satzbasis des Untersuchungskorpus 2018–2025.

Eingabe ist die Fobbe-CSV vom 17.01.2026 (auch in ZIP/gzip). Die Reden im
Untersuchungszeitraum werden technisch normalisiert, mit pySBD in Sätze zerlegt
und anhand der mitgelieferten JSON-Dateien korrigiert und ergänzt. Diese festen
Korrekturdaten wurden aus Ausgangs- und Zieldatei rekonstruiert. Der Ablauf
reproduziert den festgelegten Korpusstand, nicht die ursprüngliche Reihenfolge
aller manuellen und automatischen Bearbeitungsschritte.

Ausgaben im neu angelegten Ergebnisordner:
- Saetze_2018-2025.csv.gz: vollständige Satzbasis vor dem A&E-Filter.
- Laufbilanz.json: Ergebnis der technischen Prüfungen und Angaben zu diesem Lauf.

Die Prüfung bezieht sich auf den gespeicherten Korpusstand, nicht auf die
inhaltliche Güte der anschließenden Wörterbuchzuordnungen.

Aufruf:
    python korpus_aufbereiten.py --quelle Reden_Gesamt.zip --ausgabe ergebnis
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
import csv
import gzip
import hashlib
import io
import json
from multiprocessing import Pool
from pathlib import Path
import platform
import re
import shutil
import sys
import tempfile
import time
import zipfile

import pysbd

BASIS = Path(__file__).resolve().parent
KONFIG = BASIS / 'konfiguration'
REFERENZ_SHA256 = 'cb7aa1faa469bfc8125194619abff369f94c9ad26292f35aa7d114edcaf605a8'
# Satzbezogene Felder entstehen erst nach der Aufbereitung des Beitrags.
# Die übrigen Metadaten werden an jeden zugehörigen Satz weitergegeben.
SATZFELDER = {'sent_idx', 'sent_text', 'satz_id', 'satzposition'}
DEHYPHEN = re.compile(r'(\w)-\s*[\r\n]+\s*(\w)')
ZEILENUMBRUCH = re.compile(r'[ \t]*[\r\n]+[ \t]*')
MEHRFACHLEER = re.compile(r'\s{2,}')
# Ganze Reden können das Standardlimit eines CSV-Feldes überschreiten.
# Der Rückfall berücksichtigt die unterschiedliche Integerbreite je Plattform.
feldgrenze = sys.maxsize
while True:
    try:
        csv.field_size_limit(feldgrenze)
        break
    except OverflowError:
        feldgrenze //= 10


def fordere(bedingung: bool, hinweis: str) -> None:
    """Eine Referenzabweichung beendet den Lauf auch bei python -O."""
    if not bedingung:
        raise ValueError(hinweis)


def datei_hash(pfad: Path) -> str:
    """Kennzeichnet den exakten Byteinhalt einer Datei, blockweise gelesen."""
    wert = hashlib.sha256()
    with pfad.open('rb') as datei:
        for block in iter(lambda: datei.read(1024 * 1024), b''):
            wert.update(block)
    return wert.hexdigest()


def text_hash(text: str) -> str:
    """Kennzeichnet einen Text in der für die Korrekturdaten verwendeten UTF-8-Form."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def listen_hash(texte: list[str]) -> str:
    """Prüft Satztexte samt Reihenfolge und Satzgrenzen über eine feste JSON-Form."""
    serialisiert = json.dumps(texte, ensure_ascii=False, separators=(',', ':'))
    return text_hash(serialisiert)


def laden(name: str) -> dict:
    """Lädt eine zum festgelegten Korpusstand gehörende Konfigurationsdatei."""
    return json.loads((KONFIG / name).read_text(encoding='utf-8'))


@contextmanager
def quelle_oeffnen(pfad: Path):
    """Öffnet die CSV aus einer einfachen Datei, gzip oder einem ZIP mit genau einer CSV."""
    if pfad.suffix.lower() == '.zip':
        with zipfile.ZipFile(pfad) as archiv:
            namen = [n for n in archiv.namelist() if n.lower().endswith('.csv')]
            fordere(len(namen) == 1, 'Das ZIP muss genau eine CSV enthalten.')
            with archiv.open(namen[0]) as datei:
                yield datei
    elif pfad.suffix.lower() == '.gz':
        with gzip.open(pfad, 'rb') as datei:
            yield datei
    else:
        with pfad.open('rb') as datei:
            yield datei


def quelle_pruefen(pfad: Path, erwartet: str) -> None:
    """Verhindert die Anwendung fester Korrekturen auf eine andere Quellversion."""
    # Geprüft wird die entpackte CSV. Dateiname und ZIP-Kompression beeinflussen
    # diesen Vergleich nicht.
    wert = hashlib.sha256()
    with quelle_oeffnen(pfad) as datei:
        for block in iter(lambda: datei.read(1024 * 1024), b''):
            wert.update(block)
    fordere(wert.hexdigest() == erwartet,
            'Die Ausgangs-CSV weicht vom festgelegten Quellenstand ab.')


def vorbereinigen(text: str) -> str:
    """Vereinheitlicht Trennzeichen und Leerraum vor der Satzzerlegung mit pySBD."""
    # Weiche Trennzeichen und Trennungen über Zeilenumbrüche werden vereinheitlicht.
    # Inhaltliche Korrekturen, etwa an Regieeinträgen, stehen in den festen
    # Satzkorrekturen. Diese Funktion erkennt solche Fälle nicht selbst.
    text = text.replace('\u00ad', '')
    text = DEHYPHEN.sub(r'\1\2', text)
    text = ZEILENUMBRUCH.sub(' ', text)
    return MEHRFACHLEER.sub(' ', text).strip()


def segmentierer_starten() -> None:
    """Initialisiert in jedem Arbeitsprozess denselben deutschen Satzsegmentierer."""
    global SEGMENTIERER
    # clean=False unterbindet die zusätzliche Textbereinigung durch pySBD.
    # Damit bleibt die vorangestellte technische Normalisierung explizit sichtbar.
    SEGMENTIERER = pysbd.Segmenter(language='de', clean=False)


def segmentieren(text: str) -> list[str]:
    """Erzeugt die Ausgangssegmentierung eines Beitrags ohne leere Satzstücke."""
    return [satz.strip() for satz in SEGMENTIERER.segment(vorbereinigen(text))
            if satz.strip()]


def quelle_lesen(pfad: Path, referenz: dict, nullwerte: set[str]) -> list[dict]:
    """Liest Beiträge im Untersuchungszeitraum in ihrer ursprünglichen Reihenfolge.

    Die in der Konfiguration aufgeführten Fehlwertmarkierungen werden zu leeren
    Zeichenfolgen. Die Quellspalten und die Eindeutigkeit der Beitragskennungen
    müssen zur Referenz passen, bevor die Satzsegmentierung beginnt.
    """
    reden, ids = [], set()
    von, bis = referenz['zeitraum']
    with quelle_oeffnen(pfad) as roh:
        reader = csv.DictReader(io.TextIOWrapper(roh, encoding='utf-8-sig', newline=''))
        fordere(reader.fieldnames == referenz['ausgangsdatei']['quellspalten'],
                'Abweichende Quellspalten.')
        for row in reader:
            if not von <= int(row['sitzung_jahr']) <= bis:
                continue
            row = {k: '' if v in nullwerte else v for k, v in row.items()}
            fordere(row['rede_id'] not in ids, 'Doppelte Rede-ID in der Quelle.')
            ids.add(row['rede_id'])
            reden.append(row)
    fordere(len(reden) == referenz['bilanz']['quellbeitraege_zeitraum'],
            'Abweichende Zahl der Quellenbeiträge im Zeitraum.')
    return reden


def metadaten_aufbauen(row: dict, felder: list[str], lookup: dict,
                      lookup_felder: list[str], config: dict, patch: dict | None) -> dict:
    """Baut Satzmetadaten aus Quelle, fester Ergänzungstabelle und Einzelkorrektur.

    Die politische Ergänzung greift nur bei leerer Quellzuordnung. Anschließend
    hat eine für diesen Beitrag hinterlegte Einzelkorrektur Vorrang, sofern ihr
    erwarteter Ausgangswert zutrifft. Es wird keine Zugehörigkeit neu geschätzt.
    """
    meta = {k: row.get(k, '') for k in felder if k not in SATZFELDER}
    if not meta['redner_fraktion']:
        key = tuple(row[k].strip() for k in lookup_felder)
        meta['redner_fraktion'] = lookup.get(key, '')
    meta.update(config['standardfelder'])
    meta['ursprungs_rede_id'] = row['rede_id']
    # Eine Amtsrolle liegt vor, sobald eines der beiden Rollenfelder befüllt ist.
    # Dies entspricht der Rollenprüfung in der Auswertung.
    # Eine politische Zuordnung ist hier nicht automatisch ein Fraktionsmandat.
    amtsrolle = bool(meta['redner_rolle_kurz'].strip() or meta['redner_rolle_lang'].strip())
    meta['zugehoerigkeit_art'] = ('rollenbezogene_politische_zuordnung' if amtsrolle
                                else 'parlamentarische_zuordnung_quelle')
    # Die Herkunftskennzeichnung wird wortgleich aus dem festgelegten Datenstand
    # übernommen. Sie dokumentiert keine neue unabhängige Prüfung der Zuordnung.
    meta['zugehoerigkeit_pruefstatus'] = ('aus_bisheriger_arbeitsfassung' if meta['redner_fraktion']
                                        else 'nicht_angegeben')
    # Die *_original-Felder sichern den Stand vor den Einzelkorrekturen.
    # Bei redner_fraktion ist die feste Ergänzung eines Leerwertes dann schon erfolgt.
    for feld in ['redner_id', 'redner_vorname', 'redner_nachname', 'redner_fraktion']:
        meta[feld + '_original'] = meta[feld]
    if patch:
        for feld, werte in patch['aenderungen'].items():
            fordere(meta[feld] == werte['vorher'],
                    f"Metadaten-Ausgangswert abweichend: {row['rede_id']}, {feld}")
            meta[feld] = werte['nachher']
    return meta


def satzkorrekturen_anwenden(row: dict, saetze: list[str], patch: dict | None) -> list[str]:
    """Überträgt ausschließlich hinterlegte Änderungen auf eine geprüfte Satzliste.

    Quelltext und Ausgangssegmentierung müssen exakt zum Korrektureintrag passen.
    Jede Operation ersetzt eine Satzspanne vom Startindex bis vor den Endindex.
    Einfügungen und Löschungen haben eine leere Vorher- bzw. Nachherliste.
    Es werden keine neuen Korrekturfälle automatisch erkannt.
    """
    if not patch:
        return saetze
    rid = row['rede_id']
    fordere(text_hash(row['rede_text']) == patch['raw_rede_text_sha256'],
            f'Textkorrektur gehört zu anderem Quelltext: {rid}')
    fordere(listen_hash(saetze) == patch['baseline_list_sha256'],
            f'Abweichende Ausgangssegmentierung: {rid}')
    ende = 0
    for op in patch['operations']:
        a, b = op['baseline_start'], op['baseline_end']
        fordere(ende <= a <= b <= len(saetze) and saetze[a:b] == op['before'],
                f'Ungültige oder nicht passende Korrekturspanne: {rid}')
        ende = b
    # Rückwärts ersetzen: Die Positionen beziehen sich auf die unkorrigierte Liste.
    # Dadurch verschiebt eine Einfügung/Löschung keine noch ausstehende Korrektur.
    for op in reversed(patch['operations']):
        saetze[op['baseline_start']:op['baseline_end']] = op['after']
    fordere(listen_hash(saetze) == patch['target_list_sha256'],
            f'Abweichendes Ergebnis der Textkorrektur: {rid}')
    return saetze


def ausgabe_pruefen(pfad: Path, referenz: dict) -> dict:
    """Liest die gespeicherte CSV vollständig zurück und prüft sie gegen den Endstand.

    Neben Satz- und Beitragszahlen werden alle Zielfelder in ihrer Zeilenfolge
    geprüft. Ein zweiter Fingerabdruck erfasst nur Texte und ihre Grenzen.
    Die vorangestellte Byte-Länge macht aufeinanderfolgende Texte eindeutig trennbar.
    Vollständiges Lesen erfasst auch Fehler am Ende des gzip-Datenstroms.
    """
    felder = referenz['zielspalten']
    zeilen_hash, texte_hash = hashlib.sha256(), hashlib.sha256()
    jahre, beitrags_ids = Counter(), set()
    anzahl = 0
    with gzip.open(pfad, 'rt', encoding='utf-8', newline='') as datei:
        reader = csv.DictReader(datei, delimiter=';')
        fordere(reader.fieldnames == felder, 'Abweichende Spalten der gespeicherten CSV.')
        for row in reader:
            fordere(None not in row and all(row[k] is not None for k in felder),
                    f'Unvollständige CSV-Zeile in der Ausgabe: {reader.line_num}')
            zeilen_hash.update(json.dumps([row[k] for k in felder], ensure_ascii=False,
                                           separators=(',', ':')).encode('utf-8') + b'\n')
            utf8 = row['sent_text'].encode('utf-8')
            texte_hash.update(len(utf8).to_bytes(8, 'big'))
            texte_hash.update(utf8)
            jahre[row['sitzung_jahr']] += 1
            beitrags_ids.add(row['rede_id'])
            anzahl += 1
    beobachtet = {'satzzeilen': anzahl, 'beitraege': len(beitrags_ids),
                  'jahre': dict(sorted(jahre.items())), 'satzinhalt_sha256': zeilen_hash.hexdigest(),
                  'satztexte_sha256': texte_hash.hexdigest()}
    fordere(beobachtet == referenz['referenz'],
            f'Die gespeicherte CSV weicht von der Referenz ab: {beobachtet}')
    return beobachtet


def main() -> None:
    """Führt Quellenprüfung, Korpusaufbereitung und gesicherte Ausgabe nacheinander aus."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--quelle', type=Path, required=True)
    parser.add_argument('--ausgabe', type=Path, required=True, help='Neues Ausgabeverzeichnis')
    parser.add_argument('--prozesse', type=int, default=4, choices=range(1, 5))
    args = parser.parse_args()
    # 1. Verbindliche Eingaben prüfen. Version und Dateifingerabdrücke verhindern,
    # dass geänderte Quellen oder Korrekturdaten als derselbe Datenstand gelten.
    fordere(not args.ausgabe.exists(), 'Ausgabeverzeichnis existiert bereits.')
    fordere(pysbd.__version__ == '0.3.4', 'Benötigt wird pysbd==0.3.4.')
    fordere(datei_hash(KONFIG / 'referenz.json') == REFERENZ_SHA256,
            'Die Referenzkonfiguration wurde verändert.')
    referenz = laden('referenz.json')
    for name, erwartet in referenz['eingaben_sha256'].items():
        fordere(datei_hash(KONFIG / name) == erwartet, f'Veränderte Konfiguration: {name}')
    quelle_pruefen(args.quelle, referenz['ausgangsdatei']['csv_sha256'])
    # 2. Feste Zuordnungen und Korrekturen nach ihren Schlüsseln erschließen.
    # Doppelte Schlüssel wären mehrdeutig und werden vor dem Schreiben abgewiesen.
    meta_config = laden('metadatenkorrekturen.json')
    lookup_config = laden('fraktionszuordnung.json')
    lookup_felder = lookup_config['schluesselfelder']
    lookup = {tuple(r[k].strip() for k in lookup_felder): r['redner_fraktion']
              for r in lookup_config['eintraege']}
    fordere(len(lookup) == len(lookup_config['eintraege']), 'Mehrdeutiger Lookup-Schlüssel.')
    meta_records = meta_config['korrekturen']
    text_records = laden('satzkorrekturen.json')['patches']
    meta_patches = {p['rede_id']: p for p in meta_records}
    text_patches = {p['rede_id']: p for p in text_records}
    fordere(len(meta_patches) == len(meta_records) and len(text_patches) == len(text_records),
            'Doppelte Beitrags-ID in den Korrekturtabellen.')
    extras = laden('ergaenzungen.json')['beitraege']
    # Ergänzungen enthalten bereits Satztexte und Metadaten. nach_rede_id bestimmt
    # ihre Einfügeposition. Mehrere Ergänzungen können eine Nachfolgerkette bilden.
    nachfolger = {r['nach_rede_id']: r for r in extras}
    fordere(len(nachfolger) == len(extras), 'Mehrdeutige Einfügeposition für Zusatzbeitrag.')
    register = defaultdict(dict)
    # Das Register enthält die im festgelegten Datenstand verwendeten Kennungen,
    # soweit sie von der fortlaufenden Zählung ab null abweichen. So verweisen
    # Satzmaster und Validierungsdateien weiterhin auf dieselben Sätze.
    for r in laden('satzkennungen.json')['eintraege']:
        position = r['laufender_satzindex']
        fordere(position not in register[r['rede_id']], 'Doppelter ID-Registereintrag.')
        register[r['rede_id']][position] = r
    reden = quelle_lesen(args.quelle, referenz, set(meta_config['nullwerte']))
    quell_ids = {r['rede_id'] for r in reden}
    fordere(set(meta_patches) <= quell_ids and set(text_patches) <= quell_ids,
            'Eine Korrektur verweist auf eine fehlende Quellrede.')
    fordere(not quell_ids & {r['rede_id'] for r in extras}, 'Zusatz-ID kollidiert mit Quelle.')
    print(f'Eingaben geprüft: {len(reden):,} Quellbeiträge; {len(extras)} Zusatzbeiträge.', flush=True)

    # 3. In einen temporären Ordner schreiben. Erst ein vollständig geprüftes
    # Ergebnis wird unter dem angeforderten Ausgabeverzeichnis sichtbar.
    args.ausgabe.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix='.korpus_', dir=args.ausgabe.parent))
    start = time.perf_counter()
    jahre = Counter()
    zaehler = Counter()
    zeilen_hash, texte_hash = hashlib.sha256(), hashlib.sha256()
    verwendete_ids, verwendete_extras, verwendete_register = set(), set(), set()
    felder = referenz['zielspalten']
    try:
        with gzip.open(temp / 'Saetze_2018-2025.csv.gz', 'wt', encoding='utf-8', newline='', compresslevel=6) as datei:
            writer = csv.DictWriter(datei, fieldnames=felder, delimiter=';')
            writer.writeheader()

            def schreiben(meta: dict, saetze: list[str]) -> None:
                """Schreibt Satzzeilen mit stabilen Kennungen und zählt die Jahresbasis."""
                rid = meta['rede_id']
                fordere(rid not in verwendete_ids, f'Doppelte Beitrags-ID: {rid}')
                verwendete_ids.add(rid)
                if not saetze:
                    zaehler['leere_quellbeitraege'] += 1
                    return
                zaehler['beitraege'] += 1
                indices = set()
                for position, text in enumerate(saetze):
                    idx = satzposition = str(position)
                    # Kennung und Position sind verschiedene Größen: Nach einer
                    # Reparatur muss eine erhaltene ID nicht fortlaufend sein.
                    if position in register.get(rid, {}):
                        r = register[rid][position]
                        fordere(text_hash(text) == r['sent_text_sha256'], f'ID-Register-Text abweichend: {rid}:{position}')
                        idx, satzposition = r['sent_idx'], r['satzposition']
                        verwendete_register.add((rid, position))
                    fordere(idx not in indices, f'Doppelte Satzkennung in {rid}: {idx}')
                    indices.add(idx)
                    row = {**meta, 'sent_idx': idx, 'sent_text': text,
                           'satz_id': f'{rid}:{idx}', 'satzposition': satzposition}
                    writer.writerow(row)
                    zeilen_hash.update(json.dumps([row[k] for k in felder], ensure_ascii=False,
                                                   separators=(',', ':')).encode('utf-8') + b'\n')
                    utf8 = text.encode('utf-8')
                    texte_hash.update(len(utf8).to_bytes(8, 'big'))
                    texte_hash.update(utf8)
                    jahre[row['sitzung_jahr']] += 1
                    zaehler['satzzeilen'] += 1

            def ergaenzen(vorgaenger: str | None) -> None:
                """Fügt die festgelegte Kette segmentierter Zusatzbeiträge ein."""
                while vorgaenger in nachfolger:
                    extra = nachfolger[vorgaenger]
                    rid = extra['rede_id']
                    fordere(rid not in verwendete_extras, 'Zyklus in Zusatzbeitragsreihenfolge.')
                    verwendete_extras.add(rid)
                    schreiben(extra['metadaten'], extra['saetze'])
                    vorgaenger = rid

            ergaenzen(None)
            with Pool(args.prozesse, initializer=segmentierer_starten) as pool:
                jobs = (r['rede_text'] for r in reden)
                # imap bewahrt die Reihenfolge der Eingaben trotz paralleler
                # Segmentierung. zip ordnet jedes Ergebnis wieder seiner Rede zu.
                for n, (row, saetze) in enumerate(zip(reden, pool.imap(segmentieren, jobs, chunksize=16)), 1):
                    rid = row['rede_id']
                    saetze = satzkorrekturen_anwenden(row, saetze, text_patches.get(rid))
                    meta = metadaten_aufbauen(row, felder, lookup, lookup_felder, meta_config, meta_patches.get(rid))
                    schreiben(meta, saetze)
                    ergaenzen(rid)
                    if n % 5000 == 0:
                        print(f'{n:,}/{len(reden):,} Quellbeiträge; {zaehler["satzzeilen"]:,} Sätze', flush=True)
        # 4. Vollständige Verwendung der Ergänzungen/Kennungen und Übereinstimmung
        # von Inhalt, Reihenfolge und Zählwerten prüfen. Danach die Datei zurücklesen.
        fordere(verwendete_extras == {r['rede_id'] for r in extras}, 'Unverwendete Zusatzbeiträge.')
        fordere(verwendete_register == {(rid, p) for rid, rows in register.items() for p in rows},
                'Unverwendete Satzkennungen.')
        beobachtet = {'satzzeilen': zaehler['satzzeilen'], 'beitraege': zaehler['beitraege'],
                      'jahre': dict(sorted(jahre.items())), 'satzinhalt_sha256': zeilen_hash.hexdigest(),
                      'satztexte_sha256': texte_hash.hexdigest()}
        fordere(beobachtet == referenz['referenz'],
                f'Ergebnis weicht von der verbindlichen Referenz ab: {beobachtet}')
        print('Erzeugung abgeschlossen; vollständiger Readback der gespeicherten CSV.', flush=True)
        rueckgelesen = ausgabe_pruefen(temp / 'Saetze_2018-2025.csv.gz', referenz)
        # 5. Die Bilanz hält auch die bei Erzeugung und Rücklesen geprüften
        # Jahresgesamtzahlen fest. Die Auswertung zählt selbst aus der Satzbasis.
        bilanz = {'status': 'alle_Referenzpruefungen_bestanden', **beobachtet,
                  'dateipruefung': {'status': 'gzip_und_CSV_vollstaendig_rueckgelesen', **rueckgelesen},
                  'python': platform.python_version(), 'pysbd': pysbd.__version__,
                  'prozesse': args.prozesse, 'sekunden': round(time.perf_counter()-start, 2),
                  'quell_csv_sha256': referenz['ausgangsdatei']['csv_sha256'],
                  'konfiguration_sha256': {**referenz['eingaben_sha256'], 'referenz.json': REFERENZ_SHA256},
                  'skript_sha256': datei_hash(Path(__file__)),
                  'ausgaben_sha256': {p.name: datei_hash(p) for p in sorted(temp.iterdir())}}
        # Die Bilanz weist Software, Eingaben, Skript und Ausgaben dieses Laufs nach.
        # Laufzeit und gzip-Dateifingerabdruck können zwischen Läufen variieren.
        # Die oben geprüften Inhaltsfingerabdrücke beziehen sich auf die CSV-Werte.
        (temp / 'Laufbilanz.json').write_text(json.dumps(bilanz, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        temp.rename(args.ausgabe)
    except BaseException:
        shutil.rmtree(temp, ignore_errors=True)
        raise
    print(f'Fertig: {zaehler["satzzeilen"]:,} Sätze; sämtliche Texte, Metadaten, IDs und Zeilenfolgen geprüft.', flush=True)


if __name__ == '__main__':
    main()
