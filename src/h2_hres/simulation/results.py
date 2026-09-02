"""Resultado de una simulacion anual del sistema WPEB.

El notebook tenia dos dataclasses -- ``SimulationResult`` (celda 15) y
``ExtendedSimulationResult`` (celda 34) -- con campos solapados pero distintos,
lo que impedia comparar en una misma tabla el modelo base y el discreto. Aqui
hay una sola estructura, superconjunto de ambas: el modelo base simplemente
deriva ``n_electrolyzer_units`` y ``battery_duration_h`` de su parametrizacion.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict

__all__ = ["SimulationResult", "infeasible_result"]


@dataclass(frozen=True)
class SimulationResult:
    """Metricas anuales de una configuracion de capacidades."""

    # -- capacidades --------------------------------------------------------
    wind_mw: float
    pv_mw: float
    electrolyzer_mw: float
    n_electrolyzer_units: int
    battery_mw: float
    battery_mwh: float
    battery_duration_h: float

    # -- factibilidad -------------------------------------------------------
    feasible: bool
    agsr: float
    # Vacio si la solucion es factible. El notebook devolvia feasible=False sin
    # explicar cual de las cinco restricciones se habia violado.
    infeasibility_reason: str = ""

    # -- energia (MWh/ano) --------------------------------------------------
    total_wind_mwh: float = 0.0
    total_pv_mwh: float = 0.0
    total_renewable_mwh: float = 0.0
    total_grid_sales_mwh: float = 0.0
    total_electrolyzer_load_mwh: float = 0.0
    total_curtailment_mwh: float = 0.0
    battery_throughput_mwh: float = 0.0

    # -- desempeno ----------------------------------------------------------
    electrolyzer_cf: float = 0.0
    total_h2_kg: float = 0.0

    # -- economia (CNY) -----------------------------------------------------
    npc_cny: float = 0.0
    annualized_cost_cny: float = 0.0
    lcoe_cny_per_kwh: float = float("inf")
    lcoh_cny_per_kg: float = float("inf")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def infeasible_result(
    wind_mw: float,
    pv_mw: float,
    electrolyzer_mw: float,
    n_electrolyzer_units: int,
    battery_mw: float,
    battery_mwh: float,
    battery_duration_h: float,
    reason: str,
) -> SimulationResult:
    """Resultado nulo para una configuracion que viola una restriccion.

    No se simula: las capacidades quedan registradas junto al motivo del
    rechazo, y los costos nivelados se fijan en infinito para que nunca ganen
    una comparacion por minimo.
    """
    return SimulationResult(
        wind_mw=wind_mw,
        pv_mw=pv_mw,
        electrolyzer_mw=electrolyzer_mw,
        n_electrolyzer_units=n_electrolyzer_units,
        battery_mw=battery_mw,
        battery_mwh=battery_mwh,
        battery_duration_h=battery_duration_h,
        feasible=False,
        agsr=float("nan"),
        infeasibility_reason=reason,
    )
