"""
CSV-Import und Profilaufbereitung für die Simulation.
ANNAHME: DATEN SIND BEREITS SORTIERT NACH TIMESTAMP...
"""

import pandas as pd
from pathlib import Path
from config import SystemConfig


def _remap_ev_to_daytime(ev_series: pd.Series) -> pd.Series:
    """Verteilt EV-Energie auf 8-17 Uhr um."""
    result = pd.Series(0.0, index=ev_series.index)
    
    for day in ev_series.index.floor('D').unique():
        day_mask = (ev_series.index.floor('D') == day)
        day_energy = float(ev_series[day_mask].sum())
        
        if day_energy <= 0:
            continue
            
        daytime_mask = day_mask & (ev_series.index.hour >= 8) & (ev_series.index.hour < 17)
        if daytime_mask.sum() > 0:
            result.loc[daytime_mask] = day_energy / daytime_mask.sum()
    
    return result


def load_profiles(config: SystemConfig, ev_mode: str = 'as_is') -> pd.DataFrame:
    """Lädt Energie-Profile aus 3 CSV-Dateien (8760 Zeilen, stündlich)."""
    
    root = Path(__file__).parent
    el = pd.read_csv(root / 'data' / 'electricity_demand_profile.csv', skip_blank_lines=True)
    heat = pd.read_csv(root / 'data' / 'heat_demand_profile.csv', skip_blank_lines=True)
    pv = pd.read_csv(root / 'data' / 'pv_yield_profile.csv', skip_blank_lines=True)
    
    n = len(el)
    
    # Create DatetimeIndex only for EV remapping (if needed)
    dt_idx = pd.date_range('2021-01-01', periods=n, freq='h')
    ev = pd.Series(0.0, index=dt_idx)
    if ev_mode == 'daytime':
        ev = _remap_ev_to_daytime(ev)
    elif ev_mode != 'as_is':
        raise ValueError(f"Ungültiger ev_mode='{ev_mode}'.")
    
    return pd.DataFrame({
        'hour_of_day': [i % 24 for i in range(n)],
        'day_of_year': [i // 24 for i in range(n)],
        'load_el_kw': el['total_electrcitiy_consumption_kWh'].values,
        'load_heat_kw': (heat['Demand space heating kWh'] + heat['Demand domestic hot water kWh']).values,
        'pv_kw': pv['pv_kw'].values,
        'outdoor_temp_c': pv['outdoor_temp_c'].values,
        'ev_demand_kw': ev.values,
        'price_buy': config.price_buy_chf,
        'price_sell': config.price_sell_chf,
        'co2_intensity': config.co2_grid_kg_kwh,
        'dt_h': 1.0
    })
if __name__ == "__main__":
    config = SystemConfig()
    profiles = load_profiles(config)
    print(f"✓ {profiles.shape[0]} profiles loaded")
    print(profiles.head(2))