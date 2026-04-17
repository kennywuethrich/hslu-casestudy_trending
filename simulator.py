"""
Orchestrierungsschicht für die H2-Microgrid Simulation.

Verbindet Profile, Strategien und KPI-Auswertung.
Inputs: Scenario (Config + Profile-Modus)
Outputs: Ergebniscontainer pro Strategie + KPI-Export-Trigger
"""

import os
import pandas as pd
from typing import Dict, List, Tuple

from profiles import load_profiles as profiles
from strategies import Strategy
from analyzer import calculate_kpis as analyzer
from scenario import Scenario


class Simulator:
    """
    Hauptsimulations-Engine für H2-Microgrid Energiesystem.
    
    Koordiniert:
    - Profil-Generierung
    - Strategiebetrieb
    - KPI-Berechnung
    - Visualisierung
    """
    
    def __init__(self, scenario: Scenario, scenario_number: int = None):
        """
        Initialisiert Simulator mit Szenario.
        
        Args:
            scenario: Scenario Objekt mit Config
            scenario_number: Nummer des Szenarios in der Simulation (1 oder 2)
        """
        self.scenario = scenario
        self.scenario_number = scenario_number
        self.config = scenario.config
        self.results = {}  
        self.output_dir = "results"
        os.makedirs(self.output_dir, exist_ok=True)
        
        print(f"\n✓ Simulator initialisiert für: {scenario.name}")

    def generate_profiles(self) -> pd.DataFrame:
        """
        Lädt Energieprofile aus CSV (1h Auflösung).
        
        Returns:
            pd.DataFrame: Vollständige Energieprofile
        """
        print(f"  Lade Profile aus CSV (1h-Auflösung)...")
        profiles_df = profiles(self.config, ev_mode=self.scenario.ev_profile_mode)
        print(f"  ✓ Profile geladen ({len(profiles_df)} Zeitschritte)")
        return profiles_df
    
    def run_strategy(self, strategy: Strategy, 
                    profiles: pd.DataFrame = None) -> Tuple[pd.DataFrame, Dict]: #Optional profiles erzeugen, wenn nichts übergeben wird
        """
        Führt Betriebsstrategie aus.
        
        Args:
            strategy: Strategy Objekt (HeuristicStrategy oder PriceBasedStrategy)
            profiles: Optional: Vordefinierte Profile. Wenn None, werden neu generiert.
            
        Returns:
            tuple: (result_df, kpis_dict)
        """
        if profiles is None:
            profiles = self.generate_profiles() #generiert profiles, wenn keine übergeben wurden
        
        print(f"  Führe Strategie aus: {strategy.name}...")
        result_df = strategy.run(profiles)
        
        # KPIs berechnen
        label = f"{self.scenario.name} – {strategy.name}"
        kpis = analyzer(result_df, self.config, label=label)
        
        # Speichern
        strategy_key = strategy.name
        self.results[strategy_key] = {
            'strategy': strategy,
            'result_df': result_df,
            'kpis': kpis
        }
        
        print(f"    ✓ {strategy.name} abgeschlossen")
        return result_df, kpis
    
    def run_all_strategies(self, profiles: pd.DataFrame = None):
        """
        Führt alle verfügbaren Standardstrategien aus.
        
        Args:
            profiles: Optional: Vordefinierte Profile
        """
        if profiles is None:
            profiles = self.generate_profiles()
        
        print(f"\nFühre alle Strategien aus für: {self.scenario.name}")
        print("-" * 60)
        
        from strategies import BaseStrategy, OptimizedStrategy
        
        strategies = [
            BaseStrategy(self.config),
            OptimizedStrategy(self.config),
        ]
        
        for strategy in strategies:
            self.run_strategy(strategy, profiles)
        
        # Speichere KPIs als CSV
        self._save_scenario_kpis()
    
    def _save_scenario_kpis(self):
        """Speichert KPIs des Szenarios als CSV."""
        from analyzer import save_kpis_by_scenario
        
        if len(self.results) >= 2 and self.scenario_number:
            kpi_base = list(self.results.values())[0]['kpis']
            kpi_optimized = list(self.results.values())[1]['kpis']
            save_kpis_by_scenario(self.scenario_number, kpi_base, kpi_optimized)
    
    def get_kpis_summary(self) -> List[Dict]:
        """
        Gibt Zusammenfassung aller KPIs zurück.
        
        Returns:
            list: Liste von KPI-Dicts
        """
        return [result['kpis'] for result in self.results.values()]
    
    def print_results(self, include_plots: bool = False):
        """Gibt Ergebnisse formatiert aus."""
        if not self.results:
            print("⚠ Keine Simulationsergebnisse vorhanden!")
            return

        print("\n" + "=" * 80)
        print(f"SIMULATIONSERGEBNISSE: {self.scenario.name}")
        print("=" * 80)

        for strategy_key, result in self.results.items():
            kpis = result['kpis']
            print(f"\n{'─' * 80}")
            print(f"  Strategie: {strategy_key}")
            print(f"{'─' * 80}")

            for key, value in kpis.items():
                if key != 'label':
                    print(f"    {key:<35} {value:>15}")

        self.analyzer.print_kpi_table(self.get_kpis_summary())

        if include_plots:
            print("\nErstelle H2-SOC Visualisierungen...")
            for strategy_key, result in self.results.items():
                result_df = result['result_df']
                title = f"{self.scenario.name} – {strategy_key} – H2-SOC Jahresverlauf"
                save_path = f"h2_soc_jahr_{strategy_key.lower()}.png"
                self.analyzer.plot_h2_soc_year(result_df, title=title, save_path=save_path)
    
    def __repr__(self):
        return f"Simulator(Scenario: {self.scenario.name}, Strategies: {len(self.results)})"
