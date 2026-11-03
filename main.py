"""Animate maze generation and recursive search with Tkinter's event loop."""
import argparse
import tkinter as tk
from maze import Maze


class MazeWindow:
    def __init__(self, rows=12, cols=16, seed=None, delay=15):
        self.maze = Maze(rows, cols, seed)
        self.delay = delay
        self.size = min(40, 800 // max(rows, cols))
        self.margin = 24
        self.root = tk.Tk()
        self.root.title('Maze Runner')
        self.status = tk.StringVar(value='Generating maze…')
        tk.Label(self.root, textvariable=self.status).pack(pady=8)
        self.canvas = tk.Canvas(self.root, width=cols*self.size+48,
                                height=rows*self.size+48, bg='white')
        self.canvas.pack()
        self.button = tk.Button(self.root, text='New maze', command=self.start)
        self.button.pack(pady=8)
        self.start()

    def center(self, position):
        r, c = position
        return (self.margin+(c+.5)*self.size, self.margin+(r+.5)*self.size)

    def draw_walls(self):
        self.canvas.delete('wall')
        for r, row in enumerate(self.maze.grid):
            for c, cell in enumerate(row):
                x, y = self.margin+c*self.size, self.margin+r*self.size
                s = self.size
                edges = {'N': (x,y,x+s,y), 'S': (x,y+s,x+s,y+s),
                         'W': (x,y,x,y+s), 'E': (x+s,y,x+s,y+s)}
                for direction in cell.walls:
                    self.canvas.create_line(*edges[direction], width=2, tags='wall')

    def start(self):
        self.button.config(state='disabled')
        self.canvas.delete('all')
        self.status.set('Generating maze…')
        self.steps = self.maze.generate()
        self.generating = True
        self.previous = None
        self.tick()

    def tick(self):
        try:
            event = next(self.steps)
        except StopIteration:
            if self.generating:
                self.draw_walls()
                self.generating = False
                self.steps = self.maze.solve()
                self.status.set('Searching — red explores, gray backtracks')
                self.root.after(self.delay, self.tick)
            else:
                for a, b in zip(self.maze.path, self.maze.path[1:]):
                    self.canvas.create_line(*self.center(a), *self.center(b),
                                            fill='forest green', width=3)
                self.status.set(f'Solved — {len(self.maze.path)} cells in the route')
                self.button.config(state='normal')
            return
        if self.generating:
            self.draw_walls()
        else:
            action, position = event
            if action == 'backtrack':
                parent = self.maze.path[-1] if self.maze.path else position
                self.canvas.create_line(*self.center(position), *self.center(parent),
                                        fill='gray', width=2)
                self.previous = parent
            elif action == 'visit':
                if self.previous is not None:
                    self.canvas.create_line(*self.center(self.previous), *self.center(position),
                                            fill='red', width=2)
                self.previous = position
        self.root.after(self.delay, self.tick)

    def run(self):
        self.root.mainloop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rows', type=int, default=12)
    parser.add_argument('--cols', type=int, default=16)
    parser.add_argument('--seed', type=int)
    parser.add_argument('--delay', type=int, default=15, help='Milliseconds between animation steps')
    args = parser.parse_args()
    if not (1 <= args.rows <= 25 and 1 <= args.cols <= 25) or args.delay < 0:
        parser.error('rows and cols must be 1–25; delay must be nonnegative')
    MazeWindow(args.rows, args.cols, args.seed, args.delay).run()


if __name__ == '__main__':
    main()
