"""Seleccion del ano tipico por complementariedad viento-solar."""

import numpy as np
import pandas as pd
import pytest

from h2_hres.data.typical_year import (
    PEARSON_LABELS,
    choose_typical_year,
    daily_pearson_distribution,
)
from conftest import make_year


def test_distribution_covers_the_nine_classes_and_sums_to_one():
    distribution = daily_pearson_distribution(make_year())
    # Se ordena 1..9 como la Tabla 5: clase 1 = mas positiva.
    assert list(distribution.index) == sorted(PEARSON_LABELS)
    assert distribution.sum() == pytest.approx(1.0)
    assert (distribution >= 0).all()


def test_perfectly_correlated_days_land_in_the_top_class():
    """Viento y GHI proporcionales: Pearson = 1 -> clase 1 de la Tabla 5."""
    hours = np.arange(240)
    ramp = 1.0 + (hours % 24)
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2008-01-01", periods=240, freq="h"),
            "ws50m": ramp,
            "ghi_kwh_m2": ramp * 0.05,
        }
    )
    distribution = daily_pearson_distribution(frame)
    assert distribution.loc[1] == pytest.approx(1.0)


def test_anticorrelated_days_land_in_the_bottom_class():
    hours = np.arange(240)
    ramp = 1.0 + (hours % 24)
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2008-01-01", periods=240, freq="h"),
            "ws50m": ramp,
            "ghi_kwh_m2": (25.0 - ramp) * 0.05,
        }
    )
    distribution = daily_pearson_distribution(frame)
    assert distribution.loc[9] == pytest.approx(1.0)


def test_constant_days_are_dropped_not_counted_as_zero():
    """Un dia sin variacion no define correlacion; debe excluirse del conteo."""
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2008-01-01", periods=48, freq="h"),
            "ws50m": [5.0] * 24 + list(np.arange(24, dtype=float)),
            "ghi_kwh_m2": [0.5] * 24 + list(np.arange(24, dtype=float) * 0.02),
        }
    )
    distribution = daily_pearson_distribution(frame)
    # Solo el segundo dia entra, y esta perfectamente correlacionado.
    assert distribution.loc[1] == pytest.approx(1.0)


def test_chooses_the_year_closest_to_the_long_term_pattern():
    """El ano cuya distribucion coincide con la media global debe ganar."""
    years = {2001 + i: make_year(seed=100 + i) for i in range(5)}
    selection = choose_typical_year(years)

    distances = selection.summary["euclidean_distance"]
    assert selection.typical_year == int(distances.idxmin())
    assert distances.min() >= 0

    # La distribucion global es la media de las anuales.
    per_year = selection.summary[sorted(PEARSON_LABELS)]
    np.testing.assert_allclose(
        per_year.mean(axis=0).to_numpy(),
        selection.global_distribution.to_numpy(),
        atol=1e-12,
    )


def test_a_duplicated_year_is_selected_when_it_dominates_the_mean():
    """Tres copias identicas fijan la media: una de ellas es el ano tipico."""
    twin = make_year(seed=7)
    outlier = make_year(seed=99)
    years = {2001: twin, 2002: twin.copy(), 2003: twin.copy(), 2004: outlier}
    selection = choose_typical_year(years)
    assert selection.typical_year in (2001, 2002, 2003)


def test_empty_input_is_rejected():
    with pytest.raises(ValueError):
        choose_typical_year({})
