# Tabellenberechnung

`tabellen_neu_berechnen.py` berechnet die satzbasierten Zähler und Formelwerte
der Excel-Datengrundlage nach. Im Colab-Notebook wird dieses
Skript in Schritt 3 ausgeführt. Es benötigt:

- den neu erzeugten A&E-Satzmaster mit Themenzuordnungen,
- die vollständige Satzbasis aus Schritt 1,
- die vier unveränderten Wörterbuchdateien,
- `ergebnisse/Datengrundlage.xlsx` als feste Vorlage für Tabellenaufbau, Formeln und ergänzende Suchregeln.

Die Gesamtzahlen der Plenarsätze, Plenartage und Beiträge werden aus der
vollständigen Satzbasis ermittelt. Ein Beitrag ist eine eindeutige `rede_id`,
ein Sitzungstag ein unterschiedlicher Datumswert. Für die jährlichen Gesamtzahlen
zählt jede Zeile der Satzbasis als ein Satzvorkommen ihres Sitzungsjahres.

Der Rechner ist auf den dokumentierten Abgabestand mit 25.247 A&E-Sätzen und
die mitgelieferte Vorlage abgestimmt. Die neu ermittelten Gesamtplenum-Zahlen
werden mit deren Referenzwerten verglichen. Abweichungen führen zu einer
Fehlermeldung.

Aufruf aus dem Projekt-Hauptordner:

```bash
python auswertung/tabellen_neu_berechnen.py \
  --input lauf/Satzmaster_Agrar_Ernaehrung.csv.gz \
  --satzbasis lauf/korpus/Saetze_2018-2025.csv.gz \
  --dictionaries dictionaries \
  --template ergebnisse/Datengrundlage.xlsx \
  --output lauf/Datengrundlage_neu_berechnet.xlsx \
  --report lauf/Pruefung_Excel.json
```

Die Pfade zu Satzbasis und Satzmaster müssen den zuvor erzeugten
Dateien entsprechen. Das Notebook übernimmt diese Zuordnung automatisch.

`00_Wegweiser` ordnet die Tabellen und Abbildungen der Arbeit konkreten
Blättern und Zellbereichen zu. Die Auswertung enthält die Monatswerte für
Preise und Kosten 2022 (A4), die Fraktions- und Periodenwerte dieser Kategorie
(A8), die Wortwahlwerte aus A9 sowie die Tageszählung zum 20. März 2024.
Für diesen Tag werden 101 Agrardieselsätze gezählt; der Anteil bezieht sich
auf die 348 Agrardieselsätze des Jahres 2024. Wie in der Hauptauswertung
zählt jedes Satzvorkommen, auch bei gleichem Wortlaut in mehreren Beiträgen.
`10_Kennzahlen!A23:D25` belegt außerdem die 194 von 394 Sätzen zu
Pflanzenschutz und Artenvielfalt 2021 aus der Sitzung vom 24. Juni.

Die Gütemaße aus Tabellen 5 und 6 werden separat durch
[`validierung/kennzahlen_berechnen.py`](../validierung/kennzahlen_berechnen.py)
aus den vorhandenen Handcodierungen und Satzdateien berechnet. Die technische
Prüfung der Excel-Formeln ist von dieser inhaltlichen Validierung zu unterscheiden.

Blatt `09_Amtsrollen` ist eine ergänzende Kontrollrechnung zum Fraktionsvergleich
(Abschnitt 4.3 der Arbeit): Themenanteile und gemeinsamer Jahreswert werden
zusätzlich ohne die Beiträge berechnet, für die im Satzmaster eine Regierungs-
oder andere Amtsrolle dokumentiert ist (`redner_rolle_kurz` oder
`redner_rolle_lang` gefüllt). Das Skript schreibt dafür nur die Satzzähler mit
und ohne diese Beiträge; Anteile, Änderungen in Prozentpunkten und die
Vorzeichenprüfung der fünf wiederkehrenden Unterschiede aus Abschnitt 4.3 rechnen die Formeln der
Vorlage. Die Kontrollsumme der ausgeschlossenen Sätze steht in
`13_Datenstand` (Block „Ergänzende Kontrollrechnung“).

`--report` speichert Satzanzahlen, Eingabe-Prüfsummen und bei Excel-Ausgabe das
Ergebnis der Prüfung gespeicherter Formelwerte. Die Vorlage darf nicht als
Ausgabeziel dienen.

`ooxml_engine.py` unterstützt die in dieser konkreten Arbeitsmappe verwendeten
Formeln. Das Hilfsmodul übernimmt das vorhandene Excel-Layout und schreibt die
neu berechneten Formelwerte. Anschließend werden die gespeicherten Formelwerte
erneut gelesen und mit der Berechnung verglichen. Dieser technische Vergleich
ersetzt keinen Öffnungstest mit Microsoft Excel. Das Modul verwendet nur die
Python-Standardbibliothek und ist auf den Formelumfang dieser Vorlage begrenzt.
