"""Physical visibility and deterministic lamp placement checks."""
import math
import unittest
from lighting import (lamp_positions, line_of_sight, visibility_polygon,
                      visible_cells, wall_segments)
from maze import Maze


class LightingTests(unittest.TestCase):
    def test_closed_wall_blocks_but_doorway_transmits_light(self):
        wall = ((1, 0, 1, 2),)
        self.assertFalse(line_of_sight((.5,.5), (1.5,.5), wall))
        doorway = ((1,0,1,.25),(1,.75,1,2))
        self.assertTrue(line_of_sight((.5,.5), (1.5,.5), doorway))
        self.assertFalse(line_of_sight((.5,1), (1.5,1), doorway))

    def test_polygon_stops_at_wall_and_stays_in_radius(self):
        polygon = visibility_polygon((.5,.5), ((1,-5,1,5),), 3)
        self.assertTrue(polygon)
        self.assertLessEqual(max(x for x,y in polygon), 1+1e-8)
        self.assertTrue(all(math.hypot(x-.5,y-.5) <= 3+1e-8 for x,y in polygon))
        # The unobstructed half still fills a circle, rather than a square.
        self.assertAlmostEqual(min(x for x,y in polygon), -2.5)

    def test_diagonal_corner_does_not_leak(self):
        corner = ((1,0,1,1),(0,1,1,1))
        self.assertFalse(line_of_sight((.5,.5), (1.5,1.5), corner))
        self.assertTrue(line_of_sight((.5,.5), (.7,.7), corner))

    def test_walls_deduplicate_and_visibility_follows_passages(self):
        maze = Maze(1,2)
        self.assertEqual(len(wall_segments(maze)),7)
        self.assertEqual(visible_cells(maze,(0,0)), {(0,0)})
        maze.grid[0][0].walls.remove('E')
        maze.grid[0][1].walls.remove('W')
        self.assertEqual(len(wall_segments(maze)),6)
        self.assertEqual(visible_cells(maze,(0,0)), {(0,0),(0,1)})
        self.assertEqual(visible_cells(maze,(-1,0)), set())

    def test_lamps_are_spaced_deterministic_and_inside_floor(self):
        maze = Maze(24,32,seed=7)
        list(maze.generate())
        lamps = lamp_positions(maze)
        self.assertEqual(lamps, lamp_positions(maze))
        self.assertEqual(len(lamps),14)
        self.assertEqual(len(lamps),len(set(lamps)))
        self.assertTrue(all(0<x<maze.cols and 0<y<maze.rows for x,y in lamps))
        self.assertEqual(lamp_positions(maze,0),())
        tiny = Maze(1,1)
        self.assertEqual(len(lamp_positions(tiny)),1)

    def test_invalid_polygon_parameters(self):
        with self.assertRaises(ValueError):
            visibility_polygon((0,0),(),0)
        with self.assertRaises(ValueError):
            visibility_polygon((0,0),(),2,rays=2)
