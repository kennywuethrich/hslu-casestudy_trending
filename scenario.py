"""
Szenariodefinitionen für wiederholbare Modellläufe.

Entwickler-Kurzinfo:
- Zweck: Verwaltet vordefinierte und benutzerdefinierte Szenarien.
- Inputs: SystemConfig, ev_profile_mode und Beschreibung.
- Outputs: Scenario-Objekte für den Simulator.
- Typische Änderungen: Neue Szenarien oder geänderte Parameterwerte.
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
        ev_profile_mode: Modus zur EV-Profilaufbereitung
        description: Ausführliche Beschreibung
    """
    
    name: str
    config: SystemConfig
    ev_profile_mode: Literal['as_is', 'daytime'] = 'as_is'
    description: str = ""
    
    def __repr__(self):
        return f"Scenario('{self.name}')"



#TODO Szenarien definiern!!!!!!!!! 


# Vordefinierte Standard-Szenarien
SCENARIOS_LIBRARY = {
    'A_reference': Scenario(
        name="A: Referenz (Abend-Laden)",
        config=SystemConfig(
            price_buy_chf=0.28,
            price_sell_chf=0.10,
        ),
        ev_profile_mode='as_is',
        description="Moderate Strompreise, E-Auto lädt abends (18-22 Uhr)"
    ),
    
    'B_high_price': Scenario(
        name="B: Hoher Strompreis",
        config=SystemConfig(
            price_buy_chf=0.38,
            price_sell_chf=0.16,
            price_threshold_fc=0.35,
        ),
        ev_profile_mode='as_is',
        description="Erhöhte Strompreise und bessere Einspeisevergütung"
    ),
    
    'C_workplace': Scenario(
        name="C: Workplace Charging",
        config=SystemConfig(
            price_buy_chf=0.28,
            price_sell_chf=0.10,
        ),
        ev_profile_mode='daytime',
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
                     ev_profile_mode: str = 'as_is',
                     description: str = "") -> Scenario:
        """
        Erstellt custom Szenario.
        
        Args:
            name: Szenarioname
            config: SystemConfig Objekt
            ev_profile_mode: 'as_is' oder 'daytime'
            description: Optionale Beschreibung
            
        Returns:
            Scenario: Das neue Szenario
        """
        return Scenario(
            name=name,
            config=config,
            ev_profile_mode=ev_profile_mode,
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
            print(f"    EV-Profilmodus: {scenario.ev_profile_mode}")
            print(f"    Preis Kauf: {scenario.config.price_buy_chf} CHF/kWh")
            print(f"    Preis Verkauf: {scenario.config.price_sell_chf} CHF/kWh")
            if scenario.description:
                print(f"    {scenario.description}")
        
        print("\n" + "="*70 + "\n")
