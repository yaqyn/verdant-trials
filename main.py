"""Launch the Maze Runner educational desktop studio."""
import argparse
import sys
import tkinter as tk


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--level', type=int, default=1, choices=range(1, 6))
    parser.add_argument('--seed', type=int, default=None)
    parser.add_argument('--delay', type=int, default=180,
                        help='Animation delay in milliseconds (0–1000)')
    args = parser.parse_args()
    if not 0 <= args.delay <= 1000:
        parser.error('--delay must be between 0 and 1000')
    from app import MazeApp
    try:
        root = tk.Tk()
    except tk.TclError as error:
        print(f'Cannot open the desktop window: {error}. Run on a graphical desktop.', file=sys.stderr)
        return 1
    MazeApp(root, level_id=args.level, seed=args.seed, delay=args.delay)
    root.mainloop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
