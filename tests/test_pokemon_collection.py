"""Data contracts: linkage, version isolation, and offline cache behavior."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.collect_pokemon import Client, document, evolution_edges, validate
from scripts.collect_pokemon_bulk import load_tables


class CollectionContracts(unittest.TestCase):
    def test_each_item_requires_own_description(self):
        items = [{'item_id': 'species:1', 'name_ko': '테스트'}]
        with self.assertRaisesRegex(ValueError, 'own description'):
            validate(items, [], 1)

    def test_version_and_item_are_part_of_document_identity(self):
        source = {'source_url': 'https://pokeapi.co/api/v2/pokemon-species/1/', 'fetched_at': 'test'}
        a = document('species:1', 'species_description', source, 'title', 'same text', 'ko', 'red')
        b = document('species:1', 'species_description', source, 'title', 'same text', 'ko', 'blue')
        c = document('species:2', 'species_description', source, 'title', 'same text', 'ko', 'red')
        self.assertEqual(len({a['doc_id'], b['doc_id'], c['doc_id']}), 3)

    def test_evolution_preserves_branch_conditions(self):
        tree = {'species': {'name': 'root'}, 'evolves_to': [
            {'species': {'name': 'branch-a'}, 'evolution_details': [{'min_level': 20}], 'evolves_to': []},
            {'species': {'name': 'branch-b'}, 'evolution_details': [{'item': {'name': 'stone'}}], 'evolves_to': []}]}
        edges = evolution_edges(tree)
        self.assertEqual([e['to'] for e in edges], ['branch-a', 'branch-b'])
        self.assertEqual(edges[1]['conditions'][0]['item']['name'], 'stone')

    def test_cached_resource_works_without_network(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            client = Client(directory, delay=0)
            with patch('urllib.request.urlopen') as request:
                request.return_value.__enter__.return_value.read.return_value = b'{"id": 1}'
                first = client.get('https://pokeapi.co/api/v2/type/1/')
            offline = Client(directory, offline=True)
            with patch('urllib.request.urlopen', side_effect=AssertionError('Network must not be used')):
                self.assertEqual(offline.get(first['source_url']), first)
                with self.assertRaises(FileNotFoundError):
                    offline.get('https://pokeapi.co/api/v2/type/2/')
            self.assertEqual(offline.requests, 0)

    def test_bulk_offline_cache_verifies_checksum_without_network(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            raw = b'id,identifier\n1,example\n'
            (directory / 'sample.csv').write_bytes(raw)
            (directory / 'sources.json').write_text(json.dumps({'sample': {'sha256': hashlib.sha256(raw).hexdigest()}}))
            with patch('scripts.collect_pokemon_bulk.FILES', ['sample']), patch('urllib.request.urlopen', side_effect=AssertionError('No network')):
                tables, _, requests = load_tables(directory, True)
            self.assertEqual(tables['sample'][0]['identifier'], 'example')
            self.assertEqual(requests, 0)

    def test_bulk_rejects_corrupted_cache(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / 'sample.csv').write_bytes(b'changed data')
            (directory / 'sources.json').write_text(json.dumps({'sample': {'sha256': 'wrong'}}))
            with patch('scripts.collect_pokemon_bulk.FILES', ['sample']):
                with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                    load_tables(directory, True)


if __name__ == '__main__':
    unittest.main()
