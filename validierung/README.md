# Validierung und Gütemaße

Die Arbeitsmappen enthalten die ausgefüllten Prüfdateien der in Abschnitt 3.5 beschriebenen Validierung.

| Datei | Auswahl und Zweck |
| --- | --- |
| `Validierung_AE_und_Themen_1000.xlsx` | 1.000 ausgewählte A&E-Sätze: Prüfung des Politikfeldbezugs und der drei Themenbereiche |
| `Validierung_AE_Recall_3000.xlsx` | 3.000 vom A&E-Filter nicht ausgewählte Plenarsätze: Prüfung übersehener A&E-Bezüge |

`Prüfung` enthält Satztexte und Codierungen. `Hinweise` dokumentiert unter anderem Grundgesamtheit, Ziehung und Zufallsstartwert. `Schlüssel` ermöglicht die Zuordnung zu den Satzkennungen. Quelldateinamen und Dateiprüfsummen in den Hinweisen kennzeichnen den für die jeweilige Stichprobenziehung verwendeten Datenbestand.

Die beiden Stichproben wurden getrennt handcodiert. Der Filterstatus war dabei bekannt. Bei der Themenprüfung waren die maschinelle Themenzuordnung und die Trefferbegriffe nicht sichtbar.

Die inhaltliche Validierung durch menschliche Codierungen ist von den technischen Dateivergleichen unter `reproduktion/` zu unterscheiden.

## Nachrechnung der Gütemaße und der Blockprüfung

`kennzahlen_berechnen.py` liest die vorhandenen Handcodierungen und verbindet sie über die Fall-ID mit dem Blatt `Schlüssel`. Die Kombination aus `Rede-ID` und `Satzindex` verbindet jeden Fall mit dem Satzmaster beziehungsweise der vollständigen Satzbasis. Satztext, Jahr und Dokument-ID werden abgeglichen. Beim Textvergleich wird ausschließlich unterschiedlicher Leerraum vereinheitlicht. Doppelte oder fehlende Schlüssel, unvollständige Codierungen und abweichende Auswahlrahmen führen zum Abbruch. Bei der Nichttrefferprüfung muss die vollständige Durchsicht im Blatt `Hinweise` bestätigt sein.

Aufruf aus dem Hauptverzeichnis nach der Korpusaufbereitung und Wörterbuchanwendung:

```bash
python validierung/kennzahlen_berechnen.py \
  --satzmaster lauf/Satzmaster_Agrar_Ernaehrung.csv.gz \
  --satzbasis lauf/korpus/Saetze_2018-2025.csv.gz \
  --validierung-themen validierung/Validierung_AE_und_Themen_1000.xlsx \
  --validierung-recall validierung/Validierung_AE_Recall_3000.xlsx \
  --output lauf/Guetemasse_Validierung.csv \
  --report lauf/Pruefung_Validierung.json
```

Für eine Nachrechnung mit dem bereitgestellten Satzmaster kann dessen Pfad unter `ergebnisse/` eingesetzt werden. Die vollständige Satzbasis ist als Release-Datei erhältlich. Die beiden Ausgabedateien müssen neu sein. Das Programm überschreibt keine Eingabe und benötigt keine zusätzlichen Python-Pakete.

Die bereitgestellten Zahlen stehen in [`ergebnisse/Guetemasse_Validierung.csv`](../ergebnisse/Guetemasse_Validierung.csv). Die CSV verwendet Semikolons und Dezimalkommas. Ihre Anteilsspalten enthalten Prozentwerte, also beispielsweise `100` für 100 Prozent. Die Spalte `Zeitraum` kennzeichnet die Blockauswertung; Veränderungen stehen gesondert in `Wert_in_Prozentpunkten`. Der JSON-Bericht des jeweiligen Laufs enthält die ungerundeten Anteile zwischen 0 und 1, Veränderungen ausdrücklich in Prozentpunkten, die Bestandsgrößen, die Ergebnisse der Verknüpfungsprüfungen und die SHA-256-Prüfsummen der vier Eingaben und der Ergebnis-CSV.

## Berechnungen

Für jeden Themenbereich werden innerhalb der 1.000er-Stichprobe die vier Kombinationen von maschineller und manueller Zuordnung gezählt:

- TP: beide ordnen zu.
- FP: nur das Wörterbuch ordnet zu.
- FN: nur die Handcodierung ordnet zu.
- TN: beide ordnen nicht zu.

Die Präzision ist `TP / (TP + FP)`, die Trefferquote ist `TP / (TP + FN)`. Die 95-Prozent-Konfidenzintervalle werden jeweils nach Wilson aus dem zugehörigen Zähler und Nenner berechnet. Das ergibt die Kennzahlen aus Tabelle 5.

Für die ergänzende Blockprüfung in Abschnitt 3.5 werden dieselben 1.000 Prüfsätze anhand ihres Satzjahres in 2018–2021 und 2022–2025 aufgeteilt. Für jeden Themenbereich werden TP, FP, FN und TN sowie die Trefferquote mit Wilson-Intervall berechnet. Für den Vergleich in Abschnitt 5.4 wird zusätzlich der wirtschaftliche Anteil nach Handcodierung und Wörterbuchzuordnung in jedem Block ausgegeben: `(TP + FN) / Blockumfang` beziehungsweise `(TP + FP) / Blockumfang`. Die Veränderung ist jeweils der Anteil im zweiten minus dem im ersten Block, ausgedrückt in Prozentpunkten. Diese Anteile beziehen sich auf die Validierungsstichprobe, nicht auf das gesamte A&E-Korpus. Es werden weder Sätze neu gezogen noch Codierungen verändert.

Für Tabelle 6 wird der von Hand bestätigte A&E-Anteil getrennt in beiden Stichproben berechnet. Die Bestandsgrößen stammen aus den eingelesenen Daten: `M` bezeichnet die Zahl der Filtertreffer im Satzmaster, `N` die Zahl aller Sätze in der vollständigen Satzbasis und `N − M` die Nichttreffer. Die dokumentierten Bestandsgrößen in den Prüfdateien werden damit verglichen.

Für die in Abschnitt 3.5 berichtete Trefferquote des Politikfeldfilters wird der A&E-Anteil `q` aus der Nichttrefferstichprobe auf den gesamten Nichttrefferbestand hochgerechnet. Die geschätzte Zahl übersehener Sätze beträgt `(N − M) × q`. Zusammen mit der beobachteten Präzision `p` aus der Trefferstichprobe ergibt sich:

```text
geschätzte Trefferquote = (M × p) / (M × p + (N − M) × q)
```

Wie in der Arbeit wird die beobachtete Präzision bei der Intervallberechnung als fest angenommen. Die Wilson-Grenzen für `q` werden in diese Formel eingesetzt: Die obere Grenze für `q` ergibt die untere Grenze der Trefferquote und umgekehrt. Das Intervall berücksichtigt damit die Unsicherheit der Nichttrefferstichprobe, nicht gemeinsam die Unsicherheit beider Stichproben. Es wird keine Korrektur der berichteten Analysewerte vorgenommen.
