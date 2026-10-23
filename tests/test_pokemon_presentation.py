import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.pokemon.ui_theme import artwork, badges


class ArtworkContracts(unittest.TestCase):
    def test_unknown_species_is_explicit_missing_not_another_species(self):
        with TemporaryDirectory() as folder:
            uri, kind, url = artwork(folder, 999)
            self.assertEqual((uri, kind, url), ('', 'missing', ''))

    def test_source_cache_cannot_escape_artwork_directory(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            directory = root/'dataset/pokemon/artwork'
            directory.mkdir(parents=True)
            (root/'private.png').write_bytes(b'PRIVATE_SENTINEL')
            (directory/'manifest.json').write_text(json.dumps({'images': {'4': {
                'status': 'available', 'path': 'private.png', 'source_url': 'https://example.org'}}}))
            self.assertEqual(artwork(root, 4)[1], 'missing')

    def test_external_display_labels_are_escaped(self):
        result = badges(['<script>alert(1)</script>'])
        self.assertNotIn('<script>', result)
        self.assertIn('&lt;script&gt;', result)


if __name__ == '__main__':
    unittest.main()
