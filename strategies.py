"""
Betriebsstrategien-Modul: Heuristische und preisbasierte Steuerung.
"""

from abc import ABC, abstractmethod
import pandas as pd
from config import SystemConfig
from components import H2Storage, Electrolyzer, FuelCell, HeatPump, EVStorage, ThermalStorage


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
        ev = EVStorage(self.config)
        th = ThermalStorage(self.config)
        ely = Electrolyzer(self.config)
        fc = FuelCell(self.config)
        hp = HeatPump(self.config)
        
        results = []
        
        for _, row in profile_df.iterrows():
            result = self._dispatch_hour(row, h2, ev, th, ely, fc, hp)
            results.append(result)
        
        return pd.concat([
            profile_df.reset_index(drop=True),
            pd.DataFrame(results)
        ], axis=1)

    def _should_use_fc(self, shortage_kw: float, h2: H2Storage) -> bool:
        """
        FC-Einsatz für Heuristik:
        - oberhalb einer SOC-Zielreserve grundsätzlich zulassen,
        - unterhalb der Zielreserve nur zur Peak-Shaving-Unterstützung.
        """
        if h2.available_discharge <= 0:
            return False

        soc_pct = h2.soc_kwh / h2.capacity if h2.capacity > 0 else 0.0
        reserve_target = max(self.config.fc_reserve_soc_target, self.config.h2_min_soc)
        if soc_pct > reserve_target:
            return True

        return shortage_kw >= self.config.fc_peak_shaving_kw
    
    def _dispatch_hour(self, row, h2: H2Storage, ev: EVStorage, th: ThermalStorage,
                      ely: Electrolyzer, fc: FuelCell, hp: HeatPump) -> dict:
        """Betriebseinsatz für einen Zeitschritt."""
        dt_h = row['dt_h'] if 'dt_h' in row else 1.0
        pv = row['pv_kw']
        load_el = row['load_el_kw']
        load_heat_kw = row['load_heat_kw']
        load_heat_kwh = load_heat_kw * dt_h
        ev_drive_kwh = row['ev_demand_kw'] * dt_h
        ev_unserved_drive_kwh = ev.consume_drive_energy(ev_drive_kwh)
        
        # Basis-WP für aktuellen Wärmebedarf (wird später mit Speicher/Abwärme korrigiert)
        hp_base_kw = min(load_heat_kw / hp.cop, self.config.hp_kw_th_max / hp.cop)
        total_el_demand = load_el + hp_base_kw
        net_el = pv - total_el_demand
        
        grid_import = 0.0
        grid_export = 0.0
        ely_power = 0.0
        fc_power = 0.0
        ev_charge_kw = 0.0
        hp_extra_kw = 0.0
        h2_prod = 0.0
        heat_from_ely = 0.0
        heat_from_fc = 0.0
        heat_from_hp_extra = 0.0
        
        if net_el >= 0:
            # 1) EV immer vor H2 laden
            ev_charge_kw = ev.charge_with_power(net_el, dt_h)
            net_el = max(0.0, net_el - ev_charge_kw)

            # 2) Wärmepumpe mit Überschussstrom betreiben (Gebäudeintern puffern)
            hp_max_el_kw = self.config.hp_kw_th_max / hp.cop
            hp_extra_kw = min(net_el, max(0.0, hp_max_el_kw - hp_base_kw))
            heat_from_hp_extra = hp_extra_kw * hp.cop * dt_h
            net_el = max(0.0, net_el - hp_extra_kw)

            # Überschuss → Elektrolyseur
            ely_result = ely.run(net_el, dt_h=dt_h)
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
            if self._should_use_fc(shortage, h2):
                fc_result = fc.run(shortage, h2.available_discharge, dt_h=dt_h)
                fc_power = fc_result['power_out']
                h2_used = fc_result['h2_used']
                heat_from_fc = fc_result['heat_produced']
                h2.discharge(h2_used)
                grid_import = max(0.0, shortage - fc_power)
            else:
                grid_import = shortage
        
        # Wärmekette: Abwärme + HP-Überschuss + thermischer Speicher + Rest-WP
        heat_direct_kwh = heat_from_ely + heat_from_fc + heat_from_hp_extra

        if heat_direct_kwh > load_heat_kwh:
            th.charge(heat_direct_kwh - load_heat_kwh)
            heat_after_direct_kwh = 0.0
        else:
            heat_after_direct_kwh = load_heat_kwh - heat_direct_kwh

        heat_from_thermal_kwh = th.discharge(heat_after_direct_kwh)
        heat_after_storage_kwh = max(0.0, heat_after_direct_kwh - heat_from_thermal_kwh)

        hp_el_final_kw = heat_after_storage_kwh / (hp.cop * dt_h) if dt_h > 0 else 0.0
        hp_el_accounted_kw = hp_base_kw + hp_extra_kw
        hp_el_adjust_kw = hp_el_accounted_kw - hp_el_final_kw

        if hp_el_adjust_kw >= 0:
            if grid_import > 0:
                grid_import = max(0.0, grid_import - hp_el_adjust_kw)
            else:
                recovered_surplus_kw = max(0.0, hp_el_adjust_kw)
                if recovered_surplus_kw > 0:
                    ely_result_2 = ely.run(recovered_surplus_kw, dt_h=dt_h)
                    ely_power_2 = ely_result_2['power_used']
                    h2_prod_2 = ely_result_2['h2_produced']
                    heat_from_ely += ely_result_2['heat_produced']
                    h2_stored_2 = h2.charge(h2_prod_2)
                    unused_ely_power_2 = ely_power_2 * (1 - h2_stored_2 / h2_prod_2) if h2_prod_2 > 0 else 0.0
                    ely_power += ely_power_2
                    grid_export += max(0.0, (recovered_surplus_kw - ely_power_2) + unused_ely_power_2)
        else:
            add_import_kw = abs(hp_el_adjust_kw)
            if self._should_use_fc(add_import_kw, h2):
                extra_fc_result = fc.run(add_import_kw, h2.available_discharge, dt_h=dt_h)
                extra_fc_power = extra_fc_result['power_out']
                extra_h2_used = extra_fc_result['h2_used']
                extra_heat_kwh = extra_fc_result['heat_produced']
                if extra_h2_used > 0:
                    h2.discharge(extra_h2_used)
                    fc_power += extra_fc_power
                    heat_from_fc += extra_heat_kwh
                grid_import += max(0.0, add_import_kw - extra_fc_power)
            else:
                grid_import += add_import_kw

        hp_el_actual = hp_el_final_kw
        heat_from_waste_kwh = min(load_heat_kwh, heat_direct_kwh + heat_from_thermal_kwh)
        
        return {
            'grid_import_kw': grid_import,
            'grid_export_kw': grid_export,
            'ely_power_kw': ely_power,
            'fc_power_kw': fc_power,
            'h2_soc_kwh': h2.soc_kwh,
            'ev_soc_kwh': ev.soc_kwh,
            'ev_charge_kw': ev_charge_kw,
            'ev_unserved_drive_kwh': ev_unserved_drive_kwh,
            'thermal_soc_kwh': th.soc_kwh,
            'hp_el_kw': hp_el_actual,
            'heat_from_waste_kw': (heat_from_waste_kwh / dt_h) if dt_h > 0 else 0.0,
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
        ev = EVStorage(self.config)
        th = ThermalStorage(self.config)
        ely = Electrolyzer(self.config)
        fc = FuelCell(self.config)
        hp = HeatPump(self.config)
        
        results = []
        
        for _, row in profile_df.iterrows():
            result = self._dispatch_hour(row, h2, ev, th, ely, fc, hp)
            results.append(result)
        
        return pd.concat([
            profile_df.reset_index(drop=True),
            pd.DataFrame(results)
        ], axis=1)

    def _should_use_fc(self, price: float, shortage_kw: float, h2: H2Storage) -> bool:
        """
        Aktiviert die Brennstoffzelle bei Defizit entweder
        - wirtschaftlich (hoher Preis), oder
        - betrieblich sinnvoll, wenn H2-SOC deutlich über Reserve liegt.
        """
        if h2.available_discharge <= 0:
            return False

        soc_pct = h2.soc_kwh / h2.capacity if h2.capacity > 0 else 0.0
        reserve_target = max(self.config.fc_reserve_soc_target, self.config.h2_min_soc)
        return (price > self.config.price_threshold_fc) or (soc_pct > reserve_target) or (shortage_kw >= self.config.fc_peak_shaving_kw)
    
    def _dispatch_hour(self, row, h2: H2Storage, ev: EVStorage, th: ThermalStorage,
                      ely: Electrolyzer, fc: FuelCell, hp: HeatPump) -> dict:
        """Preisbasierter Betriebseinsatz für einen Zeitschritt."""
        dt_h = row['dt_h'] if 'dt_h' in row else 1.0
        pv = row['pv_kw']
        price = row['price_buy']
        load_el = row['load_el_kw']
        load_heat_kw = row['load_heat_kw']
        load_heat_kwh = load_heat_kw * dt_h
        ev_drive_kwh = row['ev_demand_kw'] * dt_h
        ev_unserved_drive_kwh = ev.consume_drive_energy(ev_drive_kwh)
        
        hp_base_kw = min(load_heat_kw / hp.cop, self.config.hp_kw_th_max / hp.cop)
        total_el_demand = load_el + hp_base_kw
        net_el = pv - total_el_demand
        
        grid_import = 0.0
        grid_export = 0.0
        ely_power = 0.0
        fc_power = 0.0
        ev_charge_kw = 0.0
        hp_extra_kw = 0.0
        heat_from_ely = 0.0
        heat_from_fc = 0.0
        heat_from_hp_extra = 0.0
        
        if net_el >= 0:
            ev_charge_kw = ev.charge_with_power(net_el, dt_h)
            net_el = max(0.0, net_el - ev_charge_kw)

            hp_max_el_kw = self.config.hp_kw_th_max / hp.cop
            hp_extra_kw = min(net_el, max(0.0, hp_max_el_kw - hp_base_kw))
            heat_from_hp_extra = hp_extra_kw * hp.cop * dt_h
            net_el = max(0.0, net_el - hp_extra_kw)

            # Physische Priorität: kostenloser PV-Überschuss immer zuerst in H2.
            ely_result = ely.run(net_el, dt_h=dt_h)
            ely_power = ely_result['power_used']
            h2_prod = ely_result['h2_produced']
            heat_from_ely = ely_result['heat_produced']
            h2_stored = h2.charge(h2_prod)
            unused_ely_power = ely_power * (1 - h2_stored / h2_prod) if h2_prod > 0 else 0.0
            grid_export = max(0.0, (net_el - ely_power) + unused_ely_power)
        
        else:
            shortage = abs(net_el)
            if self._should_use_fc(price, shortage, h2):
                fc_result = fc.run(shortage, h2.available_discharge, dt_h=dt_h)
                fc_power = fc_result['power_out']
                h2_used = fc_result['h2_used']
                heat_from_fc = fc_result['heat_produced']
                h2.discharge(h2_used)
                grid_import = max(0.0, shortage - fc_power)
            else:
                grid_import = shortage
        
        heat_direct_kwh = heat_from_ely + heat_from_fc + heat_from_hp_extra

        if heat_direct_kwh > load_heat_kwh:
            th.charge(heat_direct_kwh - load_heat_kwh)
            heat_after_direct_kwh = 0.0
        else:
            heat_after_direct_kwh = load_heat_kwh - heat_direct_kwh

        heat_from_thermal_kwh = th.discharge(heat_after_direct_kwh)
        heat_after_storage_kwh = max(0.0, heat_after_direct_kwh - heat_from_thermal_kwh)

        hp_el_final_kw = heat_after_storage_kwh / (hp.cop * dt_h) if dt_h > 0 else 0.0
        hp_el_accounted_kw = hp_base_kw + hp_extra_kw
        hp_el_adjust_kw = hp_el_accounted_kw - hp_el_final_kw

        if hp_el_adjust_kw >= 0:
            if grid_import > 0:
                grid_import = max(0.0, grid_import - hp_el_adjust_kw)
            else:
                recovered_surplus_kw = max(0.0, hp_el_adjust_kw)
                if recovered_surplus_kw > 0:
                    ely_result_2 = ely.run(recovered_surplus_kw, dt_h=dt_h)
                    ely_power_2 = ely_result_2['power_used']
                    h2_prod_2 = ely_result_2['h2_produced']
                    heat_from_ely += ely_result_2['heat_produced']
                    h2_stored_2 = h2.charge(h2_prod_2)
                    unused_ely_power_2 = ely_power_2 * (1 - h2_stored_2 / h2_prod_2) if h2_prod_2 > 0 else 0.0
                    ely_power += ely_power_2
                    grid_export += max(0.0, (recovered_surplus_kw - ely_power_2) + unused_ely_power_2)
        else:
            add_import_kw = abs(hp_el_adjust_kw)
            if self._should_use_fc(price, add_import_kw, h2):
                extra_fc_result = fc.run(add_import_kw, h2.available_discharge, dt_h=dt_h)
                extra_fc_power = extra_fc_result['power_out']
                extra_h2_used = extra_fc_result['h2_used']
                extra_heat_kwh = extra_fc_result['heat_produced']
                if extra_h2_used > 0:
                    h2.discharge(extra_h2_used)
                    fc_power += extra_fc_power
                    heat_from_fc += extra_heat_kwh
                grid_import += max(0.0, add_import_kw - extra_fc_power)
            else:
                grid_import += add_import_kw

        hp_el_actual = hp_el_final_kw
        heat_from_waste_kwh = min(load_heat_kwh, heat_direct_kwh + heat_from_thermal_kwh)
        
        return {
            'grid_import_kw': grid_import,
            'grid_export_kw': grid_export,
            'ely_power_kw': ely_power,
            'fc_power_kw': fc_power,
            'h2_soc_kwh': h2.soc_kwh,
            'ev_soc_kwh': ev.soc_kwh,
            'ev_charge_kw': ev_charge_kw,
            'ev_unserved_drive_kwh': ev_unserved_drive_kwh,
            'thermal_soc_kwh': th.soc_kwh,
            'hp_el_kw': hp_el_actual,
            'heat_from_waste_kw': (heat_from_waste_kwh / dt_h) if dt_h > 0 else 0.0,
        }
