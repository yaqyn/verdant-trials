"""Render the project's deliberately small SVG vocabulary on Tkinter Canvas.

Assets are parsed once and stay editable as SVG. No browser, raster conversion,
image dependency or external SVG content is required at runtime.
"""
from functools import lru_cache
from pathlib import Path
import xml.etree.ElementTree as ET

ASSETS = Path(__file__).resolve().parent / 'assets'


@lru_cache(maxsize=32)
def _asset(name):
    path = ASSETS / name
    if path.suffix != '.svg' or not path.resolve().is_relative_to(ASSETS.resolve()):
        raise ValueError('Expected a project SVG asset')
    root = ET.parse(path).getroot()
    view = tuple(map(float, root.get('viewBox', '0 0 24 24').split()))
    return view, tuple((node.tag.split('}')[-1], dict(node.attrib))
                       for node in root if node.tag.split('}')[-1] != 'title')


def draw_svg(canvas, name, x, y, width, height, tag='art', palette=None):
    """Draw a bundled SVG into a rectangle; return created canvas item IDs.

    ``name`` is relative to assets, e.g. ``icons/lantern.svg``. Palette maps
    source color hex strings to theme colors. The supported primitives are
    line, polyline, polygon, rect and circle; unsupported elements fail loudly.
    """
    (vx, vy, vw, vh), shapes = _asset(name)
    sx, sy = width / vw, height / vh
    scale = min(abs(sx), abs(sy))
    palette = palette or {}
    roles = {'#56604e': 'stone', '#9b9875': 'highlight', '#26392d': 'seam',
             '#73805a': 'moss', '#bca371': 'gold', '#e4c987': 'light',
             '#6c795a': 'moss', '#23342a': 'shadow'}
    items = []
    def point(px, py):
        return x + (float(px) - vx) * sx, y + (float(py) - vy) * sy
    def color(value):
        return '' if value == 'none' else palette.get(value, palette.get(roles.get(value), value))
    for kind, attrs in shapes:
        options = dict(tags=tag)
        stroke = color(attrs.get('stroke', 'none'))
        fill = color(attrs.get('fill', 'none'))
        thickness = max(.65, float(attrs.get('stroke-width', 1)) * scale)
        if kind in ('line', 'polyline'):
            if kind == 'line':
                coords = (*point(attrs['x1'], attrs['y1']), *point(attrs['x2'], attrs['y2']))
            else:
                values = [float(value) for value in attrs['points'].replace(',', ' ').split()]
                coords = tuple(value for i in range(0, len(values), 2)
                               for value in point(values[i], values[i + 1]))
            items.append(canvas.create_line(*coords, fill=stroke, width=thickness,
                                            capstyle='round', joinstyle='round', **options))
        elif kind == 'polygon':
            values = [float(value) for value in attrs['points'].replace(',', ' ').split()]
            coords = tuple(value for i in range(0, len(values), 2)
                           for value in point(values[i], values[i + 1]))
            items.append(canvas.create_polygon(*coords, fill=fill, outline=stroke,
                                               width=thickness, **options))
        elif kind == 'rect':
            px, py = float(attrs.get('x', 0)), float(attrs.get('y', 0))
            coords = (*point(px, py), *point(px + float(attrs['width']), py + float(attrs['height'])))
            items.append(canvas.create_rectangle(*coords, fill=fill, outline=stroke,
                                                 width=thickness, **options))
        elif kind == 'circle':
            cx, cy, radius = float(attrs['cx']), float(attrs['cy']), float(attrs['r'])
            coords = (*point(cx-radius, cy-radius), *point(cx+radius, cy+radius))
            items.append(canvas.create_oval(*coords, fill=fill, outline=stroke,
                                            width=thickness, **options))
        else:
            raise ValueError(f'Unsupported SVG primitive: {kind}')
    return items


def wall(canvas, x1, y1, x2, y2, width, tag='wall', palette=None):
    """Draw one horizontal/vertical moss-stone SVG wall segment."""
    if abs(y2-y1) >= .01 and abs(x2-x1) >= .01:
        raise ValueError('Maze walls must be horizontal or vertical')
    offset = max(1, width*.4)
    shadow = (palette or {}).get('shadow', '#171610')
    items = [canvas.create_line(x1+offset, y1+offset, x2+offset, y2+offset,
                               fill=shadow, width=width+1, capstyle='round', tags=tag)]
    if abs(y2-y1) < .01:
        return items + draw_svg(canvas, 'walls/stone-wall.svg', min(x1,x2), y1-width/2,
                        abs(x2-x1), width, tag, palette)
    if abs(x2-x1) < .01:
        return items + draw_svg(canvas, 'walls/stone-wall-vertical.svg', x1-width/2, min(y1,y2),
                        width, abs(y2-y1), tag, palette)
    raise ValueError('Maze walls must be horizontal or vertical')
