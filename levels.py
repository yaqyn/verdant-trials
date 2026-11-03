"""Progressive maze sizes and their educational focus."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Level:
    id: int
    title: str
    rows: int
    cols: int
    description: str
    concept: str


LEVELS = (
    Level(1, "First steps", 4, 5, "A compact maze with room to see each decision.",
          "A maze is a graph: cells are vertices and passages are edges."),
    Level(2, "Find your rhythm", 8, 10, "More turns and dead ends to practice backtracking.",
          "Depth-first search follows one branch until it must backtrack."),
    Level(3, "Branching paths", 12, 16, "Track your route through longer corridors.",
          "A visited set prevents the search from exploring a cell twice."),
    Level(4, "Deep exploration", 18, 24, "A larger search space rewards careful observation.",
          "Breadth-first search uses a queue to explore cells in distance order."),
    Level(5, "The labyrinth", 24, 32, "A dense maze that tests your navigation and search intuition.",
          "Both searches take O(V + E) work; their exploration order differs."),
)
