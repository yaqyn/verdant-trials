"""Interactive learning studio for maze generation, play, and search."""
import secrets
import tkinter as tk
from tkinter import ttk

from levels import LEVELS
from maze import Maze
from theme import COLORS as C, configure


class MazeApp:
    def __init__(self, root, level_id=None, seed=None, delay=25):
        self.root = root
        configure(root)
        root.title('Maze Runner — exploration studio')
        root.geometry('1180x800')
        root.minsize(920, 700)
        self.levels = list(LEVELS)
        self.level_index = next((i for i, level in enumerate(self.levels)
                                 if level.id == level_id), 0)
        self.delay = delay
        self.job = None
        self.phase = 'idle'
        self.paused = False
        self.closed = False
        self.mode = tk.StringVar(value='Play')
        self.algorithm = tk.StringVar(value='Depth-first search')
        self.seed = tk.StringVar(value=str(seed) if seed is not None else '')
        self.speed = tk.StringVar(value='Normal')
        self.level_choice = tk.StringVar()
        self.status = tk.StringVar(value='Choose a level and create a maze.')
        self.explanation = tk.StringVar()
        self.metrics = tk.StringVar()
        self.level_text = tk.StringVar()
        self.error = tk.StringVar()
        self._build()
        self._select_level()
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.bind('<KeyPress>', self._key)
        self.new_maze()

    def _build(self):
        shell = ttk.Frame(self.root, padding=18)
        shell.pack(fill='both', expand=True)
        ttk.Label(shell, text='Maze Runner', style='Title.TLabel').pack(anchor='w')
        ttk.Label(shell, text='Learn to explore. Find your own way.', style='Muted.TLabel').pack(anchor='w', pady=(3, 12))
        body = ttk.Frame(shell)
        body.pack(fill='both', expand=True)
        sidebar = ttk.Frame(body, width=250)
        sidebar.pack(side='left', fill='y', padx=(0, 24))
        sidebar.pack_propagate(False)
        ttk.Label(sidebar, text='Your expedition', style='Heading.TLabel').pack(anchor='w', pady=(0, 6))
        self._label(sidebar, 'Level')
        self.level_box = ttk.Combobox(sidebar, textvariable=self.level_choice, state='readonly',
            values=[f'{i+1}. {l.title}' for i, l in enumerate(self.levels)])
        self.level_box.pack(fill='x')
        self.level_box.bind('<<ComboboxSelected>>', self._change_level)
        ttk.Label(sidebar, textvariable=self.level_text, wraplength=245, style='Muted.TLabel').pack(anchor='w', pady=(5, 6))
        self._label(sidebar, 'Experience')
        self.mode_box = ttk.Combobox(sidebar, textvariable=self.mode, state='readonly', values=['Play', 'Observe'])
        self.mode_box.pack(fill='x')
        self.mode_box.bind('<<ComboboxSelected>>', lambda e: self._mode_changed())
        self._label(sidebar, 'Search algorithm')
        self.algorithm_box = ttk.Combobox(sidebar, textvariable=self.algorithm, state='readonly',
            values=['Depth-first search', 'Breadth-first search'])
        self.algorithm_box.pack(fill='x')
        self._label(sidebar, 'Maze seed (blank for random)')
        self.seed_entry = ttk.Entry(sidebar, textvariable=self.seed)
        self.seed_entry.pack(fill='x')
        ttk.Label(sidebar, textvariable=self.error, wraplength=245, foreground='#a42f29').pack(anchor='w')
        self._label(sidebar, 'Animation pace')
        speed = ttk.Combobox(sidebar, textvariable=self.speed, state='readonly',
                             values=['Slow', 'Normal', 'Fast', 'Instant'])
        speed.pack(fill='x')
        ttk.Button(sidebar, text='New maze', style='Accent.TButton', command=self.new_maze).pack(fill='x', pady=(10, 4))
        self.run_button = ttk.Button(sidebar, text='Run search', command=self.run_search)
        self.run_button.pack(fill='x', pady=2)
        row = ttk.Frame(sidebar)
        row.pack(fill='x', pady=2)
        self.pause_button = ttk.Button(row, text='Pause', command=self.toggle_pause)
        self.pause_button.pack(side='left', fill='x', expand=True)
        self.step_button = ttk.Button(row, text='Step', command=self.single_step)
        self.step_button.pack(side='left', fill='x', expand=True, padx=(6, 0))
        self.hint_button = ttk.Button(sidebar, text='Show next move', command=self.hint)
        self.hint_button.pack(fill='x', pady=2)
        self.reveal_button = ttk.Button(sidebar, text='Reveal route', command=self.reveal)
        self.reveal_button.pack(fill='x', pady=2)
        self.next_button = ttk.Button(sidebar, text='Next level', command=self.next_level)
        self.next_button.pack(fill='x', pady=(6, 2))
        ttk.Label(sidebar, text='Play: arrow keys or W A S D\nClick the maze to focus. Exit: E.',
                  wraplength=245, style='Muted.TLabel').pack(anchor='w', pady=6)
        workspace = ttk.Frame(body)
        workspace.pack(side='left', fill='both', expand=True)
        self.status_label = ttk.Label(workspace, textvariable=self.status, style='Heading.TLabel', wraplength=600)
        self.status_label.pack(anchor='w', pady=(0, 10))
        self.canvas = tk.Canvas(workspace, background=C['surface'], highlightthickness=2,
            highlightbackground='#c8d4dc', highlightcolor=C['accent'], takefocus=True)
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Configure>', self._resize)
        self.canvas.bind('<Button-1>', lambda e: self.canvas.focus_set())
        ttk.Label(workspace, text='Start: ring   Exit: E   Teal: route   Blue: explored   Sand: backtracked',
                  style='Muted.TLabel').pack(anchor='w', pady=(10, 6))
        ttk.Label(workspace, textvariable=self.metrics).pack(anchor='w', pady=(0, 10))
        ttk.Separator(workspace).pack(fill='x')
        ttk.Label(workspace, text='Inside the algorithm', style='Heading.TLabel').pack(anchor='w', pady=(6, 2))
        self.explanation_label = ttk.Label(workspace, textvariable=self.explanation, wraplength=600, justify='left')
        self.explanation_label.pack(anchor='w')

    def _resize(self, event):
        self.status_label.configure(wraplength=max(200, event.width-12))
        self.explanation_label.configure(wraplength=max(200, event.width-12))
        self.draw()

    @staticmethod
    def _label(parent, text):
        ttk.Label(parent, text=text).pack(anchor='w', pady=(6, 3))

    def _select_level(self):
        level = self.levels[self.level_index]
        self.level_choice.set(f'{self.level_index+1}. {level.title}')
        self.level_text.set(f'{level.rows} × {level.cols} cells\n{level.description}')
        self.explanation.set(level.concept)

    def _change_level(self, event=None):
        self.level_index = self.level_box.current()
        self._select_level()
        self.new_maze()

    def next_level(self):
        if self.level_index < len(self.levels)-1:
            self.level_index += 1
            self._select_level()
            self.new_maze()

    def _cancel(self):
        if self.job is not None:
            self.root.after_cancel(self.job)
            self.job = None

    def new_maze(self):
        raw = self.seed.get().strip()
        try:
            seed = int(raw) if raw else secrets.randbelow(1_000_000_000)
            if len(raw) > 20:
                raise ValueError
        except ValueError:
            self.error.set('Enter a whole-number seed, up to 20 characters.')
            self.seed_entry.focus_set()
            return
        self.error.set('')
        self._cancel()
        level = self.levels[self.level_index]
        self.maze = Maze(level.rows, level.cols, seed)
        self.active_seed = seed
        self.steps = self.maze.generate()
        self.phase = 'generating'
        self.paused = False
        self.player = (0, 0)
        self.trail = [self.player]
        self.explored = set()
        self.backtracked = set()
        self.overlay = []
        self.moves = self.visits = self.retreats = self.hints = 0
        self.status.set('Carving passages…')
        self.explanation.set('Generation uses depth-first search: visit an unvisited neighbor and remove the shared wall. Every cell joins the maze exactly once.')
        self._controls()
        self.tick()

    def _mode_changed(self):
        if self.phase in ('searching', 'complete'):
            self._cancel()
            self.phase = 'ready'
            self.explored.clear()
            self.backtracked.clear()
            self.overlay = []
        self.player = (0, 0)
        self.trail = [self.player]
        self.moves = self.visits = self.retreats = self.hints = 0
        self.paused = False
        if self.phase == 'ready':
            self._ready_message()
        self._controls()
        self.draw()

    def _ready_message(self):
        self.status.set('Your turn — find the exit.' if self.mode.get() == 'Play' else 'Ready to explore — select Run search.')
        self.explanation.set(self.levels[self.level_index].concept)

    def _controls(self):
        active = self.phase in ('generating', 'searching')
        ready = self.phase == 'ready'
        play = ready and self.mode.get() == 'Play'
        self.run_button.config(state='normal' if self.phase in ('ready', 'complete') and self.mode.get() == 'Observe' else 'disabled', text='Replay search' if self.phase == 'complete' else 'Run search')
        self.pause_button.config(state='normal' if active else 'disabled', text='Resume' if self.paused else 'Pause')
        self.step_button.config(state='normal' if active else 'disabled')
        self.hint_button.config(state='normal' if play else 'disabled')
        self.reveal_button.config(state='normal' if ready else 'disabled')
        self.next_button.config(state='normal' if self.phase == 'complete' and self.level_index < len(self.levels)-1 else 'disabled')
        self.algorithm_box.config(state='readonly' if self.mode.get() == 'Observe' and self.phase != 'searching' else 'disabled')

    def run_search(self):
        if self.phase not in ('ready', 'complete') or self.mode.get() != 'Observe':
            return
        strategy = 'bfs' if self.algorithm.get().startswith('Breadth') else 'dfs'
        self.steps = self.maze.solve(strategy=strategy)
        self.phase = 'searching'
        self.paused = False
        self.visits = self.retreats = 0
        self.overlay = []
        self.explored.clear()
        self.backtracked.clear()
        self.status.set(f'Exploring with {self.algorithm.get().lower()}…')
        self._controls()
        self.tick()

    def toggle_pause(self):
        if self.phase not in ('generating', 'searching'):
            return
        self.paused = not self.paused
        self._cancel()
        self._controls()
        if not self.paused:
            self.tick()

    def single_step(self):
        if self.phase not in ('generating', 'searching'):
            return
        self._cancel()
        self.paused = True
        self._advance()
        self._controls()

    def tick(self):
        self.job = None
        if self.closed or self.paused:
            return
        # Instant mode still yields to the event loop between bounded batches.
        for _ in range(80 if self.speed.get() == 'Instant' else 1):
            if not self._advance(render=False):
                return
        self.draw()
        delay = {'Slow': 160, 'Normal': self.delay, 'Fast': 1, 'Instant': 1}[self.speed.get()]
        self.job = self.root.after(delay, self.tick)

    def _advance(self, render=True):
        try:
            event = next(self.steps)
        except StopIteration:
            if self.phase == 'generating':
                self.phase = 'ready'
                self._ready_message()
                self.canvas.focus_set()
            else:
                self.phase = 'complete'
                self.overlay = list(self.maze.path)
                self.status.set(f'Route found — {max(0, len(self.overlay)-1)} steps to the exit.')
                self.explanation.set('The search is complete. In this perfect maze there is one route between any two cells. DFS follows a branch; BFS explores by distance. Try both on the same seed.')
            self._controls()
            self.draw()
            return False
        if self.phase == 'searching':
            action, position = event
            if action == 'visit':
                self.visits += 1
                self.explored.add(position)
                self.player = position
                self.explanation.set('Visit a new cell and remember how it was reached. ' +
                    ('BFS uses a queue to explore the nearest unexplored cells first.' if self.algorithm.get().startswith('Breadth') else
                     'DFS uses a stack to continue down one branch until it reaches a dead end.'))
            elif action == 'backtrack':
                self.retreats += 1
                self.backtracked.add(position)
                if self.maze.path:
                    self.player = self.maze.path[-1]
                self.explanation.set('This branch cannot reach the exit. Backtrack to a previous junction and try another unexplored passage.')
        if render:
            self.draw()
        return True

    def _key(self, event):
        if isinstance(self.root.focus_get(), (ttk.Entry, ttk.Combobox)):
            return
        direction = {'Up':'N', 'Down':'S', 'Left':'W', 'Right':'E', 'w':'N', 's':'S', 'a':'W', 'd':'E'}.get(event.keysym)
        if not direction or self.phase != 'ready' or self.mode.get() != 'Play':
            return
        if not self.maze.can_move(self.player, direction):
            self.status.set('A wall blocks that direction. Try another passage.')
            return 'break'
        dr, dc = {'N':(-1,0), 'S':(1,0), 'W':(0,-1), 'E':(0,1)}[direction]
        self.player = self.player[0]+dr, self.player[1]+dc
        self.moves += 1
        self.trail.append(self.player)
        self.overlay = []
        self.status.set('Keep exploring — the exit is marked at the bottom right.')
        if self.player == (self.maze.rows-1, self.maze.cols-1):
            self.phase = 'complete'
            optimal = len(self.maze.route_from((0,0)))-1
            self.status.set(f'You found the exit! {self.moves} moves; direct route: {optimal}.')
            self.explanation.set(f'You navigated {self.maze.rows*self.maze.cols} cells with {self.hints} hints. Observe the same maze to compare your exploration with an algorithm.')
        self._controls()
        self.draw()
        return 'break'

    def hint(self):
        if self.phase == 'ready' and self.mode.get() == 'Play':
            self.hints += 1
            self.overlay = self.maze.route_from(self.player)[:2]
            self.status.set('Hint: follow the short teal line to the next cell.')
            self.draw()

    def reveal(self):
        if self.phase == 'ready':
            self.hints += 1
            start = self.player if self.mode.get() == 'Play' else (0,0)
            self.overlay = self.maze.route_from(start)
            self.status.set('Route revealed. You can still follow it yourself or create a new maze.')
            self.draw()

    def draw(self):
        if not hasattr(self, 'maze'):
            return
        canvas = self.canvas
        canvas.delete('dynamic')
        width, height = max(canvas.winfo_width(), 100), max(canvas.winfo_height(), 100)
        size = min((width-56)/self.maze.cols, (height-56)/self.maze.rows)
        ox, oy = (width-size*self.maze.cols)/2, (height-size*self.maze.rows)/2
        geometry = (width, height, self.maze.rows, self.maze.cols, id(self.maze))
        if getattr(self, '_wall_geometry', None) != geometry:
            canvas.delete('wall')
            self._wall_geometry = geometry
            self._wall_items = {}
            self._wall_states = {}
        def center(pos):
            r,c = pos
            return ox+(c+.5)*size, oy+(r+.5)*size
        for r, row in enumerate(self.maze.grid):
            for c, cell in enumerate(row):
                x,y = ox+c*size, oy+r*size
                pos = (r,c)
                color = C['retreat'] if pos in self.backtracked else C['explored'] if pos in self.explored else None
                if color:
                    canvas.create_rectangle(x,y,x+size,y+size,fill=color,outline='',tags='dynamic')
                edges = {'N':(x,y,x+size,y), 'S':(x,y+size,x+size,y+size),
                         'W':(x,y,x,y+size), 'E':(x+size,y,x+size,y+size)}
                if self._wall_states.get(pos) != cell.walls:
                    for item in self._wall_items.get(pos, []):
                        canvas.delete(item)
                    self._wall_items[pos] = [canvas.create_line(*edges[d], fill=C['wall'], width=2, tags='wall') for d in cell.walls]
                    self._wall_states[pos] = set(cell.walls)
        canvas.tag_raise('wall')
        if self.mode.get() == 'Play':
            for a,b in zip(self.trail,self.trail[1:]):
                canvas.create_line(*center(a),*center(b),fill='#b6c9cd',width=max(2,size*.12),tags='dynamic')
        for a,b in zip(self.overlay,self.overlay[1:]):
            canvas.create_line(*center(a),*center(b),fill=C['route'],width=max(3,size*.17), capstyle='round',tags='dynamic')
        x,y = center((0,0))
        canvas.create_oval(x-size*.22,y-size*.22,x+size*.22,y+size*.22,outline=C['accent'],width=2,tags='dynamic')
        x,y = center((self.maze.rows-1,self.maze.cols-1))
        canvas.create_text(x,y,text='E',fill=C['ink'],font=('DejaVu Sans',max(10,int(size*.65)),'bold'),tags='dynamic')
        x,y = center(self.player)
        radius = max(3,size*.19)
        canvas.create_oval(x-radius,y-radius,x+radius,y+radius,fill=C['player'],outline='white',width=1,tags='dynamic')
        self.metrics.set(f'Seed {self.active_seed}     Moves {self.moves}     Explored {self.visits}     Backtracks {self.retreats}     Hints {self.hints}')

    def close(self):
        self.closed = True
        self._cancel()
        self.root.destroy()
