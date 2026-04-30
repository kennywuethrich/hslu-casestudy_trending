"""Haupteinstieg für den Vergleich von Szenario A und B."""

from typing import Dict, Tuple

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


def run_scenario(scenario_slot: str, scenario) -> Tuple[Dict, Dict]:
    """Führt Simulation für einen A/B-Slot aus.

    Args:
        scenario_slot: A oder B (für CSV-Speicherung)
        scenario: Scenario-Objekt mit config

    Returns:
        (kpi_base, kpi_optimized) Tuple
    """
    print("\n" + "=" * 80)
    print(f"Szenario {scenario_slot}: {scenario.name}")
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
    save_kpis_by_scenario(scenario_slot, kpi_base, kpi_optimized)

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


def main() -> None:
    """Führt Simulationen für Szenario A und Szenario B aus."""
    print("\n" + "=" * 80)
    print(" " * 15 + "H2-MICROGRID ENERGIESYSTEM SIMULATION")
    print(" " * 20 + "SZENARIO-VERGLEICH")
    print("=" * 80)

    scenarios = ScenarioManager.get_all_scenarios()
    if len(scenarios) < 2:
        raise ValueError("Es werden mindestens zwei Szenarien benötigt")

    scenario_a = scenarios[0]
    scenario_b = scenarios[1]

    if scenario_a.name in {"Szenario A", "Szenario 1"}:
        print("\n--> Versuche, aktuelle Strompreise von EKZ API zu laden...")
        scenario_a.config.fetch_price_from_api()

    kpi_base_a, kpi_opt_a = run_scenario("A", scenario_a)
    kpi_base_b, kpi_opt_b = run_scenario("B", scenario_b)

    print("\n" + "=" * 80)
    print("ZUSAMMENFASSUNG")
    print("=" * 80)
    print("\nSzenario A:")
    print(f"  BaseStrategy:      {kpi_base_a['Energiekosten [CHF/a]']:.0f} CHF/a")
    print(f"  OptimizedStrategy: {kpi_opt_a['Energiekosten [CHF/a]']:.0f} CHF/a")
    print(
        "  Ersparnis:         "
        f"{kpi_base_a['Energiekosten [CHF/a]'] - kpi_opt_a['Energiekosten [CHF/a]']:.0f} CHF/a"
    )

    print("\nSzenario B:")
    print(f"  BaseStrategy:      {kpi_base_b['Energiekosten [CHF/a]']:.0f} CHF/a")
    print(f"  OptimizedStrategy: {kpi_opt_b['Energiekosten [CHF/a]']:.0f} CHF/a")
    print(
        "  Ersparnis:         "
        f"{kpi_base_b['Energiekosten [CHF/a]'] - kpi_opt_b['Energiekosten [CHF/a]']:.0f} CHF/a"
    )

    print("\n✓ Szenario A und B simuliert und gespeichert!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
