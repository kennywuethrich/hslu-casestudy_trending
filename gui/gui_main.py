"""Einstiegspunkt für die GUI-Variante."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from gui import launch


def main() -> None:
    """Startet die GUI-Anwendung."""
    launch()


if __name__ == "__main__":
    main()
