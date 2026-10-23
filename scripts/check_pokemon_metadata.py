"""Small Korean metadata retrieval smoke check, not a RAG evaluation."""
import argparse
import json
from pathlib import Path
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.pokemon.embeddings import GmsEmbeddings, write_json
from src.pokemon.store import open_collection

PROBES = [('피카츄 전기 타입', 25), ('리자몽 불꽃 비행 타입', 6), ('이브이 노말 타입', 133),
          ('미라이돈 전기 드래곤 타입', 1008), ('이상해씨 풀 독 타입', 1)]


def run(offline=False):
    config = tomllib.loads((ROOT/'config/pokemon_rag.toml').read_text(encoding='utf-8'))
    cfg = config['metadata']
    manifest = json.loads((ROOT/cfg['manifest_path']).read_text(encoding='utf-8'))
    collection = open_collection(ROOT/cfg['store_path'], cfg['collection'], manifest['summary']['index_signature'])
    embedder = GmsEmbeddings(config['gms'], ROOT/cfg['cache_path'], ROOT/'streamlit_lab/.env', offline)
    vectors = embedder.embed([query for query, _ in PROBES])
    result = collection.query(query_embeddings=vectors, n_results=5, include=['distances'])
    ranks = [ids.index(f'pokemon-species:{number}') + 1 if f'pokemon-species:{number}' in ids else None
             for ids, (_, number) in zip(result['ids'], PROBES)]
    expected_ids = [f'pokemon-species:{number}' for _, number in PROBES]
    direct = collection.get(ids=expected_ids, include=['metadatas'])
    summary = {'probe_count': len(PROBES), 'top1_hits': sum(r == 1 for r in ranks),
               'top5_hits': sum(r is not None for r in ranks), 'expected_item_ranks': ranks,
               'embedding_calls': embedder.calls, 'embedding_tokens': embedder.tokens,
               'direct_id_hits': len(set(direct['ids']) & set(expected_ids)),
               'offline': offline, 'scope': 'name-and-type metadata smoke checks only'}
    write_json(ROOT/'outputs/pokemon/indexing/search_smoke.json', summary)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.offline), ensure_ascii=False, indent=2))
    except Exception as error:
        print(f'Metadata smoke check failed ({type(error).__name__}).', file=sys.stderr)
        sys.exit(1)
