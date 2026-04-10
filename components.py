"""Komponenten für H2-Speicher, Elektrolyseur, Brennstoffzelle und Wärmepumpe."""

from typing import Dict
from config import SystemConfig


class H2Storage:
    """Wasserstoffspeicher mit SOC-Tracking."""
    
    def __init__(self, config: SystemConfig):
        self.capacity = config.h2_capacity_kwh
        self.soc_kwh = config.h2_initial_soc * self.capacity
        self.min_soc_kwh = config.h2_min_soc * self.capacity

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
        space = self.available_capacity
        actual = min(energy_kwh, space)
        self.soc_kwh += actual
        return actual

    def discharge(self, energy_kwh: float) -> float:
        available = self.available_discharge
        actual = min(energy_kwh, available)
        self.soc_kwh -= actual
        return actual

    def __repr__(self):
        return f"H2Storage(SOC={self.soc_pct:.1f}%, Capacity={self.capacity}kWh)"


class ThermalStorage:
    """Einfacher thermischer Speicher [kWh_th]."""

    def __init__(self, config: SystemConfig):
        self.capacity_kwh = config.thermal_storage_capacity_kwh
        self.soc_kwh = config.thermal_initial_soc * self.capacity_kwh

    @property
    def free_capacity(self) -> float:
        return max(0.0, self.capacity_kwh - self.soc_kwh)

    def charge(self, heat_kwh: float) -> float:
        actual = min(max(0.0, heat_kwh), self.free_capacity)
        self.soc_kwh += actual
        return actual

    def discharge(self, heat_kwh: float) -> float:
        actual = min(max(0.0, heat_kwh), self.soc_kwh)
        self.soc_kwh -= actual
        return actual


class Electrolyzer:
    """Elektrolyseur mit Mindestlast und fixer Effizienz."""
    
    def __init__(self, config: SystemConfig):
        self.p_max = config.ely_kw_max
        self.p_min = 0.1 * config.ely_kw_max  # 10% Mindestlast
        self.eff_el = config.ely_eff_el      # Strom → H2 Effizienz
        self.eff_th = config.ely_eff_th      # Strom → Abwärme Effizienz

    def run(self, power_available: float, dt_h: float = 1.0) -> Dict[str, float]:
        """
        Betreibt Elektrolyseur mit verfügbarer Leistung.
        
        Args:
            power_available: Verfügbare Leistung [kW]
            dt_h: Länge des Zeitschritts in Stunden
            
        Returns:
            dict: {'power_used': kW, 'h2_produced': kWh, 'heat_produced': kWh}
        """
        if power_available < self.p_min:
            return {'power_used': 0.0, 'h2_produced': 0.0, 'heat_produced': 0.0}

        power_used = min(power_available, self.p_max)
        h2_produced = power_used * self.eff_el * dt_h
        heat_produced = power_used * self.eff_th * dt_h
        
        return {
            'power_used': power_used,
            'h2_produced': h2_produced,
            'heat_produced': heat_produced
        }

    def __repr__(self):
        return (f"Electrolyzer(P_max={self.p_max}kW, "
                f"eff_el={self.eff_el:.0%}, eff_th={self.eff_th:.0%})")


class FuelCell:
    """Brennstoffzelle mit Mindestlast und fixer Effizienz."""
    
    def __init__(self, config: SystemConfig):
        self.p_max = config.fc_kw_max
        self.p_min = 0.1 * config.fc_kw_max
        self.eff_el = config.fc_eff_el      # H2 → Strom Effizienz
        self.eff_th = config.fc_eff_th      # H2 → Abwärme Effizienz

    def run(self, power_needed: float, h2_available: float, dt_h: float = 1.0) -> Dict[str, float]:
        power_target = min(power_needed, self.p_max)
        h2_needed = (power_target * dt_h) / self.eff_el
        h2_used = min(h2_needed, h2_available)
        power_out = (h2_used * self.eff_el / dt_h) if dt_h > 0 else 0.0

        if power_out < self.p_min:
            return {'power_out': 0.0, 'h2_used': 0.0, 'heat_produced': 0.0}

        heat_produced = h2_used * self.eff_th
        
        return {
            'power_out': power_out,
            'h2_used': h2_used,
            'heat_produced': heat_produced
        }

    def __repr__(self):
        return (f"FuelCell(P_max={self.p_max}kW, "
                f"eff_el={self.eff_el:.0%}, eff_th={self.eff_th:.0%})")


class HeatPump:
    """Wärmepumpe mit konstanter Leistungszahl."""
    
    def __init__(self, config: SystemConfig):
        self.cop = config.hp_cop
        self.p_th_max = config.hp_kw_th_max

    def __repr__(self):
        return f"HeatPump(COP={self.cop}, P_th_max={self.p_th_max}kW)"
