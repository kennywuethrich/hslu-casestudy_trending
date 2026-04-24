"""Tests fuer CSV-Profile und deren Aufbereitung."""

from __future__ import annotations

from config import SystemConfig
from profiles import load_profiles


EXPECTED_COLUMNS = {
    "load_el_kw",
    "load_heat_kw",
    "pv_kw",
    "outdoor_temp_c",
    "ev_driven_kwh",
    "price_buy",
    "price_sell",
    "co2_intensity",
    "dt_h",
}


def test_load_profiles_contains_required_columns() -> None:
    """Prueft, dass alle benoetigten Spalten vorhanden sind."""

    profiles = load_profiles(SystemConfig())
    assert EXPECTED_COLUMNS.issubset(set(profiles.columns))


def test_load_profiles_has_rows_and_hourly_step() -> None:
    """Prueft, dass Profilzeilen vorhanden sind und dt_h konstant 1.0 ist."""

    profiles = load_profiles(SystemConfig())
    assert len(profiles) > 0
    assert (profiles["dt_h"] == 1.0).all()
