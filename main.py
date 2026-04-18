"""Haupteinstieg für das Standardszenario."""

from scenario import ScenarioManager
from simulator import Simulator

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
    simulator.analyzer.save_kpis_to_csv(simulator.get_kpis_summary())
    
    print("\n✓ Simulation abgeschlossen!")
    print("="*80 + "\n")
    
if __name__ == "__main__":
    main()
