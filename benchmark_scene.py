"""Measure real Qt paint work and animation pacing; does not assert display FPS.

QT_QPA_PLATFORM=offscreen .venv/bin/python benchmark_scene.py --level 5
Omit QT_QPA_PLATFORM to inspect the same animation on the desktop.
"""
import argparse
import json
from itertools import cycle
import statistics
import time

from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from qt_app import QuestWindow


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--level', type=int, choices=range(1, 6), default=5)
    parser.add_argument('--seconds', type=float, default=4)
    parser.add_argument('--width', type=int, default=1400)
    parser.add_argument('--height', type=int, default=900)
    parser.add_argument('--fullscreen', action='store_true')
    args = parser.parse_args()
    if args.seconds < 1:
        parser.error('--seconds must be at least 1')
    app = QApplication([])
    window = QuestWindow(seed=42)
    window.resize(args.width, args.height)
    window.showFullScreen() if args.fullscreen else window.show()
    window.chapter_box.setCurrentIndex(args.level-1)
    window.skip_generation()
    board = window.board
    board._scene_started -= 4  # Measure steady play separately from lamp fade-in.
    app.processEvents()
    QTest.qWait(500)  # Allow the native window manager to finish its initial resize.
    if board.renderer == 'opengl':
        if not board.isValid():
            raise RuntimeError('OpenGL unavailable; use MAZE_RENDERER=raster for software rendering')
        board.grabFramebuffer()
    else:
        board.grab()  # Warm static artwork, fog and fixture caches.
    samples = []
    geometries = set()
    original = board.paintEvent

    def paint(event):
        started = time.perf_counter()
        geometries.add((board.width(),board.height()))
        original(event)
        samples.append((started, (time.perf_counter()-started)*1000))

    board.paintEvent = paint
    swaps = []
    if board.renderer == 'opengl':
        board.frameSwapped.connect(lambda: swaps.append(time.perf_counter()))
    # Traverse real cells through QuestWindow.move, including control refresh,
    # discovery, lamp/fog updates and direction changes at corridor corners.
    path = window.maze.route_from((0,0))[:-1]
    targets = cycle(path[1:]+path[-2::-1])
    directions = {(-1,0):'N',(1,0):'S',(0,-1):'W',(0,1):'E'}
    def advance():
        target = next(targets)
        delta = (target[0]-window.player[0],target[1]-window.player[1])
        window.move(directions[delta])
    board._animation.finished.connect(advance)
    cpu_started, wall_started = time.process_time(), time.perf_counter()
    advance()
    QTimer.singleShot(round(args.seconds*1000), app.quit)
    app.exec()
    cpu, elapsed = time.process_time()-cpu_started, time.perf_counter()-wall_started
    frames = samples[5:]  # Exclude animation start-up, retain all later stalls.
    durations = sorted(value for _, value in frames)
    gaps = sorted((b[0]-a[0])*1000 for a,b in zip(frames,frames[1:]))
    result = {
        'platform': app.platformName(),
        'renderer': board.renderer,
        'window': [window.width(), window.height()],
        'board': [board.width(), board.height()],
        'viewport_changed_during_run': len(geometries) > 1,
        'pixel_ratio': board.devicePixelRatioF(),
        'cells': window.maze.rows*window.maze.cols,
        'paint_samples': len(frames),
        'model_moves': window.moves,
        'frame_gap_p95_ms': round(gaps[int((len(gaps)-1)*.95)],2),
        'frame_gap_max_ms': round(max(gaps),2),
        'frame_gaps_over_25_ms': sum(x > 25 for x in gaps),
        'paint_mean_ms': round(statistics.mean(durations), 2),
        'paint_p95_ms': round(durations[int((len(durations)-1)*.95)], 2),
        'paint_max_ms': round(max(durations), 2),
        'paint_within_16_7_ms_percent': round(100*sum(x <= 16.7 for x in durations)/len(durations), 1),
        'paint_events_per_second': round((len(frames)-1)/(frames[-1][0]-frames[0][0]), 1),
        'process_cpu_percent_of_one_core': round(cpu/elapsed*100, 1),
        'note': 'Qt paint timing and swap events; does not measure physical monitor scanout.',
    }
    if len(swaps) > 5:
        swaps = swaps[5:]
        intervals = sorted((b-a)*1000 for a,b in zip(swaps,swaps[1:]))
        result['swap_events_per_second'] = round((len(swaps)-1)/(swaps[-1]-swaps[0]),1)
        result['swap_gap_p95_ms'] = round(intervals[int((len(intervals)-1)*.95)],2)
    print(json.dumps(result, indent=2))
    window.close()


if __name__ == '__main__':
    main()
