"""Reproducibly collect all 1,025 species from official PokéAPI source CSVs."""
import argparse
import csv
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.collect_pokemon import ROOT, clean, document, save, validate

# Pin the source so subsequent runs cannot silently mix upstream revisions.
REVISION = '2bf639e5572812a67d2b94903fdcb9d095f5aeb2'
BASE = f'https://raw.githubusercontent.com/PokeAPI/pokeapi/{REVISION}/data/v2/csv/'
FILES = ['pokemon_species', 'pokemon', 'pokemon_species_names', 'pokemon_species_flavor_text',
         'pokemon_types', 'pokemon_stats', 'pokemon_abilities', 'abilities', 'ability_names',
         'ability_flavor_text', 'types', 'type_names', 'stats', 'versions', 'version_groups',
         'generations', 'languages', 'pokemon_evolution', 'evolution_triggers', 'items']


def grouped(rows, field):
    result = defaultdict(list)
    for row in rows:
        result[row[field]].append(row)
    return result


def load_tables(directory, offline):
    directory.mkdir(parents=True, exist_ok=True)
    provenance_path = directory / 'sources.json'
    provenance = json.loads(provenance_path.read_text(encoding='utf-8')) if provenance_path.exists() else {}
    tables, requests = {}, 0
    for name in FILES:
        path = directory / (name + '.csv')
        url = BASE + path.name
        if not path.exists():
            if offline:
                raise FileNotFoundError(f'Missing bulk cache: {name}')
            for attempt in range(4):
                try:
                    requests += 1
                    req = urllib.request.Request(url, headers={'User-Agent': 'PokemonResearchLab/0.1 (educational bulk collection)'})
                    with urllib.request.urlopen(req, timeout=60) as response:
                        raw = response.read()
                    temporary = path.with_suffix('.tmp')
                    temporary.write_bytes(raw)
                    temporary.replace(path)
                    provenance[name] = {'source_url': url, 'fetched_at': datetime.now(timezone.utc).isoformat(),
                                        'sha256': hashlib.sha256(raw).hexdigest()}
                    save(provenance_path, provenance)
                    time.sleep(0.25)
                    break
                except (urllib.error.URLError, TimeoutError):
                    if attempt == 3:
                        raise
                    time.sleep(2 ** attempt)
        if name not in provenance or hashlib.sha256(path.read_bytes()).hexdigest() != provenance[name]['sha256']:
            raise ValueError(f'Bulk cache provenance/checksum mismatch: {name}')
        with path.open(encoding='utf-8', newline='') as stream:
            tables[name] = list(csv.DictReader(stream))
        print(f'Loaded {name}: {len(tables[name])} rows', flush=True)
    return tables, provenance, requests


def collect(directory, offline=False):
    directory.mkdir(parents=True, exist_ok=True)
    tables, sources, requests = load_tables(directory / 'raw' / ('bulk_' + REVISION), offline)
    by_id = {name: {r['id']: r for r in tables[name]} for name in
             ('pokemon_species', 'abilities', 'types', 'stats', 'versions', 'version_groups',
              'generations', 'languages', 'evolution_triggers', 'items')}
    species_rows = tables['pokemon_species']
    species_ids = {int(r['id']) for r in species_rows}
    if species_ids != set(range(1, 1026)):
        raise ValueError('Pinned source is not exactly species IDs 1..1025')
    defaults = [p for p in tables['pokemon'] if p['is_default'] == '1']
    pokemon_by_species = {p['species_id']: p for p in defaults}
    if len(defaults) != len(pokemon_by_species) or set(pokemon_by_species) != {r['id'] for r in species_rows}:
        raise ValueError('Default variety coverage/uniqueness failure')
    names = grouped(tables['pokemon_species_names'], 'pokemon_species_id')
    flavors = grouped(tables['pokemon_species_flavor_text'], 'species_id')
    ptypes = grouped(tables['pokemon_types'], 'pokemon_id')
    pstats = grouped(tables['pokemon_stats'], 'pokemon_id')
    pabilities = grouped(tables['pokemon_abilities'], 'pokemon_id')
    ability_names = grouped(tables['ability_names'], 'ability_id')
    ability_flavors = grouped(tables['ability_flavor_text'], 'ability_id')
    type_names = grouped(tables['type_names'], 'type_id')
    evolutions = grouped(tables['pokemon_evolution'], 'evolved_species_id')
    chains = grouped(species_rows, 'evolution_chain_id')

    def korean(rows):
        return next((r['name'] for r in rows if r['local_language_id'] == '3'), '')

    def source(name):
        return {**sources[name], 'source_revision': REVISION}

    def add_doc(item_id, kind, file, title, content, language='und', version='', suffix=''):
        doc = document(item_id, kind, source(file), title, content, language, version, suffix)
        doc['source_revision'] = REVISION
        doc['source_type'] = 'pokeapi_source_csv'
        doc['version_kind'] = ('version' if kind == 'species_description' else 'version_group') if version else 'mixed_or_unspecified'
        docs.append(doc)

    items, docs = [], []
    for species in sorted(species_rows, key=lambda r: int(r['id'])):
        number = int(species['id'])
        item_id = f'pokemon-species:{number}'
        pokemon = pokemon_by_species[str(number)]
        name_ko = korean(names[str(number)])
        genus_ko = next((r['genus'] for r in names[str(number)] if r['local_language_id'] == '3'), '')
        types = [korean(type_names[t['type_id']]) or by_id['types'][t['type_id']]['identifier']
                 for t in sorted(ptypes[pokemon['id']], key=lambda r: int(r['slot']))]
        abilities = []
        for entry in pabilities[pokemon['id']]:
            aid = entry['ability_id']
            abilities.append({'id': int(aid), 'name': by_id['abilities'][aid]['identifier'],
                              'name_ko': korean(ability_names[aid]), 'is_hidden': entry['is_hidden'] == '1'})
            for flavor in ability_flavors[aid]:
                language = by_id['languages'][flavor['language_id']]['identifier']
                if language in ('ko', 'en') and clean(flavor['flavor_text']):
                    add_doc(item_id, 'ability_description', 'ability_flavor_text',
                            f'{name_ko or species["identifier"]} / {abilities[-1]["name_ko"] or abilities[-1]["name"]}',
                            clean(flavor['flavor_text']), language,
                            by_id['version_groups'][flavor['version_group_id']]['identifier'], aid)
        item = {'item_id': item_id, 'species_id': number, 'pokemon_id': int(pokemon['id']),
                'name': species['identifier'], 'name_ko': name_ko, 'genus_ko': genus_ko, 'types': types,
                'generation': by_id['generations'][species['generation_id']]['identifier'],
                'height_m': int(pokemon['height']) / 10, 'weight_kg': int(pokemon['weight']) / 10,
                'is_legendary': species['is_legendary'] == '1', 'is_mythical': species['is_mythical'] == '1',
                'abilities': abilities, 'stats': {by_id['stats'][s['stat_id']]['identifier']: int(s['base_stat']) for s in pstats[pokemon['id']]},
                'source_urls': [BASE + 'pokemon_species.csv', BASE + 'pokemon.csv'],
                'source_revision': REVISION, 'collected_at': sources['pokemon_species']['fetched_at'],
                'metadata_scope': 'default variety, pinned source snapshot; not historical-generation stats'}
        item['index_text'] = '\n'.join([f'이름: {name_ko} ({item["name"]})', f'전국도감 번호: {number}',
                                       f'분류: {genus_ko}', f'타입: {", ".join(types)}', f'최초 등장 세대: {item["generation"]}',
                                       f'키: {item["height_m"]}m / 몸무게: {item["weight_kg"]}kg',
                                       f'전설: {item["is_legendary"]} / 환상: {item["is_mythical"]}',
                                       '특성: ' + ', '.join(a['name_ko'] or a['name'] for a in abilities),
                                       '수치·타입·특성은 원본 스냅샷 기본 형태 기준이며 게임별 과거 값은 별도 확인 필요.'])
        items.append(item)
        for flavor in flavors[str(number)]:
            language = by_id['languages'][flavor['language_id']]['identifier']
            if language in ('ko', 'en') and clean(flavor['flavor_text']):
                version = by_id['versions'][flavor['version_id']]['identifier']
                add_doc(item_id, 'species_description', 'pokemon_species_flavor_text',
                        f'{name_ko or item["name"]} 도감 설명 / {version}', clean(flavor['flavor_text']), language, version)
        edges = []
        for member in chains[species['evolution_chain_id']]:
            parent = member['evolves_from_species_id']
            if parent:
                conditions = []
                for row in evolutions[member['id']]:
                    condition = {k: v for k, v in row.items() if v != ''}
                    condition['version_group'] = by_id['version_groups'].get(row['version_group_id'], {}).get('identifier', '')
                    condition['trigger_name'] = by_id['evolution_triggers'].get(row['evolution_trigger_id'], {}).get('identifier', '')
                    for field in ('trigger_item_id', 'held_item_id'):
                        if row[field]:
                            condition[field.replace('_id', '_name')] = by_id['items'][row[field]]['identifier']
                    conditions.append(condition)
                edges.append({'from_species_id': int(parent), 'from': by_id['pokemon_species'][parent]['identifier'],
                              'to_species_id': int(member['id']), 'to': member['identifier'], 'conditions': conditions})
        add_doc(item_id, 'evolution_chain', 'pokemon_evolution', f'{name_ko or item["name"]} 관련 진화 체인',
                json.dumps({'chain_id': species['evolution_chain_id'], 'edges': edges,
                            'note': '종 연결은 pokemon_species.csv의 부모·체인 필드를 결합함. 체인 전체에는 다른 종이 포함됨. 조건별 version_group을 구별해야 하며 모든 게임별 예외를 보장하지 않음.'}, ensure_ascii=False))
        docs[-1]['related_source_urls'] = [BASE + 'pokemon_species.csv', BASE + 'version_groups.csv', BASE + 'evolution_triggers.csv', BASE + 'items.csv']
    summary = validate(items, docs, 1025)
    summary['items_with_six_stats'] = sum(len(i['stats']) == 6 for i in items)
    summary['items_with_types'] = sum(bool(i['types']) for i in items)
    summary['items_with_abilities'] = sum(bool(i['abilities']) for i in items)
    summary['generations'] = dict(Counter(i['generation'] for i in items))
    if min(summary['items_with_six_stats'], summary['items_with_types'], summary['items_with_abilities']) != 1025:
        raise ValueError('Missing metadata coverage')
    save(directory / 'items.json', items)
    save(directory / 'documents.json', docs)
    save(directory / 'manifest.json', {'created_at': datetime.now(timezone.utc).isoformat(),
         'scope': 'species 1..1025, default varieties', 'source_revision': REVISION,
         'source_mode': 'official PokéAPI source CSVs', 'quality': summary,
         'network_requests': requests, 'cached_files': len(FILES) - requests if requests <= len(FILES) else None,
         'source_files': sources, 'limitations': ['Current source snapshot is not historical metadata',
         'Evolution version group conditions may not cover every game exception', 'Only ko/en retained', 'No images downloaded']})
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true')
    collect(ROOT / 'dataset' / 'pokemon', parser.parse_args().offline)
