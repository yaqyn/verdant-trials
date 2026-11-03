"""Maze data and recursive algorithms, independent of the graphical interface."""

from dataclasses import dataclass, field
from random import Random


DIRECTIONS = ((-1, 0, "N", "S"), (0, 1, "E", "W"),
              (1, 0, "S", "N"), (0, -1, "W", "E"))
OPPOSITE = {direction: opposite for _, _, direction, opposite in DIRECTIONS}


@dataclass
class Cell:
    walls: set[str] = field(default_factory=lambda: set("NSEW"))


class Maze:
    """A row-major maze whose generators expose individual animation steps.

    Exhaust ``generate`` before solving. Recursive traversal intentionally follows
    the course algorithm; grids approaching Python's recursion limit need a
    different traversal strategy.
    """

    def __init__(self, rows=12, cols=16, seed=None):
        if any(type(value) is not int or value <= 0 for value in (rows, cols)):
            raise ValueError("Rows and columns must be positive integers")
        self.rows, self.cols, self.seed = rows, cols, seed
        self.grid = [[Cell() for _ in range(cols)] for _ in range(rows)]
        self.path = []
        self.solved = False

    def neighbors(self, row, col):
        """Yield adjacent in-bounds cells and the direction from this cell."""
        for dr, dc, direction, _ in DIRECTIONS:
            nr, nc = row + dr, col + dc
            if 0 <= nr < self.rows and 0 <= nc < self.cols:
                yield nr, nc, direction

    def generate(self):
        """Carve a spanning tree using randomized recursive depth-first search."""
        self.grid = [[Cell() for _ in range(self.cols)] for _ in range(self.rows)]
        self.path = []
        self.solved = False
        rng = Random(self.seed)
        visited = {(0, 0)}
        self.grid[0][0].walls.remove("N")
        self.grid[-1][-1].walls.remove("S")

        def carve(row, col):
            choices = list(self.neighbors(row, col))
            rng.shuffle(choices)
            for nr, nc, direction in choices:
                if (nr, nc) in visited:
                    continue
                visited.add((nr, nc))
                self.grid[row][col].walls.remove(direction)
                self.grid[nr][nc].walls.remove(OPPOSITE[direction])
                yield nr, nc
                yield from carve(nr, nc)

        yield 0, 0
        yield from carve(0, 0)

    def solve(self):
        """Yield exploration/backtracking events, retaining the successful path."""
        self.path = []
        self.solved = False
        visited = set()
        goal = (self.rows - 1, self.cols - 1)

        def search(row, col):
            position = (row, col)
            visited.add(position)
            self.path.append(position)
            yield "visit", position
            if position == goal:
                self.solved = True
                return True
            for nr, nc, direction in self.neighbors(row, col):
                if direction in self.grid[row][col].walls or (nr, nc) in visited:
                    continue
                if (yield from search(nr, nc)):
                    return True
            self.path.pop()
            yield "backtrack", position
            return False

        yield from search(0, 0)
        yield "done", goal if self.solved else (0, 0)
