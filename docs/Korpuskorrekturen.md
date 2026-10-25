# Fundstellen und Begründungen der Korpuskorrekturen

Die Dateien in `korpusaufbereitung/konfiguration/` legen die Ergänzungen und
Korrekturen für den in `referenz.json` bezeichneten CPP-BT-Quellenstand vom
17.01.2026 fest. Die vorliegende Dokumentation bündelt die für diese Regeln
relevanten Begründungen und Fundstellen. Die früher genannten separaten
Prüfberichte werden zur Anwendung der Regeln nicht benötigt.

Die technischen Korrekturdateien wurden aus einer festgelegten Ausgangs- und
Zieldatei rekonstruiert. Sie bilden keinen vollständigen chronologischen
Arbeitsverlauf ab. Die nachstehenden Quellen begründen konkrete Eingriffe;
die Hashprüfungen sichern davon getrennt ihre unveränderte Anwendung.

## Welche Datei wofür zuständig ist

| Konfigurationsdatei | Umfang | Begründung und Fundstelle |
|---|---:|---|
| `ergaenzungen.json` | 271 Beiträge | 247 Beiträge aus zwei fehlenden Sitzungstagen und 24 separat geführte eingebettete Sprecherbeiträge. Jeder Eintrag enthält Protokoll-URL, XML-Fundstelle und Ursprungsbeitrag im Feld `beleg`. |
| `satzkorrekturen.json` | 25 Beiträge, 76 Operationen | Sieben rekonstruierte Hauptbeiträge und 18 Beiträge mit eingelesenen Abstimmungsnamenslisten. Die jeweiligen `beleg`-Felder erklären den Eingriff; `operations` enthält die genauen Vorher-/Nachher-Spannen. |
| `fraktionszuordnung.json` | 208 Schlüssel | Ergänzt ausschließlich leere Quellenwerte anhand von Personen-ID und beiden Namensfeldern. Die Anwendungsdaten nennen betroffene Beitragszahlen und erste/letzte Fundstelle im Ausgangskorpus. Sie sind keine Gültigkeitsintervalle einer Parteimitgliedschaft. |
| `metadatenkorrekturen.json` | 12 Beiträge | Sieben Kennzeichnungen der Textrekonstruktion und fünf gezielte Prüfungen von Namen, politischen Zuordnungen oder ihrem Prüfstatus; siehe unten. |
| `satzkennungen.json` | 1.781 Einträge | Erhält bestehende Satzkennungen nach Reparaturen. Satztext-Hashes binden jeden Eintrag an den richtigen Text; damit bleiben Verweise aus Satzmaster und Validierung gültig. |

Alle Pfade in den JSON-Feldern `dokumentation` und `einzelpruefung` beziehen sich
auf das Repository-Hauptverzeichnis. Zusätzliche Belegfelder werden vom
Aufbereitungsskript nicht als Korrekturanweisungen ausgewertet.

## Ergänzte Sitzungstage und Sprecherbeiträge

Die fehlenden Sitzungstage sind der **25.09.2025**,
[Plenarprotokoll 21/28](https://dserver.bundestag.de/btp/21/21028.pdf), und der
**17.12.2025**,
[Plenarprotokoll 21/49](https://dserver.bundestag.de/btp/21/21049.pdf).
Die Konfiguration enthält hierfür 115 beziehungsweise 132 Hauptbeiträge.
Fünf der insgesamt 24 getrennt geführten eingebetteten Beiträge stammen ebenfalls
aus diesen beiden Sitzungen. Sie dürfen nicht ein zweites Mal im Hauptbeitrag
gezählt werden.

Die anderen 19 getrennten Beiträge gehören zu den sieben reparierten
Quellblöcken `ID1911005100`, `ID1912800600`, `ID1913910900`, `ID1917005300`,
`ID1917304200`, `ID1920109100` und `ID2015400700`. Gesprochene Absätze werden der
jeweils sprechenden Person zugeordnet; Präsidiums- und Regietexte gehören nicht
zum Redetext des Hauptredners. Beispielsweise enthält
[Protokoll 19/110, Druckseiten 13593–13594](https://dserver.bundestag.de/btp/19/19110.pdf#page=71)
eine Zwischenfrage Katrin Göring-Eckardts innerhalb des Beitrags Julia Klöckners.
Diese Zwischenfrage steht als `ID1911005100__T03` separat in der Konfiguration.

`doc_id` bezeichnet den XML-Block. Zusätze wie `#T03` oder `#EINBETTUNG_01` sind
interne Abschnittskennungen der getrennten Beiträge, keine amtlichen PDF-Anker.
Das übernommene Metadatenfeld `protokoll_seite` kann die Anfangsseite einer
Sitzung enthalten; für die konkrete Passage sind Sprecher, Text und XML-Block
maßgeblich. Die verlinkten PDFs ermöglichen den inhaltlichen Gegencheck, ersetzen
aber keine vollständige erneute XML-Extraktion.

## Namenslisten und Satzsegmentierung

Bei 18 Quellbeiträgen waren insgesamt 19 Abstimmungsnamenslisten in den
Redetext geraten. Reine Listenbestandteile wurden entfernt; gesprochene
Ankündigungen in gemischten Absätzen blieben erhalten. So bezeichnet der in
Listen vorkommende Zusatz „Friedrich (Hof)“ einen Namen mit Ortszusatz und keinen
landwirtschaftlichen Hof. Es gibt dafür keine globale Löschregel für das Wort
„Hof“. Die begrenzten Eingriffe stehen mit Protokollverweisen und vollständigen
Textspannen in `satzkorrekturen.json`.

Eine weitere begrenzte Korrektur betrifft `ID1911005100`: Hinter der Bezeichnung
„Sonderrahmenplan Insektenschutz“ wurde ein schließendes Anführungszeichen ergänzt,
damit die Satzsegmentierung nicht einen langen Folgeabschnitt zusammenzieht.
Dieses Zeichen fehlt auch im amtlichen Protokoll. Die Ergänzung ist daher eine
**redaktionelle Korrektur**, keine Wiederherstellung eines ausschließlich beim
Import verlorenen Zeichens.

## Politische Zuordnungen: Reihenfolge und gezielte Belege

Zuerst ergänzt das Skript leere Quellenwerte mithilfe der festen Lookup-Tabelle.
Anschließend haben die beitragsbezogenen Einzelkorrekturen Vorrang. Deshalb
enthält die Lookup-Datei auch frühere Werte, die für einen konkret geprüften
Beitrag wieder korrigiert werden. Die betreffenden Einträge verweisen unmittelbar
auf diese Einzelkorrektur. Die Felder `*_original` sichern den Zustand **nach**
der Leerwert-Ergänzung und **vor** der Einzelkorrektur; sie sind nicht in allen
Fällen identisch mit den unveränderten Zenodo-Metadaten.

Eine politische Zuordnung bei einem Regierungs- oder Bundesratsbeitrag ist nicht
gleichbedeutend mit einer Mitgliedschaft in einer Bundestagsfraktion. Das Feld
`zugehoerigkeit_art` hält diesen Unterschied fest. Bei der automatischen
Kennzeichnung liegt eine Amtsrolle vor, sobald `redner_rolle_kurz` oder
`redner_rolle_lang` einen nicht leeren Wert enthält. Die Amtsrollenprüfung der
Auswertung verwendet dieselben beiden Rollenfelder; das Zusatzkennzeichen
selbst steuert diese Berechnung nicht. Die nachfolgenden Einzelkorrekturen
können die Zuordnungsart genauer kennzeichnen.

| Beitrag | Beleg und Begründung des gespeicherten Standes |
|---|---|
| **Lena Kreck, 26.01.2023**, `ID208205200` | [Protokoll 20/82, S. 9783 D–9784](https://dserver.bundestag.de/btp/20/20082.pdf) nennt Lena Kreck als Berliner Senatorin. Eine [amtliche Mitteilung vom 02.06.2022](https://www.berlin.de/sen/justv/presse/pressemitteilungen/2022/pressemitteilung.1213526.php) nennt ihre Zuordnung zur Linken. Der zusammengezogene Quellenname und die SPD-Ergänzung werden für diesen Beitrag berichtigt. |
| **Mehmet Daimagüler, 14.12.2023**, `ID2014407800` | [Protokoll 20/144, S. 18312 D–18313](https://dserver.bundestag.de/btp/20/20144.pdf) und [Berufungsmitteilung vom 09.03.2022](https://www.bmbfsfj.bund.de/bmbfsfj/aktuelles/pressemitteilungen/bundesregierung-beruft-erstmals-antiziganismus-beauftragten-193920) belegen Person und Amtsrolle, keine CDU/CSU-Zugehörigkeit. Die Quellen-ID `999990141` ist außerdem Judith Gerlach zugeordnet. Die unbelegte CDU/CSU-Ergänzung wird für Daimagülers Beitrag auf `ungeklärt` gesetzt; keine Ersatzpartei wird unterstellt. |
| **Felor Badenberg, 20.03.2024**, `ID2015913200` | [Protokoll 20/159, S. 20384 D](https://dserver.bundestag.de/btp/20/20159.pdf) nennt die Berliner Senatorin für den Bundesrat. Die [Bundesratsbiografie](https://www.bundesrat.de/SharedDocs/personen/DE/laender/be/badenberg-felor.html) datiert ihren CDU-Beitritt auf den 23.05.2024; die [amtliche Vereidigungsdokumentation 2023](https://www.berlin.de/rbmskzl/aktuelles/media/artikel.1318340.php) bezeichnet sie als parteilos für die CDU. Der spätere Parteieintritt belegt keine Mitgliedschaft am Beitragstag. Der gespeicherte Wert `ungeklärt` vermeidet die Gleichsetzung von Nominierung und Parteimitgliedschaft. |
| **Volker Wissing, 19.12.2024**, `ID2020700600` | Die [archivierte Bundestagsbiografie](https://www.bundestag.de/webarchiv/abgeordnete/biografien20/W/wissing_volker-861446) nennt den Austritt aus FDP und FDP-Bundestagsfraktion am 07.11.2024. Die frühere FDP-Ergänzung wird für diesen späteren Beitrag durch `fraktionslos` ersetzt. |
| **Karsten Wildberger, 06.05.2025**, `ID21201700` | Die [amtliche Biografie](https://bmds.bund.de/en/the-ministry/leadership/minister) nennt den Ministerbeginn am 06.05.2025 und den CDU-Beitritt im Mai 2025, aber keinen Eintrittstag. Der Zuordnungswert bleibt erhalten; der Prüfstatus kennzeichnet ausdrücklich, dass die tagesgenaue Mitgliedschaft offen ist. |

## Reichweite der Nachweise

Alle 208 Lookup-Schlüssel werden verwendet; sie enthalten 205 verschiedene
Quellen-IDs und sind deshalb nicht mit 208 verschiedenen Personen gleichzusetzen.
Im Ausgangskorpus werden 7.624 von 7.636 leeren Zuordnungen ergänzt; zwölf bleiben
leer. Diese Zahlen beziehen sich auf den Stand vor den Einzelkorrekturen und
Textreparaturen.

Für die 208 Lookup-Schlüssel stehen die tatsächlichen Anwendungen im
Quellenkorpus unter `anwendung_auf_ausgangskorpus`. Vorhandene nicht leere
Zuordnungen derselben ID-Namens-Kombination werden, soweit vorhanden, zusätzlich
unter `nicht_leere_vergleichswerte_in_der_quelle` mit Fundstellen genannt.
Für 124 Schlüssel enthält der Ausgangskorpus solche nicht leeren Vergleichswerte;
sie stimmen jeweils mit dem Lookup-Wert überein. Für die übrigen 84 Schlüssel
fehlt dieser interne Vergleich. Diese Angaben ermöglichen die Prüfung am
Ausgangsmaterial. Sie belegen keine
ununterbrochene historische Zugehörigkeit zwischen zwei Datumsgrenzen.

**Eine vollständige externe, datumsbezogene Einzelprüfung sämtlicher 208
Lookup-Schlüssel ist nicht dokumentiert.** Die gezielten Prüfungen oben dürfen
nicht als solche ausgegeben werden. Insbesondere bleibt Wildbergers genauer
Eintrittstag offen. Die vollständige technische Reproduktion der festgelegten
Satzbasis ist von dieser inhaltlichen Prüfgrenze zu unterscheiden.

Die aktuellen Belegangaben ergänzen ausschließlich Dokumentation. Sie verändern
keine Satztexte, Personenkennungen, politischen Zuordnungswerte, Satzkennungen
oder Referenz-Ergebniswerte. Die Prüfsummen der Konfigurationsdateien wurden an
die ergänzten Metadaten angepasst.
