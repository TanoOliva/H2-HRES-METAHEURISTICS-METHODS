"""Las correcciones de la replicacion fiel, fijadas como regresion.

Cada test aqui corresponde a una brecha cerrada respecto del notebook. Si una
refactorizacion futura las deshace, el desvio contra el paper vuelve a crecer y
estos tests lo detectan antes que la tabla de validacion.
"""

import math

import numpy as np
import pytest

from h2_hres.config.loader import load_scenario
from h2_hres.config.schema import ScenarioConfig
from h2_hres.data.nasa_power import WIND_SURFACE_ALPHA
from h2_hres.models.economics import (
    component_npc,
    hydrogen_storage_npc,
    npc_from_capacities,
    salvage_value,
)
from h2_hres.models.pv import pv_power_mw
from h2_hres.simulation.simulator import battery_power_for


# --- Brecha 1: viento a altura de buje --------------------------------------


def test_wind_surface_alphas_follow_the_power_law():
    """Los alfa tabulados deben reproducir el ratio WSC/WS50M de NASA a 105 m."""
    observed = {
        "vegtype_7": 1.2216,
        "vegtype_9": 1.2216,
        "vegtype_11": 1.1777,
        "airportgrass": 1.1173,
    }
    for surface, ratio in observed.items():
        alpha = math.log(ratio) / math.log(105.0 / 50.0)
        assert alpha == pytest.approx(WIND_SURFACE_ALPHA[surface], abs=1e-3)


def test_wind_speed_source_is_validated():
    from h2_hres.config.schema import ConfigError

    ScenarioConfig.from_dict({"wind": {"wind_speed_source": "hub_height"}})
    with pytest.raises(ConfigError, match="wind_speed_source"):
        ScenarioConfig.from_dict({"wind": {"wind_speed_source": "a_150m"}})


def test_default_uses_the_measured_series():
    """El default reproduce el CF de 40% del paper; ver CHANGELOG correccion 1."""
    assert ScenarioConfig().wind.wind_speed_source == "measured_50m"


# --- Brecha 2: relacion DC/AC del campo fotovoltaico ------------------------


def test_dc_ac_ratio_lifts_mid_irradiance_output():
    """Con DC/AC 1.2 el campo entrega mas a irradiancia media, sin pasarse en AC."""
    config = ScenarioConfig().pv
    ghi = np.array([0.5])          # kW/m2
    ambient = np.array([15.0])

    with_ratio = pv_power_mw(ghi, ambient, 80.0, config)
    flat = pv_power_mw(ghi, ambient, 80.0, config.__class__(dc_ac_ratio=1.0))
    assert with_ratio[0] > flat[0]


def test_inverter_clipping_caps_output_at_ac_capacity():
    config = ScenarioConfig().pv
    ghi = np.array([1.0, 1.2])
    ambient = np.array([10.0, 10.0])
    power = pv_power_mw(ghi, ambient, 80.0, config)
    assert power.max() <= 80.0 + 1e-9


def test_ghi_must_be_in_kw_per_m2():
    """Regresion de la correccion 7: en W/m2 el factor termico anula el campo.

    Con GHI en W/m2 la temperatura de celda tipo NOCT da miles de grados, el
    factor termico se vuelve negativo y la produccion cae a cero.
    """
    config = ScenarioConfig().pv
    ambient = np.array([15.0])

    correct = pv_power_mw(np.array([0.5]), ambient, 80.0, config)
    wrong_units = pv_power_mw(np.array([500.0]), ambient, 80.0, config)

    assert correct[0] > 0
    assert wrong_units[0] == pytest.approx(0.0)


# --- Brecha 4: valor residual y almacenamiento de H2 ------------------------


def test_salvage_only_applies_when_life_outlasts_the_horizon():
    # Electrolizador: vida 15, reemplazo en el ano 15, quedan 5 de 15 al ano 25.
    expected = 95_000.0 * 5969.14 * (5 / 15) / (1.0435 ** 25)
    assert salvage_value(95_000.0, 5969.14, 15, 25, 0.0435) == pytest.approx(expected)

    # Eolica: vida 25 = horizonte, nunca se reemplaza -> sin residual.
    assert salvage_value(190_000.0, 0.0, 25, 25, 0.0435) == 0.0


def test_salvage_reduces_the_npc():
    config = ScenarioConfig()
    with_salvage = npc_from_capacities(
        190.0, 10.0, 95.0, 30.0, 30.0, config.costs, config.economics
    )
    # Sin reemplazos no hay residual: el electrolizador cuesta mas caro.
    from dataclasses import replace

    costs = replace(
        config.costs,
        electrolyzer=replace(config.costs.electrolyzer, replacement_cny_per_kw=0.0),
    )
    without_replacement = npc_from_capacities(
        190.0, 10.0, 95.0, 30.0, 30.0, costs, config.economics
    )
    assert with_salvage > without_replacement


def test_hydrogen_storage_enters_the_npc():
    config = ScenarioConfig()
    tank = hydrogen_storage_npc(10_000.0, config.costs, config.economics)
    assert tank == pytest.approx(87_454_499.46, rel=1e-6)

    base = npc_from_capacities(
        190.0, 10.0, 95.0, 30.0, 30.0, config.costs, config.economics
    )
    with_tank = npc_from_capacities(
        190.0, 10.0, 95.0, 30.0, 30.0, config.costs, config.economics,
        hydrogen_storage_kg=10_000.0,
    )
    assert with_tank - base == pytest.approx(tank)


# --- Brecha 5: redondeo de la potencia de bateria ---------------------------


@pytest.mark.parametrize(
    "electrolyzer_mw,expected",
    [(95.0, 30.0), (80.0, 25.0), (85.0, 27.5)],
)
def test_battery_rounding_reproduces_the_published_cases(electrolyzer_mw, expected):
    """B30/E95, B25/E80 y B27.5/E85 solo salen redondeando hacia arriba a 2.5 MW."""
    assert battery_power_for(electrolyzer_mw, ScenarioConfig()) == pytest.approx(expected)


def test_battery_rounding_leaves_aligned_values_untouched():
    """Un valor ya en la malla no debe saltar un pack por error de coma flotante."""
    config = ScenarioConfig.from_dict(
        {"battery": {"power_ratio_to_electrolyzer": 0.5}}
    )
    assert battery_power_for(50.0, config) == pytest.approx(25.0)


# --- Brecha 6: zona horaria del ano tipico ----------------------------------


def test_local_time_grouping_changes_the_daily_split():
    """Agrupar en UTC parte el dia solar de Damao Banner; en local no."""
    import pandas as pd

    from h2_hres.data.typical_year import daily_pearson_distribution

    hours = np.arange(24 * 10)
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2008-01-01", periods=len(hours), freq="h"),
            "ws50m": 5.0 + np.sin(hours * 2 * np.pi / 24),
            # Ciclo solar centrado en el mediodia LOCAL (04:00 UTC en UTC+8).
            "ghi_kwh_m2": np.clip(np.sin((hours - 4) * 2 * np.pi / 24), 0, None),
        }
    )

    utc = daily_pearson_distribution(frame, utc_offset_hours=0.0)
    local = daily_pearson_distribution(frame, utc_offset_hours=8.0)
    assert not np.allclose(utc.to_numpy(), local.to_numpy())


# --- Fase 2: reparto del costo de bateria en potencia y energia ------------


def test_battery_cost_split_is_npc_neutral_at_one_hour():
    """configs/metaheuristicas.yaml no debe mover el NPC de la Fase 1 a 1 h.

    El reparto 30% potencia / 70% energia de los 2549/500/10 CNY/kW del paper
    existe para que la duracion de bateria tenga sentido economico como
    variable de decision (ver CHANGELOG.md y entrega/README.md, seccion de
    supuestos declarados). A 1 h -- donde potencia y energia coinciden
    numericamente -- la suma debe reproducir exactamente el costo original,
    o la comparativa de metaheuristicas ya no partiria de la base validada
    contra el paper.
    """
    paper = ScenarioConfig()
    split = load_scenario("configs/metaheuristicas.yaml")

    power_mw, energy_mwh = 30.0, 30.0  # 1 h: potencia == energia

    npc_paper = component_npc(
        power_mw * 1000.0, 0.0, paper.costs.battery, paper.economics
    )
    npc_split = component_npc(
        power_mw * 1000.0, energy_mwh * 1000.0, split.costs.battery, split.economics
    )
    assert npc_split == pytest.approx(npc_paper, rel=1e-9)


def test_battery_cost_split_makes_longer_duration_more_expensive():
    """A mas horas, la misma potencia cuesta mas -- ya no es gratis alargarla."""
    config = load_scenario("configs/metaheuristicas.yaml")
    one_hour = component_npc(30_000.0, 30_000.0, config.costs.battery, config.economics)
    four_hours = component_npc(30_000.0, 120_000.0, config.costs.battery, config.economics)
    assert four_hours > one_hour
