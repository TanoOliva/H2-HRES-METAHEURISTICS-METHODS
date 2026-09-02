"""Modelo de generacion eolica (celda 13 del notebook)."""

from __future__ import annotations

import numpy as np

from ..config.schema import WindConfig

__all__ = ["wind_turbine_power_mw", "aggregate_wind_power_mw"]


def wind_turbine_power_mw(
    wind_speed_ms: np.ndarray,
    rated_mw: float,
    cut_in_ms: float,
    rated_ms: float,
    cut_out_ms: float,
) -> np.ndarray:
    """Potencia de UNA turbina, con curva cubica simplificada.

    Tres regimenes: nula bajo cut-in y sobre cut-out, cubica normalizada entre
    cut-in y la velocidad nominal, y potencia nominal constante entre esa
    velocidad y cut-out.
    """
    ws = np.asarray(wind_speed_ms, dtype=float)
    p = np.zeros_like(ws, dtype=float)

    ramp = (ws >= cut_in_ms) & (ws < rated_ms)
    plateau = (ws >= rated_ms) & (ws < cut_out_ms)

    p[ramp] = rated_mw * (
        (ws[ramp] ** 3 - cut_in_ms ** 3) / (rated_ms ** 3 - cut_in_ms ** 3)
    )
    p[plateau] = rated_mw

    return np.clip(p, 0.0, rated_mw)


def aggregate_wind_power_mw(
    wind_speed_ms: np.ndarray, wind_capacity_mw: float, config: WindConfig
) -> np.ndarray:
    """Potencia del parque completo.

    El numero de turbinas se redondea al entero mas cercano, y la salida se
    satura a ``wind_capacity_mw`` para que el redondeo hacia arriba no genere
    mas potencia que la capacidad nominal declarada.
    """
    n_turbines = max(int(round(wind_capacity_mw / config.turbine_rated_mw)), 0)
    single = wind_turbine_power_mw(
        wind_speed_ms,
        rated_mw=config.turbine_rated_mw,
        cut_in_ms=config.cut_in_ms,
        rated_ms=config.rated_ms,
        cut_out_ms=config.cut_out_ms,
    )
    return np.minimum(single * n_turbines, wind_capacity_mw)
