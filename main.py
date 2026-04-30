"""Haupteinstieg für Szenario-Vergleiche."""

from scenario import ScenarioManager
from simulator import simulate
from profiles import load_profiles
from strategies import BaseStrategy, OptimizedStrategy
from analyzer import (
    calculate_kpis,
    print_kpi_table,
    save_kpis_by_scenario,
)
from plots import plot_consumption_averages_comparison, plot_h2_soc_comparison


def run_scenario(scenario_number: int, scenario) -> tuple:
    """Führt Simulation für ein Szenario aus.

    Args:
        scenario_number: Szenario-Nummer (für CSV-Speicherung)
        scenario: Scenario-Objekt mit config

    Returns:
        (kpi_base, kpi_optimized) Tuple
    """
    print("\n" + "=" * 80)
    print(f"Szenario {scenario_number}: {scenario.name}")
    print("=" * 80)
    print(f"{scenario.description}\n")

    # Profile laden
    profiles_df = load_profiles(scenario.config)
    print(f"✓ Strompreis: {profiles_df['price_buy'].iloc[0]:.4f} CHF/kWh")
    print(f"✓ Profile geladen: {len(profiles_df)} Zeitschritte")

    # Simulationen mit beiden Strategien
    base_strategy = BaseStrategy(scenario.config)
    optimized_strategy = OptimizedStrategy(scenario.config)

    print(f"\n→ Starte BaseStrategy...")
    result_base = simulate(profiles_df, scenario.config, base_strategy)

    print(f"→ Starte OptimizedStrategy...")
    result_optimized = simulate(profiles_df, scenario.config, optimized_strategy)

    # KPIs berechnen
    kpi_base = calculate_kpis(result_base, scenario.config, label="BaseStrategy")
    kpi_optimized = calculate_kpis(
        result_optimized, scenario.config, label="OptimizedStrategy"
    )

    # Ergebnisse ausgeben
    print_kpi_table([kpi_base, kpi_optimized])

    # KPIs speichern
    save_kpis_by_scenario(scenario_number, kpi_base, kpi_optimized)

    # Plots
    print("→ Generiere Plots...")
    plot_h2_soc_comparison(
        result_base,
        result_optimized,
        title=f"{scenario.name}: H2-Füllstand – Base vs Optimized",
        capacity_kwh=scenario.config.h2_capacity_kwh,
    )
    plot_consumption_averages_comparison(
        result_base,
        result_optimized,
        title=f"{scenario.name}: Netzbezug-Mittelwerte – Base vs Optimized",
    )

    return kpi_base, kpi_optimized


def main():
    """Führt Simulationen für alle Szenarien aus."""
    print("\n" + "=" * 80)
    print(" " * 15 + "H2-MICROGRID ENERGIESYSTEM SIMULATION")
    print(" " * 20 + "SZENARIO-VERGLEICH")
    print("=" * 80)

    # Szenario A
    scenario_a = ScenarioManager.get_by_name("Szenario A")
    print(f"\n--> Versuche, aktuelle Strompreise von EKZ API zu laden...")
    scenario_a.config.fetch_price_from_api()

    kpi_base_a, kpi_opt_a = run_scenario(1, scenario_a)

    # Szenario B
    scenario_b = ScenarioManager.get_by_name("Szenario B")
    kpi_base_b, kpi_opt_b = run_scenario(2, scenario_b)

    print("\n" + "=" * 80)
    print("ZUSAMMENFASSUNG ALLE SZENARIEN")
    print("=" * 80)
    print("\nSzenario A (aktueller Preis):")
    print(f"  BaseStrategy:      {kpi_base_a['Energiekosten [CHF/a]']:.0f} CHF/a")
    print(f"  OptimizedStrategy: {kpi_opt_a['Energiekosten [CHF/a]']:.0f} CHF/a")
    print(
        f"  Ersparnis:         {kpi_base_a['Energiekosten [CHF/a]'] - kpi_opt_a['Energiekosten [CHF/a]']:.0f} CHF/a"
    )

    print("\nSzenario B (günstiger Preis):")
    print(f"  BaseStrategy:      {kpi_base_b['Energiekosten [CHF/a]']:.0f} CHF/a")
    print(f"  OptimizedStrategy: {kpi_opt_b['Energiekosten [CHF/a]']:.0f} CHF/a")
    print(
        f"  Ersparnis:         {kpi_base_b['Energiekosten [CHF/a]'] - kpi_opt_b['Energiekosten [CHF/a]']:.0f} CHF/a"
    )

    print("\nPreis-Vergleich (BaseStrategy):")
    print(
        f"  Szenario A teurer: {kpi_base_a['Energiekosten [CHF/a]'] - kpi_base_b['Energiekosten [CHF/a]']:.0f} CHF/a"
    )

    print("\n✓ Alle Szenarien simuliert und gespeichert!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
