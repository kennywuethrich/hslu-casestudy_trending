"""
H2-Microgrid Energiesystem Simulation
=====================================

Ein objektorientiertes Simulation-Framework für Wasserstoff-Energiesysteme
mit PV-Erzeugung, Elektrolyseur, Brennstoffzelle und Wärmepumpe.

Komponenten:
- PV-Anlage (87 kWp)
- Elektrolyseur (33 kW)
- H2-Speicher (7650 kWh)
- Brennstoffzelle (34 kW)
- Wärmepumpe (95 kW thermisch)
- E-Auto (40 kWh Batterie)

Betriebsstrategien:
- Heuristische Eigenverbrauchsoptimierung
- Preisbasierte Steuerung

Schnelleinstieg:
    from main import run_scenario
    run_scenario('A_reference')
"""

__version__ = "1.0.0"
__author__ = "H2-Microgrid Team"

from .config import SystemConfig
from .components import H2Storage, Electrolyzer, FuelCell, HeatPump
from .profiles import ProfileGenerator
from .strategies import Strategy, HeuristicStrategy, PriceBasedStrategy
from .analyzer import ResultAnalyzer
from .scenario import Scenario, ScenarioManager, SCENARIOS_LIBRARY
from .simulator import Simulator
from .main import run_scenario, compare_all_scenarios

__all__ = [
    'SystemConfig',
    'H2Storage',
    'Electrolyzer',
    'FuelCell',
    'HeatPump',
    'ProfileGenerator',
    'Strategy',
    'HeuristicStrategy',
    'PriceBasedStrategy',
    'ResultAnalyzer',
    'Scenario',
    'ScenarioManager',
    'SCENARIOS_LIBRARY',
    'Simulator',
    'run_scenario',
    'compare_all_scenarios',
]
