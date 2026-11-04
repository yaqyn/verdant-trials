"""Top-down castle cutaway with cached masonry and wall-aware 2D lighting."""
import math
from pathlib import Path
from random import Random
import time

from PySide6.QtCore import QEasingCurve, QPointF, Property, QPropertyAnimation, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QBrush, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QPolygonF, QRadialGradient
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget, QGraphicsBlurEffect, QGraphicsPixmapItem, QGraphicsScene
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
        self._static_key = None
        self._static = QPixmap()
        self._masonry = QPixmap()
        self._wall_width = 3
        self._wallpapers = {name: QPixmap(str(ASSETS / filename)) for name, filename in
                            (('light', 'verdant-world.png'), ('dark', 'verdant-night.png'))}
        self._frame = self._wallpapers[self.mode]
        self._gate = QSvgRenderer(str(ASSETS / 'icons/waygate.svg'), self)
        self._animation = QPropertyAnimation(self, b'visualPosition', self)
        self._animation.setDuration(145)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutSine)
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

    def _set_visual_position(self, value):
        previous = self._visual_position
        self._visual_position = value
        self._player_light_key = None
        if self.maze is not None and self.scene_ready:
            _, board, size = self._geometry()
            radius = size*3.7
            def footprint(position):
                center = QPointF(board.left()+(position.x()+.5)*size,
                                 board.top()+(position.y()+.5)*size)
                return QRectF(center.x()-radius,center.y()-radius,radius*2,radius*2)
            self.update(footprint(previous).united(footprint(value)).toAlignedRect())
        else:
            self.update()

    visualPosition = Property(QPointF, _get_visual_position, _set_visual_position)

    def configure_scene(self, ready, play_mode, fog_enabled=True, ambient_motion=True):
        """Configure presentation before set_state without restarting steady lamps."""
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
            self.update()

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
        self._topology = tuple(frozenset(cell.walls) for row in maze.grid for cell in row)
        if self.scene_ready:
            self._prepare_lighting()
        self._sync_effects_timer()
        self.update()

    def _prepare_lighting(self):
        key = (id(self.maze), self._topology)
        if self._scene_key != key:
            self._scene_key = key
            self._segments = wall_segments(self.maze)
            self.lamps = list(lamp_positions(self.maze, max_lamps=14))
            self.lamps[-1] = (self.maze.cols-.24,self.maze.rows-.5)
            self._lamp_radii = [2.8]*(len(self.lamps)-1)+[3.1]
            self._light_polygons = [(visibility_polygon(pos,self._segments,radius,rays=64),)
                                    for pos,radius in zip(self.lamps,self._lamp_radii)]
            self._lamp_images = [self._pool_image(pos, polygons, radius,
                                 QColor(112,238,220,140) if index == len(self.lamps)-1 else QColor(255,192,92,118))
                                 for index,(pos,polygons,radius) in enumerate(zip(self.lamps,self._light_polygons,self._lamp_radii))]
            self._lamp_coverage = [self._pool_image(pos,polygons,radius,QColor(255,255,255,255))
                                   for pos,polygons,radius in zip(self.lamps,self._light_polygons,self._lamp_radii)]
            self._player_light_key = None
            self._visibility_key = None
        key = (self.player, tuple(self.overlay), self.play_mode)
        if self._visibility_key != key:
            self._visibility_key = key
            self.visible = visible_cells(self.maze, self.player, radius=3.4)
            self.discovered.update(self.visible)
            self._memory_origins.add(self.player)
            x,y = self.player[1]+.5,self.player[0]+.5
            self._local_segments = tuple(w for w in self._segments
                if max(w[0],w[2]) >= x-4.5 and min(w[0],w[2]) <= x+4.5
                and max(w[1],w[3]) >= y-4.5 and min(w[1],w[3]) <= y+4.5)
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
        origin = (self._visual_position.x()+.5, self._visual_position.y()+.5)
        if getattr(self, '_player_light_key', None) != origin:
            self._player_light_key = origin
            self._player_light_polygons = (visibility_polygon(origin,
                getattr(self,'_local_segments',self._segments),3.4,rays=32),)
        return origin, self._player_light_polygons

    def _soften_image(self, source, radius=2.5):
        """Qt's native blur makes continuous feathering, including shadow edges.

        Work on compact coverage textures, then cache the result. Bilinear
        enlargement alone cannot remove a stair-stepped visibility boundary.
        """
        if not hasattr(self,'_soft_scene'):
            self._soft_scene = QGraphicsScene(self)
            self._soft_item = QGraphicsPixmapItem()
            self._soft_blur = QGraphicsBlurEffect()
            self._soft_blur.setBlurHints(QGraphicsBlurEffect.BlurHint.QualityHint)
            self._soft_item.setGraphicsEffect(self._soft_blur)
            self._soft_scene.addItem(self._soft_item)
        source = QPixmap.fromImage(source) if isinstance(source,QImage) else source
        self._soft_item.setPixmap(source)
        self._soft_blur.setBlurRadius(radius)
        area = QRectF(0,0,source.width(),source.height())
        self._soft_scene.setSceneRect(area)
        result = QPixmap(source.size())
        result.fill(Qt.GlobalColor.transparent)
        painter = QPainter(result)
        self._soft_scene.render(painter,area,area)
        painter.end()
        return result

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
        return self._soften_image(image), QRectF(origin[0]-extent/resolution,origin[1]-extent/resolution,
                             extent*2/resolution,extent*2/resolution)

    def _player_coverage(self, origin, polygons, resolution):
        key = (origin,self._scene_key,resolution)
        if getattr(self,'_coverage_key',None) != key:
            self._coverage_key = key
            self._personal_coverage = self._pool_image(origin,polygons,3.4,
                                                       QColor(255,255,255,255),resolution)
        return self._personal_coverage

    def _draw_pool_image(self, painter, board, size, pool):
        image, rect = pool
        target = QRectF(board.left()+rect.x()*size,board.top()+rect.y()*size,
                        rect.width()*size,rect.height()*size)
        painter.drawPixmap(target,image,QRectF(image.rect()))

    def _radial_pool(self, painter, board, size, origin, polygons, radius, color):
        center = self._point(origin, board, size)
        gradient = QRadialGradient(center, radius*size)
        for stop, strength in ((0,1),(.12,1),(.4,.55),(.68,.16),(1,0)):
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
        p.setClipRect(board)
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
            resolution = max(12,min(48,math.ceil(size*self.devicePixelRatioF())))
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
        resolution, padding = max(12,min(48,math.ceil(size*self.devicePixelRatioF()))), 6
        self._fog_resolution = resolution
        memory_key = (id(self.maze), self._scene_key, self.play_mode,resolution)
        if getattr(self,'_fog_memory_key',None) != memory_key:
            self._fog_memory_key = memory_key
            self._fog_memory = QImage(self.maze.cols*resolution+padding*2,
                                     self.maze.rows*resolution+padding*2,QImage.Format.Format_RGB32)
            self._fog_memory.fill(Qt.GlobalColor.white)
            self._recorded_origins = set()
            self._fog_key = None
        pending = self._memory_origins-self._recorded_origins
        if pending:
            memory = QPainter(self._fog_memory)
            memory.setRenderHint(QPainter.RenderHint.Antialiasing)
            memory.setCompositionMode(QPainter.CompositionMode.CompositionMode_Darken)
            memory.translate(padding,padding)
            for row,col in pending:
                origin = (col+.5,row+.5)
                polygon = visibility_polygon(origin,self._segments,3.4,rays=64)
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
            self._fog_base = QImage(self._fog_memory.size(),QImage.Format.Format_ARGB32_Premultiplied)
            self._fog_base.fill(QColor(12,20,23))
            self._fog_base.setAlphaChannel(self._fog_memory)
            self._fog_base = self._soften_image(self._fog_base,max(2.5,resolution*.08)).toImage()
        origin, polygons = self._player_light()
        elapsed = time.monotonic()-self._scene_started
        known_lamps = tuple(index for index,position in enumerate(self.lamps)
                            if (int(position[1]),int(position[0])) in self.discovered)
        fades = tuple(round(self._lamp_strength(index,elapsed)*255) for index in known_lamps)
        key = (origin,tuple(self.overlay),len(self._recorded_origins),fades)
        if self._fog_key != key:
            self._fog_key = key
            image = self._fog_base.copy()
            mask = QPainter(image)
            mask.setRenderHint(QPainter.RenderHint.Antialiasing)
            mask.translate(padding,padding)
            mask.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
            # The same feathered coverage texture drives both visible glow and
            # fog removal. Only the small moving light is blurred each frame.
            self._draw_pool_image(mask,QRectF(),resolution,self._player_coverage(origin,polygons,resolution))
            # Once discovered, a lamp remains an independent source of sight.
            # Its radial illumination must remove fog, not merely tint a floor
            # that an opaque fog layer subsequently covers.
            for index,fade in zip(known_lamps,fades):
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
            self._fog_image = QPixmap.fromImage(image)
        p.save()
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.setClipRect(board.adjusted(-self._wall_width/2,-self._wall_width/2,self._wall_width/2,self._wall_width/2))
        margin = padding*size/resolution
        p.drawPixmap(board.adjusted(-margin,-margin,margin,margin),self._fog_image,QRectF(self._fog_image.rect()))
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
        key = (self._marks_revision,self.width(),self.height(),self.devicePixelRatioF(),self.mode)
        if getattr(self,'_marks_key',None) != key:
            self._marks_key = key
            self._marks_layer = self._new_layer()
            p = QPainter(self._marks_layer)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            self._paint_marks(p,board,size)
            p.end()
        painter.drawPixmap(0,0,self._marks_layer)

    def _paint_marks(self, p, board, size):
        inset = max(2,size*.12)
        for positions,color in ((self.explored,QColor(80,141,145,56)),(self.backtracked,QColor(154,118,86,67))):
            for r,c in positions:
                p.fillRect(QRectF(board.left()+c*size+inset,board.top()+r*size+inset,
                                  max(0,size-inset*2),max(0,size-inset*2)),color)
        colors = BOARD_COLORS[self.mode]
        self._draw_route(p,self.trail,board,size,colors['trail'],max(1.5,size*.06))
        self._draw_route(p,self.overlay,board,size,colors['route'],max(2,size*.09))

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
        self._draw_marks(p,board,size)
        colors = BOARD_COLORS[self.mode]
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
