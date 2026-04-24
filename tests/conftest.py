"""Pytest-Konfiguration und gemeinsame Fixtures."""

from __future__ import annotations

from collections.abc import Generator
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def disable_price_api(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Deaktiviert den API-Call in SystemConfig fuer reproduzierbare Tests."""

    monkeypatch.setattr("config.SystemConfig._fetch_price_from_api", lambda self: None)
    yield
