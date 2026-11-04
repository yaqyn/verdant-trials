"""Measure real Qt paint work and animation pacing; does not assert display FPS.

QT_QPA_PLATFORM=offscreen .venv/bin/python benchmark_scene.py --level 5
Omit QT_QPA_PLATFORM to inspect the same animation on the desktop.
"""
import argparse
import json
import statistics
import time

from PySide6.QtCore import QPointF, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from qt_app import QuestWindow


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--level', type=int, choices=range(1, 6), default=5)
    parser.add_argument('--seconds', type=float, default=4)
    parser.add_argument('--width', type=int, default=1400)
    parser.add_argument('--height', type=int, default=900)
    args = parser.parse_args()
    if args.seconds < 1:
        parser.error('--seconds must be at least 1')
    app = QApplication([])
    window = QuestWindow(seed=42)
    window.resize(args.width, args.height)
    window.show()
    window.chapter_box.setCurrentIndex(args.level-1)
    window.skip_generation()
    board = window.board
    board._scene_started -= 4  # Measure steady play separately from lamp fade-in.
    app.processEvents()
    QTest.qWait(500)  # Allow the native window manager to finish its initial resize.
    board.grab()  # Warm static artwork, fog and fixture caches.
    samples = []
    original = board.paintEvent

    def paint(event):
        started = time.perf_counter()
        original(event)
        samples.append((started, (time.perf_counter()-started)*1000))

    board.paintEvent = paint
    row, col = window.maze.route_from((0, 0))[1]
    board._animation.setStartValue(QPointF(0, 0))
    board._animation.setEndValue(QPointF(col, row))
    board._animation.setDuration(1000)
    board._animation.setLoopCount(-1)
    board._animation.start()
    cpu_started, wall_started = time.process_time(), time.perf_counter()
    QTimer.singleShot(round(args.seconds*1000), app.quit)
    app.exec()
    cpu, elapsed = time.process_time()-cpu_started, time.perf_counter()-wall_started
    frames = samples[5:]  # Exclude animation start-up, retain all later stalls.
    durations = sorted(value for _, value in frames)
    result = {
        'platform': app.platformName(),
        'window': [window.width(), window.height()],
        'board': [board.width(), board.height()],
        'pixel_ratio': board.devicePixelRatioF(),
        'cells': window.maze.rows*window.maze.cols,
        'paint_samples': len(frames),
        'paint_mean_ms': round(statistics.mean(durations), 2),
        'paint_p95_ms': round(durations[int((len(durations)-1)*.95)], 2),
        'paint_max_ms': round(max(durations), 2),
        'paint_within_16_7_ms_percent': round(100*sum(x <= 16.7 for x in durations)/len(durations), 1),
        'paint_events_per_second': round((len(frames)-1)/(frames[-1][0]-frames[0][0]), 1),
        'process_cpu_percent_of_one_core': round(cpu/elapsed*100, 1),
        'note': 'Qt paint timing and event cadence; does not measure compositor presentation or GPU display FPS.',
    }
    print(json.dumps(result, indent=2))
    window.close()


if __name__ == '__main__':
    main()
