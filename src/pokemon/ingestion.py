"""Question-scoped external-source selection and incremental document indexing."""
import json
from pathlib import Path
import time
import re

from .chunking import CHUNKER_VERSION, chunks_for
from .data import fingerprint
from .embeddings import GmsEmbeddings, write_json
from .llm import GmsJson
from .prompts import KINDS, QUERY_PROMPT, SELECT_PROMPT, SELECT_SCHEMA, query_schema
from .sources import SourceCatalogue
from .store import indexing_lock, open_collection


class ItemChangeRequired(ValueError):
    """The question targets a different item than the selected one."""


def validate_query(result, versions):
    if set(result) != {'queries', 'kinds', 'requested_version', 'unsupported', 'requires_item_change'}:
        raise ValueError('Unexpected query fields')
    queries = result['queries']
    if not isinstance(queries, list) or not 1 <= len(queries) <= 5 or any(
            not isinstance(q, str) or not q.strip() or len(q) > 200 for q in queries):
        raise ValueError('Invalid query list')
    if not result['kinds'] or any(k not in KINDS for k in result['kinds']):
        raise ValueError('Invalid document kinds')
    if result['requested_version'] is not None and result['requested_version'] not in versions:
        raise ValueError('Unknown game version')
    if not isinstance(result['requires_item_change'], bool) or not isinstance(result['unsupported'], list) or any(
            not isinstance(v, str) for v in result['unsupported']):
        raise ValueError('Invalid query flags')


def validate_selection(result, candidates, limit):
    allowed = {c['candidate_id'] for c in candidates}
    chosen = result['selected_ids']
    reasons = result['reasons']
    if set(result) != {'selected_ids', 'reasons'} or not isinstance(chosen, list) or len(chosen) > limit:
        raise ValueError('Invalid selected list')
    if len(set(chosen)) != len(chosen) or not set(chosen) <= allowed:
        raise ValueError('Unknown or duplicate selected ID')
    if len(reasons) != len(allowed) or {r['candidate_id'] for r in reasons} != allowed:
        raise ValueError('Missing candidate decisions')
    for reason in reasons:
        if reason['decision'] != ('select' if reason['candidate_id'] in chosen else 'reject') or not reason['reason'].strip():
            raise ValueError('Inconsistent candidate decision')


def prepare_documents(root, config, item_name, question, offline=False, progress=None, reuse_prepared=False):
    root = Path(root)
    cfg, gms = config['documents'], config['gms']
    if not isinstance(question, str) or not question.strip() or len(question) > 4000:
        raise ValueError('Question must contain 1-4000 characters')
    if not 1 <= cfg['candidate_limit'] <= 30 or not 1 <= cfg['related_limit'] <= 8:
        raise ValueError('Invalid candidate selection limits')
    started = time.monotonic()
    cache = root/cfg['cache_path']
    with indexing_lock(root/'dataset/pokemon/ingestion/write.lock'):
        source = SourceCatalogue(root, root/cfg['corpus_path'], cache/'search', offline)
        item = source.resolve(item_name)
        # Reuse only fully indexed own documents of this exact corpus/chunk/model generation.
        # Version expressions and unfamiliar domains retain the original two-prompt planner.
        simple=bool(re.search(r'도감|설명|진화|특성|타입|몸무게|종족값|키가|키는',question))
        versioned=bool(re.search(r'버전|게임|레드|블루|옐로|골드|실버|루비|사파이어|에메랄드|다이아|펄|플래티넘|블랙|화이트|썬|울트라문|썬문|소드|실드|스칼렛|바이올렛|레전드',question,re.I))
        versioned=versioned or any(re.search(r'(?<![a-z0-9-])'+re.escape(v)+r'(?![a-z0-9-])',question,re.I) for v in source.versions)
        if reuse_prepared and simple and not versioned:
            signature=fingerprint([source.signature,cfg['schema_version'],CHUNKER_VERSION,cfg['chunk_size_chars'],
                                   cfg['chunk_overlap_chars'],gms['embedding_model'],gms['embedding_dimensions']])
            path=root/cfg['manifest_path']
            path=path.with_name(path.stem+'_'+signature[:12]+'.json')
            if path.exists():
                manifest=json.loads(path.read_text(encoding='utf-8'))
                saved=manifest.get('items',{}).get(item['item_id'],{})
                own_ids={d['doc_id'] for d in source.own(item['item_id'])}
                if (manifest.get('signature')==signature and own_ids==set(saved.get('own_doc_ids',[]))):
                    collection=open_collection(root/config['metadata']['store_path'],manifest['collection'],signature)
                    rows=collection.get(where={'item_id':item['item_id']},include=['metadatas'])
                    if own_ids <= {m['doc_id'] for m in rows['metadatas']} and set(saved['chunk_ids'])<=set(rows['ids']):
                        write_json(root/'dataset/pokemon/ingestion/active.json',
                                   {'collection':manifest['collection'],'signature':signature,'manifest':str(path.relative_to(root))})
                        if progress:
                            progress('documents_reused')
                        return {'reused_prepared':True,'unsupported':[],'requested_version':None,
                                'self_documents_complete':True,'llm_calls':0,'embedding_calls':0,
                                'elapsed_seconds':round(time.monotonic()-started,3)}
        llm = GmsJson(gms, cache/'llm', root/'streamlit_lab/.env', offline)
        if progress:
            progress('search_queries')
        plan = llm.run('pokemon_query_v1', QUERY_PROMPT,
            {'selected_item': {'item_id': item['item_id'], 'name': item['name'], 'name_ko': item['name_ko']},
             'question': question, 'versions': source.versions}, query_schema(source.versions),
            lambda r: validate_query(r, source.versions))
        if plan['requires_item_change']:
            raise ItemChangeRequired('Question requires selecting another Pokemon')
        queries = sorted(set([item['name_ko'], *[q.strip() for q in plan['queries']]]))
        if progress:
            progress('source_search')
        found = source.search(item, queries, plan['kinds'], plan['requested_version'], cfg['candidate_limit'])
        candidates = [{'candidate_id': f'c{index:03d}', 'title': d['title'], 'kind': d['kind'],
                       'language': d['language'], 'version': d['version'], 'version_kind': d['version_kind'],
                       'source_item_id': d['item_id'], 'generated': d.get('is_machine_translation', False),
                       'summary': d['content'][:160]} for index, d in enumerate(found)]
        by_candidate = {c['candidate_id']: d for c, d in zip(candidates, found)}
        if progress:
            progress('candidate_selection')
        selection = llm.run('pokemon_selection_v1', SELECT_PROMPT,
            {'selected_item': item['item_id'], 'question': question, 'requested_version': plan['requested_version'],
             'selection_limit': cfg['related_limit'], 'candidates': candidates}, SELECT_SCHEMA,
            lambda r: validate_selection(r, candidates, cfg['related_limit'])) if candidates else {'selected_ids': [], 'reasons': []}
        own = source.own(item['item_id'])
        selected = {d['doc_id']: d for d in own}
        selected.update({by_candidate[i]['doc_id']: by_candidate[i] for i in selection['selected_ids']})
        chunks = [c for doc in sorted(selected.values(), key=lambda d: d['doc_id'])
                  for c in chunks_for(doc, item['item_id'], cfg['chunk_size_chars'], cfg['chunk_overlap_chars'])]
        if {c['metadata']['doc_id'] for c in chunks} != set(selected):
            raise ValueError('Selected or mandatory document did not produce chunks')
        signature = fingerprint([source.signature, cfg['schema_version'], CHUNKER_VERSION, cfg['chunk_size_chars'],
                                 cfg['chunk_overlap_chars'], gms['embedding_model'], gms['embedding_dimensions']])
        physical_name = cfg['collection'] + '_' + signature[:12]
        manifest_path = root/cfg['manifest_path']
        manifest_path = manifest_path.with_name(manifest_path.stem+'_'+signature[:12]+'.json')
        manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {'items': {}}
        embedder = GmsEmbeddings(gms, root/config['metadata']['cache_path'], root/'streamlit_lab/.env', offline)
        if progress:
            progress('document_indexing')
        vectors = embedder.embed([c['text'] for c in chunks])
        collection = open_collection(root/config['metadata']['store_path'], physical_name, signature)
        before = collection.count()
        for start in range(0, len(chunks), gms['batch_size']):
            batch = chunks[start:start+gms['batch_size']]
            collection.upsert(ids=[c['id'] for c in batch], documents=[c['text'] for c in batch],
                              embeddings=vectors[start:start+len(batch)], metadatas=[{
                                  **c['metadata'], 'schema_version': cfg['schema_version'], 'index_generation': signature} for c in batch])
        saved = collection.get(where={'item_id': item['item_id']}, include=['metadatas', 'documents'])
        expected_ids = {c['id'] for c in chunks}
        if not expected_ids <= set(saved['ids']) or not {d['doc_id'] for d in own} <= {m['doc_id'] for m in saved['metadatas']}:
            raise ValueError('Mandatory documents or selected chunks missing after indexing')
        saved_map = dict(zip(saved['ids'], saved['documents']))
        if any(saved_map[c['id']] != c['text'] for c in chunks):
            raise ValueError('Stored chunk text mismatch')
        # Preserve full translation provenance and original source relationships locally.
        for doc in selected.values():
            write_json(cache/'documents'/(doc['doc_id']+'.json'), doc)
        summary = {'collection': physical_name, 'item_id': item['item_id'], 'queries': queries,
            'candidate_count': len(candidates), 'llm_selected_count': len(selection['selected_ids']),
            'llm_rejected_count': len(candidates)-len(selection['selected_ids']), 'mandatory_documents': len(own),
            'mandatory_candidates_rejected_by_llm': sum(d['item_id'] == item['item_id'] and key not in selection['selected_ids']
                                                       for key,d in by_candidate.items()),
            'indexed_documents_this_run': len(selected), 'chunks_this_run': len(chunks),
            'count_before': before, 'count_after': collection.count(), 'llm_calls': llm.calls, 'llm_cache_hits': llm.hits,
            'llm_tokens': llm.tokens, 'embedding_calls': embedder.calls, 'embedding_cache_hits': embedder.hits,
            'embedding_tokens': embedder.tokens, 'source_requests': source.source_requests,
            'source_catalogue_searches': source.searches, 'source_search_cache_hits': source.hits,
            'source_revision': source.revision, 'self_documents_complete': True,
            'unsupported': plan['unsupported'], 'requested_version': plan['requested_version'],
            'requested_kinds': plan['kinds'],
            'elapsed_seconds': round(time.monotonic()-started, 3), 'offline': offline}
        manifest['items'][item['item_id']] = {'chunk_ids': saved['ids'], 'own_doc_ids': [d['doc_id'] for d in own]}
        manifest.update({'signature': signature, 'collection': physical_name})
        write_json(manifest_path, manifest)
        audit_key = fingerprint([item['item_id'], question, signature])
        write_json(root/'dataset/pokemon/ingestion/audit'/(audit_key+'.json'),
                   {'summary': summary, 'plan': plan, 'candidates': candidates, 'selection': selection,
                    'candidate_doc_ids': {k: d['doc_id'] for k,d in by_candidate.items()},
                    'selected_doc_ids': sorted(selected), 'chunk_ids': [c['id'] for c in chunks]})
        write_json(root/'dataset/pokemon/ingestion/active.json', {'collection': physical_name, 'signature': signature,
                                                               'manifest': str(manifest_path.relative_to(root))})
        write_json(root/'outputs/pokemon/ingestion'/('offline_summary.json' if offline else 'online_summary.json'), summary)
        if progress:
            progress('documents_ready')
        return summary
