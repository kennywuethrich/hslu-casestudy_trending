"""
Orchestierungsschicht für die H2-Microgrid Simulation.

Verbindet Profile, Strategien und KPI-Auswertung.
Inputs: Scenario (Config + Profile-Modus)
Outputs: Ergebniscontainer pro Strategie + KPI-Export-Trigger
"""

import os
import pandas as pd
from typing import Dict, List, Tuple

from analyzer import calculate_kpis, save_kpis_by_scenario
from profiles import load_profiles
from scenario import Scenario
from strategies import Strategy, BaseStrategy, OptimizedStrategy


class Simulator:
    """Orchestriert Simulation: Profile → Strategien → KPIs."""
    
    def __init__(self, scenario: Scenario, scenario_number: int = None):
        """Initialisiert Simulator mit Szenario."""
        self.scenario = scenario
        self.scenario_number = scenario_number
        self.config = scenario.config
        self.results = {}  
        self.output_dir = "results"
        os.makedirs(self.output_dir, exist_ok=True)
        
        print(f"\n✓ Simulator initialisiert für: {scenario.name}")

    def generate_profiles(self) -> pd.DataFrame:
        """Lädt Energieprofile aus CSV."""
        print(f"  Lade Profile aus CSV (1h-Auflösung)...")
        profiles_df = load_profiles(self.config, ev_mode=self.scenario.ev_profile_mode)
        print(f"  ✓ Profile geladen ({len(profiles_df)} Zeitschritte)")
        return profiles_df
    
    def run_strategy(self, strategy: Strategy, 
                    profiles: pd.DataFrame = None) -> Tuple[pd.DataFrame, Dict]:
        """Führt Strategie aus und berechnet KPIs."""
        if profiles is None:
            profiles = self.generate_profiles()
        
        print(f"  Führe Strategie aus: {strategy.name}...")
        result_df = strategy.run(profiles)
        
        # KPIs berechnen
        label = f"{self.scenario.name} – {strategy.name}"
        kpis = calculate_kpis(result_df, self.config, label=label)
        
        strategy_key = strategy.name
        self.results[strategy_key] = {
            'strategy': strategy,
            'result_df': result_df,
            'kpis': kpis
        }
        
        print(f"    ✓ {strategy.name} abgeschlossen")
        return result_df, kpis
    
    def run_all_strategies(self, profiles: pd.DataFrame = None):
        """Führt alle Strategien aus und speichert KPIs."""
        if profiles is None:
            profiles = self.generate_profiles()
        
        print(f"\nFühre alle Strategien aus für: {self.scenario.name}")
        print("-" * 60)
        
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
        if len(self.results) >= 2 and self.scenario_number:
            kpi_base = list(self.results.values())[0]['kpis']
            kpi_optimized = list(self.results.values())[1]['kpis']
            save_kpis_by_scenario(self.scenario_number, kpi_base, kpi_optimized)
    
    def get_kpis_summary(self) -> List[Dict]:
        """Gibt KPIs aller Strategien zurück."""
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

        if include_plots:
            print("\nErstelle H2-SOC Visualisierungen...")
            print("  ⚠ Visualisierungen noch nicht implementiert")
    
    def __repr__(self):
        return f"Simulator(Scenario: {self.scenario.name}, Strategies: {len(self.results)})"
