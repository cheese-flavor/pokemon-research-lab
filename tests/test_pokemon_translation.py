"""Translation safety contracts without model calls or credentials."""
import unittest

from scripts.translate_pokemon_descriptions import apply_fidelity_corrections, apply_verified_terms, glossary_for, select_targets, validate_response
from scripts.review_pokemon_translation import audit


class TranslationContracts(unittest.TestCase):
    def test_preserves_already_available_korean(self):
        items = [{'item_id': 'a', 'generation': 'generation-viii'}, {'item_id': 'b', 'generation': 'generation-ix'}]
        docs = [{'item_id': 'a', 'kind': 'species_description', 'language': 'ko'},
                {'item_id': 'a', 'kind': 'species_description', 'language': 'en'},
                {'item_id': 'b', 'kind': 'species_description', 'language': 'en'}]
        before, missing, targets = select_targets(items, docs)
        self.assertEqual(before, {'a'})
        self.assertEqual(missing, {'b'})
        self.assertEqual([d['item_id'] for d in targets], ['b'])

    def test_rejects_mixed_or_missing_version_ids(self):
        rows = [{'source_doc_id': 'red', 'english': 'sample'}, {'source_doc_id': 'blue', 'english': 'sample'}]
        with self.assertRaises(ValueError):
            validate_response(rows, {'entries': [{'source_doc_id': 'red', 'translation': '설명'}]})

    def test_rejects_numeric_omission(self):
        with self.assertRaisesRegex(ValueError, 'numeric'):
            validate_response([{'source_doc_id': 'a', 'english': '100 years'}],
                              {'entries': [{'source_doc_id': 'a', 'translation': '오랫동안'}]})

    def test_glossary_recognizes_species_name_with_spaces(self):
        result = glossary_for('Great Tusk lives in Paldea.', [{'name': 'great-tusk', 'name_ko': '위대한엄니'}])
        self.assertEqual(result['great-tusk'], '위대한엄니')
        self.assertEqual(result['Paldea'], '팔데아')

    def test_number_substring_is_not_numeric_equivalence(self):
        with self.assertRaisesRegex(ValueError, 'numeric'):
            validate_response([{'source_doc_id': 'a', 'english': '100 years'}],
                              {'entries': [{'source_doc_id': 'a', 'translation': '1000년'}]})

    def test_korean_ten_thousand_unit_preserves_value(self):
        result = validate_response([{'source_doc_id': 'a', 'english': '10,000 years'}],
                                   {'entries': [{'source_doc_id': 'a', 'translation': '1만 년'}]})
        self.assertEqual(result['a']['translation'], '1만 년')

    def test_enrichment_audit_rejects_overwritten_original(self):
        items = [{'item_id': 'a', 'generation': 'generation-ix'}]
        source = {'item_id': 'a', 'doc_id': 'source', 'kind': 'species_description', 'language': 'en',
                  'version': 'example', 'source_url': 'example', 'source_revision': 'test', 'content': 'sample'}
        translation = {**source, 'doc_id': 'ko', 'original_doc_id': 'source', 'original_content': 'sample',
                       'language': 'ko', 'content': '예시', 'is_machine_translation': True, 'source_type': 'machine_translation',
                       'translation_model': 'gpt-6.1-sol', 'translation_response_model': 'gpt-6.1-sol',
                       'review_notes': [], 'verified_terminology_corrections': [], 'fidelity_corrections': [], 'human_reviewed': False}
        summary = audit(items, [source], [source, translation], [translation])
        self.assertEqual(summary['remaining_missing_species'], 0)
        with self.assertRaisesRegex(ValueError, 'Original corpus altered'):
            audit(items, [source], [{**source, 'content': 'changed'}, translation], [translation])

    def test_official_terminology_correction_is_scoped(self):
        source = {'item_id': 'pokemon-species:920', 'content': 'Showdown Mode'}
        text, changes = apply_verified_terms(source, '승부모드로 변한다.')
        self.assertEqual(text, '결전 모드로 변한다.')
        self.assertEqual(len(changes), 1)
        untouched, changes = apply_verified_terms({**source, 'item_id': 'other'}, '승부모드로 변한다.')
        self.assertEqual(untouched, '승부모드로 변한다.')
        self.assertEqual(changes, [])

    def test_fidelity_correction_does_not_narrow_ambiguous_pronoun(self):
        source = {'item_id': 'pokemon-species:906', 'version': 'scarlet', 'doc_id': 'sample'}
        text, changes = apply_fidelity_corrections(source, '얼굴이 마르지 않도록 자주 세수한다.')
        self.assertEqual(text, '마르지 않도록 자주 세수한다.')
        self.assertEqual(len(changes), 1)


if __name__ == '__main__':
    unittest.main()
