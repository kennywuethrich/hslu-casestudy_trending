"""
Analyzer-Modul: KPI-Berechnung, Auswertung und Visualisierung.
"""

import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
from typing import Dict, List, Optional
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
        dt_h = result_df['dt_h'] if 'dt_h' in result_df.columns else pd.Series(1.0, index=result_df.index)

        ev_el_col = 'ev_charge_kw' if 'ev_charge_kw' in result_df.columns else 'ev_demand_kw'

        total_import = (result_df['grid_import_kw'] * dt_h).sum()
        total_export = (result_df['grid_export_kw'] * dt_h).sum()
        
        # Gesamtlast
        total_el_load = ((result_df['load_el_kw'] + result_df[ev_el_col]) * dt_h).sum()
        total_heat_load_el = ((result_df['load_heat_kw'] / self.config.hp_cop) * dt_h).sum()
        total_load_el_equiv = total_el_load + total_heat_load_el
        
        # Autarkiegrad
        autarky = max(0.0, 1.0 - (total_import / total_load_el_equiv))
        
        # Energiekosten
        costs_import = (result_df['grid_import_kw'] * result_df['price_buy'] * dt_h).sum()
        costs_export = (result_df['grid_export_kw'] * result_df['price_sell'] * dt_h).sum()
        net_costs = costs_import - costs_export
        
        # CO2-Emissionen
        co2_kg = (result_df['grid_import_kw'] * result_df['co2_intensity'] * dt_h).sum()
        co2_t = co2_kg / 1000.0
        
        # Referenzfall (alles aus Netz)
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
            'PV-Erzeugung [kWh]': round((result_df['pv_kw'] * dt_h).sum(), 0),
            'H2-Erzeugung [kWh]': round((result_df['ely_power_kw'] * self.config.ely_eff_el * dt_h).sum(), 0),
        }

    def _find_most_dynamic_week_start_day(self, result_df: pd.DataFrame) -> int:
        """Wählt die Woche mit der größten H2-SOC-Spannweite (Peak-to-Peak)."""
        if 'h2_soc_kwh' not in result_df.columns or len(result_df) == 0:
            return 0

        dt_h = float(result_df['dt_h'].iloc[0]) if 'dt_h' in result_df.columns else 1.0
        steps_per_day = int(round(24 / dt_h))
        week_steps = 7 * steps_per_day
        if len(result_df) < week_steps:
            return 0

        best_start = 0
        best_span = -1.0
        max_start = len(result_df) - week_steps
        for start in range(0, max_start + 1, steps_per_day):
            week_soc = result_df['h2_soc_kwh'].iloc[start:start + week_steps]
            span = float(week_soc.max() - week_soc.min())
            if span > best_span:
                best_span = span
                best_start = start

        return int(best_start / steps_per_day)

    def _build_time_index(self, result_df: pd.DataFrame) -> pd.DatetimeIndex:
        """Erstellt konsistenten Zeitindex für Visualisierungen."""
        dt_h = float(result_df['dt_h'].iloc[0]) if 'dt_h' in result_df.columns else 1.0
        freq = f"{int(round(dt_h * 60))}min"
        return pd.date_range(start='2026-01-01', periods=len(result_df), freq=freq)
    
    def plot_week(self, result_df: pd.DataFrame, title: str = "Wochenprofil", show: bool = False,
                  start_day: Optional[int] = 172, save_path: str = None,
                  adaptive_soc_axis: bool = True):
        """
        Erstellt detailliertes Wochenprofil.
        
        Args:
            result_df: DataFrame mit Simulationsergebnissen
            title: Titel für den Plot
            start_day: Starttag (0-365)
            save_path: Optional: Pfad zum Speichern
        """
        dt_h = float(result_df['dt_h'].iloc[0]) if 'dt_h' in result_df.columns else 1.0
        steps_per_day = int(round(24 / dt_h))
        if start_day is None:
            start_day = self._find_most_dynamic_week_start_day(result_df)

        start = start_day * steps_per_day
        end = start + 7 * steps_per_day
        week = result_df.iloc[start:end].reset_index(drop=True)
        
        fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
        fig.suptitle(title, fontsize=14, fontweight='bold')
        hours = range(len(week))
        
        # Plot 1: Strombilanz
        ax1 = axes[0]
        ax1.fill_between(hours, 0, week['pv_kw'],
                         alpha=0.7, color='gold', label='PV-Erzeugung')
        ev_plot_col = 'ev_charge_kw' if 'ev_charge_kw' in week.columns else 'ev_demand_kw'
        ax1.fill_between(hours, 0, -(week['load_el_kw'] + week[ev_plot_col]),
                         alpha=0.5, color='steelblue', label='El. Last + E-Auto')
        ax1.fill_between(hours, 0, -week['hp_el_kw'],
                         alpha=0.5, color='orange', label='WP Strom')
        ax1.plot(hours, week['grid_import_kw'], 'r-', lw=1.5, label='Netzbezug')
        ax1.plot(hours, -week['grid_export_kw'], 'g-', lw=1.5, label='Einspeisung')
        ax1.axhline(0, color='black', lw=0.5)
        ax1.set_ylabel('Leistung [kW]')
        ax1.legend(loc='upper right', fontsize=8)
        ax1.grid(True, alpha=0.3)
        ax1.set_title('Strombilanz')
        
        # Plot 2: ELY und BZ
        ax2 = axes[1]
        ax2.fill_between(hours, 0, week['ely_power_kw'],
                         alpha=0.7, color='purple', label='Elektrolyseur')
        ax2.fill_between(hours, 0, week['fc_power_kw'],
                         alpha=0.7, color='teal', label='Brennstoffzelle')
        ax2.fill_between(hours, 0, week['heat_from_waste_kw'],
                         alpha=0.4, color='red', label='Abwärme genutzt')
        ax2.set_ylabel('Leistung [kW]')
        ax2.legend(loc='upper right', fontsize=8)
        ax2.grid(True, alpha=0.3)
        ax2.set_title('H2-System')
        
        # Plot 3: H2-SOC
        ax3 = axes[2]
        soc_pct = week['h2_soc_kwh'] / self.config.h2_capacity_kwh * 100
        ax3.plot(hours, soc_pct, 'darkgreen', lw=2, label='H2-SOC')
        if adaptive_soc_axis and len(soc_pct) > 0:
            soc_min = float(soc_pct.min())
            soc_max = float(soc_pct.max())
            span = max(2.0, soc_max - soc_min)
            margin = max(1.0, span * 0.2)
            lower = max(0.0, soc_min - margin)
            upper = min(105.0, soc_max + margin)
            if upper - lower < 5.0:
                mid = 0.5 * (upper + lower)
                lower = max(0.0, mid - 2.5)
                upper = min(105.0, mid + 2.5)
            ax3.set_ylim(lower, upper)
        else:
            ax3.set_ylim(0, 105)
        ax3.axhline(5, color='red', ls='--', lw=1, label='Min SOC')
        ax3.set_ylabel('H2-SOC [%]')
        ax3.set_xlabel('Zeitschritte der Woche')
        ax3.legend(loc='upper right', fontsize=8)
        ax3.grid(True, alpha=0.3)
        ax3.set_title('Wasserstoff-Speicherstand')
        
        plt.tight_layout()
        
        if save_path:
            resolved_path = self._resolve_output_path(save_path)
            plt.savefig(resolved_path, dpi=150)
            print(f"  ✓ Gespeichert: {resolved_path}")
        
        # plt.show()
        plt.close(fig)

    def plot_h2_soc_year(self, result_df: pd.DataFrame, title: str = "H2-SOC Jahresverlauf",
                         save_path: str = None):
        """Zeigt Jahres-/Saisondynamik des H2-SOC als Tages-Min/Max-Band plus Tagesmittel."""
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

        # Saisonfenster zur Orientierung
        ax.axvspan(pd.Timestamp('2026-03-01'), pd.Timestamp('2026-05-31'), color='#dff0d8', alpha=0.25)
        ax.axvspan(pd.Timestamp('2026-06-01'), pd.Timestamp('2026-08-31'), color='#fcf8e3', alpha=0.25)
        ax.axvspan(pd.Timestamp('2026-09-01'), pd.Timestamp('2026-11-30'), color='#d9edf7', alpha=0.25)
        ax.axvspan(pd.Timestamp('2026-12-01'), pd.Timestamp('2026-12-31'), color='#f2dede', alpha=0.25)
        ax.axvspan(pd.Timestamp('2026-01-01'), pd.Timestamp('2026-02-28'), color='#f2dede', alpha=0.25)

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
    
    def plot_kpi_comparison(self, kpi_list: List[Dict], show: bool = False, 
                           save_path: str = None):
        """
        Erstellt KPI-Vergleichsdiagramm.
        
        Args:
            kpi_list: Liste von KPI-Dicts
            save_path: Optional: Pfad zum Speichern
        """
        labels = [k['label'] for k in kpi_list]
        metrics = ['Autarkiegrad [%]', 'Energiekosten [CHF/a]',
                  'CO2-Emissionen [tCO2/a]', 'MAC [CHF/tCO2]']
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle('KPI-Vergleich: Strategien & Szenarien', 
                    fontsize=14, fontweight='bold')
        colors = plt.cm.Set2(np.linspace(0, 1, len(labels)))
        
        for ax, metric in zip(axes.flatten(), metrics):
            values = [k[metric] for k in kpi_list]
            bars = ax.bar(labels, values, color=colors)
            ax.set_title(metric, fontweight='bold')
            ax.set_ylabel(metric)
            ax.tick_params(axis='x', rotation=30)
            
            # Werte auf Balken
            for bar, val in zip(bars, values):
                ax.text(bar.get_x() + bar.get_width() / 2,
                       bar.get_height() * 1.01,
                       f'{val:,.0f}', ha='center', va='bottom', fontsize=8)
            ax.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        
        if save_path:
            resolved_path = self._resolve_output_path(save_path)
            plt.savefig(resolved_path, dpi=150)
            print(f"  ✓ Gespeichert: {resolved_path}")
        
        # plt.show()
        plt.close(fig)
    
    def print_kpi_table(self, kpi_list: List[Dict]):
        """
        Gibt KPI-Tabelle formatiert aus.
        
        Args:
            kpi_list: Liste von KPI-Dicts
        """
        kpi_df = pd.DataFrame(kpi_list).set_index('label')
        print("\n" + "="*100)
        print("KPI-ÜBERSICHTSTABELLE")
        print("="*100)
        print(kpi_df.to_string())
        print("="*100 + "\n")
    
    def save_kpis_to_csv(self, kpi_list: List[Dict], 
                        filepath: str = "kpi_ergebnisse.csv"):
        """
        Speichert KPIs in CSV-Datei.
        
        Args:
            kpi_list: Liste von KPI-Dicts
            filepath: Zieldatei
        """
        resolved_path = self._resolve_output_path(filepath)
        kpi_df = pd.DataFrame(kpi_list)
        kpi_df.to_csv(resolved_path, index=False)
        print(f"  ✓ KPI-Ergebnisse gespeichert: {resolved_path}")
