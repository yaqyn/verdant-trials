"""Top-down castle cutaway with cached masonry and wall-aware 2D lighting."""
import math
import os
from collections import deque, OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from random import Random
import time

from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QPointF, Property, QPropertyAnimation, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QBrush, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QPolygonF, QRadialGradient, QRegion
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import QWidget
from lighting import wall_segments, grid_visibility_polygon, visible_cells, lamp_positions
from light_field import LIGHT_STOPS, feather_image, prepare_player_field

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


class _RasterCanvas(QWidget):
    renderer = 'raster'

    def paintEvent(self, event):
        self._paint_scene(event)


class _OpenGLCanvas(QOpenGLWidget):
    renderer = 'opengl'

    def __init__(self,parent=None):
        super().__init__(parent)
        self.setUpdateBehavior(QOpenGLWidget.UpdateBehavior.PartialUpdate)

    def paintEvent(self,event):
        self._gl_damage = event.region()
        super().paintEvent(event)

    def paintGL(self):
        self._paint_scene(None)


# Raster rendering remains available for headless verification and systems
# without a working OpenGL context. Native desktops use the accelerated canvas.
_headless = os.environ.get('QT_QPA_PLATFORM','').split(':')[0] in ('offscreen','minimal')
_Canvas = _OpenGLCanvas if os.environ.get('MAZE_RENDERER','opengl') != 'raster' and not _headless else _RasterCanvas


class MazeBoard(_Canvas):
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
        self._scene_full_repaint = True
        self.play_mode = True
        self.fog_enabled = False
        self.ambient_motion = True
        self.discovered = set()
        self.visible = set()
        self.lamps = []
        self._segments = ()
        self._light_polygons = []
        self._path_cache = {}
        self._lamp_layer_key = None
        self._memory_origins = set()
        self._fog_key = None
        self._topology = ()
        self._visibility_key = None
        self._scene_key = None
        self._scene_started = time.monotonic()
        self._facing = (0, 1)
        self._visual_position = QPointF(0, 0)
        self._motion_queue = deque()
        self._active_target = None
        self._motion_carry = 0
        self._leg_clock = time.monotonic()
        self._held_direction = None
        self._pending_direction = None
        self._static_key = None
        self._static = QPixmap()
        self._masonry = QPixmap()
        self._wall_width = 3
        self._wallpapers = {name: QPixmap(str(ASSETS / filename)) for name, filename in
                            (('light', 'verdant-world.png'), ('dark', 'verdant-night.png'))}
        self._frame = self._wallpapers[self.mode]
        self._animation = QPropertyAnimation(self, b'visualPosition', self)
        self._animation.setDuration(145)
        self._animation.setEasingCurve(QEasingCurve.Type.Linear)
        self._animation.finished.connect(self._motion_finished)
        self._held_timer = QTimer(self)
        self._held_timer.setSingleShot(True)
        self._held_timer.setInterval(145)
        self._held_timer.timeout.connect(self._repeat_reduced_motion)
        self._field_worker = ThreadPoolExecutor(max_workers=1,thread_name_prefix='maze-light')
        self._field_future = None
        self._prefetch_timer = QTimer(self)
        self._prefetch_timer.setSingleShot(True)
        self._prefetch_timer.timeout.connect(self._prefetch_light)
        self.effects_timer = QTimer(self)
        self.effects_timer.setInterval(16)
        self.effects_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.effects_timer.timeout.connect(self._ambient_tick)
        self._effects_timer = self.effects_timer

    def minimumSizeHint(self):
        return QSize(500, 400)

    def sizeHint(self):
        return QSize(920, 650)

    def _get_visual_position(self):
        return self._visual_position

    def _update_light_area(self, previous, value):
        _, board, size = self._geometry()
        radius = size*3.7
        def footprint(position):
            center = QPointF(board.left()+(position.x()+.5)*size,
                             board.top()+(position.y()+.5)*size)
            return QRectF(center.x()-radius,center.y()-radius,radius*2,radius*2)
        changed = footprint(previous).united(footprint(value)).intersected(board.adjusted(-16,-16,16,16))
        self.update(changed.toAlignedRect())

    def _set_visual_position(self, value):
        previous = self._visual_position
        self._visual_position = value
        if self.maze is not None and self.scene_ready:
            self._update_light_area(previous,value)
        else:
            self.update()

    visualPosition = Property(QPointF, _get_visual_position, _set_visual_position)

    def configure_scene(self, ready, play_mode, fog_enabled=True, ambient_motion=True):
        """Configure presentation before set_state without restarting steady lamps."""
        if (self.scene_ready,self.play_mode,self.fog_enabled,self.ambient_motion) != (bool(ready),bool(play_mode),bool(fog_enabled),bool(ambient_motion)):
            self._scene_full_repaint = True
        if self.play_mode != play_mode:
            self.discovered.clear()
            self._memory_origins.clear()
            self._fog_memory_key = None
            self._visibility_key = None
        if ready and not self.scene_ready:
            self._scene_started = time.monotonic()
            self._scene_key = None
        if not ready:
            self.lamps = []
            self._light_polygons = []
            self.discovered.clear()
            self._memory_origins.clear()
            self._fog_memory_key = None
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

    def _ambient_tick(self):
        # Repaint only when an opacity changes by a visible 8-bit step. Player
        # interpolation has its own Qt animation clock and still updates at 60Hz.
        elapsed = time.monotonic()-self._scene_started
        state = (tuple(round(self._lamp_strength(i,elapsed)*255) for i in range(len(self.lamps)))
                 if elapsed < 2.5 else round((.97+.025*math.sin(elapsed*.85))*255))
        if state != getattr(self,'_ambient_state',None):
            self._ambient_state = state
            if self.maze is None or not self.lamps:
                return
            _,board,size = self._geometry()
            region = QRegion()
            for position,radius in zip(self.lamps,self._lamp_radii):
                center = self._point(position,board,size)
                extent = (radius+.25)*size
                region |= QRegion(QRectF(center.x()-extent,center.y()-extent,
                                        extent*2,extent*2).toAlignedRect())
            self.update(region)

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
        previous_overlay, previous_complete = self.overlay, self.complete
        previous_topology = self._topology
        self.maze, self.player = maze, tuple(player)
        self.trail, self.overlay = list(trail), list(overlay)
        self.explored, self.backtracked = set(explored), set(backtracked)
        self.complete = complete
        self._marks_revision = getattr(self,'_marks_revision',0)+1
        target = QPointF(player[1], player[0])
        if changed_board:
            self.discovered.clear()
            self._memory_origins.clear()
            self._fog_memory_key = None
            self.visible.clear()
            self._scene_key = self._visibility_key = None
            self._scene_started = time.monotonic()
        if changed_board or self.reduced_motion or not self.play_mode:
            self._cancel_motion(clear_input=changed_board or not self.play_mode)
            self._set_visual_position(target)
        elif previous != self.player:
            delta = (player[0]-previous[0], player[1]-previous[1])
            if abs(delta[0])+abs(delta[1]) == 1:
                self._motion_queue.append(target)
                if self._animation.state() != QAbstractAnimation.State.Running:
                    self._start_next_leg()
            else:
                self._cancel_motion()
                self._set_visual_position(target)
        self._topology = tuple(frozenset(cell.walls) for row in maze.grid for cell in row)
        if self.scene_ready:
            self._prepare_lighting()
        self._sync_effects_timer()
        full = (changed_board or not self.scene_ready or not self.play_mode or self._scene_full_repaint
                or previous_overlay != self.overlay or previous_complete != complete
                or previous_topology != self._topology
                or getattr(self,'_previous_motion',None) != self.reduced_motion)
        self._previous_motion = self.reduced_motion
        self._scene_full_repaint = False
        if full:
            self.update()
        else:
            self._update_light_area(QPointF(previous[1],previous[0]),target)

    def _clear_held_input(self):
        self._held_timer.stop()
        self._held_direction = self._pending_direction = None

    def _cancel_motion(self, clear_input=True):
        self._animation.stop()
        self._prefetch_timer.stop()
        if self._field_future is not None:
            self._field_future.cancel()
            self._field_future = None
        self._motion_queue.clear()
        self._active_target = None
        self._motion_carry = 0
        if clear_input:
            self._clear_held_input()

    def _start_next_leg(self):
        if not self._motion_queue:
            return
        target = self._motion_queue.popleft()
        origin = QPointF(self._visual_position)
        self._active_target = target
        self._facing = (round(target.y()-origin.y()), round(target.x()-origin.x()))
        carry = self._motion_carry
        self._motion_carry = 0
        self._leg_clock = time.monotonic()-carry/1000
        self._animation.setStartValue(origin)
        self._animation.setEndValue(target)
        self._animation.start()
        if carry:
            self._animation.setCurrentTime(carry)

    def _motion_finished(self):
        # Preserve time left over from the display tick. Dropping it on every
        # 145ms cell caused a repeated hesitation even with fast paint times.
        elapsed = (time.monotonic()-self._leg_clock)*1000
        self._motion_carry = max(0,min(self._animation.duration()//2,
                                      round(elapsed-self._animation.duration())))
        self._active_target = None
        if self._motion_queue:
            self._start_next_leg()
            return
        direction = self._pending_direction or self._held_direction
        self._pending_direction = None
        if direction is not None and self.play_mode and not self.complete:
            self.moved.emit(direction)
        else:
            self._motion_carry = 0

    def _repeat_reduced_motion(self):
        if self._held_direction is not None and self.play_mode and not self.complete and self.reduced_motion:
            self.moved.emit(self._held_direction)
            if self._held_direction is not None:
                self._held_timer.start()

    def _prepare_lighting(self):
        key = (id(self.maze), self._topology)
        if self._scene_key != key:
            self._scene_key = key
            self._segments = wall_segments(self.maze)
            self.lamps = list(lamp_positions(self.maze, max_lamps=14))
            self.lamps[-1] = (self.maze.cols-.5,self.maze.rows-.5)
            self._lamp_radii = [1.65]*(len(self.lamps)-1)+[2.05]
            self._light_polygons = [(grid_visibility_polygon(self.maze,pos,radius,rays=64,segments=self._segments),)
                                    for pos,radius in zip(self.lamps,self._lamp_radii)]
            self._lamp_images = [self._pool_image(pos, polygons, radius,
                                 QColor(112,238,220,50) if index == len(self.lamps)-1 else QColor(255,192,92,35))
                                 for index,(pos,polygons,radius) in enumerate(zip(self.lamps,self._light_polygons,self._lamp_radii))]
            self._lamp_coverage = [self._pool_image(pos,polygons,radius,QColor(255,255,255,185))
                                   for pos,polygons,radius in zip(self.lamps,self._light_polygons,self._lamp_radii)]
            self._visibility_key = None
        key = (self.player, tuple(self.overlay), self.play_mode)
        if self._visibility_key != key:
            self._visibility_key = key
            x,y = self.player[1]+.5,self.player[0]+.5
            self._local_segments = tuple(w for w in self._segments
                if max(w[0],w[2]) >= x-4.5 and min(w[0],w[2]) <= x+4.5
                and max(w[1],w[3]) >= y-4.5 and min(w[1],w[3]) <= y+4.5)
            self.visible = visible_cells(self.maze,self.player,radius=3.4)
            self.discovered.update(self.visible)
            self._memory_origins.add(self.player)
            # Assistance deliberately reveals the requested route through the mist.
            self.discovered.update(self.overlay)


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
        key = (self.width(), self.height(), self.devicePixelRatioF(), id(self.maze), self._topology, self.mode)
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
        key = (points, board.left(), board.top(), size)
        cached = self._path_cache.get(key)
        if cached is not None:
            return cached
        path = QPainterPath()
        if points:
            path.addPolygon(QPolygonF([self._point(pos,board,size) for pos in points]))
            path.closeSubpath()
        if len(self._path_cache) > 240:
            self._path_cache.clear()
        self._path_cache[key] = path
        return path

    def _lamp_strength(self, index, elapsed):
        if self.reduced_motion or not self.ambient_motion:
            return 1.0
        fade = max(0.,min(1.,(elapsed-.18-index*.075)/1.1))
        return fade*fade*(3-2*fade)

    def _player_light(self):
        # Geometry is sampled and cached by _player_coverage. Between samples,
        # Qt blends the light fields instead of Python recasting every frame.
        return (self._visual_position.x()+.5,self._visual_position.y()+.5), ()

    def _soften_image(self, source, radius=2.5):
        """Feather premultiplied coverage with a compact compiled Gaussian pass.

        Rendering QGraphicsBlurEffect through a scene stalled small chapters
        during cache misses. This path does no scene traversal or GPU readback.
        """
        image = source.toImage() if isinstance(source,QPixmap) else source
        return QPixmap.fromImage(feather_image(image,radius))

    def _pool_image(self, origin, polygons, radius, color, resolution=32):
        # Higher-density gradient texture with native feathering; cached per lamp.
        extent = math.ceil(radius*resolution)
        image = QPixmap(extent*2,extent*2)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(extent-origin[0]*resolution,extent-origin[1]*resolution)
        self._radial_pool(painter,QRectF(0,0,0,0),resolution,origin,polygons,radius,color)
        painter.end()
        return self._soften_image(image,max(.8,resolution*.025)), QRectF(origin[0]-extent/resolution,origin[1]-extent/resolution,
                             extent*2/resolution,extent*2/resolution)

    def _field_sample(self, point, resolution):
        if point not in self._coverage_samples:
            near_player = abs(point[0]-self.player[1]-.5) <= 1.1 and abs(point[1]-self.player[0]-.5) <= 1.1
            segments = self._local_segments if near_player else self._segments
            image,area = prepare_player_field(self.maze,point,segments,resolution)
            self._coverage_samples[point] = (QPixmap.fromImage(image),QRectF(*area))
            if len(self._coverage_samples) > 96:
                self._coverage_samples.popitem(last=False)
        self._coverage_samples.move_to_end(point)
        return self._coverage_samples[point]

    def _prefetch_light(self):
        if self._field_future is not None:
            if not self._field_future.done():
                self._prefetch_timer.start(2)
                return
            future,request = self._field_future,self._field_request
            self._field_future = None
            point,resolution,key = request
            if not future.cancelled() and key == self._coverage_samples_key:
                image,area = future.result()
                self._coverage_samples[point] = (QPixmap.fromImage(image),QRectF(*area))
                if len(self._coverage_samples) > 96:
                    self._coverage_samples.popitem(last=False)
            return
        point,resolution,key = self._queued_light_sample
        if (self.isVisible() and key == self._coverage_samples_key
                and self._animation.state() == QAbstractAnimation.State.Running):
            self._field_request = (point,resolution,key)
            self._field_future = self._field_worker.submit(prepare_player_field,
                self.maze,point,self._segments,resolution)
            self._prefetch_timer.start(2)

    def _player_coverage(self, origin, polygons, resolution):
        key = (origin,self._scene_key,resolution)
        if getattr(self,'_coverage_key',None) == key:
            return self._personal_coverage
        self._coverage_key = key
        cache_key = (self._scene_key,resolution)
        if getattr(self,'_coverage_samples_key',None) != cache_key:
            self._coverage_samples_key = cache_key
            self._coverage_samples = OrderedDict()
        axis = (0 if abs(origin[0]-(math.floor(origin[0])+.5)) > 1e-6 else
                1 if abs(origin[1]-(math.floor(origin[1])+.5)) > 1e-6 else
                0 if self._facing[1] else 1)
        lower = math.floor(origin[axis]*2+1e-8)/2
        mix = max(0.,min(1.,(origin[axis]-lower)*2))
        points = []
        for coordinate,weight in ((lower,1-mix),(lower+.5,mix)):
            if weight < 1e-6:
                continue
            point = list(origin)
            point[axis] = coordinate
            point = tuple(round(value,6) for value in point)
            points.append((self._field_sample(point,resolution),weight))
        if len(points) == 1:
            self._personal_coverage = points[0][0]
        else:
            area = points[0][0][1].united(points[1][0][1])
            image = QPixmap(math.ceil(area.width()*resolution),math.ceil(area.height()*resolution))
            image.fill(Qt.GlobalColor.transparent)
            blend = QPainter(image)
            blend.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            blend.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
            offset = QRectF(-area.x()*resolution,-area.y()*resolution,0,0)
            for index,(pool,weight) in enumerate(points):
                if index == 0:
                    blend.setOpacity(weight)
                    self._draw_pool_image(blend,offset,resolution,pool)
                else:
                    # Apply weight to the source before Plus composition. Qt's
                    # painter opacity otherwise attenuates the accumulated
                    # destination and leaves the character's feet in darkness.
                    weighted = pool[0].copy()
                    alpha = QPainter(weighted)
                    alpha.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
                    alpha.fillRect(weighted.rect(),QColor(0,0,0,round(weight*255)))
                    alpha.end()
                    blend.setOpacity(1)
                    self._draw_pool_image(blend,offset,resolution,(weighted,pool[1]))
            blend.end()
            area.setWidth(image.width()/resolution)
            area.setHeight(image.height()/resolution)
            self._personal_coverage = (image,area)
        if (self._active_target is not None and not self._prefetch_timer.isActive()
                and self._animation.state() == QAbstractAnimation.State.Running):
            step = self._facing[1] if axis == 0 else self._facing[0]
            coordinate = (lower+.5 if mix < 1e-6 else lower+1) if step > 0 else lower-.5
            end = (self._active_target.x() if axis == 0 else self._active_target.y())+.5
            if step and 0 < (coordinate-origin[axis])*step <= (end-origin[axis])*step+1e-6:
                point = list(origin)
                point[axis] = coordinate
                point = tuple(round(value,6) for value in point)
                if point not in self._coverage_samples:
                    self._queued_light_sample = (point,resolution,cache_key)
                    self._prefetch_timer.start(0)
        return self._personal_coverage

    def _draw_pool_image(self, painter, board, size, pool):
        image, rect = pool
        target = QRectF(board.left()+rect.x()*size,board.top()+rect.y()*size,
                        rect.width()*size,rect.height()*size)
        painter.drawPixmap(target,image,QRectF(image.rect()))

    def _radial_pool(self, painter, board, size, origin, polygons, radius, color):
        center = self._point(origin, board, size)
        gradient = QRadialGradient(center, radius*size)
        for stop, strength in LIGHT_STOPS:
            shade = QColor(color)
            shade.setAlphaF(color.alphaF()*strength)
            gradient.setColorAt(stop, shade)
        for polygon in polygons:
            painter.save()
            painter.setClipPath(self._polygon_path(polygon,board,size), Qt.ClipOperation.IntersectClip)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(gradient)
            painter.drawEllipse(center,radius*size,radius*size)
            painter.restore()

    def _draw_lights(self, p, board, size):
        if not self.scene_ready:
            return
        elapsed = time.monotonic()-self._scene_started
        steady = elapsed > 2.5 or self.reduced_motion or not self.ambient_motion
        p.save()
        p.setClipRect(board,Qt.ClipOperation.IntersectClip)
        if steady:
            key = (self._scene_key,self.width(),self.height(),self.devicePixelRatioF(),self.mode)
            if self._lamp_layer_key != key:
                self._lamp_layer_key = key
                self._lamp_layer = self._new_layer()
                light = QPainter(self._lamp_layer)
                light.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                light.setClipRect(board)
                for pool in self._lamp_images:
                    self._draw_pool_image(light,board,size,pool)
                light.end()
            p.setOpacity(1 if self.reduced_motion or not self.ambient_motion else .97+.025*math.sin(elapsed*.85))
            p.drawPixmap(0,0,self._lamp_layer)
        else:
            for index,pool in enumerate(self._lamp_images):
                p.setOpacity(self._lamp_strength(index,elapsed))
                self._draw_pool_image(p,board,size,pool)
        p.setOpacity(1)
        if self.play_mode:
            origin, polygons = self._player_light()
            resolution = max(12,min(32,math.ceil(size*self.devicePixelRatioF())))
            if getattr(self,'_personal_pool_key',None) != (origin,self._scene_key,resolution):
                self._personal_pool_key = (origin,self._scene_key,resolution)
                coverage, rect = self._player_coverage(origin,polygons,resolution)
                tinted = coverage.copy()
                tint = QPainter(tinted)
                tint.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                tint.fillRect(tinted.rect(),QColor(255,222,157,65))
                tint.end()
                self._personal_pool = (tinted,rect)
            self._draw_pool_image(p,board,size,self._personal_pool)
        p.restore()

    def _draw_lamp_fixtures(self, p, board, size):
        if not self.scene_ready:
            return
        steady = (time.monotonic()-self._scene_started > 2.5 or self.reduced_motion or not self.ambient_motion)
        if not steady:
            return self._paint_lamp_fixtures(p,board,size)
        key = (self._scene_key,self.width(),self.height(),self.devicePixelRatioF())
        if getattr(self,'_fixture_key',None) != key:
            self._fixture_key = key
            self._fixture_layer = self._new_layer()
            fixture = QPainter(self._fixture_layer)
            fixture.setRenderHint(QPainter.RenderHint.Antialiasing)
            self._paint_lamp_fixtures(fixture,board,size)
            fixture.end()
        p.drawPixmap(0,0,self._fixture_layer)

    def _paint_lamp_fixtures(self, p, board, size):
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
            if index == len(self.lamps)-1:
                # The destination is a cool waystone beacon, distinct from the
                # warm brass passage lamps. Its halo stays calm and readable.
                radius = max(2.3,min(7,size*.105))
                halo_radius = max(9,size*.32)
                halo = QRadialGradient(center,halo_radius)
                halo.setColorAt(0,QColor(154,255,232,145))
                halo.setColorAt(.30,QColor(74,231,214,80))
                halo.setColorAt(1,QColor(61,206,198,0))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(halo)
                p.drawEllipse(center,halo_radius,halo_radius)
                p.setPen(QPen(QColor('#7dbcb0'),max(.8,radius*.16)))
                p.setBrush(QColor('#304d49'))
                p.drawEllipse(center+QPointF(0,radius*.42),radius*1.4,radius*.78)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor('#b3e5ce'),max(.7,radius*.11)))
                p.drawEllipse(center,radius*1.65,radius*1.65)
                crystal = QPainterPath(center+QPointF(0,-radius*1.45))
                crystal.lineTo(center+QPointF(radius*.72,-radius*.12))
                crystal.lineTo(center+QPointF(radius*.38,radius*.88))
                crystal.lineTo(center+QPointF(-radius*.38,radius*.88))
                crystal.lineTo(center+QPointF(-radius*.72,-radius*.12))
                crystal.closeSubpath()
                facets = QLinearGradient(center-QPointF(radius,0),center+QPointF(radius,0))
                facets.setColorAt(0,QColor('#278e93'))
                facets.setColorAt(.48,QColor('#dcfff0'))
                facets.setColorAt(.55,QColor('#7bf7d8'))
                facets.setColorAt(1,QColor('#389f9f'))
                p.setBrush(facets)
                p.setPen(QPen(QColor('#d2fff2'),max(.7,radius*.10)))
                p.drawPath(crystal)
                p.drawLine(center+QPointF(0,-radius*1.3),center+QPointF(0,radius*.70))
                p.restore()
                continue
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
        resolution, padding = max(12,min(32,math.ceil(size*self.devicePixelRatioF()))), 6
        self._fog_resolution = resolution
        memory_key = (id(self.maze), self._scene_key, self.play_mode,resolution)
        if getattr(self,'_fog_memory_key',None) != memory_key:
            self._fog_memory_key = memory_key
            self._fog_memory = QImage(self.maze.cols*resolution+padding*2,
                                     self.maze.rows*resolution+padding*2,QImage.Format.Format_Grayscale8)
            self._fog_memory.fill(Qt.GlobalColor.white)
            self._recorded_origins = set()
            self._fog_base = QImage(self._fog_memory.size(),QImage.Format.Format_ARGB32_Premultiplied)
            self._fog_base.fill(QColor(12,20,23))
            self._fog_key = None
        self._fog_changed_rect = None
        pending = self._memory_origins-self._recorded_origins
        if pending:
            memory = QPainter(self._fog_memory)
            memory.setRenderHint(QPainter.RenderHint.Antialiasing)
            memory.setCompositionMode(QPainter.CompositionMode.CompositionMode_Darken)
            memory.translate(padding,padding)
            changed = QRectF()
            for row,col in pending:
                extent = 3.4*resolution+8
                center_px = QPointF(padding+(col+.5)*resolution,padding+(row+.5)*resolution)
                patch = QRectF(center_px.x()-extent,center_px.y()-extent,extent*2,extent*2)
                changed = patch if changed.isNull() else changed.united(patch)
                origin = (col+.5,row+.5)
                nearby = self._local_segments if abs(row-self.player[0])+abs(col-self.player[1]) <= 1 else self._segments
                polygon = grid_visibility_polygon(self.maze,origin,3.4,rays=32,segments=nearby)
                memory.save()
                memory.setClipPath(self._polygon_path(polygon,QRectF(),resolution))
                center = QPointF(origin[0]*resolution,origin[1]*resolution)
                gradient = QRadialGradient(center,3.4*resolution)
                for stop,value in ((0,145),(.25,150),(.55,192),(.8,237),(1,255)):
                    gradient.setColorAt(stop,QColor(value,value,value))
                memory.setPen(Qt.PenStyle.NoPen)
                memory.setBrush(gradient)
                memory.drawEllipse(center,3.4*resolution,3.4*resolution)
                memory.restore()
            memory.end()
            self._recorded_origins.update(pending)
            self._fog_key = None
            # Convert and feather only the changed footprint. setAlphaChannel
            # on the entire map caused a stall at every newly visited cell.
            rect = changed.toAlignedRect().intersected(self._fog_memory.rect())
            alpha = self._fog_memory.copy(rect)
            patch = QImage(alpha.size(),QImage.Format.Format_ARGB32_Premultiplied)
            patch.fill(QColor(12,20,23))
            patch.setAlphaChannel(alpha)
            softened = self._soften_image(patch,max(.8,resolution*.025))
            update = QPainter(self._fog_base)
            update.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            safe = rect.adjusted(6,6,-6,-6)
            source = safe.translated(-rect.topLeft())
            update.drawPixmap(QRectF(safe),softened,QRectF(source))
            update.end()
            self._fog_changed_rect = safe
        origin, polygons = self._player_light()
        elapsed = time.monotonic()-self._scene_started
        known_lamps = tuple(range(len(self.lamps)))
        fades = tuple(round(self._lamp_strength(index,elapsed)*255) for index in known_lamps)
        control_key = (memory_key,tuple(self.overlay),fades)
        base_key = (control_key,len(self._recorded_origins))
        full = getattr(self,'_fog_lit_key',None) != control_key
        changed = self._fog_changed_rect
        if full or changed is not None:
            self._fog_lit_key = control_key
            rect = self._fog_base.rect() if full else changed
            image = self._fog_base.copy(rect)
            mask = QPainter(image)
            mask.setRenderHint(QPainter.RenderHint.Antialiasing)
            mask.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            mask.translate(padding-rect.x(),padding-rect.y())
            mask.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
            for index,fade in zip(known_lamps,fades):
                position = self.lamps[index]
                radius = self._lamp_radii[index]
                footprint = QRectF(padding+(position[0]-radius)*resolution,
                                   padding+(position[1]-radius)*resolution,
                                   radius*2*resolution,radius*2*resolution)
                if not footprint.intersects(QRectF(rect)):
                    continue
                mask.setOpacity(fade/255)
                self._draw_pool_image(mask,QRectF(),resolution,self._lamp_coverage[index])
            mask.setOpacity(1)
            # Explicit guidance remains usable through fog; round its endpoints.
            if self.overlay:
                path = QPainterPath(self._center(self.overlay[0],QRectF(),resolution))
                for point in self.overlay[1:]:
                    path.lineTo(self._center(point,QRectF(),resolution))
                mask.setPen(QPen(QColor(0,0,0,255),resolution*.75,
                    Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin))
                mask.drawPath(path)
                if len(set(self.overlay)) == 1:
                    mask.setBrush(QColor(0,0,0,255))
                    mask.drawEllipse(self._center(self.overlay[0],QRectF(),resolution),resolution*.38,resolution*.38)
            mask.end()
            if full:
                self._fog_lit_base = image
                self._fog_tiles = {}
            else:
                patch = QPixmap.fromImage(image)
                update = QPainter(self._fog_lit_base)
                update.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
                update.drawPixmap(rect.topLeft(),patch)
                update.end()
                # Reupload only affected small textures. Updating a single
                # map-sized pixmap forced a full GPU upload at every new cell.
                for key,(_,sample,_) in list(self._fog_tiles.items()):
                    if sample.intersects(rect):
                        del self._fog_tiles[key]
            self._fog_key = None
        key = (origin,base_key)
        if self._fog_key != key:
            self._fog_key = key
            coverage = self._player_coverage(origin,polygons,resolution)
            footprint = coverage[1]
            crop = QRectF(padding+footprint.x()*resolution,padding+footprint.y()*resolution,
                          footprint.width()*resolution,footprint.height()*resolution)
            core = crop.toAlignedRect().intersected(self._fog_lit_base.rect())
            rect = core.adjusted(-2,-2,2,2).intersected(self._fog_lit_base.rect())
            image = self._fog_lit_base.copy(rect)
            mask = QPainter(image)
            mask.setRenderHint(QPainter.RenderHint.Antialiasing)
            mask.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            mask.translate(padding-rect.x(),padding-rect.y())
            mask.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
            self._draw_pool_image(mask,QRectF(),resolution,coverage)
            mask.end()
            self._fog_image = QPixmap.fromImage(image)
            self._fog_patch_rect = rect
            self._fog_patch_core = core
        p.save()
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        bounds = board.adjusted(-self._wall_width/2,-self._wall_width/2,self._wall_width/2,self._wall_width/2)
        p.setClipRect(bounds,Qt.ClipOperation.IntersectClip)
        rect = self._fog_patch_rect
        patch = QRectF(board.left()+(rect.x()-padding)*size/resolution,
                       board.top()+(rect.y()-padding)*size/resolution,
                       rect.width()*size/resolution,rect.height()*size/resolution)
        outside = QPainterPath()
        outside.addRect(bounds)
        inside = QPainterPath()
        core = self._fog_patch_core
        inside.addRect(QRectF(board.left()+(core.x()-padding)*size/resolution,
                             board.top()+(core.y()-padding)*size/resolution,
                             core.width()*size/resolution,core.height()*size/resolution))
        p.save()
        p.setClipPath(outside.subtracted(inside),Qt.ClipOperation.IntersectClip)
        visible = p.clipBoundingRect()
        tile_size = 128
        for y in range(0,self._fog_lit_base.height(),tile_size):
            for x in range(0,self._fog_lit_base.width(),tile_size):
                core = QRectF(x,y,tile_size,tile_size).toAlignedRect().intersected(self._fog_lit_base.rect())
                target = QRectF(board.left()+(core.x()-padding)*size/resolution,
                                board.top()+(core.y()-padding)*size/resolution,
                                core.width()*size/resolution,core.height()*size/resolution)
                if not target.intersects(visible):
                    continue
                key = (x,y)
                if key not in self._fog_tiles:
                    sample = core.adjusted(-2,-2,2,2).intersected(self._fog_lit_base.rect())
                    self._fog_tiles[key] = (core,sample,QPixmap.fromImage(self._fog_lit_base.copy(sample)))
                _,sample,tile = self._fog_tiles[key]
                expanded = QRectF(board.left()+(sample.x()-padding)*size/resolution,
                                  board.top()+(sample.y()-padding)*size/resolution,
                                  sample.width()*size/resolution,sample.height()*size/resolution)
                p.save()
                p.setClipRect(target,Qt.ClipOperation.IntersectClip)
                p.drawPixmap(expanded,tile,QRectF(tile.rect()))
                p.restore()
        p.restore()
        p.setClipPath(inside,Qt.ClipOperation.IntersectClip)
        p.drawPixmap(patch,self._fog_image,QRectF(self._fog_image.rect()))
        p.restore()

    def _draw_player(self, p, board, size):
        """Blit native-resolution poses; vector art is rendered only once per pose."""
        position = self._visual_position
        center = QPointF(board.left()+(position.x()+.5)*size,
                         board.top()+(position.y()+.5)*size)
        radius = max(3.8, min(14., size*.23))
        moving = (abs(position.x()-self.player[1])+abs(position.y()-self.player[0])) > .001
        stride = (math.sin(self._animation.currentTime()/max(1,self._animation.duration())*math.pi*2)*.16
                  if moving and not self.reduced_motion else 0.)
        # Five gait poses preserve the subtle boot movement without rebuilding
        # dozens of paths, gradients and pens on every animation tick.
        stride = round(stride/.08)*.08
        ratio = self.devicePixelRatioF()
        geometry = (radius, ratio)
        if getattr(self, '_player_sprite_geometry', None) != geometry:
            self._player_sprite_geometry = geometry
            self._player_sprites = {}
        key = (self._facing, stride)
        sprite = self._player_sprites.get(key)
        if sprite is None:
            pixels = math.ceil((radius*3.2+4)*ratio)
            sprite = QPixmap(pixels, pixels)
            sprite.setDevicePixelRatio(ratio)
            sprite.fill(Qt.GlobalColor.transparent)
            art = QPainter(sprite)
            art.setRenderHint(QPainter.RenderHint.Antialiasing)
            art.translate(pixels/ratio/2, pixels/ratio/2)
            self._paint_player_sprite(art, radius, stride)
            art.end()
            self._player_sprites[key] = sprite
        extent = sprite.width()/ratio/2
        p.drawPixmap(center-QPointF(extent, extent), sprite)

    def _paint_player_sprite(self, p, radius, stride):
        """Paint the canonical traveller artwork around its local origin."""
        p.save()
        # A soft contact shadow anchors the feet without an outline halo.
        shadow = QRadialGradient(QPointF(1, radius*.28), radius*1.25)
        shadow.setColorAt(0, QColor(4, 13, 11, 110))
        shadow.setColorAt(1, QColor(4, 13, 11, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(shadow)
        p.drawEllipse(QRectF(-radius*1.2, -radius*.8, radius*2.4, radius*2.2))
        dr, dc = self._facing
        p.rotate(math.degrees(math.atan2(dr, dc))+90)
        # Boots remain separate from the coat; alternating steps stay subtle.
        p.setBrush(QColor('#342b24'))
        for side in (-1, 1):
            p.drawRoundedRect(QRectF(radius*(side*.34-.19), radius*(.45+side*stride),
                                     radius*.38, radius*.58), radius*.12, radius*.12)
        coat = QPainterPath(QPointF(-radius*.72, -radius*.30))
        coat.quadTo(QPointF(-radius*.96, radius*.12), QPointF(-radius*.67, radius*.76))
        coat.quadTo(QPointF(0, radius*.98), QPointF(radius*.67, radius*.76))
        coat.quadTo(QPointF(radius*.96, radius*.12), QPointF(radius*.72, -radius*.30))
        coat.quadTo(QPointF(0, -radius*.64), QPointF(-radius*.72, -radius*.30))
        fabric = QLinearGradient(QPointF(-radius, -radius*.5), QPointF(radius, radius))
        fabric.setColorAt(0, QColor('#75a68c'))
        fabric.setColorAt(.42, QColor('#3b796b'))
        fabric.setColorAt(1, QColor('#18443e'))
        p.setBrush(fabric)
        p.setPen(QPen(QColor('#183c34'), max(.7, radius*.08)))
        p.drawPath(coat)
        # Sleeves and bare hands make the shoulder line clearly human.
        for side in (-1, 1):
            p.setBrush(QColor('#487f6a'))
            p.drawEllipse(QRectF(radius*(side*.75-.21), -radius*.20,
                                radius*.42, radius*.65))
            p.setBrush(QColor('#d6ac7c'))
            p.drawEllipse(QPointF(side*radius*.82, radius*.40), radius*.16, radius*.20)
        # Leather cross-body strap and a small worn satchel.
        p.setPen(QPen(QColor('#bca377'), max(1., radius*.13)))
        p.drawLine(QPointF(-radius*.48, -radius*.25), QPointF(radius*.42, radius*.63))
        p.setPen(QPen(QColor('#4d3928'), max(.7, radius*.06)))
        p.setBrush(QColor('#94704a'))
        p.drawRoundedRect(QRectF(radius*.20, radius*.35, radius*.46, radius*.36),
                          radius*.08, radius*.08)
        # Face points forward; the hair crown occupies the back of the head.
        p.setBrush(QColor('#ddb88c'))
        p.setPen(QPen(QColor('#443a2d'), max(.7, radius*.06)))
        p.drawEllipse(QPointF(0, -radius*.47), radius*.40, radius*.47)
        hair = QPainterPath(QPointF(-radius*.39, -radius*.53))
        hair.cubicTo(-radius*.48, -radius*.14, radius*.45, -radius*.03,
                     radius*.40, -radius*.55)
        hair.quadTo(QPointF(radius*.10, -radius*.38), QPointF(-radius*.39, -radius*.53))
        p.setBrush(QColor('#514031'))
        p.drawPath(hair)
        p.setPen(QPen(QColor('#8a6b46'), max(.6, radius*.05)))
        p.drawArc(QRectF(-radius*.30, -radius*.58, radius*.60, radius*.46), 185*16, 155*16)
        # A carried brass lantern provides an obvious source for personal light.
        lantern = QPointF(radius*.99, radius*.50)
        p.setPen(QPen(QColor('#73552f'), max(.8, radius*.07)))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(lantern-QPointF(0, radius*.17), radius*.13, radius*.17)
        p.setBrush(QColor('#ffe4a5'))
        p.drawRoundedRect(QRectF(lantern.x()-radius*.17, lantern.y()-radius*.08,
                                radius*.34, radius*.38), radius*.06, radius*.06)
        p.setPen(QPen(QColor('#fff3cf'), max(.7, radius*.05)))
        p.drawLine(lantern, lantern+QPointF(0, radius*.20))
        p.restore()

    def _draw_marks(self, painter, board, size):
        key = (self._marks_revision,self.width(),self.height(),self.mode)
        if getattr(self,'_marks_key',None) != key:
            self._marks_key = key
            inset = max(2,size*.12)
            self._shade_paths = []
            for positions,color in ((self.explored,QColor(80,141,145,56)),
                                    (self.backtracked,QColor(154,118,86,67))):
                path = QPainterPath()
                for row,col in positions:
                    path.addRect(QRectF(board.left()+col*size+inset,board.top()+row*size+inset,
                                       max(0,size-inset*2),max(0,size-inset*2)))
                self._shade_paths.append((path,color))
            colors = BOARD_COLORS[self.mode]
            self._route_paths = []
            for route,color,width in ((self.trail,colors['trail'],max(1.5,size*.06)),
                                      (self.overlay,colors['route'],max(2,size*.09))):
                if len(route) < 2:
                    continue
                path = QPainterPath(self._center(route[0],board,size))
                for point in route[1:]:
                    path.lineTo(self._center(point,board,size))
                self._route_paths.append((path,QPen(QColor(color),width,Qt.PenStyle.SolidLine,
                                             Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin)))
        for path,color in self._shade_paths:
            painter.fillPath(path,color)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for path,pen in self._route_paths:
            painter.setPen(pen)
            painter.drawPath(path)

    def _paint_scene(self, event):
        p = QPainter(self)
        if self.renderer == 'opengl' and hasattr(self,'_gl_damage'):
            p.setClipRegion(self._gl_damage)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        area,board,size = self._geometry()
        if self.maze is None:
            p.fillRect(area,QColor('#243731'))
            return
        self._cache_static(area,board,size)
        p.drawPixmap(0,0,self._static)
        self._draw_marks(p,board,size)
        colors = BOARD_COLORS[self.mode]
        self._draw_lights(p,board,size)
        p.drawPixmap(0,0,self._masonry)
        origin = self._center((0,0),board,size)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(colors['origin']),1.5))
        p.drawEllipse(origin,min(14,size*.23),min(14,size*.23))
        self._draw_fog(p,board,size)
        self._draw_lamp_fixtures(p,board,size)
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
            if event.isAutoRepeat():
                event.accept()
                return
            direction = keys[event.key()]
            self._held_direction = direction
            if self._animation.state() == QAbstractAnimation.State.Running:
                # Keep one tap-turn; holding repeats at leg completion rather
                # than the desktop's unrelated key-repeat delay and rate.
                self._pending_direction = direction
            else:
                self.moved.emit(direction)
                if self.reduced_motion and self._held_direction is not None:
                    self._held_timer.start()
            event.accept()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self,event):
        keys = {Qt.Key.Key_Up:'N',Qt.Key.Key_W:'N',Qt.Key.Key_Down:'S',Qt.Key.Key_S:'S',
                Qt.Key.Key_Left:'W',Qt.Key.Key_A:'W',Qt.Key.Key_Right:'E',Qt.Key.Key_D:'E'}
        if event.key() in keys:
            if not event.isAutoRepeat() and self._held_direction == keys[event.key()]:
                self._held_direction = None
                self._held_timer.stop()
            event.accept()
        else:
            super().keyReleaseEvent(event)

    def focusOutEvent(self,event):
        self._clear_held_input()
        super().focusOutEvent(event)

    def showEvent(self,event):
        self._sync_effects_timer()
        super().showEvent(event)

    def hideEvent(self,event):
        self.effects_timer.stop()
        self._cancel_motion()
        self._set_visual_position(QPointF(self.player[1], self.player[0]))
        super().hideEvent(event)

    def closeEvent(self,event):
        self.effects_timer.stop()
        self._cancel_motion()
        self._field_worker.shutdown(wait=False,cancel_futures=True)
        super().closeEvent(event)
