# Lokale Ausführung

Die kommentierten Programme können direkt auf dem eigenen Rechner ausgeführt werden. Verwendet werden die Dateien des GitHub-Abgabestands und die ursprünglichen Reden von Zenodo. Alternativ übernimmt [agrarpolitik-bundestag-2018-2025.ipynb](../agrarpolitik-bundestag-2018-2025.ipynb) die Vorbereitung und führt durch dieselben Berechnungsschritte.

## Vorbereitung

Den zum Abgabestand gehörenden Repository-Inhalt herunterladen oder klonen und das Projekt-Hauptverzeichnis öffnen. Benötigt werden Python 3.10 oder neuer, eine Internetverbindung für den Download sowie ausreichend Speicherplatz für die Quelle und die erzeugten Dateien.

Ausgangsdatei ist ausschließlich `CPP-BT_2026-01-17_DE_CSV_Reden_Gesamt.zip` aus [Zenodo-Record 18177196](https://doi.org/10.5281/zenodo.18177196). Die folgenden Befehle laden sie nach `lauf/quelle/` und installieren die benötigte Bibliothek. Sie sind für eine Bash-Shell angegeben.

```bash
mkdir -p lauf/quelle
curl --fail --location --output lauf/quelle/CPP-BT_2026-01-17_DE_CSV_Reden_Gesamt.zip 'https://zenodo.org/records/18177196/files/CPP-BT_2026-01-17_DE_CSV_Reden_Gesamt.zip?download=1'
python -m pip install -r requirements.txt
```

Das Archiv bleibt gepackt. Die Aufbereitung liest die darin enthaltene CSV-Datei und prüft den festgelegten Quellenstand. Die große aufbereitete Satzbasis unter **Releases** wird für diesen Ablauf nicht benötigt, da sie im ersten Schritt neu entsteht.

## Berechnung

Die Befehle werden nacheinander im Projekt-Hauptverzeichnis ausgeführt. Sie schreiben neue Ergebnisse nach `lauf/`. Der Unterordner `lauf/korpus/` darf vor Schritt 1 noch nicht bestehen.

**1. Korpus aufbereiten.** `korpusaufbereitung/korpus_aufbereiten.py` erzeugt die vollständige aufbereitete Satzbasis. Ergänzungen und Korrekturen stehen in `korpusaufbereitung/konfiguration/`.

```bash
python korpusaufbereitung/korpus_aufbereiten.py --quelle lauf/quelle/CPP-BT_2026-01-17_DE_CSV_Reden_Gesamt.zip --ausgabe lauf/korpus --prozesse 2
```

**2. Wörterbücher anwenden und Satzmaster prüfen.** `src/satzmatcher.py` wendet den A&E-Filter und die drei Themenwörterbücher an. Das Prüfskript vergleicht die erzeugten Satzmasterinhalte mit dem festgelegten Analysebestand.

```bash
python src/satzmatcher.py --input lauf/korpus/Saetze_2018-2025.csv.gz --dictionaries dictionaries --output lauf/Satzmaster_Agrar_Ernaehrung.csv.gz
python reproduktion/satzmaster_pruefen.py --satzmaster lauf/Satzmaster_Agrar_Ernaehrung.csv.gz --protokoll lauf/Pruefung_Satzmaster.json
```

**3. Auswertung berechnen.** `auswertung/tabellen_neu_berechnen.py` berechnet die Auswertung aus dem Satzmaster und der vollständigen Satzbasis. Die Gesamtzahlen der Plenarsätze werden dabei direkt aus der Satzbasis gezählt. Die Vorlage bestimmt Tabellenaufbau, Formeln und ergänzende Suchregeln. Die Berechnung umfasst auch das ergänzende Blatt `09_Amtsrollen`.

```bash
python auswertung/tabellen_neu_berechnen.py --input lauf/Satzmaster_Agrar_Ernaehrung.csv.gz --satzbasis lauf/korpus/Saetze_2018-2025.csv.gz --dictionaries dictionaries --template ergebnisse/Datengrundlage.xlsx --output lauf/Datengrundlage_neu_berechnet.xlsx --report lauf/Pruefung_Excel.json
```

Der Bericht `Pruefung_Excel.json` enthält die technischen Prüfergebnisse der Tabellenberechnung. Die Kontrollzahl `amtsrollen_saetze_sechs_fraktionen` beträgt im festgelegten Analysebestand 2.656. Sie bezeichnet die für die ergänzende Amtsrollenrechnung ausgeschlossenen A&E-Sätze. Zusätzlich wird der Abgleich der gespeicherten Excel-Formelwerte dokumentiert.

**4. Gütemaße der Validierung berechnen.** Die vorhandenen menschlichen
Codierungen werden mit den maschinellen Zuordnungen und der vollständigen
Satzbasis verknüpft. Das Programm berechnet die Kennzahlen und Intervalle
der Tabellen 5 und 6. Die beiden Codierdateien bleiben unverändert.

```bash
python validierung/kennzahlen_berechnen.py --satzmaster lauf/Satzmaster_Agrar_Ernaehrung.csv.gz --validierung-themen validierung/Validierung_AE_und_Themen_1000.xlsx --validierung-recall validierung/Validierung_AE_Recall_3000.xlsx --satzbasis lauf/korpus/Saetze_2018-2025.csv.gz --output lauf/Guetemasse_Validierung.csv --report lauf/Pruefung_Validierung.json
```

Der Bericht enthält die Stichprobenumfänge, Verknüpfungsprüfungen,
Fehlklassifikationszahlen und berechneten Kennzahlen. Er bestätigt die
Nachrechnung aus den abgelegten Codierungen, keine erneute menschliche
Bewertung. Im Colab-Notebook sind Excel- und Validierungsrechnung gemeinsam
in Schritt 3 zusammengefasst.

## Ausgaben

| Datei unter `lauf/` | Inhalt |
| --- | --- |
| `korpus/Saetze_2018-2025.csv.gz` | Vollständige aufbereitete Satzbasis |
| `korpus/Laufbilanz.json` | Anzahlen und technische Prüfungen der Aufbereitung |
| `Satzmaster_Agrar_Ernaehrung.csv.gz` | Ausgewählte A&E-Sätze mit Themenzuordnungen und Trefferbelegen |
| `Pruefung_Satzmaster.json` | Ergebnis des Vergleichs mit den festgelegten Satzmasterinhalten |
| `Datengrundlage_neu_berechnet.xlsx` | Neu berechnete Excel-Auswertung |
| `Pruefung_Excel.json` | Technische Prüfungen der Excel-Berechnung |
| `Guetemasse_Validierung.csv` | Neu berechnete Gütemaße einschließlich der 95%-Intervalle |
| `Pruefung_Validierung.json` | Grundlagen, Verknüpfungsprüfungen und Kennzahlen der Validierungsrechnung |

Zusätzlich erstellt die Wörterbuchanwendung ein Manifest mit Angaben zu Eingaben, Prüfsummen und Anzahlen. Im Notebook fasst `src/ablauf.py` die Ergebnisse für einen kurzen lesbaren Bericht und den gemeinsamen ZIP-Download zusammen. Diese Hilfsfunktionen ergänzen keine fachlichen Trefferregeln.

Der Ablauf wiederholt die konsolidierte Aufbereitung mit festgelegten Korrekturdaten. Die ursprüngliche Beschaffung und XML-Extraktion ergänzender Beiträge wird nicht erneut ausgeführt. Die Vergleichsprüfungen bestätigen technische Übereinstimmung mit dem festgelegten Bestand, nicht die inhaltliche Güte der Wörterbuchregeln.
