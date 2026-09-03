"""Metaheuristicas disponibles.

Para agregar una nueva: escribir la subclase de ``Optimizer``, importarla aqui
y anadirla al REGISTRY. Queda inmediatamente disponible en la CLI mediante
``--algorithm <nombre>`` y en las comparaciones estadisticas.
"""

from typing import Dict, Type

from .base import OptimizationResult, Optimizer
from .ga import GeneticAlgorithm
from .gwo import GreyWolfOptimizer
from .pso import ParticleSwarm
from .random_search import RandomSearch

REGISTRY: Dict[str, Type[Optimizer]] = {
    GreyWolfOptimizer.name: GreyWolfOptimizer,
    ParticleSwarm.name: ParticleSwarm,
    GeneticAlgorithm.name: GeneticAlgorithm,
    RandomSearch.name: RandomSearch,
}


def get_optimizer(name: str) -> Type[Optimizer]:
    """Busca un optimizador por nombre, con un error util si no existe."""
    try:
        return REGISTRY[name]
    except KeyError:
        raise KeyError(
            "algoritmo desconocido '{}'. Disponibles: {}".format(
                name, ", ".join(sorted(REGISTRY))
            )
        ) from None


__all__ = [
    "REGISTRY",
    "GeneticAlgorithm",
    "GreyWolfOptimizer",
    "OptimizationResult",
    "Optimizer",
    "ParticleSwarm",
    "RandomSearch",
    "get_optimizer",
]
