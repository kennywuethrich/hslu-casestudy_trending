"""
Lastprofile-Generator für H2-Microgrid Simulation.
Erzeugt synthetische oder importiert echte Energielastprofile.
"""

import numpy as np
import pandas as pd
from typing import Literal


class ProfileGenerator:
    """
    Generiert oder lädt Energielastprofile für die Simulation.
    """
    
    @staticmethod
    def generate_annual_profiles(
        hours: int = 8760,
        seed: int = 42,
        ev_mode: Literal['evening', 'daytime', 'workplace'] = 'evening'
    ) -> pd.DataFrame:
        """
        Generiert synthetische Jahresprofile.
        
        Args:
            hours: Anzahl der Stunden (normalerweise 8760 für 1 Jahr)
            seed: Random Seed für Reproduzierbarkeit
            ev_mode: E-Auto Lademodus
            
        Returns:
            pd.DataFrame: Vollständige Lastprofile mit PV, Strom, Wärme, Preisen
        """
        np.random.seed(seed)
        t = np.arange(hours)
        hour_of_day = t % 24
        day_of_year = t // 24

        # --- PV-Profil (87 kWp): Tag/Nacht + Saisonalität ---
        sunrise = 6 - 2 * np.cos(2 * np.pi * day_of_year / 365)
        sunset  = 18 + 2 * np.cos(2 * np.pi * day_of_year / 365)
        day_length = sunset - sunrise

        sun_angle = np.clip((hour_of_day - sunrise) / day_length, 0, 1)
        pv_norm = np.sin(sun_angle * np.pi) ** 1.5

        seasonal = 0.65 + 0.35 * np.sin(2 * np.pi * (day_of_year - 80) / 365)
        clouds = np.random.uniform(0.7, 1.0, hours)
        pv = 87.0 * pv_norm * seasonal * clouds
        pv = np.clip(pv, 0, 87.0)

        # --- Stromlastprofil (ohne WP & E-Auto) ---
        morning_peak = np.exp(-0.5 * ((hour_of_day - 7.5) / 1.5) ** 2)
        evening_peak = np.exp(-0.5 * ((hour_of_day - 19.0) / 2.0) ** 2)
        base_load = 8.0
        load_el = base_load + 15 * morning_peak + 18 * evening_peak
        load_el += np.random.normal(0, 1.5, hours)
        load_el = np.clip(load_el, 5.0, 50.0)

        # --- Wärmelastprofil ---
        seasonal_heat = 40 + 40 * np.cos(2 * np.pi * (day_of_year - 15) / 365)
        warmwater = 8 * (np.exp(-0.5 * ((hour_of_day - 7) / 1.0) ** 2)
                        + 0.5 * np.exp(-0.5 * ((hour_of_day - 20) / 1.0) ** 2))
        seasonal_heat = np.clip(seasonal_heat, 5.0, 80.0)
        load_heat = seasonal_heat + warmwater + np.random.normal(0, 2.0, hours)
        load_heat = np.clip(load_heat, 5.0, 95.0)

        # --- E-Auto Profil ---
        ev_demand = ProfileGenerator._generate_ev_profile(
            hours, hour_of_day, day_of_year, ev_mode
        )

        # --- Dynamischer Strompreis ---
        price_buy = np.where((hour_of_day >= 7) & (hour_of_day < 21), 0.30, 0.22)
        price_buy += np.random.normal(0, 0.01, hours)

        # --- CO2-Intensität (saisonal) ---
        co2_intensity = 0.128 - 0.04 * np.sin(2 * np.pi * (day_of_year - 80) / 365)

        df = pd.DataFrame({
            'hour': t,
            'hour_of_day': hour_of_day,
            'day_of_year': day_of_year,
            'pv_kw': pv,
            'load_el_kw': load_el,
            'load_heat_kw': load_heat,
            'ev_demand_kw': ev_demand,
            'price_buy': price_buy,
            'price_sell': 0.10,
            'co2_intensity': co2_intensity
        })
        return df

    @staticmethod
    def _generate_ev_profile(
        hours: int,
        hour_of_day: np.ndarray,
        day_of_year: np.ndarray,
        ev_mode: str
    ) -> np.ndarray:
        """
        Generiert E-Auto Lademuster basierend auf Modus.
        
        Args:
            hours: Gesamtstunden
            hour_of_day: Array mit Stunde des Tages
            day_of_year: Array mit Tag des Jahres
            ev_mode: Lademodus ('evening', 'daytime', 'workplace')
            
        Returns:
            np.ndarray: E-Auto Lastprofil
        """
        ev_demand = np.zeros(hours)
        
        if ev_mode == 'evening':
            # 18-22 Uhr (4h × 7.4 kW = ~30 kWh/Tag)
            ev_demand = np.where((hour_of_day >= 18) & (hour_of_day < 22), 7.4, 0.0)
        
        elif ev_mode == 'daytime':
            # 10-14 Uhr (tagsüber, PV-optimiert)
            ev_demand = np.where((hour_of_day >= 10) & (hour_of_day < 14), 7.4, 0.0)
        
        elif ev_mode == 'workplace':
            # Nur Werktage 8-17 Uhr (Workplace Charging)
            day_of_week = (day_of_year % 7)
            is_workday = day_of_week < 5
            ev_demand = np.where(
                is_workday & (hour_of_day >= 8) & (hour_of_day < 17), 3.3, 0.0
            )
        
        return ev_demand

    @staticmethod
    def load_from_csv(filepath: str) -> pd.DataFrame:
        """
        Lädt Profile von CSV-Datei.
        
        Args:
            filepath: Pfad zu CSV-Datei mit Profilen
            
        Returns:
            pd.DataFrame: Geladene Profile
        """
        return pd.read_csv(filepath)

    def __repr__(self):
        return "ProfileGenerator(synthetic or CSV import)"
