"""A&E-Fundstellen aus normalisiertem Text dem Originalsatz zuordnen.

Der Matcher sucht beispielsweise nach 'ae', während im Original 'ä' stehen
kann. Dieses Modul erhält die Verbindung zwischen beiden Textfassungen für
den Belegexport. Es entscheidet nicht über die fachliche Satzzuordnung.

satzmatcher.py übergibt einen Originalsatz an mapped_normalize() und erhält
die Normalform mit einer Zuordnung der Zeichenpositionen. enrich_hit() ergänzt
damit die akzeptierten A&E-Treffer um die zugehörigen Originaltextstellen.
"""
from difflib import SequenceMatcher
import re
import unicodedata
from ae_matcher import HYPHENS, UMLAUTS, normalize


def mapped_normalize(text: str):
    """Normalisiert wie ae_matcher.normalize() und erhält die Ursprungsspannen.

    Positionen sind Python-Zeichenindizes, jeweils mit exklusiver Endposition.
    Bei Unicode-Komposition verweist ein geänderter Abschnitt auf seinen ganzen
    ursprünglichen Bereich. enrich_hit() prüft später, ob die Rückführung für
    die konkrete Fundstelle dieselbe Normalform ergibt.
    """
    nfc = unicodedata.normalize('NFC', text)
    if nfc == text:
        chars = [(c, i, i + 1) for i, c in enumerate(text)]
    else:
        chars = []
        for kind, i1, i2, j1, j2 in SequenceMatcher(None, text, nfc, autojunk=False).get_opcodes():
            if kind == 'equal':
                chars.extend((c, i1 + k, i1 + k + 1) for k, c in enumerate(nfc[j1:j2]))
            else:
                chars.extend((c, i1, i2) for c in nfc[j1:j2])
    chars = [(c.translate(HYPHENS), a, b) for c, a, b in chars if c != '\u00ad']
    # Zeilentrennungen vor dem Zusammenziehen des Leerraums verbinden, damit
    # exakt dieselbe Reihenfolge wie in ae_matcher.normalize() eingehalten wird.
    stage = ''.join(c for c, a, b in chars)
    removals = list(re.finditer(r'(?<=\w)-[ \t]*[\r\n]+[ \t]*(?=\w)', stage))
    if removals:
        remove = set(i for m in removals for i in range(m.start(), m.end()))
        chars = [item for i, item in enumerate(chars) if i not in remove]
    stage = ''.join(c for c, a, b in chars)
    collapsed = []
    prev = 0
    for m in re.finditer(r'\s+', stage):
        collapsed.extend(chars[prev:m.start()])
        collapsed.append((' ', chars[m.start()][1], chars[m.end() - 1][2]))
        prev = m.end()
    collapsed.extend(chars[prev:])
    if collapsed and collapsed[0][0] == ' ': collapsed = collapsed[1:]
    if collapsed and collapsed[-1][0] == ' ': collapsed = collapsed[:-1]
    # Kleinschreibung und Umlautersetzung können Zeichen erweitern. Jedes neue
    # Zeichen verweist deshalb weiterhin auf die ganze ursprüngliche Spanne.
    lowered = [(out, a, b) for c, a, b in collapsed for out in c.lower().translate(UMLAUTS)]
    normalized = ''.join(c for c, a, b in lowered)
    if normalized != normalize(text):
        raise ValueError('Export source-map normalization differs from original matcher.')
    return normalized, [(a, b) for c, a, b in lowered]


def enrich_hit(text: str, normalized: str, offsets, hit: dict):
    """Ergänzt einen A&E-Treffer um geprüfte Originalpositionen und Originalform.

    Ein technischer Widerspruch bricht den Export ab: Eine scheinbar präzise,
    aber nicht zum Treffer passende Textstelle soll nicht ausgegeben werden.
    """
    a, b = hit['start'], hit['end']
    if not (0 <= a < b <= len(normalized)) or normalized[a:b] != hit['form']:
        raise ValueError(f'Invalid normalized hit coordinates: {hit}')
    oa, ob = offsets[a][0], offsets[b - 1][1]
    original_form = text[oa:ob]
    if normalize(original_form) != hit['form']:
        raise ValueError(f'Original substring does not reproduce normalized hit: {hit}, {original_form!r}')
    return {**hit, 'original_start': oa, 'original_end': ob, 'original_form': original_form}
