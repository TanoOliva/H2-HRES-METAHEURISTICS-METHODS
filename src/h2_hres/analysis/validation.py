"""Validacion cuantitativa contra las cifras publicadas por Li et al. (2024).

Toda la replicacion se juzga aqui: cada objetivo sale del PDF con su seccion de
origen, y la tabla resultante dice si el modelo reproduce el paper o no. Sin
esto no se puede afirmar que una metaheuristica mejora al paper, porque no
habria forma de saber si la mejora viene del algoritmo o de un modelo distinto.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import pandas as pd

from ..config.schema import ScenarioConfig
from ..simulation.simulator import HourlyData, as_profile_cache, simulate_base

__all__ = [
    "Target",
    "PAPER_TARGETS",
    "validate_scenario",
    "resource_metrics",
    "wind_surface_comparison",
]


@dataclass(frozen=True)
class Target:
    """Un valor publicado contra el que se contrasta la replicacion."""

    metric: str
    reported: float
    section: str
    unit: str = ""
    tolerance_pct: float = 3.0
    note: str = ""

    def row(self, replicated: Optional[float]) -> dict:
        if replicated is None or not np.isfinite(replicated):
            deviation = np.nan
            verdict = "sin dato"
        else:
            deviation = (replicated - self.reported) / self.reported * 100.0
            verdict = "OK" if abs(deviation) <= self.tolerance_pct else "REVISAR"
        return {
            "metrica": self.metric,
            "unidad": self.unit,
            "paper": self.reported,
            "replicacion": replicated,
            "desvio_pct": deviation,
            "veredicto": verdict,
            "seccion": self.section,
            "nota": self.note,
        }


# Objetivos extraidos del paper. Las tolerancias son mas anchas donde el paper
# no publica el detalle del modelo (recurso) y mas estrictas en lo economico,
# que depende solo de la Tabla 4 y del horizonte.
PAPER_TARGETS = {
    "wind_cf": Target("CF parque eolico", 0.40, "§3.1", "fraccion", 8.0),
    "pv_cf": Target("CF parque fotovoltaico", 0.19, "§3.1", "fraccion", 15.0),
    "electrolyzer_cf": Target("CF electrolizador (W190-P10-E95)", 0.6240, "§3.1", "fraccion", 8.0),
    "lcoe_w190": Target("LCOE W190-P10-E95-B30", 0.2692, "§3.2", "CNY/kWh", 3.0),
    "lcoe_w120": Target("LCOE W120-P80-E80-B25", 0.2886, "§3.2", "CNY/kWh", 3.0),
    "lcoe_w60": Target("LCOE W60-P140-E85-B27.5", 0.3617, "§3.2", "CNY/kWh", 3.0),
    "npc_w190": Target("NPC W190-P10-E95-B30", 2675.73, "§3.2", "M CNY", 3.0),
    "npc_w120": Target("NPC W120-P80-E80-B25", 2350.38, "§3.2", "M CNY", 3.0),
    "npc_w60": Target(
        "NPC W60-P140-E85-B27.5",
        2114.53,
        "§3.2",
        "M CNY",
        3.0,
        note=(
            "inconsistente con la Tabla 4 del paper: sus propios costos implican "
            "un delta de -26.7 M CNY respecto de W120-P80, no los -235.9 que "
            "reporta. Los otros dos NPC calzan al 0.4%."
        ),
    ),
    "capex_share": Target("CAPEX sobre NPC (W190)", 0.7330, "§3.2", "fraccion", 5.0),
}

# Los tres casos con nombre del paper: (etiqueta, wind_mw, pv_mw, electrolyzer_mw).
NAMED_CASES = (
    ("w190", 190.0, 10.0, 95.0),
    ("w120", 120.0, 80.0, 80.0),
    ("w60", 60.0, 140.0, 85.0),
)


def resource_metrics(hourly: pd.DataFrame, config: ScenarioConfig) -> dict:
    """Factores de capacidad del recurso, independientes del dimensionamiento.

    Se calculan sobre un parque de referencia y se normalizan por su capacidad,
    de modo que el CF no dependa de cuantos MW se instalen.
    """
    cache = as_profile_cache(hourly, config)
    hours = cache.n_hours

    reference_mw = 100.0
    wind_energy = float(cache.wind(reference_mw).sum())
    pv_energy = float(cache.pv(reference_mw).sum())

    return {
        "wind_cf": wind_energy / (reference_mw * hours),
        "pv_cf": pv_energy / (reference_mw * hours),
        "mean_wind_speed_50m": float(np.mean(hourly["ws50m"])),
        "mean_hub_wind_speed": float(
            np.mean(hourly["wsc_ms"]) if "wsc_ms" in hourly.columns else np.nan
        ),
        "annual_ghi_kwh_m2": float(np.sum(hourly["ghi_kwh_m2"])),
        "wind_column": cache.wind_column,
    }


def validate_scenario(hourly: HourlyData, config: ScenarioConfig) -> pd.DataFrame:
    """Contrasta la replicacion completa contra los objetivos publicados."""
    cache = as_profile_cache(hourly, config)
    frame = hourly if isinstance(hourly, pd.DataFrame) else None

    results = {
        label: simulate_base(cache, wind, pv, electrolyzer, config)
        for label, wind, pv, electrolyzer in NAMED_CASES
    }

    replicated = {
        "electrolyzer_cf": results["w190"].electrolyzer_cf,
        "lcoe_w190": results["w190"].lcoe_cny_per_kwh,
        "lcoe_w120": results["w120"].lcoe_cny_per_kwh,
        "lcoe_w60": results["w60"].lcoe_cny_per_kwh,
        "npc_w190": results["w190"].npc_cny / 1e6,
        "npc_w120": results["w120"].npc_cny / 1e6,
        "npc_w60": results["w60"].npc_cny / 1e6,
        "capex_share": _capex_share(results["w190"], config),
    }

    if frame is not None:
        resource = resource_metrics(frame, config)
        replicated["wind_cf"] = resource["wind_cf"]
        replicated["pv_cf"] = resource["pv_cf"]

    rows: List[dict] = [
        target.row(replicated.get(key))
        for key, target in PAPER_TARGETS.items()
    ]
    return pd.DataFrame(rows)


def _capex_share(result, config: ScenarioConfig) -> float:
    """Fraccion del NPC que corresponde a inversion inicial.

    El paper reporta 73.30% para el caso optimo, lo que valida indirectamente el
    reparto entre capex, reemplazos, O&M y residual.
    """
    costs = config.costs
    capex = (
        result.wind_mw * 1000.0 * costs.wind.capex_cny_per_kw
        + result.pv_mw * 1000.0 * costs.pv.capex_cny_per_kw
        + result.electrolyzer_mw * 1000.0 * costs.electrolyzer.capex_cny_per_kw
        + result.battery_mw * 1000.0 * costs.battery.capex_cny_per_kw
        + config.electrolyzer.hydrogen_storage_kg
        * costs.hydrogen_storage_capex_cny_per_kg
    )
    return capex / result.npc_cny if result.npc_cny > 0 else float("nan")


def wind_surface_comparison(
    hourly_by_surface: dict, config: ScenarioConfig
) -> pd.DataFrame:
    """Compara superficies de NASA POWER contra el CF eolico del paper.

    ``hourly_by_surface`` mapea el alias de superficie al ano horario descargado
    con esa correccion de altura. La superficie adoptada es la que reproduce el
    40% que reporta el paper: se elige entre un catalogo cerrado de superficies
    fisicas documentadas, contra un objetivo externo, no ajustando un parametro
    continuo.
    """
    target = PAPER_TARGETS["wind_cf"].reported

    rows = []
    for surface, frame in hourly_by_surface.items():
        resource = resource_metrics(frame, config)
        case = simulate_base(frame, 190.0, 10.0, 95.0, config)
        rows.append(
            {
                "wind_surface": surface,
                "wind_cf": resource["wind_cf"],
                "desvio_cf_pp": (resource["wind_cf"] - target) * 100.0,
                "mean_hub_wind_speed": resource["mean_hub_wind_speed"],
                "lcoe_w190": case.lcoe_cny_per_kwh,
                "agsr_w190": case.agsr,
                "feasible_w190": case.feasible,
            }
        )
    comparison = pd.DataFrame(rows)
    return comparison.reindex(comparison["desvio_cf_pp"].abs().sort_values().index)
