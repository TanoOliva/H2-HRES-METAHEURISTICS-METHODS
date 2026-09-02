"""Modelo economico: factor de recuperacion, valores presentes y NPC."""

import pytest

from h2_hres.config.schema import ComponentCost, EconomicsConfig, ScenarioConfig
from h2_hres.models.economics import (
    component_npc,
    crf,
    levelized_cost,
    npc_from_capacities,
    present_value_of_om,
    present_value_of_replacements,
    replacement_years,
)


def test_crf_matches_closed_form():
    rate, years = 0.0435, 25
    expected = (rate * (1 + rate) ** years) / ((1 + rate) ** years - 1)
    assert crf(rate, years) == pytest.approx(expected)
    assert crf(rate, years) == pytest.approx(0.06640171, abs=1e-8)


def test_crf_with_zero_rate_is_the_analytic_limit():
    """Sin descuento el factor degenera en 1/n en vez de dividir por cero."""
    assert crf(0.0, 25) == pytest.approx(1 / 25)


def test_replacement_years_stay_inside_the_horizon():
    # El electrolizador vive 15 anos: solo se reemplaza una vez en 25.
    assert replacement_years(15, 25) == [15]
    # La bateria vive 10: se reemplaza en el ano 10 y en el 20, no en el 30.
    assert replacement_years(10, 25) == [10, 20]
    # Un componente que supera el horizonte no se reemplaza nunca.
    assert replacement_years(25, 25) == []


def test_present_value_of_om_discounts_every_year():
    value = present_value_of_om(1000.0, 10.0, 3, 0.10)
    expected = 10000 / 1.1 + 10000 / 1.1 ** 2 + 10000 / 1.1 ** 3
    assert value == pytest.approx(expected)


def test_present_value_of_replacements_discounts_at_the_right_years():
    value = present_value_of_replacements(1000.0, 500.0, 10, 25, 0.05)
    expected = 500000 / 1.05 ** 10 + 500000 / 1.05 ** 20
    assert value == pytest.approx(expected)


def test_component_without_replacement_is_capex_plus_om():
    economics = EconomicsConfig(project_lifetime_years=25, real_discount_rate=0.0435)
    cost = ComponentCost(capex_cny_per_kw=5917.0, om_cny_per_kw_year=40.2, life_years=25)
    capacity_kw = 190_000.0

    expected = capacity_kw * 5917.0 + present_value_of_om(
        capacity_kw, 40.2, 25, 0.0435
    )
    assert component_npc(capacity_kw, 0.0, cost, economics) == pytest.approx(expected)


def test_energy_basis_defaults_to_zero_and_preserves_the_notebook_npc():
    """Los costos del paper no tienen base por kWh: el NPC no debe cambiar."""
    config = ScenarioConfig()
    assert not config.costs.battery.has_energy_cost

    with_energy = npc_from_capacities(
        190.0, 10.0, 95.0, 28.5, 28.5, config.costs, config.economics
    )
    without_energy = npc_from_capacities(
        190.0, 10.0, 95.0, 28.5, 0.0, config.costs, config.economics
    )
    assert with_energy == pytest.approx(without_energy)


def test_energy_cost_makes_duration_expensive():
    """Con costo por kWh, una bateria mas larga cuesta mas: da presion al optimizador."""
    config = ScenarioConfig()
    battery = ComponentCost(
        capex_cny_per_kw=2549.0, capex_cny_per_kwh=1200.0, life_years=10
    )
    costs = config.costs.__class__(
        wind=config.costs.wind, pv=config.costs.pv,
        electrolyzer=config.costs.electrolyzer, battery=battery,
    )
    one_hour = npc_from_capacities(190.0, 10.0, 95.0, 30.0, 30.0, costs, config.economics)
    four_hours = npc_from_capacities(190.0, 10.0, 95.0, 30.0, 120.0, costs, config.economics)
    assert four_hours > one_hour


def test_levelized_cost_is_infinite_without_output():
    assert levelized_cost(1e9, 0.0) == float("inf")
    assert levelized_cost(1e9, -5.0) == float("inf")
    assert levelized_cost(100.0, 4.0) == pytest.approx(25.0)
