"""Zentrale Systemparameter für die Simulation."""

from dataclasses import dataclass
from typing import ClassVar, Literal, Optional


@dataclass
class SystemConfig:
    """Alle Systemparameter an einem Ort."""

    # Daten
    data_dir: str = 'data'
    data_csv: str = 'data_anna-heer_1h.csv'

    # Leistungen [kW]
    ely_kw_max: float = 33.0 # (Factsheet H2 S2)
    fc_kw_max: float = 34.2 # (Factsheet H2 S2)
    hp_kw_th_max: float = 95.0

    # H2-Speicher
    h2_tank_volume_m3: float = 85.0
    h2_pressure_bar: float = 35.0           # (von 3.5 bis max 35 bar)
    h2_temperature_c: float = 15.0
    h2_density_override_kg_m3: Optional[float] = 2.94 # (bei 35 bar und 15°C, sonst Berechnung über ideale Gasgleichung)
    h2_total_mass_override_kg: Optional[float] = 250.0 # (bei 35 bar und 15°C)
    h2_lhv_kwh_per_kg: float = 33.33
    h2_capacity_override_kwh: Optional[float] = 8325.5 # (Fachtsheet H2)



    h2_initial_soc: float = 0.05
    h2_min_soc: float = 0.085

    # Thermischer Speicher
    thermal_storage_capacity_kwh: float = 600.0
    thermal_initial_soc: float = 0.5

    # Wirkungsgrade
    ely_eff_el: float = 0.538
    ely_eff_th: float = 0.20
    fc_eff_el: float = 0.449
    fc_eff_th: float = 0.508
    hp_cop: float = 2.67 #(Netto COP mit H2 excel pilotprojekt)

    # Preise und Regeln mit API? bei EKZ (Zürich)
    price_buy_chf: float = 0.28
    price_sell_chf: float = 0.10
    co2_grid_kg_kwh: float = 0.128
    price_threshold_fc: float = 0.30
    fc_reserve_soc_target: float = 0.35
    fc_peak_shaving_kw: float = 37.4
    fc_dispatch_max_kw: float = 18.0

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
        if self.h2_density_override_kg_m3 is not None:
            return self.h2_density_override_kg_m3

        pressure_pa = self.h2_pressure_bar * 100000.0
        return (
            pressure_pa * self._H2_MOLAR_MASS_KG_PER_MOL /
            (self._UNIVERSAL_GAS_CONSTANT_J_PER_MOLK * self.h2_temperature_k)
        )

    @property
    def h2_total_mass_kg(self) -> float:
        if self.h2_total_mass_override_kg is not None:
            return self.h2_total_mass_override_kg
        return self.h2_density_kg_m3 * self.h2_tank_volume_m3

    @property
    def h2_capacity_kwh(self) -> float:
        if self.h2_capacity_override_kwh is not None:
            return self.h2_capacity_override_kwh
        return self.h2_total_mass_kg * self.h2_lhv_kwh_per_kg

    @property
    def dt_h(self) -> float:
        return 1.0

    def horizon_steps(self, horizon_h: int) -> int:
        return max(1, int(round(float(horizon_h))))

    def __repr__(self):
        return (f"SystemConfig(ELY={self.ely_kw_max}kW, "
                f"FC={self.fc_kw_max}kW, HP={self.hp_kw_th_max}kW, "
                f"H2={self.h2_capacity_kwh:.1f}kWh, "
                f"V={self.h2_tank_volume_m3}m3, p={self.h2_pressure_bar}bar, T={self.h2_temperature_c}C, "
                f"Price Buy={self.price_buy_chf} CHF/kWh)")
