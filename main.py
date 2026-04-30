"""Haupteinstieg für das Standardszenario."""

from scenario import ScenarioManager
from simulator import simulate
from profiles import load_profiles
from strategies import BaseStrategy, OptimizedStrategy
from analyzer import calculate_kpis, print_kpi_table
from plots import plot_consumption_averages_comparison, plot_h2_soc_comparison


def main():
    """Führt die Simulation für das Standardszenario aus."""
    print("\n" + "=" * 80)
    print(" " * 20 + "H2-MICROGRID ENERGIESYSTEM SIMULATION")
    print("=" * 80)

    # Szenario laden
    scenario = ScenarioManager.get_default()
    print(f"\n✓ Szenario: {scenario.name}")
    print(f"  {scenario.description}\n")
    
    # Optional: Aktuelle Strompreise von der EKZ API abrufen
    print("--> Versuche, aktuelle Strompreise von EKZ API zu laden...")
    scenario.config.fetch_price_from_api()

    # Profile laden
    profiles_df = load_profiles(scenario.config)
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

    # H2-Füllstand plotten
    print("→ Generiere Plots...")
    plot_h2_soc_comparison(
        result_base,
        result_optimized,
        title="H2-Füllstand – Base vs Optimized",
        capacity_kwh=scenario.config.h2_capacity_kwh,
    )
    plot_consumption_averages_comparison(
        result_base,
        result_optimized,
        title="Stromkonsum-Mittelwerte – Base vs Optimized",
    )

    print("\n✓ Simulation abgeschlossen!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
