"""Search guarantees, hints, and level-scale model behavior."""
import unittest
from maze import Maze
from levels import LEVELS


class EngineTests(unittest.TestCase):
    def test_largest_level_without_recursion_limit(self):
        level = LEVELS[-1]
        maze = Maze(level.rows, level.cols, seed=12)
        self.assertEqual(len(list(maze.generate())), level.rows * level.cols)
        for algorithm in ('dfs', 'bfs'):
            list(maze.solve(algorithm))
            self.assertTrue(maze.solved)
            self.assertEqual(maze.path, maze.route_from((0, 0)))

    def test_bfs_shortest_route_with_cycles(self):
        maze = Maze(3, 3)
        for row in maze.grid:
            for cell in row:
                cell.walls.clear()
        list(maze.solve('bfs'))
        self.assertTrue(maze.solved)
        self.assertEqual(len(maze.path), 5)

    def test_hints_do_not_mutate_solver(self):
        maze = Maze(10, 12, seed=2)
        list(maze.generate())
        list(maze.solve())
        original = maze.path.copy()
        route = maze.route_from((3, 4))
        self.assertEqual(route[0], (3, 4))
        self.assertEqual(route[-1], (9, 11))
        self.assertEqual(maze.path, original)
        self.assertTrue(maze.solved)
        for a, b in zip(route, route[1:]):
            direction = next(d for r, c, d in maze.neighbors(*a) if (r, c) == b)
            self.assertTrue(maze.can_move(a, direction))

    def test_boundaries_and_reciprocal_passages(self):
        maze = Maze(2, 2)
        maze.grid[0][0].walls.remove('E')
        self.assertFalse(maze.can_move((0, 0), 'E'))
        maze.grid[0][1].walls.remove('W')
        self.assertTrue(maze.can_move((0, 0), 'E'))
        self.assertFalse(maze.can_move((0, 0), 'N'))
        self.assertFalse(maze.can_move((-1, 0), 'S'))
        self.assertFalse(maze.can_move((0, 0), 'unknown'))
        with self.assertRaises(ValueError):
            maze.route_from((2, 0))

    def test_unsolvable_and_invalid_algorithm(self):
        maze = Maze(2, 2)
        for strategy in ('dfs', 'bfs'):
            events = list(maze.solve(strategy))
            self.assertFalse(maze.solved)
            self.assertEqual(maze.path, [])
            self.assertEqual(events[-1], ('done', (0, 0)))
        with self.assertRaises(ValueError):
            list(maze.solve('random'))

    def test_metrics_and_progression(self):
        self.assertEqual(len(LEVELS), 5)
        self.assertEqual([level.id for level in LEVELS], list(range(1, 6)))
        areas = [level.rows * level.cols for level in LEVELS]
        self.assertEqual(areas, sorted(set(areas)))
        maze = Maze(1, 3, seed=1)
        list(maze.generate())
        self.assertEqual(maze.metrics(), {'cells': 3, 'dead_ends': 2, 'junctions': 0})


if __name__ == '__main__':
    unittest.main()
