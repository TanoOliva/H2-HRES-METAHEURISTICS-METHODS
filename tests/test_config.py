"""Validacion de la configuracion tipada."""

import pytest

from h2_hres.config.loader import dump_scenario, load_scenario
from h2_hres.config.schema import ConfigError, ScenarioConfig


def test_defaults_are_valid():
    ScenarioConfig()


def test_specific_consumption_is_derived():
    """Regresion del KeyError que impedia correr la extension discreta.

    El notebook leia una clave inexistente; ahora el consumo especifico se
    deriva de la eficiencia y del HHV, y no puede faltar.
    """
    config = ScenarioConfig()
    expected = config.electrolyzer.h2_hhv_kwh_per_kg / config.electrolyzer.efficiency
    assert config.electrolyzer.specific_consumption_kwh_per_kg == pytest.approx(expected)
    assert config.electrolyzer.specific_consumption_kwh_per_kg == pytest.approx(52.5333, abs=1e-4)


def test_unknown_key_is_rejected():
    with pytest.raises(ConfigError, match="desconocida"):
        ScenarioConfig.from_dict({"wind": {"cut_in_speed": 3.0}})


def test_unknown_top_level_key_is_rejected():
    with pytest.raises(ConfigError, match="desconocida"):
        ScenarioConfig.from_dict({"electrolizador": {}})


@pytest.mark.parametrize(
    "payload",
    [
        {"wind": {"cut_in_ms": 12.0}},                 # cut_in > rated
        {"wind": {"rated_ms": 30.0}},                  # rated > cut_out
        {"electrolyzer": {"efficiency": 1.5}},         # eficiencia > 1
        {"electrolyzer": {"efficiency": 0.0}},         # eficiencia nula
        {"electrolyzer": {"min_units": 25}},           # min > max
        {"battery": {"roundtrip_efficiency": 1.2}},
        {"constraints": {"agsr_max": 1.5}},
        {"economics": {"lcoe_energy_basis": "otra_cosa"}},
        {"site": {"start_year": 2030}},                # start > end
    ],
)
def test_invalid_ranges_are_rejected(payload):
    with pytest.raises(ConfigError):
        ScenarioConfig.from_dict(payload)


def test_discrete_grid_cannot_violate_electrolyzer_constraint():
    """Coherencia entre bloques: la malla no puede exceder el limite del paper."""
    with pytest.raises(ConfigError, match="malla discreta"):
        ScenarioConfig.from_dict({"electrolyzer": {"max_units": 30}})


def test_yaml_exponent_notation_is_coerced():
    """YAML 1.1 carga 1.0e6 como string; debe convertirse a float igualmente."""
    config = ScenarioConfig.from_dict({"metaheuristic": {"penalty_infeasible": "1.0e6"}})
    assert config.metaheuristic.penalty_infeasible == 1_000_000.0


def test_roundtrip_through_yaml(tmp_path):
    original = ScenarioConfig()
    path = dump_scenario(original, tmp_path / "scenario.yaml")
    assert load_scenario(path) == original


def test_shipped_scenarios_load():
    for name in ("paper_li2024", "trabajo1_discrete"):
        load_scenario("configs/{}.yaml".format(name))


def test_config_is_frozen():
    config = ScenarioConfig()
    with pytest.raises(Exception):
        config.constraints.agsr_max = 0.5


def test_replace_revalidates():
    config = ScenarioConfig()
    modified = config.replace(search=config.search)
    assert modified == config
