"""
Analyzer-Modul: KPI-Berechnung, Auswertung und Visualisierung.
"""

import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
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
        total_import = result_df['grid_import_kw'].sum()
        total_export = result_df['grid_export_kw'].sum()
        
        # Gesamtlast
        total_el_load = (result_df['load_el_kw'] + result_df['ev_demand_kw']).sum()
        total_heat_load_el = (result_df['load_heat_kw'] / self.config.hp_cop).sum()
        total_load_el_equiv = total_el_load + total_heat_load_el
        
        # Autarkiegrad
        autarky = max(0.0, 1.0 - (total_import / total_load_el_equiv))
        
        # Energiekosten
        costs_import = (result_df['grid_import_kw'] * result_df['price_buy']).sum()
        costs_export = (result_df['grid_export_kw'] * result_df['price_sell']).sum()
        net_costs = costs_import - costs_export
        
        # CO2-Emissionen
        co2_kg = (result_df['grid_import_kw'] * result_df['co2_intensity']).sum()
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
            'PV-Erzeugung [kWh]': round(result_df['pv_kw'].sum(), 0),
            'H2-Erzeugung [kWh]': round(result_df['ely_power_kw'].sum() * self.config.ely_eff_el, 0),
        }
    
    def plot_week(self, result_df: pd.DataFrame, title: str = "Wochenprofil", show: bool = False,
                  start_day: int = 172, save_path: str = None):
        """
        Erstellt detailliertes Wochenprofil.
        
        Args:
            result_df: DataFrame mit Simulationsergebnissen
            title: Titel für den Plot
            start_day: Starttag (0-365)
            save_path: Optional: Pfad zum Speichern
        """
        start = start_day * 24
        end = start + 7 * 24
        week = result_df.iloc[start:end].reset_index(drop=True)
        
        fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
        fig.suptitle(title, fontsize=14, fontweight='bold')
        hours = range(len(week))
        
        # Plot 1: Strombilanz
        ax1 = axes[0]
        ax1.fill_between(hours, 0, week['pv_kw'],
                         alpha=0.7, color='gold', label='PV-Erzeugung')
        ax1.fill_between(hours, 0, -(week['load_el_kw'] + week['ev_demand_kw']),
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
        ax3.set_ylim(0, 105)
        ax3.axhline(5, color='red', ls='--', lw=1, label='Min SOC')
        ax3.set_ylabel('H2-SOC [%]')
        ax3.set_xlabel('Stunden der Woche')
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
