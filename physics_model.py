# Physikalisches Modell: Was passiert wenn die Strategie eine Entscheidung trifft.
#
# Datenfluss pro Zeitschritt:
#   strategy.decide(state, profile_t) → decision
#   model.step(state, decision, profile_t) → (new_state, step_log)

from __future__ import annotations
from dataclasses import dataclass
import pandas as pd
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config import SystemConfig


@dataclass
class SystemState:
    """Zustandsvektor des Energiesystems."""

    h2_mass_kg: float  # Wasserstoff im Drucktank [kg]
    T_room_C: float  # Raumtemperatur [°C]
    thermal_soc_kwh: float  # Thermischer Speicher [kWh_th]
    ev_soc_kwh: float  # EV-Batterie [kWh_el]


@dataclass
class Decision:
    """Steuerungsentscheidung der Strategie."""

    P_ely_kw: float  # Elektrolyseur-Leistung [kW_el]
    P_fc_kw: float  # Brennstoffzellen-Leistung [kW_el]
    P_ev_charge_kw: float  # EV-Ladeleistung [kW_el]
    P_hp_kw: float  # Wärmepumpen-Leistung elektrisch [kW_el]


class EnergySystemModel:
    """
    Berechnet die Physik des Energiesystems Schritt für Schritt.
    step() ist eine reine Funktion: (state, decision, profile_t) -> (new_state, log)
    """

    def __init__(self, config: SystemConfig):
        self.config = config
        self.dt_h = 1.0  # Zeitschrittweite [h]

    def initial_state(self) -> SystemState:
        """Anfangszustand aus Config-Parametern."""
        cfg = self.config
        return SystemState(
            h2_mass_kg=cfg.h2_total_mass_kg * cfg.h2_initial_soc,
            T_room_C=20.0,
            thermal_soc_kwh=cfg.thermal_storage_capacity_kwh * cfg.thermal_initial_soc,
            ev_soc_kwh=cfg.ev_capacity_kwh * 0.8,
        )

    def step(
        self,
        state: SystemState,
        decision: Decision,
        profile_t: pd.Series,
    ) -> tuple:
        """
        Einen Zeitschritt berechnen.

        Args:
            state:     Aktueller Systemzustand (wird NICHT veraendert)
            decision:  Steuerungsentscheidung der Strategie
            profile_t: Zeitreihendaten fuer diesen Zeitschritt

        Returns:
            (new_state, step_log)
        """
        cfg = self.config
        dt = self.dt_h

        # Profildaten
        P_pv_kw = float(profile_t["pv_kw"])
        P_load_el_kw = float(profile_t["load_el_kw"])
        Q_load_heat_kw = float(profile_t["load_heat_kw"])
        T_ambient_C = float(profile_t["outdoor_temp_c"])
        ev_driven_kwh = float(profile_t.get("ev_driven_kwh", 0.0))

        # Entscheidungen
        P_ely = decision.P_ely_kw
        P_fc = decision.P_fc_kw
        P_ev = decision.P_ev_charge_kw
        P_hp = decision.P_hp_kw

        # ===== 1) H2-SPEICHER =====
        # dm/dt = m_dot_in - m_dot_out
        m_dot_in = P_ely * cfg.ely_eff_el / cfg.h2_lhv_kwh_per_kg  # [kg/h]
        m_dot_out = P_fc / (cfg.fc_eff_el * cfg.h2_lhv_kwh_per_kg)  # [kg/h]
        delta_m = (m_dot_in - m_dot_out) * dt  # [kg]

        h2_min_kg = cfg.h2_total_mass_kg * cfg.h2_min_soc
        h2_max_kg = cfg.h2_total_mass_kg
        new_h2 = state.h2_mass_kg + delta_m
        new_h2 = max(h2_min_kg, min(h2_max_kg, new_h2))  # [kg]

        # ===== 2) GEBÄUDETEMPERATUR (RC-Modell) =====
        # C_th * dT/dt = Q_HP - Q_loss + Q_solar
        Q_HP = P_hp * cfg.hp_cop * dt  # [kWh_th]
        Q_loss = cfg.UA_kwh_per_K * (state.T_room_C - T_ambient_C) * dt  # [kWh_th]
        Q_solar = P_pv_kw * cfg.solar_gain_factor * dt  # [kWh_th]
        dT = (Q_HP - Q_loss + Q_solar) / cfg.C_th_kwh_per_K  # [K]

        new_T = state.T_room_C + dT
        new_T = max(16.0, min(26.0, new_T))  # [degC]

        # ===== 3) THERMISCHER SPEICHER =====
        Q_waste_ely = P_ely * cfg.ely_eff_th * dt  # [kWh_th]
        Q_waste_fc = P_fc * (cfg.fc_eff_th / cfg.fc_eff_el) * dt  # [kWh_th]
        Q_waste = Q_waste_ely + Q_waste_fc  # [kWh_th]

        Q_needed = Q_load_heat_kw * dt  # [kWh_th]
        Q_to_storage = max(0.0, Q_waste - Q_needed)  # [kWh_th]
        Q_from_storage = max(0.0, Q_needed - Q_waste)  # [kWh_th]

        new_th = state.thermal_soc_kwh + Q_to_storage - Q_from_storage
        new_th = max(0.0, min(cfg.thermal_storage_capacity_kwh, new_th))  # [kWh_th]

        # ===== 4) EV-BATTERIE =====
        # dSOC/dt = P_charge * eta - P_driven
        ev_charged = P_ev * cfg.ev_charge_efficiency * dt  # [kWh_el]
        new_ev = state.ev_soc_kwh + ev_charged - ev_driven_kwh
        new_ev = max(0.0, min(cfg.ev_capacity_kwh, new_ev))  # [kWh_el]

        # ===== 5) STROMBILANZ (algebraisch) =====
        # P_PV + P_FC + P_grid_in = P_load + P_ely + P_HP + P_EV + P_grid_out
        P_demand = P_load_el_kw + P_ely + P_hp + P_ev  # [kW_el]
        P_supply = P_pv_kw + P_fc  # [kW_el]
        P_grid_in = max(0.0, P_demand - P_supply)  # [kW_el]
        P_grid_out = max(0.0, P_supply - P_demand)  # [kW_el]

        # ===== Neuer Zustand =====
        new_state = SystemState(
            h2_mass_kg=new_h2,
            T_room_C=new_T,
            thermal_soc_kwh=new_th,
            ev_soc_kwh=new_ev,
        )

        step_log = {
            "grid_import_kw": P_grid_in,
            "grid_export_kw": P_grid_out,
            "ely_power_kw": P_ely,
            "fc_power_kw": P_fc,
            "hp_el_kw": P_hp,
            "ev_charge_kw": P_ev,
            "h2_mass_kg": new_h2,
            "h2_soc_pct": new_h2 / h2_max_kg * 100.0,
            "thermal_soc_kwh": new_th,
            "T_room_C": new_T,
            "ev_soc_kwh": new_ev,
            "heat_from_waste_kwh": Q_waste,
        }

        return new_state, step_log
