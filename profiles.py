"""
CSV-Import und Profilaufbereitung für die Simulation.

Merged drei separate CSV-Dateien positionsbasiert (Zeile 0 = Stunde 0):
  File 1: electricity_demand_profile.csv  → elektrische Last
  File 2: heat_demand_profile.csv         → Wärmelast + Außentemperatur (TAir)
  File 3: pv_yield_profile.csv            → PV-Ertrag

EV-Erweiterung:
  Studenten können _build_ev_profile() anpassen oder ersetzen,
  um eigene EV-Ladeprofile einzuspielen.
"""

import pandas as pd
from pathlib import Path
from config import SystemConfig


# ---------------------------------------------------------------------------
# EV-Profil: hier anpassen oder ersetzen
# ---------------------------------------------------------------------------


def _build_ev_profile(n: int) -> pd.Series:
    """
    Gibt ein EV-Nachfrageprofil zurück (Länge n, stündlich, in kWh).

    Aktuell: keine EVs → alles 0.
    Zum Erweitern: eigenes Profil laden oder synthetisch generieren.

    Beispiel für ein gleichmässiges Abend-Ladeprofil:
        result = pd.Series(0.0, index=range(n))
        for h in range(n):
            if h % 24 in range(20, 24):   # 20-23 Uhr
                result[h] = 2.5           # kWh pro Stunde
        return result
    """
    return pd.Series(0.0, index=range(n))


# ---------------------------------------------------------------------------
# Hauptfunktion
# ---------------------------------------------------------------------------


def load_profiles(config: SystemConfig) -> pd.DataFrame:
    """
    Lädt und merged drei CSV-Dateien zu einem DataFrame (8760 Zeilen, stündlich).

    Annahme: Alle drei Dateien haben exakt 8760 Zeilen in der richtigen
    zeitlichen Reihenfolge. Timestamps werden ignoriert, Merge ist
    positionsbasiert (Zeilenindex = Stunde des Jahres).

    Returns DataFrame mit Spalten:
        load_el_kw      Elektrische Last [kWh/h = kW]
        load_heat_kw    Wärmelast gesamt (Heizung + WW) [kWh/h = kW]
        pv_kw           PV-Ertrag (bereits skaliert) [kW]
        outdoor_temp_c  Außentemperatur aus heat_demand (TAir) [°C]
        ev_driven_kwh   EV-Ladelast [kWh/h = kW]
        price_buy       Strombezugspreis [CHF/kWh]
        price_sell      Einspeisevergütung [CHF/kWh]
        co2_intensity   CO₂-Intensität Netzstrom [kg/kWh]
        dt_h            Zeitschritt [h], immer 1.0
    """
    root = Path(__file__).parent / "data"

    # --- File 1: Elektrische Last ---
    el_df = pd.read_csv(root / "electricity_demand_profile.csv")
    load_el = el_df["total_electrcitiy_consumption_kWh"].values

    # --- File 2: Wärmelast + Außentemperatur ---
    heat_df = pd.read_csv(root / "heat_demand_profile.csv")
    load_heat = (
        heat_df["Demand space heating kWh"] + heat_df["Demand domestic hot water kWh"]
    ).values
    outdoor_temp_c = heat_df["TAir"].values  # Außentemperatur aus Wärmeprofil

    # --- File 3: PV-Ertrag ---
    pv_df = pd.read_csv(root / "pv_yield_profile.csv")
    pv_kw = pv_df["pv_kw"].values

    n = len(load_el)
    timestamps = pd.date_range(start="2023-01-01", periods=n, freq="h")

    # --- EV-Profil (erweiterbar, siehe _build_ev_profile oben) ---
    ev_demand = _build_ev_profile(n).values

    # --- Zusammenführen ---
    profiles = pd.DataFrame(
        {
            "timestamp": timestamps,
            "load_el_kw": load_el,
            "load_heat_kw": load_heat,
            "pv_kw": pv_kw,
            "outdoor_temp_c": outdoor_temp_c,
            "ev_driven_kwh": ev_demand,
            "price_buy": config.price_buy_chf,
            "price_sell": config.price_sell_chf,
            "co2_intensity": config.co2_grid_kg_kwh,
            "dt_h": 1.0,
        }
    )

    print(f"✓ {n} Stunden geladen")
    print(f"  Strom:     {profiles['load_el_kw'].sum():>10.0f} kWh/a")
    print(f"  Wärme:     {profiles['load_heat_kw'].sum():>10.0f} kWh/a")
    print(f"  PV:        {profiles['pv_kw'].sum():>10.0f} kWh/a")
    print(f"  Temp min:  {profiles['outdoor_temp_c'].min():>10.1f} °C")
    print(f"  Temp max:  {profiles['outdoor_temp_c'].max():>10.1f} °C")

    return profiles


if __name__ == "__main__":
    config = SystemConfig()
    profiles = load_profiles(config)
    print(profiles.head(5))
