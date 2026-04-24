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

    def decide(self, state: SystemState, profile_t: pd.Series) -> Decision:
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
        und Preis hoch oder Netzlast zu groß.

        Regel:
          WENN PV-Defizit > 0
            UND (Preis > price_threshold_fc ODER Defizit > fc_peak_shaving_kw)
            UND H₂-SOC > h2_min_soc
          DANN Leistung = min(Defizit, fc_dispatch_max_kw)
          SONST 0 kW
        """
        deficit_kw = -pv_surplus_kw  # positiv wenn mehr Bedarf als PV

        if deficit_kw <= 0.0:
            return 0.0  # Kein Defizit → FC nicht nötig

        price_trigger = price_buy > self.config.price_threshold_fc
        peak_shave_trigger = deficit_kw > self.config.fc_peak_shaving_kw

        if not (price_trigger or peak_shave_trigger):
            return 0.0  # Weder teurer Strom noch Lastspitze → aus

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
    Preisoptimierte Steuerung — erweitert die Basisstrategie.

    Zusätzliche Logik:
      - Elektrolyseur: Auch bei günstigem Strompreis einschalten ("günstigen Strom einlagern")
      - Brennstoffzelle: H₂-Puffer proaktiv abbauen wenn Speicher zu voll
      - Wärmepumpe: Thermischen Speicher bei PV-Überschuss vorladen
      - EV: Smart Charging — nur laden wenn Preis günstig oder Akku fast leer
    """

    PRICE_THRESHOLD_CHEAP = 0.20  # CHF/kWh — "günstiger" Strom
    THERMAL_SOC_TARGET = 0.80  # Thermischen Speicher bis 80% vorladen

    def decide(self, state: SystemState, profile_t: pd.Series) -> Decision:
        """Wie BaseStrategy, aber mit preisoptimierten Überschreibungen."""

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

        P_ely_kw = self._decide_electrolyzer_opt(pv_surplus_kw, h2_soc, price_buy)
        P_fc_kw = self._decide_fuel_cell_opt(pv_surplus_kw, h2_soc, price_buy)
        P_hp_kw = self._decide_heat_pump_opt(
            load_heat_kw, outdoor_temp_c, pv_surplus_kw, thermal_soc
        )
        P_ev_charge_kw = self._decide_ev_opt(ev_driven_kwh, ev_soc_frac, price_buy)

        return Decision(
            P_ely_kw=P_ely_kw,
            P_fc_kw=P_fc_kw,
            P_hp_kw=P_hp_kw,
            P_ev_charge_kw=P_ev_charge_kw,
        )

    def _decide_electrolyzer_opt(
        self, pv_surplus_kw: float, h2_soc: float, price_buy: float
    ) -> float:
        """
        Wie BaseStrategy, aber zusätzlich: Einschalten wenn Strom günstig ist.

        Zusatzregel:
          WENN Preis < 0.20 CHF/kWh UND Speicher nicht voll
          DANN Elektrolyseur mit Maxlast betreiben ("günstigen Strom einlagern")
        """
        # Erst Basisregel prüfen
        base = self._decide_electrolyzer(pv_surplus_kw, h2_soc)
        if base > 0.0:
            return base

        # Zusatz: Günstiger Strom verfügbar?
        if h2_soc >= self.H2_SOC_FULL:
            return 0.0  # Speicher voll → kein Einlagern möglich

        if price_buy < self.PRICE_THRESHOLD_CHEAP:
            return self.config.ely_kw_max  # Volle Last bei günstigem Preis

        return 0.0

    def _decide_fuel_cell_opt(
        self, pv_surplus_kw: float, h2_soc: float, price_buy: float
    ) -> float:
        """
        Wie BaseStrategy, aber zusätzlich: H₂-Puffer proaktiv abbauen.

        Zusatzregel:
          WENN h2_soc > fc_reserve_soc_target
          DANN FC mit halber Last betreiben (Platz für nächsten PV-Tag schaffen)
        """
        base = self._decide_fuel_cell(pv_surplus_kw, h2_soc, price_buy)
        if base > 0.0:
            return base

        # Speicher zu voll → proaktiv entladen
        if (
            h2_soc > self.config.fc_reserve_soc_target
            and h2_soc > self.config.h2_min_soc
        ):
            return self.config.fc_dispatch_max_kw * 0.5

        return 0.0

    def _decide_heat_pump_opt(
        self,
        load_heat_kw: float,
        outdoor_temp_c: float,
        pv_surplus_kw: float,
        thermal_soc: float,
    ) -> float:
        """
        Wie BaseStrategy, aber zusätzlich: Thermischen Speicher bei PV-Überschuss vorladen.

        Zusatzregel:
          WENN PV-Überschuss > 0 UND thermischer Speicher-SOC < 80%
          DANN WP mit Überschuss betreiben um Speicher zu laden
        """
        base = self._decide_heat_pump(load_heat_kw, outdoor_temp_c)

        # Speicher vorladen wenn PV-Überschuss und Platz vorhanden?
        if (
            pv_surplus_kw > 0.0
            and thermal_soc < self.THERMAL_SOC_TARGET
            and outdoor_temp_c >= self.HP_MIN_TEMP_C
        ):
            p_el_extra_kw = min(
                pv_surplus_kw, self.config.hp_kw_th_max / self.config.hp_cop
            )
            return max(base, p_el_extra_kw)

        return base

    def _decide_ev_opt(
        self, ev_driven_kwh: float, ev_soc_frac: float, price_buy: float
    ) -> float:
        """
        Smart Charging: Nur laden wenn Preis günstig oder Akku fast leer.

        Regeln:
          WENN EV fast leer (SOC < 20%) → immer laden (Notfall)
          WENN Preis günstig (< 0.20 CHF/kWh) → laden
          SONST warten
        """
        if ev_driven_kwh <= 0.0:
            return 0.0

        p_charge_kw = min(ev_driven_kwh / 1.0, self.config.ev_charge_max_kw)

        # Notfall: Akku fast leer → sofort laden
        if ev_soc_frac < 0.20:
            return p_charge_kw

        # Normales Laden: nur wenn Strom günstig
        if price_buy < self.PRICE_THRESHOLD_CHEAP:
            return p_charge_kw

        return 0.0  # Warten auf günstigeren Zeitpunkt
