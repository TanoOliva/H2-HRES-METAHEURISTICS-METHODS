"""Interfaz comun de los optimizadores.

Agregar una metaheuristica nueva (PSO, WOA, GA, LB2, hibridos) significa
escribir una subclase que implemente ``_search`` y registrarla en el REGISTRY.
Todo lo demas -- semilla, cache de perfiles, historial por iteracion, conteo de
evaluaciones, cronometraje -- lo aporta esta clase base, de modo que dos
algoritmos distintos produzcan historiales con el mismo formato y sean
comparables sin trabajo adicional.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from ...config.schema import MetaheuristicConfig
from ..objectives import Evaluation, ObjectiveFunction

__all__ = ["Optimizer", "OptimizationResult"]


@dataclass
class OptimizationResult:
    """Resultado de una corrida: la mejor solucion y como se llego a ella."""

    algorithm: str
    seed: int
    best: Evaluation
    history: pd.DataFrame
    n_evaluations: int
    elapsed_s: float

    @property
    def best_score(self) -> float:
        return self.best.score

    def summary(self) -> Dict[str, Any]:
        """Fila plana con lo esencial, para agregar varias corridas."""
        record = self.best.to_record()
        record.update(
            {
                "algorithm": self.algorithm,
                "seed": self.seed,
                "n_evaluations": self.n_evaluations,
                "elapsed_s": self.elapsed_s,
            }
        )
        return record


class Optimizer(ABC):
    """Base de todos los optimizadores sobre el espacio discreto WPEB."""

    name: str = "base"

    def __init__(
        self,
        objective: ObjectiveFunction,
        config: Optional[MetaheuristicConfig] = None,
        seed: Optional[int] = None,
    ) -> None:
        self.objective = objective
        self.config = config if config is not None else objective.config.metaheuristic
        self.seed = int(self.config.seed if seed is None else seed)
        self.rng = np.random.default_rng(self.seed)
        self.space = objective.space
        self.best: Optional[Evaluation] = None
        self._history: List[Dict[str, Any]] = []

    # -- utilidades para las subclases --------------------------------------

    def _evaluate(self, x: np.ndarray) -> Evaluation:
        """Evalua un vector y actualiza la mejor solucion conocida."""
        evaluation = self.objective.evaluate(x)
        if self.best is None or evaluation.score < self.best.score:
            self.best = evaluation
        return evaluation

    def _record(self, iteration: int, **extra: Any) -> None:
        """Anota el estado de la mejor solucion al cierre de una iteracion."""
        if self.best is None:
            raise RuntimeError("no se puede registrar antes de la primera evaluacion")

        result = self.best.result
        row: Dict[str, Any] = {
            "iteration": iteration,
            "best_score": self.best.score,
            "n_evaluations": self.objective.n_evaluations,
            "wind_mw": result.wind_mw,
            "pv_mw": result.pv_mw,
            "electrolyzer_mw": result.electrolyzer_mw,
            "n_electrolyzer_units": result.n_electrolyzer_units,
            "battery_mw": result.battery_mw,
            "battery_mwh": result.battery_mwh,
            "battery_duration_h": result.battery_duration_h,
            "feasible": result.feasible,
            "agsr": result.agsr,
            "electrolyzer_cf": result.electrolyzer_cf,
            "lcoe_cny_per_kwh": result.lcoe_cny_per_kwh,
            "lcoh_cny_per_kg": result.lcoh_cny_per_kg,
        }
        row.update(extra)
        self._history.append(row)

    # -- contrato -----------------------------------------------------------

    @abstractmethod
    def _search(self) -> None:
        """Ejecuta la busqueda, llamando a ``_evaluate`` y ``_record``."""

    def optimize(self) -> OptimizationResult:
        """Corre el algoritmo y devuelve el resultado con su historial."""
        self.objective.reset_counter()
        self.best = None
        self._history = []

        started = time.perf_counter()
        self._search()
        elapsed = time.perf_counter() - started

        if self.best is None:
            raise RuntimeError(
                "{} termino sin evaluar ninguna solucion".format(self.name)
            )

        return OptimizationResult(
            algorithm=self.name,
            seed=self.seed,
            best=self.best,
            history=pd.DataFrame(self._history),
            n_evaluations=self.objective.n_evaluations,
            elapsed_s=elapsed,
        )
