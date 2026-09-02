"""Resumenes y comparacion contra los valores reportados por el paper.

Las funciones devuelven DataFrames en vez de imprimirlos: el notebook usaba
``display()``, que solo existe dentro de IPython y hacia que estas funciones no
se pudieran usar desde un script ni testear.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..config.schema import ScenarioConfig
from ..simulation.simulator import HourlyData, as_profile_cache, simulate_base

__all__ = [
    "PAPER_CASES",
    "PAPER_OPTIMUM",
    "SUMMARY_COLUMNS",
    "summarize_grid",
    "best_solution",
    "evaluate_named_cases",
    "compare_to_paper",
    "aggregate_runs",
]

# Casos que el paper compara directamente (celda 27 del notebook).
PAPER_CASES: Tuple[Tuple[str, float, float, float], ...] = (
    ("W190-P10-E95", 190.0, 10.0, 95.0),
    ("W120-P80-E80", 120.0, 80.0, 80.0),
    ("W60-P140-E85", 60.0, 140.0, 85.0),
)

# Resultados objetivo reportados por el paper (celda 29).
PAPER_OPTIMUM: Dict[str, object] = {
    "case": "W190-P10-E95-B30",
    "wind_mw": 190.0,
    "pv_mw": 10.0,
    "electrolyzer_mw": 95.0,
    "battery_mw": 30.0,
    "battery_mwh": 30.0,
    "lcoe_cny_per_kwh": 0.2692,
    "electrolyzer_cf": 0.6240,
    "irr": 0.1260,
    "roi": 0.7897,
}

SUMMARY_COLUMNS = [
    "wind_mw",
    "pv_mw",
    "electrolyzer_mw",
    "battery_mw",
    "battery_mwh",
    "agsr",
    "electrolyzer_cf",
    "lcoe_cny_per_kwh",
    "lcoh_cny_per_kg",
    "total_grid_sales_mwh",
    "total_h2_kg",
    "npc_cny",
]


def summarize_grid(results: pd.DataFrame) -> Dict[str, object]:
    """Conteos y mejor solucion de un barrido."""
    feasible = results[results["feasible"]]
    summary: Dict[str, object] = {
        "evaluated": int(len(results)),
        "feasible": int(len(feasible)),
        "infeasible": int(len(results) - len(feasible)),
    }
    if len(feasible) > 0:
        best = feasible.sort_values("lcoe_cny_per_kwh").iloc[0]
        summary["best_lcoe_cny_per_kwh"] = float(best["lcoe_cny_per_kwh"])
        summary["best_wind_mw"] = float(best["wind_mw"])
        summary["best_electrolyzer_mw"] = float(best["electrolyzer_mw"])
        summary["best_electrolyzer_cf"] = float(best["electrolyzer_cf"])
    return summary


def best_solution(
    results: pd.DataFrame, objective: str = "lcoe_cny_per_kwh"
) -> Optional[pd.Series]:
    """Mejor fila factible segun el objetivo, o None si no hay ninguna."""
    feasible = results[results["feasible"]]
    if len(feasible) == 0:
        return None
    return feasible.sort_values(objective).iloc[0]


def evaluate_named_cases(
    hourly: HourlyData,
    config: ScenarioConfig,
    cases: Iterable[Tuple[str, float, float, float]] = PAPER_CASES,
) -> pd.DataFrame:
    """Evalua los casos con nombre del paper bajo el modelo horario propio."""
    cache = as_profile_cache(hourly, config)
    rows: List[dict] = []
    for name, wind_mw, pv_mw, electrolyzer_mw in cases:
        record = simulate_base(cache, wind_mw, pv_mw, electrolyzer_mw, config).to_dict()
        record["case"] = name
        rows.append(record)
    return pd.DataFrame(rows)[["case"] + SUMMARY_COLUMNS + ["feasible"]]


def compare_to_paper(case_table: pd.DataFrame) -> pd.DataFrame:
    """Contrasta el caso optimo del paper con lo que produce esta replicacion.

    Una desviacion no implica un error: el paper no publica todos los detalles
    operativos del modelo base que referencia, y los datos NASA POWER
    descargados hoy no son necesariamente los que usaron los autores.
    """
    optimum_name = "W190-P10-E95"
    match = case_table[case_table["case"] == optimum_name]
    if match.empty:
        raise ValueError(
            "la tabla no contiene el caso optimo del paper ({})".format(optimum_name)
        )
    row = match.iloc[0]

    comparisons = [
        ("LCOE (CNY/kWh)", PAPER_OPTIMUM["lcoe_cny_per_kwh"], row["lcoe_cny_per_kwh"]),
        ("CF electrolizador", PAPER_OPTIMUM["electrolyzer_cf"], row["electrolyzer_cf"]),
    ]

    records = []
    for metric, reported, replicated in comparisons:
        replicated = float(replicated)
        deviation = (
            (replicated - reported) / reported * 100.0
            if reported and np.isfinite(replicated)
            else np.nan
        )
        records.append(
            {
                "metric": metric,
                "paper": reported,
                "replication": replicated,
                "deviation_pct": deviation,
            }
        )
    return pd.DataFrame(records)


def aggregate_runs(summaries: Iterable[Dict[str, object]]) -> pd.DataFrame:
    """Estadistica sobre varias semillas de un mismo algoritmo.

    Una sola corrida de una metaheuristica estocastica no es un resultado
    publicable; lo que se reporta es la distribucion sobre semillas.
    """
    frame = pd.DataFrame(list(summaries))
    if frame.empty:
        return frame

    grouped = frame.groupby("algorithm")["score"]
    stats = grouped.agg(
        runs="count", best="min", mean="mean", std="std", worst="max", median="median"
    )
    stats["feasible_runs"] = frame.groupby("algorithm")["feasible"].sum()
    stats["mean_elapsed_s"] = frame.groupby("algorithm")["elapsed_s"].mean()
    return stats.reset_index()
