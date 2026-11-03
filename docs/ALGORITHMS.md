# Read the maze as a graph

A cell is a vertex. A passage is an edge. Walls decide which neighboring vertices can be reached. `Maze.can_move` checks both sides of a passage, so a broken wall cannot accidentally become a one-way door.

## Generation: build a tree

Generation starts with walls everywhere. It picks an unvisited neighbor, removes the shared wall from both cells, and continues from that neighbor. When no new neighbor remains, it returns to the previous cell.

Every new cell joins through exactly one passage. For V cells, this creates V − 1 passages. Because every cell is reached and no passage joins two already visited cells, the result is a connected tree. There is exactly one simple route between any two cells.

`Maze.generate` holds the current traversal in an explicit stack. This implements the same depth-first process as recursive calls while avoiding Python's recursion-depth ceiling. Its generator yields after a carving step so Qt can draw and handle input before continuing.

## Depth-first search: follow a branch

DFS stores the route being explored in a stack. It visits an unvisited neighbor and pushes it onto the route. At a dead end, it pops the cell and backtracks. In Observe mode, pause at a junction and predict the next step; use Step to check.

A visited set prevents repeated exploration. DFS is useful when a route is enough and does not generally guarantee the shortest route in a graph with cycles.

## Breadth-first search: explore by distance

BFS stores the frontier in a queue. Cells discovered first are explored first. A parent map records how each cell was reached; following those parents reconstructs the route.

On an unweighted graph, BFS guarantees a shortest route. On these generated tree mazes, DFS also finds the shortest route because only one simple route exists. Their exploration counts may differ, and neither is guaranteed to inspect fewer cells for every seed.

## Complexity

Generation, DFS, and BFS take O(V + E) time and O(V) auxiliary storage. A rectangular maze has bounded degree: at most four neighbors per cell. Its E is proportional to V, so traversal grows linearly with the cell count.

Animation rendering and reconstructing intermediate display routes add interface work beyond the traversal itself. Animation time is controlled by speed and should not be treated as an algorithm benchmark.

## Difficulty

The five levels increase grid size and the number of decisions a player must track. Size is a progression guide, not a mathematical guarantee that every later seed is harder. Dead-end and junction counts describe a particular maze; route length and personal navigation strategy also affect the challenge.

## Try it

1. Choose a seed and solve a small maze in Play mode.
2. Observe DFS on that same layout. Pause when the search meets a dead end.
3. Observe BFS and compare explored cells with the final route length.
4. Predict which search will explore fewer cells on another seed, then check. One example does not establish a universal winner.
