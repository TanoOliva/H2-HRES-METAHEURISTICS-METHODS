"""Cache de perfiles de generacion.

En el notebook, ``run_grid_search`` recalculaba los perfiles eolico y
fotovoltaico para cada valor de electrolizador, aunque la capacidad de
generacion no cambiara: 21 valores de viento x 20 de electrolizador implicaban
420 evaluaciones del modelo de generacion cuando bastaban 21. Aqui se memoiza
por par (wind_mw, pv_mw). El resultado numerico es identico.
"""

from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
import pandas as pd

from ..config.schema import ScenarioConfig
from .pv import pv_power_mw
from .wind import aggregate_wind_power_mw

__all__ = ["GenerationProfileCache", "REQUIRED_COLUMNS"]

# ``wsc_ms`` es la velocidad a la altura de buje que entrega NASA POWER. Los
# datos descargados antes de esa correccion solo traen ``ws50m``; en ese caso se
# avisa y se usa la velocidad a 50 m, que subestima el recurso.
REQUIRED_COLUMNS = ("ghi_kwh_m2", "t2m_c")
HUB_WIND_COLUMN = "wsc_ms"
MEASURED_WIND_COLUMN = "ws50m"

# Las capacidades vienen de mallas discretas y de redondeos del optimizador;
# se cuantizan antes de indexar para que 190.0 y 190.0000000001 compartan
# entrada de cache.
_QUANTUM_MW = 1e-6


class GenerationProfileCache:
    """Perfiles horarios de generacion para un ano meteorologico dado."""

    def __init__(self, hourly: pd.DataFrame, config: ScenarioConfig) -> None:
        missing = [c for c in REQUIRED_COLUMNS if c not in hourly.columns]
        if missing:
            raise ValueError(
                "faltan columnas en los datos horarios: {}. Se esperaban {}".format(
                    missing, list(REQUIRED_COLUMNS)
                )
            )

        wind_column = self._resolve_wind_column(hourly, config)

        self._config = config
        self._n_hours = len(hourly)
        self._wind_column = wind_column
        self._wind_speed = np.ascontiguousarray(
            hourly[wind_column].to_numpy(dtype=float)
        )
        self._ghi = np.ascontiguousarray(hourly["ghi_kwh_m2"].to_numpy(dtype=float))
        self._temperature = np.ascontiguousarray(hourly["t2m_c"].to_numpy(dtype=float))

        self._wind_cache: Dict[int, np.ndarray] = {}
        self._pv_cache: Dict[int, np.ndarray] = {}
        self._total_cache: Dict[Tuple[int, int], np.ndarray] = {}
        self.hits = 0
        self.misses = 0

    @staticmethod
    def _resolve_wind_column(hourly: pd.DataFrame, config: ScenarioConfig) -> str:
        """Elige la serie de viento segun ``wind.wind_speed_source``."""
        if config.wind.wind_speed_source == "hub_height":
            if HUB_WIND_COLUMN in hourly.columns:
                return HUB_WIND_COLUMN
            raise ValueError(
                "el escenario pide viento a altura de buje pero los datos no "
                "traen la columna '{}'. Volver a descargar con "
                "'h2hres download --force'.".format(HUB_WIND_COLUMN)
            )

        if MEASURED_WIND_COLUMN in hourly.columns:
            return MEASURED_WIND_COLUMN
        raise ValueError(
            "los datos horarios no traen la columna '{}'".format(MEASURED_WIND_COLUMN)
        )

    @property
    def n_hours(self) -> int:
        return self._n_hours

    @property
    def wind_column(self) -> str:
        """Columna de viento efectivamente usada: util para auditar una corrida."""
        return self._wind_column

    @staticmethod
    def _key(capacity_mw: float) -> int:
        return int(round(capacity_mw / _QUANTUM_MW))

    def wind(self, wind_mw: float) -> np.ndarray:
        key = self._key(wind_mw)
        profile = self._wind_cache.get(key)
        if profile is None:
            profile = aggregate_wind_power_mw(
                self._wind_speed, wind_mw, self._config.wind
            )
            self._wind_cache[key] = profile
        return profile

    def pv(self, pv_mw: float) -> np.ndarray:
        key = self._key(pv_mw)
        profile = self._pv_cache.get(key)
        if profile is None:
            profile = pv_power_mw(
                self._ghi,
                self._temperature,
                pv_mw,
                self._config.pv,
                inverter_efficiency=self._config.converter.inverter_efficiency,
            )
            self._pv_cache[key] = profile
        return profile

    def total(self, wind_mw: float, pv_mw: float) -> np.ndarray:
        """Generacion renovable agregada, lista para el despacho."""
        key = (self._key(wind_mw), self._key(pv_mw))
        profile = self._total_cache.get(key)
        if profile is None:
            self.misses += 1
            profile = np.ascontiguousarray(self.wind(wind_mw) + self.pv(pv_mw))
            self._total_cache[key] = profile
        else:
            self.hits += 1
        return profile

    def stats(self) -> Dict[str, int]:
        """Aciertos y fallos de cache; util para dimensionar corridas largas."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "wind_profiles": len(self._wind_cache),
            "pv_profiles": len(self._pv_cache),
        }
