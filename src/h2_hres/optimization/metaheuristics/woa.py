"""Whale Optimization Algorithm (WOA) sobre el espacio mixto WPEB.

Mirjalili, S., & Lewis, A. (2016). *The Whale Optimization Algorithm.*
Advances in Engineering Software.

Cada ballena sortea, una vez por iteracion, entre dos mecanismos con
probabilidad 50/50 -- igual que en la implementacion de referencia de los
propios autores, los coeficientes ``A``, ``C``, ``l`` y la moneda ``p`` son
escalares por ballena, no vectores por dimension:

- ``p < 0.5``: encierro sobre la mejor posicion conocida si ``|A| < 1``
  (explotacion), o sobre una ballena aleatoria de la manada si ``|A| >= 1``
  (exploracion) -- el mismo esquema de encierro que GWO y SHO.
- ``p >= 0.5``: actualizacion espiral tipo "bubble-net" alrededor de la mejor
  posicion conocida.

``a`` decae linealmente de 2 a 0, igual que en GWO. Al sortearse una moneda
distinta por ballena, el operador de movimiento no es vectorizable sobre toda
la poblacion a la vez como el de GWO; se recorre en un bucle, igual de
aceptable en costo que el de PSO/GA -- la simulacion horaria domina el
tiempo, no el operador de movimiento.
"""

from __future__ import annotations

import numpy as np

from .base import Optimizer

__all__ = ["WhaleOptimization"]


class WhaleOptimization(Optimizer):
    """WOA: encierro/busqueda aleatoria o espiral "bubble-net", sorteados por ballena."""

    name = "woa"

    def _search(self) -> None:
        space = self.space
        spiral_constant = self.config.woa.spiral_constant
        n_whales = self.config.population
        n_iterations = self.config.iterations

        positions = space.sample(self.rng, n_whales)
        best = positions[0].copy()
        best_score = np.inf

        for iteration in range(n_iterations):
            for i in range(n_whales):
                positions[i] = space.clip(positions[i])
                evaluation = self._evaluate(positions[i])
                if evaluation.score < best_score:
                    best_score = evaluation.score
                    best = positions[i].copy()

            a = 2.0 - iteration * (2.0 / max(n_iterations - 1, 1))

            positions = self._move(positions, best, a, spiral_constant)

            self._record(iteration + 1, a=a)

    def _move(
        self, positions: np.ndarray, best: np.ndarray, a: float, spiral_constant: float
    ) -> np.ndarray:
        """Nueva posicion de cada ballena, con coeficientes propios por ballena."""
        n_whales = len(positions)
        new_positions = np.empty_like(positions)

        for i in range(n_whales):
            r1 = self.rng.random()
            r2 = self.rng.random()
            A = 2.0 * a * r1 - a
            C = 2.0 * r2
            p = self.rng.random()

            if p < 0.5:
                if abs(A) < 1.0:
                    # Explotacion: encierro sobre la mejor posicion conocida.
                    distance = np.abs(C * best - positions[i])
                    new_positions[i] = best - A * distance
                else:
                    # Exploracion: encierro sobre una ballena aleatoria de la manada.
                    random_whale = positions[self.rng.integers(0, n_whales)]
                    distance = np.abs(C * random_whale - positions[i])
                    new_positions[i] = random_whale - A * distance
            else:
                # Ataque por burbujas: espiral logaritmica alrededor de la mejor posicion.
                l = self.rng.uniform(-1.0, 1.0)
                distance_to_best = np.abs(best - positions[i])
                new_positions[i] = (
                    distance_to_best * np.exp(spiral_constant * l) * np.cos(2.0 * np.pi * l)
                    + best
                )

        return new_positions
