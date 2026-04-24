"""Tests fuer das physikalische Schrittsimulationsmodell."""

from __future__ import annotations

import pandas as pd

from config import SystemConfig
from physics_model import Decision, EnergySystemModel, SystemState


def _sample_profile_row() -> pd.Series:
    """Erzeugt ein minimales, gueltiges Profil fuer einen Zeitschritt."""

    return pd.Series(
        {
            "pv_kw": 20.0,
            "load_el_kw": 10.0,
            "load_heat_kw": 12.0,
            "outdoor_temp_c": 8.0,
            "ev_driven_kwh": 2.0,
            "price_buy": 0.25,
            "price_sell": 0.1,
            "co2_intensity": 0.128,
            "dt_h": 1.0,
        }
    )


def test_initial_state_within_bounds() -> None:
    """Prueft, dass der Initialzustand innerhalb physischer Grenzen liegt."""

    config = SystemConfig()
    model = EnergySystemModel(config)

    state = model.initial_state()

    assert 0.0 <= state.h2_mass_kg <= config.h2_total_mass_kg
    assert 0.0 <= state.thermal_soc_kwh <= config.thermal_storage_capacity_kwh
    assert 0.0 <= state.ev_soc_kwh <= config.ev_capacity_kwh


def test_step_clips_state_to_valid_ranges() -> None:
    """Prueft Clipping von H2-, EV- und Temperaturlimits im Schrittmodell."""

    config = SystemConfig()
    model = EnergySystemModel(config)
    profile_t = _sample_profile_row()

    state = SystemState(
        h2_mass_kg=config.h2_total_mass_kg,
        T_room_C=26.0,
        thermal_soc_kwh=config.thermal_storage_capacity_kwh,
        ev_soc_kwh=config.ev_capacity_kwh,
    )
    decision = Decision(
        P_ely_kw=1000.0, P_fc_kw=0.0, P_ev_charge_kw=1000.0, P_hp_kw=200.0
    )

    new_state, step_log = model.step(state, decision, profile_t)

    assert new_state.h2_mass_kg <= config.h2_total_mass_kg
    assert new_state.ev_soc_kwh <= config.ev_capacity_kwh
    assert 16.0 <= new_state.T_room_C <= 26.0
    assert "grid_import_kw" in step_log
    assert "grid_export_kw" in step_log
