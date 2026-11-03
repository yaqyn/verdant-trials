"""Qt workflow checks with real widgets and a headless-capable event loop."""
import os
import time
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

try:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None
else:
    from qt_app import QuestWindow


@unittest.skipIf(QApplication is None, 'Qt desktop dependencies are not installed')
class QuestWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = QuestWindow(seed=42, delay=1)
        self.window.show()
        self.application.processEvents()

    def tearDown(self):
        self.window.close()
        self.application.processEvents()

    def until(self, predicate):
        deadline = time.monotonic() + 5
        while not predicate() and time.monotonic() < deadline:
            self.application.processEvents()
            QTest.qWait(1)
        self.assertTrue(predicate(), 'Qt workflow did not finish within five seconds')

    def ready(self):
        self.window.skip_generation()
        self.assertEqual(self.window.phase, 'ready')

    def test_daylight_default_and_bundled_wallpaper(self):
        self.assertEqual(self.window.theme, 'light')
        self.assertEqual(self.window.board.mode, 'light')
        self.assertFalse(self.window.board._frame.isNull())
        self.assertEqual(self.window.theme_button.text(), 'Moonlight')

    def test_player_route_completes_quest_and_next_chapter(self):
        self.ready()
        window = self.window
        window.hint()
        self.assertEqual(window.hints, 1)
        route = window.maze.route_from((0, 0))
        directions = {(-1, 0): 'N', (1, 0): 'S', (0, -1): 'W', (0, 1): 'E'}
        for (r, c), (nr, nc) in zip(route, route[1:]):
            window.move(directions[nr-r, nc-c])
        self.assertEqual(window.phase, 'complete')
        self.assertEqual(window.player, route[-1])
        self.assertEqual(window.moves, len(route)-1)
        previous = window.maze
        window.next_level()
        self.ready()
        self.assertIsNot(window.maze, previous)
        self.assertGreater(window.maze.rows * window.maze.cols, previous.rows * previous.cols)

    def test_invalid_seed_keeps_current_board(self):
        self.ready()
        window = self.window
        maze = window.maze
        for raw in ('not-a-seed', '9' * 40):
            window.seed_input.setText(raw)
            self.assertFalse(window.new_maze())
            self.assertTrue(window.error_label.text())
            self.assertIs(window.maze, maze)
            self.assertEqual(window.phase, 'ready')
        window.seed_input.setText('123')
        window.new_maze()
        self.ready()
        self.assertEqual(window.maze.seed, 123)

    def test_invalid_seed_rolls_back_chapter_selection(self):
        self.ready()
        window = self.window
        maze = window.maze
        chapter = window.level_index
        window.seed_input.setText('invalid')
        window.chapter_box.setCurrentIndex(chapter + 1)
        self.assertIs(window.maze, maze)
        self.assertEqual(window.level_index, chapter)
        self.assertEqual(window.chapter_box.currentIndex(), chapter)
        self.assertTrue(window.error_label.text())

    def test_reduced_motion_settles_player_immediately(self):
        self.ready()
        window = self.window
        route = window.maze.route_from((0, 0))
        r, c = route[1]
        window.move('S' if r == 1 else 'E')
        window.reduced_motion.setChecked(True)
        self.assertTrue(window.board.reduced_motion)
        self.assertEqual(window.board.visualPosition.x(), c)
        self.assertEqual(window.board.visualPosition.y(), r)
        # Further movement must continue snapping to the actual cell.
        r, c = route[2]
        pr, pc = route[1]
        direction = {(-1, 0): 'N', (1, 0): 'S', (0, -1): 'W', (0, 1): 'E'}[r-pr, c-pc]
        window.move(direction)
        self.assertEqual(window.board.visualPosition.x(), c)
        self.assertEqual(window.board.visualPosition.y(), r)

    def test_pause_step_restart_and_close_stop_timer(self):
        window = self.window
        window.toggle_pause()
        self.assertTrue(window.paused)
        self.assertFalse(window.timer.isActive())
        before = sum(len(cell.walls) for row in window.maze.grid for cell in row)
        window.single_step()
        after = sum(len(cell.walls) for row in window.maze.grid for cell in row)
        self.assertLess(after, before)
        self.assertTrue(window.paused)
        original = window.maze
        window.new_maze()
        self.assertIsNot(window.maze, original)
        self.assertFalse(window.paused)
        self.assertTrue(window.timer.isActive())
        window.close()
        self.assertFalse(window.timer.isActive())

    def test_searches_complete_and_mode_switch_cancels_timer(self):
        self.ready()
        window = self.window
        window.set_mode('Observe')
        for index in (0, 1):
            window.algorithm_box.setCurrentIndex(index)
            window.run_search()
            window.toggle_pause()
            for _ in range(window.maze.rows * window.maze.cols * 3):
                if window.phase == 'complete':
                    break
                window._advance()
            self.assertEqual(window.phase, 'complete')
            self.assertTrue(window.maze.solved)
            self.assertEqual(window.overlay, window.maze.path)
            self.assertGreater(window.visits, 0)
            self.assertFalse(window.timer.isActive())
        window.set_mode('Play')
        self.assertEqual(window.phase, 'ready')
        self.assertEqual(window.player, (0, 0))
        window.set_mode('Observe')
        window.run_search()
        self.assertTrue(window.timer.isActive())
        window.set_mode('Play')
        self.assertEqual(window.phase, 'ready')
        self.assertFalse(window.timer.isActive())

    def test_theme_switch_preserves_board_and_paused_step(self):
        window = self.window
        window.toggle_pause()
        maze = window.maze
        player = window.player
        for theme in ('light', 'dark'):
            window.change_theme(theme)
            self.assertEqual(window.theme, theme)
            self.assertIs(window.maze, maze)
            self.assertEqual(window.player, player)
            self.assertTrue(window.paused)
            self.assertFalse(window.timer.isActive())
        self.ready()
        self.assertEqual(window.phase, 'ready')
        self.assertFalse(window.paused)

    def test_board_keyboard_moves_and_respects_walls(self):
        self.ready()
        window = self.window
        self.assertEqual(window.player, (0, 0))
        window.board.setFocus()
        QTest.keyClick(window.board, Qt.Key.Key_Up)
        self.assertEqual(window.player, (0, 0))
        route = window.maze.route_from((0, 0))
        r, c = route[1]
        key = Qt.Key.Key_Down if r == 1 else Qt.Key.Key_Right
        QTest.keyClick(window.board, key)
        self.assertEqual(window.player, route[1])
        self.assertEqual(window.moves, 1)
