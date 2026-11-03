# Maze Runner design

## Product

An English desktop learning studio for exploring maze generation, playing progressive puzzles, and comparing search algorithms. The maze is the central artifact. Retain Tkinter and a dependency-free Python model; no network or account is needed.

## Visual direction

A drafting table for algorithms: spacious light surfaces, dark blue walls, teal routes, clearly numbered progression. Avoid game-store decoration, decorative dashboards, gradients, and color-only feedback. Typography uses the platform sans family, with a stronger title and readable body copy. The desktop window must remain usable at its documented minimum size.

## Ownership

`theme.py` is the canonical runtime palette and ttk style adapter. `app.py` consumes it for shared controls and canvas roles. This document owns intent; runtime tokens own exact values. Native ttk buttons, selectors, fields and focus behavior are canonical. Canvas rendering belongs to the app, with labeled start and finish and text feedback outside the canvas.

## Interaction

Play and Observe share maze creation, seed validation, difficulty selection and lifecycle cancellation. New maze cancels pending animation. Pause and Step expose algorithm transitions without blocking the event loop. A level change starts a fresh board. Hints help without claiming an unaided completion. Completion offers the next level; all levels remain directly available for exploration.

## Accessibility and motion

Keyboard navigation through native controls; arrows and WASD move only in play mode and must not hijack text inputs. Focus stays visible. Color is paired with labels and textual status. Animation is user-controlled with pause, step and speed controls. Resizing fits the maze without altering its topology. Tkinter assistive-technology support varies by platform; do not claim WCAG certification.

## Canonical capability map

| Capability | Owner | Verification |
| --- | --- | --- |
| Level, mode, algorithm, speed selection | Native ttk controls in app.py | GUI integration + manual smoke |
| Seed validation | App generation handler | Invalid input integration |
| Animation lifecycle | App scheduler | Pause, restart and close tests |
| Status and recovery | App learning/status labels | Completion and validation tests |
| Maze movement and route rules | maze.py | Model behavioral tests |
