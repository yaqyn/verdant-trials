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

Daylight is the default, with pale forest-fog surfaces and deep emerald text. Moonlight offers a softer dark alternative; the generated world remains a bright enchanted forest in both modes. Board terrain and route colors adapt to preserve legibility. Switching theme does not reset the maze, player position, search or animation lifecycle. New quest cancels the current traversal. Invalid seeds preserve the board and receive inline feedback. Errors and pending states must offer an obvious next action.

## Board presentation

The active wallpaper is `assets/verdant-world.png`; no decorative medieval border is baked into it. `cover_source_rect` selects a centered crop with the target aspect ratio, then scales uniformly. Excess edges crop instead of stretching, at every viewport size. Maze geometry is fitted independently and always preserves square cells. Use low-contrast neutral earth grain, stone edges with offset shadows, gold guidance, and a distinct gate. Search shading must not conceal walls. Cache static scenery at display pixel density; resize and topology changes invalidate the cache.

Player movement interpolates over a short duration, respecting each cardinal leg. Successive quick turns must not cut through walls. Algorithm jumps to nonadjacent cells snap rather than drawing a moving character through blocked passages. Reduced motion disables position interpolation.

## Pacing and accessibility

Default traversal pace is 180 ms per event. Slow/Fast presets, a live slider, Pause and Step make changes inspectable; backtracking may hold longer. Skipping generation leads directly to the same generated maze. There is no ambient flashing or required decorative motion.

Native Qt controls own keyboard focus, input, disabled and selected states. The board accepts arrows/WASD only when focused; seed inputs retain normal editing keys. H requests a hint and Space pauses active traversal without hijacking text input. A legend and text feedback supplement colors. All quest controls remain reachable at the minimum supported window size. No platform-wide assistive-technology certification is claimed.

## Verification contract

Model tests protect connectivity, reciprocal walls, deterministic seeds, large levels and BFS route behavior. Qt tests exercise completion, hints, mode changes, theme changes, invalid input, timer cancellation, pause/step, keyboard movement, rendering and animation. CI uses Qt's offscreen platform; desktop review also checks normal rendering, chapter switching, layout at minimum size and the visible popup states of selectors.
