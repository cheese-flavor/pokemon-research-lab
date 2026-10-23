"""Measure new-question and repeat paths, retaining full evidence only locally."""
import hashlib
import json
from pathlib import Path
import sys
import time
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.pokemon.citations import citation_numbers
from src.pokemon.embeddings import write_json
from src.pokemon.rag import answer_question

CASES = [
    ('q03', '4', '파이리의 수집된 한국어 도감에서 꼬리 불꽃이 건강 상태와 어떤 관련이 있는지 근거와 함께 설명해 줘'),
    ('q05', '52', '나옹의 기본 개체에 연결된 특성의 효과를 수집된 설명에 근거해 알려줘'),
]


def main():
    config = tomllib.loads((ROOT / 'config/pokemon_rag.toml').read_text(encoding='utf-8'))
    directory = ROOT / 'outputs/pokemon/submission/final'
    paths = [ROOT / 'dataset/pokemon' / name for name in
             ('items.json', 'documents.json', 'documents_ko_enriched.json')]
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    rows = []
    for name, item, question in CASES:
        pair = []
        for mode in ('online_allowed', 'offline_repeat'):
            started = time.perf_counter()
            stages = []
            def progress(stage):
                stages.append({'stage': stage, 'seconds_from_start': round(time.perf_counter() - started, 3)})
                print(name + ' ' + mode + ' ' + stage, flush=True)
            result = answer_question(ROOT, config, item, question,
                                     offline=mode == 'offline_repeat', progress=progress)
            elapsed = round(time.perf_counter() - started, 3)
            assert result['status'] in ('answered', 'insufficient')
            if name == 'q03':
                assert result['status'] == 'answered'
            assert result['trace'] == ['retrieve', 'generate']
            assert citation_numbers(result['answer']) == [s['number'] for s in result['sources']]
            assert any(s['evidence_type'] == 'external_document' for s in result['sources'])
            if pair:
                assert result['answer'] == pair[0]['answer'] and result['sources'] == pair[0]['sources']
                assert all(result['diagnostics'][key] == 0 for key in
                           ('answer_calls', 'embedding_calls', 'preparation_llm_calls', 'preparation_embedding_calls'))
            pair.append(result)
            write_json(directory / (name + '_' + mode + '.json'), result)
            row = {'case': name, 'mode': mode, 'seconds': elapsed, 'timings': result['timings'],
                   'stages': stages, 'diagnostics': result['diagnostics'],
                   'status': result['status'], 'used_citations': len(result['sources'])}
            rows.append(row)
            write_json(directory / 'performance.json', {'runs': rows, 'complete': False})
    assert before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    summary = {'runs': rows, 'complete': True, 'canonical_inputs_unchanged': True,
               'scope': 'two questions; source snapshot already downloaded; actual calls counted, no cache deletion'}
    write_json(directory / 'performance.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'Final verification failed ({type(error).__name__}).', file=sys.stderr)
        sys.exit(1)
