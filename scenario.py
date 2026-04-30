"""Szenarien für die Strategie-Vergleiche."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
from config import SystemConfig


@dataclass
class Scenario:
    """
    Definiert ein vollständiges Simulationsszenario.

    Attributes:
        name: Szenarioname
        config: Systemkonfiguration
        description: Ausführliche Beschreibung
    """

    name: str
    config: SystemConfig
    description: str = ""

    def __repr__(self) -> str:
        return f"Scenario('{self.name}')"


def _build_scenarios() -> List[Scenario]:
    """Erstellt alle verfügbaren Szenarien ohne Seiteneffekte beim Import."""
    default_config = SystemConfig()
    return [
        Scenario(
            name="Szenario A",
            config=default_config,
            description=(
                "Baseline-Szenario mit aktuellen Strompreisen.\n\n"
                "• Strombezug: aktueller Preis\n"
                "• Stromverkauf: Standardwert\n\n"
                "Dieses Szenario dient als Standard zur Vergleichbarkeit."
            ),
        ),
        Scenario(
            name="Szenario B",
            config=SystemConfig(price_buy_chf=0.15, price_sell_chf=0.08),
            description=(
                "Szenario mit günstigen Strompreisen.\n\n"
                "• Strombezug: 0.15 CHF/kWh\n"
                "• Stromeinspeisung: 0.08 CHF/kWh\n\n"
                "Günstige Preise begünstigen H2-Produktion (Elektrolyse)."
            ),
        ),
    ]


class ScenarioManager:
    """Verwaltet verfügbare Szenarien."""

    _scenarios: Optional[List[Scenario]] = None

    @classmethod
    def _ensure_scenarios_loaded(cls) -> List[Scenario]:
        if cls._scenarios is None:
            cls._scenarios = _build_scenarios()
        return cls._scenarios

    @classmethod
    def get_all_scenarios(cls) -> List[Scenario]:
        """Gibt alle Szenarien zurück."""
        return cls._ensure_scenarios_loaded()

    @classmethod
    def get_by_name(cls, name: str) -> Scenario:
        """Gibt Szenario nach Name zurück."""
        for scenario in cls._ensure_scenarios_loaded():
            if scenario.name == name:
                return scenario
        raise ValueError(f"Szenario '{name}' nicht gefunden")

    @classmethod
    def get_default(cls) -> Optional[Scenario]:
        """Gibt erstes Szenario als Default zurück."""
        scenarios = cls._ensure_scenarios_loaded()
        return scenarios[0] if scenarios else None


if __name__ == "__main__":
    print(f"Total scenarios: {len(ScenarioManager.get_all_scenarios())}")
    print(f"Default: {ScenarioManager.get_default()}")
