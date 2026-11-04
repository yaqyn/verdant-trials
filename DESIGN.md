# Maze Runner: the Verdant Trials

## Product and creative direction

An English desktop enchanted-forest quest for playing progressive labyrinths and observing graph searches. The user refined the direction to a brighter contemporary fantasy RPG, avoiding medieval gloom. Sunlit woodland, runic stones, waterfalls, stone passages, restrained gold guidance and an engraved Cinzel wordmark establish the RPG character. Contemporary spacing, strong typography, clear actions and focused screens provide the interface. No artwork or branding from an existing game is used.

Play is the primary experience. Observe reveals algorithm controls and learning explanations. A focused quest panel replaces the crowded tool sidebar. Progress is a five-chapter journey; every chapter is directly accessible and session progress is not persisted.

## Canonical runtime owners

- `qt_app.py`: application palette, shared Qt stylesheet, native controls, state transitions, timer and quest panel.
- `qt_board.py`: QPainter board, SVG wall/gate rendering, texture, cached static scenery, focus, smooth player motion.
- `maze.py`: movement rules, graph generation and search. UI changes must not change graph invariants.
- `levels.py`: chapter names, dimensions and concepts.
- `assets/`: original forest illustration, editable vector art, bundled Cinzel and its SIL Open Font License.

Qt loads the bundled font with QFontDatabase for this application; no host font installation is required. The primary wordmark is Verdant Trials, paired with the Maze Runner descriptor and a leaf/route wayfinder crest. The quest remains an RPG exploration experience rather than a medieval simulation. Cinzel is for display only. A readable system sans face handles instructions, metrics and controls. Preserve comfortable text size and wrapping instead of reducing everything to fit.

## Composition and behavior

A restrained top bar holds identity, Play/Observe selection, and lighting. The maze dominates the workspace. The quest panel holds chapter context, actions and completion feedback; advanced seed configuration is secondary. Observe additionally exposes DFS/BFS selection, run/pause/step and pace controls. Victory states show moves, direct route and assistance, and offer the next chapter without a blocking modal.

Daylight is the default, with pale forest-fog surfaces and deep emerald text. Moonlight selects the matching `verdant-night.png`, an edit of the exact daytime composition with a moon and distant warm lights. Daylight uses `verdant-world.png` unchanged. Board terrain and route colors adapt to preserve legibility. Switching theme does not reset the maze, player position, search or animation lifecycle. New quest cancels the current traversal. Invalid seeds preserve the board and receive inline feedback. Errors and pending states must offer an obvious next action.

## Board presentation

The active wallpaper is `assets/verdant-world.png`; no decorative medieval border is baked into it. `cover_source_rect` selects a centered crop with the target aspect ratio, then scales uniformly. Excess edges crop instead of stretching, at every viewport size. Maze geometry is fitted independently and always preserves square cells. The maze reads as a top-down cutaway castle: individual floor slabs, substantial raised wall tops, side faces and cast shadows. An adventurer carrying a lantern moves within the passages. This is a castle interior visualization over the enchanted-forest environment, not a return to ornamental medieval UI. Search shading must not conceal walls. After generation, wall-adjacent lamps fade in with staggered timing. Their circular gradient pools are clipped by line-of-sight visibility polygons from `lighting.py`. This is wall-occluded 2D lighting, not a claim of physically based global illumination. Cache visibility geometry and bound lamp count; never recast all rays each frame. Gentle lamp movement must not flash. Cache static scenery at display pixel density; resize and topology changes invalidate the cache.

Player movement interpolates over a short duration, respecting each cardinal leg. Successive quick turns must not cut through walls. Algorithm jumps to nonadjacent cells snap rather than drawing a moving character through blocked passages. Reduced motion disables position interpolation and ambient light animation, and shows lamps without waiting for a fade. Play fog remembers explored corridors, darkens unvisited rooms, and resets on new quests. Observe presents the full map. Hints/reveal must not disappear under fog. World settings expose fog and living-light controls.

## Pacing and accessibility

Personal lantern light follows `visualPosition` throughout movement. Fog is an opaque darkness mask removed with radial falloff, rasterized at an adaptive 12-48 pixels per cell with native gradient feathering to soften corner shadows; never reveal the raw visibility polygon at uniform brightness. Exploration memory accumulates the softly illuminated footprint rather than whole cells, so distant walls remain hidden and memory has no square boundaries. Stationary lamp illumination, fixtures, the memory mask and native-resolution character poses are cached. Discovered lamps independently remove fog inside their wall-clipped pools, and the exit carries a cool teal crystal beacon with a broader pool than ordinary warm lamps. Compact feathered coverage textures are shared by the personal glow and fog; only the moving light is blurred per frame, with fog memory feathered when it changes. A single local visibility cast follows the explorer; movement repaints only the affected light footprint. Ambient repainting occurs only when an 8-bit opacity changes. Measure paint time and Qt event cadence with `benchmark_scene.py`; a 16.7 ms paint budget targets 60 fps but does not guarantee compositor presentation. The explorer has a readable human silhouette, travel clothes, satchel and carried lantern.

Default traversal pace is 180 ms per event. Slow/Fast presets, a live slider, Pause and Step make changes inspectable; backtracking may hold longer. Skipping generation leads directly to the same generated maze. There is no ambient flashing or required decorative motion.

Native Qt controls own keyboard focus, input, disabled and selected states. The board accepts arrows/WASD only when focused; seed inputs retain normal editing keys. H requests a hint and Space pauses active traversal without hijacking text input. A legend and text feedback supplement colors. All quest controls remain reachable at the minimum supported window size. No platform-wide assistive-technology certification is claimed.

## Verification contract

Model tests protect connectivity, reciprocal walls, deterministic seeds, large levels and BFS route behavior. Qt tests exercise completion, hints, mode changes, theme changes, invalid input, timer cancellation, pause/step, keyboard movement, rendering and animation. CI uses Qt's offscreen platform; desktop review also checks normal rendering, chapter switching, layout at minimum size and the visible popup states of selectors.
