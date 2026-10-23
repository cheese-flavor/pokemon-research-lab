"""Audit missing Korean descriptions against the pinned original, entirely offline."""
import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.collect_pokemon_bulk import REVISION, ROOT


def analyze(directory):
    items = json.loads((directory / 'items.json').read_text(encoding='utf-8'))
    docs = json.loads((directory / 'documents.json').read_text(encoding='utf-8'))
    raw = directory / 'raw' / ('bulk_' + REVISION)
    def read(name):
        with (raw / (name + '.csv')).open(encoding='utf-8', newline='') as stream:
            return list(csv.DictReader(stream))
    languages = {r['id']: r['identifier'] for r in read('languages')}
    versions = {r['id']: r['identifier'] for r in read('versions')}
    original = read('pokemon_species_flavor_text')
    raw_korean = {int(r['species_id']) for r in original if languages[r['language_id']] == 'ko' and r['flavor_text'].strip()}
    normalized_korean = {d['item_id'] for d in docs if d['kind'] == 'species_description' and d['language'] == 'ko'}
    expected_ids = {f'pokemon-species:{number}' for number in raw_korean}
    if expected_ids != normalized_korean:
        raise ValueError('Original and normalized Korean coverage differ')
    missing = [i for i in items if i['item_id'] not in normalized_korean]
    raw_languages = defaultdict(set)
    by_version = defaultdict(Counter)
    for row in original:
        lang = languages[row['language_id']]
        raw_languages[int(row['species_id'])].add(lang)
        by_version[versions[row['version_id']]][lang] += 1
    generations = []
    for generation in dict.fromkeys(i['generation'] for i in items):
        total = sum(i['generation'] == generation for i in items)
        absent = sum(i['generation'] == generation for i in missing)
        generations.append({'generation': generation, 'total': total, 'missing': absent, 'available': total - absent})
    types = []
    for name in sorted({t for i in items for t in i['types']}):
        total = sum(name in i['types'] for i in items)
        absent = sum(name in i['types'] for i in missing)
        types.append({'type': name, 'total': total, 'missing': absent, 'rate': round(absent / total * 100, 2)})
    types.sort(key=lambda r: (-r['missing'], r['type']))
    result = {'revision': REVISION, 'total': len(items), 'missing': len(missing),
              'original_matches_normalized': True, 'generation_distribution': generations,
              'type_distribution': types, 'dual_type_note': '복합 타입은 각 타입에 포함하므로 타입별 건수 합계는 고유 종 수보다 큼',
              'missing_species': [{'id': i['species_id'], 'name': i['name_ko'], 'generation': i['generation'],
                                   'types': i['types'], 'original_languages': sorted(raw_languages[i['species_id']])} for i in missing],
              'version_language_rows': dict(by_version)}
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--visual-path', type=Path, default=ROOT / 'outputs/pokemon/missing-korean.html')
    args = parser.parse_args()
    result = analyze(ROOT / 'dataset/pokemon')
    output = ROOT / 'outputs/pokemon'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'language_audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    template = (ROOT / 'scripts/pokemon_language_chart.html').read_text(encoding='utf-8')
    payload = json.dumps(result, ensure_ascii=False).replace('<', '\\u003c')
    args.visual_path.parent.mkdir(parents=True, exist_ok=True)
    args.visual_path.write_text(template.replace('__AUDIT_DATA__', payload), encoding='utf-8')
    print(json.dumps({'total': result['total'], 'missing': result['missing'],
                      'raw_normalized_match': True, 'missing_languages': dict(Counter(','.join(s['original_languages']) for s in result['missing_species'])),
                      'generations': result['generation_distribution'], 'chart': str(args.visual_path)}, ensure_ascii=False, indent=2))
