"""
CSV-Import und Profilaufbereitung für die Simulation.

Entwickler-Kurzinfo:
- Zweck: Liest Profil-CSV und normalisiert Spalten für den Modellkern.
- Inputs: SystemConfig (Datei, Auflösung) und ev_profile_mode.
- Outputs: DataFrame mit Lasten, Preisen, CO2 und dt_h.
- Typische Änderungen: Datenschema, Zeitindex, EV-Remapping.
"""

import pandas as pd
import os
from config import SystemConfig


class ProfileGenerator:
    """
    Lädt Energielastprofile für die Simulation aus CSV.
    """

    REQUIRED_BASE_COLUMNS = [
        'datetime',
        'pv_kw',
        'load_el_kw',
        'load_heat_kw',
        'ev_demand_kw',
    ]

    @staticmethod
    def _resolve_csv_path(config: SystemConfig) -> str:
        """Ermittelt anhand der zentralen Auflösungswahl die passende CSV-Datei."""
        if config.time_resolution == '1h':
            filename = config.data_csv_1h
        elif config.time_resolution == '15min':
            filename = config.data_csv_15min
        else:
            raise ValueError(
                f"Ungültige time_resolution='{config.time_resolution}'. Erlaubt: '1h', '15min'."
            )
        return os.path.join(config.data_dir, filename)

    @staticmethod
    def _remap_ev_profile_to_daytime(ev_kw: pd.Series, dt_h: float) -> pd.Series:
        """Verschiebt EV-Energie je Kalendertag in ein Workplace-Fenster (08:00-17:00)."""
        if ev_kw.empty:
            return ev_kw

        result = pd.Series(0.0, index=ev_kw.index)
        day_keys = ev_kw.index.floor('D')

        for day in day_keys.unique():
            day_mask = (day_keys == day)
            day_series = ev_kw[day_mask]
            day_energy_kwh = float((day_series * dt_h).sum())

            if day_energy_kwh <= 0:
                continue

            hours = day_series.index.hour
            daytime_mask = (hours >= 8) & (hours < 17)

            if daytime_mask.sum() == 0:
                result.loc[day_series.index] = day_series.values
                continue

            per_step_kwh = day_energy_kwh / int(daytime_mask.sum())
            per_step_kw = per_step_kwh / dt_h if dt_h > 0 else 0.0

            remapped = pd.Series(0.0, index=day_series.index)
            remapped.iloc[daytime_mask] = per_step_kw
            result.loc[day_series.index] = remapped.values

        return result

    @staticmethod
    def load_simulation_profiles(config: SystemConfig, ev_profile_mode: str = 'as_is') -> pd.DataFrame:
        """
        Lädt simulierte CSV-Profile und ergänzt konfigurationsabhängige Felder.
        """
        filepath = ProfileGenerator._resolve_csv_path(config)
        if not os.path.exists(filepath):
            raise FileNotFoundError(
                f"CSV-Datei nicht gefunden: {filepath}. Bitte data/generate_data.py ausführen."
            )

        df = pd.read_csv(filepath)
        missing_cols = [
            col for col in ProfileGenerator.REQUIRED_BASE_COLUMNS if col not in df.columns
        ]
        if missing_cols:
            raise ValueError(
                f"CSV '{filepath}' hat nicht alle Pflichtspalten: {', '.join(missing_cols)}"
            )

        df['datetime'] = pd.to_datetime(df['datetime'], errors='raise', utc=True)
        df['datetime'] = df['datetime'].dt.tz_convert('Europe/Zurich')
        df = df.sort_values('datetime').set_index('datetime')

        if len(df.index) > 1:
            dt_h = (df.index[1] - df.index[0]).total_seconds() / 3600.0
        else:
            dt_h = 1.0

        ev_kw = df['ev_demand_kw'].astype(float)
        if ev_profile_mode == 'daytime':
            ev_kw = ProfileGenerator._remap_ev_profile_to_daytime(ev_kw, dt_h)
        elif ev_profile_mode != 'as_is':
            raise ValueError(f"Ungültiger ev_profile_mode='{ev_profile_mode}'. Erlaubt: 'as_is', 'daytime'.")

        timestamps = df.index
        out = pd.DataFrame({
            'hour': range(len(df)),
            'hour_of_day': timestamps.hour,
            'day_of_year': timestamps.dayofyear - 1,
            'pv_kw': df['pv_kw'].to_numpy(),
            'load_el_kw': df['load_el_kw'].to_numpy(),
            'load_heat_kw': df['load_heat_kw'].to_numpy(),
            'ev_demand_kw': ev_kw.to_numpy(),
            'price_buy': config.price_buy_chf,
            'price_sell': config.price_sell_chf,
            'co2_intensity': config.co2_grid_kg_kwh,
            'dt_h': dt_h,
        })
        return out

    def __repr__(self):
        return "ProfileGenerator(CSV-only)"
