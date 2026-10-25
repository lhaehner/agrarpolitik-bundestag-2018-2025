"""Ökonomie: geschlossene Tokenformen, Wortfamilien und Kontextausschlüsse.

Matcher.match() liefert akzeptierte Formen, Familien und Gruppen je Satz.
Lokale Ausschlusspositionen beziehen sich auf den normalisierten Text.
Die Positivliste enthält vollständige Tokenformen, keine offenen Wortstämme.
Lokale Ausschlüsse und satzweite Kontextregeln wirken unterschiedlich.
Die Unterscheidung ist in match() ausdrücklich beschrieben.

Eingabe: Satztext und Woerterbuch_Oekonomie.json. Ausgabe: oek_treffer als
0/1-Wert, Formen, Familien und Gruppen. satzmatcher.py ruft dieses Modul nur
für Sätze auf, die der A&E-Filter bereits ausgewählt hat.
"""
import collections
import json
from pathlib import Path
import re
TRANSLATION = str.maketrans({'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss'})
TOKEN_PATTERN = re.compile('[A-Za-z0-9_-]+')

def normalize(text):
    """Schreibt klein und ersetzt Umlaute/ß entsprechend der JSON-Positivliste.

    Anders als bei A&E werden Leerraum und Zeilentrennungen hier nicht verändert.
    """
    if not isinstance(text, str):
        raise ValueError('Satztext muss eine Zeichenfolge sein.')
    return text.lower().translate(TRANSLATION)

def _unique_json(pairs):
    """Verhindert, dass doppelte JSON-Schlüssel beim Einlesen unbemerkt überschreiben."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Doppelter JSON-Schlüssel: ' + key)
        result[key] = value
    return result

class Matcher:
    """Ordnet akzeptierte Tokenformen den festgelegten Familien und Gruppen zu."""

    def __init__(self, spec):
        """Prüft Positivlisten und Verweise und kompiliert die Ausschlussregeln."""
        self.spec = spec
        self.groups = {}
        self.families = {}
        self.form_families = collections.defaultdict(set)
        self.rules = []
        self.local_rules = []
        for group in spec['gruppen']:
            if group['id'] in self.groups:
                raise ValueError('Doppelte Gruppen-ID: ' + group['id'])
            self.groups[group['id']] = group
        for family in spec['familien']:
            fid = family['id']
            if fid in self.families or family['gruppe'] not in self.groups:
                raise ValueError('Ungültige Familien-/Gruppen-ID: ' + fid)
            self.families[fid] = family
            names = set()
            for subcategory in family['unterkategorien']:
                if subcategory['name'] in names:
                    raise ValueError('Doppelte Unterkategorie in ' + fid)
                names.add(subcategory['name'])
                words = subcategory['formen']
                if len(words) != len(set(words)):
                    raise ValueError('Doppelte Form innerhalb einer Unterkategorie: ' + fid)
                for word in words:
                    if not re.fullmatch('[a-z0-9_-]+', word):
                        raise ValueError('Nicht normalisierte Direktform: ' + word)
                    self.form_families[word].add(fid)
        if not self.form_families:
            raise ValueError('Leere Positivliste.')
        # nicht_erfasst erläutert die Abgrenzung der Positivliste. Es ist keine
        # zusätzliche Suchregel und darf der Positivliste nicht widersprechen.
        documented_exclusions = {word for family in spec['familien'] for exclusion in family['nicht_erfasst'] for word in exclusion['formen']}
        contradiction = documented_exclusions.intersection(self.form_families)
        if contradiction:
            raise ValueError('Widerspruch zwischen Positivliste und Dokumentation: ' + ', '.join(sorted(contradiction)))
        targets = set()
        for rule in spec['kontextregeln']:
            target = rule['grundform']
            if target not in self.form_families or target in targets:
                raise ValueError('Ungültige/doppelte Kontextregel für ' + target)
            targets.add(target)
            self.rules.append((target, re.compile(rule['suchmuster'])))
        local_ids = set()
        for rule in spec.get('lokale_ausschlussregeln', []):
            if rule['id'] in local_ids:
                raise ValueError('Doppelte lokale Regel-ID: ' + rule['id'])
            pattern = re.compile(rule['suchmuster'])
            if 'target' not in pattern.groupindex:
                raise ValueError('Lokale Regel benötigt Gruppe target: ' + rule['id'])
            local_ids.add(rule['id'])
            self.local_rules.append((rule['id'], pattern))

    @classmethod
    def from_path(cls, path):
        """Lädt ein Wörterbuch aus UTF-8-JSON und weist doppelte Schlüssel zurück."""
        with Path(path).open(encoding='utf-8-sig') as handle:
            return cls(json.load(handle, object_pairs_hook=_unique_json))

    def match(self, sentence):
        """Liefert Ökonomie als 0/1-Wert und die akzeptierten Formen samt Belegen.

        Lokale Regeln entfernen nur die genaue Tokenposition ihrer 'target'-
        Gruppe. Ein weiteres gültiges Vorkommen derselben Form bleibt erhalten.
        Satzweite Kontextregeln entfernen dagegen die festgelegte Grundform
        vollständig, sobald ihr Kontextmuster irgendwo im Satz vorkommt.
        """
        text = normalize(sentence)
        tokens = list(TOKEN_PATTERN.finditer(text))
        raw = {token.group() for token in tokens}.intersection(self.form_families)
        excluded_spans = set()
        local_exclusions = []
        for rule_id, pattern in self.local_rules:
            for occurrence in pattern.finditer(text):
                span = occurrence.span('target')
                excluded_spans.add(span)
                local_exclusions.append({'regel': rule_id, 'form': occurrence.group('target'), 'start_normalisiert': span[0], 'ende_normalisiert': span[1]})
        # Erst nach dem positionsgenauen Ausschluss zu einer Formenmenge
        # zusammenfassen: Wiederholungen zählen nicht mehrfach, können aber
        # trotz einer verworfenen Fundstelle einen gültigen Beleg liefern.
        locally_valid = {token.group() for token in tokens if token.span() not in excluded_spans}
        locally_valid.intersection_update(self.form_families)
        # Diese zweite Ausschlussebene ist ausdrücklich satzweit. 'aktive_regeln'
        # enthält die nullbasierten Positionen in der JSON-Liste kontextregeln.
        active = [i for i, (target, pattern) in enumerate(self.rules) if target in raw and pattern.search(text)]
        removed = {self.rules[i][0] for i in active}
        forms = locally_valid - removed
        removed.update(raw - locally_valid)
        families = set()
        for form in forms:
            families.update(self.form_families[form])
        groups = {self.families[fid]['gruppe'] for fid in families}
        return {'oek_treffer': int(bool(forms)), 'formen': sorted(forms), 'familien': sorted(families), 'gruppen': sorted(groups), 'formen_vor_kontextregeln': sorted(raw), 'entfernte_formen': sorted(removed), 'aktive_regeln': active, 'lokale_ausschluesse': local_exclusions}
