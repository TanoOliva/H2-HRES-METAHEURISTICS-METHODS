"""Despacho horario: conservacion de energia, limites del SOC y equivalencia
entre la ruta compilada y la ruta en CPython."""

import numpy as np
import pytest

from h2_hres.simulation.dispatch import (
    NUMBA_AVAILABLE,
    MinLoadPolicy,
    dispatch_hourly,
)

ETA = 0.9 ** 0.5
POLICIES = [MinLoadPolicy.TOP_UP, MinLoadPolicy.THRESHOLD]


def _generation(seed=0, n=2000, high=200.0):
    return np.random.default_rng(seed).uniform(0.0, high, n)


@pytest.mark.parametrize("policy", POLICIES)
def test_energy_is_conserved_every_hour(policy):
    """generacion + descarga == carga_elz + carga_bat + red + curtailment."""
    generation = _generation()
    result = dispatch_hourly(
        generation, 95.0, 0.30, 28.5, 28.5, ETA, ETA, policy=policy
    )
    balance = (
        generation
        + result.battery_discharge
        - result.electrolyzer_load
        - result.battery_charge
        - result.grid_sales
        - result.curtailment
    )
    assert np.abs(balance).max() < 1e-9


@pytest.mark.parametrize("policy", POLICIES)
def test_state_of_charge_stays_within_bounds(policy):
    capacity = 28.5
    result = dispatch_hourly(
        _generation(1), 95.0, 0.30, 28.5, capacity, ETA, ETA, policy=policy
    )
    assert result.state_of_charge.min() >= -1e-9
    assert result.state_of_charge.max() <= capacity + 1e-9


@pytest.mark.parametrize("policy", POLICIES)
def test_electrolyzer_never_exceeds_its_rating(policy):
    rating = 95.0
    result = dispatch_hourly(
        _generation(2), rating, 0.30, 28.5, 28.5, ETA, ETA, policy=policy
    )
    assert result.electrolyzer_load.max() <= rating + 1e-9


@pytest.mark.parametrize("policy", POLICIES)
def test_battery_power_limit_is_respected(policy):
    power = 28.5
    result = dispatch_hourly(
        _generation(3), 95.0, 0.30, power, 28.5, ETA, ETA, policy=policy
    )
    assert result.battery_charge.max() <= power + 1e-9
    assert result.battery_discharge.max() <= power + 1e-9


@pytest.mark.parametrize("policy", POLICIES)
def test_without_battery_and_min_load_the_load_follows_generation(policy):
    """Caso degenerado con solucion analitica: load == min(gen, rating)."""
    generation = _generation(4)
    rating = 95.0
    result = dispatch_hourly(
        generation, rating, 0.0, 0.0, 0.0, ETA, ETA, policy=policy
    )
    np.testing.assert_allclose(
        result.electrolyzer_load, np.minimum(generation, rating), atol=1e-12
    )
    np.testing.assert_allclose(
        result.grid_sales, np.maximum(generation - rating, 0.0), atol=1e-12
    )


@pytest.mark.parametrize("policy", POLICIES)
def test_minimum_load_is_respected_when_running(policy):
    """El electrolizador o esta apagado, o opera por encima de su carga minima."""
    rating, ratio = 95.0, 0.30
    result = dispatch_hourly(
        _generation(5, high=60.0), rating, ratio, 28.5, 28.5, ETA, ETA, policy=policy
    )
    running = result.electrolyzer_load > 1e-9
    assert (result.electrolyzer_load[running] >= rating * ratio - 1e-9).all()


def test_curtailment_is_zero_without_an_export_limit():
    """Comportamiento del notebook: sin limite de conexion no hay recorte."""
    result = dispatch_hourly(
        _generation(6), 95.0, 0.30, 28.5, 28.5, ETA, ETA,
        policy=MinLoadPolicy.THRESHOLD, grid_export_limit_mw=None,
    )
    assert result.curtailment.sum() == 0.0


def test_export_limit_produces_curtailment():
    """Con limite de conexion, el excedente que no cabe se recorta de verdad."""
    limit = 20.0
    result = dispatch_hourly(
        _generation(7), 95.0, 0.30, 28.5, 28.5, ETA, ETA,
        policy=MinLoadPolicy.THRESHOLD, grid_export_limit_mw=limit,
    )
    assert result.grid_sales.max() <= limit + 1e-9
    assert result.curtailment.sum() > 0.0


@pytest.mark.parametrize("policy", POLICIES)
def test_numba_and_python_paths_agree(policy):
    """Ambas rutas deben coincidir bit a bit, o el extra 'fast' cambiaria resultados."""
    generation = _generation(8)
    args = (generation, 95.0, 0.30, 28.5, 28.5, ETA, ETA)
    compiled = dispatch_hourly(*args, policy=policy, use_numba=True)
    interpreted = dispatch_hourly(*args, policy=policy, use_numba=False)
    for a, b in zip(compiled, interpreted):
        np.testing.assert_array_equal(a, b)


def test_policies_differ_under_scarce_generation():
    """Las dos reglas no son la misma: bajo escasez toman decisiones distintas."""
    generation = np.full(500, 20.0)  # por debajo de la carga minima de 28.5 MW
    generation[::10] = 90.0          # picos ocasionales que cargan la bateria
    args = (generation, 95.0, 0.30, 28.5, 28.5, ETA, ETA)
    top_up = dispatch_hourly(*args, policy=MinLoadPolicy.TOP_UP)
    threshold = dispatch_hourly(*args, policy=MinLoadPolicy.THRESHOLD)
    assert not np.allclose(top_up.electrolyzer_load, threshold.electrolyzer_load)


def test_numba_status_is_reported():
    from h2_hres.simulation.dispatch import NUMBA_STATUS
    assert isinstance(NUMBA_STATUS, str) and NUMBA_STATUS
    assert NUMBA_AVAILABLE == NUMBA_STATUS.startswith("numba activo")
