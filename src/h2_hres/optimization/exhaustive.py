"""Busquedas exhaustivas del modelo base (celdas 17 y 18 del notebook).

``run_grid_search``
    Barre todo el dominio discreto Wind x Electrolyzer. Es la referencia contra
    la cual se juzga si una metaheuristica vale la pena: sobre esta malla el
    optimo global se conoce por enumeracion.

``local_descent_search``
    Descenso por vecinos desde una semilla, analogo a la busqueda con gradiente
    del paper. Barato, pero se detiene en el primer minimo local.
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np
import pandas as pd

from ..config.schema import ScenarioConfig
from ..simulation.simulator import HourlyData, as_profile_cache, simulate_base

__all__ = ["run_grid_search", "local_descent_search", "grid_axes"]


def grid_axes(config: ScenarioConfig):
    """Ejes de la malla: capacidades de viento y de electrolizador."""
    total_capacity = config.constraints.total_generation_capacity_mw
    wind_values = np.arange(
        0.0, total_capacity + 1e-9, config.search.wind_step_mw
    )
    electrolyzer_values = np.arange(
        config.search.electrolyzer_step_mw,
        config.constraints.electrolyzer_max_mw + 1e-9,
        config.search.electrolyzer_step_mw,
    )
    return wind_values, electrolyzer_values


def run_grid_search(
    hourly: HourlyData, config: ScenarioConfig, progress: bool = True
) -> pd.DataFrame:
    """Evalua toda la malla y devuelve una fila por configuracion."""
    cache = as_profile_cache(hourly, config)
    wind_values, electrolyzer_values = grid_axes(config)
    total_capacity = config.constraints.total_generation_capacity_mw

    iterator = wind_values
    if progress:
        try:
            from tqdm.auto import tqdm

            iterator = tqdm(wind_values, desc="Barrido de viento")
        except ImportError:
            pass

    rows: List[dict] = []
    for wind_mw in iterator:
        pv_mw = total_capacity - float(wind_mw)
        if pv_mw < 0:
            continue
        for electrolyzer_mw in electrolyzer_values:
            result = simulate_base(
                cache, float(wind_mw), pv_mw, float(electrolyzer_mw), config
            )
            rows.append(result.to_dict())

    return pd.DataFrame(rows)


def local_descent_search(
    hourly: HourlyData,
    config: ScenarioConfig,
    start_wind_mw: float = 100.0,
    start_electrolyzer_mw: float = 80.0,
    max_steps: int = 1000,
) -> pd.DataFrame:
    """Desciende hacia el vecino factible de menor LCOE hasta estancarse."""
    cache = as_profile_cache(hourly, config)
    total_capacity = config.constraints.total_generation_capacity_mw
    wind_step = config.search.wind_step_mw
    electrolyzer_step = config.search.electrolyzer_step_mw

    visited = set()
    records: List[dict] = []
    current = (float(start_wind_mw), float(start_electrolyzer_mw))

    for _ in range(max_steps):
        if current in visited:
            break
        visited.add(current)

        wind_mw, electrolyzer_mw = current
        pv_mw = total_capacity - wind_mw
        current_result = simulate_base(cache, wind_mw, pv_mw, electrolyzer_mw, config)
        records.append(current_result.to_dict())

        best_neighbor: Optional[tuple] = None
        best_lcoe = float("inf")

        for neighbor_wind, neighbor_electrolyzer in (
            (wind_mw - wind_step, electrolyzer_mw),
            (wind_mw + wind_step, electrolyzer_mw),
            (wind_mw, electrolyzer_mw - electrolyzer_step),
            (wind_mw, electrolyzer_mw + electrolyzer_step),
        ):
            neighbor_pv = total_capacity - neighbor_wind
            if neighbor_wind < 0 or neighbor_pv < 0 or neighbor_electrolyzer <= 0:
                continue
            if neighbor_electrolyzer > config.constraints.electrolyzer_max_mw:
                continue

            neighbor_result = simulate_base(
                cache, neighbor_wind, neighbor_pv, neighbor_electrolyzer, config
            )
            if not neighbor_result.feasible:
                continue
            if neighbor_result.lcoe_cny_per_kwh < best_lcoe:
                best_lcoe = neighbor_result.lcoe_cny_per_kwh
                best_neighbor = (neighbor_wind, neighbor_electrolyzer)

        if best_neighbor is None or best_lcoe + 1e-12 >= current_result.lcoe_cny_per_kwh:
            break
        current = best_neighbor

    return pd.DataFrame(records)
