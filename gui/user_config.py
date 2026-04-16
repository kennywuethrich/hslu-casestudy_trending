"""Datenhaltung für GUI-Eingaben des Benutzers."""

from dataclasses import dataclass


@dataclass
class UserInputConfig:
    """Speichert alle GUI-Parameter des Benutzers."""
    
    num_evs: int
    hp_failure: bool
    smart_energy_enabled: bool
    variable_prices_enabled: bool
    price_night_chf_per_kwh: float = 0.15
    price_day_chf_per_kwh: float = 0.30
    
    def __repr__(self):
        params = [
            f"EVs={self.num_evs}",
            f"HP_Fail={self.hp_failure}",
            f"SmartEnergy={self.smart_energy_enabled}",
            f"VariablePrices={self.variable_prices_enabled}",
        ]
        if self.variable_prices_enabled:
            params.append(f"Night={self.price_night_chf_per_kwh}€ Day={self.price_day_chf_per_kwh}€")
        return f"UserConfig({', '.join(params)})"
