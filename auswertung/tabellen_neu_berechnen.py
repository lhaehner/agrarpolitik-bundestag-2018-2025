#!/usr/bin/env python3
"""Die 14 Arbeitsblätter aus dem festgelegten A&E-Satzmaster nachberechnen.

Datenfluss: Satzmaster lesen und prüfen -> binäre Satzmerkmale gruppieren ->
Zähler in vorgegebene Excel-Zellen schreiben -> bestehende Formeln auswerten.
Die Klassifikation der Sätze ist bereits im Satzmaster enthalten. Dieses Skript
wendet die vier Themen-/Filterwörterbücher nicht erneut auf die Texte an.

Die mitgelieferte ergebnisse/Datengrundlage.xlsx dient als feste Vorlage. Sie
liefert Blattnamen, Zelladressen, Perioden/Fraktionen und drei Textsuchregeln
aus 12_Begriffe_Suchregeln!C16:C18. Plenarsätze, Plenartage und Beitragszahlen werden aus
der vollständigen Satzbasis (--satzbasis) berechnet.
Der Rechner bildet den Abgabestand mit 25.247 A&E-Sätzen und 56
Ökonomiefamilien ab. Feste Zelladressen verbinden die berechneten Zähler mit
den zugehörigen Tabellen und Formeln der mitgelieferten Vorlage.

Anteile werden durch die Formeln der Vorlage berechnet. Je nach Tabelle ist
der Nenner die A&E-Satzzahl, die Satzzahl eines Themenbereichs oder die Zahl
aller Plenarsätze. Mehrere Themen/Kategorien können denselben Satz erfassen.
Vereinigungsmengen zählen ihn dagegen einmal. Die Jahresgesamtzahlen werden
aus der Satzbasis gezählt und in alle entsprechenden Quellzellen der Vorlage
geschrieben.

``Datengrundlage.xlsx`` enthält den festen Tabellenaufbau mit Formeln und
Referenzwerten. Die Ausgabedatei enthält die aus den Eingaben neu berechneten
Werte. Die Vorlage wird dabei nicht überschrieben. Das lokale Hilfsmodul
``ooxml_engine`` schreibt diese Werte und berechnet die Excel-Formeln ohne
eine installierte Excel-Anwendung. Beide Programme verwenden ausschließlich
die Python-Standardbibliothek.
"""
import argparse, csv, json, re, hashlib, datetime, collections, gzip
from pathlib import Path

# Berichtszeitraum und einheitliche Fraktionsnamen der Auswertung.
YEARS = list(range(2018, 2026))
DIM = {'Ökologie': 'oekologie', 'Ökonomie': 'oekonomie', 'S&R': 'sicherheit_resilienz'}
PARTIES = ['CDU/CSU', 'SPD', 'Grüne', 'AfD', 'FDP', 'Die Linke']
PARTY = {'BÜNDNIS 90/DIE GRÜNEN': 'Grüne', 'DIE LINKE': 'Die Linke'}
# K1–K7, G1–G7 und SR1–SR5 sind die Kategoriekennungen des Satzmasters.
# Sie verknüpfen die Wörterbuchzuordnungen mit den Tabellen. Beispielsweise
# steht G1 für Preise/Kosten, G7 für Agrardiesel und SR1 für Ernährungssicherheit.

# Die Reihenfolge entspricht 12_Begriffe_Suchregeln!C16:C18. Diese drei Textsuchen
# dienen der Wortwahl (Tabelle A9) und dem Fleischwirtschaftsbeispiel in 5.4.
TEXT_KEYS = ['sg_fleisch', 'sg_pestizid', 'sg_pflanzenschutzmittel']


def sha(path):
    """Dateiidentität über die unveränderten Bytes prüfen (auch bei .gz-Dateien)."""
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def day_of(value):
    """Ein Vorlagendatum als ISO-Tag lesen und Excel-Tageszahlen berücksichtigen."""
    if isinstance(value,(float,int)):
        return (datetime.date(1899,12,30)+datetime.timedelta(days=value)).isoformat()
    return str(value)[:10]


def years_for(value):
    """Die Jahres-/Periodenbeschriftung der Vorlage in eine Jahresliste auflösen.

    Zwei gefundene Jahreszahlen begrenzen einen einschließlich verstandenen
    Zeitraum. 'Gesamt' und Beschriftungen ohne Jahr stehen für 2018 bis 2025.
    """
    s=str(value)
    if s=='Gesamt':
        return YEARS
    y=[int(x) for x in re.findall(r'20\d{2}',s)]
    return list(range(y[0],y[-1]+1)) if y else YEARS


def load_satzbasis_totals(path):
    """Gesamtplenum-Zahlen aus der vollständigen Satzdatei ableiten.

    Eine CSV-Zeile zählt als Satzvorkommen. Beiträge zählen als eindeutige
    ``rede_id`` innerhalb der jeweiligen Gruppe. Sitzungstage sind verschiedene
    Datumswerte, nicht Sitzungsnummern. Leere Fraktionsangaben heißen in der
    Excel-Vorlage 'Ohne Zuordnung'. Die CSV wird zeilenweise verarbeitet.
    Alle acht Untersuchungsjahre müssen enthalten sein. Die Jahresgesamtzahlen
    entstehen unmittelbar beim Zählen der vollständigen Satzbasis.
    """
    years = collections.Counter()
    year_party = collections.Counter()
    days = collections.Counter()
    year_days = collections.defaultdict(set)
    year_speeches = collections.defaultdict(set)
    party_speeches = collections.defaultdict(set)
    day_speeches = collections.defaultdict(set)
    opener = gzip.open if Path(path).suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle, delimiter=';')
        required = {'sitzung_jahr', 'sitzung_datum', 'redner_fraktion', 'rede_id'}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f'Satzbasis: Fehlende Spalten {sorted(required-set(reader.fieldnames or []))}.')
        for line, row in enumerate(reader, start=2):
            try:
                year = int(row['sitzung_jahr'])
                day = row['sitzung_datum'][:10]
                speech = row['rede_id']
                party = PARTY.get(row['redner_fraktion'], row['redner_fraktion']) or 'Ohne Zuordnung'
                if year not in YEARS or int(day[:4]) != year or not speech:
                    raise ValueError('Jahr, Datum oder Beitragskennung ungültig')
                if day not in days:
                    datetime.date.fromisoformat(day)
            except (ValueError, TypeError, KeyError) as error:
                raise ValueError(f'Satzbasis: Ungültige Metadaten in Zeile {line}.') from error
            years[year] += 1
            year_party[(year, party)] += 1
            days[day] += 1
            year_days[year].add(day)
            year_speeches[year].add(speech)
            party_speeches[(year, party)].add(speech)
            day_speeches[day].add(speech)
    missing = sorted(set(YEARS) - years.keys())
    if missing:
        raise ValueError(f'Satzbasis: Fehlende Jahre {missing}.')
    return {'years': years, 'year_party': year_party, 'days': days,
            'year_days': year_days, 'year_speeches': year_speeches,
            'party_speeches': party_speeches, 'day_speeches': day_speeches}


def load_master(path,base):
    """Satzmaster prüfen und Hilfsmerkmale für die Tabellen in den Speicher laden.

    Erwartet UTF-8-CSV mit Semikolon (optional gzip-komprimiert), eindeutige
    Satzkennungen und konsistente binäre Themen-, Kategorie- und Familienflags.
    Die mit '_' beginnenden Werte dienen nur der anschließenden Aggregation.
    Ergänzende Textauswahlen stammen aus der Excel-Vorlage. Sie ersetzen keine
    Themenklassifikation. Die Originaldatei wird nicht verändert.
    """
    opener = gzip.open if Path(path).suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f, delimiter=';'))
    if len(rows)!=25247:
        raise ValueError('Die Vorlage erwartet den unveränderten A&E-Bestand mit 25.247 Sätzen.')
    required=['satz_id','rede_id','sent_idx','sent_text','sitzung_jahr','sitzung_datum','redner_fraktion','protokoll_nr','redner_rolle_kurz','redner_rolle_lang',*DIM.values()]
    required += [f'oekologie_K{i}' for i in range(1,8)]+[f'oekonomie_G{i}' for i in range(1,8)]+[f'sicherheit_resilienz_SR{i}' for i in range(1,6)]
    missing=set(required)-rows[0].keys()
    if missing:
        raise ValueError(f'Fehlende Spalten: {sorted(missing)}')
    if len({r['satz_id'] for r in rows})!=len(rows) or len({(r['rede_id'],r['sent_idx']) for r in rows})!=len(rows):
        raise ValueError('Doppelte Satzkennungen')
    # Diese Regeln ergänzen die Themenflags um die konkret berichteten Wortauswahlen.
    patterns={k:re.compile(base['12_Begriffe_Suchregeln'][f'C{16+i}']) for i,k in enumerate(TEXT_KEYS)}
    famcols=[k for k in rows[0] if k.startswith('oekonomie_familie_')]
    if len(famcols)!=56:
        raise ValueError('Die Vorlage erwartet die bestehenden 56 Ökonomiefamilien.')
    flags=[*DIM.values()]+[k for k in rows[0] if re.match(r'(oekologie_K|oekonomie_G|sicherheit_resilienz_SR|oekonomie_familie_)',k)]
    for r in rows:
        for k in flags:
            if r[k] not in ('0','1'):
                raise ValueError(f'Nichtbinärer Wert: {r["satz_id"]} {k}')
            r[k]=int(r[k])
        r['_year']=int(r['sitzung_jahr'])
        r['_day']=r['sitzung_datum'][:10]
        r['_month']=r['_day'][:7]
        r['_party']=PARTY.get(r['redner_fraktion'],r['redner_fraktion'])
        # Amtsrolle: am Beitrag dokumentierte Regierungs- oder andere Amtsrolle (09_Amtsrollen).
        # Maßgeblich ist die Rolle des Beitrags, nicht die Person.
        r['_amt']=int(bool(r['redner_rolle_kurz'].strip() or r['redner_rolle_lang'].strip()))
        if int(r['_day'][:4])!=r['_year']:
            raise ValueError('Jahr und Datum widersprechen sich')
        # Themenzahl je Satz. union und multi vermeiden das Addieren überlappender Treffer.
        r['_dimcount']=sum(r[k] for k in DIM.values())
        r['_union']=int(r['_dimcount']>0)
        r['_multi']=int(r['_dimcount']>=2)
        text=re.sub(r'\s+',' ',r['sent_text'].lower())
        for key,pattern in patterns.items():
            r[key]=int(bool(pattern.search(text)))
        for topic,prefix,maximum in [('oekologie','oekologie_K',7),('oekonomie','oekonomie_G',7),('sicherheit_resilienz','sicherheit_resilienz_SR',5)]:
            if r[topic]!=int(any(r[f'{prefix}{i}'] for i in range(1,maximum+1))):
                raise ValueError(f'Kategorie/Dimension widersprüchlich: {r["satz_id"]}')
        if r['oekonomie']!=int(any(r[k] for k in famcols)):
            raise ValueError('Familien/Ökonomie widersprüchlich')
        if r['oekonomie_G7']!=r['oekonomie_familie_agrardiesel']:
            raise ValueError('G7/Agrardieselfamilie widersprüchlich')
    return rows


def aggregate(master,base,package,satzbasis):
    """Zelländerungen und Kontrollzahlen aus bereits klassifizierten Sätzen erzeugen.

    ``base`` ist die mit read_workbook gelesene Referenzmappe. ``package``
    bezeichnet den Wörterbuchordner. ``satzbasis`` enthält alle Plenarsätze
    und liefert durch Zählung die Gesamtzahlen nach Jahr, Fraktion und Tag.
    Rückgabe: Änderungen nach Blatt/Zelladresse sowie eine
    Zusammenfassung. Erst main()/patch_workbook schreibt eine XLSX.
    Die nachfolgenden Blöcke entsprechen den festen Tabellen der Vorlage.
    """
    corpus=load_satzbasis_totals(satzbasis)
    annual_total=corpus['years']
    rows=load_master(master,base)
    changes=collections.defaultdict(dict)
    # Hash-Abgleich bindet die bestehenden Satzflags an exakt diese Wörterbuchdateien.
    for key,filename in [('oekologie','Woerterbuch_Oekologie.json'),('oekonomie','Woerterbuch_Oekonomie.json'),('sicherheit_resilienz','Woerterbuch_Sicherheit_und_Resilienz.json')]:
        path=Path(package)/filename
        if not path.exists():
            raise ValueError(f'Wörterbuch im Wörterbuchordner fehlt: {filename}')
        expected=sha(path)
        if any(r.get(key+'_dictionary_sha256')!=expected for r in rows):
            raise ValueError(f'Satzmaster passt nicht zum Wörterbuch: {filename}. Themen zuerst neu berechnen.')
    # Die Zuordnung erfolgt nach Blattname, Zeile und Spalte der festen Vorlage.
    # Beispiel: vals(blatt, 9, 'CDE', [a, b, c]) befüllt C9, D9 und E9.
    # stats zählt Satzvorkommen sowie eindeutige Rede-IDs und Kalendertage.

    def put(s,cell,value):
        changes[s][cell]=value

    def vals(s,row,columns,values):
        for c,v in zip(columns,values):
            put(s,f'{c}{row}',v)

    def get(s,row,col):
        return base[s].get(f'{col}{row}')

    source_cells = 0
    def put_source(sheet, cell, value):
        # Diese Kontrolle sichert den festen Abgabebestand ab. Geschrieben
        # wird immer der aus der vollständigen Satzbasis berechnete Wert.
        nonlocal source_cells
        if base[sheet].get(cell) != value:
            raise ValueError(f'Gesamtkorpus weicht von der Referenz ab: {sheet}!{cell} '
                             f'({value} statt {base[sheet].get(cell)}).')
        put(sheet,cell,value)
        source_cells += 1

    def subset(period=None,party=None,day=None,month=None):
        ys=set(years_for(period)) if period is not None else set(YEARS)
        return [r for r in rows if r['_year'] in ys and (party is None or r['_party']==PARTY.get(party,party)) and (day is None or r['_day']==day) and (month is None or r['_month']==month)]

    def count(rs,key):
        return sum(r[key] for r in rs)

    def selected(rs,key):
        return [r for r in rs if r[key]]

    def unique(rs,key):
        return len({r[key] for r in rs})

    def stats(rs,key):
        x=selected(rs,key)
        return [len(x),unique(x,'rede_id'),unique(x,'_day')]
    byyear={y:subset(y) for y in YEARS}
    byday=collections.defaultdict(list)
    for r in rows:
        byday[r['_day']].append(r)
    # Zuerst die gemeinsame Berechnungsbasis füllen. Die übrigen Tabellen
    # beziehen sich durch Formeln auf sie oder erhalten eigene Detailzählungen.
    s='11_Berechnungsbasis'
    expected_days={day_of(get(s,i,'A')) for i in range(90,589)}
    expected_parties={(int(get(s,i,'A')),get(s,i,'B')) for i in range(21,86)}
    if set(corpus['days'])!=expected_days:
        raise ValueError('Die Sitzungstage der vollständigen Satzbasis passen nicht zur Vorlage.')
    if set(corpus['year_party'])!=expected_parties:
        raise ValueError('Die Jahres-/Fraktionsgruppen der vollständigen Satzbasis passen nicht zur Vorlage.')
    # A&E-Jahres-/Fraktions-/Tagesbestände müssen zur festen Vorlage passen.
    # Die Gesamtzahlen je Jahr kommen aus Schritt 1, nicht aus dem Excel-Bestand.
    for i in range(9,17):
        y=int(get(s,i,'A'))
        rs=byyear[y]
        if len(rs)!=get(s,i,'C'):
            raise ValueError(f'A&E-Jahresbestand {y} verändert')
        if annual_total[y]<len(rs):
            raise ValueError(f'Jahresgesamtzahl {y} ist kleiner als der A&E-Jahresbestand.')
        put_source(s,f'B{i}',annual_total[y])
        put_source(s,f'G{i}',len(corpus['year_days'][y]))
        put_source(s,f'I{i}',len(corpus['year_speeches'][y]))
        vals(s,i,'CDEFHJKL',[len(rs),count(rs,'oekologie'),count(rs,'oekonomie'),count(rs,'sicherheit_resilienz'),unique(rs,'_day'),unique(rs,'rede_id'),count(rs,'_union'),count(rs,'_multi')])
    for i in range(21,86):
        rs=subset(get(s,i,'A'),get(s,i,'B'))
        if len(rs)!=get(s,i,'D'):
            raise ValueError(f'A&E-Fraktionsbestand in Zeile {i} verändert')
        group=(int(get(s,i,'A')),get(s,i,'B'))
        put_source(s,f'C{i}',corpus['year_party'][group])
        put_source(s,f'H{i}',len(corpus['party_speeches'][group]))
        vals(s,i,'DEFGIJ',[len(rs),count(rs,'oekologie'),count(rs,'oekonomie'),count(rs,'sicherheit_resilienz'),unique(rs,'rede_id'),unique(rs,'_day')])
    for i in range(90,589):
        d=day_of(get(s,i,'A'))
        rs=byday.get(d,[])
        if len(rs)!=get(s,i,'D'):
            raise ValueError(f'A&E-Tagesbestand {d} verändert')
        put_source(s,f'C{i}',corpus['days'][d])
        put_source(s,f'H{i}',len(corpus['day_speeches'][d]))
        vals(s,i,'DEFGI',[len(rs),count(rs,'oekologie'),count(rs,'oekonomie'),count(rs,'sicherheit_resilienz'),unique(rs,'rede_id')])
    put_source('00_Wegweiser','B30',sum(annual_total.values()))
    vals('00_Wegweiser',31,'B',[len(rows)])
    for i,k in enumerate(DIM.values(),32):
        put('00_Wegweiser',f'B{i}',count(rows,k))

    # Blatt 01 erhält seine Jahresübersicht über die Formeln der Vorlage.
    # Hier folgen zusätzliche Zählungen für Fraktionen und Themenkombinationen.
    s='02_Fraktion_Jahr'
    for i in range(9,17):
        rs=subset(party=get(s,i,'A'))
        vals(s,i,'CEGI',[len(rs),*[count(rs,k) for k in DIM.values()]])
        put_source(s,f'B{i}',sum(corpus['year_party'][(year,get(s,i,'A'))] for year in YEARS))

    # Vergleichspool dieser Tabelle: nur die sechs in PARTIES festgelegten Fraktionen.
    s='03_Fraktionsvergleich'
    for i in range(56,200):
        y,p,dim=[get(s,i,c) for c in 'ABC']
        rs=subset(y,p)
        pool=[r for r in byyear[y] if r['_party'] in PARTIES]
        vals(s,i,'DEFG',[len(rs),count(rs,DIM[dim]),len(pool),count(pool,DIM[dim])])
    for i in range(204,330):
        period,p,dim=[get(s,i,c) for c in 'ABC']
        yy=[int(y) for y in period.split('/')]
        a,b=[subset(y,p) for y in yy]
        vals(s,i,'DEFG',[len(a),count(a,DIM[dim]),len(b),count(b,DIM[dim])])

    # Abdeckung: Sätze mit mindestens einem bzw. mehreren Themenbereichen.
    s='04_Themenzuordnungen'
    for i in range(9,18):
        rs=subset(get(s,i,'A'))
        vals(s,i,'BCF',[len(rs),count(rs,'_union'),count(rs,'_multi')])

    # Tabelle A5: Monatszahlen mit A&E- und Agrardiesel-Jahresnenner.
    # Tabelle A7: Agrardiesel / Ökonomiesätze derselben Fraktion im Jahr 2024.
    s='06_Agrardiesel'
    diesel='oekonomie_G7'
    for i in range(10,46):
        rs=subset(month=get(s,i,'A'))
        year=int(get(s,i,'A')[:4])
        vals(s,i,'BCDEG',[len(rs),*stats(rs,diesel),count(byyear[year],diesel)])
    for i in range(50,66):
        rs=subset(get(s,i,'A'),get(s,i,'B'))
        vals(s,i,'CDEFH',[len(rs),*stats(rs,diesel),count(rs,'oekonomie')])
    # Quartalskonzentration: gleicher Jahresbestand für Zähler und Nenner.
    for i,y in enumerate([2023,2024,2025],71):
        rs=byyear[y]
        q=[r for r in rs if int(r['_month'][-2:])<=3]
        vals(s,i,'BCEF',[count(rs,diesel),count(q,diesel),len(rs),len(q)])
    # Tageszahl aus Abschnitt 4.2: jedes G7-Satzvorkommen am 20. März 2024.
    # Der Jahresnenner enthält dieselbe Kategorie im gesamten Jahr 2024.
    day_hits=selected(subset(day='2024-03-20'),diesel)
    diesel_2024=count(byyear[2024],diesel)
    vals(s,78,'BC',[len(day_hits),diesel_2024])
    # Wortwahl (Tabelle A9): jede Bezeichnung je Satz einmal; Überschneidungen
    # bleiben in beiden Spalten enthalten. Die Gesamtzeile umfasst alle A&E-Sätze.
    s='07_Wortwahl_Fleischwirtschaft'
    for i,p in enumerate(PARTIES,9):
        rs=subset(party=p)
        vals(s,i,'BC',[count(rs,'sg_pestizid'),count(rs,'sg_pflanzenschutzmittel')])
    vals(s,15,'BC',[count(rows,'sg_pestizid'),count(rows,'sg_pflanzenschutzmittel')])
    # Kompakter Nachweis zum Beispiel in Abschnitt 5.4: Fleischwirtschaftssätze
    # ohne eine Zuordnung zu den drei Themenbereichen. Keine neue Kategorie.
    flesh=selected(rows,'sg_fleisch')
    uncoded=[r for r in flesh if not r['_union']]
    vals(s,22,'BC',[len(flesh),len(uncoded)])
    example=next((r for r in uncoded if r['_year']==2020),uncoded[0] if uncoded else None)
    if example:
        put(s,'A26',example['satz_id'])
        put(s,'B26',example['_day'])
        put(s,'C26',example['rede_id'])
        put(s,'A28',example['sent_text'])
    else:
        raise ValueError('Der dokumentierte Fleischwirtschaftsnachweis ohne Themenzuordnung fehlt.')

    # Tabellen A1–A3 speichern beide Bezugsgrößen:
    # alle A&E-Sätze und alle Sätze des jeweiligen Themenbereichs.
    s='08_Kategorien'
    prefix={'Ökologie':'oekologie_K','Ökonomie':'oekonomie_G','S&R':'sicherheit_resilienz_SR'}
    for i in range(9,28):
        dim=get(s,i,'A')
        key=prefix[dim]+str(get(s,i,'B'))
        vals(s,i,'DEG',[count(rows,key),len(rows),count(rows,DIM[dim])])
    for i in range(31,183):
        dim=get(s,i,'A')
        key=prefix[dim]+str(get(s,i,'B'))
        rs=byyear[get(s,i,'D')]
        vals(s,i,'EFH',[count(rs,key),len(rs),count(rs,DIM[dim])])

    # Tabelle A4: Preise/Kosten und Ernährungssicherheit nach Monat 2022.
    # August hat keinen A&E-Nenner; die Quotientenformel zeigt dafür n.a.
    s='05_Unterthemen'
    for i in range(30,42):
        rs=subset(month=get(s,i,'A'))
        vals(s,i,'BCE',[len(rs),count(rs,'oekonomie_G1'),count(rs,'sicherheit_resilienz_SR1')])
    # Tabelle A8: 6 Fraktionen x 4 Zeiträume. Nenner sind Ökonomiesätze,
    # nicht alle A&E-Sätze. 2022 wird als eigener Zeitraum geführt.
    for i in range(47,71):
        rs=subset(get(s,i,'B'),get(s,i,'A'))
        vals(s,i,'CD',[count(rs,'oekonomie_G1'),count(rs,'oekonomie')])

    # Datumsbeleg zur Ernährungssicherheit im selben Blatt wie Jahres-/Monatswerte.
    # Die Abgrenzung nach Datum ist keine Aussage über Ursachen.
    hits=selected(byyear[2022],'sicherheit_resilienz_SR1')
    post=[r for r in hits if r['_day']>='2022-02-24']
    first=min(post,key=lambda r:(r['_day'],r['rede_id'],int(r['sent_idx']))) if post else None
    put(s,'F77',min(r['_day'] for r in hits) if hits else 'n.a.')
    put(s,'F78',max(r['_day'] for r in hits) if hits else 'n.a.')
    put(s,'F79',sum(r['_day']<'2022-02-24' for r in hits))
    put(s,'F80',first['_day'] if first else 'n.a.')
    put(s,'F81',f'Protokoll {first["protokoll_nr"]}, Rede {first["rede_id"]}, Satz {first["sent_idx"]}' if first else 'n.a.')

    # Kontrollrechnung Amtsrollen: Zähler mit und ohne Beiträge aus Amtsrollen je
    # Fraktion und Jahr sowie für den gemeinsamen Pool der sechs Fraktionen.
    # Anteile, Änderungen und die Vorzeichenprüfung rechnen die Formeln der Vorlage.
    s='09_Amtsrollen'
    for i in range(12,60):
        rs=subset(get(s,i,'B'),get(s,i,'A'))
        ohne=[r for r in rs if not r['_amt']]
        vals(s,i,'CDGHLMQR',[len(rs),count(rs,'_amt'),*[n for k in DIM.values() for n in (count(rs,k),count(ohne,k))]])
    for i in range(64,72):
        pool=[r for r in byyear[get(s,i,'A')] if r['_party'] in PARTIES]
        ohne=[r for r in pool if not r['_amt']]
        vals(s,i,'BCEFJKOP',[len(pool),count(pool,'_amt'),*[n for k in DIM.values() for n in (count(pool,k),count(ohne,k))]])

    s='10_Kennzahlen'
    for i,(dim,col) in enumerate(zip(DIM.values(),'DEF'),7):
        best=max(YEARS,key=lambda y:count(byyear[y],dim)/len(byyear[y]))
        br=best-2018+9
        vals(s,i,'BC',[best,f"='11_Berechnungsbasis'!{col}{br}/'11_Berechnungsbasis'!C{br}*100"])
    # Abschnitt 4.1: K1-Satzvorkommen im Jahr 2021 und am 24. Juni 2021.
    # Der Anteil der Sitzung am Jahreswert wird in der Vorlage berechnet.
    put(s,'C23',count(byyear[2021],'oekologie_K1'))
    put(s,'C24',count(subset(day='2021-06-24'),'oekologie_K1'))
    # Herkunftsfelder können bei byteweise neu gespeicherten, inhaltlich gleichen
    # Eingabedateien abweichen. Diese Hashes sind keine fachlichen Ergebniswerte.
    put('00_Wegweiser','A2','Datengrundlage für Ergebnisse und Diskussion')
    put('00_Wegweiser','A3','Analysebestand 2018–2025. Themenzuordnungen nach dem abschließenden Wörterbuchstand.')
    put('00_Wegweiser','A4','Die mitgelieferte Datengrundlage ist Ergebnisbestand und feste Vorlage; Neuberechnungen werden separat gespeichert.')
    put('00_Wegweiser','A28','Aktueller Umfang')

    s='13_Datenstand'
    put(s,'A3','Neuberechnung aus A&E-Satzmaster und vollständiger Satzbasis; Datengrundlage.xlsx liefert den festen Tabellenaufbau.')
    put(s,'A6','Quellen des dokumentierten Berechnungsstands')
    put(s,'B8',Path(master).name)
    put(s,'C8',sha(master))
    put(s,'A9','Vollständige Satzbasis')
    put(s,'B9',Path(satzbasis).name)
    put(s,'C9',sha(satzbasis))
    put(s,'A13','Excel-Vorlage')
    put(s,'C13','Tabellenaufbau, Formeln und drei ergänzende Textsuchregeln. Gesamtplenum-Zahlen aus der Satzbasis neu berechnet.')
    put(s,'B20','Unterschiedliche Datumswerte. Die Gesamtplenartage werden aus der vollständigen Satzbasis ermittelt.')
    dictionary_files={10:'Woerterbuch_Oekologie.json',11:'Woerterbuch_Oekonomie.json',12:'Woerterbuch_Sicherheit_und_Resilienz.json',14:'Woerterbuch_Agrar_Ernaehrung.json'}
    for i,f in dictionary_files.items():
        path=Path(package)/f
        if path.exists():
            put(s,f'C{i}',sha(path))
    for i,v in {40:sum(annual_total.values()),41:len(rows),42:count(rows,'oekologie'),43:count(rows,'oekonomie'),44:count(rows,'sicherheit_resilienz'),45:count(rows,'oekonomie_G1'),46:count(rows,diesel),47:count(rows,'sicherheit_resilienz_SR1'),48:0}.items():
        put(s,f'B{i}',v)
    put_source(s,'B40',sum(annual_total.values()))
    put(s,'B58',sum(r['_amt'] for r in rows if r['_party'] in PARTIES))
    put(s,'B33','auswertung/tabellen_neu_berechnen.py berechnet A&E-Zähler, Gesamtplenum-Zahlen und Formelwerte. Die Vorlage liefert Tabellenaufbau, Formeln und Suchregeln.')
    put(s,'B35','A&E-Zähler aus dem Satzmaster. Gesamtplenum-Zahlen aus der vollständigen Satzbasis und gegen die Referenzwerte geprüft.')
    put(s,'B53','Geführter Gesamtablauf: agrarpolitik-bundestag-2018-2025.ipynb. Tabellenberechnung: auswertung/tabellen_neu_berechnen.py (Python-Standardbibliothek). Vorlage: ergebnisse/Datengrundlage.xlsx; Ausgabe separat.')
    # Jahreswerte der Unterthemen kommen per Formel aus der Kategorieübersicht.
    put('05_Unterthemen','A3','Satzanzahl und Anteil an allen A&E-Sätzen desselben Jahres')
    put('05_Unterthemen','A24','Quelle: '+Path(master).name)
    put('05_Unterthemen','A25','SHA-256: '+sha(master))
    summary={'satzanzahl':len(rows),'themen':{k:count(rows,k) for k in DIM.values()},'kategorien':{prefix[d]+str(i):count(rows,prefix[d]+str(i)) for d in DIM for i in range(1,8 if d!='S&R' else 6)},'jahre':{y:{'plenarsaetze':annual_total[y],'ae':len(byyear[y]),**{k:count(byyear[y],k) for k in DIM.values()}} for y in YEARS},'neu_berechnete_eingabezellen':sum(len(v) for v in changes.values()),'master_sha256':sha(master),'satzbasis_sha256':sha(satzbasis),'plenarsaetze':sum(annual_total.values()),'gepruefte_korpuskennzahlen':source_cells,'amtsrollen_saetze_sechs_fraktionen':sum(r['_amt'] for r in rows if r['_party'] in PARTIES),'agrardiesel_2024_03_20':{'satzvorkommen':len(day_hits),'jahressatzvorkommen':diesel_2024},'fleischwirtschaft':{'satzvorkommen':len(flesh),'ohne_themenzuordnung':len(uncoded)}}
    return dict(changes),summary


def main():
    """CLI-Eingaben lesen, Zellwerte berechnen und die gewünschten Ausgaben schreiben.

    Ohne --output wird keine Arbeitsmappe exportiert. --json-output speichert
    nur die berechneten Zelländerungen, --report die aggregierten Kontrollzahlen.
    Die vollständige Formelneuberechnung erfolgt erst beim XLSX-Export.
    """
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True,help='Neu kodierter A&E-Satzmaster (UTF-8-BOM, Semikolon)')
    parser.add_argument('--template',type=Path,required=True,help='Mitgelieferte ergebnisse/Datengrundlage.xlsx mit 14 Blättern')
    parser.add_argument('--satzbasis',type=Path,required=True,help='Vollständige aufbereitete Satzbasis aus Schritt 1 (CSV oder CSV.gz)')
    parser.add_argument('--dictionaries',type=Path,default=Path(__file__).resolve().parents[1] / 'dictionaries',help='Ordner mit den veröffentlichten Wörterbüchern')
    parser.add_argument('--output',type=Path,help='Neue XLSX; muss von der Vorlage verschieden sein')
    parser.add_argument('--json-output',type=Path,help='Optional: Zelländerungen als JSON für andere Ausgabewege')
    parser.add_argument('--report',type=Path,help='Optional: Kontrollsummen als JSON')
    args=parser.parse_args()
    from ooxml_engine import read_workbook,patch_workbook,audit_formula_caches,calc_workbook,ExcelError
    # 1. Tabellenaufbau lesen und alle veränderlichen Zähler aus den Daten ableiten.
    base=read_workbook(args.template)
    changes,summary=aggregate(args.input,base,args.dictionaries,args.satzbasis)
    changes['13_Datenstand']['B13']=args.template.name
    summary['neu_berechnete_eingabezellen']=sum(len(values) for values in changes.values())
    summary['vorlage_sha256']=sha(args.template)
    if args.json_output:
        args.json_output.write_text(json.dumps(changes,ensure_ascii=False,indent=2),encoding='utf-8')
    if args.output:
        if args.output.resolve()==args.template.resolve():
            raise ValueError('Vorlage und Ausgabe müssen verschieden sein')
        # 2. Eine neue Arbeitsmappe mit den Zählern und berechneten Formelwerten schreiben.
        patch_workbook(args.template,args.output,changes)
        # 3. Gespeicherte Formelwerte erneut lesen und auf vollständigen Export prüfen.
        # Der Vergleich nutzt denselben Formelrechner. Er prüft die Speicherung,
        # nicht unabhängig die fachliche Richtigkeit der Klassifikation.
        cache_audit=audit_formula_caches(args.output)
        if cache_audit['missing_caches'] or cache_audit['mismatches']:
            raise ValueError('Die gespeicherten Excel-Formelwerte weichen von der Neuberechnung ab.')
        if any(isinstance(value,ExcelError) for sheet in calc_workbook(read_workbook(args.output)).values() for value in sheet.values()):
            raise ValueError('Die exportierte Excel-Datei enthält Fehlerzellen.')
        summary['exported_formula_caches']={key:cache_audit[key] for key in ('formulas','matched','missing_caches')}
        summary['exported_formula_caches']['mismatches']=len(cache_audit['mismatches'])
        summary['ausgabe_datei']=args.output.name
        summary['ausgabe_sha256']=sha(args.output)
        summary['status']='tabellen_neu_berechnet'
    if args.report:
        args.report.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
