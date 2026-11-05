"""Behavior checks for maze generation and recursive solving."""

import unittest

from maze import Maze


DIRECTIONS = ((-1, 0, "N", "S"), (1, 0, "S", "N"),
              (0, -1, "W", "E"), (0, 1, "E", "W"))


class MazeTests(unittest.TestCase):
    def generated(self, rows=7, cols=9, seed=42):
        maze = Maze(rows=rows, cols=cols, seed=seed)
        list(maze.generate())
        return maze

    def signature(self, maze):
        return tuple(tuple(frozenset(cell.walls) for cell in row)
                     for row in maze.grid)

    def test_generation_makes_connected_tree_with_reciprocal_walls(self):
        maze = self.generated()
        rows, cols = len(maze.grid), len(maze.grid[0])
        passages = 0
        reached = {(0, 0)}
        pending = [(0, 0)]
        while pending:
            row, col = pending.pop()
            for dr, dc, wall, opposite in DIRECTIONS:
                nr, nc = row + dr, col + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    self.assertEqual(wall in maze.grid[row][col].walls,
                                     opposite in maze.grid[nr][nc].walls)
                    if wall not in maze.grid[row][col].walls:
                        passages += 1
                        if (nr, nc) not in reached:
                            reached.add((nr, nc))
                            pending.append((nr, nc))
        self.assertEqual(len(reached), rows * cols)
        self.assertEqual(passages // 2, rows * cols - 1)
        self.assertNotIn("N", maze.grid[0][0].walls)
        self.assertNotIn("S", maze.grid[-1][-1].walls)

    def test_seed_reproduces_layout(self):
        self.assertEqual(self.signature(self.generated(seed=17)),
                         self.signature(self.generated(seed=17)))

    def test_solver_returns_valid_route(self):
        maze = self.generated()
        list(maze.solve())
        self.assertTrue(maze.solved)
        self.assertEqual(maze.path[0], (0, 0))
        self.assertEqual(maze.path[-1], (6, 8))
        self.assertEqual(len(maze.path), len(set(maze.path)))
        for (row, col), (nr, nc) in zip(maze.path, maze.path[1:]):
            direction = next((wall for dr, dc, wall, _ in DIRECTIONS
                              if (row + dr, col + dc) == (nr, nc)), None)
            self.assertIsNotNone(direction)
            self.assertNotIn(direction, maze.grid[row][col].walls)

    def test_generation_and_solving_can_repeat(self):
        maze = self.generated()
        for _ in range(3):
            list(maze.solve())
            self.assertTrue(maze.solved)
            list(maze.generate())
        list(maze.solve())
        self.assertTrue(maze.solved)

    def test_single_cell(self):
        maze = self.generated(rows=1, cols=1)
        list(maze.solve())
        self.assertTrue(maze.solved)
        self.assertEqual(maze.path, [(0, 0)])

    def test_invalid_dimensions(self):
        for rows, cols in ((0, 3), (3, 0), (-1, 3), (3, -1), (1.5, 3), (3, True)):
            with self.subTest(rows=rows, cols=cols):
                with self.assertRaises(ValueError):
                    Maze(rows=rows, cols=cols)

    def test_ascii_map_shows_walls_route_and_openings(self):
        maze = self.generated(rows=2, cols=2, seed=7)
        route = maze.route_from((0, 0))
        drawing = maze.to_ascii(route)
        self.assertIn("S", drawing)
        self.assertIn("G", drawing)
        self.assertEqual(len(drawing.splitlines()), 5)
        with self.assertRaises(ValueError):
            maze.to_ascii([(2, 0)])


if __name__ == "__main__":
    unittest.main()
