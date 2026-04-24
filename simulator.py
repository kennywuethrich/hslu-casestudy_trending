# Simulations-Schleife: Modell + Strategie zusammenstecken.

import pandas as pd
from config import SystemConfig
from physics_model import EnergySystemModel


def simulate(
    profile_df: pd.DataFrame,
    config: SystemConfig,
    strategy,
) -> pd.DataFrame:
    """
    Simuliert das Energiesystem über den gesamten Zeitraum.

    Args:
        profile_df: Zeitreihendaten (pv_kw, load_el_kw, load_heat_kw,
                    outdoor_temp_c, ev_driven_kwh, price_buy, price_sell, co2_intensity)
        config:     Systemparameter
        strategy:   Betriebsstrategie mit .decide(state, profile_t)

    Returns:
        DataFrame: Eingangsprofil + Simulationsergebnisse pro Zeitschritt
    """
    model = EnergySystemModel(config)
    state = model.initial_state()

    results = []

    for _, row in profile_df.iterrows():
        # 1. Strategie entscheidet: Was tun in diesem Zeitschritt?
        decision = strategy.decide(state, row)

        # 2. Physik berechnet neuen Zustand und loggt alle Groessen
        new_state, step_log = model.step(state, decision, row)

        results.append(step_log)
        state = new_state

    return pd.concat(
        [profile_df.reset_index(drop=True), pd.DataFrame(results)],
        axis=1,
    )
