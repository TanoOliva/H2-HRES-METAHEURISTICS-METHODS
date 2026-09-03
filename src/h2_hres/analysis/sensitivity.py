"""Sensibilidad del optimo al limite de AGSR y a la carga minima del electrolizador.

Se resuelve con :func:`run_grid_search` sobre el modelo base, no con una
metaheuristica: el barrido es determinista, de modo que las curvas de
sensibilidad no llevan ruido de semilla y la tendencia se lee sin ambiguedad.
Cada valor barrido son 21 x 20 = 420 evaluaciones (~2-3 s), asi que los nueve
valores por defecto entre los dos parametros toman unos 20-25 s en total.

Dos parametros, por lo que reportan §3.1 del paper: el limite de AGSR es la
restriccion que define el dominio factible y fija el limite inferior del
electrolizador; la carga minima (30% en el paper) determina el dimensionamiento
de la bateria.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Sequence

import pandas as pd

from ..config.schema import ScenarioConfig
from ..optimization.exhaustive import run_grid_search
from ..simulation.simulator import HourlyData
from .summaries import summarize_grid

__all__ = [
    "AGSR_MAX_VALUES",
    "MIN_LOAD_RATIO_VALUES",
    "sweep_agsr_max",
    "sweep_min_load_ratio",
    "run_sensitivity_study",
]

AGSR_MAX_VALUES: Sequence[float] = (0.10, 0.15, 0.20, 0.25, 0.30)
MIN_LOAD_RATIO_VALUES: Sequence[float] = (0.20, 0.30, 0.40, 0.50)

_SUMMARY_KEYS = (
    "evaluated", "feasible", "infeasible",
    "best_lcoe_cny_per_kwh", "best_wind_mw", "best_electrolyzer_mw",
    "best_electrolyzer_cf",
)


def _sweep(
    hourly: HourlyData,
    config: ScenarioConfig,
    parameter: str,
    values: Sequence[float],
    build_config,
    progress: bool,
) -> pd.DataFrame:
    rows = []
    for value in values:
        swept_config = build_config(config, value)
        results = run_grid_search(hourly, swept_config, progress=progress)
        summary = summarize_grid(results)

        row = {"parameter": parameter, "value": float(value)}
        for key in _SUMMARY_KEYS:
            row[key] = summary.get(key, float("nan"))
        row["feasible_share"] = (
            summary["feasible"] / summary["evaluated"] if summary["evaluated"] else 0.0
        )
        rows.append(row)
    return pd.DataFrame(rows)


def sweep_agsr_max(
    hourly: HourlyData,
    config: ScenarioConfig,
    values: Sequence[float] = AGSR_MAX_VALUES,
    progress: bool = False,
) -> pd.DataFrame:
    """Optimo y tamano del dominio factible en funcion del limite de AGSR."""

    def build_config(base: ScenarioConfig, value: float) -> ScenarioConfig:
        return base.replace(constraints=replace(base.constraints, agsr_max=value))

    return _sweep(hourly, config, "agsr_max", values, build_config, progress)


def sweep_min_load_ratio(
    hourly: HourlyData,
    config: ScenarioConfig,
    values: Sequence[float] = MIN_LOAD_RATIO_VALUES,
    progress: bool = False,
) -> pd.DataFrame:
    """Optimo y tamano del dominio factible en funcion de la carga minima."""

    def build_config(base: ScenarioConfig, value: float) -> ScenarioConfig:
        return base.replace(electrolyzer=replace(base.electrolyzer, min_load_ratio=value))

    return _sweep(hourly, config, "min_load_ratio", values, build_config, progress)


def run_sensitivity_study(
    hourly: HourlyData,
    config: ScenarioConfig,
    agsr_values: Sequence[float] = AGSR_MAX_VALUES,
    min_load_values: Sequence[float] = MIN_LOAD_RATIO_VALUES,
    progress: bool = False,
) -> dict:
    """Los dos barridos, listos para reportar o graficar."""
    return {
        "agsr_max": sweep_agsr_max(hourly, config, agsr_values, progress),
        "min_load_ratio": sweep_min_load_ratio(hourly, config, min_load_values, progress),
    }
