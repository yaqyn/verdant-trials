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

    def test_personal_light_tracks_interpolated_position_and_keeps_feet_visible(self):
        from PySide6.QtCore import QPointF, Qt
        from PySide6.QtGui import QImage, QPainter
        self.window.skip_generation()
        board = self.window.board
        board.grab()
        _, floor, cell = board._geometry()
        route = self.window.maze.route_from((0, 0))
        r, c = route[1]
        # Logical destination differs from the intermediate rendered position.
        board.player = (r, c)
        for fraction in (.1, .35, .65, .9):
            board.visualPosition = QPointF(c*fraction, r*fraction)
            origin, polygons = board._player_light()
            self.assertAlmostEqual(origin[0], c*fraction+.5)
            self.assertAlmostEqual(origin[1], r*fraction+.5)
            image = QImage(board.size(), QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(image)
            board._draw_fog(painter, floor, cell)
            painter.end()
            center = board._point(origin, floor, cell)
            self.assertLess(image.pixelColor(round(center.x()), round(center.y())).alpha(), 3)

    def test_personal_light_fades_gradually_and_stops_at_solid_wall(self):
        from maze import Maze
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QImage, QPainter
        board = self.window.board
        maze = Maze(1, 5)
        for col in range(2):
            maze.grid[0][col].walls.remove('E')
            maze.grid[0][col+1].walls.remove('W')
        board.configure_scene(True, True)
        board.set_state(maze,(0,0),[],[],set(),set())
        board.grab()
        _, floor, cell = board._geometry()
        image = QImage(board.size(), QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        board._draw_fog(painter,floor,cell)
        painter.end()
        alpha = lambda x: image.pixelColor(round(floor.left()+x*cell), round(floor.center().y())).alpha()
        self.assertLess(alpha(.5), 3)
        self.assertLess(alpha(1.5), alpha(2.5))
        self.assertGreater(alpha(3.5), 235)

    def test_unexplored_fog_is_opaque_and_stable_when_idle(self):
        from PySide6.QtGui import QImage, QPainter
        from PySide6.QtCore import Qt
        self.window.chapter_box.setCurrentIndex(4)
        self.window.skip_generation()
        board = self.window.board
        board.grab()
        _, floor, cell = board._geometry()
        image = QImage(board.size(), QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        board._draw_fog(painter,floor,cell)
        painter.end()
        # Even wall tops in far unexplored regions must be completely hidden.
        pixel = image.pixelColor(round(floor.right()-cell*2),round(floor.bottom()-cell*2))
        self.assertEqual(pixel.alpha(),255)
        self.assertEqual((pixel.red(),pixel.green(),pixel.blue()),(12,20,23))
        cached = board._fog_image.cacheKey()
        board.grab()
        self.assertEqual(board._fog_image.cacheKey(),cached)

    def test_memory_records_soft_visibility_instead_of_uniform_cells(self):
        from maze import Maze
        board = self.window.board
        maze = Maze(1,5)
        for col in range(4):
            maze.grid[0][col].walls.remove('E')
            maze.grid[0][col+1].walls.remove('W')
        board.configure_scene(True,True)
        board.set_state(maze,(0,0),[],[],set(),set())
        board.grab()
        memory = board._fog_memory
        # Three points within the same cell retain different fog strengths.
        samples = [memory.pixelColor(round(2+x*12),8).red() for x in (2.1,2.5,2.9)]
        self.assertLess(samples[0],samples[1])
        self.assertLess(samples[1],samples[2])
        first = memory.copy()
        board.set_state(maze,(0,0),[],[],set(),set())
        board.grab()
        self.assertEqual(first,board._fog_memory)

    def test_idle_light_only_repaints_when_opacity_changes(self):
        self.window.skip_generation()
        board = self.window.board
        board._scene_started -= 4
        calls = []
        board.update = lambda *args: calls.append(True)
        board._ambient_tick()
        first = len(calls)
        board._ambient_tick()
        self.assertEqual(len(calls),first)
