"""Keep document boundaries and evolution condition alternatives intact."""
import json

from .data import fingerprint

CHUNKER_VERSION = 'chunk-v2'


def split_text(text, size, overlap):
    if size < 50 or not 0 <= overlap < size:
        raise ValueError('Invalid chunk size or overlap')
    start = 0
    while start < len(text):
        stop = min(start + size, len(text))
        if stop < len(text):
            boundary = max(text.rfind('\n', start + size//2, stop), text.rfind('。', start + size//2, stop),
                           text.rfind('. ', start + size//2, stop))
            if boundary >= 0:
                stop = boundary + 1
        yield text[start:stop]
        if stop == len(text):
            break
        start = max(start + 1, stop - overlap)


def chunks_for(doc, selected_id, size, overlap):
    # Validate configuration even when a document is short.
    if size < 50 or not 0 <= overlap < size:
        raise ValueError('Invalid chunk profile')
    profile = fingerprint([CHUNKER_VERSION, size, overlap])
    units = []
    if doc['kind'] == 'evolution_chain':
        chain = json.loads(doc['content'])
        for edge_index, edge in enumerate(chain['edges']):
            header = json.dumps({'chain_id': chain['chain_id'], 'from_species_id': edge['from_species_id'],
                                 'from': edge['from'], 'to_species_id': edge['to_species_id'], 'to': edge['to']}, ensure_ascii=False)
            for condition_index, condition in enumerate(edge['conditions']):
                # Each row is an alternative (OR); fields within the row must be read together (AND).
                text = header + '\n조건 행 내부 AND / 다른 조건 행과 OR\n' + json.dumps(condition, ensure_ascii=False, sort_keys=True)
                units.append((f'{edge_index}:{condition_index}', text))
        if not units:
            units = [('no-edges', doc['content'])]
    else:
        units = [('body', doc['content'])]
    result = []
    for unit_id, unit in units:
        parts = list(split_text(unit, size, overlap))
        for part_index, text in enumerate(parts):
            index = f'{unit_id}:{part_index}'
            metadata = {k: doc[k] for k in ('doc_id', 'title', 'source_url', 'kind', 'source_type', 'language',
                        'version', 'version_kind', 'version_scope', 'source_revision', 'collected_at')}
            metadata.update({'item_id': selected_id, 'source_item_id': doc['item_id'], 'chunk_index': index,
                'chunk_profile': profile, 'content_hash': fingerprint(text), 'evidence_type': 'external_document',
                'is_machine_translation': doc.get('is_machine_translation', False),
                'is_official_korean_text': doc.get('is_official_korean_text', doc['language'] == 'ko')})
            for field in ('original_doc_id', 'translation_model'):
                if field in doc:
                    metadata[field] = doc[field]
            # Context needed by generation must be repeated on split condition continuations.
            prefix = f"{doc['title']} / {doc['version_kind']}:{doc['version']} / {doc['language']}"
            if doc.get('is_machine_translation'):
                prefix += ' / 생성 한국어 번역'
            if doc['kind'] == 'evolution_chain':
                prefix += ' / 조건 범위: 수집 체인, 게임별 완전성 미확인'
                if unit_id != 'no-edges':
                    prefix += ' / ' + unit.split('\n', 1)[0] + f' / 조건 행 {unit_id}'
                    prefix += f' / 행 조각 {part_index+1}/{len(parts)} (부분 조각만으로 전체 조건 단정 금지)'
                    prefix += ' / ID·버전은 식별 필드, 0인 요구 플래그는 요구 없음'
            result.append({'id': fingerprint([selected_id, doc['doc_id'], profile, index]),
                           'text': prefix + '\n' + text, 'metadata': metadata})
    return result
