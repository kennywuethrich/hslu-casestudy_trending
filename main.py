"""
Haupteinstiegspunkt für H2-Microgrid Energiesystem Simulation.
Benutzerfreundliche Schnittstelle für einfache Simulationen.
"""

from scenario import ScenarioManager, SCENARIOS_LIBRARY
from simulator import Simulator


def main():
    """Interaktive Hauptroutine."""
    
    print("\n" + "="*80)
    print(" "*20 + "H2-MICROGRID ENERGIESYSTEM SIMULATION")
    print("="*80)
    
    # 1. Verfügbare Szenarien anzeigen
    ScenarioManager.print_available()
    
    # 2. Szenario-Auswahl
    print("Wähle ein Szenario oder gib 'custom' für benutzerdefiniertes Szenario ein:")
    scenario_input = input("  Szenario-ID (A_reference/B_high_price/C_workplace/custom): ").strip().lower()
    
    if scenario_input == 'custom':
        print("\n⚠ Custom-Szenario-Erstellung wird derzeit nicht unterstützt.")
        print("  Bitte verwende vordefinierte Szenarien.")
        scenario_input = 'A_reference'
    
    # Szenario laden
    try:
        scenario = ScenarioManager.get_predefined(scenario_input)
    except ValueError as e:
        print(f"✗ Fehler: {e}")
        print("  Verwende Standard-Szenario 'A_reference'")
        scenario = ScenarioManager.get_predefined('A_reference')
    
    # 3. Simulator initialisieren
    simulator = Simulator(scenario)
    
    # 4. Profile generieren
    profiles = simulator.generate_profiles(hours=8760)
    
    # 5. Alle Strategien ausführen
    simulator.run_all_strategies(profiles)
    
    # 6. Ergebnisse anzeigen
    simulator.print_results(include_plots=True)
    
    # 7. Exportieren
    print("\nExportiere Ergebnisse...")
    simulator.export_results()
    
    print("\n✓ Simulation abgeschlossen!")
    print("="*80 + "\n")


def run_scenario(scenario_key: str, export: bool = True, include_plots: bool = True):
    """
    Schnelle Ausführung eines vordefinierten Szenarios.
    
    Args:
        scenario_key: Schlüssel aus SCENARIOS_LIBRARY
        export: Ob Ergebnisse exportiert werden sollen
        include_plots: Ob Jahresübersichts-Plots erstellt werden sollen
        
    Example:
        >>> run_scenario('A_reference')
    """
    print(f"\n{'='*80}")
    print(f"Starte Szenario: {scenario_key}")
    print(f"{'='*80}\n")
    
    # Szenario laden
    scenario = ScenarioManager.get_predefined(scenario_key)
    
    # Simulator
    simulator = Simulator(scenario)
    profiles = simulator.generate_profiles()
    simulator.run_all_strategies(profiles)
    
    # Ausgabe
    simulator.print_results(include_plots=include_plots)
    
    if export:
        simulator.export_results()
    
    return simulator


def compare_all_scenarios(export: bool = True):
    """
    Vergleicht alle vordefinierten Szenarien.
    
    Args:
        export: Ob Ergebnisse exportiert werden sollen
        
    Example:
        >>> compare_all_scenarios()
    """
    print("\n" + "="*80)
    print(" "*25 + "SZENARIO-VERGLEICH")
    print("="*80 + "\n")
    
    all_results = []
    
    for scenario_key in SCENARIOS_LIBRARY.keys():
        print(f"\n{'─'*80}")
        print(f"Szenario: {scenario_key}")
        print(f"{'─'*80}\n")
        
        simulator = run_scenario(scenario_key, export=False, include_plots=False)
        all_results.append(simulator)
    
    # Vergleich erstellen
    print("\n" + "="*80)
    print(" "*25 + "ERGEBNIS-ZUSAMMENFASSUNG")
    print("="*80)
    
    # Alle KPIs sammeln
    all_kpis = []
    for simulator in all_results:
        all_kpis.extend(simulator.get_kpis_summary())
    
    # KPI-Tabelle
    first_simulator = all_results[0]
    first_simulator.analyzer.print_kpi_table(all_kpis)
    
    # Plot
    print("Erstelle Vergleichsplot...")
    first_simulator.analyzer.plot_kpi_comparison(
        all_kpis,
        save_path="szenario_vergleich.png"
    )
    
    if export:
        first_simulator.analyzer.save_kpis_to_csv(all_kpis, "alle_szenarien_kpi.csv")
    
    print("\n✓ Szenario-Vergleich abgeschlossen!")
    print("="*80 + "\n")
    
    return all_results


if __name__ == "__main__":
    # Wähle eine dieser Optionen:
    
    # Option 1: Interaktiver Modus
    main()
    
    # Option 2: Direktes Szenario ausführen
    # run_scenario('A_reference')
    
    # Option 3: Alle Szenarien vergleichen
    # compare_all_scenarios()
