"""Algoritmo genetico de codificacion real sobre el espacio mixto WPEB.

Seleccion por torneo, cruce BLX-alpha, mutacion gaussiana y elitismo. Los
individuos de elite se reevaluan en la generacion siguiente -- desperdicia unas
pocas evaluaciones -- pero mantener el presupuesto identico al de los demas
algoritmos (``population * iterations``) importa mas que ahorrarlas: es lo que
hace comparable la comparativa.
"""

from __future__ import annotations

import numpy as np

from ...config.schema import GAConfig
from ..encoding import DecisionSpace
from .base import Optimizer

__all__ = ["GeneticAlgorithm"]


class GeneticAlgorithm(Optimizer):
    """GA real-coded: torneo + BLX-alpha + mutacion gaussiana + elitismo."""

    name = "ga"

    def _search(self) -> None:
        space = self.space
        params = self.config.ga
        n_pop = self.config.population
        n_iterations = self.config.iterations

        positions = space.sample(self.rng, n_pop)

        for generation in range(n_iterations):
            scores = np.empty(n_pop)
            for i in range(n_pop):
                positions[i] = space.clip(positions[i])
                scores[i] = self._evaluate(positions[i]).score

            positions = self._next_generation(positions, scores, params, space)

            self._record(generation + 1)

    def _next_generation(
        self,
        positions: np.ndarray,
        scores: np.ndarray,
        params: GAConfig,
        space: DecisionSpace,
    ) -> np.ndarray:
        n_pop = len(positions)
        order = np.argsort(scores)
        elite_count = min(params.elite_count, n_pop)

        new_positions = np.empty_like(positions)
        new_positions[:elite_count] = positions[order[:elite_count]]

        for i in range(elite_count, n_pop):
            parent_a = self._tournament_select(positions, scores, params.tournament_size)
            parent_b = self._tournament_select(positions, scores, params.tournament_size)

            if self.rng.random() < params.crossover_rate:
                child = self._crossover(parent_a, parent_b)
            else:
                child = parent_a.copy()

            child = self._mutate(child, params, space)
            new_positions[i] = space.clip(child)

        return new_positions

    def _tournament_select(
        self, positions: np.ndarray, scores: np.ndarray, tournament_size: int
    ) -> np.ndarray:
        """Elige el mejor de ``tournament_size`` individuos tomados al azar."""
        contenders = self.rng.choice(len(positions), size=tournament_size, replace=False)
        winner = contenders[np.argmin(scores[contenders])]
        return positions[winner]

    def _crossover(self, parent_a: np.ndarray, parent_b: np.ndarray, alpha: float = 0.5) -> np.ndarray:
        """Cruce BLX-alpha: muestrea uniforme en un intervalo expandido entre padres."""
        low = np.minimum(parent_a, parent_b)
        high = np.maximum(parent_a, parent_b)
        span = high - low
        return self.rng.uniform(low - alpha * span, high + alpha * span)

    def _mutate(self, individual: np.ndarray, params: GAConfig, space: DecisionSpace) -> np.ndarray:
        """Mutacion gaussiana gen a gen, con sigma proporcional al rango de cada variable."""
        sigma = params.mutation_sigma_ratio * (space.upper - space.lower)
        mask = self.rng.random(individual.shape) < params.mutation_rate
        noise = self.rng.normal(0.0, sigma)
        return np.where(mask, individual + noise, individual)
