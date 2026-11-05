"""Maze graph and stepwise search algorithms, independent of the interface."""

from collections import deque
from dataclasses import dataclass, field
from random import Random

DIRECTIONS = ((-1, 0, "N", "S"), (0, 1, "E", "W"),
              (1, 0, "S", "N"), (0, -1, "W", "E"))
OPPOSITE = {direction: opposite for _, _, direction, opposite in DIRECTIONS}


@dataclass
class Cell:
    walls: set[str] = field(default_factory=lambda: set("NSEW"))


class Maze:
    """Row-major maze exposing one animation event per traversal step.

    Explicit stacks retain recursive DFS's push/explore/backtrack behavior while
    avoiding Python's call-stack limit on larger educational levels. Exhaust a
    generation before solving or moving through the resulting maze.
    """

    def __init__(self, rows=12, cols=16, seed=None):
        if any(type(value) is not int or value <= 0 for value in (rows, cols)):
            raise ValueError("Rows and columns must be positive integers")
        self.rows, self.cols, self.seed = rows, cols, seed
        self.grid = [[Cell() for _ in range(cols)] for _ in range(rows)]
        self.path = []
        self.solved = False

    def neighbors(self, row, col):
        for dr, dc, direction, _ in DIRECTIONS:
            nr, nc = row + dr, col + dc
            if 0 <= nr < self.rows and 0 <= nc < self.cols:
                yield nr, nc, direction

    def can_move(self, position, direction):
        """Return whether a compass move stays inside a reciprocal passage."""
        row, col = position
        if direction not in OPPOSITE or not (0 <= row < self.rows and 0 <= col < self.cols):
            return False
        for nr, nc, candidate in self.neighbors(row, col):
            if candidate == direction:
                return (direction not in self.grid[row][col].walls and
                        OPPOSITE[direction] not in self.grid[nr][nc].walls)
        return False

    def _passages(self, position):
        for nr, nc, direction in self.neighbors(*position):
            if self.can_move(position, direction):
                yield nr, nc

    def generate(self):
        """Carve a spanning tree with randomized depth-first search."""
        self.grid = [[Cell() for _ in range(self.cols)] for _ in range(self.rows)]
        self.path, self.solved = [], False
        rng = Random(self.seed)
        visited = {(0, 0)}
        self.grid[0][0].walls.remove("N")
        self.grid[-1][-1].walls.remove("S")

        def choices(position):
            candidates = list(self.neighbors(*position))
            rng.shuffle(candidates)
            return iter(candidates)

        stack = [((0, 0), choices((0, 0)))]
        yield 0, 0
        while stack:
            position, candidates = stack[-1]
            candidate = next(candidates, None)
            if candidate is None:
                stack.pop()
                continue
            nr, nc, direction = candidate
            neighbor = (nr, nc)
            if neighbor in visited:
                continue
            row, col = position
            visited.add(neighbor)
            self.grid[row][col].walls.remove(direction)
            self.grid[nr][nc].walls.remove(OPPOSITE[direction])
            yield neighbor
            stack.append((neighbor, choices(neighbor)))

    @staticmethod
    def _reconstruct(parents, position):
        path = []
        while position is not None:
            path.append(position)
            position = parents[position]
        return path[::-1]

    def route_from(self, start):
        """Return a shortest route to the exit without altering search state."""
        if not (0 <= start[0] < self.rows and 0 <= start[1] < self.cols):
            raise ValueError("Start must be inside the maze")
        start = tuple(start)
        goal = (self.rows - 1, self.cols - 1)
        queue, parents = deque([start]), {start: None}
        while queue:
            position = queue.popleft()
            if position == goal:
                return self._reconstruct(parents, position)
            for neighbor in self._passages(position):
                if neighbor not in parents:
                    parents[neighbor] = position
                    queue.append(neighbor)
        return []

    def directions_from(self, start):
        """Return compass steps for the shortest route from a cell to the exit."""
        route = self.route_from(start)
        steps = []
        for (row, col), (next_row, next_col) in zip(route, route[1:]):
            direction = next(
                direction
                for dr, dc, direction, _ in DIRECTIONS
                if (row + dr, col + dc) == (next_row, next_col)
            )
            steps.append(direction)
        return steps

    def metrics(self):
        """Count graph features; boundary entrance/exit openings are excluded."""
        degrees = [sum(1 for _ in self._passages((r, c)))
                   for r in range(self.rows) for c in range(self.cols)]
        return {"cells": self.rows * self.cols,
                "dead_ends": sum(degree == 1 for degree in degrees),
                "junctions": sum(degree >= 3 for degree in degrees)}

    def to_ascii(self, route=()):
        """Return a compact text map for terminals, logs, and lessons."""
        marked = {tuple(position) for position in route}
        if any(not (0 <= row < self.rows and 0 <= col < self.cols)
               for row, col in marked):
            raise ValueError("Route cells must be inside the maze")
        lines = []
        for row in range(self.rows):
            top = []
            middle = []
            for col in range(self.cols):
                cell = self.grid[row][col]
                top.append("+" + ("---" if "N" in cell.walls else "   "))
                marker = "S" if (row, col) == (0, 0) else "G" if (row, col) == (self.rows - 1, self.cols - 1) else "*" if (row, col) in marked else " "
                middle.append(("|" if "W" in cell.walls else " ") + f" {marker} ")
            lines.append("".join(top) + "+")
            lines.append("".join(middle) + ("|" if "E" in self.grid[row][-1].walls else " "))
        lines.append("".join("+" + ("---" if "S" in cell.walls else "   ") for cell in self.grid[-1]) + "+")
        return "\n".join(lines)

    def solve(self, strategy="dfs"):
        """Yield (action, position), maintaining the current route in ``path``.

        DFS visits deeply then backtracks; BFS visits in distance order and
        exposes each visited cell's parent route. Both return a shortest route
        on our tree mazes; BFS also guarantees this on graphs containing cycles.
        """
        if strategy not in ("dfs", "bfs"):
            raise ValueError("Strategy must be 'dfs' or 'bfs'")
        self.path, self.solved = [], False
        start, goal = (0, 0), (self.rows - 1, self.cols - 1)
        visited = {start}
        if strategy == "bfs":
            queue, parents = deque([start]), {start: None}
            while queue:
                position = queue.popleft()
                self.path = self._reconstruct(parents, position)
                yield "visit", position
                if position == goal:
                    self.solved = True
                    break
                for neighbor in self._passages(position):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        parents[neighbor] = position
                        queue.append(neighbor)
            if not self.solved:
                self.path = []
        else:
            self.path = [start]
            stack = [(start, iter(self._passages(start)))]
            yield "visit", start
            while stack:
                position, neighbors = stack[-1]
                if position == goal:
                    self.solved = True
                    break
                neighbor = next(neighbors, None)
                if neighbor is None:
                    stack.pop()
                    self.path.pop()
                    yield "backtrack", position
                elif neighbor not in visited:
                    visited.add(neighbor)
                    self.path.append(neighbor)
                    stack.append((neighbor, iter(self._passages(neighbor))))
                    yield "visit", neighbor
        yield "done", goal if self.solved else start
