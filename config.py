"""
Konfigurationsmodul für H2-Microgrid Energiesystem Simulation.
Enthält alle Systemparameter und Konfigurationen.
"""

from dataclasses import dataclass


@dataclass
class SystemConfig:
    """
    Zentrale Konfigurationsklasse für alle Systemparameter.
    
    Anlagenkomponenten:
    - PV-Anlage: 87 kWp
    - Elektrolyseur: 33 kW
    - H2-Speicher: 85 m³ (~7650 kWh chemische Energie @ 30 bar)
    - Brennstoffzelle: 34 kW
    - Wärmepumpe: 95 kW (thermisch)
    - E-Auto: 40 kWh Batterie
    """
    
    # Anlagenleistungen [kW]
    pv_kwp: float = 87.0
    ely_kw_max: float = 33.0       # Elektrolyseur max. Leistung
    fc_kw_max: float = 34.0        # Brennstoffzelle max. Leistung
    hp_kw_th_max: float = 95.0     # Wärmepumpe max. thermische Leistung
    ev_battery_kwh: float = 40.0   # E-Auto Batteriekapazität

    # H2-Speicher
    # 85 m³ bei 30 bar → ~2550 Nm³. LHV H2 ≈ 3.0 kWh/Nm³ → ~7650 kWh
    h2_capacity_kwh: float = 7650.0
    h2_initial_soc: float = 0.3    # Anfangs-SOC (30%)
    h2_min_soc: float = 0.05       # Minimaler SOC (5% Reserve)

    # Wirkungsgrade
    ely_eff_el: float = 0.65       # Strom → H2 (chemisch)
    ely_eff_th: float = 0.20       # Strom → Abwärme
    fc_eff_el: float = 0.50        # H2 → Strom
    fc_eff_th: float = 0.30        # H2 → Abwärme
    hp_cop: float = 3.5            # Wärmepumpe COP

    # Preise & CO2
    price_buy_chf: float = 0.28    # Netzstrom [CHF/kWh]
    price_sell_chf: float = 0.10   # Einspeisevergütung [CHF/kWh]
    co2_grid_kg_kwh: float = 0.128 # Schweizer Netzmix CO2-Intensität [kg/kWh]

    # Preisbasierte Strategie: Schwellenwerte
    price_threshold_ely: float = 0.20  # ELY läuft wenn Preis < Schwellenwert
    price_threshold_fc: float = 0.30   # BZ liefert wenn Preis > Schwellenwert

    def __repr__(self):
        return (f"SystemConfig(PV={self.pv_kwp}kWp, ELY={self.ely_kw_max}kW, "
                f"FC={self.fc_kw_max}kW, HP={self.hp_kw_th_max}kW, "
                f"H2={self.h2_capacity_kwh}kWh, Price Buy={self.price_buy_chf} CHF/kWh)")


# Vordefinierte Konfigurationen für Szenarien
SCENARIOS = {
    'A_reference': SystemConfig(
        price_buy_chf=0.28,
        price_sell_chf=0.10,
    ),
    'B_high_price': SystemConfig(
        price_buy_chf=0.38,
        price_sell_chf=0.16,
        price_threshold_ely=0.28,
        price_threshold_fc=0.35,
    ),
    'C_workplace': SystemConfig(
        price_buy_chf=0.28,
        price_sell_chf=0.10,
    ),
}
