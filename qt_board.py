"""Top-down castle cutaway with cached masonry and wall-aware 2D lighting."""
import math
from pathlib import Path
from random import Random
import time

from PySide6.QtCore import QEasingCurve, QPointF, Property, QPropertyAnimation, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QBrush, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QPolygonF, QRadialGradient
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget
from lighting import wall_segments, visibility_polygon, visible_cells, lamp_positions

ASSETS = Path(__file__).resolve().parent / 'assets'


def cover_source_rect(image_width, image_height, target_width, target_height):
    """Fill by centered cropping with identical scaling on both image axes."""
    if min(image_width, image_height, target_width, target_height) <= 0:
        raise ValueError('Image and target dimensions must be positive')
    scale = max(target_width / image_width, target_height / image_height)
    width, height = target_width / scale, target_height / scale
    return QRectF((image_width-width)/2, (image_height-height)/2, width, height)


BOARD_COLORS = {
    'dark': dict(base=(83, 81, 73), border='#817f70', stone='#989384', highlight='#c9c1aa',
                 side='#454a47', seam='#55564f', trail='#899982', route='#f3d491',
                 marker='#78a794', origin='#e6ce8e'),
    'light': dict(base=(177, 174, 154), border='#777a6b', stone='#a2a292', highlight='#d8d5bf',
                  side='#5c655c', seam='#787d70', trail='#799271', route='#685020',
                  marker='#3c7869', origin='#526733'),
}


class MazeBoard(QWidget):
    """Render a castle plan; traversal and movement rules remain in the engine."""
    moved = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName('Quest maze')
        self.setAccessibleDescription('Top-down castle corridors. Move with arrow keys or W A S D to the waygate.')
        self.setMinimumSize(440, 340)
        self.maze = None
        self.player = (0, 0)
        self.trail, self.overlay = [], []
        self.explored, self.backtracked = set(), set()
        self.complete = False
        self.reduced_motion = False
        self.mode = 'dark'
        self.scene_ready = False
        self.play_mode = True
        self.fog_enabled = False
        self.ambient_motion = True
        self.discovered = set()
        self.visible = set()
        self.lamps = []
        self._segments = ()
        self._light_polygons = []
        self._visibility_key = None
        self._scene_key = None
        self._scene_started = time.monotonic()
        self._facing = (0, 1)
        self._visual_position = QPointF(0, 0)
        self._static_key = None
        self._static = QPixmap()
        self._masonry = QPixmap()
        self._wallpapers = {name: QPixmap(str(ASSETS / filename)) for name, filename in
                            (('light', 'verdant-world.png'), ('dark', 'verdant-night.png'))}
        self._frame = self._wallpapers[self.mode]
        self._gate = QSvgRenderer(str(ASSETS / 'icons/waygate.svg'), self)
        self._animation = QPropertyAnimation(self, b'visualPosition', self)
        self._animation.setDuration(105)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.effects_timer = QTimer(self)
        self.effects_timer.setInterval(33)
        self.effects_timer.timeout.connect(self.update)
        self._effects_timer = self.effects_timer

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

    def configure_scene(self, ready, play_mode, fog_enabled=True, ambient_motion=True):
        """Configure presentation before set_state without restarting steady lamps."""
        if self.play_mode != play_mode:
            self.discovered.clear()
            self._visibility_key = None
        if ready and not self.scene_ready:
            self._scene_started = time.monotonic()
            self._scene_key = None
        if not ready:
            self.lamps = []
            self._light_polygons = []
            self.discovered.clear()
            self.visible.clear()
            self._scene_key = None
        self.scene_ready, self.play_mode = bool(ready), bool(play_mode)
        self.fog_enabled, self.ambient_motion = bool(fog_enabled), bool(ambient_motion)
        self._sync_effects_timer()

    def _sync_effects_timer(self):
        active = self.isVisible() and self.scene_ready and self.ambient_motion and not self.reduced_motion
        if active and not self.effects_timer.isActive():
            self.effects_timer.start()
        elif not active:
            self.effects_timer.stop()

    def set_theme(self, mode):
        if mode not in BOARD_COLORS:
            raise ValueError('Board theme must be dark or light')
        self.mode = mode
        self._frame = self._wallpapers[mode]
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
        if changed_board:
            self.discovered.clear()
            self.visible.clear()
            self._scene_key = self._visibility_key = None
            self._scene_started = time.monotonic()
        if changed_board or self.reduced_motion or not self.play_mode:
            self._animation.stop()
            self._set_visual_position(target)
        elif previous != self.player:
            self._animation.stop()
            origin = QPointF(previous[1], previous[0])
            self._set_visual_position(origin)
            self._facing = (player[0]-previous[0], player[1]-previous[1])
            if abs(self._facing[0])+abs(self._facing[1]) == 1:
                self._animation.setStartValue(origin)
                self._animation.setEndValue(target)
                self._animation.start()
            else:
                self._set_visual_position(target)
        if self.scene_ready:
            self._prepare_lighting()
        self._sync_effects_timer()
        self.update()

    def _prepare_lighting(self):
        key = (id(self.maze), tuple(frozenset(cell.walls) for row in self.maze.grid for cell in row))
        if self._scene_key != key:
            self._scene_key = key
            self._segments = wall_segments(self.maze)
            self.lamps = list(lamp_positions(self.maze, max_lamps=14))
            self._light_polygons = [visibility_polygon(pos, self._segments, 2.35, rays=64)
                                    for pos in self.lamps]
            self._visibility_key = None
        key = (self.player, tuple(self.overlay), self.play_mode)
        if self._visibility_key != key:
            self._visibility_key = key
            self.visible = visible_cells(self.maze, self.player, radius=3.4)
            self.discovered.update(self.visible)
            # Assistance deliberately reveals the requested route through the mist.
            self.discovered.update(self.overlay)
            self._player_polygon = visibility_polygon((self.player[1]+.5, self.player[0]+.5),
                                                        self._segments, 3.4, rays=96)

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

    def _point(self, position, board, size):
        x, y = position
        return QPointF(board.left()+x*size, board.top()+y*size)

    def _new_layer(self):
        ratio = self.devicePixelRatioF()
        image = QPixmap(round(self.width()*ratio), round(self.height()*ratio))
        image.setDevicePixelRatio(ratio)
        image.fill(Qt.GlobalColor.transparent)
        return image

    def _cache_static(self, area, board, size):
        signature = tuple(frozenset(cell.walls) for row in self.maze.grid for cell in row)
        key = (self.width(), self.height(), self.devicePixelRatioF(), id(self.maze), signature, self.mode)
        if key == self._static_key:
            return
        self._static_key = key
        self._static = self._new_layer()
        p = QPainter(self._static)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.fillRect(area, QColor('#1e2c29' if self.mode == 'dark' else '#dce4d6'))
        if not self._frame.isNull():
            source = cover_source_rect(self._frame.width(), self._frame.height(), area.width(), area.height())
            p.drawPixmap(area, self._frame, source)
        self._draw_floor(p, board, size)
        p.end()
        self._masonry = self._new_layer()
        p = QPainter(self._masonry)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._draw_walls(p, board, size)
        p.end()

    def _draw_floor(self, p, board, size):
        colors = BOARD_COLORS[self.mode]
        p.setPen(Qt.PenStyle.NoPen)
        for spread in (14, 10, 6):
            p.setBrush(QColor(8, 18, 14, 28))
            p.drawRoundedRect(board.adjusted(-spread, -spread+6, spread, spread+6), 5, 5)
        plinth = board.adjusted(-8, -8, 8, 8)
        gradient = QLinearGradient(plinth.topLeft(), plinth.bottomRight())
        gradient.setColorAt(0, QColor('#8b8d7a'))
        gradient.setColorAt(1, QColor('#424b43'))
        p.fillRect(plinth, gradient)
        p.fillRect(board, QColor(*colors['base']))
        rng = Random(719)
        tile = max(8, size*.5)
        for row in range(math.ceil(board.height()/tile)):
            for col in range(math.ceil(board.width()/tile)):
                x, y = board.left()+col*tile, board.top()+row*tile
                rectangle = QRectF(x, y, min(tile, board.right()-x), min(tile, board.bottom()-y))
                n = rng.randint(-7, 7)
                fill = QColor(*(max(0, min(255, channel+n)) for channel in colors['base']))
                p.fillRect(rectangle.adjusted(.55,.55,-.55,-.55), fill)
                p.setPen(QPen(QColor(20, 27, 23, 38), .8))
                p.drawRect(rectangle)
                p.setPen(QPen(QColor(240, 236, 213, 28), .6))
                p.drawLine(rectangle.topLeft()+QPointF(1,1),rectangle.topRight()+QPointF(-1,1))
                if rng.random() < .13 and tile > 15:
                    p.setPen(QPen(QColor(42, 47, 38, 38), .6))
                    a = rectangle.center()
                    p.drawLine(a, a+QPointF(tile*.18,-tile*.21))
        p.setPen(QPen(QColor(colors['border']), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(board)

    def _draw_walls(self, p, board, size):
        colors = BOARD_COLORS[self.mode]
        thickness = max(2.8, min(13, size*.17))
        height = max(2, min(8, size*.10))
        segments = wall_segments(self.maze)
        self._wall_width = thickness
        # Thick wall volumes: projected side, cap, bevel and mortar courses.
        for x1,y1,x2,y2 in segments:
            a, b = self._point((x1,y1),board,size), self._point((x2,y2),board,size)
            for spread, alpha in ((7,18),(4,32),(1,65)):
                p.setPen(QPen(QColor(5,12,9,alpha), thickness+spread,
                              Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap))
                p.drawLine(a+QPointF(height*.65,height+2),b+QPointF(height*.65,height+2))
        for x1,y1,x2,y2 in segments:
            a, b = self._point((x1,y1),board,size), self._point((x2,y2),board,size)
            p.setPen(QPen(QColor(colors['side']),thickness,Qt.PenStyle.SolidLine,Qt.PenCapStyle.SquareCap))
            p.drawLine(a+QPointF(0,height),b+QPointF(0,height))
            vertical = abs(x1-x2) < .01
            cap = QLinearGradient(a-QPointF(thickness/2,thickness/2),a+QPointF(thickness/2,thickness/2))
            cap.setColorAt(0,QColor(colors['highlight']))
            cap.setColorAt(.3,QColor(colors['stone']))
            cap.setColorAt(1,QColor(colors['side']))
            p.setPen(QPen(QBrush(cap),thickness,Qt.PenStyle.SolidLine,Qt.PenCapStyle.SquareCap))
            p.drawLine(a,b)
            p.setPen(QPen(QColor(colors['highlight']),max(.7,thickness*.10)))
            offset = QPointF(-thickness*.38,0) if vertical else QPointF(0,-thickness*.38)
            p.drawLine(a+offset,b+offset)
            p.setPen(QPen(QColor(colors['seam']),max(.65,thickness*.07)))
            courses = max(1,round(size/max(12,thickness*1.4)))
            for i in range(1,courses+1):
                t = i/courses
                center = a+(b-a)*t
                delta = QPointF(thickness*.40,0) if vertical else QPointF(0,thickness*.40)
                p.drawLine(center-delta,center+delta)

    def _draw_route(self, painter, route, board, size, color, width):
        if len(route) < 2:
            return
        path = QPainterPath(self._center(route[0], board, size))
        for position in route[1:]:
            path.lineTo(self._center(position, board, size))
        painter.setPen(QPen(QColor(color), width, Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(path)

    def _polygon_path(self, points, board, size):
        path = QPainterPath()
        if points:
            path.addPolygon(QPolygonF([self._point(pos,board,size) for pos in points]))
            path.closeSubpath()
        return path

    def _lamp_strength(self, index, elapsed):
        if self.reduced_motion or not self.ambient_motion:
            return 1.0
        fade = max(0.,min(1.,(elapsed-.18-index*.075)/1.1))
        return fade*fade*(3-2*fade)

    def _draw_lights(self, p, board, size):
        if not self.scene_ready:
            return
        elapsed = time.monotonic()-self._scene_started
        p.save()
        p.setClipRect(board)
        for index,(position,polygon) in enumerate(zip(self.lamps,self._light_polygons)):
            strength = self._lamp_strength(index,elapsed)
            if strength <= 0:
                continue
            center = self._point(position,board,size)
            oscillation = 0 if self.reduced_motion or not self.ambient_motion else math.sin(elapsed*1.3+index*2.1)*.025
            radius = size*2.35
            p.save()
            p.setClipPath(self._polygon_path(polygon,board,size), Qt.ClipOperation.IntersectClip)
            gradient = QRadialGradient(center+QPointF(oscillation*size*.12,oscillation*size*.08), radius)
            alpha = round((70 if self.mode == 'dark' else 37)*strength*(1+oscillation))
            gradient.setColorAt(0,QColor(255,203,105,alpha))
            gradient.setColorAt(.22,QColor(255,194,87,round(alpha*.72)))
            gradient.setColorAt(.62,QColor(249,178,68,round(alpha*.20)))
            gradient.setColorAt(1,QColor(255,184,79,0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(gradient)
            p.drawEllipse(center,radius,radius)
            p.restore()
        p.restore()

    def _draw_lamp_fixtures(self, p, board, size):
        if not self.scene_ready:
            return
        elapsed = time.monotonic()-self._scene_started
        for index,position in enumerate(self.lamps):
            strength = self._lamp_strength(index,elapsed)
            if strength <= 0:
                continue
            center = self._point(position,board,size)
            radius = max(1.7,min(5,size*.075))
            p.save()
            p.setOpacity(strength)
            p.setPen(QPen(QColor('#443c2b'),max(1,radius*.4)))
            p.setBrush(QColor('#78613e'))
            p.drawEllipse(center+QPointF(1,2),radius*1.4,radius*1.4)
            p.setBrush(QColor('#ffdc93'))
            p.setPen(QPen(QColor('#fff1c5'),.7))
            p.drawEllipse(center,radius,radius)
            p.restore()

    def _draw_fog(self, p, board, size):
        if not (self.scene_ready and self.play_mode and self.fog_enabled) or self.complete:
            return
        p.save()
        p.setClipRect(board.adjusted(-self._wall_width/2,-self._wall_width/2,self._wall_width/2,self._wall_width/2))
        all_area = QPainterPath()
        all_area.addRect(board.adjusted(-12,-12,12,12))
        known = QPainterPath()
        for r,c in self.discovered | set(self.trail) | set(self.overlay):
            known.addRect(QRectF(board.left()+c*size,board.top()+r*size,size,size))
        visible_path = self._polygon_path(getattr(self,'_player_polygon',()),board,size)
        guidance = QPainterPath()
        guidance.setFillRule(Qt.FillRule.WindingFill)
        for r,c in self.overlay:
            guidance.addRect(QRectF(board.left()+c*size,board.top()+r*size,size,size))
        visible_path = visible_path.united(guidance)
        # Unvisited space stays opaque; remembered passages remain dimly readable.
        p.fillPath(all_area.subtracted(known).subtracted(visible_path),QColor(15,22,24,239))
        p.fillPath(known.subtracted(visible_path),QColor(20,27,29,110))
        p.restore()

    def _draw_player(self, p, board, size):
        position = self._visual_position
        center = QPointF(board.left()+(position.x()+.5)*size,board.top()+(position.y()+.5)*size)
        radius = max(3.0,min(11.,size*.18))
        p.save()
        p.translate(center)
        dr,dc = self._facing
        angle = math.degrees(math.atan2(dr,dc))+90
        p.rotate(angle)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(6,14,12,85))
        p.drawEllipse(QRectF(-radius*.7,-radius*.2,radius*1.8,radius*2.3))
        # Boots, a broad travelling cloak, shoulders, hood and pale face.
        p.setBrush(QColor('#3a3025'))
        p.drawEllipse(QRectF(-radius*.6,radius*.55,radius*.5,radius*.65))
        p.drawEllipse(QRectF(radius*.1,radius*.55,radius*.5,radius*.65))
        cloak = QPainterPath(QPointF(0,-radius*.5))
        cloak.cubicTo(-radius*.8,-radius*.3,-radius*.95,radius*.55,-radius*.85,radius)
        cloak.quadTo(QPointF(0,radius*1.3),QPointF(radius*.85,radius))
        cloak.cubicTo(radius*.95,radius*.55,radius*.8,-radius*.3,0,-radius*.5)
        cloth = QLinearGradient(QPointF(-radius,0),QPointF(radius,0))
        cloth.setColorAt(0,QColor('#1c514b'))
        cloth.setColorAt(.55,QColor('#4e9180'))
        cloth.setColorAt(1,QColor('#244e45'))
        p.setBrush(cloth)
        p.setPen(QPen(QColor('#c8b77d'),.8))
        p.drawPath(cloak)
        p.setBrush(QColor('#d7b68b'))
        p.setPen(QPen(QColor('#233c35'),max(1,radius*.18)))
        p.drawEllipse(QPointF(0,-radius*.35),radius*.42,radius*.47)
        p.setPen(QPen(QColor('#83ad91'),max(.8,radius*.1)))
        p.drawLine(QPointF(0,radius*.18),QPointF(0,radius*.9))
        p.restore()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        area,board,size = self._geometry()
        if self.maze is None:
            p.fillRect(area,QColor('#243731'))
            return
        self._cache_static(area,board,size)
        p.drawPixmap(0,0,self._static)
        inset = max(2,size*.12)
        for positions,color in ((self.explored,QColor(80,141,145,56)),(self.backtracked,QColor(154,118,86,67))):
            for r,c in positions:
                p.fillRect(QRectF(board.left()+c*size+inset,board.top()+r*size+inset,
                                  max(0,size-inset*2),max(0,size-inset*2)),color)
        colors = BOARD_COLORS[self.mode]
        self._draw_route(p,self.trail,board,size,colors['trail'],max(1.5,size*.06))
        self._draw_route(p,self.overlay,board,size,colors['route'],max(2,size*.09))
        self._draw_lights(p,board,size)
        p.drawPixmap(0,0,self._masonry)
        self._draw_lamp_fixtures(p,board,size)
        origin = self._center((0,0),board,size)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(colors['origin']),1.5))
        p.drawEllipse(origin,min(14,size*.23),min(14,size*.23))
        goal = self._center((self.maze.rows-1,self.maze.cols-1),board,size)
        icon = min(34,max(8,size*.65))
        self._gate.render(p,QRectF(goal.x()-icon/2,goal.y()-icon/2,icon,icon))
        self._draw_fog(p,board,size)
        self._draw_player(p,board,size)
        if self.hasFocus():
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor('#a48b55'),1))
            p.drawRoundedRect(area.adjusted(1,1,-1,-1),10,10)

    def mousePressEvent(self,event):
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        super().mousePressEvent(event)

    def keyPressEvent(self,event):
        keys = {Qt.Key.Key_Up:'N',Qt.Key.Key_W:'N',Qt.Key.Key_Down:'S',Qt.Key.Key_S:'S',
                Qt.Key.Key_Left:'W',Qt.Key.Key_A:'W',Qt.Key.Key_Right:'E',Qt.Key.Key_D:'E'}
        if event.key() in keys:
            self.moved.emit(keys[event.key()])
            event.accept()
        else:
            super().keyPressEvent(event)

    def showEvent(self,event):
        self._sync_effects_timer()
        super().showEvent(event)

    def hideEvent(self,event):
        self.effects_timer.stop()
        self._animation.stop()
        self._set_visual_position(QPointF(self.player[1], self.player[0]))
        super().hideEvent(event)

    def closeEvent(self,event):
        self.effects_timer.stop()
        self._animation.stop()
        super().closeEvent(event)
