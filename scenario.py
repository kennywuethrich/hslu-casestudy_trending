"""
Szenario-Modul: Definition und Verwaltung von Simulationsszenarien.
"""

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
        ev_mode: E-Auto Lademodus
        description: Ausführliche Beschreibung
    """
    
    name: str
    config: SystemConfig
    ev_mode: Literal['evening', 'daytime', 'workplace'] = 'evening'
    description: str = ""
    
    def __repr__(self):
        return f"Scenario('{self.name}', EV-Mode: {self.ev_mode})"


# Vordefinierte Standard-Szenarien
SCENARIOS_LIBRARY = {
    'A_reference': Scenario(
        name="A: Referenz (Abend-Laden)",
        config=SystemConfig(
            price_buy_chf=0.28,
            price_sell_chf=0.10,
        ),
        ev_mode='evening',
        description="Moderate Strompreise, E-Auto lädt abends (18-22 Uhr)"
    ),
    
    'B_high_price': Scenario(
        name="B: Hoher Strompreis",
        config=SystemConfig(
            price_buy_chf=0.38,
            price_sell_chf=0.16,
            price_threshold_fc=0.35,
        ),
        ev_mode='evening',
        description="Erhöhte Strompreise und bessere Einspeisevergütung"
    ),
    
    'C_workplace': Scenario(
        name="C: Workplace Charging",
        config=SystemConfig(
            price_buy_chf=0.28,
            price_sell_chf=0.10,
        ),
        ev_mode='daytime',
        description="E-Auto lädt tagsüber am Arbeitsplatz (PV-optimiert)"
    ),
}


class ScenarioManager:
    """Verwaltet und erstellt Simulationsszenarien."""
    
    @staticmethod
    def get_predefined(scenario_key: str) -> Scenario:
        """
        Gibt vordefiniertes Szenario zurück.
        
        Args:
            scenario_key: Schlüssel aus SCENARIOS_LIBRARY
            
        Returns:
            Scenario: Das angeforderte Szenario
            
        Raises:
            ValueError: Wenn Szenario nicht existiert
        """
        if scenario_key not in SCENARIOS_LIBRARY:
            available = ', '.join(SCENARIOS_LIBRARY.keys())
            raise ValueError(
                f"Szenario '{scenario_key}' nicht gefunden. "
                f"Verfügbar: {available}"
            )
        return SCENARIOS_LIBRARY[scenario_key]
    
    @staticmethod
    def list_all() -> dict:
        """
        Gibt alle verfügbaren vordefinierten Szenarien.
        
        Returns:
            dict: Alle Szenarien mit Beschreibungen
        """
        return SCENARIOS_LIBRARY
    
    @staticmethod
    def create_custom(name: str, config: SystemConfig, 
                     ev_mode: str = 'evening',
                     description: str = "") -> Scenario:
        """
        Erstellt custom Szenario.
        
        Args:
            name: Szenarioname
            config: SystemConfig Objekt
            ev_mode: E-Auto Lademodus
            description: Optionale Beschreibung
            
        Returns:
            Scenario: Das neue Szenario
        """
        return Scenario(
            name=name,
            config=config,
            ev_mode=ev_mode,
            description=description
        )
    
    @staticmethod
    def print_available():
        """Gibt alle verfügbaren Szenarien formatiert aus."""
        print("\n" + "="*70)
        print("VERFÜGBARE VORDEFINIERTE SZENARIEN")
        print("="*70)
        
        for key, scenario in SCENARIOS_LIBRARY.items():
            print(f"\n  {key}: {scenario.name}")
            print(f"    EV-Mode: {scenario.ev_mode}")
            print(f"    Preis Kauf: {scenario.config.price_buy_chf} CHF/kWh")
            print(f"    Preis Verkauf: {scenario.config.price_sell_chf} CHF/kWh")
            if scenario.description:
                print(f"    {scenario.description}")
        
        print("\n" + "="*70 + "\n")
