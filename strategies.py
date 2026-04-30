# strategies.py
# Betriebsstrategien für das Gebäude-Energiesystem
#
# Aufgabe dieser Datei:
#   Entscheiden WIE VIEL Leistung jede Komponente in einem Zeitschritt bekommt.
#   Die Physik (was diese Leistung bewirkt) passiert in physics_model.py.
#
# Struktur:
#   BaseStrategy      → Einfache Wenn-Dann Regeln
#   OptimizedStrategy → Preisoptimierte Erweiterung von BaseStrategy

from typing import Optional

import pandas as pd
from config import SystemConfig
from physics_model import SystemState, Decision

# ---------------------------------------------------------------------------
# BaseStrategy — regelbasiert, einfache Wenn-Dann Logik
# ---------------------------------------------------------------------------


class BaseStrategy:
    """
    Einfache regelbasierte Steuerung.

    Jede Komponente wird nach klaren Wenn-Dann Regeln gesteuert.
    Kein Lookahead, keine Optimierung — nur der aktuelle Zeitschritt zählt.
    """

    # Konstanten (gelten für beide Strategien)
    ELY_MIN_LOAD_FRACTION = 0.10  # Elektrolyseur startet erst ab 10% der Maxlast
    H2_SOC_FULL = 0.95  # H₂-Speicher gilt als "voll" bei 95%
    HP_MIN_TEMP_C = 5.0  # Wärmepumpe nur ab +5°C Außentemperatur

    def __init__(self, config: SystemConfig):
        self.config = config
        # Maximale H₂-Masse für SOC-Berechnung
        self.h2_max_mass_kg = config.h2_total_mass_kg

    def decide(
        self,
        state: SystemState,
        profile_t: pd.Series,
        forecast_t: Optional[pd.DataFrame] = None,
    ) -> Decision:
        """
        Trifft Steuerungsentscheidung für diesen Zeitschritt.

        Args:
            state:     Aktueller Systemzustand
            profile_t: Zeitreihendaten für diesen Zeitschritt

        Returns:
            Decision mit Leistungssollwerten [kW] für alle Komponenten
        """
        # Eingangsdaten lesen
        pv_kw = float(profile_t["pv_kw"])  # PV-Erzeugung [kW]
        load_el_kw = float(profile_t["load_el_kw"])  # Elektrischer Bedarf [kW]
        load_heat_kw = float(profile_t["load_heat_kw"])  # Wärmebedarf [kW]
        outdoor_temp_c = float(profile_t["outdoor_temp_c"])  # Außentemperatur [°C]
        price_buy = float(profile_t["price_buy"])  # Strompreis [CHF/kWh]
        ev_driven_kwh = float(profile_t.get("ev_driven_kwh", 0.0))  # Gefahrene kWh

        # H₂-Füllstand berechnen (0.0 = leer, 1.0 = voll)
        h2_soc = state.h2_mass_kg / self.h2_max_mass_kg

        # PV-Überschuss (positiv = mehr PV als Grundlast)
        pv_surplus_kw = pv_kw - load_el_kw

        # Entscheidungen für jede Komponente
        P_ely_kw = self._decide_electrolyzer(pv_surplus_kw, h2_soc)
        P_fc_kw = self._decide_fuel_cell(pv_surplus_kw, h2_soc, price_buy)
        P_hp_kw = self._decide_heat_pump(load_heat_kw, outdoor_temp_c)
        P_ev_charge_kw = self._decide_ev(ev_driven_kwh)

        return Decision(
            P_ely_kw=P_ely_kw,
            P_fc_kw=P_fc_kw,
            P_hp_kw=P_hp_kw,
            P_ev_charge_kw=P_ev_charge_kw,
        )

    def _decide_electrolyzer(self, pv_surplus_kw: float, h2_soc: float) -> float:
        """
        Elektrolyseur einschalten wenn PV-Überschuss vorhanden und Speicher nicht voll.

        Regel:
          WENN PV-Überschuss > Mindestlast (10% p_max)
            UND H₂-Speicher nicht voll (SOC < 95%)
          DANN Leistung = min(PV-Überschuss, ely_kw_max)
          SONST 0 kW
        """
        ely_min_kw = self.ELY_MIN_LOAD_FRACTION * self.config.ely_kw_max

        if pv_surplus_kw < ely_min_kw:
            return 0.0  # Zu wenig Überschuss → aus

        if h2_soc >= self.H2_SOC_FULL:
            return 0.0  # Speicher voll → aus

        return min(pv_surplus_kw, self.config.ely_kw_max)

    def _decide_fuel_cell(
        self, pv_surplus_kw: float, h2_soc: float, price_buy: float
    ) -> float:
        """
        Brennstoffzelle einschalten wenn Strombedarf nicht durch PV gedeckt
        und Netzlast zu groß (Peak Shaving).

        Regel:
          WENN PV-Defizit > 0
            UND Defizit > fc_peak_shaving_kw (Lastspitzen-Schwellenwert)
            UND H₂-SOC > h2_min_soc
          DANN Leistung = min(Defizit, fc_dispatch_max_kw)
          SONST 0 kW
        """
        deficit_kw = -pv_surplus_kw  # positiv wenn mehr Bedarf als PV

        if deficit_kw <= 0.0:
            return 0.0  # Kein Defizit → FC nicht nötig

        peak_shave_trigger = deficit_kw > self.config.fc_peak_shaving_kw

        if not peak_shave_trigger:
            return 0.0  # Keine Lastspitze → aus

        if h2_soc <= self.config.h2_min_soc:
            return 0.0  # Speicher fast leer → schützen

        return min(deficit_kw, self.config.fc_dispatch_max_kw)

    def _decide_heat_pump(self, load_heat_kw: float, outdoor_temp_c: float) -> float:
        """
        Wärmepumpe einschalten wenn Wärmebedarf vorhanden und Außentemperatur ok.

        Regel:
          WENN Wärmebedarf > 0
            UND Außentemperatur >= 5°C
          DANN el. Leistung = load_heat_kw / COP  (begrenzt auf hp_kw_th_max / COP)
          SONST 0 kW

        Rückgabe: elektrische Leistung [kW], nicht thermische!
        """
        if load_heat_kw <= 0.0:
            return 0.0  # Kein Wärmebedarf

        if outdoor_temp_c < self.HP_MIN_TEMP_C:
            return 0.0  # Zu kalt → WP ineffizient

        p_el_needed_kw = load_heat_kw / self.config.hp_cop  # [kW_el]
        p_el_max_kw = self.config.hp_kw_th_max / self.config.hp_cop  # [kW_el]

        return min(p_el_needed_kw, p_el_max_kw)

    def _decide_ev(self, ev_driven_kwh: float) -> float:
        """
        EV: Nachladen was gefahren wurde (einfache Regel).

        Regel:
          WENN heute gefahren (ev_driven_kwh > 0)
          DANN Ladeleistung = ev_driven_kwh / 1h (in einer Stunde nachladen)
          SONST 0 kW
        """
        if ev_driven_kwh <= 0.0:
            return 0.0

        p_charge_kw = ev_driven_kwh / 1.0  # [kW] — in 1 Stunde nachladen
        return min(p_charge_kw, self.config.ev_charge_max_kw)


# ---------------------------------------------------------------------------
# OptimizedStrategy — preisoptimiert, erweitert BaseStrategy
# ---------------------------------------------------------------------------


class OptimizedStrategy(BaseStrategy):
    """
    Optimierte Steuerung mit 24h-Forecast für Brennstoffzelle.

    Unterschied zu BaseStrategy:
      - Elektrolyseur: wie BaseStrategy (PV-Überschuss)
      - Brennstoffzelle: mit 24h-Vorausblick optimiert
      - Wärmepumpe: wie BaseStrategy (nur Wärmebedarf decken)
      - EV: Normales Laden (keine Preis-Abhängigkeit)

    Technische Implementierung:
      - forecast_profile_24h: Optional DataFrame mit nächsten 24 Stunden
      - _decide_fuel_cell_opt(): Nutzt Forecast zur Entladungsplanung
    """

    def decide(
        self,
        state: SystemState,
        profile_t: pd.Series,
        forecast_t: Optional[pd.DataFrame] = None,
    ) -> Decision:
        """
        Kleine MPC-artige Logik mit 24h-Vorschau.

        Die Forecast-Sicht wird vor allem für die Brennstoffzelle genutzt,
        damit wir bei Bedarf jetzt entladen und später mit PV wieder füllen
        können.
        """

        # Eingangsdaten lesen
        pv_kw = float(profile_t["pv_kw"])
        load_el_kw = float(profile_t["load_el_kw"])
        load_heat_kw = float(profile_t["load_heat_kw"])
        outdoor_temp_c = float(profile_t["outdoor_temp_c"])
        price_buy = float(profile_t["price_buy"])
        ev_driven_kwh = float(profile_t.get("ev_driven_kwh", 0.0))

        h2_soc = state.h2_mass_kg / self.h2_max_mass_kg
        thermal_soc = state.thermal_soc_kwh / self.config.thermal_storage_capacity_kwh
        ev_soc_frac = state.ev_soc_kwh / self.config.ev_capacity_kwh

        pv_surplus_kw = pv_kw - load_el_kw

        # Basisregel für PV-Nutzung und Wärmebedarf
        P_ely_kw = self._decide_electrolyzer(pv_surplus_kw, h2_soc)
        P_fc_kw = self._decide_fuel_cell_opt(
            pv_surplus_kw,
            h2_soc,
            price_buy,
            thermal_soc,
            forecast_t,
        )
        P_hp_kw = self._decide_heat_pump(load_heat_kw, outdoor_temp_c)

        # EV bleibt einfach und robust
        P_ev_charge_kw = self._decide_ev_opt(ev_driven_kwh, ev_soc_frac, price_buy)

        return Decision(
            P_ely_kw=P_ely_kw,
            P_fc_kw=P_fc_kw,
            P_hp_kw=P_hp_kw,
            P_ev_charge_kw=P_ev_charge_kw,
        )

    def _decide_ev_opt(
        self, ev_driven_kwh: float, ev_soc_frac: float, price_buy: float
    ) -> float:
        """
        EV-Laden: Nachladen wenn gefahren wurde.

        Regel:
          WENN gefahren (ev_driven_kwh > 0)
          DANN Ladeleistung = ev_driven_kwh / 1h
          SONST 0 kW
        """
        if ev_driven_kwh <= 0.0:
            return 0.0

        p_charge_kw = min(ev_driven_kwh / 1.0, self.config.ev_charge_max_kw)
        return p_charge_kw

    def _summarize_forecast(self, forecast_t: Optional[pd.DataFrame]) -> dict:
        """Fasst ein 24h-Fenster zu einfachen Energiesummen zusammen."""
        if forecast_t is None or len(forecast_t) <= 1:
            return {
                "future_pv_surplus_kwh": 0.0,
                "future_el_deficit_kwh": 0.0,
                "future_heat_load_kwh": 0.0,
            }

        future_t = forecast_t.iloc[1:]
        future_pv_surplus_kwh = (
            (future_t["pv_kw"] - future_t["load_el_kw"]).clip(lower=0.0).sum()
        )
        future_el_deficit_kwh = (
            (future_t["load_el_kw"] - future_t["pv_kw"]).clip(lower=0.0).sum()
        )
        future_heat_load_kwh = future_t["load_heat_kw"].sum()

        return {
            "future_pv_surplus_kwh": float(future_pv_surplus_kwh),
            "future_el_deficit_kwh": float(future_el_deficit_kwh),
            "future_heat_load_kwh": float(future_heat_load_kwh),
        }

    def _decide_fuel_cell_opt(
        self,
        pv_surplus_kw: float,
        h2_soc: float,
        price_buy: float,
        thermal_soc: float,
        forecast_t: Optional[pd.DataFrame],
    ) -> float:
        """Entscheidet die Brennstoffzelle mit 24h-Forecast."""
        base = self._decide_fuel_cell(pv_surplus_kw, h2_soc, price_buy)
        if base > 0.0:
            return base

        deficit_kw = -pv_surplus_kw
        if deficit_kw <= 0.0 or h2_soc <= self.config.h2_min_soc:
            return 0.0

        forecast = self._summarize_forecast(forecast_t)
        future_pv_surplus_kwh = forecast["future_pv_surplus_kwh"]
        future_el_deficit_kwh = forecast["future_el_deficit_kwh"]
        future_heat_load_kwh = forecast["future_heat_load_kwh"]

        thermal_buffer_need = (
            future_heat_load_kwh > 0.35 * self.config.thermal_storage_capacity_kwh
            and thermal_soc < 0.85
        )
        pv_recovery_expected = future_pv_surplus_kwh >= future_el_deficit_kwh

        if thermal_buffer_need or pv_recovery_expected:
            return min(deficit_kw, self.config.fc_dispatch_max_kw)

        return 0.0
