"""Einfaches Standardszenario für die Simulation."""

from dataclasses import dataclass
from typing import Literal
from config import SystemConfig


@dataclass
class Scenario:
    """
    Definiert ein vollständiges Simulationsszenario.
    
    Attributes:
        name: Szenarioname
        config: Systemkonfiguration
        ev_profile_mode: Modus zur EV-Profilaufbereitung
        description: Ausführliche Beschreibung
    """
    
    name: str
    config: SystemConfig
    ev_profile_mode: Literal['as_is', 'daytime'] = 'as_is'
    description: str = ""
    
    def __repr__(self):
        return f"Scenario('{self.name}')"



DEFAULT_SCENARIO = Scenario(
    name="Referenzszenario",
    config=SystemConfig(
        price_buy_chf=0.28,
        price_sell_chf=0.10,
    ),
    ev_profile_mode='as_is',
    description="Einfaches Basisszenario für spätere GUI-Parametrisierung."
)


class ScenarioManager:
    """Verwaltet das einzige aktive Standardszenario."""
    
    @staticmethod
    def print_available():
        """Gibt das aktive Standardszenario aus."""
        print("\n" + "="*70)
        print("AKTIVES STANDARDSZENARIO")
        print("="*70)

        scenario = DEFAULT_SCENARIO
        print(f"\n  {scenario.name}")
        print(f"    EV-Profilmodus: {scenario.ev_profile_mode}")
        print(f"    Preis Kauf: {scenario.config.price_buy_chf} CHF/kWh")
        print(f"    Preis Verkauf: {scenario.config.price_sell_chf} CHF/kWh")
        if scenario.description:
            print(f"    {scenario.description}")

        print("\n" + "="*70 + "\n")

    @staticmethod
    def get_default() -> Scenario:
        return DEFAULT_SCENARIO
