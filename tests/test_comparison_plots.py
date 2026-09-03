"""Figuras de la comparativa de metaheuristicas: se generan y se guardan sin error."""

import pandas as pd
import pytest

from h2_hres.analysis.comparison_plots import (
    plot_convergence_by_algorithm,
    plot_quality_vs_time,
    plot_score_boxplot,
    plot_sensitivity_sweep,
)
from h2_hres.analysis.plots import save_figure
from h2_hres.analysis.sensitivity import sweep_agsr_max
from h2_hres.analysis.style import (
    ALGORITHM_COLORS,
    ALGORITHM_ORDER,
    algorithm_color,
    algorithm_linestyle,
)
from h2_hres.config.schema import ScenarioConfig
from h2_hres.optimization.metaheuristics import REGISTRY, get_optimizer
from h2_hres.optimization.objectives import ObjectiveFunction


def _small_config():
    return ScenarioConfig.from_dict(
        {
            "battery": {"duration_candidates_h": [1.0, 2.0]},
            "costs": {"battery": {"capex_cny_per_kwh": 500.0}},
            "metaheuristic": {"population": 6, "iterations": 3, "seed": 7},
        }
    )


@pytest.fixture(scope="module")
def multi_algorithm_runs(hourly):
    """Historial y resumen de cada algoritmo registrado, 2 semillas cada uno."""
    config = _small_config()
    objective = ObjectiveFunction(hourly, config)

    histories, summaries = [], []
    for name in sorted(REGISTRY):
        for seed in (1, 2):
            result = get_optimizer(name)(objective, seed=seed).optimize()
            history = result.history.copy()
            history["algorithm"] = name
            history["seed"] = seed
            histories.append(history)
            summaries.append(result.summary())

    return pd.concat(histories, ignore_index=True), pd.DataFrame(summaries)


def test_algorithm_order_covers_the_registry():
    """Todo algoritmo registrado tiene un lugar fijo en el orden de la paleta."""
    assert set(ALGORITHM_ORDER) == set(REGISTRY)
    assert set(ALGORITHM_COLORS) == set(REGISTRY)


def test_algorithm_colors_are_distinct_hex():
    colors = list(ALGORITHM_COLORS.values())
    assert len(colors) == len(set(colors))
    assert all(c.startswith("#") and len(c) == 7 for c in colors)


def test_random_is_the_only_dashed_line():
    assert algorithm_linestyle("random") == "--"
    for name in set(ALGORITHM_ORDER) - {"random"}:
        assert algorithm_linestyle(name) == "-"


def test_unknown_algorithm_gets_a_fallback_color():
    color = algorithm_color("un_algoritmo_futuro")
    assert color not in ALGORITHM_COLORS.values()
    assert color.startswith("#")


def test_convergence_by_algorithm_covers_every_algorithm(multi_algorithm_runs, tmp_path):
    history, _ = multi_algorithm_runs
    figure = plot_convergence_by_algorithm(history)
    axes = figure.axes[0]
    legend_labels = {t.get_text() for t in axes.get_legend().get_texts()}
    assert legend_labels == {name.upper() for name in REGISTRY}
    path = save_figure(figure, tmp_path / "convergence.png")
    assert path.exists() and path.stat().st_size > 0


def test_score_boxplot_has_one_box_per_algorithm(multi_algorithm_runs, tmp_path):
    _, runs = multi_algorithm_runs
    figure = plot_score_boxplot(runs)
    axes = figure.axes[0]
    assert len(axes.get_xticklabels()) == runs["algorithm"].nunique()
    path = save_figure(figure, tmp_path / "boxplot.png")
    assert path.exists()


def test_quality_vs_time_plots_one_point_per_run(multi_algorithm_runs, tmp_path):
    _, runs = multi_algorithm_runs
    figure = plot_quality_vs_time(runs)
    path = save_figure(figure, tmp_path / "quality_vs_time.png")
    assert path.exists()


def test_sensitivity_sweep_plot_has_three_panels(hourly, tmp_path):
    config = _small_config()
    table = sweep_agsr_max(
        hourly,
        config.replace(
            search=type(config.search)(wind_step_mw=50.0, electrolyzer_step_mw=25.0)
        ),
        values=(0.10, 0.30),
    )
    figure = plot_sensitivity_sweep(table, "Limite AGSR")
    assert len(figure.axes) == 3
    path = save_figure(figure, tmp_path / "sensitivity.png")
    assert path.exists()


def test_boxplot_handles_a_single_algorithm(tmp_path):
    runs = pd.DataFrame({"algorithm": ["gwo"] * 5, "score": [0.3, 0.29, 0.31, 0.28, 0.30]})
    figure = plot_score_boxplot(runs)
    axes = figure.axes[0]
    assert len(axes.get_xticklabels()) == 1
    path = save_figure(figure, tmp_path / "single.png")
    assert path.exists()
