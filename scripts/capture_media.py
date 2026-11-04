#!/usr/bin/env python3
"""Capture actual Qt screens and a scripted square gameplay demo for the README.

Run with the project interpreter; ImageMagick and ExifTool are documentation-only
requirements. The game itself needs neither tool. Captures use the same painter
through the offscreen raster backend, without opening desktop windows.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['MAZE_RENDERER'] = 'raster'
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from PIL import Image
from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from qt_app import QuestWindow

DIRECTIONS = {(-1,0):'N',(1,0):'S',(0,-1):'W',(0,1):'E'}


def settled(app):
    app.processEvents()
    QTest.qWait(20)
    app.processEvents()


def pil_frame(widget):
    image = widget.grab().toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    return Image.frombytes('RGBA',(image.width(),image.height()),bytes(image.constBits()),
                           'raw','RGBA',image.bytesPerLine()).convert('RGB')


def move_to(window,target):
    row,col = window.player
    window.move(DIRECTIONS[target[0]-row,target[1]-col])


def crop_widgets(window,widgets,margin=8):
    bounds = QRect()
    for widget in widgets:
        rect = QRect(widget.mapTo(window,QPoint()),widget.size())
        bounds = rect if bounds.isNull() else bounds.united(rect)
    return window.grab(bounds.adjusted(-margin,-margin,margin,margin).intersected(window.rect()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exiftool',default=shutil.which('exiftool'))
    parser.add_argument('--screenshots-only',action='store_true')
    args = parser.parse_args()
    if not args.exiftool:
        parser.error('Install ExifTool or pass --exiftool /path/to/exiftool')
    exif = [args.exiftool] if os.access(args.exiftool,os.X_OK) else ['perl',args.exiftool]
    app = QApplication([])
    out = ROOT/'docs'
    out.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='verdant-media-') as temp:
        def save_raster(pixmap,name):
            source = Path(temp)/(name+'.png')
            target = out/(name+'.webp')
            pixmap.save(str(source))
            subprocess.run(['magick',str(source),'-strip','-define','webp:lossless=true',str(target)],check=True)
            subprocess.run(exif+['-overwrite_original','-all=',
                '-XMP-dc:Creator=Abdulrahman M. Yaqyn',
                '-XMP-dc:Rights=Copyright Abdulrahman M. Yaqyn','-XMP-x:XMPToolkit=',str(target)],check=True,stdout=subprocess.DEVNULL)
            subprocess.run(['magick','compare','-metric','AE',str(source),str(target),'null:'],check=True)
            print(name,pixmap.width(),pixmap.height(),target.stat().st_size)

        window = QuestWindow(level_id=3,seed=42,delay=180)
        window.resize(1440,980)
        window.show()
        window.skip_generation()
        window.change_theme('dark')
        window.reduced_motion.setChecked(True)
        path = window.maze.route_from((0,0))
        for target in path[1:min(35,len(path)-2)]:
            move_to(window,target)
        window.reduced_motion.setChecked(False)
        window.fog_checkbox.setChecked(False)
        window.board._scene_started -= 4
        settled(app)
        save_raster(window.grab(),'interface')
        window.fog_checkbox.setChecked(True)
        settled(app)
        save_raster(crop_widgets(window,[window.chapter_box,window.description_label,
                                         window.hint_button,window.reveal_button]),'controls-play')
        window.set_mode('Observe')
        window.run_search()
        window.toggle_pause()
        settled(app)
        save_raster(crop_widgets(window,[window.observe_panel,window.pacing_panel]),'controls-observe')
        window.set_mode('Play')
        window._toggle_advanced()
        settled(app)
        save_raster(crop_widgets(window,[window.advanced_button,window.advanced]),'controls-world')
        window.close()

        if args.screenshots_only:
            return

        # Scripted inputs drive real QuestWindow.move and real animation values.
        # This is a demonstration, not a recording of a human solving the maze.
        frames = []
        for level,seed in ((4,42),(5,17)):
            game = QuestWindow(level_id=level,seed=seed,delay=180)
            game.show()
            game.skip_generation()
            game.change_theme('dark')
            path = game.maze.route_from((0,0))
            game.reduced_motion.setChecked(True)
            start = min(38,len(path)//4)
            for target in path[1:start+1]:
                move_to(game,target)
            game.reduced_motion.setChecked(False)
            board = game.board
            board.setParent(None)
            game.hide()
            board.resize(720,720)
            board.show()
            board.setFocus()
            settled(app)
            for target in path[start+1:min(start+41,len(path)-1)]:
                move_to(game,target)
                for timestamp in (48,96,145):
                    app.processEvents()
                    if board._animation.state():
                        board._animation.setCurrentTime(timestamp)
                    board._scene_started = time.monotonic()-4-len(frames)*.05
                    frames.append(pil_frame(board))
            game.close()
            board.close()
        # Shared palette keeps the static forest stable between frames.
        samples = Image.new('RGB',(360*6,360))
        for index in range(6):
            samples.paste(frames[index*(len(frames)-1)//5].resize((360,360)),(index*360,0))
        palette = samples.quantize(colors=256,method=Image.Quantize.MEDIANCUT)
        encoded = [frame.quantize(palette=palette,dither=Image.Dither.FLOYDSTEINBERG) for frame in frames]
        durations = [50]*len(encoded)
        durations[0] = durations[len(encoded)//2] = 700
        durations[-1] = 700
        encoded[0].save(out/'gameplay-hard.gif',save_all=True,append_images=encoded[1:],
                        duration=durations,loop=0,optimize=True,disposal=1)
        print('gameplay-hard.gif',len(encoded),'frames',encoded[0].size,(out/'gameplay-hard.gif').stat().st_size)


if __name__ == '__main__':
    main()
