"""Quiet, deterministic earthen ground for the maze's playable surface."""
from functools import lru_cache
from random import Random

PALETTES = {'dark': ((51, 47, 39), '#332f27', '#3c382e'),
            'light': ((190, 181, 159), '#beb59f', '#b3aa94')}


@lru_cache(maxsize=6)
def texture(width, height, theme='dark'):
    """Return a softly mottled RGB texture, independent of quest randomness."""
    from PIL import Image, ImageFilter
    base = PALETTES[theme][0]
    rng = Random(731)
    small = Image.new('RGB', (max(2, width//12), max(2, height//12)))
    # Shared channel variation prevents colored speckles in the earth.
    variations = [rng.randint(-3, 3) for _ in range(small.width*small.height)]
    small.putdata([tuple(max(0, min(255, c+variation)) for c in base)
                   for variation in variations])
    image = small.resize((width, height), Image.Resampling.BICUBIC).filter(ImageFilter.GaussianBlur(2))
    # Fine grain stays low contrast; it reads as soil rather than visual noise.
    pixels = image.load()
    for y in range(height):
        for x in range(width):
            grain = rng.choice((-1, 0, 0, 0, 1))
            pixels[x, y] = tuple(max(0, min(255, c+grain)) for c in pixels[x, y])
    return image


def draw_ground(canvas, x, y, width, height, theme='dark', tag='floor'):
    """Draw ground once per board geometry; retain the returned PhotoImage.

    A dependency-free canvas fallback preserves the muted earth palette when
    Pillow is absent. This function never alters the maze's random generator.
    """
    width, height = max(1, round(width)), max(1, round(height))
    try:
        from PIL import ImageTk
        photo = ImageTk.PhotoImage(texture(width, height, theme), master=canvas)
        canvas.create_image(x, y, image=photo, anchor='nw', tags=tag)
        return photo
    except ImportError:
        _, base, fleck = PALETTES[theme]
        canvas.create_rectangle(x, y, x+width, y+height, fill=base, outline='', tags=tag)
        rng = Random(731)
        for _ in range(min(180, width*height//500)):
            px, py = x+rng.randrange(width), y+rng.randrange(height)
            canvas.create_line(px, py, px+1, py, fill=fleck, tags=tag)
        return None
