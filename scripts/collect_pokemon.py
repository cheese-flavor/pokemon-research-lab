"""Collect PokéAPI species 1..151 locally; standard library, no GMS key required."""
import argparse
import hashlib
import json
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://pokeapi.co/api/v2/'


class Client:
    def __init__(self, directory, delay=0.25, offline=False):
        self.directory = directory
        self.delay = delay
        self.offline = offline
        self.requests = 0
        self.hits = 0

    def get(self, url):
        parsed = urlparse(url)
        if parsed.scheme != 'https' or parsed.netloc != 'pokeapi.co' or not parsed.path.startswith('/api/v2/') or parsed.query:
            raise ValueError('Only official PokéAPI resource URLs are allowed')
        path = self.directory / (hashlib.sha256(url.encode()).hexdigest() + '.json')
        if path.exists():
            self.hits += 1
            saved = json.loads(path.read_text(encoding='utf-8'))
            if saved['source_url'] != url:
                raise ValueError('Cache URL mismatch')
            return saved
        if self.offline:
            raise FileNotFoundError(f'Missing cached resource: {url}')
        for attempt in range(4):
            try:
                self.requests += 1
                request = urllib.request.Request(url, headers={'User-Agent': 'PokemonResearchLab/0.1 (educational data collection)'})
                with urllib.request.urlopen(request, timeout=30) as response:
                    data = json.load(response)
                result = {'source_url': url, 'fetched_at': datetime.now(timezone.utc).isoformat(), 'data': data}
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_suffix('.tmp')
                temporary.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
                temporary.replace(path)
                time.sleep(self.delay)
                return result
            except urllib.error.HTTPError as error:
                if error.code not in (429, 500, 502, 503, 504) or attempt == 3:
                    raise
                retry = error.headers.get('Retry-After', '')
                time.sleep(max(2 ** attempt, min(float(retry), 60) if retry.isdigit() else 0))
            except (urllib.error.URLError, TimeoutError):
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)


def localized(entries, field='name', language='ko'):
    return next((e[field] for e in entries if e['language']['name'] == language), '')


def clean(text):
    return ' '.join(text.replace('\f', ' ').split())


def document(item_id, kind, saved, title, content, language='und', version='', suffix=''):
    identity = f'{item_id}:{kind}:{saved["source_url"]}:{language}:{version}:{suffix}'
    return {'doc_id': hashlib.sha256(identity.encode()).hexdigest(), 'item_id': item_id,
            'kind': kind, 'title': title, 'source_url': saved['source_url'],
            'collected_at': saved['fetched_at'], 'source_type': 'pokeapi',
            'language': language, 'version': version,
            'version_scope': 'explicit' if version else 'not_version_specific', 'content': content}


def evolution_edges(node):
    edges = []
    for child in node.get('evolves_to', []):
        edges.append({'from': node['species']['name'], 'to': child['species']['name'],
                      'conditions': child['evolution_details']})
        edges.extend(evolution_edges(child))
    return edges


def validate(items, docs, count):
    ids = {i['item_id'] for i in items}
    if len(items) != count or len(ids) != count:
        raise ValueError('Item count or uniqueness failure')
    if len({d['doc_id'] for d in docs}) != len(docs):
        raise ValueError('Duplicate document IDs')
    if any(d['item_id'] not in ids or not d['content'].strip() or not d['source_url'] for d in docs):
        raise ValueError('Invalid document linkage/content/source')
    own = {d['item_id'] for d in docs if d['kind'] == 'species_description'}
    if own != ids:
        raise ValueError('Every species must have its own description')
    return {'items': len(items), 'unique_items': len(ids), 'documents': len(docs),
            'items_with_own_document': len(own),
            'missing_korean_names': sum(not i['name_ko'] for i in items),
            'items_without_korean_description': len(ids - {d['item_id'] for d in docs if d['kind'] == 'species_description' and d['language'] == 'ko'}),
            'document_kinds': dict(Counter(d['kind'] for d in docs)),
            'document_languages': dict(Counter(d['language'] for d in docs))}


def save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def collect(count, directory, offline=False):
    directory.mkdir(parents=True, exist_ok=True)
    client = Client(directory / 'raw', offline=offline)
    items, docs = [], []
    for number in range(1, count + 1):
        species_saved = client.get(f'{BASE}pokemon-species/{number}/')
        species = species_saved['data']
        default = next(v['pokemon'] for v in species['varieties'] if v['is_default'])
        pokemon_saved = client.get(default['url'])
        pokemon = pokemon_saved['data']
        if species['id'] != number or pokemon['species']['url'] != species_saved['source_url']:
            raise ValueError('Species/default variety linkage mismatch')
        item_id = f'pokemon-species:{number}'
        name_ko = localized(species['names'])
        type_names = []
        for entry in sorted(pokemon['types'], key=lambda e: e['slot']):
            type_data = client.get(entry['type']['url'])['data']
            type_names.append(localized(type_data['names']) or type_data['name'])
        abilities = []
        for entry in pokemon['abilities']:
            ability_saved = client.get(entry['ability']['url'])
            ability = ability_saved['data']
            abilities.append({'id': ability['id'], 'name': ability['name'], 'name_ko': localized(ability['names']), 'is_hidden': entry['is_hidden']})
            for flavor in ability['flavor_text_entries']:
                if flavor['language']['name'] in ('ko', 'en') and clean(flavor['flavor_text']):
                    docs.append(document(item_id, 'ability_description', ability_saved,
                                         f'{name_ko or species["name"]} / {localized(ability["names"]) or ability["name"]}',
                                         clean(flavor['flavor_text']), flavor['language']['name'],
                                         flavor['version_group']['name'], str(ability['id'])))
        item = {'item_id': item_id, 'species_id': number, 'pokemon_id': pokemon['id'],
                'name': species['name'], 'name_ko': name_ko, 'types': type_names,
                'generation': species['generation']['name'],
                'height_m': pokemon['height'] / 10, 'weight_kg': pokemon['weight'] / 10,
                'is_legendary': species['is_legendary'], 'is_mythical': species['is_mythical'],
                'abilities': abilities, 'stats': {s['stat']['name']: s['base_stat'] for s in pokemon['stats']},
                'source_urls': [species_saved['source_url'], pokemon_saved['source_url']],
                'collected_at': species_saved['fetched_at'],
                'metadata_scope': 'default variety, API current snapshot; not original-generation stats'}
        item['index_text'] = '\n'.join([f'이름: {name_ko} ({species["name"]})', f'전국도감 번호: {number}',
                                       f'타입: {", ".join(type_names)}', f'최초 등장 세대: {item["generation"]}',
                                       f'키: {item["height_m"]}m / 몸무게: {item["weight_kg"]}kg',
                                       f'전설: {item["is_legendary"]} / 환상: {item["is_mythical"]}',
                                       '특성: ' + ', '.join(a['name_ko'] or a['name'] for a in abilities),
                                       '수치·타입·특성은 현재 API 기본 형태 기준이며 게임별 과거 값은 별도 확인 필요.'])
        items.append(item)
        for flavor in species['flavor_text_entries']:
            if flavor['language']['name'] in ('ko', 'en') and clean(flavor['flavor_text']):
                docs.append(document(item_id, 'species_description', species_saved,
                                     f'{name_ko or species["name"]} 도감 설명 / {flavor["version"]["name"]}',
                                     clean(flavor['flavor_text']), flavor['language']['name'], flavor['version']['name']))
        chain_saved = client.get(species['evolution_chain']['url'])
        edges = evolution_edges(chain_saved['data']['chain'])
        docs.append(document(item_id, 'evolution_chain', chain_saved, f'{name_ko or species["name"]} 관련 진화 체인',
                             json.dumps({'edges': edges, 'note': '체인 전체에는 현재 항목 이외의 종이 포함됨. 조건은 구조화된 원본 필드이며 특정 게임 버전의 완전한 조건/예외를 보장하지 않음.'}, ensure_ascii=False)))
        if number % 10 == 0 or number == count:
            print(f'Collected {number}/{count}; HTTP={client.requests}, cache_hits={client.hits}', flush=True)
    summary = validate(items, docs, count)
    save(directory / 'items.json', items)
    save(directory / 'documents.json', docs)
    save(directory / 'manifest.json', {'created_at': datetime.now(timezone.utc).isoformat(),
         'scope': f'species 1..{count}, default varieties', 'quality': summary,
         'network_requests': client.requests, 'cache_hits': client.hits,
         'limitations': ['Evolution conditions are not fully version-specific', 'Current metadata is not historical generation metadata', 'Only ko/en descriptions retained', 'No image files downloaded'],
         'source_policy': 'https://pokeapi.co/docs/v2#fairuse'})
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count', type=int, default=151)
    parser.add_argument('--offline', action='store_true', help='Require all API responses to exist in local cache')
    args = parser.parse_args()
    if not 1 <= args.count <= 151:
        parser.error('--count must be between 1 and 151')
    collect(args.count, ROOT / 'dataset' / 'pokemon_pilot', args.offline)
