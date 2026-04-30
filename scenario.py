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
            name="Szenario 1",
            config=default_config,
            description=(
                "Baseline-Szenario mit aktuellen Strompreisen.\n\n"
                "• Strombezug: aktueller Preis\n"
                "• Stromverkauf: Standardwert\n\n"
                "Dieses Szenario dient als Standard zur Vergleichbarkeit."
            ),
        ),
        Scenario(
            name="Szenario 2",
            config=SystemConfig(price_buy_chf=0.15, price_sell_chf=0.08),
            description=(
                "Szenario mit günstigen Strompreisen.\n\n"
                "• Strombezug: 0.15 CHF/kWh\n"
                "• Stromeinspeisung: 0.08 CHF/kWh\n\n"
                "Günstige Preise begünstigen H2-Produktion (Elektrolyse)."
            ),
        ),
        Scenario(
            name="Szenario 3",
            config=SystemConfig(
                scenario_id="commuter_peak",
                ev_profile_mode="commuter_peak",
                ev_fleet_size=24,
                ev_evening_trip_kwh_per_vehicle=7.0,
                ev_capacity_kwh=1440.0,
                ev_charge_max_kw=264.0,
            ),
            description=(
                "Pendler-Flotte mit Abend-Peak.\n\n"
                "• 24 E-Autos als Flotte\n"
                "• Fahrenergie konzentriert Mo-Fr von 18-21 Uhr\n"
                "• Hohe gleichzeitige Ladeleistung am Abend\n\n"
                "Dieses Szenario stresst Lastspitzen und Peak-Shaving."
            ),
        ),
        Scenario(
            name="Szenario 4",
            config=SystemConfig(
                scenario_id="grid_limit",
                grid_import_limit_kw=45.0,
            ),
            description=(
                "Netzlimit-Szenario mit begrenztem Netzanschluss.\n\n"
                "• Maximaler Netzbezug: 45 kW\n"
                "• Nicht gedeckter Bedarf wird als KPI ausgewiesen\n\n"
                "Dieses Szenario testet Robustheit bei Netzengpässen."
            ),
        ),
        Scenario(
            name="Szenario 5",
            config=SystemConfig(
                scenario_id="cold_week_travel_weekend",
                ev_profile_mode="travel_weekend",
                ev_fleet_size=10,
                ev_evening_trip_kwh_per_vehicle=4.0,
                ev_capacity_kwh=600.0,
                ev_charge_max_kw=110.0,
                cold_week_enabled=True,
                cold_week_start_day=330,
                cold_week_duration_days=7,
                cold_week_delta_c=-9.0,
                travel_weekend_enabled=True,
                travel_weekend_start_day=333,
                travel_trip_kwh_per_vehicle=35.0,
            ),
            description=(
                "Kalte Woche plus EV-Reise-Wochenende.\n\n"
                "• 7 Tage Kältewelle im Winter\n"
                "• Zusätzliche EV-Reisen am Wochenende\n"
                "• Erhöhte Wärme- und Mobilitätslast gleichzeitig\n\n"
                "Dieses Szenario reizt Speicher- und Prognoselogik aus."
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
