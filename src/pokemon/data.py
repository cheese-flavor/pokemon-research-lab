"""Validate canonical species metadata and build one index record per species."""
import hashlib
import json
import math

STATS = {'hp': 'HP', 'attack': '공격', 'defense': '방어',
         'special-attack': '특수공격', 'special-defense': '특수방어', 'speed': '스피드'}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def load_records(path, expected_count, schema_version):
    items = json.loads(path.read_text(encoding='utf-8'))
    if len(items) != expected_count or {i['species_id'] for i in items} != set(range(1, expected_count + 1)):
        raise ValueError('Unexpected species set')
    records = []
    for item in sorted(items, key=lambda i: i['species_id']):
        if item['item_id'] != f"pokemon-species:{item['species_id']}":
            raise ValueError('Species ID mismatch')
        if not all(item[k] for k in ('name', 'name_ko', 'source_revision', 'source_urls', 'index_text', 'metadata_scope')):
            raise ValueError('Required item fields missing')
        if len(item['types']) not in (1, 2) or set(item['stats']) != set(STATS):
            raise ValueError('Invalid type or stats structure')
        for value in [item['height_m'], item['weight_kg'], *item['stats'].values()]:
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError('Invalid numeric attribute')
        text = item['index_text'] + '\n능력치: ' + ', '.join(
            f'{label} {item["stats"][key]}' for key, label in STATS.items())
        text += f'\n종족값 합계: {sum(item["stats"].values())}'
        metadata = {k: item[k] for k in ('item_id', 'species_id', 'pokemon_id', 'name_ko', 'name', 'generation',
                    'height_m', 'weight_kg', 'is_legendary', 'is_mythical', 'metadata_scope', 'source_revision', 'collected_at')}
        metadata.update(item['stats'])
        metadata.update({'bst': sum(item['stats'].values()), 'type_1': item['types'][0],
                         'type_2': item['types'][1] if len(item['types']) == 2 else '',
                         'content_hash': fingerprint(text), 'schema_version': schema_version,
                         'evidence_type': 'metadata', 'source_url': item['source_urls'][0]})
        records.append({'id': item['item_id'], 'text': text, 'metadata': metadata,
                        'source_urls': item['source_urls']})
    return records
