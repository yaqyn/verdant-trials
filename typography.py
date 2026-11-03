"""Register the bundled Cinzel face for this process without host installation."""
import ctypes
import ctypes.util
from pathlib import Path
import sys
from tkinter import font

FONT_PATH = Path(__file__).resolve().parent / 'assets' / 'fonts' / 'Cinzel.ttf'


def register_font():
    """Best-effort process-local registration; unsupported Tk builds fall back."""
    if not FONT_PATH.is_file():
        return False
    try:
        if sys.platform.startswith('linux'):
            library = ctypes.util.find_library('fontconfig')
            if not library:
                return False
            fc = ctypes.CDLL(library)
            fc.FcConfigGetCurrent.restype = ctypes.c_void_p
            fc.FcConfigAppFontAddFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
            fc.FcConfigAppFontAddFile.restype = ctypes.c_int
            fc.FcConfigBuildFonts.argtypes = [ctypes.c_void_p]
            fc.FcConfigBuildFonts.restype = ctypes.c_int
            config = fc.FcConfigGetCurrent()
            if not config:
                return False
            return bool(fc.FcConfigAppFontAddFile(config, str(FONT_PATH).encode())
                        and fc.FcConfigBuildFonts(config))
        if sys.platform == 'win32':
            return bool(ctypes.windll.gdi32.AddFontResourceExW(str(FONT_PATH), 0x10, 0))
    except (OSError, AttributeError):
        pass
    return False


def families(root):
    """Choose installed faces; do not pretend an unavailable family is loaded."""
    register_font()
    available = set(font.families(root))
    body = next((face for face in ('DejaVu Sans', 'Liberation Sans', 'Arial', 'Helvetica')
                 if face in available), font.nametofont('TkDefaultFont', root=root).actual('family'))
    heading = next((face for face in ('Cinzel', 'DejaVu Serif', 'Liberation Serif', 'Georgia', 'Times')
                    if face in available), body)
    return heading, body
