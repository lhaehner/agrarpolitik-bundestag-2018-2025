# Technische Dokumentation

## 1. Zweck und Ablauf

Das Projekt bildet den festgelegten Analyseablauf der Masterarbeit ab:
Redetexte aufbereiten, in Sätze zerlegen, A&E auswählen, Themenbereiche
zuordnen und die Ergebnisgrundlagen auswerten. Die Programme setzen die
bereitgestellten Wörterbuchregeln deterministisch um. Gemessen wird die
Präsenz der definierten Gegenstandsbezüge im Satz.

Die wissenschaftliche Begründung der Entscheidungen steht im Methodenteil.
Das [Codebuch](../codebuch/Codebuch.pdf) erläutert Begriffe und Zuordnungsregeln. Es ergänzt Anhang B „Aufbau und Abgrenzungen der Wörterbücher“. Anhang C „Daten, Codebuch und Programmcode“ enthält die Übersicht und den Zugang zum GitHub-Repository. Dieses Dokument beschreibt die technische Umsetzung des Analyseablaufs und die verwendeten Dateien.

## 2. Quelle und Korpusaufbereitung

Ausgangsquelle ist Seán Fobbes *Corpus der Plenarprotokolle des Deutschen
Bundestages* (CPP-BT), Version **2026-01-17**:
[Versions-DOI 10.5281/zenodo.18177196](https://doi.org/10.5281/zenodo.18177196).
Verwendet wird `CPP-BT_2026-01-17_DE_CSV_Reden_Gesamt.csv` aus dem
entsprechenden ZIP. Die dortige Variable `saetze` ist eine Quellenstatistik.
Die eigenen Analyseeinheiten entstehen aus den Redetexten.

`korpusaufbereitung/korpus_aufbereiten.py` führt folgende Schritte aus:

| Schritt | Umsetzung |
| --- | --- |
| Zeitraum | Auswahl 2018–2025: 58.939 Quelldatensätze. 43 leere Redetexte erzeugen keine Satzzeilen. |
| Politische Zuordnung | Fehlende Angaben über die festgelegte Personen- und Namenstabelle ergänzen. Beitragsspezifische Korrekturen haben Vorrang. |
| Ergänzungen | 115 Redeblöcke vom 25.09.2025 und 132 vom 17.12.2025 einfügen. |
| Sprechertrennung | Festgelegte Rekonstruktionen der 247 ergänzten und sieben weiteren Blöcke übernehmen und 24 zusätzliche Teilbeiträge abbilden. |
| Textkorrektur | Die 19 bestätigten Listenblöcke in 18 Reden entfernen und das Schlusszeichen nach „Sonderrahmenplan Insektenschutz“ ergänzen. |
| Vorverarbeitung | Weiche Trennzeichen entfernen, Worttrennungen an Zeilenumbrüchen verbinden, übrige Umbrüche und mehrfachen Leerraum vereinheitlichen. |
| Segmentierung | `pysbd==0.3.4`, Sprache `de`, `clean=False`. Satzränder trimmen und leere Ergebnisse verwerfen. |
| Ausgabe | Festgelegte Kennungen, Metadaten und Reihenfolge erhalten. Die gespeicherte Satzdatei vollständig zurücklesen und prüfen. |

Die Bereinigung verwendet ausdrücklich bezeichnete Textbereiche. Sie ist
keine pauschale Entfernung sämtlicher Regieangaben. Der fertige Bestand
enthält 1.912.729 Satzvorkommen aus 59.167 Beitragskennungen mit Satzzeilen.

### Feste Korrekturdaten

Die sechs Dateien in `korpusaufbereitung/konfiguration/` sind Teil der
Reproduktionsgrundlage:

| Datei | Aufgabe |
| --- | --- |
| `fraktionszuordnung.json` | Fehlende politische Zuordnungen ergänzen |
| `metadatenkorrekturen.json` | Festgelegte beitragsspezifische Angaben und Standardfelder setzen |
| `satzkorrekturen.json` | Bezeichnete Satzbereiche nach der Segmentierung ersetzen |
| `ergaenzungen.json` | Ergänzte Redeblöcke und getrennte Sprecherpassagen einfügen |
| `satzkennungen.json` | Bestehende Kennungen und abweichende Positionsangaben erhalten |
| `referenz.json` | Eingangs- und Inhaltsprüfwerte sowie erwartete Ausgabestruktur festlegen |

Die Angaben unter `herkunft` dokumentieren die Herkunft der Korrekturdaten. Sie werden nicht als Programme oder zusätzliche Eingabepfade verwendet.

Die [Dokumentation der Korpuskorrekturen](Korpuskorrekturen.md) verbindet die
festgelegten Eingriffe mit ihren Fundstellen und Quellen. Sie erläutert auch,
welche politischen Zuordnungen als zeitlose Ergänzungstabelle übernommen
wurden und welchen Umfang deren historische Überprüfung abdeckt.

Diese Daten wurden aus den festgelegten Eingriffen und dem verbindlichen
Satzbestand konsolidiert. Die Januartexte werden neu segmentiert. Abweichende
Bereiche werden durch die bezeichneten Korrekturen ersetzt. Ergänzte und
getrennte Beiträge werden mit ihren festgelegten Sätzen übernommen.
Die ursprüngliche XML-Extraktion dieser Ergänzungen und Sprechertrennungen
wird nicht erneut ausgeführt. Die reparierte Zieldatei ist für den Lauf ab
Januarquelle nicht erforderlich. Der Lauf verwendet die mitgelieferten
Korrekturdaten und prüft den festgelegten Quellenstand vom 17.01.2026.

### Politische Zuordnung und Quellenfelder

`redner_fraktion` enthält die für die Analyse verwendete politische Zuordnung.
Bei Amts- und Regierungsrollen ist dies eine rollenbezogene politische
Zuordnung und keine durchgängig reine Fraktionsmitgliedschaftsvariable.
Die Rollenfelder bleiben erhalten. Fehlende Zuordnung und belegte
Fraktionslosigkeit bleiben unterscheidbar. Einzelne Korrekturen stehen in
den Konfigurationsdateien.

Felder mit `_original` gehören zum übernommenen Prüfbestand. Sie enthalten
teilweise eigene Bearbeitungen und sind nicht pauschal mit unveränderten
Fobbe-Quellfeldern gleichzusetzen. Diese sind im Ausgangsarchiv
nachprüfbar. Das Januararchiv enthält bereits `version=2026-01-17` zusammen
mit `doi_version=10.5281/zenodo.15462956`. Dieser übernommene Feldinhalt wird
nicht überschrieben. Bibliografisch maßgeblich bleibt die oben angegebene
Versions-DOI **10.5281/zenodo.18177196**.

## 3. Wörterbuchanwendung

`src/satzmatcher.py` liest die vollständige Satzbasis, führt den A&E-Filter
aus und wendet auf die ausgewählten Sätze die drei Themenwörterbücher an.
Ein gültiger Treffer genügt für den Wert 1. Weitere Treffer erhöhen diesen
Satzwert nicht. Mehrere Themenbereiche, Kategorien oder Familien können
zugleich zugeordnet sein. Ein A&E-Satz kann auch in keinem der drei
Themenbereiche einen Treffer haben.

Die vier Wörterbücher verwenden unterschiedliche Datenschemata und
Normalisierungen. Diese Unterschiede gehören zum ausgeführten Verfahren:

| Wörterbuch und Modul | Technische Umsetzung |
| --- | --- |
| A&E — `ae_matcher.py` | Ausdrücklich definierte Regex-Wortstämme und Mehrwortfolgen mit positiven und negativen Kontexten, Zeichenfenstern und lokalen Ausnahmen |
| Ökologie — `oekologie_matcher.py` | Geschlossene Formenlisten mit zugehörigen Regex, lokalen Ausschlüssen und bestimmten Folgekontexten |
| Ökonomie — `oekonomie_matcher.py` | Vollständige normalisierte Tokenformen mit Wortfamilien, lokalen Ausschlüssen und satzweiten Grundform-Ausschlüssen |
| S&R — `sr_matcher.py` | Geschlossene Formen, Direktregeln und Kombinationen zweier Ausdrucksgruppen innerhalb desselben Satzes |

**A&E:** `patterns` enthält 427 Regeln: 352 Direktregeln, 48 Kontextregeln
und 27 lokale Ausschlüsse. `role` bezeichnet ihre Funktion: `direct` für
Direktregeln, `context` für Kontextregeln und `exclusion` für lokale Ausschlüsse.
Alle enthaltenen Regeln werden entsprechend ihrer Funktion ausgeführt.
Eine Direktregel benötigt keinen positiven Kontextpartner. Eine Kontextregel
begründet die Zuordnung nur bei erfüllter Kontextbedingung. Lokale Ausschlüsse
verwerfen bestimmte Fundstellen. Andere gültige Treffer im Satz bleiben wirksam.
Der Matcher prüft beim Laden, ob Regelfunktion und benötigte Angaben zusammenpassen.
Die Regelkennungen erscheinen in den Trefferbelegen. Präfixe wie `shadow:`
sind dabei Bestandteil der Kennung. Die Regelfunktion steht im Feld `role`.

`context_any` fordert einen positiven Kontextpartner. `context_none` prüft
negative Kontexte. `context_window` misst Zeichenabstände.
`context_boundary: clause` begrenzt an `. ; : ! ?`. `context_distinct`
verhindert eine überlappende Selbstbestätigung. Lokale Ausschlüsse können
auch eine Fundstelle als Kontextpartner ausschließen. `exception_rule_keys`
nennt Ausnahmen.

**Ökologie:** `entries` verbindet `forms`, `regex`, Kategorie und Untergruppe.
Die Formen dienen der Vorauswahl, das Regex prüft die Fundstelle.
`following_context_regex` begrenzt bestimmte Ergänzungsstrichformen.
`exclusions` maskiert über `entry_ids` lokale Treffer. Eine `capture_group`
kann die Zielspanne einschränken.

**Ökonomie:** `gruppen`, `familien` und `unterkategorien` ordnen die Formen.
Ungelistete Flexionen und Komposita werden nicht automatisch ergänzt.
`lokale_ausschlussregeln` entfernt konkrete Vorkommen. `kontextregeln`
entfernt die betroffene Grundform satzweit. `nicht_erfasst` ist eine
Erläuterung und keine zusätzliche ausführbare Sperrliste.

**S&R:** `lexemes` definiert Formen, `direct_rules` ihre Direktzuordnung.
`cooccurrence_rules` verlangt mindestens einen Ausdruck aus `any_a` und einen
aus `any_b` im selben Satz. Reihenfolge und Abstand sind frei. Eine zusätzliche
grammatische Verbindung wird nicht geprüft. `local_exclusions` maskiert
benannte Namensverwendungen.

Erläuterungen der JSONs stehen in regulären Datenfeldern wie `description`,
`notes`, `reason` oder `hinweise`. JSON-Kommentare mit `//` sind nicht vorgesehen.
`schema_version` kennzeichnet das vom jeweiligen Matcher erwartete Dateiformat.
Regelkennungen verbinden die Wörterbucheinträge mit ihren Trefferbelegen.
Das Codebuch wird beim Programmlauf nicht eingelesen.

## 4. Satzdateien und Ergebnisfelder

Die CSV-Dateien verwenden Semikolon als Trennzeichen und UTF-8, gegebenenfalls
mit BOM. `.csv.gz` bezeichnet eine verlustfrei komprimierte CSV. Kennungen
sind als Text zu behandeln. Pflichtfelder des Matchers sind `rede_id`,
`sent_idx`, `sent_text` und `sitzung_jahr`. Eine vorhandene `satz_id` bleibt
erhalten. Andernfalls wird sie als `rede_id:sent_idx` gebildet.

| Feld oder Feldgruppe | Bedeutung |
| --- | --- |
| `rede_id`, `ursprungs_rede_id` | Beitragskennung und Bezug zum ursprünglichen Beitrag |
| `satz_id`, `sent_idx`, `satzposition` | Satzkennung, Kennungsindex und Reihenfolge nach Bearbeitung. Index und Position können verschieden sein |
| `sent_text` | Analysierter Satztext |
| `sitzung_jahr`, `sitzung_datum`, `wahlperiode`, `sitzung_nr` | Zeitliche und parlamentarische Einordnung |
| `redner_*`, `zugehoerigkeit_*` | Sprecherangaben, Rolle und politische Zuordnung |
| `korpus_reparatur_status`, `quellstatistik_status` | Hinweise zur übernommenen Bearbeitung und zu Quellenstatistiken |
| `zeichen`, `tokens`, `typen`, `saetze` | Übernommene Quellenstatistiken, keine neu gezählten Satzmerkmale |
| `agrar_ernaehrung` | Politikfeldzuordnung, im ausgegebenen A&E-Master stets 1 |
| `oekologie`, `oekonomie`, `sicherheit_resilienz` | Drei getrennte 0/1-Themenkennzeichen |
| `oekologie_K*`, `oekonomie_G*`, `sicherheit_resilienz_SR*` | 0/1-Kategoriekennzeichen. Definitionen in den Wörterbüchern und im Codebuch |
| `oekonomie_familie_*` | 0/1-Kennzeichen der Ökonomiefamilien |
| `dimensionen_anzahl`, `dimensionen_mindestens_eine` | Zahl zugeordneter Themenbereiche (0–3) beziehungsweise mindestens ein Themenbereich (0/1) |
| `agrar_ernaehrung_hit_*`, `*_trefferbegriffe_json`, `*_trefferformen_json` | Auslösende Regelkennungen, Begriffe und Formen |
| `*_evidence_json` | Strukturierte Fundstellen und Angaben zu angewandten Regeln oder Ausschlüssen |
| `*_dictionary_sha256` | Fingerabdruck der verwendeten Themenwörterbuchdatei |

`oekonomie_ohne_agrardieselfamilie` zählt Sätze mit mindestens einer anderen
Ökonomiefamilie. `oekonomie_ohne_agrardieselsaetze` zählt Ökonomiesätze, die
nicht der Kategorie G7 zugeordnet sind. Die beiden zusätzlichen Felder bleiben
zur Beschreibung des bereitgestellten Satzmasters erhalten. Sie werden für
die berichteten Ergebnistabellen nicht verwendet.

`agrar_ernaehrung_evidence_count` zählt Trefferfamilien,
`agrar_ernaehrung_hit_count` einzelne Fundstellen. Beides ist von der binären
Politikfeldzuordnung zu unterscheiden. JSON-Spalten enthalten strukturierte
Listen oder Objekte in einer CSV-Zelle.

Fundstellenpositionen sind nicht zwischen den Matchern austauschbar:
A&E und S&R dokumentieren Originalspannen. Ökologie dokumentiert Positionen
im normalisierten Text. Ökonomie weist normalisierte Formen und gegebenenfalls
normalisierte Ausschlusspositionen aus. Positionsbereiche verwenden
Python-Indizes: Beginn einschließlich, Ende ausschließlich.
`source_spans.py` führt normalisierte A&E-Fundstellen auf den Originalsatz zurück.

## 5. Auswertung und Bezugsgrößen

Gezählt werden Satzvorkommen. Identischer Wortlaut unter verschiedenen
Satzkennungen wird nicht als Dublette entfernt. Für den Politikfeldanteil
wird die A&E-Satzzahl durch die Gesamtzahl aller berücksichtigten Plenarsätze
desselben Jahres geteilt. Diese Gesamtzahlen werden direkt aus der vollständigen Satzbasis gezählt und in der Excel-Auswertung ausgewiesen. Für Themenanteile innerhalb A&E ist die A&E-Satzzahl die
Bezugsgröße. Fraktions- und Periodenvergleiche verwenden die jeweils
zugehörige Teilmenge. Mehrfachzuordnungen bleiben bei der Interpretation
von Summen zu beachten.

| Jahr | Gesamtzahl der Plenarsätze |
| --- | ---: |
| 2018 | 242.148 |
| 2019 | 259.488 |
| 2020 | 244.311 |
| 2021 | 175.631 |
| 2022 | 269.405 |
| 2023 | 275.800 |
| 2024 | 241.408 |
| 2025 | 204.538 |
| **Gesamt** | **1.912.729** |

`auswertung/tabellen_neu_berechnen.py` berechnet die Zähler und Formelwerte der Excel-Auswertung. Die Gesamtzahlen der Plenarsätze, Beiträge und Sitzungstage werden aus der vollständigen aufbereiteten Satzbasis neu ermittelt.

`ergebnisse/Datengrundlage.xlsx` liefert als feste Vorlage den Tabellenaufbau, Zellzuordnungen, Formeln und die ergänzenden Textsuchregeln aus `12_Begriffe_Suchregeln`. Die Regelarten bleiben getrennt: Wörterbuchzuordnungen stammen aus dem Satzmaster, ergänzende Textsuchen werden für die Wortwahlanalyse und den Fleischwirtschaftsnachweis ausgeführt. Der Rechner verwendet die festgelegten Jahre, Fraktionen und Tabellenbereiche dieses Analysebestands. `00_Wegweiser` weist die Bezüge zu den Ergebnistabellen und Abbildungen der Arbeit aus.

Die Vorlage wird nicht überschrieben. Das Notebook erzeugt `Datengrundlage_neu_berechnet.xlsx`. Die bereits bereitgestellte Auswertung liegt unter `ergebnisse/Datengrundlage.xlsx`. Aufruf und Eingaben stehen in [auswertung/README.md](../auswertung/README.md).

### Unterthemen und Wortwahl

Die Monatsauswertung für 2022 enthält die Kategorie Preise und Kosten (G1)
und Ernährungssicherheit (SR1). Ihr Monatsanteil bezieht sich jeweils auf die
A&E-Sätze desselben Monats. Ohne A&E-Sätze ist der Anteil nicht definiert.
Die Fraktionsauswertung von Preise und Kosten verwendet als Nenner die
ökonomisch zugeordneten Sätze derselben Fraktion im jeweiligen Zeitraum:
2018–2025, 2018–2021, 2022 oder 2023–2025.

`10_Kennzahlen!A23:D25` weist die 394 Satzvorkommen der Kategorie K1
(Pflanzenschutz und Artenvielfalt) im Jahr 2021 und die darin enthaltenen
194 Vorkommen vom 24. Juni 2021 aus. Die Auswahl beruht auf Kategorie und
Sitzungsdatum; der Anteil der Sitzung am Jahreswert wird als Quotient berechnet.

Die Wortwahlauswertung zählt unabhängig von den Themenzuordnungen Sätze
mit Wortformen, die mit Pestizid oder Pflanzenschutzmittel beginnen. Ein Satz
zählt je Bezeichnung einmal und kann in beiden Spalten enthalten sein.
Die Gesamtwerte 274 und 467 schließen fraktionslose Beiträge ein.

### Tageszählung zum 20. März 2024

Die Agrardieselauswertung weist in `06_Agrardiesel!A76:D78` die 101
Satzvorkommen der Kategorie G7 vom 20. März 2024 aus. Der Anteil wird durch
die 348 Agrardieselsätze des Jahres 2024 geteilt. Die Auswahl verwendet
ausschließlich das Sitzungsdatum und die vorhandene Kategoriezuordnung.
Wie bei den übrigen Auswertungen zählt jedes Satzvorkommen.

### Ergänzende Kontrollrechnung zu Amtsrollen

Das Blatt `09_Amtsrollen` ergänzt den Fraktionsvergleich aus Abschnitt 4.3 der Arbeit. Als Amtsbeitrag gilt ein Beitrag, bei dem mindestens eines der Felder `redner_rolle_kurz` oder `redner_rolle_lang` nach Entfernen äußerer Leerzeichen gefüllt ist. Maßgeblich ist die am Beitrag dokumentierte Rolle. Andere Beiträge derselben Person ohne diese Kennzeichnung bleiben enthalten.

Das Skript berechnet für jede der sechs Vergleichsfraktionen und jedes Jahr die A&E- und Themenzähler mit und ohne die so gekennzeichneten Sätze. Die Formeln der Vorlage verkleinern sowohl Themenzähler als auch A&E-Nenner. Der gemeinsame Jahreswert wird aus dem ebenfalls reduzierten Pool derselben sechs Fraktionen gebildet. Tabelle 3 prüft für alle acht Jahre fünf Abstände zu diesem Jahreswert: Grüne Ökologie darüber, AfD Ökologie darunter, SPD Ökonomie darunter sowie AfD und Linke Ökonomie darüber.

Im festgelegten Analysebestand werden dabei 2.656 A&E-Sätze ausgeschlossen. Diese Kontrollzahl steht in `13_Datenstand!B58` und im Berechnungsbericht unter `amtsrollen_saetze_sechs_fraktionen`. Die Hauptauswertung bleibt unverändert. Die Kontrollrechnung betrifft die dokumentierten Beitragsrollen, nicht den Einfluss der Regierungs- oder Oppositionsstellung einer Fraktion.

## 6. Ausführen und prüfen

Der Einstieg ist in der [README](../README.md) beschrieben. Der Vorbereitungsabschnitt des Colab-Notebooks lädt Programme, die vier Wörterbücher, Korrekturdaten, Vergleichsgrundlagen und Excel-Vorlage aus dem festgelegten GitHub-Abgabestand. Das unveränderte Redenarchiv `CPP-BT_2026-01-17_DE_CSV_Reden_Gesamt.zip` wird direkt aus [Zenodo-Record 18177196](https://doi.org/10.5281/zenodo.18177196) geladen. Seine erwartete MD5-Prüfsumme lautet `9b03325c65c6930bc5e44d4206ce3d42`. Im Notebook sind keine Archive oder Datendateien eingebettet.

Nach der Vorbereitung führt das Notebook linear durch Korpusaufbereitung, Wörterbuchanwendung, Excel-Auswertung mit Validierungsrechnung und Download. Zwischenergebnisse werden innerhalb der Sitzung weitergegeben. Die separat beim GitHub-Release bereitgestellte Datei `Saetze_2018-2025.csv.gz` ermöglicht den direkten Zugang zur vollständigen Satzbasis. Der Notebook-Ablauf erzeugt sie selbst und benötigt diese Release-Datei nicht als Eingabe.

Die Programmdateien liegen separat lesbar in den jeweiligen Ordnern. Die Ausführungszellen im [Colab-Notebook](../agrarpolitik-bundestag-2018-2025.ipynb) rufen diese Dateien auf und übergeben Eingabe- und Ausgabepfade. Die Texte zu den Arbeitsschritten erklären die Funktion der Programme und Eingabedateien und verlinken sie im GitHub-Abgabestand `abgabe-v1.0`. Die kommentierten Programme sind dort ohne Ausführung des Notebooks lesbar. Ergebnislinks führen zu den bereits bereitgestellten Dateien, die neu berechneten Dateien entstehen in der Colab-Sitzung. `src/ablauf.py` lädt die Zenodo-Quelldatei und stellt später den Berechnungsbericht sowie das Ergebnis-ZIP zusammen. Die fachlichen Regeln stehen in den Wörterbüchern und den Programmen der Ordner `korpusaufbereitung`, `src` und `auswertung`.

Für lokale Ausführung werden Python 3.10 oder neuer und `pysbd==0.3.4` benötigt. Die vollständige Befehlsfolge steht in [Ausfuehrung_lokal.md](Ausfuehrung_lokal.md). Sie wird im Projekt-Hauptverzeichnis gestartet und schreibt neue Ergebnisse in `lauf/`.

Die Aufbereitung prüft alle 48 Ausgabefelder und die Zeilenfolge der vollständig zurückgelesenen Satzbasis. `reproduktion/satzmaster_pruefen.py` prüft 146 Inhaltsfelder pro A&E-Satz in Reihenfolge. JSON-Belege werden strukturell ausgewertet. Die drei Wörterbuch-Dateihashes sind vom Inhaltsvergleich ausgenommen. Sie werden gesondert dokumentiert, weil auch reine Formatierungsänderungen eine Dateiprüfsumme verändern. Die Referenzwerte sind festgehaltene Vergleichswerte und keine unabhängig erhobenen Validierungsdaten.

`Laufbilanz.json` protokolliert die Korpusaufbereitung. Das Satzmaster-Manifest dokumentiert Eingaben, Prüfsummen und Anzahlen der Wörterbuchanwendung. Das Notebook fasst erfolgreiche Prüfungen in `Bericht_zur_Berechnung.txt` zusammen. Sein Ergebnis-ZIP enthält diesen Bericht, den A&E-Satzmaster, die neu berechnete Excel-Auswertung sowie die Gütemaße und den Bericht der Validierungsrechnung. Die vollständige Satzbasis wird dabei nicht nochmals verpackt.

Die beiden abgeschlossenen Validierungsdateien liegen unter `validierung/`. Sie dokumentieren die inhaltliche Prüfung des A&E-Filters und der Themenwörterbücher. Die Hinweise in den Arbeitsmappen beschreiben die Stichprobenziehung. Historische Dateinamen und Prüfsummen bezeichnen den damaligen Ziehungsstand. Die technische Reproduktionsprüfung ersetzt diese inhaltliche Validierung nicht.

`validierung/kennzahlen_berechnen.py` berechnet aus den vorhandenen
Handcodierungen und den maschinellen Satzzuordnungen die Gütemaße aus
Tabellen 5 und 6. Es prüft die Zuordnung der Stichprobensätze zu den
Satzdateien. Präzision und Recall der Themenbereiche werden aus den
entsprechenden Übereinstimmungs- und Fehlklassifikationszahlen ermittelt.
Die hochgerechnete Trefferquote des Politikfeldfilters berücksichtigt die
Größen der Treffer- und Nichttrefferbestände. Berechnungsverfahren und
Intervallbildung stehen in [validierung/README.md](../validierung/README.md).
Die erneute Rechnung verwendet die abgeschlossenen menschlichen Codierungen
und ist keine neue Handcodierung.
