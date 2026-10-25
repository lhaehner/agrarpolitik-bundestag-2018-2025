"""Ökologie: geschlossene Formen, Kategorien und lokale Ausschlüsse.

EcologyMatcher.match() prüft einen bereits segmentierten Satz. Fundstellen
beziehen sich auf den normalisierten Text (Endposition exklusiv). Formen,
Suchmuster und Ausschlüsse stammen aus dem JSON. Der Matcher erweitert die
Formenlisten nicht durch Stemming oder Lemmatisierung. Bereits eine akzeptierte
Fundstelle setzt den Themenbereich auf 1. Weitere Treffer bleiben als Belege.

Eingabe: Satztext und Woerterbuch_Oekologie.json. Ausgabe: oekologie als
0/1-Wert, Kategorien und Fundstellen. satzmatcher.py ruft dieses Modul nur
für Sätze auf, die der A&E-Filter bereits ausgewählt hat.
"""
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

def normalize(text, hyphenated_tokens=()):
    """Vereinheitlicht Schreibweisen und repariert Trennungen am Zeilenende.

    Wörterbuchformen mit Bindestrich und ergänzende Bindestriche vor
    'und', 'oder' oder 'sowie' werden bei der Zeilenverbindung berücksichtigt.
    Umlaute bleiben hier erhalten. Die anderen Fachmatcher normalisieren anders.
    """
    text = unicodedata.normalize('NFKC', str(text)).replace('\xad', '')
    text = text.translate(str.maketrans({'‐': '-', '‑': '-', '﹣': '-', '－': '-'}))
    text = re.sub('(?<=\\w)[–—](?=\\w)', '-', text)
    text = re.sub('(?<=\\w)[–—](?=(?:,\\s*[\\w-]+[-–—]){0,8}(?:,\\s*)?\\s+(?:und|oder|sowie)\\b)', '-', text, flags=re.IGNORECASE)
    hyphenated_tokens = set(hyphenated_tokens)
    linebreak = re.compile('(?P<left>[\\w-]+)-[ \\t]*\\r?\\n\\s*(?P<right>[\\w-]+)')

    def join_linebreak(match):
        """Entscheidet anhand der Formenliste, ob der Bindestrich erhalten bleibt."""
        left, right = (match.group('left'), match.group('right'))
        compound = left + '-' + right
        if (left + '-').casefold() in hyphenated_tokens and right.casefold() in ('und', 'oder', 'sowie'):
            return left + '- ' + right
        return compound if compound.casefold() in hyphenated_tokens else left + right
    while linebreak.search(text):
        text = linebreak.sub(join_linebreak, text)
    return re.sub('\\s+', ' ', text).casefold().strip()

class EcologyMatcher:
    """Kompiliert die geschlossenen Ökologieformen und ihre lokalen Ausschlüsse."""

    def __init__(self, dictionary):
        """Prüft Kennungen/Ausschlussziele und indexiert das erste Wort jeder Form."""
        if isinstance(dictionary, (str, Path)):
            dictionary = json.loads(Path(dictionary).read_text(encoding='utf-8'))
        if dictionary.get('schema_version') != '3.0-closed-ecology':
            raise ValueError('Nicht unterstütztes Wörterbuchschema.')
        self.dictionary = dictionary
        self.entries = dictionary['entries']
        self.by_id = {e['id']: e for e in self.entries}
        self.by_label = {e['label']: e for e in self.entries}
        if len(self.by_id) != len(self.entries) or len(self.by_label) != len(self.entries):
            raise ValueError('Doppelte Eintragskennung oder Bezeichnung.')
        self.patterns = {e['id']: re.compile(e['regex']) for e in self.entries}
        self.context = {e['id']: re.compile(e['following_context_regex']) for e in self.entries if e.get('following_context_regex')}
        # Das erste Wort jeder gelisteten Form begrenzt die Suchkandidaten.
        # Erst das vollständige Regex-Muster entscheidet über eine Fundstelle.
        self.index = defaultdict(set)
        self.hyphenated_tokens = set()
        for e in self.entries:
            for form in e['forms']:
                self.index[form.split()[0]].add(e['id'])
                self.hyphenated_tokens.update((token for token in form.split() if '-' in token))
        self.blockers = {b['id']: b for b in dictionary['exclusions']}
        if len(self.blockers) != len(dictionary['exclusions']):
            raise ValueError('Doppelte Ausschlusskennung.')
        self.blocker_patterns = {k: re.compile(b['regex']) for k, b in self.blockers.items()}
        for blocker_id, blocker in self.blockers.items():
            if 'capture_group' not in blocker:
                continue
            group = blocker['capture_group']
            pattern = self.blocker_patterns[blocker_id]
            valid = isinstance(group, str) and group in pattern.groupindex or (type(group) is int and 1 <= group <= pattern.groups)
            if not valid:
                raise ValueError('Ungültige Zielgruppe des Ausschlusses: ' + blocker_id)
        self.entry_blockers = defaultdict(list)
        for b in dictionary['exclusions']:
            for entry_id in b['entry_ids']:
                if entry_id not in self.by_id:
                    raise ValueError('Unbekanntes Ziel eines Ausschlusses: ' + entry_id)
                self.entry_blockers[entry_id].append(b['id'])

    def match(self, sentence):
        """Liefert binäre Zuordnung, Kategorien sowie akzeptierte/verworfene Belege.

        Eine Ausschlussregel betrifft nur ihre zugeordneten Einträge und die
        überlappende Fundstelle. Andere Vorkommen desselben Eintrags bleiben
        zulässig. 'capture_group' kann den Ausschluss auf einen Teil des größeren
        Ausschlussausdrucks beschränken.
        """
        text = normalize(sentence, self.hyphenated_tokens)
        candidates = set()
        for token in re.findall('\\w+(?:-\\w+)*-?', text):
            candidates.update(self.index.get(token, ()))
        hits, rejected = ([], [])
        block_cache = {}
        for entry_id in sorted(candidates):
            e = self.by_id[entry_id]
            for m in self.patterns[entry_id].finditer(text):
                reasons = []
                context = self.context.get(entry_id)
                # Verkürzte Formen in Aufzählungen brauchen den ausdrücklich
                # hinterlegten Anschluss unmittelbar nach ihrer Fundstelle.
                if context and (not context.match(text, m.end())):
                    reasons.append('coordination_not_selected')
                for blocker_id in self.entry_blockers.get(entry_id, ()):
                    # Jeden lokalen Ausschluss einmal pro Satz suchen. Die Zielspanne
                    # anschließend für alle betroffenen Einträge verwenden.
                    if blocker_id not in block_cache:
                        group = self.blockers[blocker_id].get('capture_group', 0)
                        block_cache[blocker_id] = [x.span(group) for x in self.blocker_patterns[blocker_id].finditer(text) if x.start(group) >= 0]
                    if any((a < m.end() and m.start() < b for a, b in block_cache[blocker_id])):
                        reasons.append(blocker_id)
                item = dict(entry_id=entry_id, label=e['label'], category=e['category'], group=e['group'], form=m.group(), start=m.start(), end=m.end())
                if reasons:
                    item['exclusions'] = reasons
                    rejected.append(item)
                else:
                    hits.append(item)
        hits.sort(key=lambda h: (h['start'], h['end'], h['entry_id']))
        rejected.sort(key=lambda h: (h['start'], h['end'], h['entry_id']))
        return dict(oekologie=int(bool(hits)), categories=sorted({h['category'] for h in hits}), entry_ids=sorted({h['entry_id'] for h in hits}), labels=sorted({h['label'] for h in hits}), hits=hits, rejected=rejected, normalized_text=text)
