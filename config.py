"""Zentrale Systemparameter für die Simulation."""

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, Optional
import requests


@dataclass
class SystemConfig:
    """Alle Systemparameter an einem Ort."""

    # --- Datenpfad -------------------------------------------------------
    data_dir: str = "data"
    data_csv: str = "data_anna-heer_1h.csv"

    # --- Komponenten: Leistungsgrenzen [kW] ------------------------------
    ely_kw_max: float = 33.0  # Elektrolyseur max. Eingangsleistung (Factsheet H2 S2)
    fc_kw_max: float = 34.2  # Brennstoffzelle max. Ausgangsleistung (Factsheet H2 S2)
    hp_kw_th_max: float = 95.0  # Wärmepumpe max. thermische Leistung

    # --- H₂-Speicher: Tank-Physik ----------------------------------------
    h2_tank_volume_m3: float = 85.0  # Tankvolumen [m³]
    h2_pressure_bar: float = 35.0  # Betriebsdruck [bar] (3.5–35 bar)
    h2_temperature_c: float = 15.0  # Tanktemperatur [°C]
    h2_density_override_kg_m3: Optional[float] = 2.94  # Dichte bei 35 bar, 15°C [kg/m³]
    h2_total_mass_override_kg: Optional[float] = (
        250.0  # Gesamtmasse bei 35 bar, 15°C [kg]
    )
    h2_lhv_kwh_per_kg: float = 33.33  # Unterer Heizwert H₂ [kWh/kg]
    h2_capacity_override_kwh: Optional[float] = (
        8325.5  # Energieinhalt (Factsheet H2) [kWh]
    )
    h2_initial_soc: float = 0.05  # Anfangsfüllstand [0–1]
    h2_min_soc: float = 0.085  # Minimaler Füllstand [0–1]

    # --- Thermischer Speicher --------------------------------------------
    thermal_storage_capacity_kwh: float = 600.0  # Kapazität [kWh_th]
    thermal_initial_soc: float = 0.5  # Anfangsfüllstand [0–1]

    # --- Wirkungsgrade ---------------------------------------------------
    ely_eff_el: float = 0.538  # Elektrolyseur: Strom → H₂
    ely_eff_th: float = 0.20  # Elektrolyseur: Strom → Abwärme
    fc_eff_el: float = 0.449  # Brennstoffzelle: H₂ → Strom
    fc_eff_th: float = 0.508  # Brennstoffzelle: H₂ → Abwärme
    hp_cop: float = 2.67  # Wärmepumpe COP (Netto, Pilotprojekt)

    # --- EV --------------------------------------------------------------
    ev_capacity_kwh: float = 60.0  # Batteriekapazität [kWh]
    ev_charge_max_kw: float = 11.0  # Maximale Ladeleistung [kW]
    ev_charge_efficiency: float = 0.92  # Lade-Wirkungsgrad [-]

    # --- Gebäude: RC-Modell (Thermik) ------------------------------------
    C_th_kwh_per_K: float = 50.0  # Thermische Kapazität Gebäude [kWh/K]
    UA_kwh_per_K: float = 2.5  # Wärmedurchgangskoeffizient × Fläche [kWh/(K·h)]
    solar_gain_factor: float = 0.05  # Solare Gewinne als Anteil der PV-Leistung [-]

    # --- Betriebsregeln und Preise ---------------------------------------
    price_buy_chf: float = (
        0.28  # Stromkaufpreis [CHF/kWh] (wird ggf. per API überschrieben)
    )
    price_sell_chf: float = 0.10  # Stromverkaufspreis [CHF/kWh]
    co2_grid_kg_kwh: float = 0.128  # CO₂-Intensität Netzstrom [kg/kWh]
    price_threshold_fc: float = 0.30  # FC-Trigger: Preis über diesem Wert [CHF/kWh]
    price_threshold_cheap: float = (
        0.20  # Günstiger Strom: Ely bei Preis darunter [CHF/kWh]
    )
    fc_reserve_soc_target: float = 0.35  # FC proaktiv entladen wenn H₂-SOC darüber
    fc_peak_shaving_kw: float = 37.4  # Peak-Shaving-Grenze [kW]
    fc_dispatch_max_kw: float = 18.0  # Maximale FC-Einsatzleistung [kW]

    # --- Physikalische Konstanten (unveränderlich) -----------------------
    _H2_MOLAR_MASS_KG_PER_MOL: ClassVar[float] = 0.00201588
    _UNIVERSAL_GAS_CONSTANT_J_PER_MOLK: ClassVar[float] = 8.314462618

    def __post_init__(self):
        # Plausibilitätsprüfungen
        assert self.h2_tank_volume_m3 > 0, "h2_tank_volume_m3 muss > 0 sein"
        assert self.h2_pressure_bar > 0, "h2_pressure_bar muss > 0 sein"
        assert self.h2_temperature_c > -273.15, "h2_temperature_c muss > -273.15 sein"
        assert self.h2_lhv_kwh_per_kg > 0, "h2_lhv_kwh_per_kg muss > 0 sein"
        assert self.fc_dispatch_max_kw > 0, "fc_dispatch_max_kw muss > 0 sein"
        assert (
            self.fc_dispatch_max_kw <= self.fc_kw_max
        ), "fc_dispatch_max_kw darf fc_kw_max nicht überschreiten"

        # Aktuellen Strompreis von EKZ Zürich API abrufen
        self._fetch_price_from_api()

    # --- H₂-Speicher: abgeleitete Eigenschaften --------------------------

    @property
    def h2_temperature_k(self) -> float:
        """Tanktemperatur in Kelvin."""
        return self.h2_temperature_c + 273.15

    @property
    def h2_density_kg_m3(self) -> float:
        """H₂-Dichte im Tank [kg/m³] — Override oder ideales Gasgesetz."""
        if self.h2_density_override_kg_m3 is not None:
            return self.h2_density_override_kg_m3
        pressure_pa = self.h2_pressure_bar * 100_000.0
        return (
            pressure_pa
            * self._H2_MOLAR_MASS_KG_PER_MOL
            / (self._UNIVERSAL_GAS_CONSTANT_J_PER_MOLK * self.h2_temperature_k)
        )

    @property
    def h2_total_mass_kg(self) -> float:
        """Maximale H₂-Masse im Tank [kg]."""
        if self.h2_total_mass_override_kg is not None:
            return self.h2_total_mass_override_kg
        return self.h2_density_kg_m3 * self.h2_tank_volume_m3

    @property
    def h2_capacity_kwh(self) -> float:
        """Energieinhalt des H₂-Tanks bei Vollbefüllung [kWh]."""
        if self.h2_capacity_override_kwh is not None:
            return self.h2_capacity_override_kwh
        return self.h2_total_mass_kg * self.h2_lhv_kwh_per_kg

    @property
    def dt_h(self) -> float:
        """Zeitschrittlänge [h]."""
        return 1.0

    # --- EKZ Zürich API: aktueller Strompreis ----------------------------

    def _fetch_price_from_api(self):
        """Ruft aktuellen Kombitarif von EKZ Zürich API ab (optional)."""
        try:
            url = "https://data.stadt-zuerich.ch/api/3/action/datastore_search"
            params = {
                "resource_id": "19d90084-6f06-45f2-95bb-9d2ffe7b62a2",
                "limit": 100,
            }
            response = requests.get(url, params=params, timeout=5)
            data = response.json()

            current_hour = datetime.now().hour
            matching_record = None

            for record in data["result"]["records"]:
                ts = record.get("TimestampStartCet", "")
                try:
                    ts_dt = datetime.fromisoformat(
                        ts.replace("+01:00", "").replace("+02:00", "")
                    )
                    if ts_dt.hour == current_hour:
                        matching_record = record
                        break
                except Exception:
                    continue

            # Fallback: ersten verfügbaren Record nehmen
            if not matching_record and data["result"]["records"]:
                matching_record = data["result"]["records"][0]

            if matching_record:
                kombitarif = matching_record.get("KombitarifRpkWh")
                if kombitarif is not None:
                    self.price_buy_chf = float(kombitarif) / 100.0  # Rappen → CHF
                    print(
                        f"API: Strompreis aktualisiert auf {self.price_buy_chf:.4f} CHF/kWh"
                    )

        except Exception as e:
            print(f"Hinweis: EKZ-API nicht erreichbar ({e}), verwende Standardpreis.")

    def __repr__(self):
        return (
            f"SystemConfig("
            f"ELY={self.ely_kw_max}kW, FC={self.fc_kw_max}kW, HP={self.hp_kw_th_max}kW, "
            f"H2={self.h2_capacity_kwh:.0f}kWh @ {self.h2_pressure_bar}bar, "
            f"Preis={self.price_buy_chf:.3f} CHF/kWh)"
        )
