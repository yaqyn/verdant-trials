# Maze Runner

Watch a random maze take shape, then follow a recursive search from entrance to exit. Red traces exploration, gray shows backtracking, and green marks the finished route.

A fresh implementation based on [Boot.dev's Build a Maze Solver in Python](https://www.boot.dev/courses/build-maze-solver-python): Tkinter, grid cells, randomized maze generation, and recursive backtracking.

## Run

Requires Python 3.10+ with Tkinter and a graphical desktop. No pip dependencies.

```bash
python3 main.py
python3 main.py --rows 15 --cols 20 --seed 42 --delay 5
```

On Arch Linux, install the `tk` system package if Tkinter is unavailable. Close the window to quit; select **New maze** after a search to generate another maze. With a seed, New maze reproduces the same layout. Grid dimensions are limited to 1–25 per side to keep the recursive algorithms within Python's usual recursion limit.

## Design

`maze.py` owns the cells and algorithms without depending on a GUI. Generation visits new neighbors and removes both sides of each shared wall. This creates a connected tree: exactly one route connects any pair of cells. The solver explores passages recursively and backs out of dead ends.

`main.py` draws the grid and advances the algorithms through Tkinter's `after` callback. Each generator yields a small unit of work, allowing the window to handle input between animation steps.

## Test

```bash
python3 -m unittest discover -v
```
