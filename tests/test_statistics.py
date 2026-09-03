"""Comparacion estadistica entre algoritmos: A12, Wilcoxon pareado, ranking."""

import numpy as np
import pandas as pd
import pytest

from h2_hres.analysis.statistics import (
    comparison_table,
    pairwise_wilcoxon,
    vargha_delaney_a12,
)


def _runs(algorithm_scores: dict) -> pd.DataFrame:
    """Arma un DataFrame de corridas: mismas semillas para todos los algoritmos."""
    rows = []
    for algorithm, scores in algorithm_scores.items():
        for seed, score in enumerate(scores):
            rows.append(
                {
                    "algorithm": algorithm,
                    "seed": seed,
                    "score": score,
                    "feasible": True,
                    "elapsed_s": 1.0,
                }
            )
    return pd.DataFrame(rows)


def test_a12_is_one_half_for_identical_samples():
    sample = np.array([1.0, 2.0, 3.0, 4.0])
    assert vargha_delaney_a12(sample, sample) == pytest.approx(0.5)


def test_a12_is_one_when_a_always_wins():
    a = np.array([1.0, 2.0, 3.0])
    b = np.array([10.0, 20.0, 30.0])
    assert vargha_delaney_a12(a, b) == pytest.approx(1.0)
    assert vargha_delaney_a12(b, a) == pytest.approx(0.0)


def test_a12_handles_ties_with_half_weight():
    # a=[1,2] vs b=[1,2]: cada elemento de a empata con un elemento de b y
    # gana al otro -> 0.5 exacto, coherente con el caso de muestras identicas.
    a = np.array([1.0, 2.0])
    b = np.array([1.0, 2.0])
    assert vargha_delaney_a12(a, b) == pytest.approx(0.5)


def test_a12_rejects_empty_samples():
    with pytest.raises(ValueError):
        vargha_delaney_a12(np.array([]), np.array([1.0]))


def test_pairwise_wilcoxon_detects_a_real_difference():
    """Un algoritmo consistentemente mejor debe dar A12=0 y significancia."""
    rng = np.random.default_rng(0)
    runs = _runs(
        {
            "good": 0.25 + rng.normal(0, 0.001, 10),
            "bad": 0.35 + rng.normal(0, 0.001, 10),
        }
    )
    table = pairwise_wilcoxon(runs)

    assert len(table) == 1
    row = table.iloc[0]
    assert row["a12"] == pytest.approx(0.0)
    assert row["p_value_holm"] < 0.05
    assert bool(row["significativo_alpha_0.05"])


def test_pairwise_wilcoxon_finds_no_difference_in_identical_algorithms():
    rng = np.random.default_rng(1)
    scores = 0.30 + rng.normal(0, 0.01, 12)
    runs = _runs({"a": scores, "b": scores.copy()})

    table = pairwise_wilcoxon(runs)
    row = table.iloc[0]
    assert row["p_value"] == pytest.approx(1.0)
    assert row["a12"] == pytest.approx(0.5)
    assert not bool(row["significativo_alpha_0.05"])


def test_pairwise_wilcoxon_covers_all_pairs_for_four_algorithms():
    rng = np.random.default_rng(2)
    runs = _runs({name: 0.3 + rng.normal(0, 0.01, 8) for name in ("gwo", "pso", "ga", "random")})
    table = pairwise_wilcoxon(runs)
    # C(4,2) = 6 pares.
    assert len(table) == 6
    pairs = set(zip(table["algoritmo_a"], table["algoritmo_b"]))
    assert len(pairs) == 6


def test_pairwise_wilcoxon_requires_at_least_two_algorithms():
    runs = _runs({"solo": [0.1, 0.2, 0.3]})
    with pytest.raises(ValueError, match="dos algoritmos"):
        pairwise_wilcoxon(runs)


def test_pairwise_wilcoxon_requires_shared_seeds():
    """Semillas disjuntas entre algoritmos no se pueden aparear."""
    rows = [
        {"algorithm": "a", "seed": 0, "score": 0.2, "feasible": True, "elapsed_s": 1.0},
        {"algorithm": "b", "seed": 1, "score": 0.3, "feasible": True, "elapsed_s": 1.0},
    ]
    with pytest.raises(ValueError, match="semillas comunes"):
        pairwise_wilcoxon(pd.DataFrame(rows))


def test_holm_correction_is_never_smaller_than_uncorrected():
    rng = np.random.default_rng(3)
    runs = _runs({name: 0.3 + rng.normal(0, 0.02, 10) for name in ("a", "b", "c")})
    table = pairwise_wilcoxon(runs)
    assert (table["p_value_holm"] >= table["p_value"] - 1e-12).all()


def test_comparison_table_ranks_by_best_score():
    runs = _runs({"good": [0.20, 0.21, 0.19], "bad": [0.40, 0.41, 0.39]})
    table = comparison_table(runs)

    assert list(table["ranking"]) == [1, 2]
    assert table.iloc[0]["algorithm"] == "good"
    assert table.iloc[0]["best"] < table.iloc[1]["best"]


def test_comparison_table_empty_input():
    assert comparison_table(pd.DataFrame(columns=["algorithm", "seed", "score"])).empty
