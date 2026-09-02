"""Modelo de generacion fotovoltaica (celda 13 del notebook)."""

from __future__ import annotations

import numpy as np

from ..config.schema import PVConfig

__all__ = ["pv_power_mw", "cell_temperature_c"]


def cell_temperature_c(
    ghi_kwh_m2: np.ndarray, ambient_c: np.ndarray, config: PVConfig
) -> np.ndarray:
    """Temperatura de celda, aproximacion tipo NOCT."""
    ghi = np.asarray(ghi_kwh_m2, dtype=float)
    t_amb = np.asarray(ambient_c, dtype=float)
    return t_amb + (config.noct_c - 20.0) / 0.8 * ghi


def pv_power_mw(
    ghi_kwh_m2: np.ndarray,
    ambient_c: np.ndarray,
    pv_ac_capacity_mw: float,
    config: PVConfig,
    inverter_efficiency: float = 1.0,
) -> np.ndarray:
    """Potencia AC del campo fotovoltaico.

    La GHI horaria en kWh/m2 se interpreta como irradiancia media en kW/m2, de
    modo que su valor coincide numericamente con la produccion relativa antes de
    perdidas. Se aplican derating y correccion termica sobre la capacidad DC.

    La capacidad DC es ``pv_ac_capacity_mw * dc_ac_ratio``: el campo tiene mas
    modulos que la potencia nominal del inversor (Tabla 3 del paper: 96.15 MW DC
    para 80 MW AC, ratio 1.2). El exceso se recorta en el inversor -- *clipping*
    -- lo que aumenta la produccion en horas de irradiancia media sin superar
    nunca la capacidad AC.
    """
    ghi = np.asarray(ghi_kwh_m2, dtype=float)
    t_cell = cell_temperature_c(ghi, ambient_c, config)

    gamma = config.temp_coeff_pct_per_c / 100.0
    temp_factor = 1.0 + gamma * (t_cell - 25.0)

    relative = ghi * config.derating_factor * np.maximum(temp_factor, 0.0)

    dc_capacity_mw = pv_ac_capacity_mw * config.dc_ac_ratio
    power_dc = dc_capacity_mw * np.maximum(relative, 0.0)

    power_ac = power_dc * inverter_efficiency
    return np.minimum(power_ac, pv_ac_capacity_mw)
