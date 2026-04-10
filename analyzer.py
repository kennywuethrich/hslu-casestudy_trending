"""KPI-Berechnung und Visualisierung für die Simulation."""

import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
from typing import Dict, List
from config import SystemConfig


class ResultAnalyzer:
    """
    Analysiert Simulationsergebnisse und berechnet KPIs.
    Unterstützt auch Visualisierungen.
    """
    
    def __init__(self, config: SystemConfig):
        self.config = config
        self.output_dir = "results"
        os.makedirs(self.output_dir, exist_ok=True)

    def _resolve_output_path(self, filepath: str) -> str:
        """Löst relative Dateinamen standardmäßig in den results-Ordner auf."""
        if not filepath:
            return filepath
        if os.path.isabs(filepath) or os.path.dirname(filepath):
            return filepath
        return os.path.join(self.output_dir, filepath)
    
    def calculate_kpis(self, result_df: pd.DataFrame, label: str = "") -> Dict:
        """
        Berechnet alle wichtigen KPIs.
        
        Args:
            result_df: DataFrame mit Simulationsergebnissen
            label: Bezeichnung für diese Analyse
            
        Returns:
            dict: Dictionary mit allen KPIs
        """
        timestep_hours = result_df['dt_h'] if 'dt_h' in result_df.columns else pd.Series(1.0, index=result_df.index)
        ev_power_column = 'ev_charge_kw' if 'ev_charge_kw' in result_df.columns else 'ev_demand_kw'

        total_import = (result_df['grid_import_kw'] * timestep_hours).sum()
        total_export = (result_df['grid_export_kw'] * timestep_hours).sum()
        
        total_el_load = ((result_df['load_el_kw'] + result_df[ev_power_column]) * timestep_hours).sum()
        total_heat_load_el = ((result_df['load_heat_kw'] / self.config.hp_cop) * timestep_hours).sum()
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
            'H2-Erzeugung [kWh]': round((result_df['ely_power_kw'] * self.config.ely_eff_el * timestep_hours).sum(), 0),
        }

    def _build_time_index(self, result_df: pd.DataFrame) -> pd.DatetimeIndex:
        """Erstellt konsistenten Zeitindex für Visualisierungen."""
        dt_h = float(result_df['dt_h'].iloc[0]) if 'dt_h' in result_df.columns else 1.0
        freq = f"{int(round(dt_h * 60))}min"
        return pd.date_range(start='2026-01-01', periods=len(result_df), freq=freq)

    def plot_h2_soc_year(self, result_df: pd.DataFrame, title: str = "H2-SOC Jahresverlauf",
                         save_path: str = None):
        """Zeigt den H2-SOC über das Jahr als Tagesband und Tagesmittel."""
        if 'h2_soc_kwh' not in result_df.columns or len(result_df) == 0:
            return

        time_index = self._build_time_index(result_df)
        soc_pct = result_df['h2_soc_kwh'].to_numpy() / self.config.h2_capacity_kwh * 100.0

        plot_df = pd.DataFrame({'datetime': time_index, 'soc_pct': soc_pct})
        daily_stats = plot_df.set_index('datetime')['soc_pct'].resample('D').agg(['min', 'mean', 'max'])

        fig, ax = plt.subplots(figsize=(14, 5))
        ax.fill_between(
            daily_stats.index,
            daily_stats['min'].values,
            daily_stats['max'].values,
            color='forestgreen',
            alpha=0.15,
            label='Tagesbereich (Min/Max)'
        )
        ax.plot(daily_stats.index, daily_stats['mean'].values, color='darkgreen', lw=1.8, label='Tagesmittel H2-SOC')
        ax.axhline(5, color='red', ls='--', lw=1, label='Min SOC')

        ax.axvspan(pd.Timestamp('2026-01-01'), pd.Timestamp('2026-02-28'), color='#f2dede', alpha=0.25)
        ax.axvspan(pd.Timestamp('2026-03-01'), pd.Timestamp('2026-05-31'), color='#dff0d8', alpha=0.25)
        ax.axvspan(pd.Timestamp('2026-06-01'), pd.Timestamp('2026-08-31'), color='#fcf8e3', alpha=0.25)
        ax.axvspan(pd.Timestamp('2026-09-01'), pd.Timestamp('2026-11-30'), color='#d9edf7', alpha=0.25)
        ax.axvspan(pd.Timestamp('2026-12-01'), pd.Timestamp('2026-12-31'), color='#f2dede', alpha=0.25)


        ax.set_title(title, fontweight='bold')
        ax.set_ylabel('H2-SOC [%]')
        ax.set_xlabel('Monat')
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper right', fontsize=8)

        soc_min = float(daily_stats['min'].min())
        soc_max = float(daily_stats['max'].max())
        span = max(2.0, soc_max - soc_min)
        margin = max(1.0, span * 0.2)
        lower = max(0.0, min(5.0, soc_min) - margin)
        upper = min(105.0, max(5.0, soc_max) + margin)
        if upper - lower < 6.0:
            mid = 0.5 * (upper + lower)
            lower = max(0.0, mid - 3.0)
            upper = min(105.0, mid + 3.0)
        ax.set_ylim(lower, upper)

        plt.tight_layout()

        if save_path:
            resolved_path = self._resolve_output_path(save_path)
            plt.savefig(resolved_path, dpi=150)
            print(f"  ✓ Gespeichert: {resolved_path}")

        plt.close(fig)

    def plot_year_energy_overview(self, result_df: pd.DataFrame,
                                  title: str = "Jahresübersicht Energiebilanz",
                                  save_path: str = None):
        """Zeigt die wichtigsten Jahresflüsse in einer kompakten Übersicht."""
        if len(result_df) == 0:
            return

        dt_h = result_df['dt_h'] if 'dt_h' in result_df.columns else pd.Series(1.0, index=result_df.index)
        time_index = self._build_time_index(result_df)

        ev_col = 'ev_charge_kw' if 'ev_charge_kw' in result_df.columns else 'ev_demand_kw'

        flows = pd.DataFrame({
            'datetime': time_index,
            'pv_kwh': result_df['pv_kw'].to_numpy() * dt_h.to_numpy(),
            'load_el_kwh': result_df['load_el_kw'].to_numpy() * dt_h.to_numpy(),
            'hp_el_kwh': result_df['hp_el_kw'].to_numpy() * dt_h.to_numpy(),
            'ev_charge_kwh': result_df[ev_col].to_numpy() * dt_h.to_numpy(),
            'grid_import_kwh': result_df['grid_import_kw'].to_numpy() * dt_h.to_numpy(),
            'grid_export_kwh': result_df['grid_export_kw'].to_numpy() * dt_h.to_numpy(),
            'ely_el_kwh': result_df['ely_power_kw'].to_numpy() * dt_h.to_numpy(),
        }).set_index('datetime')

        monthly = flows.resample('ME').sum()
        cumulative = flows.cumsum()

        fig, axes = plt.subplots(3, 1, figsize=(14, 12), sharex=False)
        fig.suptitle(title, fontsize=14, fontweight='bold')

        ax1 = axes[0]
        x = np.arange(len(monthly.index))
        w = 0.2
        ax1.bar(x - 1.5 * w, monthly['grid_import_kwh'], width=w, label='Netzbezug', color='#d95f02')
        ax1.bar(x - 0.5 * w, monthly['grid_export_kwh'], width=w, label='Netzeinspeisung', color='#1b9e77')
        ax1.bar(x + 0.5 * w, monthly['ely_el_kwh'], width=w, label='Strom -> H2 (ELY)', color='#7570b3')
        ax1.bar(x + 1.5 * w, monthly['ev_charge_kwh'], width=w, label='Strom -> EV', color='#66a61e')
        ax1.set_ylabel('Energie [kWh/Monat]')
        ax1.set_title('Monatliche Energieströme (Kernflüsse)')
        ax1.set_xticks(x)
        ax1.set_xticklabels([d.strftime('%b') for d in monthly.index])
        ax1.grid(True, axis='y', alpha=0.3)
        ax1.legend(loc='upper right', fontsize=8)

        ax2 = axes[1]
        total_demand = monthly['load_el_kwh'] + monthly['hp_el_kwh'] + monthly['ev_charge_kwh']
        ax2.plot(monthly.index, monthly['pv_kwh'], lw=2.2, color='#e6ab02', label='PV-Erzeugung')
        ax2.plot(monthly.index, total_demand, lw=2.2, color='#333333', label='El. Nachfrage gesamt')
        ax2.fill_between(monthly.index, monthly['pv_kwh'].values, total_demand.values,
                         where=(monthly['pv_kwh'].values >= total_demand.values),
                         color='#a6d854', alpha=0.25, interpolate=True, label='Monatlicher Überschuss')
        ax2.set_ylabel('Energie [kWh/Monat]')
        ax2.set_title('PV vs. elektrische Gesamtnachfrage')
        ax2.grid(True, alpha=0.3)
        ax2.legend(loc='upper right', fontsize=8)

        ax3 = axes[2]
        ax3.plot(cumulative.index, cumulative['grid_import_kwh'], color='#d95f02', lw=1.8, label='kumuliert Netzbezug')
        ax3.plot(cumulative.index, cumulative['grid_export_kwh'], color='#1b9e77', lw=1.8, label='kumuliert Einspeisung')
        ax3.plot(cumulative.index, cumulative['ely_el_kwh'], color='#7570b3', lw=1.8, label='kumuliert Strom -> H2')
        ax3.plot(cumulative.index, cumulative['ev_charge_kwh'], color='#66a61e', lw=1.8, label='kumuliert Strom -> EV')
        ax3.set_ylabel('Energie [kWh]')
        ax3.set_title('Kumulierte Jahresverläufe')
        ax3.grid(True, alpha=0.3)
        ax3.legend(loc='upper left', fontsize=8)

        summary = (
            f"Jahressummen\n"
            f"Netzbezug: {flows['grid_import_kwh'].sum():,.0f} kWh\n"
            f"Einspeisung: {flows['grid_export_kwh'].sum():,.0f} kWh\n"
            f"ELY-Strom: {flows['ely_el_kwh'].sum():,.0f} kWh\n"
            f"EV-Ladestrom: {flows['ev_charge_kwh'].sum():,.0f} kWh"
        )
        ax3.text(0.995, 0.03, summary, transform=ax3.transAxes,
                 ha='right', va='bottom', fontsize=9,
                 bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.85, edgecolor='#888'))

        plt.tight_layout()

        if save_path:
            resolved_path = self._resolve_output_path(save_path)
            plt.savefig(resolved_path, dpi=150)
            print(f"  ✓ Gespeichert: {resolved_path}")

        plt.close(fig)
    
    def print_kpi_table(self, kpi_list: List[Dict]):
        kpi_df = pd.DataFrame(kpi_list).set_index('label')
        print("\n" + "="*100)
        print("KPI-ÜBERSICHTSTABELLE")
        print("="*100)
        print(kpi_df.to_string())
        print("="*100 + "\n")
    
    def save_kpis_to_csv(self, kpi_list: List[Dict], 
                        filepath: str = "kpi_ergebnisse.csv"):
        resolved_path = self._resolve_output_path(filepath)
        kpi_df = pd.DataFrame(kpi_list)
        kpi_df.to_csv(resolved_path, index=False)
        print(f"  ✓ KPI-Ergebnisse gespeichert: {resolved_path}")
