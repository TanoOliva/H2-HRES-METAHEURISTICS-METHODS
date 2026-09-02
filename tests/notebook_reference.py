"""Codigo ORIGINAL del notebook, copiado literalmente de las celdas 4, 13, 15 y 17.

NO EDITAR. Este modulo no es parte del paquete: es la referencia congelada
contra la cual ``test_parity.py`` verifica que la modularizacion no cambio
ningun numero del modelo base. Sigue siendo la unica copia ejecutable del
notebook ``WPEB_trabajo1_metaheuristics_colab.ipynb``, que se elimino del
repositorio tras confirmar la paridad (el original queda en el commit 3381fc7).

Solo se omite ``simulate_wpeb_extended`` (celda 34), que no se puede ejecutar:
lee ``config["electrolyzer_specific_consumption_kwh_per_kg"]``, una clave que
nunca existio, y lanza KeyError en la primera evaluacion.
"""
import math
from dataclasses import dataclass, asdict
from typing import Dict, Optional

import numpy as np
import pandas as pd

CONFIG = {
    "lat": 41.70, "lon": 110.43,
    "start_year": 2001, "end_year": 2021,
    "analysis_year_for_8760": None,
    "total_generation_capacity_mw": 200.0,
    "agsr_max": 0.20,
    "electrolyzer_ratio_max": 0.50,
    "wind_step_mw": 10.0,
    "electrolyzer_step_mw": 5.0,
    "battery_power_ratio_to_electrolyzer": 0.30,
    "battery_duration_h": 1.0,
    "h2_hhv_kwh_per_kg": 39.4,
    "electrolyzer_efficiency": 0.75,
    "electrolyzer_min_load_ratio": 0.30,
    "project_lifetime_years": 25,
    "real_discount_rate": 0.0435,
    "wind_turbine_rated_mw": 5.0,
    "wind_cut_in_ms": 2.5,
    "wind_rated_ms": 10.5,
    "wind_cut_out_ms": 25.0,
    "pv_dc_ac_ratio": 1.2,
    "pv_temp_coeff_pct_per_c": -0.5,
    "pv_noct_c": 47.0,
    "pv_stc_efficiency_pct": 13.0,
    "pv_derating_factor": 0.90,
    "converter_efficiency": 0.95,
    "battery_roundtrip_efficiency": 0.90,
}

COSTS = {
    "wind_capex_cny_per_kw": 5917.0, "wind_replacement_cny_per_kw": 0.0,
    "wind_om_cny_per_kw_year": 40.2, "wind_life_years": 25,
    "pv_capex_cny_per_kw": 4633.0, "pv_replacement_cny_per_kw": 0.0,
    "pv_om_cny_per_kw_year": 17.6, "pv_life_years": 25,
    "electrolyzer_capex_cny_per_kw": 6964.0,
    "electrolyzer_replacement_cny_per_kw": 5969.14,
    "electrolyzer_om_cny_per_kw_year": 208.92, "electrolyzer_life_years": 15,
    "battery_capex_cny_per_kw": 2549.0, "battery_replacement_cny_per_kw": 500.0,
    "battery_om_cny_per_kw_year": 10.0, "battery_life_years": 10,
    "hydrogen_storage_capex_cny_per_kg": 6611.77,
    "hydrogen_storage_om_cny_per_kg_year": 141.68,
    "hydrogen_storage_life_years": 25,
}


def wind_turbine_power_mw(ws, rated_mw, cut_in, rated, cut_out):
    ws = np.asarray(ws)
    p = np.zeros_like(ws, dtype=float)
    mask1 = (ws >= cut_in) & (ws < rated)
    mask2 = (ws >= rated) & (ws < cut_out)
    p[mask1] = rated_mw * ((ws[mask1]**3 - cut_in**3) / (rated**3 - cut_in**3))
    p[mask2] = rated_mw
    return np.clip(p, 0.0, rated_mw)


def aggregate_wind_power_mw(df, wind_capacity_mw, config):
    n_turbines = max(int(round(wind_capacity_mw / config["wind_turbine_rated_mw"])), 0)
    single = wind_turbine_power_mw(
        df["ws50m"].values,
        rated_mw=config["wind_turbine_rated_mw"],
        cut_in=config["wind_cut_in_ms"],
        rated=config["wind_rated_ms"],
        cut_out=config["wind_cut_out_ms"],
    )
    total = single * n_turbines
    return np.minimum(total, wind_capacity_mw)


def pv_power_mw(df, pv_ac_capacity_mw, config):
    ghi = df["ghi_kwh_m2"].values
    t_amb = df["t2m_c"].values
    t_cell = t_amb + (config["pv_noct_c"] - 20.0) / 0.8 * ghi
    gamma = config["pv_temp_coeff_pct_per_c"] / 100.0
    temp_factor = 1.0 + gamma * (t_cell - 25.0)
    rel = ghi * config["pv_derating_factor"] * np.maximum(temp_factor, 0.0)
    p = pv_ac_capacity_mw * np.clip(rel, 0.0, 1.0)
    return np.minimum(p, pv_ac_capacity_mw)


@dataclass
class SimulationResult:
    wind_mw: float
    pv_mw: float
    electrolyzer_mw: float
    battery_mw: float
    battery_mwh: float
    feasible: bool
    agsr: float
    total_wind_mwh: float
    total_pv_mwh: float
    total_renewable_mwh: float
    total_grid_sales_mwh: float
    total_electrolyzer_load_mwh: float
    electrolyzer_cf: float
    total_h2_kg: float
    npc_cny: float
    annualized_cost_cny: float
    lcoe_cny_per_kwh: float
    lcoh_cny_per_kg: float


def crf(i, n):
    return (i * (1 + i) ** n) / (((1 + i) ** n) - 1)


def present_value_of_replacements(capacity_kw, replacement_cost_per_kw, life_years,
                                  project_years, discount_rate):
    years = list(range(life_years, project_years, life_years))
    return sum((capacity_kw * replacement_cost_per_kw) / ((1 + discount_rate) ** y)
               for y in years)


def present_value_of_om(capacity_kw, om_per_kw_year, project_years, discount_rate):
    return sum((capacity_kw * om_per_kw_year) / ((1 + discount_rate) ** y)
               for y in range(1, project_years + 1))


def npc_from_capacities(wind_mw, pv_mw, electrolyzer_mw, battery_mw, config, costs):
    i = config["real_discount_rate"]
    n = config["project_lifetime_years"]

    def comp(cap_mw, capex, repl, om, life):
        cap_kw = cap_mw * 1000.0
        return (cap_kw * capex
                + present_value_of_replacements(cap_kw, repl, life, n, i)
                + present_value_of_om(cap_kw, om, n, i))

    npc = 0.0
    npc += comp(wind_mw, costs["wind_capex_cny_per_kw"], costs["wind_replacement_cny_per_kw"],
                costs["wind_om_cny_per_kw_year"], costs["wind_life_years"])
    npc += comp(pv_mw, costs["pv_capex_cny_per_kw"], costs["pv_replacement_cny_per_kw"],
                costs["pv_om_cny_per_kw_year"], costs["pv_life_years"])
    npc += comp(electrolyzer_mw, costs["electrolyzer_capex_cny_per_kw"],
                costs["electrolyzer_replacement_cny_per_kw"],
                costs["electrolyzer_om_cny_per_kw_year"], costs["electrolyzer_life_years"])
    npc += comp(battery_mw, costs["battery_capex_cny_per_kw"], costs["battery_replacement_cny_per_kw"],
                costs["battery_om_cny_per_kw_year"], costs["battery_life_years"])
    return npc


def simulate_wpeb(df, wind_mw, pv_mw, electrolyzer_mw, config, costs,
                  battery_duration_h=None):
    if battery_duration_h is None:
        battery_duration_h = config["battery_duration_h"]

    total_capacity = wind_mw + pv_mw
    battery_mw = config["battery_power_ratio_to_electrolyzer"] * electrolyzer_mw
    battery_mwh = battery_mw * battery_duration_h

    if total_capacity <= 0 or abs(total_capacity - config["total_generation_capacity_mw"]) > 1e-9:
        return SimulationResult(wind_mw, pv_mw, electrolyzer_mw, battery_mw, battery_mwh, False, np.nan,
                                0, 0, 0, 0, 0, 0, 0, 0, 0, np.inf, np.inf)

    if electrolyzer_mw <= 0 or electrolyzer_mw > config["electrolyzer_ratio_max"] * total_capacity:
        return SimulationResult(wind_mw, pv_mw, electrolyzer_mw, battery_mw, battery_mwh, False, np.nan,
                                0, 0, 0, 0, 0, 0, 0, 0, 0, np.inf, np.inf)

    p_wind = aggregate_wind_power_mw(df, wind_mw, config)
    p_pv = pv_power_mw(df, pv_mw, config)

    soc = 0.0
    soc_max = battery_mwh
    p_batt_max = battery_mw

    eta_rt = config["battery_roundtrip_efficiency"]
    eta_ch = math.sqrt(eta_rt)
    eta_dis = math.sqrt(eta_rt)

    min_elz = config["electrolyzer_min_load_ratio"] * electrolyzer_mw

    grid_sales = []
    electrolyzer_load = []

    for gen in (p_wind + p_pv):
        p_elz = min(gen, electrolyzer_mw)

        if 0 < p_elz < min_elz:
            deficit = min_elz - p_elz
            p_can_discharge = min(p_batt_max, soc * eta_dis)
            p_dis = min(deficit, p_can_discharge)
            p_elz += p_dis
            soc -= p_dis / eta_dis
            if p_elz < min_elz:
                soc += p_dis / eta_dis
                p_elz = 0.0

        remaining = gen - p_elz

        if remaining > 0 and soc < soc_max:
            p_charge_room = min(p_batt_max, (soc_max - soc) / eta_ch)
            p_ch = min(remaining, p_charge_room)
            soc += p_ch * eta_ch
            remaining -= p_ch

        p_grid = max(remaining, 0.0)

        grid_sales.append(p_grid)
        electrolyzer_load.append(p_elz)

    grid_sales = np.array(grid_sales)
    electrolyzer_load = np.array(electrolyzer_load)

    e_wind = p_wind.sum()
    e_pv = p_pv.sum()
    e_gen = e_wind + e_pv
    e_grid = grid_sales.sum()
    e_elz = electrolyzer_load.sum()

    agsr = 0.0 if e_gen <= 0 else e_grid / e_gen
    feasible = agsr <= config["agsr_max"]

    electrolyzer_cf = 0.0 if electrolyzer_mw <= 0 else e_elz / (electrolyzer_mw * len(df))
    h2_kg = (e_elz * 1000.0 * config["electrolyzer_efficiency"]) / config["h2_hhv_kwh_per_kg"]

    npc = npc_from_capacities(wind_mw, pv_mw, electrolyzer_mw, battery_mw, config, costs)
    annualized = crf(config["real_discount_rate"], config["project_lifetime_years"]) * npc

    served_kwh = (e_elz + e_grid) * 1000.0
    lcoe = np.inf if served_kwh <= 0 else annualized / served_kwh
    lcoh = np.inf if h2_kg <= 0 else annualized / h2_kg

    return SimulationResult(
        wind_mw=wind_mw, pv_mw=pv_mw, electrolyzer_mw=electrolyzer_mw,
        battery_mw=battery_mw, battery_mwh=battery_mwh, feasible=feasible, agsr=agsr,
        total_wind_mwh=e_wind, total_pv_mwh=e_pv, total_renewable_mwh=e_gen,
        total_grid_sales_mwh=e_grid, total_electrolyzer_load_mwh=e_elz,
        electrolyzer_cf=electrolyzer_cf, total_h2_kg=h2_kg, npc_cny=npc,
        annualized_cost_cny=annualized, lcoe_cny_per_kwh=lcoe, lcoh_cny_per_kg=lcoh,
    )


def run_grid_search(df_year, config, costs):
    rows = []
    total_cap = config["total_generation_capacity_mw"]
    wind_values = np.arange(0, total_cap + 1e-9, config["wind_step_mw"])
    electrolyzer_values = np.arange(config["electrolyzer_step_mw"],
                                    total_cap * config["electrolyzer_ratio_max"] + 1e-9,
                                    config["electrolyzer_step_mw"])
    for wind_mw in wind_values:
        pv_mw = total_cap - wind_mw
        if pv_mw < 0:
            continue
        for e_mw in electrolyzer_values:
            res = simulate_wpeb(df_year, wind_mw, pv_mw, e_mw, config, costs)
            rows.append(asdict(res))
    return pd.DataFrame(rows)
