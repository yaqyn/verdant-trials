# Maze Runner

A medieval forest quest for playing mazes and seeing how search algorithms explore them. Navigate yourself, ask for a hint, or pause an algorithm and inspect its next decision.

> Built from [Boot.dev's Build a Maze Solver in Python](https://www.boot.dev/courses/build-maze-solver-python), extended with progressive levels, player controls, and algorithm comparison.

## Start exploring

Requires **Python 3.10+**, Tkinter, and a graphical desktop. Pillow enables the illustrated forest frame and bundled display typography. No accounts or runtime network access are needed.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
.venv/bin/python main.py --level 3 --seed 42 --delay 15
```

On Arch Linux, Tkinter requires the `tk` package. On Ubuntu, install `python3-tk`. `python3 -m tkinter` checks whether your desktop can open a Tk window.

## Enter the forest

Dark forest is the default theme. Switch World lighting to Daylight for lighter controls without resetting the quest. The board features an original generated ruined-forest frame, SVG moss-stone walls, and original compass, lantern, gate and wayfarer icons. Cinzel gives display headings an engraved RPG character; instructions retain a readable system font. Asset provenance and the final generation prompt are in [assets/ARTWORK.md](assets/ARTWORK.md). Font fallbacks and a plain board keep the app functional on limited systems.

## Choose your experience

**Play:** click the maze and use arrow keys or WASD. The dot is your position; **E** marks the exit. Show next move reveals one step. Reveal route shows the remaining route. Both count as assistance. When you reach the exit, compare your move count with the direct route and continue to the next level.

**Observe:** choose depth-first or breadth-first search, then select Run search. Pause freezes the traversal; Step advances one event. Replay search lets you try another algorithm on the same maze. Live explanations describe visits and backtracking. Teal shows the revealed or completed route, blue marks explored cells, and sand marks backtracking.

New maze cancels the current animation. Blank seeds create random layouts; a numeric seed reproduces a layout at the same level. The actual seed is shown below the board. Slow, Normal, Fast, and Instant control animation pace; Instant still processes bounded batches so the window can handle input.

## Five levels

| Level | Grid | Learning focus |
| --- | --- | --- |
| The moss gate | 4 × 5 | Cells and passages form a graph |
| Whispering grove | 8 × 10 | Following branches and backtracking |
| Ruins of the lost | 12 × 16 | Remembering visited cells |
| Moonlit thicket | 18 × 24 | Exploring by distance with BFS |
| The elder labyrinth | 24 × 32 | Comparing traversal work |

Levels increase the search space. Random seeds vary in route length and branching, so a larger board is not guaranteed to be harder in every instance. All levels are available immediately; no progress is saved between sessions.

## Understand the algorithms

Generation carves a connected tree with exactly one route between any pair of cells. DFS follows a branch and backs out of dead ends. BFS explores cells in distance order. Both find the same route in these tree mazes; their exploration order and visit counts differ.

The engine uses explicit stacks to retain DFS behavior without Python's recursion-depth limit. Tkinter advances generators through `after` callbacks, keeping drawing and input separate from traversal logic. Animation speed is a teaching control, not a performance benchmark.

Read [the algorithm walkthrough](docs/ALGORITHMS.md) for mechanics, complexity, and short experiments.

## Verify and maintain

```bash
.venv/bin/python -m unittest discover -v
.venv/bin/python -m compileall -q app.py art.py maze.py theme.py typography.py
```

Model tests cover connectivity, reciprocal walls, deterministic seeds, large levels, unsolvable graphs, and BFS shortest routes in graphs with cycles. GUI tests cover play completion, hints, search replay, pause/step, invalid input, and cancellation. GUI tests skip when no display is available; CI uses Xvfb to run them on Python 3.11–3.13.

| File | Responsibility |
| --- | --- |
| `maze.py` | Cells, generation, searches, movement, route hints |
| `levels.py` | Progressive grids and learning concepts |
| `app.py` | Desktop workflows, animation, rendering |
| `theme.py`, `typography.py` | Dark/daylight colors, native controls, bundled font |
| `art.py`, `assets/` | Forest frame, editable SVG icons and wall renderer |
| `main.py` | Command-line options and desktop launch |

[DESIGN.md](DESIGN.md) records interaction and visual decisions. Keyboard controls use native widgets; animation can be paused or stepped. Tkinter assistive-technology support varies by platform. This is a local educational app; it has no packaging installer, telemetry, cloud service, or saved player profile.
