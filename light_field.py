"""CPU light-field preparation, safe to run away from the GUI thread."""
import math

from PIL import Image, ImageFilter
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPolygonF, QRadialGradient

from lighting import grid_visibility_polygon

LIGHT_STOPS = ((0,1),(.12,1),(.4,.55),(.68,.16),(1,0))


def feather_image(source, radius):
    image = source.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    rgba = Image.frombuffer('RGBA',(image.width(),image.height()),image.constBits(),
                            'raw','BGRA',image.bytesPerLine(),1)
    pixels = rgba.filter(ImageFilter.GaussianBlur(radius)).tobytes('raw','BGRA')
    return QImage(pixels,image.width(),image.height(),image.width()*4,
                  QImage.Format.Format_ARGB32_Premultiplied).copy()


def prepare_player_field(maze, point, segments, resolution):
    """Return owned image storage; never create a QPixmap on a worker thread."""
    radius = 3.4
    extent = math.ceil(radius*resolution)
    polygon = grid_visibility_polygon(maze,point,radius,rays=32,segments=segments)
    image = QImage(extent*2,extent*2,QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addPolygon(QPolygonF([QPointF(extent+(x-point[0])*resolution,
                                    extent+(y-point[1])*resolution) for x,y in polygon]))
    path.closeSubpath()
    painter.setClipPath(path)
    center = QPointF(extent,extent)
    gradient = QRadialGradient(center,radius*resolution)
    for stop,strength in LIGHT_STOPS:
        gradient.setColorAt(stop,QColor(255,255,255,round(strength*255)))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(gradient)
    painter.drawEllipse(center,radius*resolution,radius*resolution)
    painter.end()
    image = feather_image(image,max(.8,resolution*.025))
    return image, (point[0]-extent/resolution,point[1]-extent/resolution,
                   extent*2/resolution,extent*2/resolution)
