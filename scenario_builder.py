"""Erstellt Szenarien dynamisch aus GUI-Eingaben."""

import pandas as pd
from config import SystemConfig
from scenario import Scenario
from user_config import UserInputConfig
from profile_modifier import ProfileModifier


class ScenarioBuilder:
    """Konstruiert Scenario-Objekt aus Benutzer-Eingaben und modifizierten Profilen."""
    
    @staticmethod
    def build(user_config: UserInputConfig, profiles: pd.DataFrame) -> Scenario:
        """
        Erstellt ein Scenario basierend auf GUI-Eingaben.
        
        Args:
            user_config: UserInputConfig aus GUI
            profiles: Energie-Profile (werden intern modifiziert)
        
        Returns:
            Scenario: Vorkonfiguriertes Szenario
        """
        modified_profiles = ProfileModifier.apply_all(profiles, user_config)
        
        system_config = ScenarioBuilder._build_config(user_config)
        
        scenario_name = ScenarioBuilder._build_name(user_config)
        scenario_description = ScenarioBuilder._build_description(user_config)
        
        scenario = Scenario(
            name=scenario_name,
            config=system_config,
            ev_profile_mode='as_is',
            description=scenario_description
        )
        
        scenario._profiles = modified_profiles
        
        return scenario
    
    @staticmethod
    def _build_config(user_config: UserInputConfig) -> SystemConfig:
        """Erstellt SystemConfig basierend auf GUI-Eingaben."""
        config = SystemConfig()
        
        if user_config.hp_failure:
            config.hp_kw_th_max = 0.0
        
        if user_config.variable_prices_enabled:
            config.price_buy_chf = user_config.price_day_chf_per_kwh
        else:
            config.price_buy_chf = 0.28
        
        return config
    
    @staticmethod
    def _build_name(user_config: UserInputConfig) -> str:
        """Erstellt aussagekräftigen Szenario-Namen."""
        parts = []
        
        if user_config.num_evs > 1:
            parts.append(f"{user_config.num_evs}×EV")
        
        if user_config.hp_failure:
            parts.append("HP-Off")
        
        if user_config.smart_energy_enabled:
            parts.append("SmartEnergy")
        
        if user_config.variable_prices_enabled:
            parts.append("VarPrice")
        
        return " | ".join(parts) if parts else "Basis-Szenario"
    
    @staticmethod
    def _build_description(user_config: UserInputConfig) -> str:
        """Erstellt ausführliche Beschreibung."""
        lines = []
        
        lines.append(f"E-Autos: {user_config.num_evs}")
        lines.append(f"Wärmepumpe AUS: {'Ja' if user_config.hp_failure else 'Nein'}")
        lines.append(f"Smart Energy: {'Ja' if user_config.smart_energy_enabled else 'Nein'}")
        
        if user_config.variable_prices_enabled:
            lines.append(f"Nacht-Tarif: {user_config.price_night_chf_per_kwh:.2f} CHF/kWh")
            lines.append(f"Tag-Tarif: {user_config.price_day_chf_per_kwh:.2f} CHF/kWh")
        
        return " | ".join(lines)
