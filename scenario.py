"""Szenarien für die Strategie-Vergleiche."""

from dataclasses import dataclass
from typing import Literal, List
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


SCENARIOS = [
    Scenario(
        name="Szenario A",
        config=SystemConfig(),  # Preise werden automatisch von der API abgerufen
        ev_profile_mode='as_is',
        description=f"Baseline-Szenario mit aktuellen Strompreisen (von EKZ API).\n\n"
                   f"• Strombezug: {SystemConfig().price_buy_chf:.4f} CHF/kWh\n"
                   f"• Stromverkauf: {SystemConfig().price_sell_chf:.4f} CHF/kWh\n"
                   f"• EV-Profil: Über den Tag verteilt\n\n"
                   f"Dieses Szenario dient als Standard zur Vergleichbarkeit." 

    ),
    Scenario(
        name="Szenario B",
        config=SystemConfig(
            price_buy_chf=0.15,
            price_sell_chf=0.08,
        ),
        ev_profile_mode='as_is',
        description="Szenario mit günstigen Strompreisen.\n\n"
                   "• Strombezug: 0.15 CHF/kWh (niedrig)\n"
                   "• Stromeinspeisung: 0.08 CHF/kWh\n"
                   "• EV-Profil: Über den Tag verteilt\n\n"
                   "Günstige Preise begünstigen H2-Produktion (Elektrolyse)."
    ),
    #TODO ERWEITERBAR ~ Kenny, 16.04.2026
    # E-Autos werden von Pierre abgeklärt. maybe auch mit verschiedenen Fahrzeugtypen (Plugin Hybrid, hybrid, Vollelektro) und verschiedene Szenarien. Auto schon vorheizen im Winter, Batterie schon aufwärmen, damit der Wirkungsgrad des Autos besser ist (Strom aus dem Haus ist günstiger als Batterie-Strom des E-Autos.)
]


class ScenarioManager:
    """Verwaltet verfügbare Szenarien."""
    
    @staticmethod
    def get_all_scenarios() -> List[Scenario]:
        """Gibt alle Szenarien zurück."""
        return SCENARIOS
    
    @staticmethod
    def get_by_name(name: str) -> Scenario:
        """Gibt Szenario nach Name zurück."""
        for scenario in SCENARIOS:
            if scenario.name == name:
                return scenario
        raise ValueError(f"Szenario '{name}' nicht gefunden")
    
    @staticmethod
    def get_default() -> Scenario:
        """Gibt erstes Szenario als Default zurück."""
        return SCENARIOS[0] if SCENARIOS else None


if __name__ == '__main__':
    print(f"Total scenarios: {len(ScenarioManager.get_all_scenarios())}")
    print(f"Default: {ScenarioManager.get_default()}")
    print(f"Scenario A: {ScenarioManager.get_by_name('Szenario A').config.price_buy_chf} CHF/kWh")
