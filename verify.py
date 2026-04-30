#!/usr/bin/env python3
"""Kleines Verifikations-Setup für das Projekt.

Dieser Check führt aus:
- Einheitstests mit pytest
- Optional Pylint-Analyse für Quellcodequalität
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PYLINT_TARGETS = [
    "main.py",
    "simulator.py",
    "scenario.py",
    "strategies.py",
    "physics_model.py",
    "profiles.py",
    "config.py",
    "analyzer.py",
]


def run_command(command: list[str]) -> int:
    print(f"\n→ Running: {' '.join(command)}")
    result = subprocess.run(command, cwd=ROOT)
    print(f"← Exit code: {result.returncode}\n")
    return result.returncode


def has_module(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def run_pytest() -> int:
    if not has_module("pytest"):
        print("Pytest ist nicht installiert. Installiere es mit 'pip install -r requirements-dev.txt'.")
        return 1
    return run_command([sys.executable, "-m", "pytest", "tests"])


def run_pylint() -> int:
    if not has_module("pylint"):
        print("Pylint ist nicht installiert. Installiere es mit 'pip install -r requirements-dev.txt'.")
        return 1
    return run_command([sys.executable, "-m", "pylint", *PYLINT_TARGETS])


def main() -> int:
    skip_pylint = "--skip-pylint" in sys.argv
    print("=== Projekt-Verifikation ===")

    status = 0
    status |= run_pytest()

    if not skip_pylint:
        status |= run_pylint()
    else:
        print("Pylint-Check übersprungen.")

    if status == 0:
        print("=== Verifikation erfolgreich ===")
    else:
        print("=== Verifikation fehlgeschlagen ===")

    return status


if __name__ == "__main__":
    raise SystemExit(main())
