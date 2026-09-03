"""Corre varias metaheuristicas sobre el mismo objetivo y junta sus resultados.

Un solo lugar para el bucle algoritmo x semilla evita que el subcomando
``compare`` de la CLI y el generador de reporte (``analysis/report.py``)
diverjan en como arman el historial y el resumen de corridas.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Sequence, Tuple

import pandas as pd

from .metaheuristics import OptimizationResult, get_optimizer
from .objectives import ObjectiveFunction

__all__ = ["run_comparison"]


def run_comparison(
    objective: ObjectiveFunction,
    algorithms: Sequence[str],
    seeds: Sequence[int],
    on_result: Optional[Callable[[str, int, OptimizationResult], None]] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Corre cada algoritmo sobre cada semilla y devuelve ``(history, runs)``.

    Todos los algoritmos comparten ``objective`` -- y por lo tanto el mismo
    cache de perfiles de generacion -- y las mismas semillas, para que la
    comparacion no arrastre diferencias de datos ni de presupuesto.

    ``on_result`` se llama tras cada corrida con ``(algoritmo, semilla,
    resultado)``; sirve para que quien orquesta (la CLI, el reporte) imprima
    progreso sin que esta funcion haga I/O por su cuenta.
    """
    histories: List[pd.DataFrame] = []
    summaries: List[Dict[str, object]] = []

    for algorithm in algorithms:
        optimizer_class = get_optimizer(algorithm)
        for seed in seeds:
            result = optimizer_class(objective, seed=seed).optimize()
            history = result.history.copy()
            history["algorithm"] = algorithm
            history["seed"] = seed
            histories.append(history)
            summaries.append(result.summary())
            if on_result is not None:
                on_result(algorithm, seed, result)

    all_history = pd.concat(histories, ignore_index=True)
    runs = pd.DataFrame(summaries)
    return all_history, runs
