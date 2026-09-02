"""Metaheuristicas: ejecucion, reproducibilidad y calidad frente a la linea base."""

import numpy as np
import pytest

from h2_hres.config.schema import ScenarioConfig
from h2_hres.optimization import (
    REGISTRY,
    DecisionSpace,
    GreyWolfOptimizer,
    ObjectiveFunction,
    RandomSearch,
    get_optimizer,
)

# Presupuesto reducido: estos tests verifican comportamiento, no convergencia.
SMALL = {"metaheuristic": {"population": 8, "iterations": 5, "seed": 42}}


@pytest.fixture(scope="module")
def small_config():
    return ScenarioConfig.from_dict(SMALL)


@pytest.mark.parametrize("name", sorted(REGISTRY))
def test_every_registered_optimizer_runs(hourly, small_config, name):
    """Regresion del bug bloqueante: el GWO del notebook nunca llego a correr."""
    optimizer = get_optimizer(name)(ObjectiveFunction(hourly, small_config))
    result = optimizer.optimize()

    assert result.n_evaluations == small_config.metaheuristic.evaluation_budget
    assert np.isfinite(result.best_score)
    assert len(result.history) > 0
    assert result.elapsed_s > 0


@pytest.mark.parametrize("name", sorted(REGISTRY))
def test_same_seed_reproduces_the_run(hourly, small_config, name):
    cls = get_optimizer(name)
    first = cls(ObjectiveFunction(hourly, small_config), seed=7).optimize()
    second = cls(ObjectiveFunction(hourly, small_config), seed=7).optimize()

    assert first.best_score == second.best_score
    assert first.best.design == second.best.design
    np.testing.assert_allclose(
        first.history["best_score"], second.history["best_score"]
    )


@pytest.mark.parametrize("name", sorted(REGISTRY))
def test_different_seeds_explore_differently(hourly, small_config, name):
    cls = get_optimizer(name)
    a = cls(ObjectiveFunction(hourly, small_config), seed=1).optimize()
    b = cls(ObjectiveFunction(hourly, small_config), seed=2).optimize()
    assert a.history["best_score"].tolist() != b.history["best_score"].tolist()


@pytest.mark.parametrize("name", sorted(REGISTRY))
def test_best_score_is_monotonically_non_increasing(hourly, small_config, name):
    """El historial registra el mejor acumulado: nunca puede empeorar."""
    result = get_optimizer(name)(ObjectiveFunction(hourly, small_config)).optimize()
    scores = result.history["best_score"].to_numpy()
    assert (np.diff(scores) <= 1e-12).all()


def test_gwo_beats_random_search_at_equal_budget(hourly):
    """Con el mismo presupuesto, la busqueda dirigida debe ganarle al azar."""
    config = ScenarioConfig.from_dict(
        {"metaheuristic": {"population": 15, "iterations": 20, "seed": 42}}
    )
    gwo = GreyWolfOptimizer(ObjectiveFunction(hourly, config), seed=42).optimize()
    random = RandomSearch(ObjectiveFunction(hourly, config), seed=42).optimize()

    assert gwo.n_evaluations == random.n_evaluations
    assert gwo.best_score <= random.best_score


def test_decoded_designs_always_respect_the_discrete_grid(hourly, small_config):
    """Toda solucion evaluada debe caer en la malla, sea cual sea el vector."""
    space = DecisionSpace(small_config)
    rng = np.random.default_rng(0)
    battery = small_config.battery
    electrolyzer = small_config.electrolyzer

    for _ in range(200):
        # Vectores deliberadamente fuera de rango, para probar la proyeccion.
        x = rng.uniform(-500, 500, space.n_dimensions)
        design = space.decode(x)

        assert electrolyzer.min_units <= design.n_electrolyzer_units <= electrolyzer.max_units
        assert battery.power_min_mw <= design.battery_mw <= battery.power_max_mw
        assert design.battery_duration_h in battery.duration_candidates_h
        assert 0.0 <= design.wind_mw <= small_config.constraints.total_generation_capacity_mw
        assert design.wind_mw + design.pv_mw == pytest.approx(
            small_config.constraints.total_generation_capacity_mw
        )
        # La potencia de bateria cae siempre en un multiplo del paso.
        assert design.battery_mw % battery.power_step_mw == pytest.approx(0.0, abs=1e-9)


def test_penalty_orders_infeasible_below_feasible(hourly, small_config):
    """Una solucion factible siempre debe puntuar mejor que una infactible."""
    objective = ObjectiveFunction(hourly, small_config)
    space = objective.space
    rng = np.random.default_rng(3)

    feasible_scores, infeasible_scores = [], []
    for _ in range(120):
        evaluation = objective.evaluate(space.sample(rng, 1)[0])
        target = feasible_scores if evaluation.result.feasible else infeasible_scores
        target.append(evaluation.score)

    if feasible_scores and infeasible_scores:
        assert max(feasible_scores) < min(infeasible_scores)


def test_penalty_grows_with_the_constraint_violation(small_config):
    """La penalizacion debe dar gradiente hacia la region factible."""
    from h2_hres.optimization.objectives import PenaltyPolicy
    from h2_hres.simulation.results import SimulationResult

    policy = PenaltyPolicy(base=1e6, agsr_weight=1e3)

    def result_with(agsr):
        return SimulationResult(
            wind_mw=100.0, pv_mw=100.0, electrolyzer_mw=50.0, n_electrolyzer_units=10,
            battery_mw=15.0, battery_mwh=15.0, battery_duration_h=1.0,
            feasible=False, agsr=agsr,
        )

    mild = policy.score(result_with(0.25), agsr_max=0.20)
    severe = policy.score(result_with(0.60), agsr_max=0.20)
    assert severe > mild > 1e6


def test_unknown_algorithm_lists_the_available_ones():
    with pytest.raises(KeyError, match="Disponibles"):
        get_optimizer("no_existe")


def test_decision_space_warns_about_free_battery_duration():
    """Duracion libre sin costo por kWh: el optimo no seria interpretable."""
    config = ScenarioConfig()
    warnings = DecisionSpace(config).warnings()
    assert any("kWh" in message for message in warnings)

    fixed = ScenarioConfig.from_dict({"battery": {"duration_candidates_h": [1.0]}})
    assert DecisionSpace(fixed).warnings() == []
