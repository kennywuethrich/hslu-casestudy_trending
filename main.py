"""Haupteinstieg für das Standardszenario."""

from scenario import ScenarioManager
from simulator import Simulator


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

    print("\nExportiere Ergebnisse...")
    simulator.export_results()
    
    print("\n✓ Simulation abgeschlossen!")
    print("="*80 + "\n")
if __name__ == "__main__":
    main()
