"""Execute task-4 representative ingestion and cache/profile checks; no RAG answers."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.pokemon.embeddings import write_json
from src.pokemon.ingestion import prepare_documents

CASES = [('25', '피카츄가 라이츄로 진화하는 조건을 찾아줘'),
         ('133', '이브이의 진화 분기와 조건을 비교할 자료를 찾아줘'),
         ('1008', '미라이돈의 바이올렛 도감 설명을 한국어로 찾아줘')]


def main():
    config = tomllib.loads((ROOT/'config/pokemon_rag.toml').read_text(encoding='utf-8'))
    files = [ROOT/'dataset/pokemon'/n for n in ('items.json','documents.json','documents_ko_enriched.json')]
    before = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    results = []
    for identity, question in CASES:
        print(f'Verifying species {identity}', flush=True)
        online = prepare_documents(ROOT, config, identity, question)
        offline = prepare_documents(ROOT, config, identity, question, offline=True)
        assert offline['count_before'] == offline['count_after'] == online['count_after']
        assert offline['llm_calls'] == offline['embedding_calls'] == offline['source_requests'] == 0
        assert offline['self_documents_complete'] and offline['source_search_cache_hits'] == 1
        results.append({'online':online, 'offline':offline})
    alternate = deepcopy(config)
    alternate['documents']['chunk_size_chars'] = 400
    changed = prepare_documents(ROOT, alternate, *CASES[1])
    assert changed['collection'] != results[1]['online']['collection']
    assert changed['chunks_this_run'] > results[1]['online']['chunks_this_run']
    assert changed['llm_calls'] == changed['source_requests'] == 0
    # Restore the default active collection for the next work unit.
    restored = prepare_documents(ROOT, config, *CASES[2], offline=True)
    corpus = json.loads(files[2].read_text(encoding='utf-8'))
    generated = [d for d in corpus if d['item_id']=='pokemon-species:1008' and d.get('is_machine_translation')]
    assert generated
    for doc in generated:
        sidecar = ROOT/config['documents']['cache_path']/'documents'/(doc['doc_id']+'.json')
        assert json.loads(sidecar.read_text(encoding='utf-8')) == doc
    assert before == {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    summary = {'cases':results,'alternate_400':changed,'active_collection':restored['collection'],
               'final_chunk_count':restored['count_after'],'translation_provenance_documents':len(generated),
               'all_three_input_files_unchanged':True}
    write_json(ROOT/'outputs/pokemon/ingestion/verification.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        print(f'Ingestion verification failed ({type(error).__name__}).',file=sys.stderr)
        sys.exit(1)
