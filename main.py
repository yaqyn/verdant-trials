"""Launch Maze Runner: the Verdant Trials."""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--level', type=int, default=1, choices=range(1, 6))
    parser.add_argument('--seed', type=int)
    parser.add_argument('--delay', type=int, default=180,
                        help='Animation delay in milliseconds (30–600)')
    args = parser.parse_args()
    if not 30 <= args.delay <= 600:
        parser.error('--delay must be between 30 and 600')
    try:
        from PySide6.QtWidgets import QApplication
        from qt_app import QuestWindow
    except ImportError as error:
        print(f'Missing desktop dependency: {error}. Install requirements.txt in your virtual environment.', file=sys.stderr)
        return 1
    app = QApplication(sys.argv[:1])
    app.setApplicationName('Maze Runner')
    app.setOrganizationName('Verdant Trials')
    window = QuestWindow(level_id=args.level, seed=args.seed, delay=args.delay)
    window.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
