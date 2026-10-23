"""Korean official terminology must be scoped, conservative and idempotent."""
import unittest

from scripts.pokemon_korean_terms import apply_terms, verified_mentions


class KoreanTermContracts(unittest.TestCase):
    def test_historical_aliases_use_korean_names(self):
        text, changes = apply_terms({'item_id': 'pokemon-species:1007', 'content': 'Winged King'}, '날개 달린 왕인 듯하다.')
        self.assertEqual(text, '날개의왕인 듯하다.')
        self.assertEqual(changes[0]['korean'], '날개의왕')
        text, _ = apply_terms({'item_id': 'pokemon-species:1008', 'content': 'Iron Serpent'}, '무쇠 이무기라고 전해진다.')
        self.assertEqual(text, '무쇠이무기라고 전해진다.')

    def test_component_names_are_not_translated_as_generic_worms(self):
        source = {'item_id': 'pokemon-species:1011', 'content': 'fore-wyrm and core-wyrm'}
        result, changes = apply_terms(source, '앞쪽 벌레의 머리와 속의 벌레의 꼬리다.')
        self.assertEqual(result, '외미르의 머리와 내미르의 꼬리다.')
        self.assertEqual(len(changes), 2)

    def test_does_not_insert_terms_absent_from_source(self):
        source = {'item_id': 'pokemon-species:1007', 'content': 'It resembles Cyclizar.'}
        text, changes = apply_terms(source, '날개 달린 왕과 비슷하다.')
        self.assertEqual(text, '날개 달린 왕과 비슷하다.')
        self.assertEqual(changes, [])

    def test_does_not_change_another_species_alias(self):
        source = {'item_id': 'pokemon-species:1', 'content': 'Winged King'}
        self.assertEqual(apply_terms(source, '날개 달린 왕')[0], '날개 달린 왕')

    def test_region_name_normalization_is_idempotent(self):
        source = {'item_id': 'pokemon-species:912', 'content': 'Paldean dishes in Paldea'}
        first, _ = apply_terms(source, '팔데아의 전통 요리다.')
        self.assertEqual(first, '팔데아지방의 전통 요리다.')
        self.assertEqual(apply_terms(source, first), (first, []))

    def test_already_correct_term_is_verified_without_change(self):
        source = {'item_id': 'pokemon-species:1024', 'content': 'Terastal phenomenon'}
        text, changes = apply_terms(source, '테라스탈 현상이다.')
        self.assertEqual(changes, [])
        self.assertEqual(verified_mentions(source, text)[0]['korean'], '테라스탈')

    def test_region_expansion_adjusts_korean_particles(self):
        source = {'item_id': 'pokemon-species:912', 'content': 'Paldea'}
        self.assertEqual(apply_terms(source, '팔데아로 이주했다.')[0], '팔데아지방으로 이주했다.')
        self.assertEqual(apply_terms(source, '팔데아는 넓다.')[0], '팔데아지방은 넓다.')


if __name__ == '__main__':
    unittest.main()
