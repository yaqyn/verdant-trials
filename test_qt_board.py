"""Qt board rendering and wall-safe movement transitions."""
import os
import unittest

if not os.environ.get('DISPLAY') and not os.environ.get('WAYLAND_DISPLAY'):
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
try:
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from qt_board import MazeBoard, cover_source_rect
except ImportError:
    MazeBoard = None
from maze import Maze


@unittest.skipIf(MazeBoard is None, 'Qt is not installed')
class BoardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        self.board = MazeBoard()
        self.board.resize(800, 600)
        self.maze = Maze(4, 5, seed=42)
        list(self.maze.generate())
        self.state((0, 0))

    def tearDown(self):
        self.board.close()

    def state(self, player):
        self.board.set_state(self.maze, player, [], [], set(), set())

    def test_paint_cache_and_repeated_state(self):
        image = QImage(800, 600, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        self.board.render(image)
        self.assertFalse(self.board._static.isNull())
        first_key = self.board._static_key
        self.state((0, 0))
        self.board.render(image)
        self.assertEqual(first_key, self.board._static_key)
        self.assertNotEqual(image.pixelColor(400, 300).alpha(), 0)
        self.board.resize(650, 500)
        self.board.render(image)
        self.assertNotEqual(first_key, self.board._static_key)

    def test_cover_crop_keeps_uniform_scale_at_every_window_shape(self):
        for image_size in ((2560, 1440), (1536, 1024)):
            iw, ih = image_size
            for target in ((1600, 500), (600, 1000), (800, 800), (1920, 1080)):
                tw, th = target
                with self.subTest(image=image_size, target=target):
                    source = cover_source_rect(iw, ih, tw, th)
                    self.assertAlmostEqual(tw/source.width(), th/source.height())
                    self.assertAlmostEqual(source.center().x(), iw/2)
                    self.assertAlmostEqual(source.center().y(), ih/2)
                    self.assertGreaterEqual(source.left(), 0)
                    self.assertGreaterEqual(source.top(), 0)
                    self.assertLessEqual(source.right(), iw)
                    self.assertLessEqual(source.bottom(), ih)
                    self.assertTrue(abs(source.width()-iw) < .001 or
                                    abs(source.height()-ih) < .001)
        with self.assertRaises(ValueError):
            cover_source_rect(0, 100, 100, 100)

    def test_theme_repaints_floor_without_mutating_maze(self):
        image = QImage(800, 600, QImage.Format.Format_ARGB32)
        self.board.render(image)
        dark_key = self.board._static_key
        self.board.set_theme('light')
        self.board.render(image)
        self.assertNotEqual(dark_key, self.board._static_key)
        self.assertIs(self.board.maze, self.maze)
        _, area, size = self.board._geometry()
        interior = image.pixelColor(round(area.left()+size*.25), round(area.top()+size*.25))
        self.assertGreater(interior.lightness(), 100)

    def test_movement_animation_does_not_cut_corners(self):
        self.state((0, 1))
        self.board.visualPosition = QPointF(.5, 0)
        self.state((1, 1))
        self.assertEqual(self.board._animation.startValue(), QPointF(1, 0))
        self.state((3, 4))
        self.assertEqual(self.board.visualPosition, QPointF(4, 3))
        self.board.reduced_motion = True
        self.state((3, 3))
        self.assertEqual(self.board.visualPosition, QPointF(3, 3))

    def test_keys_emit_compass_directions(self):
        directions = []
        self.board.moved.connect(directions.append)
        QTest.keyClick(self.board, Qt.Key.Key_Up)
        QTest.keyClick(self.board, Qt.Key.Key_D)
        self.assertEqual(directions, ['N', 'E'])
