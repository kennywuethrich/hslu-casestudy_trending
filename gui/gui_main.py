"""Einstiegspunkt für die GUI-Variante der Simulation."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gui import launch_gui


if __name__ == "__main__":
    launch_gui()
