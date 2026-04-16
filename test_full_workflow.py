"""Test kompletter Workflow: GUI-Config -> Simulation -> Ergebnisse."""

from user_config import UserInputConfig
from scenario_builder import ScenarioBuilder
from simulator import Simulator
from profiles import ProfileGenerator
from config import SystemConfig


def test_full_workflow():
    print("=" * 70)
    print("VOLLSTÄNDIGER WORKFLOW-TEST")
    print("=" * 70)

    # 1. Lade Basis-Profile
    print("\n1. Lade Basis-Profile...")
    pg = ProfileGenerator()
    config = SystemConfig()
    profiles = pg.load_simulation_profiles(config)
    print(f"   ✓ {len(profiles)} Zeitschritte")

    # 2. Simuliere GUI-Eingabe: 2 EVs, Smart Energy, Wärmepumpe OK
    print("\n2. Erstelle Benutzer-Szenario (GUI)...")
    user_cfg = UserInputConfig(
        num_evs=2,
        hp_failure=False,
        smart_energy_enabled=True,
        variable_prices_enabled=False,
        price_night_chf_per_kwh=0.15,
        price_day_chf_per_kwh=0.28
    )
    print(f"   ✓ {user_cfg}")

    # 3. Baue Scenario
    print("\n3. Baue Scenario...")
    scenario = ScenarioBuilder.build(user_cfg, profiles)
    print(f"   ✓ Name: {scenario.name}")
    print(f"   ✓ HP max: {scenario.config.hp_kw_th_max} kW")
    print(f"   ✓ Preis: {scenario.config.price_buy_chf} CHF/kWh")

    # 4. Führe Simulation aus
    print("\n4. Starte Simulation...")
    simulator = Simulator(scenario)
    simulator.run_all_strategies(profiles)
    
    # 5. Überprüfe Ergebnisse
    print("\n5. Überprüfe KPI-Ergebnisse...")
    kpis = simulator.get_kpis_summary()
    print(f"   ✓ {len(kpis)} Strategien simuliert\n")
    
    for idx, kpi in enumerate(kpis, 1):
        print(f"   Strategie {idx}:")
        for key, val in list(kpi.items())[:5]:
            if key != 'label':
                print(f"      {key}: {val}")

    print("\n" + "=" * 70)
    print("✓ WORKFLOW-TEST ERFOLGREICH")
    print("=" * 70)


if __name__ == "__main__":
    test_full_workflow()
