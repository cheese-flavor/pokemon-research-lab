"""Task 3: build/recheck the metadata collection without touching source data."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.pokemon.data import fingerprint, load_records
from src.pokemon.embeddings import GmsEmbeddings, write_json
from src.pokemon.store import indexing_lock, open_collection


def run(config_path, offline=False):
    config = tomllib.loads(config_path.read_text(encoding='utf-8'))
    cfg, gms = config['metadata'], config['gms']
    source = ROOT / cfg['items_path']
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    records = load_records(source, cfg['expected_count'], cfg['schema_version'])
    signature = fingerprint([source_hash, cfg['schema_version'], gms['embedding_model'],
                             gms['embedding_dimensions'], [r['metadata']['content_hash'] for r in records]])
    started = time.monotonic()
    manifest_path = ROOT / cfg['manifest_path']
    with indexing_lock(manifest_path.with_suffix('.lock')):
        collection = open_collection(ROOT / cfg['store_path'], cfg['collection'], signature)
        embedder = GmsEmbeddings(gms, ROOT / cfg['cache_path'], ROOT / 'streamlit_lab/.env', offline)
        count_before = collection.count()
        for start in range(0, len(records), gms['batch_size']):
            batch = records[start:start + gms['batch_size']]
            vectors = embedder.embed([r['text'] for r in batch])
            collection.upsert(ids=[r['id'] for r in batch], documents=[r['text'] for r in batch],
                              embeddings=vectors, metadatas=[{**r['metadata'], 'index_generation': signature} for r in batch])
            print(f'Indexed {min(start + len(batch), len(records))}/{len(records)}', flush=True)
        saved = collection.get(include=['metadatas', 'documents'])
        expected = {r['id']: r for r in records}
        if set(saved['ids']) != set(expected) or collection.count() != len(records):
            raise ValueError('Indexed species set/count mismatch')
        for identity, metadata, text in zip(saved['ids'], saved['metadatas'], saved['documents']):
            if text != expected[identity]['text'] or metadata['content_hash'] != fingerprint(text):
                raise ValueError('Indexed text integrity mismatch')
        if hashlib.sha256(source.read_bytes()).hexdigest() != source_hash:
            raise ValueError('Source changed during indexing')
        summary = {'collection': cfg['collection'], 'count_before': count_before, 'count_after': collection.count(),
                   'embedding_model': embedder.model, 'dimensions': embedder.dimensions,
                   'embedding_calls': embedder.calls, 'cache_hits': embedder.hits, 'embedding_tokens': embedder.tokens,
                   'source_sha256': source_hash, 'input_unchanged': True, 'index_signature': signature,
                   'elapsed_seconds': round(time.monotonic() - started, 3), 'offline': offline}
        write_json(manifest_path, {'summary': summary, 'records': [
            {'id': r['id'], 'content_hash': r['metadata']['content_hash'], 'source_urls': r['source_urls']} for r in records]})
        write_json(ROOT / 'outputs/pokemon/indexing' / ('offline_summary.json' if offline else 'online_summary.json'), summary)
        return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'config/pokemon_rag.toml')
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.config, args.offline), ensure_ascii=False, indent=2))
    except Exception as error:
        # API exceptions may contain request payloads: do not print their message or traceback.
        print(f'Indexing failed ({type(error).__name__}); check configuration, key, cache and lock.', file=sys.stderr)
        sys.exit(1)
