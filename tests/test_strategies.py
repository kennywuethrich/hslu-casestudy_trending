"""Tests fuer Base- und Optimized-Strategie."""

from __future__ import annotations

import pandas as pd

from config import SystemConfig
from physics_model import SystemState
from strategies import BaseStrategy, OptimizedStrategy


def _state(config: SystemConfig, h2_soc: float = 0.5) -> SystemState:
    """Erzeugt einen Systemzustand mit konfigurierbarem H2-SOC."""

    return SystemState(
        h2_mass_kg=config.h2_total_mass_kg * h2_soc,
        T_room_C=20.0,
        thermal_soc_kwh=config.thermal_storage_capacity_kwh * 0.5,
        ev_soc_kwh=config.ev_capacity_kwh * 0.5,
    )


def _profile(**overrides: float) -> pd.Series:
    """Erzeugt ein Standardprofil und ueberschreibt einzelne Felder."""

    values = {
        "pv_kw": 0.0,
        "load_el_kw": 10.0,
        "load_heat_kw": 10.0,
        "outdoor_temp_c": 10.0,
        "ev_driven_kwh": 0.0,
        "price_buy": 0.35,
        "price_sell": 0.1,
        "co2_intensity": 0.128,
        "dt_h": 1.0,
    }
    values.update(overrides)
    return pd.Series(values)


def test_base_strategy_uses_fc_on_expensive_deficit() -> None:
    """Prueft FC-Einsatz bei Defizit und hohem Strompreis."""

    config = SystemConfig()
    strategy = BaseStrategy(config)

    decision = strategy.decide(
        _state(config, h2_soc=0.5),
        _profile(pv_kw=0.0, load_el_kw=20.0, price_buy=0.5),
    )

    assert decision.P_fc_kw > 0.0


def test_base_strategy_disables_hp_below_min_temperature() -> None:
    """Prueft, dass die Waermepumpe bei zu tiefer Temperatur aus bleibt."""

    config = SystemConfig()
    strategy = BaseStrategy(config)

    decision = strategy.decide(
        _state(config),
        _profile(load_heat_kw=20.0, outdoor_temp_c=0.0),
    )

    assert decision.P_hp_kw == 0.0


def test_optimized_strategy_charges_ely_when_power_is_cheap() -> None:
    """Prueft den Preisvorteilsmodus der optimierten Strategie."""

    config = SystemConfig()
    strategy = OptimizedStrategy(config)

    decision = strategy.decide(
        _state(config, h2_soc=0.2),
        _profile(pv_kw=0.0, load_el_kw=0.0, price_buy=0.1),
    )

    assert decision.P_ely_kw == config.ely_kw_max
