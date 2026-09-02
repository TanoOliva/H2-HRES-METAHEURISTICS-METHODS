"""Despacho horario del sistema WPEB.

Unifica las dos logicas de carga minima que el notebook tenia duplicadas e
inconsistentes entre el modelo base (celda 15) y el extendido (celda 34):

``TOP_UP`` (base)
    El electrolizador toma toda la generacion disponible; si queda por debajo
    de la carga minima, la bateria intenta completar el deficit. Si aun asi no
    llega, se apaga y la descarga se revierte.

``THRESHOLD`` (extendida)
    Si la generacion por si sola alcanza la carga minima, el electrolizador
    opera. Si no, la bateria intenta sostener el minimo; si no puede, se apaga
    sin descargar nada.

Ambas viven en un unico nucleo para que sus resultados sigan siendo
comparables. El nucleo es una funcion pura -- sin pandas ni dataclasses -- que
acumula en listas de Python: esa forma es rapida en CPython y ademas compilable
con numba cuando la plataforma lo permite.
"""

from __future__ import annotations

from enum import IntEnum
from typing import NamedTuple, Optional

import numpy as np

__all__ = [
    "MinLoadPolicy",
    "DispatchResult",
    "dispatch_hourly",
    "NUMBA_AVAILABLE",
    "NUMBA_STATUS",
]


class MinLoadPolicy(IntEnum):
    """Regla de operacion del electrolizador bajo la carga minima."""

    TOP_UP = 0  # modelo base, celda 15
    THRESHOLD = 1  # extension discreta, celda 34


class DispatchResult(NamedTuple):
    """Series horarias resultantes del despacho, en MW."""

    electrolyzer_load: np.ndarray
    grid_sales: np.ndarray
    battery_charge: np.ndarray
    battery_discharge: np.ndarray
    curtailment: np.ndarray
    state_of_charge: np.ndarray  # MWh al cierre de cada hora


# Centinela: numba no admite Optional[float] en modo nopython, asi que cualquier
# valor negativo del limite de exportacion significa "sin limite".
_NO_GRID_LIMIT = -1.0


def _dispatch_core(
    generation_mw,
    electrolyzer_mw: float,
    min_load_mw: float,
    battery_power_mw: float,
    battery_energy_mwh: float,
    eta_charge: float,
    eta_discharge: float,
    policy: int,
    grid_export_limit_mw: float,
):
    """Bucle secuencial sobre el estado de carga.

    Es secuencial por naturaleza -- el SOC de cada hora depende de la anterior --
    de modo que no se puede vectorizar sin cambiar el modelo. Por eso se aisla
    aqui: es el unico punto caliente del simulador.

    ``generation_mw`` puede ser una lista de floats (ruta CPython) o un array
    de NumPy (ruta numba); ambas se indexan igual.
    """
    n = len(generation_mw)

    electrolyzer_load = []
    grid_sales = []
    battery_charge = []
    battery_discharge = []
    curtailment = []
    state_of_charge = []

    soc = 0.0

    for t in range(n):
        generation = generation_mw[t]
        load = 0.0
        discharge = 0.0
        charge = 0.0
        exported = 0.0
        curtailed = 0.0

        if policy == 0:
            # TOP_UP: consumir todo lo posible y completar con bateria si el
            # resultado cae bajo la carga minima.
            load = generation if generation < electrolyzer_mw else electrolyzer_mw
            if 0.0 < load < min_load_mw:
                deficit = min_load_mw - load
                available = soc * eta_discharge
                if battery_power_mw < available:
                    available = battery_power_mw
                discharge = deficit if deficit < available else available
                load += discharge
                if load < min_load_mw:
                    # No se alcanza el minimo: se apaga y se revierte la descarga.
                    load = 0.0
                    discharge = 0.0
        else:
            # THRESHOLD: operar solo si el minimo es alcanzable.
            if generation >= min_load_mw and electrolyzer_mw > 0.0:
                load = generation if generation < electrolyzer_mw else electrolyzer_mw
            elif electrolyzer_mw > 0.0 and battery_power_mw > 0.0 and soc > 0.0:
                available = soc * eta_discharge
                if battery_power_mw < available:
                    available = battery_power_mw
                if generation + available >= min_load_mw:
                    headroom = electrolyzer_mw - generation
                    discharge = available if available < headroom else headroom
                    if discharge < 0.0:
                        discharge = 0.0
                    load = generation + discharge
                    if load > electrolyzer_mw:
                        load = electrolyzer_mw

        if discharge > 0.0:
            soc -= discharge / eta_discharge
            if soc < 0.0:
                soc = 0.0

        surplus = generation + discharge - load
        if surplus < 0.0:
            surplus = 0.0

        # Cargar la bateria con el excedente antes de exportar.
        if surplus > 1e-12 and battery_power_mw > 0.0 and battery_energy_mwh > 0.0:
            room = (battery_energy_mwh - soc) / eta_charge
            if room < 0.0:
                room = 0.0
            charge = surplus if surplus < battery_power_mw else battery_power_mw
            if room < charge:
                charge = room
            if charge > 0.0:
                soc += charge * eta_charge
                surplus -= charge
            else:
                charge = 0.0

        # Exportar el remanente, recortando lo que exceda el limite de conexion.
        if surplus > 1e-12:
            if grid_export_limit_mw < 0.0:
                exported = surplus
            else:
                exported = (
                    surplus if surplus < grid_export_limit_mw else grid_export_limit_mw
                )
                curtailed = surplus - exported

        electrolyzer_load.append(load)
        grid_sales.append(exported)
        battery_charge.append(charge)
        battery_discharge.append(discharge)
        curtailment.append(curtailed)
        state_of_charge.append(soc)

    return (
        electrolyzer_load,
        grid_sales,
        battery_charge,
        battery_discharge,
        curtailment,
        state_of_charge,
    )


# Compilacion opcional. numba es un extra (``pip install -e .[fast]``), nunca una
# dependencia dura: sin el se usa exactamente la misma funcion en CPython y los
# resultados son identicos bit a bit. La compilacion puede fallar tambien por
# politicas del sistema -- por ejemplo, Windows Application Control bloqueando la
# DLL nativa de numba -- por eso se captura cualquier excepcion y se guarda el
# motivo en NUMBA_STATUS en lugar de propagarlo.
_dispatch_core_python = _dispatch_core

try:  # pragma: no cover - depende del entorno
    from numba import njit

    _dispatch_core = njit(cache=True)(_dispatch_core)
    NUMBA_AVAILABLE = True
    NUMBA_STATUS = "numba activo"
except Exception as _exc:  # pragma: no cover - numba ausente o bloqueado
    NUMBA_AVAILABLE = False
    NUMBA_STATUS = "numba no disponible ({}: {})".format(
        type(_exc).__name__, str(_exc)[:120]
    )


def dispatch_hourly(
    generation_mw: np.ndarray,
    electrolyzer_mw: float,
    min_load_ratio: float,
    battery_power_mw: float,
    battery_energy_mwh: float,
    eta_charge: float,
    eta_discharge: float,
    policy: MinLoadPolicy = MinLoadPolicy.TOP_UP,
    grid_export_limit_mw: Optional[float] = None,
    use_numba: bool = True,
) -> DispatchResult:
    """Despacha un ano horario y devuelve las series resultantes.

    ``use_numba=False`` fuerza la ruta en CPython, lo que permite verificar en
    los tests que ambas implementaciones coinciden.
    """
    limit = (
        _NO_GRID_LIMIT if grid_export_limit_mw is None else float(grid_export_limit_mw)
    )

    if use_numba and NUMBA_AVAILABLE:
        core = _dispatch_core
        generation = np.ascontiguousarray(generation_mw, dtype=np.float64)
    else:
        # Las listas de Python evitan el coste de crear un escalar de NumPy por
        # cada una de las 8760 horas, que es lo que domina esta ruta.
        core = _dispatch_core_python
        generation = np.asarray(generation_mw, dtype=np.float64).tolist()

    outputs = core(
        generation,
        float(electrolyzer_mw),
        float(min_load_ratio * electrolyzer_mw),
        float(battery_power_mw),
        float(battery_energy_mwh),
        float(eta_charge),
        float(eta_discharge),
        int(policy),
        limit,
    )
    return DispatchResult(*(np.asarray(series, dtype=np.float64) for series in outputs))
