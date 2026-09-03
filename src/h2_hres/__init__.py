"""h2_hres -- replicacion y extension discreta del sistema WPEB.

Modularizacion del notebook ``WPEB_trabajo1_metaheuristics_colab.ipynb``, que
replica Li et al. (2024), *Capacity optimization of a wind-photovoltaic-
electrolysis-battery (WPEB) hybrid energy system for power and hydrogen
generation*, y lo extiende con una formulacion discreta resuelta por
metaheuristicas.
"""

from .config import ScenarioConfig, default_scenario, load_scenario

__version__ = "0.3.0"

__all__ = ["ScenarioConfig", "default_scenario", "load_scenario", "__version__"]
