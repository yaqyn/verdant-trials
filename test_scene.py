"""Scene behavior: time-of-day, exploration controls, and effect lifecycle."""
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
try:
    from PySide6.QtCore import QTimer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None
else:
    from qt_app import QuestWindow


@unittest.skipIf(QApplication is None, 'Qt desktop dependencies are not installed')
class SceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = QuestWindow(seed=42, delay=180)
        self.window.show()
        self.application.processEvents()

    def tearDown(self):
        self.window.close()
        self.application.processEvents()

    def test_lighting_modes_use_distinct_wallpapers_without_reset(self):
        self.window.skip_generation()
        board = self.window.board
        maze = board.maze
        day = board._frame.toImage()
        self.assertFalse(day.isNull())
        self.window.change_theme('dark')
        night = board._frame.toImage()
        self.assertFalse(night.isNull())
        self.assertNotEqual(day, night)
        self.assertIs(board.maze, maze)
        self.window.change_theme('light')
        self.assertEqual(day, board._frame.toImage())

    def test_exploration_controls_are_passed_to_scene_and_observe_shows_full_map(self):
        self.window.skip_generation()
        board = self.window.board
        calls = []
        original = board.configure_scene
        def capture(**kwargs):
            calls.append(kwargs)
            return original(**kwargs)
        board.configure_scene = capture
        self.window.fog_checkbox.setChecked(False)
        self.assertFalse(calls[-1]['fog_enabled'])
        self.window.fog_checkbox.setChecked(True)
        self.window.ambient_checkbox.setChecked(False)
        self.assertTrue(calls[-1]['fog_enabled'])
        self.assertFalse(calls[-1]['ambient_motion'])
        self.window.set_mode('Observe')
        self.assertFalse(calls[-1]['play_mode'])
        self.assertFalse(self.window.fog_checkbox.isEnabled())
        self.window.set_mode('Play')
        self.assertTrue(calls[-1]['play_mode'])
        self.assertTrue(self.window.fog_checkbox.isEnabled())

    def test_lamps_and_discovery_wait_for_generation_then_reset_on_new_quest(self):
        window = self.window
        board = window.board
        self.assertEqual(board.lamps, [])
        self.assertEqual(board.discovered, set())
        window.chapter_box.setCurrentIndex(1)
        window.skip_generation()
        self.assertTrue(board.lamps)
        self.assertTrue(board.visible)
        self.assertTrue(board.visible <= board.discovered)
        initial = set(board.discovered)
        route = window.maze.route_from((0, 0))
        directions = {(-1, 0): 'N', (1, 0): 'S', (0, -1): 'W', (0, 1): 'E'}
        for (r, c), (nr, nc) in zip(route[:-2], route[1:-1]):
            window.move(directions[nr-r, nc-c])
        self.assertTrue(initial <= board.discovered)
        self.assertTrue(set(route[:-1]) <= board.discovered)
        self.assertGreater(len(board.discovered), len(initial))
        window.new_maze()
        self.assertEqual(board.discovered, set())
        self.assertEqual(board.lamps, [])
        self.assertFalse(board.scene_ready)

    def test_fog_really_obscures_unexplored_ground(self):
        window = self.window
        window.chapter_box.setCurrentIndex(1)
        window.skip_generation()
        board = window.board
        unknown = next((r, c) for r in range(window.maze.rows)
                       for c in range(window.maze.cols) if (r, c) not in board.discovered)
        _, floor, cell = board._geometry()
        row, col = unknown
        x = round(floor.left() + (col+.5)*cell)
        y = round(floor.top() + (row+.5)*cell)
        hidden = board.grab().toImage().pixelColor(x, y).lightness()
        window.fog_checkbox.setChecked(False)
        revealed = board.grab().toImage().pixelColor(x, y).lightness()
        self.assertGreater(revealed, hidden + 40)

    def test_ambient_timers_start_after_generation_and_stop_when_hidden(self):
        board = self.window.board
        effect_timers = lambda: board.findChildren(QTimer)
        self.assertFalse(any(timer.isActive() for timer in effect_timers()))

        self.window.skip_generation()
        self.application.processEvents()
        self.assertTrue(any(timer.isActive() for timer in effect_timers()))
        board.hide()
        self.application.processEvents()
        self.assertFalse(any(timer.isActive() for timer in effect_timers()))
        board.show()
        self.application.processEvents()
        self.assertTrue(any(timer.isActive() for timer in effect_timers()))
        self.window.reduced_motion.setChecked(True)
        self.application.processEvents()
        self.assertFalse(any(timer.isActive() for timer in effect_timers()))
        self.window.close()
        self.assertFalse(any(timer.isActive() for timer in effect_timers()))

    def test_guidance_overlap_does_not_cut_a_hole_in_visible_ground(self):
        from PySide6.QtGui import QImage, QPainter
        from PySide6.QtCore import Qt
        window = self.window
        window.skip_generation()
        board = window.board
        _, floor, cell = board._geometry()
        board.overlay = [(0, 0), (0, 0)]
        image = QImage(board.size(), QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        board._draw_fog(painter, floor, cell)
        painter.end()
        self.assertEqual(image.pixelColor(round(floor.left()+cell*.5),
                                          round(floor.top()+cell*.5)).alpha(), 0)
