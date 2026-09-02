"""Simulacion anual: restricciones, coherencia energetica y ambos modelos."""

import numpy as np
import pytest

from h2_hres.config.schema import ScenarioConfig
from h2_hres.simulation import simulate_base, simulate_discrete


def test_base_case_produces_coherent_energy_accounting(profile_cache, config):
    result = simulate_base(profile_cache, 190.0, 10.0, 95.0, config)
    assert result.total_renewable_mwh == pytest.approx(
        result.total_wind_mwh + result.total_pv_mwh
    )
    assert result.total_grid_sales_mwh <= result.total_renewable_mwh + 1e-6
    assert 0.0 <= result.electrolyzer_cf <= 1.0
    assert result.agsr == pytest.approx(
        result.total_grid_sales_mwh / result.total_renewable_mwh
    )


def test_hydrogen_follows_the_derived_specific_consumption(profile_cache, config):
    """El H2 debe salir del mismo consumo especifico en ambos modelos."""
    result = simulate_base(profile_cache, 190.0, 10.0, 95.0, config)
    # La carga se mide en el bus AC; a las celdas llega lo que deja pasar el
    # rectificador (P_rectifier_loss en la Eq. 6 del paper).
    expected = (
        result.total_electrolyzer_load_mwh
        * config.converter.rectifier_efficiency
        * 1000.0
        / config.electrolyzer.specific_consumption_kwh_per_kg
    )
    assert result.total_h2_kg == pytest.approx(expected)


def test_discrete_model_runs_without_a_missing_key(profile_cache, config):
    """Regresion del bug que impedia ejecutar la extension del notebook."""
    result = simulate_discrete(profile_cache, 190.0, 19, 28.5, 1.0, config)
    assert result.total_h2_kg > 0
    assert np.isfinite(result.lcoe_cny_per_kwh)


def test_both_models_agree_on_hydrogen_conversion(profile_cache, config):
    base = simulate_base(profile_cache, 190.0, 10.0, 95.0, config)
    discrete = simulate_discrete(profile_cache, 190.0, 19, 28.5, 1.0, config)
    # Distinta politica de despacho, pero la misma relacion energia -> H2.
    expected_ratio = (
        config.converter.rectifier_efficiency
        / config.electrolyzer.specific_consumption_kwh_per_kg
    )
    for result in (base, discrete):
        ratio = result.total_h2_kg / (result.total_electrolyzer_load_mwh * 1000.0)
        assert ratio == pytest.approx(expected_ratio)


@pytest.mark.parametrize(
    "wind,pv,electrolyzer,fragment",
    [
        (190.0, 20.0, 95.0, "capacidad fija"),   # wind + pv != 200
        (190.0, 10.0, 0.0, "capacidad nula"),    # electrolizador nulo
        (190.0, 10.0, 150.0, "supera el maximo"),  # E > 50% de la generacion
        (-10.0, 210.0, 95.0, "negativa"),
    ],
)
def test_base_constraints_are_reported_with_a_reason(
    profile_cache, config, wind, pv, electrolyzer, fragment
):
    """El notebook devolvia feasible=False sin decir por que."""
    result = simulate_base(profile_cache, wind, pv, electrolyzer, config)
    assert not result.feasible
    assert fragment in result.infeasibility_reason


@pytest.mark.parametrize(
    "units,battery_mw,duration,fragment",
    [
        (25, 28.5, 1.0, "supera el maximo"),      # fuera del limite del paper
        (5, 28.5, 1.0, "rango discreto"),         # bajo el minimo de unidades
        (19, 500.0, 1.0, "fuera del rango"),      # bateria fuera de rango
        (19, 28.5, 3.0, "no esta entre las candidatas"),
    ],
)
def test_discrete_constraints_are_reported_with_a_reason(
    profile_cache, config, units, battery_mw, duration, fragment
):
    result = simulate_discrete(profile_cache, 190.0, units, battery_mw, duration, config)
    assert not result.feasible
    assert fragment in result.infeasibility_reason


def test_lcoe_basis_changes_the_denominator(profile_cache, hourly):
    """Las dos bases del LCOE deben dar valores distintos y ordenados."""
    both = ScenarioConfig()
    only = ScenarioConfig.from_dict({"economics": {"lcoe_energy_basis": "electrolyzer_only"}})

    with_grid = simulate_base(hourly, 190.0, 10.0, 95.0, both)
    without_grid = simulate_base(hourly, 190.0, 10.0, 95.0, only)

    # Mismo numerador, denominador menor -> LCOE mayor.
    assert without_grid.lcoe_cny_per_kwh > with_grid.lcoe_cny_per_kwh
    assert without_grid.annualized_cost_cny == pytest.approx(with_grid.annualized_cost_cny)


def test_infeasible_solutions_still_report_lcoe(profile_cache, config):
    """Se conserva el LCOE de los puntos infactibles para poder mapear el dominio."""
    result = simulate_base(profile_cache, 0.0, 200.0, 100.0, config)
    if not result.feasible and result.infeasibility_reason.startswith("AGSR"):
        assert np.isfinite(result.lcoe_cny_per_kwh)


def test_profile_cache_avoids_recomputation(hourly, config):
    from h2_hres.simulation.simulator import as_profile_cache

    cache = as_profile_cache(hourly, config)
    for electrolyzer in (50.0, 60.0, 70.0, 80.0, 90.0):
        simulate_base(cache, 190.0, 10.0, electrolyzer, config)

    stats = cache.stats()
    # Un unico perfil de generacion para las cinco capacidades de electrolisis.
    assert stats["wind_profiles"] == 1
    assert stats["pv_profiles"] == 1
    assert stats["hits"] == 4
