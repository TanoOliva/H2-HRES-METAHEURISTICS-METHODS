"""Grey Wolf Optimizer sobre el espacio mixto WPEB (celda 37 del notebook).

La posicion interna de cada lobo es continua; la proyeccion a variables enteras
y discretas ocurre al decodificar, en ``DecisionSpace``. Es el esquema habitual
para aplicar GWO a un problema mixto sin reescribir el operador de movimiento.
"""

from __future__ import annotations

import numpy as np

from .base import Optimizer

__all__ = ["GreyWolfOptimizer"]


class GreyWolfOptimizer(Optimizer):
    """GWO clasico: la jerarquia alpha-beta-delta guia al resto de la manada."""

    name = "gwo"

    def _search(self) -> None:
        space = self.space
        n_wolves = self.config.population
        n_iterations = self.config.iterations

        positions = space.sample(self.rng, n_wolves)

        # Las tres mejores posiciones conocidas. Se guardan aparte de
        # ``self.best`` porque el movimiento del GWO necesita las tres.
        leaders = np.zeros((3, space.n_dimensions), dtype=float)
        leader_scores = np.full(3, np.inf)

        for iteration in range(n_iterations):
            for i in range(n_wolves):
                positions[i] = space.clip(positions[i])
                evaluation = self._evaluate(positions[i])
                self._update_leaders(leaders, leader_scores, positions[i], evaluation.score)

            # El coeficiente ``a`` decae linealmente de 2 a 0: la manada pasa de
            # explorar a explotar alrededor de los lideres.
            a = 2.0 - iteration * (2.0 / max(n_iterations - 1, 1))

            positions = self._move(positions, leaders, a)

            self._record(iteration + 1, a=a)

    @staticmethod
    def _update_leaders(
        leaders: np.ndarray,
        leader_scores: np.ndarray,
        position: np.ndarray,
        score: float,
    ) -> None:
        """Inserta una posicion en la jerarquia alpha-beta-delta si corresponde."""
        if score < leader_scores[0]:
            leaders[2] = leaders[1]
            leader_scores[2] = leader_scores[1]
            leaders[1] = leaders[0]
            leader_scores[1] = leader_scores[0]
            leaders[0] = position.copy()
            leader_scores[0] = score
        elif score < leader_scores[1]:
            leaders[2] = leaders[1]
            leader_scores[2] = leader_scores[1]
            leaders[1] = position.copy()
            leader_scores[1] = score
        elif score < leader_scores[2]:
            leaders[2] = position.copy()
            leader_scores[2] = score

    def _move(self, positions: np.ndarray, leaders: np.ndarray, a: float) -> np.ndarray:
        """Nueva posicion de cada lobo: promedio de los tres tirones de lider.

        Vectorizado sobre lobos y dimensiones. El notebook usaba un bucle
        anidado; el resultado estadistico es el mismo pero el consumo de numeros
        aleatorios difiere, de modo que las trayectorias no son comparables
        semilla a semilla con las del notebook.
        """
        n_wolves, n_dimensions = positions.shape
        shape = (3, n_wolves, n_dimensions)

        r1 = self.rng.random(shape)
        r2 = self.rng.random(shape)

        A = 2.0 * a * r1 - a
        C = 2.0 * r2

        # leaders[:, None, :] difunde los 3 lideres sobre toda la manada.
        distance = np.abs(C * leaders[:, None, :] - positions[None, :, :])
        candidates = leaders[:, None, :] - A * distance

        return candidates.mean(axis=0)
