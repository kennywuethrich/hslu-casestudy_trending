"""Generiert eine einzige 1h-Zeitreihe mit PV-Leistung und Aussentemperatur fuer Zuerich."""

from pathlib import Path

import numpy as np
import pandas as pd
import pvlib


YEAR = 2026
PV_KWP = 87.0
PV_AREA_M2 = 87
BLOCK_ROTATIONS_DEG = [15, 30, 45]


def generate_pv_data(times: pd.DatetimeIndex, pv_area_m2: float = PV_AREA_M2) -> pd.Series:
    """Generiert PV-Einstrahlung [Wh/m²] für die gegebene Zeitachse."""
    location = pvlib.location.Location(
        latitude=47.37,
        longitude=8.54,
        tz='Europe/Zurich',
        name='Zurich',
    )

    solar_position = location.get_solarposition(times)
    clearsky = location.get_clearsky(times, model='ineichen')

    block_area_m2 = pv_area_m2 / 3
    surface_area_m2 = block_area_m2 / 2

    poa_weighted_sum = pd.Series(0.0, index=times)
    total_area_m2 = 0.0

    for rotation_deg in BLOCK_ROTATIONS_DEG:
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
                model='isotropic',
            )
            poa_weighted_sum += poa_irradiance['poa_global'] * surface_area_m2
            total_area_m2 += surface_area_m2

    poa_combined = poa_weighted_sum / total_area_m2

    np.random.seed(42)
    cloud_factor = np.random.normal(loc=0.85, scale=0.15, size=len(times))
    cloud_factor = np.clip(cloud_factor, 0.3, 1.0)

    poa_with_clouds = poa_combined * cloud_factor
    return pd.Series(poa_with_clouds, index=times, name='pv_irradiance_wh_m2')


def generate_outdoor_temperature(times: pd.DatetimeIndex) -> pd.Series:
    """Erzeugt ein stundenaufgeloestes Aussentemperaturprofil fuer Zuerich [degC]."""
    np.random.seed(42)
    day_of_year = times.dayofyear
    hour = times.hour + times.minute / 60.0

    seasonal_c = 10.0 + 10.5 * np.sin(2 * np.pi * (day_of_year - 81) / 365.25)
    diurnal_c = 3.0 * np.sin(2 * np.pi * (hour - 14) / 24.0)
    noise_c = np.random.normal(loc=0.0, scale=1.2, size=len(times))

    temp_c = np.round(np.clip(seasonal_c + diurnal_c + noise_c, -12.0, 35.0), 1)
    return pd.Series(temp_c, index=times, name='outdoor_temp_c')


def build_dataset_1h() -> pd.DataFrame:
    """Erzeugt den 1h-Datensatz mit PV-Leistung und Aussentemperatur."""
    times = pd.date_range(
        f'{YEAR}-01-01',
        f'{YEAR}-12-31 23:00',
        freq='h',
        tz='Europe/Zurich',
    )

    print('\n[INFO] Generiere Zeitreihe mit 1h Auflösung...')
    print(f'[INFO] Zeitraum: {times[0]} bis {times[-1]}')
    print(f'[INFO] Anzahl Einträge: {len(times)}')
    print(f'[INFO] PV: {PV_KWP} kWp')

    pv_irradiance = generate_pv_data(times)
    pv_kw = np.clip(PV_KWP * (pv_irradiance / 1000.0), 0.0, PV_KWP)
    outdoor_temp_c = (generate_outdoor_temperature(times))

    return pd.DataFrame({
        'datetime': times,
        'pv_kw': pv_kw.values,
        'outdoor_temp_c': outdoor_temp_c.values,
    })


def main() -> pd.DataFrame:
    output_dir = Path(__file__).resolve().parent
    df = build_dataset_1h()

    output_file = output_dir / 'pv_yield_profile.csv'
    df.to_csv(output_file, index=False)

    print(f'[SUCCESS] CSV erstellt: {output_file}')
    print('[INFO] Kennzahlen:')
    print(f"  PV Jahresenergie [MWh]: {(df['pv_kw'].sum()) / 1000:.1f}")
    print('\nFirst 5 rows:')
    print(df.head().to_string(index=False))

    return df


if __name__ == '__main__':
    main()
