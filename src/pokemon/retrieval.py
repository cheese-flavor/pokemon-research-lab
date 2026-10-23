"""Merge a mandatory metadata record with scoped semantic document results."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import tiktoken

from .chunking import CHUNKER_VERSION
from .citations import prompt_evidence
from .data import fingerprint
from .embeddings import GmsEmbeddings
from .sources import SourceCatalogue
from .prompts import KINDS
from .store import read_collection


def version_matches(metadata, versions, groups):
    if not versions or metadata['kind'] == 'evolution_chain':
        return True
    if metadata['version_kind'] == 'version':
        return metadata['version'] in versions
    if metadata['version_kind'] == 'version_group':
        return metadata['version'] in {groups[v] for v in versions}
    return False


def language_priority(metadata):
    if metadata['language'] == 'ko':
        return 1 if metadata.get('is_machine_translation') else 0
    return 0 if metadata['language'] == 'und' else 2


def deduplicate(rows, keep_versions=False):
    """Exact body duplicates only; keep aliases/provenance and version coverage."""
    result, seen = [], {}
    for row in rows:
        m = row['metadata']
        key = (m['source_item_id'], m['kind'], m['language'], m['content_hash'],
               m['version_kind'], m['version'] if keep_versions else None)
        if key not in seen:
            entry = deepcopy(row)
            entry['provenance'] = [{'chunk_id': row['id'], 'doc_id': m['doc_id'], 'version': m['version']}]
            seen[key] = entry
            result.append(entry)
        else:
            seen[key]['provenance'].append({'chunk_id': row['id'], 'doc_id': m['doc_id'], 'version': m['version']})
    return result


class Retriever:
    def __init__(self, root, config, offline=False):
        self.root, self.config = Path(root), config
        self.source = SourceCatalogue(self.root, self.root/config['documents']['corpus_path'],
                                      self.root/config['documents']['cache_path']/'search', offline)
        cfg = config['metadata']
        manifest = json.loads((self.root/cfg['manifest_path']).read_text(encoding='utf-8'))['summary']
        if manifest['source_sha256'] != hashlib.sha256((self.root/cfg['items_path']).read_bytes()).hexdigest():
            raise ValueError('Metadata index is stale')
        self.meta = read_collection(self.root/cfg['store_path'], cfg['collection'], manifest['index_signature'])
        active = json.loads((self.root/'dataset/pokemon/ingestion/active.json').read_text(encoding='utf-8'))
        d, gms = config['documents'], config['gms']
        signature = fingerprint([self.source.signature, d['schema_version'], CHUNKER_VERSION, d['chunk_size_chars'],
                                 d['chunk_overlap_chars'], gms['embedding_model'], gms['embedding_dimensions']])
        if active['signature'] != signature:
            raise ValueError('Active document index does not match configuration')
        if manifest['embedding_model'] != gms['embedding_model'] or manifest['dimensions'] != gms['embedding_dimensions']:
            raise ValueError('Metadata and query embedding models differ')
        self.docs = read_collection(self.root/cfg['store_path'], active['collection'], signature)
        self.embedder = GmsEmbeddings(gms, self.root/cfg['cache_path'], self.root/'streamlit_lab/.env', offline)
        group_ids = {r['id']: r['identifier'] for r in self.source.rows('version_groups')}
        self.groups = {v: group_ids[g] for v, g in self.source.version_groups.items()}

    def retrieve(self, item_name, question, versions=None, kinds=None, blocked=False):
        cfg = self.config['retrieval']
        top_k, fetch_k, maximum = cfg['document_top_k'], cfg['document_fetch_k'], cfg['max_fetch_k']
        if not 1 <= top_k <= fetch_k <= maximum <= 1000:
            raise ValueError('Invalid Top-k/fetch settings')
        if cfg['context_budget_tokens'] < 1:
            raise ValueError('Invalid evidence context budget')
        versions = list(dict.fromkeys(versions or []))
        if kinds and not set(kinds)<=set(KINDS):
            raise ValueError('Unknown document kind')
        if any(v not in self.groups for v in versions):
            raise ValueError('Unknown requested game version')
        item = self.source.resolve(item_name)
        item_id = item['item_id']
        meta = self.meta.get(ids=[item_id], include=['documents','metadatas'])
        if meta['ids'] != [item_id]:
            raise ValueError('Selected metadata not indexed')
        evidence = [{'number':1, 'chunk_ids':[item_id], 'doc_ids':[], 'item_id':item_id, 'source_item_id':item_id,
                     'evidence_type':'metadata', 'kind':'metadata', 'title':item['name_ko']+' 기본 형태 메타데이터',
                     'source_url':item['source_urls'][0], 'source_urls':item['source_urls'],
                     'source_revision':item['source_revision'], 'language':'ko', 'versions':[],
                     'source_type':'pokeapi_metadata', 'collected_at':item['collected_at'],
                     'metadata_scope':item['metadata_scope'],
                     'version_kind':'snapshot', 'is_machine_translation':False, 'text':meta['documents'][0]}]
        evidence[0]['source_urls']=list(dict.fromkeys([*item['source_urls'],*[self.source.source_urls[name] for name in
            ('pokemon_species_names','pokemon_types','type_names','pokemon_stats','pokemon_abilities','ability_names','generations')]]))
        encoder = tiktoken.get_encoding('cl100k_base')
        def tokens(value):
            return len(encoder.encode(json.dumps(prompt_evidence(value),ensure_ascii=False,sort_keys=True)))
        if tokens(evidence) > cfg['context_budget_tokens']:
            raise ValueError('Budget cannot fit mandatory metadata')
        filters = [{'item_id':item_id}, {'source_item_id':item_id}]
        if kinds:
            filters.append({'kind':{'$in':kinds}})
        scoped = self.docs.get(where={'$and':filters}, include=['documents','metadatas'])
        all_rows = [{'id':i,'text':t,'metadata':m} for i,t,m in zip(scoped['ids'],scoped['documents'],scoped['metadatas'])]
        eligible = [r for r in all_rows if version_matches(r['metadata'],versions,self.groups)]
        warnings = []
        if versions and not any(r['metadata']['version_kind'] in ('version','version_group') for r in eligible):
            warnings.append('요청 버전의 명시적 설명이 없습니다. 다른 버전을 대체 근거로 사용하지 않습니다.')
        if not eligible and not blocked:
            warnings.append('선택 항목·버전 범위의 설명 근거가 없습니다.')
        diagnostics = {'scoped_chunks':len(all_rows), 'eligible_chunks':len(eligible), 'raw_candidates':0,
                       'deduplicated_candidates':0, 'document_top_k':top_k}
        if eligible and not blocked:
            vector = self.embedder.embed([question])[0]
            # All eligible IDs enforce exact version filters before semantic search.
            eligible_ids = [r['id'] for r in eligible]
            preference = {}
            def representation_key(row):
                m=row['metadata']
                title = self.source.by_doc[m['original_doc_id']]['title'] if m.get('original_doc_id') else m['title']
                return (m['kind'],title,m['version_kind'],m['version'],m['chunk_index'])
            for row in eligible:
                key = representation_key(row)
                if key not in preference or language_priority(row['metadata']) < language_priority(preference[key]['metadata']):
                    preference[key] = row
            limit = min(fetch_k,len(eligible))
            while True:
                found = self.docs.query(query_embeddings=[vector],n_results=limit,
                    where={'$and':[{'item_id':item_id},{'source_item_id':item_id},{'doc_id':{'$in':list({r['metadata']['doc_id'] for r in eligible})}}]},
                    include=['documents','metadatas','distances'])
                ranked=[]
                for i,t,m,dist in zip(found['ids'][0],found['documents'][0],found['metadatas'][0],found['distances'][0]):
                    if i in eligible_ids:
                        raw={'id':i,'text':t,'metadata':m}
                        chosen=deepcopy(preference[representation_key(raw)])
                        chosen['distance']=float(dist)
                        ranked.append(chosen)
                unique=deduplicate(ranked,keep_versions=len(versions)>1)
                if len(unique)>=top_k or limit>=min(maximum,len(eligible)):
                    break
                limit=min(limit*2,maximum,len(eligible))
            # Version comparisons reserve one available description for each requested version.
            if len(versions)>1:
                first=[]
                for version in versions:
                    match=next((r for r in unique if r['metadata']['version_kind']!='mixed_or_unspecified'
                                and version_matches(r['metadata'],[version],self.groups)),None)
                    if match is not None and match not in first:
                        first.append(match)
                    elif match is None:
                        warnings.append(f'{version} 버전 설명 근거가 검색되지 않았습니다.')
                unique=first+[r for r in unique if r not in first]
            diagnostics.update(raw_candidates=len(ranked),deduplicated_candidates=len(unique))
            for row in unique:
                if len(evidence)-1>=top_k:
                    break
                m=row['metadata']
                entry={'number':len(evidence)+1,'chunk_ids':list(dict.fromkeys(p['chunk_id'] for p in row['provenance'])),
                    'doc_ids':list(dict.fromkeys(p['doc_id'] for p in row['provenance'])),
                    'item_id':m['item_id'],'source_item_id':m['source_item_id'],'evidence_type':'external_document',
                    'kind':m['kind'],'title':m['title'],'source_url':m['source_url'],'source_revision':m['source_revision'],
                    'source_type':m['source_type'],'version_scope':m['version_scope'],'collected_at':m['collected_at'],
                    'language':m['language'],'versions':sorted({p['version'] for p in row['provenance'] if p['version']}),
                    'version_kind':m['version_kind'],'is_machine_translation':m.get('is_machine_translation',False),
                    'text':row['text']}
                entry['chunk_index']=m['chunk_index']
                source_doc=self.source.by_doc[m['doc_id']]
                entry['source_urls']=list(dict.fromkeys([m['source_url'],*source_doc.get('related_source_urls',[])]))
                if m.get('original_doc_id'):
                    original=self.source.by_doc[m['original_doc_id']]
                    entry.update(original_doc_id=m['original_doc_id'],original_text=original['content'],
                                 translation_model=m.get('translation_model',''))
                if tokens(evidence+[entry])>cfg['context_budget_tokens']:
                    warnings.append('근거 토큰 예산으로 일부 문서가 제외됐습니다.')
                    continue
                evidence.append(entry)
        evolution_available=sum(r['metadata']['kind']=='evolution_chain' for r in eligible)
        evolution_selected=sum(e['kind']=='evolution_chain' for e in evidence)
        if not blocked and evolution_available>evolution_selected:
            warnings.append('진화 체인의 일부 조건만 검색됐습니다. 전체 분기 목록으로 단정하지 않습니다.')
        diagnostics.update(evidence_tokens=tokens(evidence),external_evidence_count=len(evidence)-1,
                           embedding_calls=self.embedder.calls,embedding_cache_hits=self.embedder.hits)
        return {'selected_item_id':item_id,'selected_name':item['name_ko'],'evidence':evidence,
                'warnings':warnings,'diagnostics':diagnostics}
