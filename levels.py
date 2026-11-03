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
    Level(1, "The moss gate", 4, 5, "A compact maze with room to see each decision.",
          "A maze is a graph: cells are vertices and passages are edges."),
    Level(2, "Whispering grove", 8, 10, "More turns and dead ends to practice backtracking.",
          "Depth-first search follows one branch until it must backtrack."),
    Level(3, "Ruins of the lost", 12, 16, "Track your route through longer corridors.",
          "A visited set prevents the search from exploring a cell twice."),
    Level(4, "Moonlit thicket", 18, 24, "A larger search space rewards careful observation.",
          "Breadth-first search uses a queue to explore cells in distance order."),
    Level(5, "The elder labyrinth", 24, 32, "A dense maze that tests your navigation and search intuition.",
          "Both searches take O(V + E) work; their exploration order differs."),
)
