# Maze Runner: the Verdant Trials

## Product and direction

An English desktop learning quest: play progressive forest labyrinths or observe how graph searches find a way through them. The user requested a dark medieval forest RPG atmosphere. Original ruined-forest artwork, mossy stone walls, antique brass, and restrained quest language give the app its identity. No artwork or branding from an existing game is used.

The maze remains the primary artifact. Learning explanations use plain algorithm terminology; controls pair thematic labels with understandable actions. Progression is a five-chapter journey, not a claim of saved player progression.

## Visual ownership

`theme.py` owns exact semantic colors in `THEMES`; `COLORS` is updated in place when switching modes. Dark forest is the default; Daylight is an accessible light alternative for controls. Both retain the forest board artwork and use a dark board palette where needed to preserve legibility. Native ttk widgets own keyboard, focus, hover, disabled and popup behavior. `app.py` owns composition and state, consuming the theme rather than redefining widget colors.

`assets/forest-frame.png` is original generated environmental art: moonlit ruins and roots frame a quiet clearing. Keep the maze inside its central opening. Artwork resizes only when canvas dimensions change. `art.py` renders the original SVG wall segments and quest icons. Geometry, labels, player markers and routes must remain readable on every level.

## Typography

Bundled Cinzel provides engraved Roman display headings suited to the quest setting. Instructions and controls use an available system sans face. `typography.py` registers Cinzel privately for the process where supported; no host font configuration is modified. Systems whose Tk exposes only bitmap fonts use fallbacks; Pillow display-title rendering may provide the bundled face independently of Tk font availability.

## Composition

The header establishes title and world lighting. A scrollable quest journal holds level selection and actions; the board occupies the remaining workspace. Quest chapter and current state sit above the board; legend, metrics and wayfinder notes sit below. Minimum window size and dynamic text wrapping must be tested. The sidebar scrolls rather than hiding actions at smaller sizes.

## Behavior

Play and Observe share maze creation, seed validation, difficulty selection and lifecycle cancellation. New quest cancels pending animation. Pause and Step expose individual transitions. A level change starts a fresh board. Hints and route reveals count as assistance. Completion offers the next chapter; all chapters remain directly available. Numeric seeds reproduce a board at a given level. Session progress and lighting preferences are not persisted.

Theme changes preserve the maze, current player position, algorithm state and animation lifecycle. Only presentation changes. Errors remain inline and preserve the current board.

## Accessibility and motion

Keyboard navigation uses native controls; arrows and WASD move only in Play and do not hijack text inputs. Focus stays visible. Color is paired with a legend, icons and textual feedback. The default step delay is 180 ms; backtracking holds 1.4× longer. Presets and a live 30–600 ms slider provide explicit pacing. Enter maze now skips generation without changing its result. The map floor uses deterministic neutral earth grain; wall shadows add depth without obscuring passages. There is no ambient flashing or compulsory decorative animation. Pause, Step and pace controls remain available. Tkinter assistive-technology support varies by platform; no WCAG certification is claimed. Semantic text foreground/background pairs are tested for a 4.5:1 contrast floor.

## Canonical capability map

| Capability | Owner | Verification |
| --- | --- | --- |
| Level, mode, algorithm, speed and theme | Native ttk controls in app.py | GUI lifecycle and theme switch checks |
| Seed validation | App generation handler | Invalid input integration |
| Animation lifecycle | App scheduler | Pause, restart and close tests |
| Status and recovery | Quest status and notes | Completion and validation tests |
| Movement and route rules | maze.py | Model behavioral tests |
| SVG drawing | art.py + bundled assets | Primitive renderer tests |
| Font registration | typography.py | Bundled license and fallback checks |
