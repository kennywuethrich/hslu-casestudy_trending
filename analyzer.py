"""KPI-Berechnung für die Simulation."""

import pandas as pd
import os
from typing import Dict, List
from config import SystemConfig


def calculate_kpis(result_df: pd.DataFrame, config: SystemConfig, label: str = "") -> Dict:
    """
    Berechnet alle wichtigen KPIs.
    
    Args:
        result_df: DataFrame mit Simulationsergebnissen
        config: SystemConfig mit System-Parametern
        label: Bezeichnung für diese Analyse
        
    Returns:
        dict: Dictionary mit allen KPIs
    """
    timestep_hours = result_df['dt_h'] if 'dt_h' in result_df.columns else pd.Series(1.0, index=result_df.index)
    ev_power_column = 'ev_charge_kw' if 'ev_charge_kw' in result_df.columns else 'ev_demand_kw'

    total_import = (result_df['grid_import_kw'] * timestep_hours).sum()
    total_export = (result_df['grid_export_kw'] * timestep_hours).sum()
    
    total_el_load = ((result_df['load_el_kw'] + result_df[ev_power_column]) * timestep_hours).sum()
    total_heat_load_el = ((result_df['load_heat_kw'] / config.hp_cop) * timestep_hours).sum()
    total_load_el_equiv = total_el_load + total_heat_load_el
    
    autarky = max(0.0, 1.0 - (total_import / total_load_el_equiv))
    
    costs_import = (result_df['grid_import_kw'] * result_df['price_buy'] * timestep_hours).sum()
    costs_export = (result_df['grid_export_kw'] * result_df['price_sell'] * timestep_hours).sum()
    net_costs = costs_import - costs_export
    
    co2_kg = (result_df['grid_import_kw'] * result_df['co2_intensity'] * timestep_hours).sum()
    co2_t = co2_kg / 1000.0
    
    ref_import = total_load_el_equiv
    ref_costs = (ref_import * result_df['price_buy'].mean())
    ref_co2_t = (ref_import * result_df['co2_intensity'].mean()) / 1000.0
    
    delta_cost = net_costs - ref_costs
    delta_co2 = ref_co2_t - co2_t
    
    mac = delta_cost / delta_co2 if delta_co2 > 0 else float('inf')
    
    return {
        'label': label,
        'Netzbezug [kWh]': round(total_import, 0),
        'Netzeinspeisung [kWh]': round(total_export, 0),
        'Autarkiegrad [%]': round(autarky * 100, 1),
        'Energiekosten [CHF/a]': round(net_costs, 0),
        'CO2-Emissionen [tCO2/a]': round(co2_t, 2),
        'MAC [CHF/tCO2]': round(mac, 1),
        'Referenz CO2 [tCO2/a]': round(ref_co2_t, 2),
        'CO2-Einsparung [tCO2/a]': round(delta_co2, 2),
        'PV-Erzeugung [kWh]': round((result_df['pv_kw'] * timestep_hours).sum(), 0),
        'H2-Erzeugung [kWh]': round((result_df['ely_power_kw'] * config.ely_eff_el * timestep_hours).sum(), 0),
    }


def print_kpi_table(kpi_list: List[Dict]):
    """Gibt KPI-Tabelle aus."""
    kpi_df = pd.DataFrame(kpi_list).set_index('label')
    print("\n" + "="*100)
    print("KPI-ÜBERSICHTSTABELLE")
    print("="*100)
    print(kpi_df.to_string())
    print("="*100 + "\n")


def save_kpis_to_csv(kpi_list: List[Dict], filepath: str = "kpi_ergebnisse.csv"):
    """Speichert KPIs als CSV."""
    output_dir = "results"
    os.makedirs(output_dir, exist_ok=True)
    resolved_path = os.path.join(output_dir, filepath) if not os.path.isabs(filepath) else filepath
    kpi_df = pd.DataFrame(kpi_list)
    kpi_df.to_csv(resolved_path, index=False)
    print(f"  ✓ KPI-Ergebnisse gespeichert: {resolved_path}")


def save_kpis_by_scenario(scenario_number: int, kpi_base: Dict, kpi_optimized: Dict):
    """Speichert KPIs für ein Szenario als CSV mit beiden Strategien.
    
    Args:
        scenario_number: Nummer des Szenarios (1 oder 2)
        kpi_base: KPI-Dict für BaseStrategy
        kpi_optimized: KPI-Dict für OptimizedStrategy
    """
    output_dir = "results"
    os.makedirs(output_dir, exist_ok=True)
    
    # Dateiname basierend auf Szenario-Nummer
    filepath = os.path.join(output_dir, f"kpis_szenario_{scenario_number}.csv")
    
    # DataFrame mit beiden Strategien
    data = {
        'KPI': [k for k in kpi_base.keys() if k != 'label'],
        'BaseStrategy': [kpi_base.get(k, '-') for k in kpi_base.keys() if k != 'label'],
        'OptimizedStrategy': [kpi_optimized.get(k, '-') for k in kpi_optimized.keys() if k != 'label']
    }
    kpi_df = pd.DataFrame(data)
    kpi_df.to_csv(filepath, index=False)
    print(f"  ✓ Szenario-KPIs gespeichert: {filepath}")


if __name__ == "__main__":
    from profiles import ProfileGenerator
    
    config = SystemConfig()
    profiles = ProfileGenerator.load_simulation_profiles(config)
    
    kpis = calculate_kpis(profiles, config, label="Test")
    print_kpi_table([kpis])
    save_kpis_to_csv([kpis])
