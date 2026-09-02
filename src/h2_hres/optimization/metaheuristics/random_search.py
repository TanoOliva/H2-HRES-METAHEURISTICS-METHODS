"""Busqueda aleatoria: linea base honesta (celda 38 del notebook).

Muestrea directamente sobre la malla discreta -- unidades enteras, potencias
multiplo del paso, duraciones del catalogo -- en lugar de muestrear continuo y
proyectar. Asi cada muestra es un diseno valido y la comparacion con las
metaheuristicas mide busqueda, no suerte en el redondeo.

Toda metaheuristica deberia superarla con el mismo presupuesto de evaluaciones;
si no lo hace, el problema esta mal planteado o el algoritmo mal ajustado.
"""

from __future__ import annotations

import numpy as np

from .base import Optimizer

__all__ = ["RandomSearch"]


class RandomSearch(Optimizer):
    """Muestreo uniforme sobre el espacio discreto, sin memoria."""

    name = "random"

    def _search(self) -> None:
        config = self.objective.config
        battery = config.battery
        electrolyzer = config.electrolyzer

        battery_grid = np.arange(
            battery.power_min_mw,
            battery.power_max_mw + 1e-9,
            battery.power_step_mw,
        )
        n_durations = len(battery.duration_candidates_h)
        total_capacity = config.constraints.total_generation_capacity_mw

        # Mismo presupuesto que los algoritmos poblacionales, para que la
        # comparacion sea a igual numero de evaluaciones.
        budget = self.config.evaluation_budget
        report_every = max(self.config.population, 1)

        for evaluation_index in range(budget):
            x = np.array(
                [
                    self.rng.uniform(0.0, total_capacity),
                    self.rng.integers(electrolyzer.min_units, electrolyzer.max_units + 1),
                    self.rng.choice(battery_grid),
                    self.rng.integers(0, n_durations),
                ],
                dtype=float,
            )
            self._evaluate(x)

            if (evaluation_index + 1) % report_every == 0:
                self._record((evaluation_index + 1) // report_every)

        # Garantiza una fila final aunque el presupuesto no sea multiplo exacto.
        if not self._history or self._history[-1]["n_evaluations"] < budget:
            self._record(len(self._history) + 1)
