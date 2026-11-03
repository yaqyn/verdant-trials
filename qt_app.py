"""Qt quest interface: play first, with a separate algorithm observation mode."""
from pathlib import Path
import secrets

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QFontDatabase, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox,
    QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton, QScrollArea,
    QSlider, QVBoxLayout, QWidget)

from levels import LEVELS
from maze import Maze
from qt_board import MazeBoard

ASSETS = Path(__file__).resolve().parent / 'assets'
PALETTES = {
    'dark': dict(bg='#101713', panel='#19231d', raised='#223027', ink='#f1ead8',
                 muted='#b4beaf', line='#354537', gold='#d8bf83', on_gold='#182018', error='#f2ab99'),
    'light': dict(bg='#e9e9df', panel='#f7f6ee', raised='#dedfd0', ink='#25382c',
                  muted='#56644f', line='#b4bba7', gold='#72541f', on_gold='#fffaf0', error='#9d3527')}


def stylesheet(mode):
    c = PALETTES[mode]
    return f'''
    QWidget {{ color: {c['ink']}; font-family: "DejaVu Sans"; font-size: 14px; }}
    QMainWindow, QWidget#shell {{ background: {c['bg']}; }}
    QFrame#questPanel {{ background: {c['panel']}; border: 1px solid {c['line']}; border-radius: 16px; }}
    QFrame#victory {{ background: {c['raised']}; border: 1px solid {c['gold']}; border-radius: 12px; }}
    QLabel {{ background: transparent; border: none; }}
    QLabel#brand {{ font-family: "Cinzel"; font-size: 27px; color: {c['gold']}; }}
    QLabel#chapterTitle {{ font-family: "Cinzel"; font-size: 24px; }}
    QLabel#sectionTitle {{ font-family: "Cinzel"; font-size: 18px; }}
    QLabel#muted, QLabel#metrics {{ color: {c['muted']}; font-size: 12px; }}
    QLabel#error {{ color: {c['error']}; font-size: 12px; }}
    QLabel#status {{ font-size: 16px; font-weight: 600; }}
    QPushButton {{ background: {c['raised']}; border: 1px solid {c['line']};
        border-radius: 9px; padding: 10px 14px; min-height: 19px; }}
    QPushButton:hover {{ border-color: {c['gold']}; }}
    QPushButton:pressed {{ background: {c['panel']}; }}
    QPushButton:focus {{ border: 2px solid {c['gold']}; padding: 9px 13px; }}
    QPushButton:disabled {{ color: {c['muted']}; background: {c['panel']}; border-color: {c['line']}; }}
    QPushButton#primary, QPushButton:checked {{ background: {c['gold']}; color: {c['on_gold']}; border-color: {c['gold']}; }}
    QPushButton#primary:disabled {{ background: {c['raised']}; color: {c['muted']}; border-color: {c['line']}; }}
    QPushButton#quiet {{ background: transparent; border-color: transparent; text-align: left; padding-left: 0; }}
    QComboBox, QLineEdit {{ background: {c['bg']}; border: 1px solid {c['line']};
        border-radius: 8px; padding: 9px 11px; min-height: 20px; selection-background-color: {c['gold']}; }}
    QComboBox:focus, QLineEdit:focus {{ border-color: {c['gold']}; }}
    QComboBox::drop-down {{ border: none; width: 28px; }}
    QComboBox::down-arrow {{ image: url({(ASSETS / 'icons/chevron-down.svg').as_posix()}); width: 12px; height: 8px; }}
    QComboBox QAbstractItemView {{ background: {c['panel']}; color: {c['ink']};
        selection-background-color: {c['raised']}; border: 1px solid {c['line']}; padding: 5px; }}
    QSlider::groove:horizontal {{ height: 4px; background: {c['line']}; border-radius: 2px; }}
    QSlider::sub-page:horizontal {{ background: {c['gold']}; border-radius: 2px; }}
    QSlider::handle:horizontal {{ width: 16px; height: 16px; margin: -6px 0; background: {c['gold']}; border-radius: 8px; }}
    QScrollArea {{ border: none; background: transparent; }}
    QScrollArea > QWidget > QWidget {{ background: transparent; }}
    QScrollBar:vertical {{ background: {c['panel']}; width: 8px; margin: 0; border-radius: 4px; }}
    QScrollBar::handle:vertical {{ background: {c['line']}; min-height: 30px; border-radius: 4px; }}
    QScrollBar::handle:vertical:hover {{ background: {c['gold']}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
    QCheckBox {{ spacing: 8px; }}
    QCheckBox::indicator {{ width: 15px; height: 15px; border: 1px solid {c['line']}; border-radius: 4px; background: {c['bg']}; }}
    QCheckBox::indicator:checked {{ background: {c['gold']}; }}
    '''


class QuestWindow(QMainWindow):
    def __init__(self, level_id=1, seed=None, delay=180):
        super().__init__()
        QFontDatabase.addApplicationFont(str(ASSETS / 'fonts/Cinzel.ttf'))
        self.setWindowTitle('Maze Runner — The Verdant Trials')
        self.setWindowIcon(QIcon(str(ASSETS / 'icons/compass.svg')))
        self.resize(1360, 900)
        self.setMinimumSize(1000, 720)
        self.level_index = next((i for i, l in enumerate(LEVELS) if l.id == level_id), 0)
        self.mode = 'Play'
        self.theme = 'dark'
        self.phase = 'idle'
        self.paused = False
        self.closed = False
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._tick)
        self._build(delay)
        self.seed_input.setText('' if seed is None else str(seed))
        self.change_theme('dark')
        self.new_maze()

    def _label(self, text='', role='', wrap=False):
        label = QLabel(text)
        if role:
            label.setObjectName(role)
        label.setWordWrap(wrap)
        return label

    def _button(self, text, handler, primary=False):
        button = QPushButton(text)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(handler)
        if primary:
            button.setObjectName('primary')
        return button

    def _build(self, delay):
        shell = QWidget()
        shell.setObjectName('shell')
        self.setCentralWidget(shell)
        layout = QVBoxLayout(shell)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(20)
        top = QHBoxLayout()
        brand_group = QVBoxLayout()
        brand_group.setSpacing(3)
        brand_group.addWidget(self._label('Maze Runner', 'brand'))
        brand_group.addWidget(self._label('The Verdant Trials', 'muted'))
        top.addLayout(brand_group)
        top.addStretch()
        self.mode_group = QButtonGroup(self)
        self.play_button = self._button('Play', lambda: self.set_mode('Play'))
        self.observe_button = self._button('Observe', lambda: self.set_mode('Observe'))
        for button in (self.play_button, self.observe_button):
            button.setCheckable(True)
            button.setMinimumWidth(105)
            self.mode_group.addButton(button)
            top.addWidget(button)
        self.play_button.setChecked(True)
        top.addSpacing(16)
        self.theme_button = self._button('Daylight', lambda: self.change_theme('light' if self.theme == 'dark' else 'dark'))
        top.addWidget(self.theme_button)
        layout.addLayout(top)
        content = QHBoxLayout()
        content.setSpacing(22)
        layout.addLayout(content, 1)
        field = QVBoxLayout()
        field.setSpacing(10)
        self.chapter_title = self._label('', 'chapterTitle')
        field.addWidget(self.chapter_title)
        self.status_label = self._label('', 'status', True)
        field.addWidget(self.status_label)
        self.board = MazeBoard()
        self.board.moved.connect(self.move)
        field.addWidget(self.board, 1)
        self.metrics_label = self._label('', 'metrics', True)
        field.addWidget(self.metrics_label)
        self.legend = self._label('Arrows / WASD to move    H for a hint    Gold marks guidance', 'muted', True)
        field.addWidget(self.legend)
        content.addLayout(field, 1)
        panel = QFrame()
        panel.setObjectName('questPanel')
        panel.setFixedWidth(310)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 20, 18, 20)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        panel_layout.addWidget(scroll)
        inner = QWidget()
        right = QVBoxLayout(inner)
        right.setContentsMargins(0, 0, 5, 0)
        right.setSpacing(14)
        scroll.setWidget(inner)
        right.addWidget(self._label('Quest journal', 'sectionTitle'))
        self.chapter_box = QComboBox()
        self.chapter_box.setAccessibleName('Quest chapter')
        self.chapter_box.addItems([f'{l.id}. {l.title}' for l in LEVELS])
        self.chapter_box.setCurrentIndex(self.level_index)
        self.chapter_box.currentIndexChanged.connect(self._chapter_changed)
        right.addWidget(self.chapter_box)
        self.description_label = self._label('', 'muted', True)
        right.addWidget(self.description_label)
        self.play_panel = QWidget()
        play_layout = QVBoxLayout(self.play_panel)
        play_layout.setContentsMargins(0, 0, 0, 0)
        play_layout.setSpacing(9)
        self.hint_button = self._button('Lantern hint', self.hint, True)
        self.hint_button.setIcon(QIcon(str(ASSETS / 'icons/lantern.svg')))
        self.reveal_button = self._button('Reveal the route', self.reveal)
        play_layout.addWidget(self.hint_button)
        play_layout.addWidget(self.reveal_button)
        play_layout.addWidget(self._label('Find the gate. Hints show one safe step; revealing the route counts as assistance.', 'muted', True))
        right.addWidget(self.play_panel)
        self.observe_panel = QWidget()
        observe_layout = QVBoxLayout(self.observe_panel)
        observe_layout.setContentsMargins(0, 0, 0, 0)
        observe_layout.setSpacing(9)
        observe_layout.addWidget(self._label('Search algorithm', 'muted'))
        self.algorithm_box = QComboBox()
        self.algorithm_box.setAccessibleName('Search algorithm')
        self.algorithm_box.addItems(['Depth-first search', 'Breadth-first search'])
        observe_layout.addWidget(self.algorithm_box)
        self.run_button = self._button('Run search', self.run_search, True)
        observe_layout.addWidget(self.run_button)
        right.addWidget(self.observe_panel)
        self.pacing_panel = QWidget()
        pacing = QVBoxLayout(self.pacing_panel)
        pacing.setContentsMargins(0, 0, 0, 0)
        pacing.setSpacing(8)
        row = QHBoxLayout()
        self.pause_button = self._button('Pause', self.toggle_pause)
        self.step_button = self._button('Step', self.single_step)
        row.addWidget(self.pause_button)
        row.addWidget(self.step_button)
        pacing.addLayout(row)
        self.pace_label = self._label('', 'muted')
        pacing.addWidget(self.pace_label)
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(30, 600)
        self.speed_slider.setValue(max(30, min(600, delay)))
        self.speed_slider.setAccessibleName('Animation delay; right is slower')
        self.speed_slider.valueChanged.connect(self._pace_changed)
        pacing.addWidget(self.speed_slider)
        presets = QHBoxLayout()
        for text, ms in [('Fast', 60), ('Normal', 180), ('Slow', 400)]:
            presets.addWidget(self._button(text, lambda checked=False, value=ms: self.speed_slider.setValue(value)))
        pacing.addLayout(presets)
        self.skip_button = self._button('Enter maze now', self.skip_generation)
        pacing.addWidget(self.skip_button)
        right.addWidget(self.pacing_panel)
        self.victory = QFrame()
        self.victory.setObjectName('victory')
        victory_layout = QVBoxLayout(self.victory)
        victory_layout.setSpacing(10)
        victory_layout.addWidget(self._label('Quest complete', 'sectionTitle'))
        self.victory_text = self._label('', '', True)
        victory_layout.addWidget(self.victory_text)
        self.next_button = self._button('Next chapter', self.next_level, True)
        victory_layout.addWidget(self.next_button)
        right.addWidget(self.victory)
        self.new_button = self._button('Begin a new quest', self.new_maze)
        right.addWidget(self.new_button)
        self.advanced_button = self._button('World settings +', self._toggle_advanced)
        self.advanced_button.setObjectName('quiet')
        right.addWidget(self.advanced_button)
        self.advanced = QWidget()
        advanced = QVBoxLayout(self.advanced)
        advanced.setContentsMargins(0, 0, 0, 0)
        advanced.setSpacing(8)
        advanced.addWidget(self._label('World seed · blank for random', 'muted'))
        self.seed_input = QLineEdit()
        self.seed_input.setPlaceholderText('e.g. 42')
        self.seed_input.setAccessibleName('World seed')
        self.seed_input.returnPressed.connect(self.new_maze)
        advanced.addWidget(self.seed_input)
        self.reduced_motion = QCheckBox('Reduce movement animation')
        self.reduced_motion.toggled.connect(self._motion_changed)
        advanced.addWidget(self.reduced_motion)
        right.addWidget(self.advanced)
        self.advanced.hide()
        self.error_label = self._label('', 'error', True)
        right.addWidget(self.error_label)
        right.addStretch()
        right.addWidget(self._label('Wayfinder’s notes', 'sectionTitle'))
        self.notes_label = self._label('', 'muted', True)
        right.addWidget(self.notes_label)
        content.addWidget(panel)
        self.hint_shortcut = QShortcut(QKeySequence('H'), self.board)
        self.hint_shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
        self.hint_shortcut.activated.connect(self._hint_shortcut)
        self.pause_shortcut = QShortcut(QKeySequence('Space'), self.board)
        self.pause_shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
        self.pause_shortcut.activated.connect(self._pause_shortcut)
        self._pace_changed()

    def _toggle_advanced(self):
        visible = not self.advanced.isVisible()
        self.advanced.setVisible(visible)
        self.advanced_button.setText('World settings −' if visible else 'World settings +')

    def _motion_changed(self, enabled):
        self.board.reduced_motion = enabled or self.mode == 'Observe'
        self._refresh()

    def _hint_shortcut(self):
        if not isinstance(QApplication.focusWidget(), QLineEdit):
            self.hint()

    def _pause_shortcut(self):
        if not isinstance(QApplication.focusWidget(), (QLineEdit, QComboBox, QPushButton)):
            self.toggle_pause()

    def _chapter_changed(self, index):
        previous = self.level_index
        self.level_index = index
        if not self.new_maze():
            self.level_index = previous
            self.chapter_box.blockSignals(True)
            self.chapter_box.setCurrentIndex(previous)
            self.chapter_box.blockSignals(False)

    def _pace_changed(self, value=None):
        ms = self.speed_slider.value()
        self.pace_label.setText(f'{ms} ms per step · right is slower')
        if self.timer.isActive():
            self.timer.start(ms)

    def change_theme(self, mode=None):
        self.theme = mode if mode in PALETTES else ('light' if self.theme == 'dark' else 'dark')
        self.setStyleSheet(stylesheet(self.theme))
        self.theme_button.setText('Daylight' if self.theme == 'dark' else 'Dark forest')
        self.board.set_theme(self.theme)

    def new_maze(self):
        raw = self.seed_input.text().strip()
        try:
            if len(raw) > 20:
                raise ValueError
            seed = int(raw) if raw else secrets.randbelow(1_000_000_000)
        except ValueError:
            self.error_label.setText('Use a whole-number seed, up to 20 characters.')
            self.advanced.show()
            self.seed_input.setFocus()
            return False
        self.error_label.clear()
        self.timer.stop()
        level = LEVELS[self.level_index]
        self.active_seed = seed
        self.maze = Maze(level.rows, level.cols, seed)
        self.steps = self.maze.generate()
        self.phase, self.paused = 'generating', False
        self.player = (0, 0)
        self.trail, self.overlay = [self.player], []
        self.explored, self.backtracked = set(), set()
        self.moves = self.hints = self.visits = self.retreats = 0
        self.carved = 0
        self.chapter_title.setText(level.title)
        self.description_label.setText(f'Chapter {level.id} of {len(LEVELS)} · {level.rows} × {level.cols}\n{level.description}')
        self.status_label.setText('The forest is opening a path…')
        self.notes_label.setText('Generation removes a wall only when reaching a new cell. Every cell becomes connected, with one route between any pair.')
        self._refresh()
        self._tick()
        return True

    def set_mode(self, mode):
        if mode not in ('Play', 'Observe'):
            return
        if mode == self.mode:
            return
        self.mode = mode
        self.play_button.setChecked(mode == 'Play')
        self.observe_button.setChecked(mode == 'Observe')
        if self.phase != 'generating':
            self.timer.stop()
            self.phase, self.paused = 'ready', False
            self.player = (0, 0)
            self.trail, self.overlay = [self.player], []
            self.explored.clear()
            self.backtracked.clear()
            self.moves = self.hints = self.visits = self.retreats = 0
            self._ready_message()
        self._refresh()
        self.board.setFocus()

    def _ready_message(self):
        self.status_label.setText('Find the ancient gate.' if self.mode == 'Play' else 'Choose a search and watch its decisions.')
        self.notes_label.setText(LEVELS[self.level_index].concept)

    def _refresh(self):
        active = self.phase in ('generating', 'searching')
        ready = self.phase == 'ready'
        self.play_panel.setVisible(self.mode == 'Play' and self.phase != 'complete')
        self.observe_panel.setVisible(self.mode == 'Observe')
        self.pacing_panel.setVisible(active or self.mode == 'Observe')
        self.victory.setVisible(self.phase == 'complete')
        self.hint_button.setEnabled(ready and self.mode == 'Play')
        self.reveal_button.setEnabled(ready and self.mode == 'Play')
        self.run_button.setEnabled(self.phase in ('ready', 'complete'))
        self.run_button.setText('Replay search' if self.phase == 'complete' else 'Run search')
        self.algorithm_box.setEnabled(self.phase != 'searching')
        self.pause_button.setEnabled(active)
        self.pause_button.setText('Resume' if self.paused else 'Pause')
        self.step_button.setEnabled(active)
        self.skip_button.setVisible(self.phase == 'generating')
        self.next_button.setEnabled(self.level_index < len(LEVELS)-1)
        self.next_button.setText('Next chapter' if self.level_index < len(LEVELS)-1 else 'Final chapter complete')
        self.legend.setText('Arrows / WASD to move    H for a hint    Gold marks guidance' if self.mode == 'Play'
                            else 'Gold: current route    Blue: explored    Ash: backtracked    Space: pause')
        self.metrics_label.setText(f'World seed {self.active_seed}    Moves {self.moves}    Explored {self.visits}    Backtracks {self.retreats}    Hints {self.hints}')
        self.board.reduced_motion = self.reduced_motion.isChecked() or self.mode == 'Observe'
        self.board.set_state(self.maze, self.player, self.trail, self.overlay,
                             self.explored, self.backtracked, self.phase == 'complete')

    def _tick(self):
        if self.closed or self.paused:
            return
        if self._advance():
            delay = self.speed_slider.value()
            if getattr(self, 'last_action', '') == 'backtrack' and self.phase == 'searching':
                delay = round(delay*1.4)
            self.timer.start(delay)

    def _advance(self):
        try:
            event = next(self.steps)
        except StopIteration:
            self.timer.stop()
            if self.phase == 'generating':
                self.phase = 'ready'
                self._ready_message()
                self.board.setFocus()
            else:
                self.phase = 'complete'
                self.overlay = list(self.maze.path)
                self.status_label.setText('The search found the gate.')
                self.victory_text.setText(f'{max(0, len(self.overlay)-1)} steps in the route.\n{self.visits} cells explored; {self.retreats} backtracks.')
                self.notes_label.setText('This maze is a tree: there is one route between any pair of cells. DFS and BFS find the same route, but explore in a different order.')
            self._refresh()
            return False
        if self.phase == 'generating':
            self.carved += 1
            self.status_label.setText(f'The forest is opening a path… {self.carved} / {self.maze.rows*self.maze.cols} cells')
        if self.phase == 'searching':
            action, position = event
            self.last_action = action
            self.overlay = list(self.maze.path)
            if action == 'visit':
                self.player = position
                self.explored.add(position)
                self.visits += 1
                self.notes_label.setText('Visit a new cell. ' + ('BFS takes the oldest cell from its queue, exploring by distance.' if self.algorithm_box.currentIndex() else 'DFS follows a branch, remembering the route in a stack.'))
            elif action == 'backtrack':
                self.retreats += 1
                self.backtracked.add(position)
                if self.maze.path:
                    self.player = self.maze.path[-1]
                self.notes_label.setText('A dead end: return to the previous cell and look for an unexplored branch.')
        self._refresh()
        return True

    def skip_generation(self):
        if self.phase != 'generating':
            return
        self.timer.stop()
        for _ in self.steps:
            pass
        self.paused = False
        self._advance()

    def run_search(self):
        if self.mode != 'Observe' or self.phase not in ('ready', 'complete'):
            return
        self.timer.stop()
        self.steps = self.maze.solve('bfs' if self.algorithm_box.currentIndex() else 'dfs')
        self.phase, self.paused = 'searching', False
        self.explored.clear()
        self.backtracked.clear()
        self.overlay = []
        self.visits = self.retreats = 0
        self.last_action = ''
        self.status_label.setText(f'Exploring with {self.algorithm_box.currentText().lower()}…')
        self._tick()

    def toggle_pause(self):
        if self.phase not in ('generating', 'searching'):
            return
        self.paused = not self.paused
        self.timer.stop()
        self._refresh()
        if not self.paused:
            self._tick()

    def single_step(self):
        if self.phase not in ('generating', 'searching'):
            return
        self.timer.stop()
        self.paused = True
        self._advance()
        self._refresh()

    def move(self, direction):
        if self.mode != 'Play' or self.phase != 'ready':
            return
        if not self.maze.can_move(self.player, direction):
            self.status_label.setText('Stone blocks the way. Try another passage.')
            return
        dr, dc = {'N':(-1,0), 'S':(1,0), 'W':(0,-1), 'E':(0,1)}[direction]
        self.player = self.player[0]+dr, self.player[1]+dc
        self.trail.append(self.player)
        self.overlay = []
        self.moves += 1
        self.status_label.setText('Follow the passages to the gate.')
        if self.player == (self.maze.rows-1, self.maze.cols-1):
            self.phase = 'complete'
            direct = len(self.maze.route_from((0,0)))-1
            self.status_label.setText('You found the exit. The gate is open.')
            self.victory_text.setText(f'{self.moves} moves · direct route {direct}\n{self.hints} hints used' + ('\nAn unaided journey.' if self.hints == 0 else '\nThe lantern helped you find your way.'))
            self.notes_label.setText('Continue to the next chapter, or switch to Observe to compare your route with a search algorithm.')
        self._refresh()

    def hint(self):
        if self.mode != 'Play' or self.phase != 'ready':
            return
        self.hints += 1
        self.overlay = self.maze.route_from(self.player)[:2]
        self.status_label.setText('The lantern lights your next step.')
        self._refresh()
        self.board.setFocus()

    def reveal(self):
        if self.mode != 'Play' or self.phase != 'ready':
            return
        self.hints += 1
        self.overlay = self.maze.route_from(self.player)
        self.status_label.setText('The route is revealed. Follow the golden thread.')
        self._refresh()
        self.board.setFocus()

    def next_level(self):
        if self.level_index < len(LEVELS)-1:
            self.chapter_box.setCurrentIndex(self.level_index+1)

    def closeEvent(self, event):
        self.closed = True
        self.timer.stop()
        super().closeEvent(event)
