"""Physical visibility and deterministic lamp placement checks."""
import math
import unittest
from lighting import (lamp_positions, line_of_sight, visibility_polygon,
                      visible_cells, wall_segments, grid_ray_distance,
                      grid_visibility_polygon)
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

    def test_grid_rays_respect_reciprocal_walls_and_open_boundaries(self):
        maze = Maze(1,3)
        maze.grid[0][0].walls.remove('E')
        # A claimed wall on either side still blocks the ray.
        self.assertEqual(grid_ray_distance(maze,(.5,.5),(1,0),4),.5)
        maze.grid[0][1].walls.remove('W')
        self.assertEqual(grid_ray_distance(maze,(.5,.5),(1,0),4),1.5)
        self.assertEqual(grid_ray_distance(maze,(1,.5),(-1,0),4),1)
        self.assertEqual(grid_ray_distance(maze,(1,.5),(1,0),4),1)
        self.assertEqual(grid_ray_distance(maze,(.5,.5),(0,1),4),.5)
        # Entrance/exit openings are clipped to the floor boundary.
        maze.grid[0][0].walls.remove('N')
        self.assertEqual(grid_ray_distance(maze,(.5,.5),(0,-1),4),.5)

    def test_grid_corner_cannot_leak_between_incident_walls(self):
        maze = Maze(2,2)
        for row in maze.grid:
            for cell in row:
                cell.walls.clear()
        self.assertAlmostEqual(grid_ray_distance(maze,(.5,.5),(1,1),4),math.sqrt(4.5))
        # This wall touches the corner from the diagonal cell, even though
        # both passages immediately beside the emitter are open.
        maze.grid[1][1].walls.add('W')
        self.assertAlmostEqual(grid_ray_distance(maze,(.5,.5),(1,1),4),math.sqrt(.5))
        self.assertNotIn((1,1),visible_cells(maze,(0,0)))
        self.assertIn((0,1),visible_cells(maze,(0,0)))

    def test_grid_polygon_matches_segment_silhouettes_for_seeded_mazes(self):
        for seed in range(5):
            maze = Maze(8,9,seed=seed)
            list(maze.generate())
            segments = wall_segments(maze)
            for origin in ((2.25,2.5),(4.5,3.75),(6.75,5.25),(3.,2.5),(4.5,4.)):
                if (origin[0].is_integer() and not maze.can_move((int(origin[1]),int(origin[0])-1),'E')
                        or origin[1].is_integer() and not maze.can_move((int(origin[1])-1,int(origin[0])),'S')):
                    continue  # Boundary emitters are tested only in open passages.
                with self.subTest(seed=seed,origin=origin):
                    reference = visibility_polygon(origin,segments,3.4,rays=32)
                    walked = grid_visibility_polygon(maze,origin,3.4,rays=32,segments=segments)
                    local = grid_visibility_polygon(maze,origin,3.4,rays=32)
                    self.assertEqual(len(walked),len(reference))
                    self.assertEqual(walked,local)
                    for expected,actual in zip(reference,walked):
                        # The general renderer can extend through external
                        # entrances; grid rays intentionally stop at the floor.
                        if all(0<x<maze.cols and 0<y<maze.rows for x,y in (expected,actual)):
                            self.assertAlmostEqual(actual[0],expected[0],places=6)
                            self.assertAlmostEqual(actual[1],expected[1],places=6)
                    row,col = int(origin[1]),int(origin[0])
                    eye = (col+.5,row+.5)
                    expected_cells = {(r,c) for r in range(maze.rows) for c in range(maze.cols)
                                      if math.hypot(r-row,c-col) <= 3.4
                                      and line_of_sight(eye,(c+.5,r+.5),segments)}
                    self.assertEqual(visible_cells(maze,(row,col),3.4),expected_cells)

    def test_grid_ray_stops_at_collinear_wall_endpoint(self):
        maze = Maze(4,4)
        for row in maze.grid:
            for cell in row:
                cell.walls.clear()
        maze.grid[1][2].walls.add('N')
        self.assertEqual(grid_ray_distance(maze,(.5,1),(1,0),4),1.5)
        self.assertEqual(grid_ray_distance(maze,(3.5,1),(-1,0),4),.5)
        self.assertEqual(grid_ray_distance(maze,(2.5,1),(1,0),4),0)

    def test_grid_visibility_does_not_scan_global_wall_inventory(self):
        from unittest.mock import patch
        maze = Maze(24,32,seed=42)
        list(maze.generate())
        with patch('lighting.wall_segments',side_effect=AssertionError('global scan')):
            self.assertTrue(visible_cells(maze,(10,10)))
            self.assertTrue(grid_visibility_polygon(maze,(10.5,10.5),3.4))
        with self.assertRaises(ValueError):
            grid_ray_distance(maze,(.5,.5),(0,0),3)
        with self.assertRaises(ValueError):
            grid_visibility_polygon(maze,(.5,.5),0)
