"""Fixtures compartidas. Ningun test toca la red."""

import numpy as np
import pandas as pd
import pytest

from h2_hres.config.schema import ScenarioConfig
from h2_hres.simulation.simulator import as_profile_cache


def make_year(seed: int = 12345, n_hours: int = 8760) -> pd.DataFrame:
    """Ano horario sintetico con estacionalidad diaria y anual.

    No pretende parecerse a Damao Banner: solo necesita ser reproducible y
    ejercitar los tres regimenes de la curva de potencia y el ciclo solar.
    """
    rng = np.random.default_rng(seed)
    hours = np.arange(n_hours)
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2008-01-01", periods=n_hours, freq="h"),
            "ws50m": np.abs(
                rng.weibull(2.0, n_hours) * 7.5 + 0.5 * np.sin(hours * 2 * np.pi / 24)
            ),
            "ghi_kwh_m2": (
                np.clip(np.sin(hours * 2 * np.pi / 24), 0, None)
                * rng.uniform(0.30, 0.95, n_hours)
                * (0.75 + 0.25 * np.sin(hours * 2 * np.pi / 8760))
            ),
            "t2m_c": 8
            + 16 * np.sin(hours * 2 * np.pi / 8760 - 1.8)
            + rng.normal(0, 3.5, n_hours),
        }
    )


@pytest.fixture(scope="session")
def config() -> ScenarioConfig:
    return ScenarioConfig()


@pytest.fixture(scope="session")
def hourly() -> pd.DataFrame:
    return make_year()


@pytest.fixture(scope="session")
def profile_cache(hourly, config):
    return as_profile_cache(hourly, config)
