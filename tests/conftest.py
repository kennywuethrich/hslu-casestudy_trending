"""Pytest-Konfiguration und gemeinsame Fixtures."""

from __future__ import annotations

from collections.abc import Generator

import pytest


@pytest.fixture(autouse=True)
def disable_price_api(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Deaktiviert den API-Call in SystemConfig fuer reproduzierbare Tests."""

    monkeypatch.setattr("config.SystemConfig._fetch_price_from_api", lambda self: None)
    yield
