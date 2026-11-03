"""Asset rendering checks without a display dependency."""
import unittest
from pathlib import Path
from art import ASSETS, draw_svg, wall


class RecordingCanvas:
    def __init__(self):
        self.items = []

    def __getattr__(self, name):
        if not name.startswith('create_'):
            raise AttributeError(name)
        def create(*coords, **options):
            self.items.append((name, coords, options))
            return len(self.items)
        return create


class ArtTests(unittest.TestCase):
    def test_all_bundled_vectors_draw_within_requested_bounds(self):
        for path in ASSETS.rglob('*.svg'):
            with self.subTest(path=path.name):
                canvas = RecordingCanvas()
                result = draw_svg(canvas, str(path.relative_to(ASSETS)), 10, 20, 64, 64)
                self.assertTrue(result)
                for _, coords, options in canvas.items:
                    self.assertTrue(all(9.99 <= value <= 74.01 for value in coords[::2]))
                    self.assertTrue(all(19.99 <= value <= 84.01 for value in coords[1::2]))
                    self.assertEqual(options['tags'], 'art')

    def test_wall_orientations_and_theme_palette(self):
        canvas = RecordingCanvas()
        horizontal = wall(canvas, 0, 4, 64, 4, 8, palette={'stone': '#abcdef'})
        self.assertEqual(len(horizontal), 6)
        self.assertEqual(canvas.items[1][2]['fill'], '#abcdef')
        vertical = wall(canvas, 4, 0, 4, 64, 8)
        self.assertEqual(len(vertical), 6)
        with self.assertRaises(ValueError):
            wall(canvas, 0, 0, 10, 10, 2)

    def test_rejects_non_project_assets(self):
        with self.assertRaises(ValueError):
            draw_svg(RecordingCanvas(), '../main.py', 0, 0, 24, 24)


if __name__ == '__main__':
    unittest.main()
