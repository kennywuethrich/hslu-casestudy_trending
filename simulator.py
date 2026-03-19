"""
Simulator-Modul: Koordiniert die gesamte H2-Microgrid Simulation.
"""

import pandas as pd
from typing import List, Dict, Tuple
from config import SystemConfig
from profiles import ProfileGenerator
from strategies import Strategy, HeuristicStrategy, PriceBasedStrategy
from analyzer import ResultAnalyzer
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
    
    def __init__(self, scenario: Scenario):
        """
        Initialisiert Simulator mit Szenario.
        
        Args:
            scenario: Scenario Objekt mit Config und EV-Mode
        """
        self.scenario = scenario
        self.config = scenario.config
        self.profile_generator = ProfileGenerator()
        self.analyzer = ResultAnalyzer(self.config)
        self.results = {}  # Speichert Ergebnisse aller Strategien
        
        print(f"\n✓ Simulator initialisiert für: {scenario.name}")
    
    def generate_profiles(self, hours: int = 8760) -> pd.DataFrame:
        """
        Generiert oder lädt Energieprofile.
        
        Args:
            hours: Anzahl Stunden (Standard: 8760 = 1 Jahr)
            
        Returns:
            pd.DataFrame: Vollständige Energieprofile
        """
        print(f"  Generiere Profile ({hours} Stunden)...")
        profiles = self.profile_generator.generate_annual_profiles(
            hours=hours,
            ev_mode=self.scenario.ev_mode
        )
        print(f"  ✓ Profile generiert")
        return profiles
    
    def run_strategy(self, strategy: Strategy, 
                    profiles: pd.DataFrame = None) -> Tuple[pd.DataFrame, Dict]:
        """
        Führt Betriebsstrategie aus.
        
        Args:
            strategy: Strategy Objekt (HeuristicStrategy oder PriceBasedStrategy)
            profiles: Optional: Vordefinierte Profile. Wenn None, werden neu generiert.
            
        Returns:
            tuple: (result_df, kpis_dict)
        """
        if profiles is None:
            profiles = self.generate_profiles()
        
        print(f"  Führe Strategie aus: {strategy.name}...")
        result_df = strategy.run(profiles)
        
        # KPIs berechnen
        label = f"{self.scenario.name}\n{strategy.name}"
        kpis = self.analyzer.calculate_kpis(result_df, label=label)
        
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
        
        strategies = [
            HeuristicStrategy(self.config),
            PriceBasedStrategy(self.config)
        ]
        
        for strategy in strategies:
            self.run_strategy(strategy, profiles)
    
    def get_kpis_summary(self) -> List[Dict]:
        """
        Gibt Zusammenfassung aller KPIs zurück.
        
        Returns:
            list: Liste von KPI-Dicts
        """
        return [result['kpis'] for result in self.results.values()]
    
    def print_results(self, include_plots: bool = False):
        """
        Gibt Ergebnisse formatiert aus.
        
        Args:
            include_plots: Ob Plots generiert werden sollen
        """
        if not self.results:
            print("⚠ Keine Simulationsergebnisse vorhanden!")
            return
        
        print("\n" + "="*80)
        print(f"SIMULATIONSERGEBNISSE: {self.scenario.name}")
        print("="*80)
        
        for strategy_key, result in self.results.items():
            kpis = result['kpis']
            print(f"\n{'─'*80}")
            print(f"  Strategie: {strategy_key}")
            print(f"{'─'*80}")
            
            for key, value in kpis.items():
                if key != 'label':
                    print(f"    {key:<35} {value:>15}")
        
        # KPI-Tabelle
        self.analyzer.print_kpi_table(self.get_kpis_summary())
        
        # Plots
        if include_plots:
            self._create_plots()
    
    def _create_plots(self):
        """Erstellt Visualisierungen."""
        print("\nErstelle Visualisierungen...")
        
        for strategy_key, result in self.results.items():
            result_df = result['result_df']
            
            # Sommerwoche
            title = f"{self.scenario.name} – {strategy_key} – Sommerwoche"
            save_path = f"woche_sommer_{strategy_key.lower()}.png"
            self.analyzer.plot_week(result_df, title=title,
                                   start_day=172, save_path=save_path)
            
            # Winterwoche
            title = f"{self.scenario.name} – {strategy_key} – Winterwoche"
            save_path = f"woche_winter_{strategy_key.lower()}.png"
            self.analyzer.plot_week(result_df, title=title,
                                   start_day=10, save_path=save_path)
        
        # KPI-Vergleich
        kpis_list = self.get_kpis_summary()
        self.analyzer.plot_kpi_comparison(kpis_list, 
                                         save_path="kpi_vergleich.png")
    
    def export_results(self, csv_filepath: str = "simulationsergebnisse.csv"):
        """
        Exportiert Detailergebnisse.
        
        Args:
            csv_filepath: Zieldatei für CSV
        """
        for strategy_key, result in self.results.items():
            result_df = result['result_df']
            filename = f"{csv_filepath.replace('.csv', '')}_{strategy_key}.csv"
            result_df.to_csv(filename, index=False)
            print(f"  ✓ Exportiert: {filename}")
        
        # KPIs zu CSV
        kpis_list = self.get_kpis_summary()
        self.analyzer.save_kpis_to_csv(kpis_list)
    
    def __repr__(self):
        return f"Simulator(Scenario: {self.scenario.name}, Strategies: {len(self.results)})"
