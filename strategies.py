"""
Betriebsstrategien-Modul: Heuristische und preisbasierte Steuerung.
"""

from abc import ABC, abstractmethod
import pandas as pd
import numpy as np
from config import SystemConfig
from components import H2Storage, Electrolyzer, FuelCell, HeatPump


class Strategy(ABC):
    """
    Abstrakte Basisklasse für Betriebsstrategien.
    Definiert Interface für konkrete Strategieimplementierungen.
    """
    
    def __init__(self, config: SystemConfig):
        self.config = config
        self.name = self.__class__.__name__
        
    @abstractmethod
    def run(self, profile_df: pd.DataFrame) -> pd.DataFrame:
        """
        Führt Simulation mit dieser Strategie durch.
        
        Args:
            profile_df: DataFrame mit Energieprofilen
            
        Returns:
            pd.DataFrame: Erweitert um Ergebnisspalten
        """
        pass
    
    def __repr__(self):
        return f"{self.name}(Config: {self.config})"


class HeuristicStrategy(Strategy):
    """
    Strategie 1: Eigenverbrauchsoptimierung (Heuristik)
    
    Priorität:
    1. PV → Last
    2. PV-Überschuss → Elektrolyseur (H2 produzieren)
    3. H2 im Speicher → Brennstoffzelle (bei Defizit)
    4. Defizit → Netz
    5. Überschuss → Netz
    
    Wärme: Wärmepumpe deckt Bedarf; Abwärme von ELY/BZ wird angerechnet.
    """
    
    def run(self, profile_df: pd.DataFrame) -> pd.DataFrame:
        """Führt Simulation mit heuristischer Strategie durch."""
        h2 = H2Storage(self.config)
        ely = Electrolyzer(self.config)
        fc = FuelCell(self.config)
        hp = HeatPump(self.config)
        
        results = []
        
        for _, row in profile_df.iterrows():
            result = self._dispatch_hour(row, h2, ely, fc, hp)
            results.append(result)
        
        return pd.concat([
            profile_df.reset_index(drop=True),
            pd.DataFrame(results)
        ], axis=1)
    
    def _dispatch_hour(self, row, h2: H2Storage, ely: Electrolyzer, 
                      fc: FuelCell, hp: HeatPump) -> dict:
        """Betriebseinsatz für eine Stunde."""
        pv = row['pv_kw']
        load_el = row['load_el_kw'] + row['ev_demand_kw']
        load_heat = row['load_heat_kw']
        
        # Wärmedeckung mit WP
        hp_el_needed = min(load_heat / hp.cop, self.config.hp_kw_th_max / hp.cop)
        total_el_demand = load_el + hp_el_needed
        net_el = pv - total_el_demand
        
        grid_import = 0.0
        grid_export = 0.0
        ely_power = 0.0
        fc_power = 0.0
        h2_prod = 0.0
        heat_from_ely = 0.0
        heat_from_fc = 0.0
        
        if net_el >= 0:
            # Überschuss → Elektrolyseur
            ely_result = ely.run(net_el)
            ely_power = ely_result['power_used']
            h2_prod = ely_result['h2_produced']
            heat_from_ely = ely_result['heat_produced']
            
            h2_stored = h2.charge(h2_prod)
            unused_ely_power = ely_power * (1 - h2_stored / h2_prod) if h2_prod > 0 else 0
            grid_export = (net_el - ely_power) + unused_ely_power
            grid_export = max(0.0, grid_export)
        
        else:
            # Defizit → Brennstoffzelle
            shortage = abs(net_el)
            fc_result = fc.run(shortage, h2.soc_kwh)
            fc_power = fc_result['power_out']
            h2_used = fc_result['h2_used']
            heat_from_fc = fc_result['heat_produced']
            h2.discharge(h2_used)
            grid_import = max(0.0, shortage - fc_power)
        
        # Abwärme-Korrektur
        total_waste_heat = heat_from_ely + heat_from_fc
        heat_covered_by_waste = min(total_waste_heat, load_heat)
        remaining_heat_demand = load_heat - heat_covered_by_waste
        hp_el_actual = remaining_heat_demand / hp.cop
        hp_el_saved = hp_el_needed - hp_el_actual
        
        if grid_import > 0:
            grid_import = max(0.0, grid_import - hp_el_saved)
        else:
            grid_export += hp_el_saved
        
        return {
            'grid_import_kw': grid_import,
            'grid_export_kw': grid_export,
            'ely_power_kw': ely_power,
            'fc_power_kw': fc_power,
            'h2_soc_kwh': h2.soc_kwh,
            'hp_el_kw': hp_el_actual,
            'heat_from_waste_kw': heat_covered_by_waste,
        }


class PriceBasedStrategy(Strategy):
    """
    Strategie 2: Preisbasierte Steuerung
    
    - Elektrolyseur läuft bevorzugt bei günstigen Strompreisen
    - Brennstoffzelle liefert bevorzugt bei hohen Strompreisen
    - E-Auto lädt bei günstigen Preisen
    
    Ziel: Wirtschaftliche Optimierung der H2-Produktion und -Nutzung
    """
    
    def run(self, profile_df: pd.DataFrame) -> pd.DataFrame:
        """Führt Simulation mit preisbasierter Strategie durch."""
        h2 = H2Storage(self.config)
        ely = Electrolyzer(self.config)
        fc = FuelCell(self.config)
        hp = HeatPump(self.config)
        
        results = []
        
        for _, row in profile_df.iterrows():
            result = self._dispatch_hour(row, h2, ely, fc, hp)
            results.append(result)
        
        return pd.concat([
            profile_df.reset_index(drop=True),
            pd.DataFrame(results)
        ], axis=1)
    
    def _dispatch_hour(self, row, h2: H2Storage, ely: Electrolyzer,
                      fc: FuelCell, hp: HeatPump) -> dict:
        """Preisbasierter Betriebseinsatz für eine Stunde."""
        pv = row['pv_kw']
        price = row['price_buy']
        load_el = row['load_el_kw'] + row['ev_demand_kw']
        load_heat = row['load_heat_kw']
        
        hp_el_needed = min(load_heat / hp.cop, self.config.hp_kw_th_max / hp.cop)
        total_el_demand = load_el + hp_el_needed
        net_el = pv - total_el_demand
        
        grid_import = 0.0
        grid_export = 0.0
        ely_power = 0.0
        fc_power = 0.0
        heat_from_ely = 0.0
        heat_from_fc = 0.0
        
        if net_el >= 0:
            # ELY nur bei günstigen Preisen oder großem Überschuss
            if price < self.config.price_threshold_ely or net_el > 10.0:
                ely_result = ely.run(net_el)
                ely_power = ely_result['power_used']
                h2_prod = ely_result['h2_produced']
                heat_from_ely = ely_result['heat_produced']
                h2.charge(h2_prod)
                grid_export = max(0.0, net_el - ely_power)
            else:
                grid_export = net_el
        
        else:
            shortage = abs(net_el)
            # BZ bevorzugt bei hohem Strompreis (wirtschaftlich sinnvoll)
            if price > self.config.price_threshold_fc and h2.soc_kwh > h2.min_soc_kwh:
                fc_result = fc.run(shortage, h2.soc_kwh)
                fc_power = fc_result['power_out']
                h2_used = fc_result['h2_used']
                heat_from_fc = fc_result['heat_produced']
                h2.discharge(h2_used)
                grid_import = max(0.0, shortage - fc_power)
            else:
                grid_import = shortage
        
        # Abwärme-Korrektur
        total_waste_heat = heat_from_ely + heat_from_fc
        heat_covered_by_waste = min(total_waste_heat, load_heat)
        remaining_heat_demand = load_heat - heat_covered_by_waste
        hp_el_actual = remaining_heat_demand / hp.cop
        hp_el_saved = hp_el_needed - hp_el_actual
        
        if grid_import > 0:
            grid_import = max(0.0, grid_import - hp_el_saved)
        else:
            grid_export += hp_el_saved
        
        return {
            'grid_import_kw': grid_import,
            'grid_export_kw': grid_export,
            'ely_power_kw': ely_power,
            'fc_power_kw': fc_power,
            'h2_soc_kwh': h2.soc_kwh,
            'hp_el_kw': hp_el_actual,
            'heat_from_waste_kw': heat_covered_by_waste,
        }
