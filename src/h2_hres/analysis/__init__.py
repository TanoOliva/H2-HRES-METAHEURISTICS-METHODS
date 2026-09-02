"""Resumenes, comparacion con el paper y graficos."""

from .plots import (
    plot_convergence,
    plot_feasible_domain,
    plot_lcoe_heatmap,
    plot_typical_year_selection,
    save_figure,
)
from .summaries import (
    PAPER_CASES,
    PAPER_OPTIMUM,
    aggregate_runs,
    best_solution,
    compare_to_paper,
    evaluate_named_cases,
    summarize_grid,
)

__all__ = [
    "PAPER_CASES",
    "PAPER_OPTIMUM",
    "aggregate_runs",
    "best_solution",
    "compare_to_paper",
    "evaluate_named_cases",
    "plot_convergence",
    "plot_feasible_domain",
    "plot_lcoe_heatmap",
    "plot_typical_year_selection",
    "save_figure",
    "summarize_grid",
]
