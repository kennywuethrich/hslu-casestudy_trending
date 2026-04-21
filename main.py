"""Haupteinstieg für das Standardszenario."""


from scenario import ScenarioManager
from simulator import Simulator
from plots import plot_h2_soc

# Keine Funktion mehr. Wir starten über .\gui\gui_main.py

def main():
    """Führt das einzige aktive Standardszenario aus."""
    print("\n" + "="*80)
    print(" "*20 + "H2-MICROGRID ENERGIESYSTEM SIMULATION")
    print("="*80)

    ScenarioManager.print_available()

    scenario = ScenarioManager.get_default()
    simulator = Simulator(scenario)
    profiles = simulator.generate_profiles(hours=8760)

    simulator.run_all_strategies(profiles)
    simulator.print_results(include_plots=True)

    # H2-Füllstand für jede Strategie plotten
    for strat_key, result in simulator.results.items():
        df = result['result_df']
        cap = simulator.config.h2_capacity_kwh
        plot_h2_soc(df, title=f"H2-Füllstand – {strat_key}", capacity_kwh=cap)

    # KPIs speichern
    # simulator.analyzer.save_kpis_to_csv(simulator.get_kpis_summary())
    
    print("\n✓ Simulation abgeschlossen!")
    print("="*80 + "\n")
    
if __name__ == "__main__":
    main()
