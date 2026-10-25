# Daten, Codebuch und Programmcode zur Masterarbeit

**Agrarpolitik im Wandel? Eine quantitative Korpusanalyse des Deutschen Bundestages (2018–2025)**  
Linus Hähner · Stand: 22. Oktober 2026

[![In Colab öffnen](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/lhaehner/agrarpolitik-bundestag-2018-2025/blob/abgabe-v1.0/agrarpolitik-bundestag-2018-2025.ipynb)

Das Repository enthält das Codebuch, die vier Wörterbücher im JSON-Format, die kommentierten Programme, Analyseergebnisse und Validierungsdateien der Arbeit. Das [Colab-Notebook](agrarpolitik-bundestag-2018-2025.ipynb) führt durch die erneute Berechnung von der Ausgangsquelle bis zum Satzmaster, zur Excel-Auswertung und zu den Gütemaßen der Validierung.

Die ursprünglichen Reden werden direkt von [Zenodo, Version 2026-01-17](https://doi.org/10.5281/zenodo.18177196), bezogen. Die große aufbereitete Satzbasis `Saetze_2018-2025.csv.gz` steht beim [GitHub-Release `abgabe-v1.0`](https://github.com/lhaehner/agrarpolitik-bundestag-2018-2025/releases/tag/abgabe-v1.0) als gesonderter Download bereit. Sie ist nicht im automatisch erzeugten Quellcode-ZIP von GitHub enthalten. Für den vollständigen Notebook-Ablauf ist ihr Download nicht erforderlich: Sie wird dort neu erzeugt.

## Orientierung

| Gesuchter Inhalt | Ablage |
| --- | --- |
| Codebuch als Lesefassung | [Codebuch.pdf](codebuch/Codebuch.pdf) |
| Vier tatsächlich verwendete Wörterbücher | `dictionaries/` |
| Unveränderte Ausgangsreden | [Redenarchiv auf Zenodo](https://zenodo.org/records/18177196/files/CPP-BT_2026-01-17_DE_CSV_Reden_Gesamt.zip?download=1) |
| Vollständige aufbereitete Satzbasis | [Saetze_2018-2025.csv.gz herunterladen](https://github.com/lhaehner/agrarpolitik-bundestag-2018-2025/releases/download/abgabe-v1.0/Saetze_2018-2025.csv.gz) (ca. 145 MB) |
| A&E-Satzmaster | `ergebnisse/Satzmaster_Agrar_Ernaehrung.csv.gz` |
| Fertige Excel-Auswertung | [ergebnisse/Datengrundlage.xlsx](ergebnisse/Datengrundlage.xlsx) |
| Berechnete Gütemaße der Validierung | [ergebnisse/Guetemasse_Validierung.csv](ergebnisse/Guetemasse_Validierung.csv) |
| Validierung mit 1.000 Sätzen | [validierung/Validierung_AE_und_Themen_1000.xlsx](validierung/Validierung_AE_und_Themen_1000.xlsx) |
| A&E-Recall-Prüfung mit 3.000 Sätzen | [validierung/Validierung_AE_Recall_3000.xlsx](validierung/Validierung_AE_Recall_3000.xlsx) |
| Geführter Berechnungsablauf | [agrarpolitik-bundestag-2018-2025.ipynb](agrarpolitik-bundestag-2018-2025.ipynb) |
| Technische Umsetzung und Bedeutung der Datenfelder | [docs/Technische_Dokumentation.md](docs/Technische_Dokumentation.md) |
| Fundstellen und Quellen der Korpuskorrekturen | [docs/Korpuskorrekturen.md](docs/Korpuskorrekturen.md) |
| Bedingungen zur Nachnutzung | [LICENSE](LICENSE) |

Das Codebuch ergänzt **Anhang B: Aufbau und Abgrenzungen der Wörterbücher**. Die JSON-Dateien legen die Wortformen und Suchregeln fest, die der Programmcode anwendet. **Anhang C: Daten, Codebuch und Programmcode** der Masterarbeit enthält die Übersicht und den Zugang zu diesem Repository. Zum Lesen der Dokumentation, der Validierungsdateien und der fertigen Ergebnisse ist keine erneute Berechnung erforderlich.

Für einen schnellen Einstieg:

1. **Ergebnisse ansehen:** `ergebnisse/Datengrundlage.xlsx` öffnen. In `00_Wegweiser` die gesuchte Tabelle oder Abbildung der Arbeit nachschlagen.
2. **Regeln verstehen:** `codebuch/Codebuch.pdf` lesen. Die zugehörigen Suchregeln stehen in `dictionaries/`.
3. **Ergebnisse nachrechnen:** das oben verlinkte Colab-Notebook öffnen und die vier Schritte ausführen.

Die Excel-Blätter sind durchgehend von `00` bis `13` nummeriert. Auf die Ergebnisübersichten folgen die Berechnungsbasis, Begriffe und Suchregeln sowie Angaben zum Datenstand. Jahres- und Monatswerte der Ernährungssicherheit stehen gemeinsam mit den anderen vertieften Unterthemen in `05_Unterthemen`.

Das erste Blatt `00_Wegweiser` der Datengrundlage ordnet die Ergebnistabellen 7–10 und A1–A9 sowie die Abbildungen 1–2 der Arbeit den jeweiligen Blättern und Zellbereichen zu. Die Gütemaße aus Tabellen 5 und 6 sowie die Blockprüfung und der Vergleich der wirtschaftlichen Stichprobenanteile aus Abschnitten 3.5 und 5.4 stehen in `Guetemasse_Validierung.csv`. Die Wörterbuchübersichten aus Tabellen 1–4 werden durch Codebuch und JSON-Dateien erläutert.

## Berechnung in Google Colab

Das Notebook wird in [Google Colab](https://colab.research.google.com/) geöffnet. Es verwendet den dort festgelegten GitHub-Abgabestand und die genaue Zenodo-Quellversion. Programme, Wörterbücher und Daten werden automatisch geladen. Es sind keine Datei-Uploads erforderlich.

| Abschnitt | Was passiert? | Was wird weitergegeben? |
| --- | --- | --- |
| **Vorbereitung** | Programme, Wörterbücher und Hilfsdateien aus GitHub laden, die benötigte Bibliothek installieren und das Redenarchiv von Zenodo herunterladen | Arbeitsumgebung und unveränderte Ausgangsquelle |
| **1. Korpus aufbereiten** | Reden auswählen, festgelegte Ergänzungen und Korrekturen anwenden und Sätze erzeugen | Vollständige aufbereitete Satzbasis |
| **2. Wörterbücher anwenden** | A&E-Sätze auswählen, die drei Themenwörterbücher anwenden und das Ergebnis technisch vergleichen | A&E-Satzmaster mit Zuordnungen und Trefferbelegen |
| **3. Auswertung berechnen** | Tabellen aus Satzmaster und vollständiger Satzbasis sowie Gütemaße aus den vorhandenen Handcodierungen berechnen | Neue Excel-Auswertung und Gütemaße der Validierung |
| **4. Ergebnisse herunterladen** | Satzmaster, Excel-Auswertung und Gütemaße einzeln oder gemeinsam als ZIP speichern | Berechnungsergebnisse und Prüfberichte |

Die Ausführungszellen werden der Reihe nach gestartet. Sie rufen die genannten Python-Dateien auf und geben Zwischenergebnisse automatisch weiter. Bei jedem Schritt sind die verwendeten Programme und Eingabedateien mit ihrer Funktion erläutert und auf den GitHub-Abgabestand `abgabe-v1.0` verlinkt. Die kommentierten Programmdateien lassen sich über diese Links direkt lesen. Verlinkte Ergebnisdateien zeigen den bereitgestellten Abgabestand. Neu berechnete Ergebnisse entstehen in der Colab-Sitzung und stehen anschließend zum Download bereit.

Das Notebook benötigt eine Internetverbindung und eine CPU-Laufzeit. Es installiert `pysbd==0.3.4`. Fortschrittsmeldungen erscheinen unter den Ausführungszellen. Die Dauer hängt von der zugeteilten Colab-Umgebung ab. Ergebnisse müssen vor dem Ende der Sitzung heruntergeladen werden.

Das Ergebnis-ZIP enthält `Satzmaster_Agrar_Ernaehrung.csv.gz`, `Datengrundlage_neu_berechnet.xlsx`, `Guetemasse_Validierung.csv`, den zugehörigen Validierungsbericht und einen kurzen `Bericht_zur_Berechnung.txt` mit Anzahlen und Prüfergebnissen. Die bereits bereitgestellten Ergebnisse im Repository bleiben erhalten.

## Ordner und Programme

Alle Pfade beziehen sich auf das Projekt-Hauptverzeichnis.

| Ordner | Aufgabe |
| --- | --- |
| `codebuch/` | Zusammengeführtes Codebuch als PDF |
| `dictionaries/` | A&E-Filter und die drei Themenwörterbücher als JSON |
| `korpusaufbereitung/` | Kommentierter Aufbereitungscode und festgelegte Ergänzungs- und Korrekturdaten |
| `src/` | Wörterbuchanwendung sowie Hilfsfunktionen für Satzmaster und Notebook |
| `auswertung/` | Programme und Hinweise zur Tabellenberechnung |
| `ergebnisse/` | A&E-Satzmaster, Excel-Auswertung und Gütemaße der Validierung |
| `validierung/` | Die beiden ausgefüllten Excel-Prüfdateien, das Programm zur Berechnung der Gütemaße und eine Erläuterung |
| `reproduktion/` | Prüfskript und Vergleichsgrundlage für die technischen Satzmasterinhalte |
| `docs/` | Technische Dokumentation, Quellen der Korpuskorrekturen und Anleitung zur lokalen Ausführung |

`ergebnisse/Datengrundlage.xlsx` enthält die bereitgestellten Analyseergebnisse und dient zugleich als feste Vorlage für Tabellenaufbau, Formeln und ergänzende Suchregeln. Der Berechnungscode zählt die Werte aus den Satzdateien neu und schreibt sie in eine separate `Datengrundlage_neu_berechnet.xlsx`. Die bereitgestellte Datengrundlage wird dabei nicht überschrieben.

Das Blatt `09_Amtsrollen` dokumentiert die ergänzende Kontrollrechnung zum Fraktionsvergleich in Abschnitt 4.3 der Arbeit. Es zeigt die Themenanteile und den gemeinsamen Jahreswert zusätzlich ohne Beiträge mit dokumentierter Regierungs- oder anderer Amtsrolle und prüft die fünf durchgehend gleichgerichteten Fraktionsunterschiede. Die Hauptauswertung bleibt unverändert.

Die Berechnung ist auch außerhalb von Colab möglich. Die Befehle stehen in [docs/Ausfuehrung_lokal.md](docs/Ausfuehrung_lokal.md).

## Daten und Validierung

Die vollständige Satzbasis enthält **1.912.729 Plenarsätze**, der A&E-Satzmaster **25.247 Sätze**. Ein Satz kann mehreren Themenbereichen zugeordnet sein. `.csv.gz` bezeichnet eine komprimierte CSV-Tabelle. Nach dem Entpacken liegt UTF-8-Text mit Semikolon als Trennzeichen vor. Kennungen sind als Text zu behandeln.

Die Auswertung zählt die Plenarsätze je Jahr direkt aus `Saetze_2018-2025.csv.gz`. Die Jahresgesamtzahlen stehen zusammen mit den daraus berechneten Anteilen in `ergebnisse/Datengrundlage.xlsx`.

Die 1.000er-Datei dokumentiert die Prüfung ausgewählter A&E-Sätze einschließlich der drei Themenbereiche. Die 3.000er-Datei dokumentiert die Prüfung von Sätzen, die der A&E-Filter nicht ausgewählt hat. Ziehungsregeln, Ausgangsbestände und Codierungen stehen in den Arbeitsblättern der Dateien. `validierung/kennzahlen_berechnen.py` verknüpft diese vorhandenen Handcodierungen mit den Satzdateien und berechnet Präzision, Recall und die berichteten Wilson-Intervalle. Die menschlichen Bewertungen werden dabei nicht erneut vorgenommen. Weitere Hinweise stehen in [validierung/README.md](validierung/README.md).

Die technische Reproduktion verwendet festgelegte Ergänzungen und Korrekturen. Die damalige Beschaffung und XML-Extraktion ergänzender Beiträge wird nicht erneut ausgeführt. Technische Ergebnisgleichheit und die inhaltliche Prüfung durch menschliche Codierungen sind unterschiedliche Nachweise.

## Lizenz

Der Programmcode und das Colab-Notebook stehen unter der **MIT-Lizenz**. Die eigenen Inhalte in Codebuch, Wörterbüchern, Ergebnis- und Validierungsdateien sowie Dokumentation und die eigenen Bearbeitungen der Satzbasis stehen unter **CC BY 4.0**. Einzelheiten und Abgrenzungen stehen in [LICENSE](LICENSE).

Der Ausgangskorpus CPP-BT ist unter **CC0 1.0** veröffentlicht. Diese Freigabe bleibt für die übernommenen Quellinhalte bestehen. Gesondert gekennzeichnete Fremdinhalte und verwendete Softwarebibliotheken behalten ihre jeweiligen Bedingungen.

## Zitierhinweis

Hähner, L. (2026). *Agrarpolitik im Wandel? Eine quantitative Korpusanalyse des Deutschen Bundestages (2018–2025): Daten, Codebuch und Programmcode* (Abgabestand abgabe-v1.0) [Datensatz und Software]. GitHub. https://github.com/lhaehner/agrarpolitik-bundestag-2018-2025

Quelle: Seán Fobbe, *Corpus der Plenarprotokolle des Deutschen Bundestages*, Version 17.01.2026, [DOI 10.5281/zenodo.18177196](https://doi.org/10.5281/zenodo.18177196).
