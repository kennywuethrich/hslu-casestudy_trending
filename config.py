"""
Konfigurationsmodul für H2-Microgrid Energiesystem Simulation.
Enthält alle Systemparameter und Konfigurationen.
"""

from dataclasses import dataclass
from typing import ClassVar, Literal, Optional


@dataclass
class SystemConfig:
    """
    Zentrale Konfigurationsklasse für alle Systemparameter.
    
    Anlagenkomponenten:
    - Elektrolyseur: 33 kW
    - H2-Speicher: Parametriert über Volumen, Druck und Temperatur
    - Brennstoffzelle: 34 kW
    - Wärmepumpe: 95 kW (thermisch)
    """

    # Datengrundlage (zentraler Schalter)
    # - time_resolution steuert, welche CSV-Datei verwendet wird.
    #   1h -> stündliche Auswertung, 15min -> native viertelstündliche Auswertung.

    time_resolution: Literal['1h', '15min'] = '1h'
    data_dir: str = 'data'
    data_csv_1h: str = 'data_anna-heer_1h.csv'
    data_csv_15min: str = 'data_anna-heer_15min.csv'
    
    # Anlagenleistungen [kW]
    ely_kw_max: float = 33.0       # Elektrolyseur max. Leistung
    fc_kw_max: float = 34.0        # Brennstoffzelle max. Leistung
    hp_kw_th_max: float = 95.0     # Wärmepumpe max. thermische Leistung

    # H2-Speicher (editierbare physikalische Eingaben)
    # Druck als absoluter Druck [bar(abs)] angeben.
    h2_tank_volume_m3: float = 85.0
    h2_pressure_bar: float = 30.0
    h2_temperature_c: float = 15.0

    # Optional: Falls Messwerte vorliegen, kann Dichte oder Gesamtmasse direkt
    # überschrieben werden. Wenn beide None sind, wird aus idealem Gasgesetz gerechnet.
    h2_density_override_kg_m3: Optional[float] = None
    h2_total_mass_override_kg: Optional[float] = None

    # Chemischer Heizwert (LHV) zur Umrechnung Masse -> Energie
    h2_lhv_kwh_per_kg: float = 33.33

    # Legacy/optional: Direkte Überschreibung der berechneten H2-Kapazität
    h2_capacity_override_kwh: Optional[float] = None

    h2_initial_soc: float = 0.05   # Anfangs-SOC (5%) (State of Charge)
    h2_min_soc: float = 0.05       # Minimaler SOC (5% Reserve)

    # Thermischer Speicher zur WP-Lastverschiebung
    thermal_storage_capacity_kwh: float = 600.0
    thermal_initial_soc: float = 0.5

    # Wirkungsgrade
    ely_eff_el: float = 0.65       # Strom → H2 (chemisch)
    ely_eff_th: float = 0.20       # Strom → Abwärme
    fc_eff_el: float = 0.50        # H2 → Strom / "FC"->Fuel Cell
    fc_eff_th: float = 0.30        # H2 → Abwärme
    hp_cop: float = 3.5            # Wärmepumpe COP (Coefficient of Performance)

    # Preise & CO2
    price_buy_chf: float = 0.28    # Netzstrom [CHF/kWh]
    price_sell_chf: float = 0.10   # Einspeisevergütung [CHF/kWh]
    co2_grid_kg_kwh: float = 0.128 # Schweizer Netzmix CO2-Intensität [kg/kWh]

    # Preisbasierte Strategie: Schwellenwerte
    price_threshold_fc: float = 0.30   # BZ liefert wenn Preis > Schwellenwert

    # FC-Dispatch (beide Strategien)
    fc_reserve_soc_target: float = 0.35  # Höhere Reserve für saisonalen H2-Aufbau
    fc_peak_shaving_kw: float = 35.0     # FC vorrangig bei größeren Defiziten
    fc_dispatch_max_kw: float = 18.0     # Begrenzung der FC-Abgabe pro Zeitschritt

    # Konstanten für H2-Eigenschaften
    _H2_MOLAR_MASS_KG_PER_MOL: ClassVar[float] = 0.00201588
    _UNIVERSAL_GAS_CONSTANT_J_PER_MOLK: ClassVar[float] = 8.314462618

    def __post_init__(self):
        if self.h2_tank_volume_m3 <= 0:
            raise ValueError("h2_tank_volume_m3 muss > 0 sein.")
        if self.h2_pressure_bar <= 0:
            raise ValueError("h2_pressure_bar muss > 0 sein.")
        if self.h2_temperature_c <= -273.15:
            raise ValueError("h2_temperature_c muss > -273.15 sein.")
        if self.h2_lhv_kwh_per_kg <= 0:
            raise ValueError("h2_lhv_kwh_per_kg muss > 0 sein.")
        if self.h2_density_override_kg_m3 is not None and self.h2_density_override_kg_m3 <= 0:
            raise ValueError("h2_density_override_kg_m3 muss > 0 sein.")
        if self.h2_total_mass_override_kg is not None and self.h2_total_mass_override_kg <= 0:
            raise ValueError("h2_total_mass_override_kg muss > 0 sein.")
        if self.h2_capacity_override_kwh is not None and self.h2_capacity_override_kwh <= 0:
            raise ValueError("h2_capacity_override_kwh muss > 0 sein.")
        if self.fc_dispatch_max_kw <= 0:
            raise ValueError("fc_dispatch_max_kw muss > 0 sein.")
        if self.fc_dispatch_max_kw > self.fc_kw_max:
            raise ValueError("fc_dispatch_max_kw darf fc_kw_max nicht überschreiten.")


    # Berechnung der H2-Eigenschaften basierend auf den Eingabeparametern
    
    @property
    def h2_temperature_k(self) -> float:
        return self.h2_temperature_c + 273.15

    @property
    def h2_density_kg_m3(self) -> float:
        """
        H2-Dichte [kg/m³].
        - Mit Override: direkter Mess-/Tabellenwert.
        - Ohne Override: ideale Gasgleichung rho = p*M/(R*T).
        """
        if self.h2_density_override_kg_m3 is not None:
            return self.h2_density_override_kg_m3

        pressure_pa = self.h2_pressure_bar * 100000.0
        return (
            pressure_pa * self._H2_MOLAR_MASS_KG_PER_MOL /
            (self._UNIVERSAL_GAS_CONSTANT_J_PER_MOLK * self.h2_temperature_k)
        )

    @property
    def h2_total_mass_kg(self) -> float:
        """Gesamtmasse H2 im Tank [kg]."""
        if self.h2_total_mass_override_kg is not None:
            return self.h2_total_mass_override_kg
        return self.h2_density_kg_m3 * self.h2_tank_volume_m3

    @property
    def h2_capacity_kwh(self) -> float:
        """Chemische H2-Energie im Tank [kWh] (LHV-basiert)."""
        if self.h2_capacity_override_kwh is not None:
            return self.h2_capacity_override_kwh
        return self.h2_total_mass_kg * self.h2_lhv_kwh_per_kg

    def __repr__(self):
        return (f"SystemConfig(ELY={self.ely_kw_max}kW, "
                f"FC={self.fc_kw_max}kW, HP={self.hp_kw_th_max}kW, "
                f"H2={self.h2_capacity_kwh:.1f}kWh, "
                f"V={self.h2_tank_volume_m3}m3, p={self.h2_pressure_bar}bar, T={self.h2_temperature_c}C, "
                f"Price Buy={self.price_buy_chf} CHF/kWh, "
                f"Resolution={self.time_resolution})")
