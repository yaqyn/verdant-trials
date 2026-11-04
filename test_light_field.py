"""Worker-produced coverage must be independent of GUI objects and buffers."""
from concurrent.futures import ThreadPoolExecutor
import gc
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')

from PySide6.QtWidgets import QApplication
from light_field import prepare_player_field
from maze import Maze


class LightFieldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def test_worker_image_keeps_owned_pixels_and_blocks_closed_walls(self):
        maze = Maze(1,2)
        with ThreadPoolExecutor(max_workers=1) as worker:
            image,area = worker.submit(prepare_player_field,maze,(.5,.5),None,32).result()
        gc.collect()
        storage_churn = bytearray(image.sizeInBytes())
        del storage_churn
        x = round((.5-area[0])*32)
        y = round((.5-area[1])*32)
        self.assertEqual(image.pixelColor(x,y).alpha(),255)
        self.assertEqual(image.pixelColor(x+32,y).alpha(),0)
