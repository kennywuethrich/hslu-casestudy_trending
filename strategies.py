"""
Strategiemodul mit reinen Entscheidungsregeln.

Entwickler-Kurzinfo:
- Zweck: Definiert, wann die Brennstoffzelle eingesetzt werden darf.
- Inputs: Preis, Defizit, SOC, Saisoninformation.
- Outputs: should_use_fc-Entscheidung je Zeitschritt.
- Typische Änderungen: Regelwerte oder neue Strategieklassen.
"""

from abc import ABC, abstractmethod
import pandas as pd

from config import SystemConfig
from components import H2Storage
from dispatch import run_dispatch


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
        return run_dispatch(profile_df, self.config, self._should_use_fc)

    def _should_use_fc(self, price: float, shortage_kw: float, h2: H2Storage, day_of_year: int) -> bool:
        """
        FC-Einsatz für Heuristik:
        - oberhalb Reserve-Ziel ist FC grundsätzlich erlaubt,
        - darunter nur bei größeren Defiziten (Peak-Shaving).
        """
        del price, day_of_year
        if h2.available_discharge <= 0:
            return False

        soc_pct = h2.soc_kwh / h2.capacity if h2.capacity > 0 else 0.0
        reserve_target = max(self.config.fc_reserve_soc_target, self.config.h2_min_soc)

        if soc_pct > reserve_target:
            return True

        return shortage_kw >= self.config.fc_peak_shaving_kw


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
        return run_dispatch(profile_df, self.config, self._should_use_fc)

    def _should_use_fc(self, price: float, shortage_kw: float, h2: H2Storage, day_of_year: int) -> bool:
        """
        Aktiviert die Brennstoffzelle bei Defizit
        - wirtschaftlich (hoher Preis),
        - oder zur Eigenverbrauchserhöhung im Sommer bei gutem SOC,
        - oder für Peak-Shaving.
        """
        if h2.available_discharge <= 0:
            return False

        soc_pct = h2.soc_kwh / h2.capacity if h2.capacity > 0 else 0.0
        reserve_target = max(self.config.fc_reserve_soc_target, self.config.h2_min_soc)

        is_summer = 121 <= int(day_of_year) <= 273
        summer_self_use = is_summer and soc_pct > reserve_target

        return summer_self_use or (price > self.config.price_threshold_fc) or (shortage_kw >= self.config.fc_peak_shaving_kw)
