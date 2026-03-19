"""
=============================================================================
H2-Microgrid Energiesystem Simulation
Wohnkomplex mit PV, Elektrolyseur, Brennstoffzelle, H2-Speicher, Wärmepumpe
=============================================================================
Komponenten:
  - PV-Anlage:        87 kWp
  - Elektrolyseur:    33 kW
  - H2-Speicher:      85 m³ (~7650 kWh chemische Energie @ 30 bar)
  - Brennstoffzelle:  34 kW
  - Wärmepumpe:       95 kW (thermisch)
  - E-Auto:           40 kWh Batterie

Betriebsstrategien:
  1. Heuristik (Eigenverbrauchsoptimierung)
  2. Preisbasierte Steuerung

Szenarien:
  A. Referenz (moderate Preise, Abend-Laden E-Auto)
  B. Hoher Strompreis + höhere Einspeisevergütung
  C. Tagsüber-Laden E-Auto (Workplace Charging)
=============================================================================
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from dataclasses import dataclass, field
from typing import Optional


# =============================================================================
# 1. SYSTEM-PARAMETER (dataclass für saubere Konfiguration)
# =============================================================================

@dataclass
class SystemConfig:
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


# =============================================================================
# 2. KOMPONENTEN-KLASSEN
# =============================================================================

class H2Storage:
    """Wasserstoffspeicher mit SOC-Tracking"""
    def __init__(self, config: SystemConfig):
        self.capacity = config.h2_capacity_kwh
        self.soc_kwh = config.h2_initial_soc * self.capacity
        self.min_soc_kwh = config.h2_min_soc * self.capacity

    @property
    def soc_pct(self):
        return self.soc_kwh / self.capacity

    def charge(self, energy_kwh: float) -> float:
        """Lädt Speicher. Gibt tatsächlich gespeicherte Energie zurück."""
        space = self.capacity - self.soc_kwh
        actual = min(energy_kwh, space)
        self.soc_kwh += actual
        return actual

    def discharge(self, energy_kwh: float) -> float:
        """Entlädt Speicher. Gibt tatsächlich entnommene Energie zurück."""
        available = max(0.0, self.soc_kwh - self.min_soc_kwh)
        actual = min(energy_kwh, available)
        self.soc_kwh -= actual
        return actual


class Electrolyzer:
    """
    Elektrolyseur: Wandelt Strom in H2 (chemische Energie) + Abwärme.
    Minimale Teillast: 10% der Nennleistung (realistisch für PEM-ELY).
    """
    def __init__(self, config: SystemConfig):
        self.p_max = config.ely_kw_max
        self.p_min = 0.1 * config.ely_kw_max  # 10% Mindestlast
        self.eff_el = config.ely_eff_el
        self.eff_th = config.ely_eff_th

    def run(self, power_available: float) -> dict:
        """
        Läuft mit verfügbarer Leistung (begrenzt durch p_min und p_max).
        Gibt H2-Produktion und Abwärme zurück.
        """
        # Wenn zu wenig Leistung für Mindestlast → ELY aus
        if power_available < self.p_min:
            return {'power_used': 0.0, 'h2_produced': 0.0, 'heat_produced': 0.0}

        power_used = min(power_available, self.p_max)
        h2_produced = power_used * self.eff_el
        heat_produced = power_used * self.eff_th
        return {
            'power_used': power_used,
            'h2_produced': h2_produced,
            'heat_produced': heat_produced
        }


class FuelCell:
    """
    Brennstoffzelle: Wandelt H2 in Strom + Abwärme.
    Minimale Teillast: 10% der Nennleistung.
    """
    def __init__(self, config: SystemConfig):
        self.p_max = config.fc_kw_max
        self.p_min = 0.1 * config.fc_kw_max
        self.eff_el = config.fc_eff_el
        self.eff_th = config.fc_eff_th

    def run(self, power_needed: float, h2_available: float) -> dict:
        """
        Erzeugt Strom aus H2. Begrenzt durch Leistung und H2-Verfügbarkeit.
        """
        # Maximale BZ-Leistung und H2-Limitierung
        power_target = min(power_needed, self.p_max)
        h2_needed = power_target / self.eff_el
        h2_used = min(h2_needed, h2_available)
        power_out = h2_used * self.eff_el

        # Mindestlast-Check
        if power_out < self.p_min:
            return {'power_out': 0.0, 'h2_used': 0.0, 'heat_produced': 0.0}

        heat_produced = h2_used * self.eff_th
        return {
            'power_out': power_out,
            'h2_used': h2_used,
            'heat_produced': heat_produced
        }


class HeatPump:
    """Wärmepumpe mit konstantem COP."""
    def __init__(self, config: SystemConfig):
        self.cop = config.hp_cop
        self.p_th_max = config.hp_kw_th_max

    def cover_heat_demand(self, heat_demand: float, el_available: float) -> dict:
        """
        Deckt Wärmebedarf. Begrenzt durch thermische Nennleistung
        und verfügbare elektrische Leistung.
        """
        heat_possible_by_power = el_available * self.cop
        heat_possible = min(heat_demand, self.p_th_max, heat_possible_by_power)
        el_used = heat_possible / self.cop
        return {
            'heat_out': heat_possible,
            'el_used': el_used,
            'heat_unmet': heat_demand - heat_possible
        }


# =============================================================================
# 3. LASTPROFILE GENERIEREN (Dummy-Profile, ersetzbar durch echte CSVs)
# =============================================================================

def generate_profiles(hours: int = 8760, seed: int = 42,
                      ev_mode: str = 'evening') -> pd.DataFrame:
    """
    Generiert synthetische Lastprofile für 1 Jahr.
    ev_mode: 'evening' | 'daytime' | 'workplace'
    """
    np.random.seed(seed)
    t = np.arange(hours)
    hour_of_day = t % 24
    day_of_year = t // 24

    # --- PV-Profil (87 kWp): Tag/Nacht + Saisonalität ---
    # Tageslänge variiert zwischen ~8h (Winter) und ~16h (Sommer)
    sunrise = 6 - 2 * np.cos(2 * np.pi * day_of_year / 365)   # 4-8 Uhr
    sunset  = 18 + 2 * np.cos(2 * np.pi * day_of_year / 365)  # 16-20 Uhr
    day_length = sunset - sunrise

    # Sinus-Kurve für PV-Leistung innerhalb des Tages
    sun_angle = np.clip((hour_of_day - sunrise) / day_length, 0, 1)
    pv_norm = np.sin(sun_angle * np.pi) ** 1.5  # Leicht abgeflacht

    # Saisonale Skalierung (Sommer: 100%, Winter: 30%)
    seasonal = 0.65 + 0.35 * np.sin(2 * np.pi * (day_of_year - 80) / 365)

    # Zufällige Bewölkung (±20%)
    clouds = np.random.uniform(0.7, 1.0, hours)
    pv = 87.0 * pv_norm * seasonal * clouds
    pv = np.clip(pv, 0, 87.0)

    # --- Stromlastprofil Wohnkomplex (ohne WP & E-Auto) ---
    # Morgen- und Abendspitze
    morning_peak = np.exp(-0.5 * ((hour_of_day - 7.5) / 1.5) ** 2)
    evening_peak = np.exp(-0.5 * ((hour_of_day - 19.0) / 2.0) ** 2)
    base_load = 8.0
    load_el = base_load + 15 * morning_peak + 18 * evening_peak
    load_el += np.random.normal(0, 1.5, hours)  # Rauschen
    load_el = np.clip(load_el, 5.0, 50.0)

    # --- Wärmelastprofil ---
    # Heizbedarf: Saisonal (Winter hoch, Sommer niedrig) + Warmwasser-Spitzen
    seasonal_heat = 40 + 40 * np.cos(2 * np.pi * (day_of_year - 15) / 365)
    warmwater = 8 * (np.exp(-0.5 * ((hour_of_day - 7) / 1.0) ** 2)
                    + 0.5 * np.exp(-0.5 * ((hour_of_day - 20) / 1.0) ** 2))
    seasonal_heat = np.clip(seasonal_heat, 5.0, 80.0)
    load_heat = seasonal_heat + warmwater + np.random.normal(0, 2.0, hours)
    load_heat = np.clip(load_heat, 5.0, 95.0)

    # --- E-Auto Profil ---
    ev_demand = np.zeros(hours)
    if ev_mode == 'evening':
        # Lädt von 18-22 Uhr (4h × 7.4 kW = ~30 kWh/Tag)
        ev_demand = np.where((hour_of_day >= 18) & (hour_of_day < 22), 7.4, 0.0)
    elif ev_mode == 'daytime':
        # Lädt von 10-14 Uhr (tagsüber, PV-optimiert)
        ev_demand = np.where((hour_of_day >= 10) & (hour_of_day < 14), 7.4, 0.0)
    elif ev_mode == 'workplace':
        # Lädt nur an Werktagen von 8-17 Uhr
        day_of_week = (day_of_year % 7)  # Vereinfacht
        is_workday = day_of_week < 5
        ev_demand = np.where(
            is_workday & (hour_of_day >= 8) & (hour_of_day < 17), 3.3, 0.0)

    # --- Dynamischer Strompreis (Schweiz, vereinfacht) ---
    # Hochtarif Tag (7-21 Uhr), Niedertarif Nacht
    price_buy = np.where((hour_of_day >= 7) & (hour_of_day < 21), 0.30, 0.22)
    price_buy += np.random.normal(0, 0.01, hours)  # Kleines Rauschen

    # --- CO2-Intensität (saisonal: Sommer mehr Solar im Netz → weniger CO2) ---
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
        'price_sell': 0.10,       # Feste Einspeisevergütung
        'co2_intensity': co2_intensity
    })
    return df


# =============================================================================
# 4. BETRIEBSSTRATEGIEN
# =============================================================================

def strategy_heuristic(df: pd.DataFrame, config: SystemConfig) -> pd.DataFrame:
    """
    Strategie 1: Eigenverbrauchsoptimierung (Heuristik)
    Priorität: PV → Last → ELY (Überschuss) → Netz
               Defizit: BZ → Netz
    Wärme: WP deckt Bedarf; Abwärme von ELY/BZ wird angerechnet.
    """
    h2 = H2Storage(config)
    ely = Electrolyzer(config)
    fc = FuelCell(config)
    hp = HeatPump(config)

    results = []

    for _, row in df.iterrows():
        pv = row['pv_kw']
        load_el = row['load_el_kw'] + row['ev_demand_kw']
        load_heat = row['load_heat_kw']

        # --- Schritt 1: Wärme ---
        # Zuerst: Abwärme aus BZ/ELY vom letzten Schritt ist hier vereinfacht
        # synchron. Wir berechnen Wärme nach Strom (iterativ wäre exakter).
        # Wärmepumpe deckt Wärmebedarf (Strom dafür kommt aus PV/Netz)
        hp_el_needed = load_heat / hp.cop
        hp_el_needed = min(hp_el_needed, config.hp_kw_th_max / hp.cop)

        # --- Schritt 2: Strombilanz ---
        total_el_demand = load_el + hp_el_needed
        net_el = pv - total_el_demand

        grid_import = 0.0
        grid_export = 0.0
        ely_power = 0.0
        fc_power = 0.0
        h2_prod = 0.0
        heat_from_ely = 0.0
        heat_from_fc = 0.0

        if net_el >= 0:
            # Überschuss → Elektrolyseur
            ely_result = ely.run(net_el)
            ely_power = ely_result['power_used']
            h2_prod = ely_result['h2_produced']
            heat_from_ely = ely_result['heat_produced']

            # H2 in Tank
            h2_stored = h2.charge(h2_prod)
            # Wenn Tank voll → Rest-Überschuss ins Netz
            if h2_prod > 0:
                unused_ely_power = ely_power * (1 - h2_stored / h2_prod) if h2_prod > 0 else 0
            else:
                unused_ely_power = 0.0

            grid_export = (net_el - ely_power) + unused_ely_power
            grid_export = max(0.0, grid_export)

        else:
            # Defizit → Brennstoffzelle
            shortage = abs(net_el)
            fc_result = fc.run(shortage, h2.soc_kwh)
            fc_power = fc_result['power_out']
            h2_used = fc_result['h2_used']
            heat_from_fc = fc_result['heat_produced']

            # H2 aus Tank entnehmen
            h2.discharge(h2_used)

            # Verbleibendes Defizit → Netz
            grid_import = max(0.0, shortage - fc_power)

        # --- Schritt 3: Abwärme-Korrektur ---
        # Abwärme von ELY und BZ reduziert den Strombedarf der WP
        total_waste_heat = heat_from_ely + heat_from_fc
        heat_covered_by_waste = min(total_waste_heat, load_heat)
        remaining_heat_demand = load_heat - heat_covered_by_waste
        # Angepasster WP-Strombedarf
        hp_el_actual = remaining_heat_demand / hp.cop

        # Korrekturbuchung: Wenn WP weniger Strom braucht, geht der Überschuss
        # ins Netz oder spart Netzbezug
        hp_el_saved = hp_el_needed - hp_el_actual
        if grid_import > 0:
            grid_import = max(0.0, grid_import - hp_el_saved)
        else:
            grid_export += hp_el_saved

        results.append({
            'grid_import_kw': grid_import,
            'grid_export_kw': grid_export,
            'ely_power_kw': ely_power,
            'fc_power_kw': fc_power,
            'h2_soc_kwh': h2.soc_kwh,
            'hp_el_kw': hp_el_actual,
            'heat_from_waste_kw': heat_covered_by_waste,
        })

    return pd.concat([df.reset_index(drop=True),
                      pd.DataFrame(results)], axis=1)


def strategy_price_based(df: pd.DataFrame, config: SystemConfig) -> pd.DataFrame:
    """
    Strategie 2: Preisbasierte Steuerung
    - ELY läuft nur wenn Strompreis UNTER Schwellenwert (günstig produzieren)
    - BZ liefert bevorzugt wenn Strompreis ÜBER Schwellenwert (teuer = BZ wirtschaftlich)
    - E-Auto lädt bevorzugt bei günstigem Preis (wenn vorhanden)
    """
    h2 = H2Storage(config)
    ely = Electrolyzer(config)
    fc = FuelCell(config)
    hp = HeatPump(config)

    results = []

    for _, row in df.iterrows():
        pv = row['pv_kw']
        price = row['price_buy']
        load_el = row['load_el_kw'] + row['ev_demand_kw']
        load_heat = row['load_heat_kw']

        hp_el_needed = min(load_heat / hp.cop, config.hp_kw_th_max / hp.cop)
        total_el_demand = load_el + hp_el_needed
        net_el = pv - total_el_demand

        grid_import = 0.0
        grid_export = 0.0
        ely_power = 0.0
        fc_power = 0.0
        heat_from_ely = 0.0
        heat_from_fc = 0.0

        if net_el >= 0:
            # Überschuss → ELY nur wenn Preis günstig ODER viel Überschuss
            if price < config.price_threshold_ely or net_el > 10.0:
                ely_result = ely.run(net_el)
                ely_power = ely_result['power_used']
                h2_prod = ely_result['h2_produced']
                heat_from_ely = ely_result['heat_produced']
                h2.charge(h2_prod)
                grid_export = max(0.0, net_el - ely_power)
            else:
                # Direkteinspeisung (wenn Preis hoch und Überschuss)
                grid_export = net_el

        else:
            shortage = abs(net_el)
            # BZ bevorzugt bei hohem Strompreis
            if price > config.price_threshold_fc and h2.soc_kwh > h2.min_soc_kwh:
                fc_result = fc.run(shortage, h2.soc_kwh)
                fc_power = fc_result['power_out']
                h2_used = fc_result['h2_used']
                heat_from_fc = fc_result['heat_produced']
                h2.discharge(h2_used)
                grid_import = max(0.0, shortage - fc_power)
            else:
                # Direkt aus Netz (wenn Preis günstig → H2 sparen)
                grid_import = shortage

        # Abwärme-Korrektur (identisch zur Heuristik)
        total_waste_heat = heat_from_ely + heat_from_fc
        heat_covered_by_waste = min(total_waste_heat, load_heat)
        remaining_heat_demand = load_heat - heat_covered_by_waste
        hp_el_actual = remaining_heat_demand / hp.cop
        hp_el_saved = hp_el_needed - hp_el_actual

        if grid_import > 0:
            grid_import = max(0.0, grid_import - hp_el_saved)
        else:
            grid_export += hp_el_saved

        results.append({
            'grid_import_kw': grid_import,
            'grid_export_kw': grid_export,
            'ely_power_kw': ely_power,
            'fc_power_kw': fc_power,
            'h2_soc_kwh': h2.soc_kwh,
            'hp_el_kw': hp_el_actual,
            'heat_from_waste_kw': heat_covered_by_waste,
        })

    return pd.concat([df.reset_index(drop=True),
                      pd.DataFrame(results)], axis=1)


# =============================================================================
# 5. KPI-BERECHNUNG (inkl. korrektem MAC)
# =============================================================================

def calculate_kpis(result_df: pd.DataFrame,
                   config: SystemConfig,
                   label: str = "") -> dict:
    """
    Berechnet alle geforderten KPIs.
    Referenzfall für MAC: Alles aus dem Netz (kein PV, kein H2-System).
    """
    total_import = result_df['grid_import_kw'].sum()   # kWh
    total_export = result_df['grid_export_kw'].sum()   # kWh

    # Gesamtlast (elektrisch + Wärme in kWh_el via COP)
    total_el_load = (result_df['load_el_kw'] + result_df['ev_demand_kw']).sum()
    total_heat_load_el = (result_df['load_heat_kw'] / config.hp_cop).sum()
    total_load_el_equiv = total_el_load + total_heat_load_el

    # Autarkiegrad: Anteil Last, der OHNE Netzbezug gedeckt wurde
    autarky = max(0.0, 1.0 - (total_import / total_load_el_equiv))

    # Energiekosten
    costs_import = (result_df['grid_import_kw'] * result_df['price_buy']).sum()
    costs_export = (result_df['grid_export_kw'] * result_df['price_sell']).sum()
    net_costs = costs_import - costs_export

    # CO2-Emissionen (nur Netzbezug erzeugt CO2)
    co2_kg = (result_df['grid_import_kw'] * result_df['co2_intensity']).sum()
    co2_t = co2_kg / 1000.0

    # --- MAC: Vergleich mit Referenzfall (alles aus Netz, keine Anlage) ---
    ref_import = total_load_el_equiv  # Komplette Last aus Netz
    ref_costs = (ref_import * result_df['price_buy'].mean())
    ref_co2_t = (ref_import * result_df['co2_intensity'].mean()) / 1000.0

    delta_cost = net_costs - ref_costs        # CHF (negativ = Ersparnis)
    delta_co2 = ref_co2_t - co2_t            # tCO2 (positiv = Vermeidung)

    mac = delta_cost / delta_co2 if delta_co2 > 0 else float('inf')

    kpis = {
        'label': label,
        'Netzbezug [kWh]': round(total_import, 0),
        'Netzeinspeisung [kWh]': round(total_export, 0),
        'Autarkiegrad [%]': round(autarky * 100, 1),
        'Energiekosten [CHF/a]': round(net_costs, 0),
        'CO2-Emissionen [tCO2/a]': round(co2_t, 2),
        'MAC [CHF/tCO2]': round(mac, 1),
        'Referenz CO2 [tCO2/a]': round(ref_co2_t, 2),
        'CO2-Einsparung [tCO2/a]': round(delta_co2, 2),
    }
    return kpis


# =============================================================================
# 6. VISUALISIERUNG
# =============================================================================

def plot_week(result_df: pd.DataFrame, title: str = "Wochenprofil",
              start_day: int = 172):  # Sommerwoche (ca. 21. Juni)
    """Detailliertes Wochenprofil (Strom + H2-SOC)"""
    start = start_day * 24
    end = start + 7 * 24
    week = result_df.iloc[start:end]

    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
    fig.suptitle(title, fontsize=14, fontweight='bold')
    hours = range(len(week))

    # --- Plot 1: Strombilanz ---
    ax1 = axes[0]
    ax1.fill_between(hours, 0, week['pv_kw'], alpha=0.7,
                     color='gold', label='PV-Erzeugung')
    ax1.fill_between(hours, 0, -(week['load_el_kw'] + week['ev_demand_kw']),
                     alpha=0.5, color='steelblue', label='El. Last + E-Auto')
    ax1.fill_between(hours, 0, -week['hp_el_kw'],
                     alpha=0.5, color='orange', label='WP Strom')
    ax1.plot(hours, week['grid_import_kw'], 'r-', lw=1.5, label='Netzbezug')
    ax1.plot(hours, -week['grid_export_kw'], 'g-', lw=1.5, label='Einspeisung')
    ax1.axhline(0, color='black', lw=0.5)
    ax1.set_ylabel('Leistung [kW]')
    ax1.legend(loc='upper right', fontsize=8)
    ax1.grid(True, alpha=0.3)

    # --- Plot 2: ELY und BZ ---
    ax2 = axes[1]
    ax2.fill_between(hours, 0, week['ely_power_kw'],
                     alpha=0.7, color='purple', label='Elektrolyseur [kW]')
    ax2.fill_between(hours, 0, week['fc_power_kw'],
                     alpha=0.7, color='teal', label='Brennstoffzelle [kW]')
    ax2.fill_between(hours, 0, week['heat_from_waste_kw'],
                     alpha=0.4, color='red', label='Abwärme genutzt [kW]')
    ax2.set_ylabel('Leistung [kW]')
    ax2.legend(loc='upper right', fontsize=8)
    ax2.grid(True, alpha=0.3)

    # --- Plot 3: H2-SOC ---
    ax3 = axes[2]
    soc_pct = week['h2_soc_kwh'] / SystemConfig().h2_capacity_kwh * 100
    ax3.plot(hours, soc_pct, 'darkgreen', lw=2, label='H2-SOC [%]')
    ax3.set_ylim(0, 105)
    ax3.axhline(5, color='red', ls='--', lw=1, label='Min SOC (5%)')
    ax3.set_ylabel('H2-SOC [%]')
    ax3.set_xlabel('Stunden der Woche')
    ax3.legend(loc='upper right', fontsize=8)
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(f'wochenprofil_{title.replace(" ", "_")}.png', dpi=150)
    plt.show()


def plot_kpi_comparison(kpi_list: list):
    """Balkendiagramm-Vergleich aller Szenarien und Strategien"""
    labels = [k['label'] for k in kpi_list]
    metrics = ['Autarkiegrad [%]', 'Energiekosten [CHF/a]',
               'CO2-Emissionen [tCO2/a]', 'MAC [CHF/tCO2]']
    titles = ['Autarkiegrad [%]', 'Energiekosten [CHF/a]',
              'CO2-Emissionen [tCO2/a]', 'MAC [CHF/tCO2]']

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('KPI-Vergleich: Strategien & Szenarien', fontsize=14, fontweight='bold')
    colors = plt.cm.Set2(np.linspace(0, 1, len(labels)))

    for ax, metric, title in zip(axes.flatten(), metrics, titles):
        values = [k[metric] for k in kpi_list]
        bars = ax.bar(labels, values, color=colors)
        ax.set_title(title, fontweight='bold')
        ax.set_ylabel(metric)
        ax.tick_params(axis='x', rotation=30)
        # Werte auf Balken
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() * 1.01,
                    f'{val:,.0f}', ha='center', va='bottom', fontsize=8)
        ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig('kpi_vergleich.png', dpi=150)
    plt.show()


# =============================================================================
# 7. HAUPTPROGRAMM: SZENARIEN & VERGLEICH
# =============================================================================

def run_scenario(name: str, config: SystemConfig,
                 ev_mode: str = 'evening') -> dict:
    """Führt beide Strategien für ein Szenario aus und gibt KPIs zurück."""
    print(f"\n{'='*60}")
    print(f"  Szenario: {name}")
    print(f"{'='*60}")

    df = generate_profiles(hours=8760, ev_mode=ev_mode)

    # Strategie 1: Heuristik
    result_h = strategy_heuristic(df.copy(), config)
    kpi_h = calculate_kpis(result_h, config,
                           label=f"{name}\nHeuristik")

    # Strategie 2: Preisbasiert
    result_p = strategy_price_based(df.copy(), config)
    kpi_p = calculate_kpis(result_p, config,
                           label=f"{name}\nPreisbasiert")

    # Ausgabe
    for kpi in [kpi_h, kpi_p]:
        print(f"\n  Strategie: {kpi['label'].split(chr(10))[-1]}")
        for k, v in kpi.items():
            if k != 'label':
                print(f"    {k:<30} {v}")

    return {'heuristic': (result_h, kpi_h), 'price': (result_p, kpi_p)}


if __name__ == "__main__":

    # --- Szenario A: Referenz (moderate Preise, Abend-Laden) ---
    config_A = SystemConfig(
        price_buy_chf=0.28,
        price_sell_chf=0.10,
    )
    res_A = run_scenario("A: Referenz (Abend-Laden)", config_A, ev_mode='evening')

    # --- Szenario B: Hoher Strompreis ---
    config_B = SystemConfig(
        price_buy_chf=0.38,   # Höherer Bezugspreis
        price_sell_chf=0.16,  # Bessere Einspeisevergütung
        price_threshold_ely=0.28,
        price_threshold_fc=0.35,
    )
    res_B = run_scenario("B: Hoher Strompreis", config_B, ev_mode='evening')

    # --- Szenario C: Tagsüber-Laden E-Auto (Workplace Charging) ---
    config_C = SystemConfig(
        price_buy_chf=0.28,
        price_sell_chf=0.10,
    )
    res_C = run_scenario("C: Workplace Charging", config_C, ev_mode='daytime')

    # --- KPI Zusammenfassung ---
    all_kpis = [
        res_A['heuristic'][1], res_A['price'][1],
        res_B['heuristic'][1], res_B['price'][1],
        res_C['heuristic'][1], res_C['price'][1],
    ]

    print("\n\n=== KPI ÜBERSICHTSTABELLE ===")
    kpi_df = pd.DataFrame(all_kpis).set_index('label')
    print(kpi_df.to_string())
    kpi_df.to_csv('kpi_ergebnisse.csv')

    # --- Plots ---
    # Sommerwoche Szenario A, Heuristik
    plot_week(res_A['heuristic'][0],
              title="Szenario A – Heuristik – Sommerwoche", start_day=172)
    # Winterwoche Szenario A, Heuristik
    plot_week(res_A['heuristic'][0],
              title="Szenario A – Heuristik – Winterwoche", start_day=10)
    # KPI-Vergleich
    plot_kpi_comparison(all_kpis)
