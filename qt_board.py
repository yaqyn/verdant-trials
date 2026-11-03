"""Immersive, resolution-independent Qt maze board and movement animation."""
from pathlib import Path
from random import Random

from PySide6.QtCore import QByteArray, QEasingCurve, QPointF, Property, QPropertyAnimation, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QBrush, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QPolygonF, QRadialGradient
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget

ASSETS = Path(__file__).resolve().parent / 'assets'


def cover_source_rect(image_width, image_height, target_width, target_height):
    """Center-crop an image to fill a target without distorting its proportions.

    Cropping happens in source-image coordinates. Both image axes receive the
    same scale when Qt paints this rectangle into the target viewport.
    """
    if min(image_width, image_height, target_width, target_height) <= 0:
        raise ValueError('Image and target dimensions must be positive')
    scale = max(target_width / image_width, target_height / image_height)
    width, height = target_width / scale, target_height / scale
    return QRectF((image_width-width)/2, (image_height-height)/2, width, height)


BOARD_COLORS = {
    'dark': dict(base=(81, 77, 63), border='#a0a183', stone='#a1a48b',
                 highlight='#d2cfb2', moss='#829268', trail='#929f7a', route='#f3d491',
                 marker='#f6dfae', marker_edge='#fff8e0', origin='#e6ce8e'),
    'light': dict(base=(189, 191, 163), border='#697c5b', stone='#55674f',
                  highlight='#97aa7f', moss='#748e61', trail='#81926d', route='#65511d',
                  marker='#5c793b', marker_edge='#f6f3d5', origin='#526733'),
}


class MazeBoard(QWidget):
    """Paint the world while leaving movement rules and scheduling to its owner."""

    moved = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName('Quest maze')
        self.setAccessibleDescription('Move with arrow keys or W A S D. Reach the enchanted waygate.')
        self.setMinimumSize(440, 340)
        self.maze = None
        self.player = (0, 0)
        self.trail, self.overlay = [], []
        self.explored, self.backtracked = set(), set()
        self.complete = False
        self.reduced_motion = False
        self.mode = 'dark'
        self._visual_position = QPointF(0, 0)
        self._static_key = None
        self._static = QPixmap()
        self._frame = QPixmap(str(ASSETS / 'verdant-world.png'))
        self._gate = QSvgRenderer(str(ASSETS / 'icons/waygate.svg'), self)
        self._walls = {}
        self._tiles = {}
        for mode, colors in BOARD_COLORS.items():
            renderers = []
            for filename in ('stone-wall.svg', 'stone-wall-vertical.svg'):
                data = (ASSETS / 'walls' / filename).read_bytes()
                for source, role in ((b'#56604e', 'stone'), (b'#9b9875', 'highlight'),
                                     (b'#73805a', 'moss')):
                    data = data.replace(source, colors[role].encode())
                renderers.append(QSvgRenderer(QByteArray(data), self))
            self._walls[mode] = renderers
            self._tiles[mode] = self._make_texture(colors['base'])
        self._animation = QPropertyAnimation(self, b'visualPosition', self)
        self._animation.setDuration(105)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def minimumSizeHint(self):
        return QSize(500, 400)

    def sizeHint(self):
        return QSize(920, 650)

    def _get_visual_position(self):
        return self._visual_position

    def _set_visual_position(self, value):
        self._visual_position = value
        self.update()

    visualPosition = Property(QPointF, _get_visual_position, _set_visual_position)

    def set_theme(self, mode):
        if mode not in BOARD_COLORS:
            raise ValueError('Board theme must be dark or light')
        self.mode = mode
        self._static_key = None
        self.update()

    def set_state(self, maze, player, trail, overlay, explored, backtracked, complete=False):
        changed_board = maze is not self.maze
        previous = self.player
        self.maze, self.player = maze, tuple(player)
        self.trail, self.overlay = list(trail), list(overlay)
        self.explored, self.backtracked = set(explored), set(backtracked)
        self.complete = complete
        target = QPointF(player[1], player[0])
        if changed_board or self.reduced_motion:
            self._animation.stop()
            self._set_visual_position(target)
        elif previous != self.player:
            self._animation.stop()
            # Finish the preceding cell transition before turning a corner.
            # Interpolating directly from a half-finished move can cut a wall.
            origin = QPointF(previous[1], previous[0])
            self._set_visual_position(origin)
            adjacent = abs(previous[0]-player[0])+abs(previous[1]-player[1]) == 1
            if adjacent:
                self._animation.setStartValue(origin)
                self._animation.setEndValue(target)
                self._animation.start()
            else:
                # BFS frontiers jump between branches; never animate through walls.
                self._set_visual_position(target)
        self.update()

    @staticmethod
    def _make_texture(base):
        tile = QPixmap(96, 96)
        tile.fill(QColor(*base))
        painter = QPainter(tile)
        rng = Random(731)
        for y in range(96):
            for x in range(96):
                n = rng.choice((-2, -1, 0, 0, 0, 1, 2))
                painter.setPen(QColor(*(channel+n for channel in base)))
                painter.drawPoint(x, y)
        painter.end()
        return tile

    def _geometry(self):
        area = QRectF(0, 0, self.width(), self.height())
        if self.maze is None:
            return area, QRectF(), 0
        size = min(self.width()*.80/self.maze.cols, self.height()*.74/self.maze.rows)
        board = QRectF((self.width()-size*self.maze.cols)/2,
                       (self.height()-size*self.maze.rows)/2,
                       size*self.maze.cols, size*self.maze.rows)
        return area, board, size

    def _center(self, position, board, size):
        row, col = position
        return QPointF(board.left()+(col+.5)*size, board.top()+(row+.5)*size)

    def _cache_static(self, area, board, size):
        signature = tuple(frozenset(cell.walls) for row in self.maze.grid for cell in row)
        key = (self.width(), self.height(), self.devicePixelRatioF(), id(self.maze), signature, self.mode)
        if key == self._static_key:
            return
        self._static_key = key
        ratio = self.devicePixelRatioF()
        self._static = QPixmap(round(self.width()*ratio), round(self.height()*ratio))
        self._static.setDevicePixelRatio(ratio)
        self._static.fill(QColor('#101914'))
        p = QPainter(self._static)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if not self._frame.isNull():
            source = cover_source_rect(self._frame.width(), self._frame.height(),
                                       area.width(), area.height())
            p.drawPixmap(area, self._frame, source)
        colors = BOARD_COLORS[self.mode]
        # A softly shadowed map floats above the scenery; only the landscape is
        # cropped on resize. The maze always keeps square cells and its own fit.
        p.setPen(Qt.PenStyle.NoPen)
        for inset in range(10, 2, -2):
            p.setBrush(QColor(16, 38, 24, 12))
            p.drawRoundedRect(board.adjusted(-inset, -inset+4, inset, inset+4), 8, 8)
        p.fillRect(board.adjusted(-3, -3, 3, 3), QBrush(self._tiles[self.mode]))
        p.setPen(QPen(QColor(colors['border']), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(board.adjusted(-3, -3, 3, 3))
        width = max(2.0, min(6.0, size*.11))
        p.setPen(QPen(QColor(0, 0, 0, 145), width+2, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        edges = []
        for r, row in enumerate(self.maze.grid):
            for c, cell in enumerate(row):
                x, y = board.left()+c*size, board.top()+r*size
                candidates = {'N': (x,y,x+size,y), 'W': (x,y,x,y+size)}
                if r == self.maze.rows-1:
                    candidates['S'] = (x,y+size,x+size,y+size)
                if c == self.maze.cols-1:
                    candidates['E'] = (x+size,y,x+size,y+size)
                edges.extend((direction, coords) for direction, coords in candidates.items()
                             if direction in cell.walls)
        for _, (x1,y1,x2,y2) in edges:
            p.drawLine(QPointF(x1+2,y1+3), QPointF(x2+2,y2+3))
        for direction, (x1,y1,x2,y2) in edges:
            if direction in ('N', 'S'):
                self._walls[self.mode][0].render(p, QRectF(x1,y1-width/2,size,width))
            else:
                self._walls[self.mode][1].render(p, QRectF(x1-width/2,y1,width,size))
        p.end()

    def _draw_route(self, painter, route, board, size, color, width):
        if len(route) < 2:
            return
        path = QPainterPath(self._center(route[0], board, size))
        for position in route[1:]:
            path.lineTo(self._center(position, board, size))
        painter.setPen(QPen(QColor(color), width, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(path)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        area, board, size = self._geometry()
        if self.maze is None:
            p.fillRect(area, QColor('#101914'))
            return
        self._cache_static(area, board, size)
        p.drawPixmap(0, 0, self._static)
        # Insets keep search shading away from the stone edges.
        inset = max(2, size*.11)
        for positions, color in ((self.explored, QColor(85, 138, 143, 65)),
                                 (self.backtracked, QColor(154, 118, 86, 80))):
            for r,c in positions:
                p.fillRect(QRectF(board.left()+c*size+inset, board.top()+r*size+inset,
                                  max(0,size-inset*2), max(0,size-inset*2)), color)
        colors = BOARD_COLORS[self.mode]
        self._draw_route(p, self.trail, board, size, colors['trail'], max(1.5,size*.08))
        self._draw_route(p, self.overlay, board, size, colors['route'], max(2,size*.12))
        origin = self._center((0,0), board, size)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(colors['origin']), 1.5))
        radius = min(15, size*.25)
        p.drawEllipse(origin, radius, radius)
        goal = self._center((self.maze.rows-1,self.maze.cols-1), board, size)
        icon = min(34, max(8,size*.72))
        self._gate.render(p, QRectF(goal.x()-icon/2, goal.y()-icon/2,icon,icon))
        position = self._visual_position
        center = QPointF(board.left()+(position.x()+.5)*size,
                         board.top()+(position.y()+.5)*size)
        radius = max(3.0, min(10.0,size*.16))
        glow = QRadialGradient(center, radius*3)
        glow.setColorAt(0,QColor(244,207,123,155))
        glow.setColorAt(1,QColor(244,207,123,0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(center,radius*3,radius*3)
        diamond = QPolygonF([QPointF(center.x(),center.y()-radius),
                             QPointF(center.x()+radius*.7,center.y()),
                             QPointF(center.x(),center.y()+radius),
                             QPointF(center.x()-radius*.7,center.y())])
        p.setBrush(QColor(colors['marker']))
        p.setPen(QPen(QColor(colors['marker_edge']),1))
        p.drawPolygon(diamond)
        if self.hasFocus():
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor('#a48b55'),1))
            p.drawRoundedRect(area.adjusted(1,1,-1,-1),10,10)

    def mousePressEvent(self, event):
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        keys = {Qt.Key.Key_Up:'N', Qt.Key.Key_W:'N', Qt.Key.Key_Down:'S', Qt.Key.Key_S:'S',
                Qt.Key.Key_Left:'W', Qt.Key.Key_A:'W', Qt.Key.Key_Right:'E', Qt.Key.Key_D:'E'}
        if event.key() in keys:
            self.moved.emit(keys[event.key()])
            event.accept()
        else:
            super().keyPressEvent(event)

    def hideEvent(self, event):
        self._animation.stop()
        super().hideEvent(event)
