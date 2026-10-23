"""Bounded offline submission replay; aggregate output only, no quality scoring."""
import hashlib
import json
import math
from pathlib import Path
import sys
from time import perf_counter
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from verify_pokemon_rag import CASES
from src.pokemon.citations import citation_numbers
from src.pokemon.embeddings import write_json
from src.pokemon.explore import explore_items, matches
from src.pokemon.rag import answer_question


def main():
    config = tomllib.loads((ROOT / 'config/pokemon_rag.toml').read_text(encoding='utf-8'))
    paths = [ROOT / 'dataset/pokemon' / name for name in
             ('items.json', 'documents.json', 'documents_ko_enriched.json')]
    hashes = lambda: {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    before = hashes()
    rows = []
    for case in CASES:
        started = perf_counter()
        result = answer_question(ROOT, config, offline=True,
                                 **{k: v for k, v in case.items() if k != 'id'})
        elapsed = perf_counter() - started
        assert result['trace'] == ['retrieve', 'generate']
        assert citation_numbers(result['answer']) == [s['number'] for s in result['sources']]
        assert result['diagnostics']['answer_calls'] == result['diagnostics']['embedding_calls'] == 0
        assert all(e['item_id'] == e['source_item_id'] == result['selected_item_id']
                   for e in result['evidence'])
        rows.append({'case': case['id'], 'seconds': round(elapsed, 3),
                     'status': result['status'], 'stages': result['timings']})
    for name, query in [('objective', '1세대 전기 타입 중 몸무게 10kg 이하'),
                        ('subjective', '귀엽고 대전에서 무조건 이기는 포켓몬')]:
        started = perf_counter()
        result = explore_items(ROOT, config, query, offline=True)
        elapsed = perf_counter() - started
        assert result['diagnostics']['llm_calls'] == result['diagnostics']['embedding_calls'] == 0
        assert all(matches(item, result['plan']) for item in result['items'])
        if name == 'objective':
            assert {i['species_id'] for i in result['items']} == {25, 81}
        else:
            assert result['count'] == 0 and result['plan']['unsupported']
        rows.append({'case': name, 'seconds': round(elapsed, 3), 'count': result['count']})
    assert hashes() == before
    ordered = sorted(row['seconds'] for row in rows)
    summary = {'mode': 'offline cached sequential replay; not cold/network latency',
               'cases': rows, 'case_count': len(rows),
               'p95_nearest_rank_seconds': ordered[math.ceil(.95 * len(ordered)) - 1],
               'external_calls': 0, 'input_hashes_unchanged': True,
               'quality_scope': 'structural assertions only; independent factual review pending'}
    write_json(ROOT / 'outputs/pokemon/submission/verification.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'Submission verification failed ({type(error).__name__}).', file=sys.stderr)
        sys.exit(1)
