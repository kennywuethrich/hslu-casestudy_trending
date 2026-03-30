"""
Wohnüberbauung Anna-Heer-Strasse Zürich - Zeitreihen-Generator
Generiert simulationsfertige 1h- und 15min-CSV-Dateien.

Enthält alle zeitabhängigen physikalischen Profile:
- PV-Leistung [kW]
- Elektrische Last [kW]
- Wärmelast [kW]
- EV-Ladebedarf [kW]

Preis- und CO2-Werte bleiben bewusst in config.py (szenarioabhängig).
"""

import pandas as pd
import numpy as np
import pvlib
from pathlib import Path

# ============================================================================
# CONFIG - Hier einstellen!
# ============================================================================

YEAR = 2026
NUM_APARTMENTS = 83
PV_KWP = 87.0
PV_AREA_M2 = 87
# Drehung der Wohnblöcke relativ zur Nord-Süd-Achse (gegen den Uhrzeigersinn)
BLOCK_ROTATIONS_DEG = [15, 30, 45]
OUTPUT_RESOLUTIONS = ('1h', '15min')
EV_MODE = 'daytime'  # 'evening', 'daytime', 'workplace'

# ============================================================================


def generate_pv_data(times, pv_area_m2=87):
    """
    Generiert PV-Ertragsdaten mit pvlib Sonnenstandsmodell.
    
    PV-Aufteilung:
    - 3 Wohnblöcke mit je 1/3 der Gesamtfläche
    - Pro Block: 50% der Fläche +10° und 50% der Fläche -10°
    - Die Flächen sind Ost/West geneigt
    - Blöcke sind relativ zur Nord-Süd-Achse um 15°, 30° und 45° gedreht
    
    Args:
        times: pandas DatetimeIndex mit Zeitstempel
        pv_area_m2: Gesamtfläche der PV-Anlage in m²
    
    Returns:
        pandas Series mit PV-Ertrag in Wh/m²
    """
    # Zürich Koordinaten
    location = pvlib.location.Location(
        latitude=47.37,
        longitude=8.54,
        tz='Europe/Zurich',
        name='Zurich'
    )
    
    # Sonnenstand berechnen
    solar_position = location.get_solarposition(times)
    
    # Clearsky-Strahlung (ideales Wetter)
    clearsky = location.get_clearsky(times, model='ineichen')
    
    # Modellierung der 3 Blöcke mit je 2 gegensätzlichen Dachflächen (Ost/West).
    # Eine "-10°"-Neigung wird physikalisch als +10° mit gegenüberliegendem Azimut modelliert.
    block_area_m2 = pv_area_m2 / 3
    surface_area_m2 = block_area_m2 / 2

    poa_weighted_sum = pd.Series(0.0, index=times)
    total_area_m2 = 0.0

    for rotation_deg in BLOCK_ROTATIONS_DEG:
        # Ohne Rotation: Ost = 90°, West = 270°; mit Rotation gegen Uhrzeigersinn verschoben.
        east_azimuth = (90 - rotation_deg) % 360
        west_azimuth = (270 - rotation_deg) % 360

        for surface_azimuth in [east_azimuth, west_azimuth]:
            poa_irradiance = pvlib.irradiance.get_total_irradiance(
                surface_tilt=10,
                surface_azimuth=surface_azimuth,
                solar_zenith=solar_position['zenith'],
                solar_azimuth=solar_position['azimuth'],
                dni=clearsky['dni'],
                ghi=clearsky['ghi'],
                dhi=clearsky['dhi'],
                model='isotropic'
            )
            poa_weighted_sum += poa_irradiance['poa_global'] * surface_area_m2
            total_area_m2 += surface_area_m2

    # Flächengewichteter Mittelwert über alle Teilflächen
    poa_combined = poa_weighted_sum / total_area_m2
    
    # Wolkeneffekt: Reduzierung durch zufällige Bewölkung
    # Realistische Bewölkung: ~30% der Zeit teilweise bewölkt
    np.random.seed(42)  # Reproduzierbar
    cloud_factor = np.random.normal(loc=0.85, scale=0.15, size=len(times))
    cloud_factor = np.clip(cloud_factor, 0.3, 1.0)  # 30-100%
    
    poa_with_clouds = poa_combined * cloud_factor
    
    return pd.Series(poa_with_clouds, index=times, name='pv_irradiance_wh_m2')


def generate_load_profile(times, resolution: str, num_apartments=83):
    """
    Generiert realistische Stromverbrauchsdaten basierend auf SLP-H0 Profil.
    (Standardlastprofil Haushalt, Deutschland/Schweiz)
    
    Args:
        times: pandas DatetimeIndex
        num_apartments: Anzahl der Wohnungen
    
    Returns:
        pandas Series mit Stromverbrauch in kWh pro Zeitschritt
    """
    np.random.seed(42)
    
    # Durchschnittlicher Jahresverbrauch pro Wohnung: ~3500 kWh/Jahr
    # (typisch für Schweiz: 2000-3500 kWh für Einfamilienhaus/Wohnung)
    annual_consumption_per_apartment = 3500  # kWh/Jahr
    
    # Durchschnittlicher Verbrauch pro Zeitschritt
    if resolution == '1h':
        hourly_avg = annual_consumption_per_apartment / 8760  # kWh/Wohnung/Stunde
    else:  # 15min
        hourly_avg = annual_consumption_per_apartment / 35040  # kWh/Wohnung/15min
    
    # Basis-Tagesgang (SLP-H0 ähnlich)
    # Peaks: Morgens (6-8h), Abends (18-21h)
    hours = times.hour
    days_of_year = times.dayofyear
    
    # Tagesgang-Faktor (vereinfacht)
    hourly_profile = np.ones(len(times))
    
    # Nachts (0-6 Uhr): reduzierter Verbrauch (50%)
    night_mask = (hours >= 0) & (hours < 6)
    hourly_profile[night_mask] *= 0.5
    
    # Morgen-Peak (6-9 Uhr): erhöht (120%)
    morning_mask = (hours >= 6) & (hours < 9)
    hourly_profile[morning_mask] *= 1.2
    
    # Tagsüber (9-17 Uhr): normal (100%)
    day_mask = (hours >= 9) & (hours < 17)
    hourly_profile[day_mask] *= 1.0
    
    # Abend-Peak (17-21 Uhr): stark erhöht (150%)
    evening_mask = (hours >= 17) & (hours < 21)
    hourly_profile[evening_mask] *= 1.5
    
    # Spät-Abend (21-24 Uhr): reduziert (70%)
    late_evening_mask = (hours >= 21) & (hours < 24)
    hourly_profile[late_evening_mask] *= 0.7
    
    # Wochentag-Faktor
    weekday_factor = np.ones(len(times))
    is_weekend = times.dayofweek >= 5  # Samstag/Sonntag
    weekday_factor[is_weekend] *= 0.85  # Wochenende: -15%
    
    # Saisonalität (Winter mehr Verbrauch wegen Heizung + Licht)
    # Peak im Januar/Dezember, Minimum im Juli/August
    seasonal_factor = 0.8 + 0.4 * np.sin(2 * np.pi * (days_of_year - 80) / 365.25)
    
    # Zufälliges Rauschen (Tag-zu-Tag Variabilität)
    random_noise = np.random.normal(loc=1.0, scale=0.1, size=len(times))
    random_noise = np.clip(random_noise, 0.7, 1.3)
    
    # Kombinieren
    load_profile = (
        hourly_avg * num_apartments *
        hourly_profile *
        weekday_factor *
        seasonal_factor *
        random_noise
    )
    
    return pd.Series(load_profile, index=times, name='electricity_consumption_kwh')


def generate_heat_profile(times, resolution: str):
    """Generiert synthetisches Wärmelastprofil der Überbauung [kWh pro Zeitschritt]."""
    hours = times.hour
    day_of_year = times.dayofyear

    # Jahresgang + Warmwasseranteil
    seasonal_heat_kw = 40 + 40 * np.cos(2 * np.pi * (day_of_year - 15) / 365.25)
    warmwater_kw = 8 * (
        np.exp(-0.5 * ((hours - 7) / 1.0) ** 2)
        + 0.5 * np.exp(-0.5 * ((hours - 20) / 1.0) ** 2)
    )

    heat_kw = np.clip(seasonal_heat_kw + warmwater_kw, 5.0, 95.0)
    dt_h = 1.0 if resolution == '1h' else 0.25
    heat_kwh_step = heat_kw * dt_h
    return pd.Series(heat_kwh_step, index=times, name='heat_demand_kwh')


def generate_ev_profile(times, resolution: str, ev_mode: str = 'daytime'):
    """Generiert EV-Ladeprofil [kWh pro Zeitschritt] für gewählten Modus."""
    hours = times.hour
    day_of_year = times.dayofyear
    day_of_week = day_of_year % 7

    ev_kw = np.zeros(len(times))
    if ev_mode == 'evening':
        ev_kw = np.where((hours >= 18) & (hours < 22), 7.4, 0.0)
    elif ev_mode == 'daytime':
        ev_kw = np.where((hours >= 10) & (hours < 14), 7.4, 0.0)
    elif ev_mode == 'workplace':
        is_workday = day_of_week < 5
        ev_kw = np.where(is_workday & (hours >= 8) & (hours < 17), 3.3, 0.0)

    dt_h = 1.0 if resolution == '1h' else 0.25
    ev_kwh_step = ev_kw * dt_h
    return pd.Series(ev_kwh_step, index=times, name='ev_demand_kwh')


def build_dataset(resolution: str) -> pd.DataFrame:
    """Erzeugt vollständigen Datensatz für eine Auflösung ('1h' oder '15min')."""
    if resolution not in ('1h', '15min'):
        raise ValueError("resolution muss '1h' oder '15min' sein")

    freq = 'h' if resolution == '1h' else '15min'
    end_timestamp = f'{YEAR}-12-31 23:00' if resolution == '1h' else f'{YEAR}-12-31 23:45'
    times = pd.date_range(
        f'{YEAR}-01-01',
        end_timestamp,
        freq=freq,
        tz='Europe/Zurich'
    )

    print(f"\n[INFO] Generiere Zeitreihen mit {resolution} Auflösung...")
    print(f"[INFO] Zeitraum: {times[0]} bis {times[-1]}")
    print(f"[INFO] Anzahl Einträge: {len(times)}")
    print(f"[INFO] Wohnungen: {NUM_APARTMENTS}, PV: {PV_KWP} kWp")

    pv_irradiance = generate_pv_data(times, pv_area_m2=PV_AREA_M2)
    load_kwh_step = generate_load_profile(times, resolution=resolution, num_apartments=NUM_APARTMENTS)
    heat_kwh_step = generate_heat_profile(times, resolution=resolution)
    ev_kwh_step = generate_ev_profile(times, resolution=resolution, ev_mode=EV_MODE)

    dt_h = 1.0 if resolution == '1h' else 0.25

    # Leistungsspalten für den bestehenden Simulationskern
    load_el_kw = load_kwh_step / dt_h
    load_heat_kw = heat_kwh_step / dt_h
    ev_demand_kw = ev_kwh_step / dt_h
    pv_kw = np.clip(PV_KWP * (pv_irradiance / 1000.0), 0.0, PV_KWP)

    df = pd.DataFrame({
        'datetime': times,
        'pv_kw': pv_kw.values,
        'load_el_kw': load_el_kw.values,
        'load_heat_kw': load_heat_kw.values,
        'ev_demand_kw': ev_demand_kw.values,
        # Zusätzliche Transparenz-Spalten
        'pv_irradiance_wh_m2': pv_irradiance.values,
        'electricity_consumption_kwh_step': load_kwh_step.values,
        'heat_demand_kwh_step': heat_kwh_step.values,
        'ev_demand_kwh_step': ev_kwh_step.values,
    })

    return df


def main():
    output_dir = Path(__file__).resolve().parent
    created = {}

    for resolution in OUTPUT_RESOLUTIONS:
        df = build_dataset(resolution)
        output_file = output_dir / f'data_annaheer_{resolution}.csv'
        df.to_csv(output_file, index=False)
        created[resolution] = (output_file, df)

        print(f"[SUCCESS] CSV erstellt: {output_file}")
        print("[INFO] Kennzahlen:")
        print(f"  PV Jahresenergie [MWh]: {(df['pv_kw'].sum() * (1.0 if resolution == '1h' else 0.25)) / 1000:.1f}")
        print(f"  Stromverbrauch [MWh]: {(df['load_el_kw'].sum() * (1.0 if resolution == '1h' else 0.25)) / 1000:.1f}")
        print(f"  Wärmelast [MWh]: {(df['load_heat_kw'].sum() * (1.0 if resolution == '1h' else 0.25)) / 1000:.1f}")
        print(f"  EV-Ladung [MWh]: {(df['ev_demand_kw'].sum() * (1.0 if resolution == '1h' else 0.25)) / 1000:.1f}")

    print("\nFirst 5 rows (1h):")
    print(created['1h'][1].head().to_string(index=False))

    return created['1h'][1]


if __name__ == '__main__':
    df = main()
