"""A&E-Politikfeldfilter für das mitgelieferte Wörterbuch.

Matcher.classify() prüft einen bereits segmentierten Satz. Ein akzeptierter
Treffer genügt. Mehrere Treffer erhöhen das Satzgewicht nicht. Positionen in
diesem Modul beziehen sich auf den normalisierten Text (Endposition exklusiv).

Die Funktion jeder Regel steht im JSON-Feld role:
- direct: Direktregel ohne erforderlichen positiven Kontextpartner.
- context: Kontextregel, die bei erfülltem Kontext eine Zuordnung begründet.
- exclusion: lokaler Ausschluss für bestimmte Fundstellen. Andere gültige
  Treffer desselben Satzes bleiben wirksam.

Beim Laden werden die Regelfunktionen und ihre benötigten Angaben geprüft.
Alle enthaltenen Regeln werden entsprechend ihrer Funktion ausgeführt.

Eingabe: Satztext und Woerterbuch_Agrar_Ernaehrung.json. Ausgabe: flag als
0/1-Wert und Fundstellen mit Regelkennungen. satzmatcher.py verwendet flag für
die Auswahl des Analysekorpus und übernimmt die Fundstellen als Trefferbelege.
"""
from __future__ import annotations
import json, re, unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
try:
    from re import _parser as rp
except ImportError:
    import sre_parse as rp
# Technische Kennung des mitgelieferten JSON-Schemas, keine Programmhistorie.
VERSION = '5.0-role-based'
POSITIVE = {'direct', 'context'}
HYPHENS = str.maketrans({'‐': '-', '‑': '-', '﹣': '-', '－': '-'})
UMLAUTS = str.maketrans({'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss'})

def normalize(text):
    """Vereinheitlicht Unicode, Trennstriche, Leerraum und Umlautschreibweisen.

    Dies ist eine technische Schreibweisenanpassung, keine Lemmatisierung.
    Zeilentrennungen werden verbunden. Dadurch können sich Positionen gegenüber
    dem Originalsatz ändern. Die Rückführung übernimmt source_spans.py.
    """
    s = unicodedata.normalize('NFC', text).translate(HYPHENS).replace('\xad', '')
    s = re.sub('(?<=\\w)-[ \\t]*[\\r\\n]+[ \\t]*(?=\\w)', '', s)
    return re.sub('\\s+', ' ', s).strip().lower().translate(UMLAUTS)

def overlapping(rx, text, left=0, right=None):
    """Findet auch überlappende Vorkommen im angegebenen Zeichenbereich."""
    right = len(text) if right is None else right
    while left <= right:
        m = rx.search(text, left, right)
        if m is None:
            return
        if m.end() == m.start():
            raise ValueError(f'Leere Fundstelle bei Regex {rx.pattern!r}')
        yield m
        # Ein Fortschritt ab dem Trefferanfang erhält überlappende Kandidaten.
        left = m.start() + 1

def prefixes(seq, acc=''):
    """Leitet kurze Anfangszeichen aus einem geparsten Regex für den Index ab.

    Verzweigungen liefern mehrere Präfixe. Ein nicht eindeutig indexierbares
    Muster wird später vollständig geprüft, statt aufgrund des Index zu fehlen.
    """
    for i, (op, arg) in enumerate(seq):
        if len(acc) >= 3:
            return {acc}
        if op == rp.LITERAL:
            acc += chr(arg)
        elif op in (rp.AT, rp.ASSERT, rp.ASSERT_NOT):
            continue
        elif op == rp.SUBPATTERN:
            if arg[1] or arg[2]:
                return {''}
            return prefixes(list(arg[-1]) + list(seq[i + 1:]), acc)
        elif op == rp.BRANCH:
            return set().union(*(prefixes(list(b) + list(seq[i + 1:]), acc) for b in arg[1]))
        elif op in (rp.MAX_REPEAT, rp.MIN_REPEAT):
            lo, hi, sub = arg
            if lo:
                if lo != hi:
                    return prefixes(list(sub) * min(lo, 3), acc)
                return prefixes(list(sub) * min(lo, 3) + list(seq[i + 1:]), acc)
            if acc:
                return {acc}
            return prefixes(list(sub) + list(seq[i + 1:]), acc) | prefixes(list(seq[i + 1:]), acc)
        else:
            return {acc}
    return {acc}

def starts_at_boundary(seq):
    """Prüft, ob die untersuchten Regex-Zweige mit einer Wortgrenze beginnen."""
    for i, (op, arg) in enumerate(seq):
        if op == rp.AT:
            if arg == rp.AT_BOUNDARY:
                return True
            continue
        if op in (rp.ASSERT, rp.ASSERT_NOT):
            continue
        if op == rp.SUBPATTERN:
            return starts_at_boundary(list(arg[-1]) + list(seq[i + 1:]))
        if op == rp.BRANCH:
            return all((starts_at_boundary(list(b) + list(seq[i + 1:])) for b in arg[1]))
        if op in (rp.MAX_REPEAT, rp.MIN_REPEAT):
            lo, hi, sub = arg
            return starts_at_boundary(list(sub) + list(seq[i + 1:])) and (lo > 0 or starts_at_boundary(list(seq[i + 1:])))
        return False
    return False

@dataclass
class Rule:
    """Verbindet eine JSON-Regel mit ihren kompilierten Such- und Kontextmustern."""
    spec: dict
    role: str
    rx: object
    any_rx: list
    none_rx: list

    @property
    def key(self):
        """Stabile Kennung für Trefferbelege und Verweise zwischen Regeln."""
        return self.spec['key']

class Matcher:
    """Prüft die Zugehörigkeit zum Politikfeld Agrar und Ernährung.

    Nur die im Wörterbuch festgelegten lokalen Ausschlüsse und Kontextbedingungen
    können eine positive Fundstelle verwerfen. Andere Fundstellen bleiben prüfbar.
    Positive Regeln verdrängen einander nicht.
    """

    def __init__(self, path_or_dict):
        """Lädt und prüft das Regelschema und bereitet den Suchindex einmalig vor."""
        self.path = Path(path_or_dict) if not isinstance(path_or_dict, dict) else None
        self.dictionary = json.loads(self.path.read_text(encoding='utf-8-sig')) if self.path else path_or_dict
        d = self.dictionary
        schema = d.get('schema_version')
        if schema != VERSION:
            raise ValueError(f'schema_version muss {VERSION!r} sein, erhalten: {schema!r}')
        if not isinstance(d.get('patterns'), list) or not d['patterns']:
            raise ValueError('patterns muss eine nichtleere Liste sein')
        # Suchmuster werden einmal vorbereitet und für alle Sätze wiederverwendet.
        self.rules = []
        self.buckets = defaultdict(set)
        self.fallback = set()
        seen = set()
        fields = {
            'key', 'regex', 'role', 'priority',
            'context_any', 'context_none', 'context_window',
            'context_distinct', 'context_boundary', 'evidence_family',
            'block_scope', 'blocks_roles', 'exception_rule_keys',
            'masks_positive_context', 'label', 'notes', 'tags',
        }
        for i, p in enumerate(d['patterns']):
            if not isinstance(p, dict):
                raise ValueError(f'patterns[{i}] ist kein Objekt')
            key = p.get('key')
            unknown = set(p) - fields
            if unknown:
                raise ValueError(f'{key}: unbekannte Regelfelder {sorted(unknown)}')
            if not isinstance(key, str) or not key or key in seen:
                raise ValueError(f'Ungültiger/doppelter Regelkey: {key!r}')
            seen.add(key)
            if 'priority' in p and type(p['priority']) is not int:
                raise ValueError(f'{key}: priority muss ganzzahlig sein')
            if 'evidence_family' in p and (not isinstance(p['evidence_family'], str) or not p['evidence_family']):
                raise ValueError(f'{key}: evidence_family muss eine nichtleere Zeichenkette sein')
            role = p.get('role')
            if not isinstance(role, str) or role not in POSITIVE | {'exclusion'}:
                raise ValueError(f'{key}: unbekannte Regelfunktion role={role!r}')
            # Kontextregeln benötigen einen positiven Kontextpartner.
            # Direktregeln dürfen trotzdem negative Kontextbedingungen haben.
            has_context = bool(p.get('context_any'))
            if role in POSITIVE and (role == 'context') != has_context:
                raise ValueError(f'{key}: role und positive Kontextbedingungen widersprechen sich')
            if (role == 'exclusion') != key.startswith('exclude:'):
                raise ValueError(f'{key}: lokale Ausschlüsse benötigen das Kennungspräfix exclude:')
            if not isinstance(p.get('regex'), str) or not p['regex']:
                raise ValueError(f'{key}: regex fehlt')
            try:
                rx = re.compile(p['regex'])
            except re.error as e:
                raise ValueError(f'{key}: {e}') from e
            if rx.search('') is not None:
                raise ValueError(f'{key}: leere Fundstellen sind nicht zulässig')
            w = p.get('context_window')
            if w is not None and (type(w) is not int or w < 0):
                raise ValueError(f'{key}: context_window muss nichtnegative ganze Zeichenzahl sein')
            if p.get('context_boundary') not in (None, 'clause'):
                raise ValueError(f'{key}: unbekannte context_boundary')
            for f in ['context_distinct', 'masks_positive_context']:
                if f in p and type(p[f]) is not bool:
                    raise ValueError(f'{key}: {f} muss Boolean sein')

            def compile_context(f):
                """Prüft eine Kontextliste und kompiliert ihre Regex-Muster."""
                v = p.get(f, [])
                if not isinstance(v, list) or not all((isinstance(x, str) and x for x in v)):
                    raise ValueError(f'{key}: {f} muss Regexliste sein')
                compiled = [re.compile(x) for x in v]
                if any((rx.search('') is not None for rx in compiled)):
                    raise ValueError(f'{key}: leere Fundstelle in {f} nicht zulässig')
                return compiled
            crs = [compile_context(f) for f in ['context_any', 'context_none']]
            if role == 'exclusion' and p.get('block_scope') != 'overlapping_match':
                raise ValueError(f'{key}: lokaler Ausschluss erfordert block_scope=overlapping_match')
            if role != 'exclusion' and any((f in p for f in ['block_scope', 'blocks_roles', 'exception_rule_keys', 'masks_positive_context'])):
                raise ValueError(f'{key}: Ausschlussfelder sind nur bei role=exclusion zulässig')
            if 'blocks_roles' in p and (not isinstance(p['blocks_roles'], list) or not p['blocks_roles'] or any((x not in POSITIVE for x in p['blocks_roles']))):
                raise ValueError(f'{key}: blocks_roles muss positive Rollen nennen')
            exceptions = p.get('exception_rule_keys', [])
            if not isinstance(exceptions, list) or not all((isinstance(x, str) for x in exceptions)):
                raise ValueError(f'{key}: exception_rule_keys muss eine Liste von Regelkennungen sein')
            ri = len(self.rules)
            r = Rule(p, role, rx, *crs)
            self.rules.append(r)
            # Der Index darf nur die Suche beschleunigen. Alle nicht sicher
            # indexierbaren Regeln bleiben im vollständigen Fallback enthalten.
            try:
                ast = list(rp.parse(p['regex']))
                pr = prefixes(ast)
                safe = starts_at_boundary(ast) and (not rx.flags & (re.IGNORECASE | re.LOCALE | re.ASCII))
                if safe and all((len(x) == 3 and re.fullmatch('\\w{3}', x) for x in pr)):
                    for pref in pr:
                        self.buckets[pref].add(ri)
                else:
                    self.fallback.add(ri)
            except Exception:
                self.fallback.add(ri)
        activekeys = {r.key for r in self.rules if r.role in POSITIVE}
        for r in self.rules:
            unknown = set(r.spec.get('exception_rule_keys', [])) - activekeys
            if unknown:
                raise ValueError(f'{r.key}: unbekannte positive Regeln in exception_rule_keys: {sorted(unknown)}')
        if not activekeys:
            raise ValueError('Keine positive Regel')

    # Der Präfixindex beschleunigt die Suche. Unsichere Muster werden voll geprüft.
    def relevant(self, text):
        """Liefert mögliche Regelindizes einschließlich aller Fallback-Regeln."""
        chosen = set(self.fallback)
        for s in set(re.findall('\\b\\w{1,3}', text)):
            chosen.update(self.buckets.get(s, ()))
        return sorted(chosen)

    @staticmethod
    def hit(r, m):
        """Erzeugt einen Trefferbeleg mit Positionen im normalisierten Satz.

        priority und family werden als technische Angaben mitgeführt. Sie
        gewichten keine Sätze und verdrängen keine anderen positiven Treffer.
        """
        return {'key': r.key, 'role': r.role, 'start': m.start(), 'end': m.end(), 'form': m.group(), 'family': r.spec.get('evidence_family') or r.key, 'priority': r.spec.get('priority', 0)}

    # Fenstergrenzen sind Zeichenabstände zwischen Fundstellen, keine Wortzahlen.
    def context(self, r, text, a, b, masks):
        """Prüft Kontextbedingungen für genau eine Fundstelle [a, b).

        Ohne Begrenzung ist der ganze Satz maßgeblich. Ein Fenster misst die
        Zeichenlücke zwischen Fundstellen. 'clause' begrenzt zusätzlich an
        den hier aufgeführten Satzzeichen. 'any' verlangt mindestens einen
        positiven Kontextpartner. 'none' darf keinen Treffer liefern.
        Masken und 'context_distinct' betreffen die positiven Kontextbelege.
        """
        lo, hi = (0, len(text))
        w = r.spec.get('context_window')
        if r.spec.get('context_boundary') == 'clause':
            lo = max((text.rfind(c, 0, a) for c in '.;:!?')) + 1
            hi = min([p for c in '.;:!?' if (p := text.find(c, b)) >= 0] or [len(text)])

        def near(m):
            """Prüft den Abstand zweier Spannen. Überlappungen haben Abstand null."""
            return w is None or max(m.start() - b, a - m.end(), 0) <= w
        negatives = [m.group() for rx in r.none_rx for m in overlapping(rx, text, lo, hi) if near(m)]
        if negatives:
            return (False, 'negative_context', negatives)
        evidence = []

        def valid(rx):
            """Sucht einen unmaskierten, gegebenenfalls getrennten Kontextbeleg."""
            for m in overlapping(rx, text, lo, hi):
                if not near(m):
                    continue
                if r.spec.get('context_distinct', False) and m.start() < b and (a < m.end()):
                    continue
                if any((x['start'] < m.end() and m.start() < x['end'] for x in masks)):
                    continue
                evidence.append(m.group())
                return True
            return False
        if r.any_rx and (not any((valid(rx) for rx in r.any_rx))):
            return (False, 'missing_context', [])
        return (True, 'accepted', evidence)

    # Lokale Ausschlüsse wirken auf Fundstellen. Positive Regeln konkurrieren nicht.
    def classify(self, text, *, normalized=False, explain=False, full_scan=False):
        """Liefert 0/1-Zuordnung und alle akzeptierten Fundstellen eines Satzes.

        'normalized=True' setzt die Normalisierung dieses Moduls voraus.
        'explain' ergänzt auch verworfene Kandidaten und Ablehnungsgründe.
        'full_scan' prüft dieselben Regeln ohne den beschleunigenden Präfixindex.
        Kennungspräfixe wie stem:, phrase: und shadow: sind Belegkennungen.
        Über die Zuordnungswirkung entscheidet die Regelfunktion role.
        """
        s = text if normalized else normalize(text)
        selected = range(len(self.rules)) if full_scan else self.relevant(s)
        raw = []
        trace = []
        for i in selected:
            r = self.rules[i]
            for m in overlapping(r.rx, s):
                raw.append((r, m))
        # Zuerst lokale Ausschlüsse ermitteln, damit ihre Reihenfolge im JSON die
        # anschließende Beurteilung positiver Fundstellen nicht beeinflusst.
        exclusions = []
        for r, m in raw:
            if r.role != 'exclusion':
                continue
            ok, reason, ctx = self.context(r, s, m.start(), m.end(), [])
            if ok:
                exclusions.append((r, self.hit(r, m)))
            if explain:
                trace.append(dict(self.hit(r, m), status='active_exclusion' if ok else reason, context=ctx))
        accepted = []
        for r, m in raw:
            if r.role not in POSITIVE:
                continue
            h = self.hit(r, m)
            veto = []
            masks = []
            for br, bh in exclusions:
                if r.key in br.spec.get('exception_rule_keys', []):
                    continue
                if br.spec.get('masks_positive_context', False):
                    masks.append(bh)
                if r.role not in br.spec.get('blocks_roles', ['direct', 'context']):
                    continue
                # Der Ausschluss gilt für die konkrete Textstelle. Ein anderer
                # positiver Treffer desselben Satzes bleibt davon unberührt.
                overlap = bh['start'] < h['end'] and h['start'] < bh['end']
                if overlap:
                    veto.append(br.key)
            if veto:
                if explain:
                    trace.append(dict(h, status='blocked', exclusion_keys=veto))
                continue
            ok, reason, ctx = self.context(r, s, m.start(), m.end(), masks)
            if ok:
                accepted.append(dict(h, context=ctx))
            if explain:
                trace.append(dict(h, status=reason, context=ctx))
        accepted.sort(key=lambda h: (h['start'], h['end'], h['key']))
        result = {'flag': int(bool(accepted)), 'raw_positive': any((r.role in POSITIVE for r, m in raw)), 'keys': sorted({h['key'] for h in accepted}), 'families': sorted({h['family'] for h in accepted}), 'forms': sorted({h['form'] for h in accepted}), 'hits': accepted}
        if explain:
            result.update(normalized_text=s, trace=trace)
        return result
