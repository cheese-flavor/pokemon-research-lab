"""Search a pinned external-source catalogue, using verified local source caches."""
import csv
import hashlib
import json
import re
from pathlib import Path

from .data import fingerprint
from .embeddings import write_json


class SourceCatalogue:
    def __init__(self, root, corpus_path, cache_path, offline=False):
        self.root, self.cache = Path(root), Path(cache_path)
        self.items = json.loads((self.root/'dataset/pokemon/items.json').read_text(encoding='utf-8'))
        self.by_item = {i['item_id']: i for i in self.items}
        self.docs = json.loads(Path(corpus_path).read_text(encoding='utf-8'))
        self.by_doc = {d['doc_id']: d for d in self.docs}
        if len(self.by_doc) != len(self.docs):
            raise ValueError('Duplicate source document IDs')
        revisions = {i['source_revision'] for i in self.items} | {d['source_revision'] for d in self.docs}
        if len(revisions) != 1:
            raise ValueError('Mixed source snapshots')
        self.revision = revisions.pop()
        self.raw = self.root/'dataset/pokemon/raw'/('bulk_' + self.revision)
        self.source_requests = 0
        if not (self.raw/'sources.json').exists() or len(list(self.raw.glob('*.csv'))) != 20:
            from scripts.collect_pokemon_bulk import load_tables
            _, _, self.source_requests = load_tables(self.raw, offline)
        sources = json.loads((self.raw/'sources.json').read_text(encoding='utf-8'))
        self.source_urls = {name: value['source_url'] for name,value in sources.items()}
        for name, source in sources.items():
            if hashlib.sha256((self.raw/(name+'.csv')).read_bytes()).hexdigest() != source['sha256']:
                raise ValueError('Pinned external source cache corrupted')
        urls = {s['source_url'] for s in sources.values()}
        for doc in self.docs:
            if doc['item_id'] not in self.by_item or doc['source_url'] not in urls or not doc['content'].strip():
                raise ValueError('Invalid document source linkage')
        self.version_groups = {r['identifier']: r['version_group_id'] for r in self.rows('versions')}
        self.versions = sorted(self.version_groups)
        self.signature = fingerprint([self.revision, hashlib.sha256(Path(corpus_path).read_bytes()).hexdigest(),
                                      fingerprint(self.items), 'catalogue-v1'])
        self.searches = self.hits = 0

    def rows(self, name):
        with (self.raw/(name+'.csv')).open(encoding='utf-8', newline='') as handle:
            return list(csv.DictReader(handle))

    def resolve(self, name):
        matches = [i for i in self.items if str(name).strip().casefold() in
                   (str(i['species_id']), i['item_id'], i['name'].casefold(), i['name_ko'].casefold())]
        if len(matches) != 1:
            raise ValueError('Choose one exact Pokemon name or species number')
        return matches[0]

    def own(self, item_id):
        docs = [d for d in self.docs if d['item_id'] == item_id]
        if not any(d['kind'] == 'species_description' for d in docs):
            raise ValueError('Own species description missing')
        return docs

    def search(self, item, queries, kinds, version, limit):
        key = fingerprint([self.signature, item['item_id'], queries, kinds, version, limit])
        path = self.cache/(key+'.json')
        if path.exists():
            cached = json.loads(path.read_text(encoding='utf-8'))
            if cached['key'] != key or fingerprint(cached['doc_ids']) != cached['ids_hash']:
                raise ValueError('Source search cache corrupted')
            self.hits += 1
            return [self.by_doc[d] for d in cached['doc_ids']]
        related = {item['item_id']}
        for doc in self.own(item['item_id']):
            if doc['kind'] == 'evolution_chain':
                for edge in json.loads(doc['content'])['edges']:
                    related.update(f'pokemon-species:{edge[k]}' for k in ('from_species_id', 'to_species_id'))
        joined = ' '.join(queries).casefold()
        for other in self.items:
            if any(n and n.casefold() in joined for n in (other['name'], other['name_ko'])):
                related.add(other['item_id'])
        words = set(re.findall(r'[가-힣a-z0-9-]{2,}', joined))
        ranked = []
        for doc in self.docs:
            if doc['item_id'] not in related:
                continue
            score = (doc['kind'] in kinds) * 10 + (doc['language'] == 'ko') * 3
            score += sum(w in (doc['title']+' '+doc['content'][:220]).casefold() for w in words)
            score += (doc['version'] == version) * 20 if version else 0
            score += doc['item_id'] != item['item_id']
            ranked.append((-score, doc['doc_id'], doc))
        ranked.sort(key=lambda row: row[:2])
        result = [r[2] for r in ranked[:limit]]
        write_json(path, {'key': key, 'doc_ids': [d['doc_id'] for d in result],
                          'ids_hash': fingerprint([d['doc_id'] for d in result]), 'source_revision': self.revision})
        self.searches += 1
        return result
