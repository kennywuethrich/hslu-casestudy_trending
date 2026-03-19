"""
Komponenten-Modul: H2-Speicher, Elektrolyseur, Brennstoffzelle, Wärmepumpe.
"""

from typing import Dict
from config import SystemConfig


class H2Storage:
    """
    Wasserstoffspeicher mit State-of-Charge (SOC) Tracking.
    Kann geladen und entladen werden mit Kapazitätslimits.
    """
    
    def __init__(self, config: SystemConfig):
        self.capacity = config.h2_capacity_kwh
        self.soc_kwh = config.h2_initial_soc * self.capacity
        self.min_soc_kwh = config.h2_min_soc * self.capacity
        self._charge_history = []
        self._discharge_history = []

    @property
    def soc_pct(self) -> float:
        """State of Charge in Prozent [0-100%]"""
        return 100.0 * self.soc_kwh / self.capacity

    @property
    def available_capacity(self) -> float:
        """Verfügbare Kapazität für Speicherung [kWh]"""
        return self.capacity - self.soc_kwh

    @property
    def available_discharge(self) -> float:
        """Verfügbare Entladung (ohne unter Minimum zu gehen) [kWh]"""
        return max(0.0, self.soc_kwh - self.min_soc_kwh)

    def charge(self, energy_kwh: float) -> float:
        """
        Lädt Speicher mit gegebener Energie.
        
        Returns:
            float: Tatsächlich gespeicherte Energie [kWh]
        """
        space = self.available_capacity
        actual = min(energy_kwh, space)
        self.soc_kwh += actual
        self._charge_history.append(actual)
        return actual

    def discharge(self, energy_kwh: float) -> float:
        """
        Entlädt Speicher mit gegebener Energie.
        
        Returns:
            float: Tatsächlich entnommene Energie [kWh]
        """
        available = self.available_discharge
        actual = min(energy_kwh, available)
        self.soc_kwh -= actual
        self._discharge_history.append(actual)
        return actual

    def reset(self, config: SystemConfig):
        """Setzt Speicher auf Anfangszustand zurück."""
        self.soc_kwh = config.h2_initial_soc * self.capacity
        self._charge_history = []
        self._discharge_history = []

    def __repr__(self):
        return f"H2Storage(SOC={self.soc_pct:.1f}%, Capacity={self.capacity}kWh)"


class Electrolyzer:
    """
    Elektrolyseur: Wandelt Strom in H2 (chemische Energie) + Abwärme.
    Minimale Teillast: 10% der Nennleistung (realistisch für PEM-ELY).
    """
    
    def __init__(self, config: SystemConfig):
        self.p_max = config.ely_kw_max
        self.p_min = 0.1 * config.ely_kw_max  # 10% Mindestlast
        self.eff_el = config.ely_eff_el      # Strom → H2 Effizienz
        self.eff_th = config.ely_eff_th      # Strom → Abwärme Effizienz
        self._runtime_history = []

    def run(self, power_available: float) -> Dict[str, float]:
        """
        Betreibt Elektrolyseur mit verfügbarer Leistung.
        
        Args:
            power_available: Verfügbare Leistung [kW]
            
        Returns:
            dict: {'power_used': kW, 'h2_produced': kWh, 'heat_produced': kWh}
        """
        # Wenn zu wenig Leistung für Mindestlast → ELY aus
        if power_available < self.p_min:
            return {'power_used': 0.0, 'h2_produced': 0.0, 'heat_produced': 0.0}

        power_used = min(power_available, self.p_max)
        h2_produced = power_used * self.eff_el
        heat_produced = power_used * self.eff_th
        
        self._runtime_history.append(power_used)
        
        return {
            'power_used': power_used,
            'h2_produced': h2_produced,
            'heat_produced': heat_produced
        }

    def __repr__(self):
        return (f"Electrolyzer(P_max={self.p_max}kW, "
                f"eff_el={self.eff_el:.0%}, eff_th={self.eff_th:.0%})")


class FuelCell:
    """
    Brennstoffzelle: Wandelt H2 in Strom + Abwärme.
    Minimale Teillast: 10% der Nennleistung.
    """
    
    def __init__(self, config: SystemConfig):
        self.p_max = config.fc_kw_max
        self.p_min = 0.1 * config.fc_kw_max
        self.eff_el = config.fc_eff_el      # H2 → Strom Effizienz
        self.eff_th = config.fc_eff_th      # H2 → Abwärme Effizienz
        self._runtime_history = []

    def run(self, power_needed: float, h2_available: float) -> Dict[str, float]:
        """
        Betreibt Brennstoffzelle unter Berücksichtigung von 
        Leistungsbedarf und H2-Verfügbarkeit.
        
        Args:
            power_needed: Benötigte Leistung [kW]
            h2_available: Verfügbarer Wasserstoff [kWh]
            
        Returns:
            dict: {'power_out': kW, 'h2_used': kWh, 'heat_produced': kWh}
        """
        power_target = min(power_needed, self.p_max)
        h2_needed = power_target / self.eff_el
        h2_used = min(h2_needed, h2_available)
        power_out = h2_used * self.eff_el

        # Mindestlast-Check
        if power_out < self.p_min:
            return {'power_out': 0.0, 'h2_used': 0.0, 'heat_produced': 0.0}

        heat_produced = h2_used * self.eff_th
        self._runtime_history.append(power_out)
        
        return {
            'power_out': power_out,
            'h2_used': h2_used,
            'heat_produced': heat_produced
        }

    def __repr__(self):
        return (f"FuelCell(P_max={self.p_max}kW, "
                f"eff_el={self.eff_el:.0%}, eff_th={self.eff_th:.0%})")


class HeatPump:
    """
    Wärmepumpe mit konstantem Leistungszahl (COP).
    Deckt Wärmebedarf durch elektrische Leistung.
    """
    
    def __init__(self, config: SystemConfig):
        self.cop = config.hp_cop
        self.p_th_max = config.hp_kw_th_max
        self._runtime_history = []

    def cover_heat_demand(self, heat_demand: float, el_available: float) -> Dict[str, float]:
        """
        Deckt Wärmebedarf mit verfügbarer elektrischer Leistung.
        
        Args:
            heat_demand: Wärmebedarf [kWh]
            el_available: Verfügbare elektrische Leistung [kW]
            
        Returns:
            dict: {'heat_out': kWh, 'el_used': kW, 'heat_unmet': kWh}
        """
        heat_possible_by_power = el_available * self.cop
        heat_possible = min(heat_demand, self.p_th_max, heat_possible_by_power)
        el_used = heat_possible / self.cop
        heat_unmet = heat_demand - heat_possible
        
        self._runtime_history.append(el_used)
        
        return {
            'heat_out': heat_possible,
            'el_used': el_used,
            'heat_unmet': heat_unmet
        }

    def __repr__(self):
        return f"HeatPump(COP={self.cop}, P_th_max={self.p_th_max}kW)"
