"""Theme changes preserve shared tokens and readable widget states."""
import unittest
from pathlib import Path
from theme import COLORS, THEMES


class ThemeTests(unittest.TestCase):
    def test_bundled_artwork_and_font_are_present(self):
        root = Path(__file__).parent / 'assets'
        self.assertTrue((root / 'forest-frame.png').is_file())
        self.assertTrue((root / 'fonts/Cinzel.ttf').is_file())
        self.assertTrue((root / 'fonts/OFL-Cinzel.txt').is_file())

    def test_both_themes_supply_all_semantic_roles(self):
        for theme in THEMES.values():
            self.assertEqual(set(theme), set(COLORS))
            for value in theme.values():
                self.assertRegex(value, r'^#[0-9a-fA-F]{6}$')

    def test_reading_text_contrast(self):
        def luminance(hex_color):
            channels = [int(hex_color[i:i+2], 16) / 255 for i in (1, 3, 5)]
            channels = [v / 12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in channels]
            return sum(v*w for v, w in zip(channels, (.2126, .7152, .0722)))
        for name, theme in THEMES.items():
            for foreground, background in [('ink','background'),('muted','background'),
                                            ('ink','field'),('on_accent','accent')]:
                a, b = sorted([luminance(theme[foreground]), luminance(theme[background])])
                self.assertGreaterEqual((b+.05)/(a+.05), 4.5, (name, foreground, background))
