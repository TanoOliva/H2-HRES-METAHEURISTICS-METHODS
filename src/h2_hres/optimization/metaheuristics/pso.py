"""Particle Swarm Optimization (PSO) sobre el espacio mixto WPEB.

Igual que GWO, la particula vive en el espacio continuo y la proyeccion a
variables enteras y discretas ocurre al decodificar, en ``DecisionSpace``.
"""

from __future__ import annotations

import numpy as np

from .base import Optimizer

__all__ = ["ParticleSwarm"]


class ParticleSwarm(Optimizer):
    """PSO con constriccion de Clerc-Kennedy y velocidad acotada por variable.

    ``v = chi * (v + c1*r1*(pbest - x) + c2*r2*(gbest - x))``

    con ``chi = config.pso.inertia`` y ``c1 = c2`` los coeficientes cognitivo y
    social. Es la formulacion de constriccion, no la de peso de inercia clasico:
    el factor multiplica toda la suma, no solo la velocidad previa, y es lo que
    garantiza convergencia sin necesidad de decaer ``chi`` con las iteraciones.
    """

    name = "pso"

    def _search(self) -> None:
        space = self.space
        params = self.config.pso
        n_particles = self.config.population
        n_iterations = self.config.iterations

        positions = space.sample(self.rng, n_particles)
        velocity_range = params.velocity_clamp_ratio * (space.upper - space.lower)
        velocities = self.rng.uniform(
            -velocity_range, velocity_range, size=positions.shape
        )

        personal_best_positions = positions.copy()
        personal_best_scores = np.full(n_particles, np.inf)
        global_best_position = positions[0].copy()
        global_best_score = np.inf

        for iteration in range(n_iterations):
            for i in range(n_particles):
                positions[i] = space.clip(positions[i])
                score = self._evaluate(positions[i]).score
                if score < personal_best_scores[i]:
                    personal_best_scores[i] = score
                    personal_best_positions[i] = positions[i].copy()
                if score < global_best_score:
                    global_best_score = score
                    global_best_position = positions[i].copy()

            r1 = self.rng.random(positions.shape)
            r2 = self.rng.random(positions.shape)
            velocities = params.inertia * (
                velocities
                + params.cognitive * r1 * (personal_best_positions - positions)
                + params.social * r2 * (global_best_position[None, :] - positions)
            )
            velocities = np.clip(velocities, -velocity_range, velocity_range)
            positions = positions + velocities

            self._record(iteration + 1)
