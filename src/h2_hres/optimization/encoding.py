"""Espacio de decision de la extension discreta (celda 35 del notebook).

Los optimizadores poblacionales trabajan sobre un vector continuo; la
proyeccion al espacio mixto real -- entero para las unidades de electrolisis,
multiplo de un paso para la potencia de bateria, indice de catalogo para la
duracion -- ocurre aqui, en un solo lugar.

Centralizarlo importa: mientras los limites vivan dentro de cada algoritmo,
agregar PSO o WOA obliga a reescribirlos, y cualquier discrepancia hace que dos
algoritmos exploren espacios distintos y sus resultados dejen de ser comparables.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import numpy as np

from ..config.schema import ScenarioConfig

__all__ = ["Design", "DecisionSpace"]


@dataclass(frozen=True)
class Design:
    """Un diseno concreto, ya proyectado al espacio factible."""

    wind_mw: float
    pv_mw: float
    n_electrolyzer_units: int
    electrolyzer_mw: float
    battery_mw: float
    battery_duration_h: float
    battery_mwh: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "wind_mw": self.wind_mw,
            "pv_mw": self.pv_mw,
            "n_electrolyzer_units": self.n_electrolyzer_units,
            "electrolyzer_mw": self.electrolyzer_mw,
            "battery_mw": self.battery_mw,
            "battery_duration_h": self.battery_duration_h,
            "battery_mwh": self.battery_mwh,
        }


class DecisionSpace:
    """Limites y decodificacion del vector de decision.

    Componentes del vector:

    ``x[0]``
        capacidad eolica en MW (continua); la PV es el complemento a la
        capacidad total fija
    ``x[1]``
        numero de unidades de electrolisis (entera, se redondea)
    ``x[2]``
        potencia de bateria en MW (se proyecta al multiplo de paso mas cercano)
    ``x[3]``
        indice del catalogo de duraciones (entera, se redondea)
    """

    VARIABLE_NAMES = (
        "wind_mw",
        "n_electrolyzer_units",
        "battery_mw",
        "battery_duration_index",
    )

    def __init__(self, config: ScenarioConfig) -> None:
        self.config = config
        electrolyzer = config.electrolyzer
        battery = config.battery
        constraints = config.constraints

        self.lower = np.array(
            [0.0, electrolyzer.min_units, battery.power_min_mw, 0.0], dtype=float
        )
        self.upper = np.array(
            [
                constraints.total_generation_capacity_mw,
                electrolyzer.max_units,
                battery.power_max_mw,
                len(battery.duration_candidates_h) - 1,
            ],
            dtype=float,
        )

    @property
    def n_dimensions(self) -> int:
        return len(self.lower)

    def clip(self, x: np.ndarray) -> np.ndarray:
        return np.clip(np.asarray(x, dtype=float), self.lower, self.upper)

    def decode(self, x: np.ndarray) -> Design:
        """Proyecta un vector continuo al diseno discreto mas cercano."""
        config = self.config
        battery = config.battery
        electrolyzer = config.electrolyzer
        total_capacity = config.constraints.total_generation_capacity_mw

        x = self.clip(x)

        wind_mw = float(x[0])
        pv_mw = total_capacity - wind_mw

        units = int(
            np.clip(round(float(x[1])), electrolyzer.min_units, electrolyzer.max_units)
        )

        step = battery.power_step_mw
        battery_mw = float(
            np.clip(
                round(float(x[2]) / step) * step,
                battery.power_min_mw,
                battery.power_max_mw,
            )
        )

        candidates = battery.duration_candidates_h
        index = int(np.clip(round(float(x[3])), 0, len(candidates) - 1))
        duration_h = float(candidates[index])

        return Design(
            wind_mw=wind_mw,
            pv_mw=pv_mw,
            n_electrolyzer_units=units,
            electrolyzer_mw=units * electrolyzer.unit_mw,
            battery_mw=battery_mw,
            battery_duration_h=duration_h,
            battery_mwh=battery_mw * duration_h,
        )

    def sample(self, rng: np.random.Generator, size: int) -> np.ndarray:
        """Poblacion inicial uniforme dentro de los limites."""
        return rng.uniform(self.lower, self.upper, size=(size, self.n_dimensions))

    def warnings(self) -> List[str]:
        """Avisos de modelado, no errores de configuracion.

        El caso importante: si la duracion de la bateria es variable de decision
        pero no tiene costo por energia, alargarla es gratis y el optimizador la
        llevara al maximo sin que ese resultado signifique nada.
        """
        messages = []
        battery = self.config.battery
        if len(battery.duration_candidates_h) > 1 and not self.config.costs.battery.has_energy_cost:
            messages.append(
                "la duracion de bateria es variable de decision ({} candidatas) pero "
                "costs.battery no tiene componente por kWh: alargar la bateria no "
                "cuesta nada y el optimo en duracion no es interpretable. "
                "Definir capex_cny_per_kwh o fijar una sola duracion.".format(
                    len(battery.duration_candidates_h)
                )
            )
        return messages
