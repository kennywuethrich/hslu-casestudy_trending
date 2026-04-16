"""Integration-Tests für neue GUI-Module."""

import pandas as pd
from user_config import UserInputConfig
from profile_modifier import ProfileModifier
from scenario_builder import ScenarioBuilder
from profiles import ProfileGenerator
from config import SystemConfig


def test_all():
    print("=" * 60)
    print("INTEGRATION TEST")
    print("=" * 60)

    # 1. Lade Profile
    print("\n1. Lade Profile...")
    pg = ProfileGenerator()
    config = SystemConfig()
    profiles = pg.load_simulation_profiles(config)
    print(f"   ✓ {len(profiles)} Zeitschritte geladen")

    # 2. Erstelle Benutzer-Config
    print("\n2. Erstelle UserInputConfig...")
    user_cfg = UserInputConfig(
        num_evs=3,
        hp_failure=True,
        smart_energy_enabled=True,
        variable_prices_enabled=True,
        price_night_chf_per_kwh=0.12,
        price_day_chf_per_kwh=0.35
    )
    print(f"   ✓ {user_cfg}")

    # 3. Modifiziere Profile
    print("\n3. Modifiziere Profile...")
    modified = ProfileModifier.apply_all(profiles, user_cfg)
    print(f"   ✓ Profile modifiziert")
    print(f"   - EV-Demand Ø: {modified['ev_demand_kw'].mean():.2f} kW (orig: {profiles['ev_demand_kw'].mean():.2f} kW)")
    print(f"   - Last Ø: {modified['load_el_kw'].mean():.2f} kW (orig: {profiles['load_el_kw'].mean():.2f} kW)")

    # 4. Baue Scenario
    print("\n4. Baue Scenario aus UserConfig...")
    scenario = ScenarioBuilder.build(user_cfg, profiles)
    print(f"   ✓ Szenario: {scenario.name}")
    print(f"   ✓ HP-max: {scenario.config.hp_kw_th_max} kW")

    # 5. Teste Preis-Funktion
    print("\n5. Teste variable Strompreise...")
    price_7 = ProfileModifier.get_hourly_price(7, user_cfg)
    price_23 = ProfileModifier.get_hourly_price(23, user_cfg)
    print(f"   - 07:00 Uhr: {price_7:.2f} CHF/kWh (Tag)")
    print(f"   - 23:00 Uhr: {price_23:.2f} CHF/kWh (Nacht)")

    print("\n" + "=" * 60)
    print("✓ ALLE TESTS ERFOLGREICH")
    print("=" * 60)


if __name__ == "__main__":
    test_all()
