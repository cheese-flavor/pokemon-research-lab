"""Scoped Korean localization rules verified on official Korean Pokémon pages.

These are terminology rules, not replacement Pokédex descriptions.
Only apply a rule when the English original contains its term and scope matches.
"""
import re

RULES_VERSION = 'official-ko-terms-2026-10-22-v2'
RULES = [
    {'english': 'Winged King', 'korean': '날개의왕', 'kind': 'historical_alias', 'species': [1007],
     'pattern': r'날개\s*달린\s*왕|날개\s*의\s*왕',
     'source_url': 'https://www.pokemonkorea.co.kr/pokedex/view/1274'},
    {'english': 'Iron Serpent', 'korean': '무쇠이무기', 'kind': 'historical_alias', 'species': [1008],
     'pattern': r'무쇠\s*이무기|철의?\s*뱀',
     'source_url': 'https://www.pokemonkorea.co.kr/pokedex/view/1275'},
    {'english': 'fore-wyrm', 'korean': '외미르', 'kind': 'component_name', 'species': [1011],
     'pattern': r'앞쪽\s*벌레|바깥쪽\s*벌레|외미르',
     'source_url': 'https://pokemonkorea.co.kr/pokedex/view/1278'},
    {'english': 'core-wyrm', 'korean': '내미르', 'kind': 'component_name', 'species': [1011],
     'pattern': r'속의\s*벌레|안쪽\s*벌레|내미르',
     'source_url': 'https://pokemonkorea.co.kr/pokedex/view/1278'},
    {'english': 'Showdown Mode', 'korean': '결전 모드', 'kind': 'mode', 'species': [920],
     'pattern': r'(?:승부|쇼다운|대결|배틀|전투|결투|결전)\s*모드',
     'source_url': 'https://pokemonkorea.co.kr/pokedex/view/1172'},
    {'english': 'flame sac', 'korean': '불꽃 주머니', 'kind': 'anatomical_term', 'species': [909, 910],
     'pattern': r'불꽃\s*주머니',
     'source_url': 'https://pokemonkorea.co.kr/pokedex/view/1160'},
    {'english': 'Hisui', 'korean': '히스이지방', 'kind': 'region', 'species': None,
     'pattern': r'히스이(?!지방)', 'english_pattern': r'\bHisui\b',
     'source_url': 'https://pokemonkorea.co.kr/game/view/11503'},
    {'english': 'Paldea', 'korean': '팔데아지방', 'kind': 'region', 'species': None,
     'pattern': r'팔데아(?!지방)', 'english_pattern': r'\bPaldea(?:n)?\b',
     'source_url': 'https://pokemonkorea.co.kr/sv/menu189?mode=view&number=2624'},
    {'english': 'Terastal', 'korean': '테라스탈', 'kind': 'phenomenon', 'species': [1024],
     'pattern': r'테라스탈',
     'source_url': 'https://pokemonkorea.co.kr/sv/menu189?mode=view&number=2624'},
]


def eligible(source, rule):
    raw_id = source['item_id'].split(':')[-1]
    if not raw_id.isdecimal():
        return False
    species_id = int(raw_id)
    english_pattern = rule.get('english_pattern', re.escape(rule['english']))
    return (rule['species'] is None or species_id in rule['species']) and bool(re.search(english_pattern, source['content'], re.IGNORECASE))


def apply_terms(source, text):
    changes = []
    for rule in RULES:
        if not eligible(source, rule):
            continue
        updated = re.sub(rule['pattern'], rule['korean'], text)
        if rule['kind'] == 'region':
            # Both region aliases end in a vowel; '지방' ends in a consonant.
            particles = {'로': '으로', '를': '을', '는': '은', '가': '이'}
            updated = re.sub(re.escape(rule['korean']) + r'(로|를|는|가)(?=\s|[.,!?]|$)',
                             lambda match: rule['korean'] + particles[match.group(1)], updated)
        if updated != text:
            changes.append({'english': rule['english'], 'korean': rule['korean'], 'kind': rule['kind'],
                            'source_url': rule['source_url'], 'rules_version': RULES_VERSION,
                            'note': 'Official Korean terminology normalization; English meaning unchanged'})
        text = updated
    return text, changes


def verified_mentions(source, text):
    return [{'english': rule['english'], 'korean': rule['korean'], 'kind': rule['kind'],
             'source_url': rule['source_url'], 'rules_version': RULES_VERSION}
            for rule in RULES if eligible(source, rule) and rule['korean'] in text]
