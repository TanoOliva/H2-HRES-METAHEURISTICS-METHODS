"""Spotted Hyena Optimizer (SHO) sobre el espacio mixto WPEB.

Dhiman, G., & Kumar, V. (2017). *Spotted hyena optimizer: A novel bio-inspired
based metaheuristic technique for engineering applications.* Advances in
Engineering Software.

Estructuralmente es GWO con un solo lider ("prey", la mejor posicion conocida)
en vez de tres, y un coeficiente ``h`` que decae de ``h_max`` (5.0 por defecto)
a 0 en vez de 2 a 0 -- un rango de exploracion inicial mas amplio. Sigue la
actualizacion de posicion de la implementacion de referencia de los propios
autores (encierro directo sobre la presa); el paper describe ademas un paso de
"formacion de cluster" cuyo tamano no queda especificado de forma reproducible
y que la implementacion de referencia no usa, asi que no se replica aqui.
"""

from __future__ import annotations

import numpy as np

from .base import Optimizer

__all__ = ["SpottedHyenaOptimizer"]


class SpottedHyenaOptimizer(Optimizer):
    """SHO: encierro de toda la manada sobre la presa (mejor posicion conocida)."""

    name = "sho"

    def _search(self) -> None:
        space = self.space
        h_max = self.config.sho.h_max
        n_hyenas = self.config.population
        n_iterations = self.config.iterations

        positions = space.sample(self.rng, n_hyenas)
        prey = positions[0].copy()
        prey_score = np.inf

        for iteration in range(n_iterations):
            for i in range(n_hyenas):
                positions[i] = space.clip(positions[i])
                evaluation = self._evaluate(positions[i])
                if evaluation.score < prey_score:
                    prey_score = evaluation.score
                    prey = positions[i].copy()

            # h decae linealmente de h_max a 0: la manada pasa de explorar
            # ampliamente alrededor de la presa a converger sobre ella.
            h = h_max - iteration * (h_max / max(n_iterations - 1, 1))

            positions = self._move(positions, prey, h)

            self._record(iteration + 1, h=h)

    def _move(self, positions: np.ndarray, prey: np.ndarray, h: float) -> np.ndarray:
        """Encierro vectorizado de toda la manada sobre la presa."""
        r1 = self.rng.random(positions.shape)
        r2 = self.rng.random(positions.shape)

        B = 2.0 * r1
        E = 2.0 * h * r2 - h

        distance = np.abs(B * prey[None, :] - positions)
        return prey[None, :] - E * distance
