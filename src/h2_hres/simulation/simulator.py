"""Simulacion anual del sistema WPEB (celdas 15 y 34 del notebook).

Dos puntos de entrada sobre un unico nucleo:

``simulate_base``
    Replica del paper: la bateria se dimensiona como un porcentaje fijo de la
    capacidad del electrolizador, y el electrolizador es continuo.

``simulate_discrete``
    Extension del trabajo 1: electrolizador modular en unidades enteras, y
    potencia y duracion de bateria como variables de decision discretas.
"""

from __future__ import annotations

import math
from typing import Optional, Union

import numpy as np
import pandas as pd

from ..config.schema import ScenarioConfig
from ..models.economics import crf, levelized_cost, npc_from_capacities
from ..models.profiles import GenerationProfileCache
from .dispatch import MinLoadPolicy, dispatch_hourly
from .results import SimulationResult, infeasible_result

__all__ = [
    "simulate_base",
    "simulate_discrete",
    "as_profile_cache",
    "battery_power_for",
]

HourlyData = Union[pd.DataFrame, GenerationProfileCache]

_CAPACITY_TOLERANCE_MW = 1e-9


def as_profile_cache(
    hourly: HourlyData, config: ScenarioConfig
) -> GenerationProfileCache:
    """Acepta indistintamente un DataFrame horario o un cache ya construido.

    Reutilizar el mismo cache entre evaluaciones es lo que evita recalcular los
    perfiles de generacion en cada llamada del optimizador.
    """
    if isinstance(hourly, GenerationProfileCache):
        return hourly
    return GenerationProfileCache(hourly, config)


def battery_power_for(electrolyzer_mw: float, config: ScenarioConfig) -> float:
    """Potencia de bateria del modelo base, en tamanos de pack comerciales.

    El paper la fija en 30% de la capacidad del electrolizador -- el ratio de
    carga minima -- pero los casos publicados muestran que redondea hacia arriba
    al pack disponible: 0.30*95=28.5 -> B30, 0.30*80=24 -> B25 y
    0.30*85=25.5 -> B27.5. De ahi el paso de 2.5 MW.
    """
    battery = config.battery
    exact = battery.power_ratio_to_electrolyzer * electrolyzer_mw
    step = battery.power_rounding_step_mw
    # El epsilon evita que un exacto ya alineado a la malla salte un pack por
    # error de coma flotante (25.0 / 2.5 = 9.999...).
    return math.ceil(exact / step - 1e-9) * step


def simulate_base(
    hourly: HourlyData,
    wind_mw: float,
    pv_mw: float,
    electrolyzer_mw: float,
    config: ScenarioConfig,
    battery_duration_h: Optional[float] = None,
) -> SimulationResult:
    """Modelo base del paper, con bateria proporcional al electrolizador."""
    battery = config.battery
    duration_h = battery.duration_h if battery_duration_h is None else battery_duration_h
    battery_mw = battery_power_for(electrolyzer_mw, config)
    battery_mwh = battery_mw * duration_h

    units = int(round(electrolyzer_mw / config.electrolyzer.unit_mw))

    reason = _check_base_constraints(wind_mw, pv_mw, electrolyzer_mw, config)
    if reason:
        return infeasible_result(
            wind_mw, pv_mw, electrolyzer_mw, units,
            battery_mw, battery_mwh, duration_h, reason,
        )

    return _simulate(
        hourly=hourly,
        wind_mw=wind_mw,
        pv_mw=pv_mw,
        electrolyzer_mw=electrolyzer_mw,
        n_electrolyzer_units=units,
        battery_mw=battery_mw,
        battery_duration_h=duration_h,
        config=config,
        policy=MinLoadPolicy.TOP_UP,
    )


def simulate_discrete(
    hourly: HourlyData,
    wind_mw: float,
    n_electrolyzer_units: int,
    battery_mw: float,
    battery_duration_h: float,
    config: ScenarioConfig,
) -> SimulationResult:
    """Extension discreta: electrolizador modular y bateria libre."""
    total_capacity = config.constraints.total_generation_capacity_mw
    pv_mw = total_capacity - wind_mw
    electrolyzer_mw = n_electrolyzer_units * config.electrolyzer.unit_mw
    battery_mwh = battery_mw * battery_duration_h

    reason = _check_discrete_constraints(
        wind_mw, pv_mw, n_electrolyzer_units, battery_mw, battery_duration_h, config
    )
    if reason:
        return infeasible_result(
            wind_mw, pv_mw, electrolyzer_mw, int(n_electrolyzer_units),
            battery_mw, battery_mwh, battery_duration_h, reason,
        )

    return _simulate(
        hourly=hourly,
        wind_mw=wind_mw,
        pv_mw=pv_mw,
        electrolyzer_mw=electrolyzer_mw,
        n_electrolyzer_units=int(n_electrolyzer_units),
        battery_mw=battery_mw,
        battery_duration_h=battery_duration_h,
        config=config,
        policy=MinLoadPolicy.THRESHOLD,
    )


# ---------------------------------------------------------------------------
# Restricciones
# ---------------------------------------------------------------------------


def _check_base_constraints(
    wind_mw: float, pv_mw: float, electrolyzer_mw: float, config: ScenarioConfig
) -> str:
    constraints = config.constraints
    total = wind_mw + pv_mw

    if wind_mw < 0 or pv_mw < 0:
        return "capacidad negativa (wind={:.1f}, pv={:.1f})".format(wind_mw, pv_mw)
    if abs(total - constraints.total_generation_capacity_mw) > _CAPACITY_TOLERANCE_MW:
        return "wind+pv={:.3f} MW no respeta la capacidad fija de {:.1f} MW".format(
            total, constraints.total_generation_capacity_mw
        )
    if electrolyzer_mw <= 0:
        return "electrolizador de capacidad nula"
    if electrolyzer_mw > constraints.electrolyzer_max_mw + _CAPACITY_TOLERANCE_MW:
        return "electrolizador {:.1f} MW supera el maximo de {:.1f} MW".format(
            electrolyzer_mw, constraints.electrolyzer_max_mw
        )
    return ""


def _check_discrete_constraints(
    wind_mw: float,
    pv_mw: float,
    n_units: int,
    battery_mw: float,
    battery_duration_h: float,
    config: ScenarioConfig,
) -> str:
    electrolyzer = config.electrolyzer
    battery = config.battery

    reason = _check_base_constraints(
        wind_mw, pv_mw, n_units * electrolyzer.unit_mw, config
    )
    if reason:
        return reason

    if not electrolyzer.min_units <= n_units <= electrolyzer.max_units:
        return "n_units={} fuera del rango discreto [{}, {}]".format(
            n_units, electrolyzer.min_units, electrolyzer.max_units
        )
    if not battery.power_min_mw <= battery_mw <= battery.power_max_mw:
        return "bateria {:.1f} MW fuera del rango [{:.1f}, {:.1f}]".format(
            battery_mw, battery.power_min_mw, battery.power_max_mw
        )
    if not any(
        abs(battery_duration_h - candidate) < 1e-9
        for candidate in battery.duration_candidates_h
    ):
        return "duracion de bateria {} h no esta entre las candidatas {}".format(
            battery_duration_h, list(battery.duration_candidates_h)
        )
    return ""


# ---------------------------------------------------------------------------
# Nucleo comun
# ---------------------------------------------------------------------------


def _simulate(
    hourly: HourlyData,
    wind_mw: float,
    pv_mw: float,
    electrolyzer_mw: float,
    n_electrolyzer_units: int,
    battery_mw: float,
    battery_duration_h: float,
    config: ScenarioConfig,
    policy: MinLoadPolicy,
) -> SimulationResult:
    cache = as_profile_cache(hourly, config)
    battery = config.battery
    battery_mwh = battery_mw * battery_duration_h

    wind_profile = cache.wind(wind_mw)
    pv_profile = cache.pv(pv_mw)
    generation = cache.total(wind_mw, pv_mw)

    # El consumo parasito de la planta (``P_plant_load`` en la Eq. 6 del paper)
    # se descuenta de la generacion bruta antes de despachar. Con el default de
    # 0.0 el perfil pasa intacto.
    converter = config.converter
    if converter.plant_load_ratio > 0:
        generation = generation * (1.0 - converter.plant_load_ratio)

    dispatch = dispatch_hourly(
        generation_mw=generation,
        electrolyzer_mw=electrolyzer_mw,
        min_load_ratio=config.electrolyzer.min_load_ratio,
        battery_power_mw=battery_mw,
        battery_energy_mwh=battery_mwh,
        # La bateria pasa por el convertidor bidireccional en ambos sentidos,
        # ademas de su propia eficiencia de ciclo.
        eta_charge=battery.eta_charge * converter.bidirectional_efficiency,
        eta_discharge=battery.eta_discharge * converter.bidirectional_efficiency,
        policy=policy,
        grid_export_limit_mw=config.constraints.grid_export_limit_mw,
    )

    energy_wind = float(wind_profile.sum())
    energy_pv = float(pv_profile.sum())
    energy_renewable = energy_wind + energy_pv
    energy_grid = float(dispatch.grid_sales.sum())
    energy_electrolyzer = float(dispatch.electrolyzer_load.sum())
    energy_curtailed = float(dispatch.curtailment.sum())
    throughput = float(dispatch.battery_charge.sum() + dispatch.battery_discharge.sum())

    agsr = energy_grid / energy_renewable if energy_renewable > 0 else 0.0
    feasible = agsr <= config.constraints.agsr_max
    reason = (
        ""
        if feasible
        else "AGSR={:.4f} supera el maximo de {:.2f}".format(
            agsr, config.constraints.agsr_max
        )
    )

    hours = cache.n_hours
    capacity_factor = (
        energy_electrolyzer / (electrolyzer_mw * hours) if electrolyzer_mw > 0 else 0.0
    )

    # El electrolizador se alimenta en DC: la energia que llega a las celdas es
    # la que toma del bus AC menos la perdida del rectificador (``P_rectifier_loss``
    # en la Eq. 6). El factor de capacidad sigue midiendose sobre la carga AC,
    # que es la potencia contratada.
    energy_to_cells = energy_electrolyzer * converter.rectifier_efficiency
    h2_kg = (
        energy_to_cells * 1000.0 / config.electrolyzer.specific_consumption_kwh_per_kg
    )

    npc = npc_from_capacities(
        wind_mw=wind_mw,
        pv_mw=pv_mw,
        electrolyzer_mw=electrolyzer_mw,
        battery_mw=battery_mw,
        battery_mwh=battery_mwh,
        costs=config.costs,
        economics=config.economics,
        hydrogen_storage_kg=config.electrolyzer.hydrogen_storage_kg,
    )
    annualized = npc * crf(
        config.economics.real_discount_rate, config.economics.project_lifetime_years
    )

    # Energia util del denominador del LCOE. El notebook usaba criterios
    # distintos en el modelo base y en el extendido; ahora es una decision
    # explicita del escenario (ver CHANGELOG.md, correccion 2).
    if config.economics.lcoe_energy_basis == "electrolyzer_only":
        served_mwh = energy_electrolyzer
    else:
        served_mwh = energy_electrolyzer + energy_grid

    return SimulationResult(
        wind_mw=wind_mw,
        pv_mw=pv_mw,
        electrolyzer_mw=electrolyzer_mw,
        n_electrolyzer_units=n_electrolyzer_units,
        battery_mw=battery_mw,
        battery_mwh=battery_mwh,
        battery_duration_h=battery_duration_h,
        feasible=bool(feasible),
        agsr=float(agsr),
        infeasibility_reason=reason,
        total_wind_mwh=energy_wind,
        total_pv_mwh=energy_pv,
        total_renewable_mwh=energy_renewable,
        total_grid_sales_mwh=energy_grid,
        total_electrolyzer_load_mwh=energy_electrolyzer,
        total_curtailment_mwh=energy_curtailed,
        battery_throughput_mwh=throughput,
        electrolyzer_cf=float(capacity_factor),
        total_h2_kg=float(h2_kg),
        npc_cny=float(npc),
        annualized_cost_cny=float(annualized),
        lcoe_cny_per_kwh=levelized_cost(annualized, served_mwh * 1000.0),
        lcoh_cny_per_kg=levelized_cost(annualized, h2_kg),
    )
