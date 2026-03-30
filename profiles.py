"""
Lastprofile-Generator für H2-Microgrid Simulation.
Lädt simulationsfertige Profile aus CSV-Dateien.
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
    def load_simulation_profiles(config: SystemConfig) -> pd.DataFrame:
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

        timestamps = df.index
        out = pd.DataFrame({
            'hour': range(len(df)),
            'hour_of_day': timestamps.hour,
            'day_of_year': timestamps.dayofyear - 1,
            'pv_kw': df['pv_kw'].to_numpy(),
            'load_el_kw': df['load_el_kw'].to_numpy(),
            'load_heat_kw': df['load_heat_kw'].to_numpy(),
            'ev_demand_kw': df['ev_demand_kw'].to_numpy(),
            'price_buy': config.price_buy_chf,
            'price_sell': config.price_sell_chf,
            'co2_intensity': config.co2_grid_kg_kwh,
            'dt_h': dt_h,
        })
        return out

    def __repr__(self):
        return "ProfileGenerator(CSV-only)"
