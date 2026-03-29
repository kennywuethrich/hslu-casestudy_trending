"""
Wohnüberbauung Zürich - Zeitreihen-Generator
Generiert realistische PV-Ertragsdaten mit pvlib (echtes Sonnenstandsmodell)
und synthetische Stromverbrauchsdaten für 83 Wohnungen.
"""

import pandas as pd
import numpy as np
import pvlib
from pathlib import Path

# ============================================================================
# CONFIG - Hier einstellen!
# ============================================================================

RESOLUTION = '1h'  # '1h' für stündlich oder '15min' für vierteljährlich
YEAR = 2026
NUM_APARTMENTS = 83
PV_AREA_M2 = 87  # Gesamtfläche in m²

# ============================================================================


def generate_pv_data(times, pv_area_m2=87):
    """
    Generiert PV-Ertragsdaten mit pvlib Sonnenstandsmodell.
    
    Die PV-Anlage hat 87 m² Fläche:
    - 43.5 m² mit +10° Neigung, Südseite (Azimuth 180°)
    - 43.5 m² mit +10° Neigung, Nordseite (Azimuth 0°)
    
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
    
    # POA (Plane of Array) Irradiance für beide Ausrichtungen
    # Surface 1: +10° Neigung, Südseite
    poa_irradiance_1 = pvlib.irradiance.get_total_irradiance(
        surface_tilt=10,
        surface_azimuth=180,
        solar_zenith=solar_position['zenith'],
        solar_azimuth=solar_position['azimuth'],
        dni=clearsky['dni'],
        ghi=clearsky['ghi'],
        dhi=clearsky['dhi'],
        model='isotropic'
    )
    
    # Surface 2: +10° Neigung, Nordseite (andere Himmelsrichtung)
    poa_irradiance_2 = pvlib.irradiance.get_total_irradiance(
        surface_tilt=10,
        surface_azimuth=0,
        solar_zenith=solar_position['zenith'],
        solar_azimuth=solar_position['azimuth'],
        dni=clearsky['dni'],
        ghi=clearsky['ghi'],
        dhi=clearsky['dhi'],
        model='isotropic'
    )
    
    # Durchschnitt beider Hälften
    poa_combined = (poa_irradiance_1['poa_global'] + poa_irradiance_2['poa_global']) / 2
    
    # Wolkeneffekt: Reduzierung durch zufällige Bewölkung
    # Realistische Bewölkung: ~30% der Zeit teilweise bewölkt
    np.random.seed(42)  # Reproduzierbar
    cloud_factor = np.random.normal(loc=0.85, scale=0.15, size=len(times))
    cloud_factor = np.clip(cloud_factor, 0.3, 1.0)  # 30-100%
    
    poa_with_clouds = poa_combined * cloud_factor
    
    return pd.Series(poa_with_clouds, index=times, name='pv_irradiance_wh_m2')


def generate_load_profile(times, num_apartments=83):
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
    if RESOLUTION == '1h':
        hourly_avg = annual_consumption_per_apartment / 8760  # kWh/Wohnung/Stunde
    else:  # 15min
        hourly_avg = annual_consumption_per_apartment / 8760 / 4  # kWh/Wohnung/15min
    
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


def main():
    # Zeitindex generieren
    freq = 'h' if RESOLUTION == '1h' else '15min'
    times = pd.date_range(
        f'{YEAR}-01-01',
        f'{YEAR}-12-31 23:00',
        freq=freq,
        tz='Europe/Zurich'
    )
    
    print(f"[INFO] Generiere Zeitreihen mit {RESOLUTION} Auflösung...")
    print(f"[INFO] Zeitraum: {times[0]} bis {times[-1]}")
    print(f"[INFO] Anzahl Einträge: {len(times)}")
    print(f"[INFO] Wohnungen: {NUM_APARTMENTS}, PV-Fläche: {PV_AREA_M2} m²")
    
    # PV-Daten
    print("[INFO] Berechne PV-Ertrag mit pvlib Sonnenstandsmodell...")
    pv_data = generate_pv_data(times, pv_area_m2=PV_AREA_M2)
    
    # Stromverbrauch
    print("[INFO] Generiere Stromverbrauchsprofil...")
    load_data = generate_load_profile(times, num_apartments=NUM_APARTMENTS)
    
    # DataFrame zusammenstellen
    df = pd.DataFrame({
        'datetime': times,
        'pv_irradiance_wh_m2': pv_data.values,
        'electricity_consumption_kwh': load_data.values
    })
    
    # CSV speichern
    output_file = Path(__file__).resolve().parent / f'wohnoverbauung_zurich_{RESOLUTION}.csv'
    df.to_csv(output_file, index=False)
    
    print(f"\n[SUCCESS] CSV erstellt: {output_file}")
    print(f"\nStatistiken:")
    print(f"\nPV-Ertrag (Wh/m²):")
    print(f"  Min: {pv_data.min():.2f}")
    print(f"  Max: {pv_data.max():.2f}")
    print(f"  Mean: {pv_data.mean():.2f}")
    print(f"  Jahresertrag: {pv_data.sum() / 1000:.1f} kWh/m² (normalerweise ~1000-1200 für Zürich)")
    
    print(f"\nStromverbrauch (kWh pro Zeitschritt):")
    print(f"  Min: {load_data.min():.3f}")
    print(f"  Max: {load_data.max():.3f}")
    print(f"  Mean: {load_data.mean():.3f}")
    print(f"  Jahresverbrauch: {load_data.sum():.0f} kWh (für {NUM_APARTMENTS} Wohnungen)")
    
    print(f"\nFirst 5 rows:")
    print(df.head().to_string(index=False))
    
    return df


if __name__ == '__main__':
    df = main()
