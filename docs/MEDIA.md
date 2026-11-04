# README media

## Identity and palette

**Verdant Trials** keeps the game's luminous forest, travelling adventurer and lantern-lit maze identity. The cover is illustrative key art, not a gameplay screenshot. The playable character is the same brown-haired traveller in green clothing, boots and a cross-body satchel, carrying a warm lantern toward a teal crystal waygate.

README icons use established runtime Moonlight tokens: primary gold `#e4cd92`, forest canvas `#1b2928`, panel `#243732`, and foreground `#f3f1df`. Teal `#70eedc` is the secondary rendering/beacon accent. These are named interface tokens, not guessed samples from the raster artwork. Heading SVGs preserve the workspace's canonical `readme-style/icons.json` geometry, with 1.6-unit rounded strokes and a dark backing.

## Screenshots and gameplay

Captured on 2026-11-04 from the actual Qt application through its offscreen raster canvas, sharing the painter used by the native OpenGL board. No interface or gameplay imagery was generated or mocked.

- `interface.webp`: full window, chapter 3, seed 42, Moonlight. Fog is disabled for the overview; the travelled path comes from scripted calls to the real movement controller.
- `controls-play.webp`: actual chapter selection and hint/reveal buttons.
- `controls-observe.webp`: a paused real search, with Resume, Step, slider and presets.
- `controls-world.webp`: actual seed, fog, living-light and reduced-animation settings.
- `gameplay-hard.gif`: square board captures of chapter 4 (432 cells, seed 42), then chapter 5 (768 cells, seed 17). Scripted inputs drive `QuestWindow.move`; positions are sampled from the real animation at 48, 96 and 145 ms per step. Encoded at 20 fps with brief holds at the beginning, transition and end. This demonstrates gameplay and rendering, rather than a human solve or a frame-rate measurement.

| Asset | Dimensions | Bytes |
| --- | --- | --- |
| `cover.webp` | 1672 × 941 | 2,693,318 |
| `interface.webp` | 1440 × 980 | 744,394 |
| `controls-play.webp` | 283 × 203 | 8,622 |
| `controls-observe.webp` | 283 × 278 | 9,342 |
| `controls-world.webp` | 283 × 208 | 7,704 |
| `gameplay-hard.gif` | 720 × 720 | 9,979,566 |

Reproduce the captures with the project environment, ImageMagick and ExifTool:

```bash
.venv/bin/python scripts/capture_media.py
```

Pass `--exiftool /path/to/exiftool` for an executable outside PATH. Add `--screenshots-only` to refresh screenshots while preserving the selected GIF. Neither tool is required to play.

Heavy raster pictures are lossless WebP. ImageMagick converted them; ExifTool removed metadata, leaving only the owner's XMP Creator and Rights. ImageMagick absolute-error comparison against the PNG originals reported zero decoded-pixel differences. SVGs and the selected GIF are not passed through metadata cleanup or raster conversion.

## Cover provenance

`cover.webp` was made with the built-in image-generation tool. References were the canonical `assets/verdant-world.png` and a raster preview of the QPainter adventurer. The generated PNG was converted without cropping or resizing, with zero decoded-pixel differences. The source PNG remains in the generation archive outside the repository; the complete lossless image and prompt are retained here.

### Final cover prompt

Use case: stylized-concept. Create finished premium indie fantasy video-game KEY ART COVER for the actual game VERDANT TRIALS. Landscape 16:9 composition. Input 1 is the game's canonical enchanted forest world: retain its distinctive sunlit emerald woodland, monumental runic standing stones with teal inlays, misty valley and waterfalls. Input 2 is the actual tiny top-down adventurer sprite; translate its identity into beautifully illustrated key art: a solitary young adult traveller with brown hair, emerald green travel coat, brown boots, cross-body leather satchel, small warm brass lantern in one hand. Show this traveller prominently at three-quarter/back angle in the foreground, full body, lantern visible, entering an ancient stone labyrinth threaded through the forest; the character should look like an appealing playable fantasy game protagonist, NOT a realistic soldier or armored knight. A small teal crystal waygate glows invitingly beyond the passages. Rich hand-painted stylized 3D fantasy game art, luminous and adventurous, warm forest daylight with mysterious shaded passages, restrained golden accents. Atmospheric depth, tactile mossy stone, expressive silhouette, beautiful original game illustration. Strong landscape cover layout with a memorable hero silhouette and room for very readable LARGE title across the upper center: exact text VERDANT TRIALS (V E R D A N T, T R I A L S), elegant engraved gold fantasy display lettering with subtle leaf/path motif. Title must be spelled exactly and remain readable at GitHub README width. Only text on cover is VERDANT TRIALS. No interface, buttons, screens, fake gameplay, existing-game logos, third-party characters, subtitles, credits, border or watermark. Contemporary enchanted adventure, not medieval grimdark, not horror. Project-bound final cover asset.

### Selected asset hashes

```text
625f03bb1696c2c2b369efc9f4ade278f9b4c6ea7af018d8537217ca633d78ae  cover.webp
2f218feae89e2e8f1957365a8a904ceaa8fcc03386b91c0060f6886e0c038554  gameplay-hard.gif
```

No existing game's artwork was used. The separate Cinzel font keeps its bundled SIL Open Font License.
