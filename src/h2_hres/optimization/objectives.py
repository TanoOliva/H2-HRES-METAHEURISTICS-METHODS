"""Funcion objetivo de la extension discreta (celda 35 del notebook).

El objetivo es minimizar el LCOE sujeto a AGSR <= 20%. Las soluciones
infactibles reciben una penalizacion configurable en lugar de descartarse: la
penalizacion proporcional al exceso de AGSR da gradiente hacia la region
factible, mientras que un descarte plano deja al optimizador sin informacion
sobre cuan lejos esta de cumplir.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np

from ..config.schema import MetaheuristicConfig, ScenarioConfig
from ..models.profiles import GenerationProfileCache
from ..simulation.results import SimulationResult
from ..simulation.simulator import HourlyData, as_profile_cache, simulate_discrete
from .encoding import DecisionSpace, Design

__all__ = ["PenaltyPolicy", "Evaluation", "ObjectiveFunction"]


@dataclass(frozen=True)
class PenaltyPolicy:
    """Como se castiga la infactibilidad."""

    base: float = 1e6
    agsr_weight: float = 1e3

    @classmethod
    def from_config(cls, config: MetaheuristicConfig) -> "PenaltyPolicy":
        return cls(base=config.penalty_infeasible, agsr_weight=config.penalty_agsr_weight)

    def score(self, result: SimulationResult, agsr_max: float) -> float:
        """Puntaje a minimizar: LCOE si es factible, penalizacion si no."""
        if result.feasible:
            return result.lcoe_cny_per_kwh

        # Un AGSR NaN indica que la solucion ni siquiera llego a simularse (violo
        # una restriccion de capacidad); recibe solo la penalizacion base.
        if np.isnan(result.agsr):
            return self.base

        excess = max(result.agsr - agsr_max, 0.0)
        return self.base + self.agsr_weight * excess


@dataclass(frozen=True)
class Evaluation:
    """Una evaluacion completa: vector, diseno decodificado y resultado."""

    score: float
    design: Design
    result: SimulationResult

    def to_record(self) -> Dict[str, Any]:
        record = self.result.to_dict()
        record["score"] = self.score
        return record


class ObjectiveFunction:
    """Objetivo evaluable, con cache de perfiles y conteo de evaluaciones.

    Todos los optimizadores comparten esta instancia, de modo que compiten con
    el mismo modelo, el mismo cache y el mismo contador de presupuesto.
    """

    def __init__(
        self,
        hourly: HourlyData,
        config: ScenarioConfig,
        space: Optional[DecisionSpace] = None,
        penalty: Optional[PenaltyPolicy] = None,
    ) -> None:
        self.config = config
        self.cache: GenerationProfileCache = as_profile_cache(hourly, config)
        self.space = space if space is not None else DecisionSpace(config)
        self.penalty = (
            penalty
            if penalty is not None
            else PenaltyPolicy.from_config(config.metaheuristic)
        )
        self.n_evaluations = 0

    def __call__(self, x: np.ndarray) -> Evaluation:
        return self.evaluate(x)

    def evaluate(self, x: np.ndarray) -> Evaluation:
        design = self.space.decode(x)
        result = simulate_discrete(
            self.cache,
            wind_mw=design.wind_mw,
            n_electrolyzer_units=design.n_electrolyzer_units,
            battery_mw=design.battery_mw,
            battery_duration_h=design.battery_duration_h,
            config=self.config,
        )
        self.n_evaluations += 1
        score = self.penalty.score(result, self.config.constraints.agsr_max)
        return Evaluation(score=float(score), design=design, result=result)

    def reset_counter(self) -> None:
        self.n_evaluations = 0
