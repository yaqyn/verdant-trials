"""Desktop workflow tests using a real Tk event loop when a display is available."""
import time
from types import SimpleNamespace
import unittest

try:
    import tkinter as tk
    from app import MazeApp
except ImportError:
    tk = None


@unittest.skipIf(tk is None, "Tkinter is not installed")
class AppTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f'Desktop display unavailable: {exc}')
        self.app = MazeApp(self.root, seed=42, delay=1)
        self.app.speed.set('Instant')
        self.root.update_idletasks()

    def tearDown(self):
        if hasattr(self, 'app') and not self.app.closed:
            self.app.close()

    def until(self, predicate):
        deadline = time.monotonic() + 5
        while not predicate() and time.monotonic() < deadline:
            self.root.update()
        self.assertTrue(predicate(), 'Desktop operation did not finish within five seconds')

    def ready(self):
        self.until(lambda: self.app.phase == 'ready')

    def test_pause_single_step_resume_and_restart(self):
        app = self.app
        app.toggle_pause()
        self.assertTrue(app.paused)
        self.assertIsNone(app.job)
        before = sum(len(cell.walls) for row in app.maze.grid for cell in row)
        app.single_step()
        after = sum(len(cell.walls) for row in app.maze.grid for cell in row)
        self.assertLess(after, before)
        self.assertTrue(app.paused)
        self.assertIsNone(app.job)
        app.toggle_pause()
        self.ready()
        old_maze = app.maze
        app.new_maze()
        self.assertIsNot(app.maze, old_maze)
        self.ready()
        self.assertEqual(app.moves, 0)
        self.assertEqual(app.player, (0, 0))

    def test_invalid_seed_preserves_current_maze(self):
        self.ready()
        app = self.app
        old_maze = app.maze
        for invalid in ('not a number', '9' * 21):
            app.seed.set(invalid)
            app.new_maze()
            self.assertTrue(app.error.get())
            self.assertIs(app.maze, old_maze)
            self.assertEqual(app.phase, 'ready')
        app.seed.set('123')
        app.new_maze()
        self.assertEqual(app.error.get(), '')
        self.ready()
        self.assertEqual(app.active_seed, 123)

    def test_player_can_follow_hint_route_and_complete_level(self):
        self.ready()
        app = self.app
        app.hint()
        self.assertEqual(app.hints, 1)
        self.assertEqual(len(app.overlay), 2)
        route = app.maze.route_from((0, 0))
        self.root.focus_force()
        keys = {(-1, 0): 'Up', (1, 0): 'Down', (0, -1): 'Left', (0, 1): 'Right'}
        for (r, c), (nr, nc) in zip(route, route[1:]):
            app._key(SimpleNamespace(keysym=keys[nr-r, nc-c]))
        self.assertEqual(app.phase, 'complete')
        self.assertEqual(app.player, route[-1])
        self.assertEqual(app.moves, len(route)-1)
        self.assertIn('found the exit', app.status.get())
        old_level = app.level_index
        app.next_level()
        self.assertEqual(app.level_index, old_level+1)
        self.ready()

    def test_both_searches_complete_and_mode_switch_cancels_work(self):
        self.ready()
        app = self.app
        app.mode.set('Observe')
        app._mode_changed()
        for algorithm in ('Depth-first search', 'Breadth-first search'):
            app.algorithm.set(algorithm)
            app.run_search()
            self.until(lambda: app.phase == 'complete')
            self.assertTrue(app.maze.solved)
            self.assertEqual(app.overlay, app.maze.path)
            self.assertGreater(app.visits, 0)
            self.assertIsNone(app.job)
            app._mode_changed()
        app.speed.set('Slow')
        app.run_search()
        self.assertIsNotNone(app.job)
        app.mode.set('Play')
        app._mode_changed()
        self.assertEqual(app.phase, 'ready')
        self.assertIsNone(app.job)
        self.assertEqual(app.player, (0, 0))

    def test_close_cancels_animation_callback(self):
        self.assertIsNotNone(self.app.job)
        self.app.close()
        self.assertTrue(self.app.closed)
        self.assertIsNone(self.app.job)


if __name__ == '__main__':
    unittest.main()
