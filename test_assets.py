"""Bundled quest art stays self-contained and editable."""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


class AssetTests(unittest.TestCase):
    def test_original_illustration_and_licensed_font_are_bundled(self):
        assets = Path(__file__).parent / 'assets'
        self.assertGreater((assets / 'verdant-world.png').stat().st_size, 100_000)
        self.assertGreater((assets / 'fonts/Cinzel.ttf').stat().st_size, 10_000)
        self.assertIn('SIL OPEN FONT LICENSE', (assets / 'fonts/OFL-Cinzel.txt').read_text())

    def test_vectors_are_self_contained(self):
        for path in (Path(__file__).parent / 'assets').rglob('*.svg'):
            with self.subTest(asset=path.name):
                root = ET.parse(path).getroot()
                self.assertIn('viewBox', root.attrib)
                for node in root.iter():
                    self.assertFalse(node.tag.endswith('script'))
                    for key, value in node.attrib.items():
                        if key.endswith('href'):
                            self.assertTrue(value.startswith('#'))
