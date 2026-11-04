"""Wall-aware 2D visibility in maze-cell coordinates, independent of Qt.

The renderer can cache wall segments and lamp polygons until topology changes.
Moving light intensity is cheap: it does not require rebuilding visibility.
"""
from math import atan2, ceil, cos, floor, hypot, inf, pi, sin

_EPS = 1e-9
_TAU = 2 * pi


def wall_segments(maze):
    """Return unique physical walls as (x1, y1, x2, y2) tuples.

    Keeping a wall reported by either adjacent cell also makes malformed
    reciprocal passages conservative: light never leaks through a claimed wall.
    """
    result = set()
    for row, cells in enumerate(maze.grid):
        for col, cell in enumerate(cells):
            edges = {'N': (col, row, col+1, row),
                     'S': (col, row+1, col+1, row+1),
                     'W': (col, row, col, row+1),
                     'E': (col+1, row, col+1, row+1)}
            result.update(edges[direction] for direction in cell.walls)
    return tuple(sorted(result))


def _nearby(origin, segments, radius):
    """Discard walls outside the circle's enclosing box before ray casting."""
    x, y = origin
    return tuple(segment for segment in segments
                 if max(segment[0], segment[2]) >= x-radius
                 and min(segment[0], segment[2]) <= x+radius
                 and max(segment[1], segment[3]) >= y-radius
                 and min(segment[1], segment[3]) <= y+radius)


def _ray_hit(origin, direction, segment):
    """Distance to a ray/segment intersection, including corner endpoints."""
    ox, oy = origin
    dx, dy = direction
    ax, ay, bx, by = segment
    sx, sy = bx-ax, by-ay
    qx, qy = ax-ox, ay-oy
    cross = dx*sy-dy*sx
    if abs(cross) < _EPS:
        if abs(qx*dy-qy*dx) > _EPS:
            return None
        # A collinear wall cannot become an unlit leak along its length.
        first, second = qx*dx+qy*dy, (bx-ox)*dx+(by-oy)*dy
        if max(first, second) < -_EPS:
            return None
        return max(0., min(first, second))
    distance = (qx*sy-qy*sx)/cross
    fraction = (qx*dy-qy*dx)/cross
    if distance >= -_EPS and -_EPS <= fraction <= 1+_EPS:
        return max(0., distance)
    return None


def visibility_polygon(origin, segments, radius, rays=96):
    """A circular light footprint clipped by the nearest wall on every ray.

    Uniform circle samples create a smooth radial edge. Additional rays around
    wall endpoints preserve hard shadow silhouettes and light through doors.
    Coordinates are clockwise in screen space (positive y points downward).
    """
    if radius <= 0 or rays < 8:
        raise ValueError('A positive radius and at least eight rays are required')
    nearby = _nearby(origin, segments, radius)
    ox, oy = origin
    angles = {index*_TAU/rays for index in range(rays)}
    for ax, ay, bx, by in nearby:
        for x, y in ((ax, ay), (bx, by)):
            angle = atan2(y-oy, x-ox)
            angles.update(((angle-offset) % _TAU for offset in (-1e-6, 0, 1e-6)))
    # Maze walls are axis aligned. Avoid a general cross-product intersection
    # for every ray/wall pair during moving-lantern animation.
    axis_aligned = all(ax == bx or ay == by for ax,ay,bx,by in nearby)
    vertical = tuple((ax, min(ay,by), max(ay,by)) for ax,ay,bx,by in nearby if ax == bx)
    horizontal = tuple((ay, min(ax,bx), max(ax,bx)) for ax,ay,bx,by in nearby if ay == by)
    boundary = []
    for angle in sorted(angles):
        dx, dy = cos(angle), sin(angle)
        nearest = radius
        if axis_aligned:
            if abs(dx) > _EPS:
                for x, low, high in vertical:
                    distance = (x-ox)/dx
                    if 0 <= distance < nearest and low-_EPS <= oy+dy*distance <= high+_EPS:
                        nearest = distance
            if abs(dy) > _EPS:
                for y, low, high in horizontal:
                    distance = (y-oy)/dy
                    if 0 <= distance < nearest and low-_EPS <= ox+dx*distance <= high+_EPS:
                        nearest = distance
        else:
            for segment in nearby:
                hit = _ray_hit(origin, (dx,dy), segment)
                if hit is not None and hit < nearest:
                    nearest = hit
        boundary.append((ox+dx*nearest, oy+dy*nearest))
    return tuple(boundary)


def line_of_sight(origin, target, segments):
    """Whether an unobstructed straight line connects two points.

    Touching a wall endpoint blocks sight through a closed diagonal corner.
    Target points on the surface of a wall remain visible; points behind it do
    not. Cell-center targets do not rely on this surface convention.
    """
    dx, dy = target[0]-origin[0], target[1]-origin[1]
    distance = hypot(dx, dy)
    if distance < _EPS:
        return True
    direction = dx/distance, dy/distance
    for segment in _nearby(origin, segments, distance):
        hit = _ray_hit(origin, direction, segment)
        if hit is not None and _EPS < hit < distance-_EPS:
            return False
    return True


def _grid_blocked(maze, row, col, axis, step):
    """Check either cell's claim on a shared physical wall."""
    if not (0 <= row < maze.rows and 0 <= col < maze.cols):
        return True
    nr, nc = (row, col+step) if axis == 0 else (row+step, col)
    if not (0 <= nr < maze.rows and 0 <= nc < maze.cols):
        return True
    direction, opposite = (('E','W') if step > 0 else ('W','E')) if axis == 0 else (
                           ('S','N') if step > 0 else ('N','S'))
    return direction in maze.grid[row][col].walls or opposite in maze.grid[nr][nc].walls


def grid_ray_distance(maze, origin, direction, radius):
    """Distance to the first maze wall, visiting only cells crossed by the ray.

    A grid DDA advances to the next vertical or horizontal cell boundary.
    Reciprocal wall claims are conservative. At exact corners, all incident
    edges are checked so a ray cannot squeeze diagonally through masonry.
    The outer floor boundary clips rays even at the entrance and exit.
    """
    dx, dy = direction
    length = hypot(dx,dy)
    if radius <= 0 or length < _EPS:
        raise ValueError('A positive radius and nonzero direction are required')
    dx, dy = dx/length, dy/length
    ox, oy = origin
    col, row = floor(ox), floor(oy)
    if not (0 <= row < maze.rows and 0 <= col < maze.cols):
        return 0.
    # An emitter exactly on a claimed wall cannot shine along that wall.
    if abs(ox-round(ox)) < _EPS:
        if _grid_blocked(maze,row,col,0,-1):
            return 0.
        if abs(oy-round(oy)) < _EPS and _grid_blocked(maze,row-1,col,0,-1):
            return 0.
    if abs(oy-round(oy)) < _EPS:
        if _grid_blocked(maze,row,col,1,-1):
            return 0.
        if abs(ox-round(ox)) < _EPS and _grid_blocked(maze,row,col-1,1,-1):
            return 0.
    sx, sy = (1 if dx >= 0 else -1), (1 if dy >= 0 else -1)
    delta_x = abs(1/dx) if abs(dx) > _EPS else inf
    delta_y = abs(1/dy) if abs(dy) > _EPS else inf
    along_vertical_edge = delta_x == inf and abs(ox-round(ox)) < _EPS
    along_horizontal_edge = delta_y == inf and abs(oy-round(oy)) < _EPS
    next_x = ((col+1-ox) if sx > 0 else (ox-col))*delta_x if delta_x != inf else inf
    next_y = ((row+1-oy) if sy > 0 else (oy-row))*delta_y if delta_y != inf else inf
    while True:
        distance = min(next_x,next_y)
        if distance >= radius:
            return radius
        if abs(next_x-next_y) < _EPS:
            if (_grid_blocked(maze,row,col,0,sx) or _grid_blocked(maze,row,col,1,sy)
                    or _grid_blocked(maze,row+sy,col,0,sx)
                    or _grid_blocked(maze,row,col+sx,1,sy)):
                return max(0.,distance)
            row, col = row+sy, col+sx
            next_x, next_y = next_x+delta_x, next_y+delta_y
        elif next_x < next_y:
            nc = col+sx
            if (not 0 <= nc < maze.cols
                    or ('E' if sx > 0 else 'W') in maze.grid[row][col].walls
                    or ('W' if sx > 0 else 'E') in maze.grid[row][nc].walls):
                return max(0.,distance)
            if along_horizontal_edge and (_grid_blocked(maze,row-1,col,0,sx)
                    or _grid_blocked(maze,row,nc,1,-1)):
                return max(0.,distance)
            col, next_x = nc, next_x+delta_x
        else:
            nr = row+sy
            if (not 0 <= nr < maze.rows
                    or ('S' if sy > 0 else 'N') in maze.grid[row][col].walls
                    or ('N' if sy > 0 else 'S') in maze.grid[nr][col].walls):
                return max(0.,distance)
            if along_vertical_edge and (_grid_blocked(maze,row,col-1,1,sy)
                    or _grid_blocked(maze,nr,col,0,-1)):
                return max(0.,distance)
            row, next_y = nr, next_y+delta_y


def grid_visibility_polygon(maze, origin, radius, rays=32, segments=None):
    """Circular visibility with endpoint silhouettes and grid-walking rays.

    Segments supply only silhouette angles, not per-ray intersection work.
    When omitted, collect walls from the local radius instead of the full map.
    """
    if radius <= 0 or rays < 8:
        raise ValueError('A positive radius and at least eight rays are required')
    ox, oy = origin
    if segments is None:
        local = set()
        for row in range(max(0,floor(oy-radius)-1),min(maze.rows,floor(oy+radius)+1)):
            for col in range(max(0,floor(ox-radius)-1),min(maze.cols,floor(ox+radius)+1)):
                edges = {'N':(col,row,col+1,row), 'S':(col,row+1,col+1,row+1),
                         'W':(col,row,col,row+1), 'E':(col+1,row,col+1,row+1)}
                local.update(edges[wall] for wall in maze.grid[row][col].walls)
        segments = local
    angles = {index*_TAU/rays for index in range(rays)}
    for ax,ay,bx,by in _nearby(origin,segments,radius):
        for x,y in ((ax,ay),(bx,by)):
            angle = atan2(y-oy,x-ox)
            angles.update((angle+offset) % _TAU for offset in (-1e-6,0,1e-6))
    result = []
    for angle in sorted(angles):
        direction = cos(angle),sin(angle)
        distance = grid_ray_distance(maze,origin,direction,radius)
        result.append((ox+direction[0]*distance,oy+direction[1]*distance))
    return tuple(result)


def visible_cells(maze, position, radius=3.5):
    """Cell centers currently visible from a player's row/column position."""
    row, col = position
    if radius <= 0 or not (0 <= row < maze.rows and 0 <= col < maze.cols):
        return set()
    origin = col+.5, row+.5
    result = set()
    reach = ceil(radius)
    for r in range(max(0, row-reach), min(maze.rows, row+reach+1)):
        for c in range(max(0, col-reach), min(maze.cols, col+reach+1)):
            distance = hypot(r-row,c-col)
            if distance <= radius and (distance < _EPS or
                    grid_ray_distance(maze,origin,(c-col,r-row),distance) >= distance-_EPS):
                result.add((r, c))
    return result


def lamp_positions(maze, max_lamps=14):
    """Deterministic, spaced floor lamps positioned beside existing walls.

    Small maps get two lamps; larger maps get about one per 32 cells, bounded
    by max_lamps. Farthest-point placement avoids obvious clusters and uses no
    random state, so light placement cannot alter maze generation or replay.
    """
    if max_lamps < 0:
        raise ValueError('Lamp count must be nonnegative')
    count = min(max_lamps, maze.rows*maze.cols,
                max(2, ceil(maze.rows*maze.cols/32)))
    if not count:
        return ()
    candidates = []
    for row, cells in enumerate(maze.grid):
        for col, cell in enumerate(cells):
            x, y = col+.5, row+.5
            for wall, offset in (('N', (0,-.29)), ('W', (-.29,0)),
                                 ('S', (0,.29)), ('E', (.29,0))):
                if wall in cell.walls:
                    x, y = x+offset[0], y+offset[1]
                    break
            candidates.append((x,y))
    # Start near the entrance, then maximize separation from selected lamps.
    selected = [candidates.pop(0)]
    while candidates and len(selected) < count:
        best = max(range(len(candidates)), key=lambda index:
                   min((candidates[index][0]-x)**2+(candidates[index][1]-y)**2
                       for x,y in selected))
        selected.append(candidates.pop(best))
    return tuple(selected)
