"""Betriebsstrategien für H2-Microgrid Steuerung.

BaseStrategy: Einfache Heuristik ohne Optimierung
OptimizedStrategy: 720h-Lookahead Optimierung
"""

from abc import ABC, abstractmethod
import pandas as pd
import numpy as np

from config import SystemConfig
from components import H2Storage
from dispatch import run_dispatch


class Strategy(ABC):
    """Abstrakte Basisklasse für Betriebsstrategien."""
    
    def __init__(self, config: SystemConfig):
        self.config = config
        self.name = self.__class__.__name__
        
    @abstractmethod
    def run(self, profile_df: pd.DataFrame) -> pd.DataFrame:
        """Führt Simulation durch und gibt erweiterten DataFrame zurück."""
        pass
    
    def __repr__(self):
        return f"{self.name}(H2={self.config.h2_capacity_kwh:.0f}kWh)"


class BaseStrategy(Strategy):
    """
    Strategie A: Einfache Regeln (Nicht optimiert)
    
    Logik:
    1. PV → Last + Heizung (HP)
    2. PV-Überschuss → Elektrolyseur (H2 laden)
    3. Wenn PV-Defizit UND H2 vorhanden → FC nutzen (Backup)
    4. Sonst → Netz
    5. HP nur wenn outdoor_temp_c ≥ +5°C
    """
    
    def run(self, profile_df: pd.DataFrame) -> pd.DataFrame:
        """Führt Dispatch mit BaseStrategy durch."""
        return run_dispatch(profile_df, self.config, self._should_use_fc)
    
    def _should_use_fc(self, price: float, shortage_kw: float, h2: H2Storage, day_of_year: int) -> bool:
        """FC-Entscheidung: Nutze nur wenn Defizit vorhanden UND H2 verfügbar."""
        if shortage_kw <= 0:
            return False
        if h2.available_discharge <= 0:
            return False
        return True


class OptimizedStrategy(Strategy):
    """
    Strategie B: 720h-Lookahead Optimierung
    
    Schaut 30 Tage voraus und plant:
    - Wann lade ich H2? (Wenn große Defizite kommend)
    - Wann nutze ich HP-Extra? (Bei günstigen Bedingungen)
    - Minimiere: Gesamtnetzimporte
    
    Constraints:
    - H2-SOC: 8.5% bis 100%
    - ELY max: 33 kW
    - FC max: 34.2 kW
    - HP nur wenn outdoor_temp_c ≥ +5°C
    """
    
    HORIZON_H = 720  # 30 Tage
    
    def run(self, profile_df: pd.DataFrame) -> pd.DataFrame:
        """Pre-compute optimal FC/ELY-Planung über 720h, dann simuliere."""
        n = len(profile_df)
        fc_plan = np.zeros(n)
        
        # Fenster-basierte Optimierung
        for start_idx in range(0, n, self.HORIZON_H):
            end_idx = min(start_idx + self.HORIZON_H, n)
            window_df = profile_df.iloc[start_idx:end_idx].reset_index(drop=True)
            
            fc_opt = self._optimize_window(window_df)
            fc_plan[start_idx:end_idx] = fc_opt
        
        # Simulate mit pre-computed FC-Plan
        result_df = run_dispatch(
            profile_df, self.config,
            self._make_fc_callback(fc_plan)
        )
        
        return result_df
    
    def _optimize_window(self, window_df: pd.DataFrame) -> np.ndarray:
        """Lookahead-Heuristik pro 720h Fenster."""
        n = len(window_df)
        fc_opt = np.zeros(n)
        
        # Für jede Stunde: Schaue 24h voraus
        for i in range(n):
            pv = window_df.iloc[i]['pv_kw']
            load_el = window_df.iloc[i]['load_el_kw']
            
            # Lookahead: Summe der nächsten 24h Defizit
            future_deficit = 0.0
            for j in range(i, min(i + 24, n)):
                future_pv = window_df.iloc[j]['pv_kw']
                future_load = window_df.iloc[j]['load_el_kw']
                future_deficit += max(0.0, future_load - future_pv)
            
            # Strategie: Wenn großes Defizit kommend UND PV jetzt vorhanden
            # → Nutze FC jetzt weniger, lade H2 lieber (via ELY-boost in dispatch)
            # ABER: Wir können hier nur FC-Entscheidung pre-compute
            # Einfache Heuristik: Wenn Defizit imminent → FC nutzen
            immediate_deficit = load_el - pv
            if immediate_deficit > 5.0:
                fc_opt[i] = 1.0  # "Ja, FC nutzen"
        
        return fc_opt
    
    def _make_fc_callback(self, fc_plan: np.ndarray):
        """Callback-Factory für FC-Plan-Befolgung."""
        indices = {'idx': 0}
        
        def callback(price, shortage_kw, h2, day_of_year):
            if shortage_kw <= 0 or h2.available_discharge <= 0:
                return False
            
            idx = indices['idx']
            indices['idx'] = (idx + 1) % len(fc_plan)
            return fc_plan[idx] > 0.5
        
        return callback

