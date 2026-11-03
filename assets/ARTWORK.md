# Quest artwork

`forest-frame.png` is an original image generated with the built-in image generation tool for this project. It is stored locally and requires no runtime network requests. No game artwork was copied.

## Final image prompt

Use case: stylized-concept. Asset type: desktop medieval fantasy maze game background and ornamental frame, wide landscape 1536x1024. Original dark forest quest atmosphere, painterly highly detailed environment art. Ancient moss-covered carved stone rectangular frame surrounding a large perfectly flat very dark desaturated green central rectangular clearing occupying central 78 percent width and 74 percent height, intended to hold a legible maze overlay. Border only: twisted roots, ruined gothic stone arches, tiny warm golden embers, ferns, misty midnight evergreen forest, restrained antique brass ornaments at corners. Straight-on flat UI backdrop, symmetrical readable frame, lush cinematic detail concentrated around outer edges; center extremely quiet uniformly dark green-black without objects or texture. Sophisticated somber medieval RPG atmosphere, pale moonlight, no text, no letters, no logos, no characters, no maze lines. Image must be usable as game board background.

## Vector assets

The SVG quest icons and wall segments are original project-local vector drawings. `qt_board.py` renders the vectors through Qt SVG at the board scale, with painter-based shadows; no browser engine is required.

## Typography

Bundled Cinzel is distributed under its accompanying SIL Open Font License. Font provenance is recorded alongside the font in `assets/fonts/`. The app uses it for display headings and keeps instructions in a readable system font. Qt loads the bundled font through QFontDatabase for this application. System fallbacks preserve functionality when the face cannot be loaded.
