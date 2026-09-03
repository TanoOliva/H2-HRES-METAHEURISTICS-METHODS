"""Barridos de sensibilidad sobre AGSR y carga minima del electrolizador."""

from dataclasses import replace

import pytest

from h2_hres.analysis.sensitivity import (
    run_sensitivity_study,
    sweep_agsr_max,
    sweep_min_load_ratio,
)


@pytest.fixture(scope="module")
def coarse_config(config):
    """Malla mas gruesa: 4x4=16 combinaciones en vez de 420, para tests rapidos."""
    return config.replace(
        search=replace(config.search, wind_step_mw=50.0, electrolyzer_step_mw=25.0)
    )


def test_sweep_agsr_max_returns_one_row_per_value(hourly, coarse_config):
    table = sweep_agsr_max(hourly, coarse_config, values=(0.10, 0.20, 0.30))
    assert list(table["value"]) == [0.10, 0.20, 0.30]
    assert (table["parameter"] == "agsr_max").all()
    assert (table["evaluated"] > 0).all()


def test_relaxing_agsr_grows_the_feasible_domain(hourly, coarse_config):
    """Restriccion mas laxa -> nunca menos configuraciones factibles."""
    table = sweep_agsr_max(hourly, coarse_config, values=(0.10, 0.20, 0.30))
    feasible_counts = table.sort_values("value")["feasible"].to_numpy()
    assert (feasible_counts[1:] >= feasible_counts[:-1]).all()


def test_relaxing_agsr_never_increases_the_optimal_lcoe(hourly, coarse_config):
    """Mas opciones factibles -> el minimo de LCOE no puede empeorar."""
    table = sweep_agsr_max(hourly, coarse_config, values=(0.10, 0.20, 0.30)).sort_values("value")
    lcoe = table["best_lcoe_cny_per_kwh"].dropna().to_numpy()
    assert (lcoe[1:] <= lcoe[:-1] + 1e-9).all()


def test_sweep_min_load_ratio_returns_one_row_per_value(hourly, coarse_config):
    table = sweep_min_load_ratio(hourly, coarse_config, values=(0.20, 0.30, 0.40, 0.50))
    assert list(table["value"]) == [0.20, 0.30, 0.40, 0.50]
    assert (table["parameter"] == "min_load_ratio").all()


def test_sweep_does_not_mutate_the_base_config(hourly, coarse_config):
    """La config original no debe cambiar: cada valor construye una copia."""
    original_agsr = coarse_config.constraints.agsr_max
    sweep_agsr_max(hourly, coarse_config, values=(0.05, 0.99))
    assert coarse_config.constraints.agsr_max == original_agsr


def test_run_sensitivity_study_returns_both_sweeps(hourly, coarse_config):
    study = run_sensitivity_study(
        hourly, coarse_config, agsr_values=(0.10, 0.30), min_load_values=(0.20, 0.40)
    )
    assert set(study) == {"agsr_max", "min_load_ratio"}
    assert len(study["agsr_max"]) == 2
    assert len(study["min_load_ratio"]) == 2


def test_feasible_share_is_a_fraction(hourly, coarse_config):
    table = sweep_agsr_max(hourly, coarse_config, values=(0.20,))
    row = table.iloc[0]
    assert 0.0 <= row["feasible_share"] <= 1.0
    assert row["feasible_share"] == pytest.approx(row["feasible"] / row["evaluated"])
