"""Tests fuer die Simulations-Orchestrierung."""

from __future__ import annotations

import pandas as pd

from config import SystemConfig
from physics_model import Decision
from simulator import simulate


class DummyStrategy:
    """Einfache Teststrategie mit konstanten Sollwerten."""

    def decide(self, state, profile_t):
        """Liefert stets eine neutrale Entscheidung ohne Komponenteneinsatz."""

        _ = (state, profile_t)
        return Decision(P_ely_kw=0.0, P_fc_kw=0.0, P_ev_charge_kw=0.0, P_hp_kw=0.0)


def test_simulate_returns_rowwise_results() -> None:
    """Prueft, dass simulate pro Eingangszeile einen Output erzeugt."""

    config = SystemConfig()
    profile_df = pd.DataFrame(
        [
            {
                "pv_kw": 5.0,
                "load_el_kw": 10.0,
                "load_heat_kw": 8.0,
                "outdoor_temp_c": 6.0,
                "ev_driven_kwh": 1.0,
                "price_buy": 0.3,
                "price_sell": 0.1,
                "co2_intensity": 0.128,
                "dt_h": 1.0,
            },
            {
                "pv_kw": 20.0,
                "load_el_kw": 8.0,
                "load_heat_kw": 6.0,
                "outdoor_temp_c": 9.0,
                "ev_driven_kwh": 0.0,
                "price_buy": 0.2,
                "price_sell": 0.1,
                "co2_intensity": 0.128,
                "dt_h": 1.0,
            },
        ]
    )

    result = simulate(profile_df, config, DummyStrategy())

    assert len(result) == len(profile_df)
    assert "grid_import_kw" in result.columns
    assert "h2_soc_pct" in result.columns
