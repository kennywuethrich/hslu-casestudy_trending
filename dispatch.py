"""Physische Energie- und Wärmebilanz pro Zeitschritt."""

from typing import Callable, Dict, Tuple
import pandas as pd

from config import SystemConfig
from components import H2Storage, Electrolyzer, FuelCell, HeatPump, ThermalStorage


ShouldUseFC = Callable[[float, float, H2Storage, int], bool]


def _run_electrolyzer(
    available_power_kw: float,
    dt_h: float,
    electrolyzer: Electrolyzer,
    hydrogen_storage: H2Storage,
) -> Tuple[float, float, float]:
    electrolyzer_result = electrolyzer.run(available_power_kw, dt_h=dt_h)
    electrolyzer_power_kw = electrolyzer_result['power_used']
    hydrogen_produced_kwh = electrolyzer_result['h2_produced']
    heat_from_electrolyzer_kwh = electrolyzer_result['heat_produced']

    hydrogen_stored_kwh = hydrogen_storage.charge(hydrogen_produced_kwh)
    curtailed_electrolyzer_power_kw = (
        electrolyzer_power_kw * (1 - hydrogen_stored_kwh / hydrogen_produced_kwh)
        if hydrogen_produced_kwh > 0
        else 0.0
    )
    grid_export_kw = max(0.0, (available_power_kw - electrolyzer_power_kw) + curtailed_electrolyzer_power_kw)

    return electrolyzer_power_kw, heat_from_electrolyzer_kwh, grid_export_kw


def _run_fuel_cell(
    shortage_kw: float,
    market_price: float,
    day_of_year: int,
    dt_h: float,
    config: SystemConfig,
    hydrogen_storage: H2Storage,
    fuel_cell: FuelCell,
    should_use_fc: ShouldUseFC,
) -> Tuple[float, float, float]:
    if shortage_kw <= 0:
        return 0.0, 0.0, 0.0

    if not should_use_fc(market_price, shortage_kw, hydrogen_storage, day_of_year):
        return 0.0, shortage_kw, 0.0

    requested_fc_power_kw = min(shortage_kw, config.fc_dispatch_max_kw)
    fuel_cell_result = fuel_cell.run(requested_fc_power_kw, hydrogen_storage.available_discharge, dt_h=dt_h)
    fuel_cell_power_kw = fuel_cell_result['power_out']
    hydrogen_used_kwh = fuel_cell_result['h2_used']
    heat_from_fuel_cell_kwh = fuel_cell_result['heat_produced']

    hydrogen_storage.discharge(hydrogen_used_kwh)
    grid_import_kw = max(0.0, shortage_kw - fuel_cell_power_kw)

    return fuel_cell_power_kw, grid_import_kw, heat_from_fuel_cell_kwh


def _compute_heat_balance(
    load_heat_kwh: float,
    dt_h: float,
    heat_pump: HeatPump,
    base_heat_pump_power_kw: float,
    extra_heat_pump_power_kw: float,
    grid_import_kw: float,
    grid_export_kw: float,
    electrolyzer_power_kw: float,
    fuel_cell_power_kw: float,
    heat_from_electrolyzer_kwh: float,
    heat_from_fuel_cell_kwh: float,
    heat_from_extra_heat_pump_kwh: float,
    market_price: float,
    day_of_year: int,
    config: SystemConfig,
    hydrogen_storage: H2Storage,
    thermal_storage: ThermalStorage,
    electrolyzer: Electrolyzer,
    fuel_cell: FuelCell,
    should_use_fc: ShouldUseFC,
) -> Tuple[float, float, float, float, float, float, float]:
    direct_heat_kwh = heat_from_electrolyzer_kwh + heat_from_fuel_cell_kwh + heat_from_extra_heat_pump_kwh

    if direct_heat_kwh > load_heat_kwh:
        thermal_storage.charge(direct_heat_kwh - load_heat_kwh)
        heat_still_needed_kwh = 0.0
    else:
        heat_still_needed_kwh = load_heat_kwh - direct_heat_kwh

    heat_from_thermal_storage_kwh = thermal_storage.discharge(heat_still_needed_kwh)
    remaining_heat_need_kwh = max(0.0, heat_still_needed_kwh - heat_from_thermal_storage_kwh)

    final_heat_pump_power_kw = remaining_heat_need_kwh / (heat_pump.cop * dt_h) if dt_h > 0 else 0.0
    planned_heat_pump_power_kw = base_heat_pump_power_kw + extra_heat_pump_power_kw
    heat_pump_power_correction_kw = planned_heat_pump_power_kw - final_heat_pump_power_kw

    if heat_pump_power_correction_kw >= 0:
        if grid_import_kw > 0:
            grid_import_kw = max(0.0, grid_import_kw - heat_pump_power_correction_kw)
        else:
            recovered_surplus_kw = max(0.0, heat_pump_power_correction_kw)
            if recovered_surplus_kw > 0:
                extra_ely_power_kw, extra_ely_heat_kwh, extra_grid_export_kw = _run_electrolyzer(
                    recovered_surplus_kw,
                    dt_h,
                    electrolyzer,
                    hydrogen_storage,
                )
                electrolyzer_power_kw += extra_ely_power_kw
                heat_from_electrolyzer_kwh += extra_ely_heat_kwh
                grid_export_kw += extra_grid_export_kw
    else:
        extra_shortage_kw = abs(heat_pump_power_correction_kw)
        extra_fc_power_kw, extra_grid_import_kw, extra_fc_heat_kwh = _run_fuel_cell(
            extra_shortage_kw,
            market_price,
            day_of_year,
            dt_h,
            config,
            hydrogen_storage,
            fuel_cell,
            should_use_fc,
        )
        fuel_cell_power_kw += extra_fc_power_kw
        heat_from_fuel_cell_kwh += extra_fc_heat_kwh
        grid_import_kw += extra_grid_import_kw

    heat_from_waste_kwh = min(load_heat_kwh, direct_heat_kwh + heat_from_thermal_storage_kwh)

    return (
        grid_import_kw,
        grid_export_kw,
        electrolyzer_power_kw,
        fuel_cell_power_kw,
        final_heat_pump_power_kw,
        heat_from_electrolyzer_kwh,
        heat_from_waste_kwh,
    )


def _dispatch_step(
    row,
    config: SystemConfig,
    hydrogen_storage: H2Storage,
    thermal_storage: ThermalStorage,
    electrolyzer: Electrolyzer,
    fuel_cell: FuelCell,
    heat_pump: HeatPump,
    should_use_fc: ShouldUseFC,
) -> Dict[str, float]:
    dt_h = row['dt_h'] if 'dt_h' in row else 1.0
    pv_power_kw = row['pv_kw']
    market_price = row['price_buy']
    electric_load_kw = row['load_el_kw']
    ev_home_charging_power_kw = max(0.0, row['ev_demand_kw'])
    heat_load_kw = row['load_heat_kw']
    heat_load_kwh = heat_load_kw * dt_h
    day_of_year = int(row['day_of_year']) if 'day_of_year' in row else 0

    base_heat_pump_power_kw = min(heat_load_kw / heat_pump.cop, config.hp_kw_th_max / heat_pump.cop)
    total_electric_demand_kw = electric_load_kw + ev_home_charging_power_kw + base_heat_pump_power_kw
    net_electric_balance_kw = pv_power_kw - total_electric_demand_kw

    grid_import = 0.0
    grid_export = 0.0
    electrolyzer_power = 0.0
    fuel_cell_power = 0.0
    extra_heat_pump_power_kw = 0.0
    heat_from_ely = 0.0
    heat_from_fc = 0.0
    heat_from_hp_extra = 0.0

    if net_electric_balance_kw >= 0:
        max_heat_pump_power_kw = config.hp_kw_th_max / heat_pump.cop
        extra_heat_pump_power_kw = min(
            net_electric_balance_kw,
            max(0.0, max_heat_pump_power_kw - base_heat_pump_power_kw),
        )
        heat_from_hp_extra = extra_heat_pump_power_kw * heat_pump.cop * dt_h
        remaining_surplus_kw = max(0.0, net_electric_balance_kw - extra_heat_pump_power_kw)

        electrolyzer_power, heat_from_ely, grid_export = _run_electrolyzer(
            remaining_surplus_kw,
            dt_h,
            electrolyzer,
            hydrogen_storage,
        )
    else:
        shortage_kw = abs(net_electric_balance_kw)
        fuel_cell_power, grid_import, heat_from_fc = _run_fuel_cell(
            shortage_kw,
            market_price,
            day_of_year,
            dt_h,
            config,
            hydrogen_storage,
            fuel_cell,
            should_use_fc,
        )

    (
        grid_import,
        grid_export,
        electrolyzer_power,
        fuel_cell_power,
        final_heat_pump_power_kw,
        heat_from_ely,
        heat_from_waste_kwh,
    ) = _compute_heat_balance(
        heat_load_kwh,
        dt_h,
        heat_pump,
        base_heat_pump_power_kw,
        extra_heat_pump_power_kw,
        grid_import,
        grid_export,
        electrolyzer_power,
        fuel_cell_power,
        heat_from_ely,
        heat_from_fc,
        heat_from_hp_extra,
        market_price,
        day_of_year,
        config,
        hydrogen_storage,
        thermal_storage,
        electrolyzer,
        fuel_cell,
        should_use_fc,
    )

    return {
        'grid_import_kw': grid_import,
        'grid_export_kw': grid_export,
        'ely_power_kw': electrolyzer_power,
        'fc_power_kw': fuel_cell_power,
        'h2_soc_kwh': hydrogen_storage.soc_kwh,
        'ev_charge_kw': ev_home_charging_power_kw,
        'ev_unserved_drive_kwh': 0.0,
        'thermal_soc_kwh': thermal_storage.soc_kwh,
        'hp_el_kw': final_heat_pump_power_kw,
        'heat_from_waste_kw': (heat_from_waste_kwh / dt_h) if dt_h > 0 else 0.0,
    }


def run_dispatch(profile_df: pd.DataFrame, config: SystemConfig, should_use_fc: ShouldUseFC) -> pd.DataFrame:
    """Führt Dispatch für ein gesamtes Profil aus."""
    hydrogen_storage = H2Storage(config)
    thermal_storage = ThermalStorage(config)
    electrolyzer = Electrolyzer(config)
    fuel_cell = FuelCell(config)
    heat_pump = HeatPump(config)

    results = []
    for _, row in profile_df.iterrows():
        step_result = _dispatch_step(
            row,
            config,
            hydrogen_storage,
            thermal_storage,
            electrolyzer,
            fuel_cell,
            heat_pump,
            should_use_fc,
        )
        results.append(step_result)

    return pd.concat([
        profile_df.reset_index(drop=True),
        pd.DataFrame(results)
    ], axis=1)
