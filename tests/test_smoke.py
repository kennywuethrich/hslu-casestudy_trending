"""Einfacher Smoke-Test für die Projekt-Basisfunktionalität."""

import pandas as pd

from config import SystemConfig
from simulator import simulate
from strategies import BaseStrategy


def test_smoke_simulation_pipeline() -> None:
    """Prüft, dass eine minimale Simulation durchläuft."""
    config = SystemConfig(price_buy_chf=0.28, price_sell_chf=0.10)
    profile_df = pd.DataFrame(
        [
            {
                "pv_kw": 0.0,
                "load_el_kw": 5.0,
                "load_heat_kw": 8.0,
                "outdoor_temp_c": 10.0,
                "ev_driven_kwh": 0.0,
                "price_buy": 0.28,
                "price_sell": 0.10,
                "co2_intensity": 0.128,
                "dt_h": 1.0,
            }
        ]
    )

    result = simulate(profile_df, config, BaseStrategy(config))

    assert len(result) == 1
    assert "h2_soc_pct" in result.columns
    assert result["h2_soc_pct"].iloc[0] >= 0
    assert result["h2_soc_pct"].iloc[0] <= 100
