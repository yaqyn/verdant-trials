"""Subtle procedural ground remains deterministic and low contrast."""
import unittest


class GroundTests(unittest.TestCase):
    def test_texture_is_deterministic_and_quiet(self):
        try:
            from ground import texture
            image = texture(120, 90)
        except ImportError:
            self.skipTest('Pillow not installed')
        self.assertEqual(image.tobytes(), texture(120, 90).tobytes())
        self.assertEqual(image.size, (120, 90))
        for low, high in image.getextrema():
            self.assertLessEqual(high-low, 18)
