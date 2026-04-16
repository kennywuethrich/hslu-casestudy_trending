"""Modifiziert Energieprofile basierend auf GUI-Eingaben."""

import pandas as pd
import numpy as np
from user_config import UserInputConfig


class ProfileModifier:
    """Wendet Benutzer-Parameter auf Energieprofile an."""
    
    BASELINE_EV_COUNT = 1
    SHIFTABLE_LOAD_FRACTION = 0.30
    
    @staticmethod
    def apply_all(profiles: pd.DataFrame, user_config: UserInputConfig) -> pd.DataFrame:
        """Wendet alle aktiven Modifikationen an."""
        modified = profiles.copy()
        
        if user_config.num_evs != ProfileModifier.BASELINE_EV_COUNT:
            modified = ProfileModifier.scale_ev_demand(modified, user_config.num_evs)
        
        if user_config.smart_energy_enabled:
            modified = ProfileModifier.apply_smart_energy(modified)
        
        return modified
    
    @staticmethod
    def scale_ev_demand(profiles: pd.DataFrame, num_evs: int) -> pd.DataFrame:
        """Skaliert EV-Ladeprofil basierend auf Fahrzeuganzahl."""
        modified = profiles.copy()
        scaling_factor = num_evs / ProfileModifier.BASELINE_EV_COUNT
        modified['ev_demand_kw'] = modified['ev_demand_kw'] * scaling_factor
        return modified
    
    @staticmethod
    def apply_smart_energy(profiles: pd.DataFrame) -> pd.DataFrame:
        """
        Verschiebt 30% der Haushaltslast zu PV-Spitzenwerten.
        
        Identifiziert täglich verschiebbare Last und verteilt sie
        zu Stunden mit höchster Solarstrahlung.
        """
        modified = profiles.copy()
        modified['load_el_kw'] = modified['load_el_kw'].astype(float)
        modified['pv_kw'] = modified['pv_kw'].astype(float)
        
        daily_groups = modified.groupby('day_of_year')
        new_load = modified['load_el_kw'].copy()
        
        for day, day_data in daily_groups:
            day_indices = day_data.index
            base_load = modified.loc[day_indices, 'load_el_kw']
            pv_profile = modified.loc[day_indices, 'pv_kw']
            
            shiftable_energy = (base_load * ProfileModifier.SHIFTABLE_LOAD_FRACTION).sum()
            if shiftable_energy <= 0:
                continue
            
            pv_peak_value = pv_profile.max()
            if pv_peak_value <= 0:
                continue
            
            pv_normalized = pv_profile / pv_peak_value
            distribution = pv_normalized / pv_normalized.sum() if pv_normalized.sum() > 0 else 0
            
            reduced_base_load = base_load * (1 - ProfileModifier.SHIFTABLE_LOAD_FRACTION)
            shifted_load = reduced_base_load + (shiftable_energy * distribution)
            
            new_load.loc[day_indices] = shifted_load
        
        modified['load_el_kw'] = new_load
        return modified
    
    @staticmethod
    def get_hourly_price(hour_of_day: int, user_config: UserInputConfig) -> float:
        """
        Berechnet Strompreis für Stunde basierend auf Tarif.
        
        Nacht-Tarif: 22:00 - 06:00 Uhr
        Tag-Tarif: 06:00 - 22:00 Uhr
        """
        if not user_config.variable_prices_enabled:
            return user_config.price_day_chf_per_kwh
        
        night_start, night_end = 22, 6
        is_night = hour_of_day >= night_start or hour_of_day < night_end
        
        return user_config.price_night_chf_per_kwh if is_night else user_config.price_day_chf_per_kwh
