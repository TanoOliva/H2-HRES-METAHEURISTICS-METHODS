"""Resumenes, comparacion con el paper y generacion de figuras."""

import pandas as pd
import pytest

from h2_hres.analysis import (
    PAPER_CASES,
    aggregate_runs,
    best_solution,
    compare_to_paper,
    evaluate_named_cases,
    plot_convergence,
    plot_feasible_domain,
    plot_lcoe_heatmap,
    plot_typical_year_selection,
    save_figure,
    summarize_grid,
)
from h2_hres.config.schema import ScenarioConfig
from h2_hres.data.typical_year import choose_typical_year
from h2_hres.optimization import GreyWolfOptimizer, ObjectiveFunction, run_grid_search
from conftest import make_year


@pytest.fixture(scope="module")
def grid(profile_cache, config):
    return run_grid_search(profile_cache, config, progress=False)


def test_named_cases_cover_the_paper_comparison(profile_cache, config):
    table = evaluate_named_cases(profile_cache, config)
    assert len(table) == len(PAPER_CASES)
    assert set(table["case"]) == {name for name, *_ in PAPER_CASES}
    assert "lcoe_cny_per_kwh" in table.columns


def test_compare_to_paper_reports_deviations(profile_cache, config):
    table = evaluate_named_cases(profile_cache, config)
    comparison = compare_to_paper(table)
    assert set(comparison["metric"]) == {"LCOE (CNY/kWh)", "CF electrolizador"}
    assert comparison["paper"].notna().all()


def test_compare_to_paper_requires_the_optimum_case():
    with pytest.raises(ValueError, match="caso optimo"):
        compare_to_paper(pd.DataFrame({"case": ["otro"]}))


def test_summarize_grid_counts_add_up(grid):
    summary = summarize_grid(grid)
    assert summary["feasible"] + summary["infeasible"] == summary["evaluated"]
    assert summary["evaluated"] == len(grid)


def test_best_solution_returns_none_without_feasible_points():
    empty = pd.DataFrame({"feasible": [False], "lcoe_cny_per_kwh": [1.0]})
    assert best_solution(empty) is None


def test_aggregate_runs_summarizes_seeds(hourly):
    config = ScenarioConfig.from_dict(
        {"metaheuristic": {"population": 6, "iterations": 4, "seed": 42}}
    )
    objective = ObjectiveFunction(hourly, config)
    summaries = [
        GreyWolfOptimizer(objective, seed=seed).optimize().summary()
        for seed in (1, 2, 3)
    ]
    stats = aggregate_runs(summaries)

    assert len(stats) == 1
    row = stats.iloc[0]
    assert row["algorithm"] == "gwo"
    assert row["runs"] == 3
    assert row["best"] <= row["mean"] <= row["worst"]


def test_aggregate_runs_handles_no_runs():
    assert aggregate_runs([]).empty


def test_figures_are_written_to_disk(grid, tmp_path):
    domain = save_figure(plot_feasible_domain(grid), tmp_path / "domain.png")
    assert domain.exists() and domain.stat().st_size > 0

    heatmap = plot_lcoe_heatmap(grid)
    if heatmap is not None:
        path = save_figure(heatmap, tmp_path / "heatmap.png")
        assert path.exists()

    selection = choose_typical_year({2001 + i: make_year(200 + i) for i in range(3)})
    path = save_figure(
        plot_typical_year_selection(selection.summary), tmp_path / "typical.png"
    )
    assert path.exists()


def test_heatmap_is_none_without_feasible_points():
    empty = pd.DataFrame(
        {"feasible": [False], "wind_mw": [0.0], "electrolyzer_mw": [0.0],
         "lcoe_cny_per_kwh": [1.0]}
    )
    assert plot_lcoe_heatmap(empty) is None


def test_convergence_plot_handles_multiple_seeds(tmp_path):
    history = pd.DataFrame(
        {
            "iteration": [1, 2, 3, 1, 2, 3],
            "best_score": [1.0, 0.8, 0.7, 1.1, 0.9, 0.75],
            "seed": [1, 1, 1, 2, 2, 2],
        }
    )
    path = save_figure(plot_convergence(history, "gwo"), tmp_path / "conv.png")
    assert path.exists()
