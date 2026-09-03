"""Generador de entrega/: estructura de archivos y coherencia del README."""

from dataclasses import replace

import pytest

from h2_hres.analysis.report import generate_report
from h2_hres.config.schema import ScenarioConfig


@pytest.fixture(scope="module")
def report_config(config):
    """Malla gruesa (sensibilidad rapida) + costo de bateria por energia."""
    return ScenarioConfig.from_dict(
        {
            "battery": {"duration_candidates_h": [1.0, 2.0]},
            "costs": {"battery": {"capex_cny_per_kwh": 500.0}},
            "search": {"wind_step_mw": 50.0, "electrolyzer_step_mw": 25.0},
            "metaheuristic": {"population": 5, "iterations": 3, "seed": 7},
        }
    )


@pytest.fixture(scope="module")
def generated_report(hourly, report_config, tmp_path_factory):
    out_dir = tmp_path_factory.mktemp("entrega")
    messages = []
    path = generate_report(
        hourly, report_config, year=2008, out_dir=out_dir,
        algorithms=("gwo", "random"), runs=2,
        agsr_values=(0.10, 0.30), min_load_values=(0.20, 0.40),
        on_progress=messages.append,
    )
    return path, messages


def test_generate_report_writes_the_expected_tree(generated_report):
    path, _ = generated_report
    expected = [
        "README.md",
        "configs/escenario_resuelto.yaml",
        "datos/history.csv",
        "datos/runs.csv",
        "tablas/validacion_paper.csv",
        "tablas/estadistica_algoritmos.csv",
        "tablas/tests_pareados.csv",
        "tablas/sensibilidad_agsr.csv",
        "tablas/sensibilidad_carga_minima.csv",
        "figuras/convergencia_por_algoritmo.png",
        "figuras/distribucion_scores.png",
        "figuras/calidad_vs_tiempo.png",
        "figuras/sensibilidad_agsr.png",
        "figuras/sensibilidad_carga_minima.png",
    ]
    for relative in expected:
        assert (path / relative).exists(), relative
        assert (path / relative).stat().st_size > 0, relative


def test_generate_report_notifies_each_stage(generated_report):
    _, messages = generated_report
    assert len(messages) == 4
    assert "Validando" in messages[0]
    assert "comparativa" in messages[1]
    assert "Barriendo" in messages[2]
    assert "README" in messages[3]


def test_readme_mentions_every_algorithm(generated_report):
    path, _ = generated_report
    readme = (path / "README.md").read_text(encoding="utf-8")
    assert "GWO" in readme
    assert "RANDOM" in readme.upper()


def test_readme_tables_match_the_csv_files(generated_report):
    """El README no puede quedar desincronizado de sus propios CSV."""
    import pandas as pd

    path, _ = generated_report
    readme = (path / "README.md").read_text(encoding="utf-8")

    stats = pd.read_csv(path / "tablas" / "estadistica_algoritmos.csv")
    for algorithm in stats["algorithm"]:
        assert algorithm in readme.lower() or algorithm.upper() in readme

    validation = pd.read_csv(path / "tablas" / "validacion_paper.csv")
    n_ok = int((validation["veredicto"] == "OK").sum())
    assert "{} de {} objetivos".format(n_ok, len(validation)) in readme


def test_generate_report_skips_pairwise_with_one_algorithm(hourly, report_config, tmp_path):
    path = generate_report(
        hourly, report_config, year=2008, out_dir=tmp_path / "entrega",
        algorithms=("gwo",), runs=2,
        agsr_values=(0.10, 0.30), min_load_values=(0.20, 0.40),
    )
    assert not (path / "tablas" / "tests_pareados.csv").exists()
    readme = (path / "README.md").read_text(encoding="utf-8")
    assert "No se corrieron tests pareados" in readme


def test_generate_report_is_idempotent_on_the_same_directory(hourly, report_config, tmp_path):
    """Regenerar sobre la misma carpeta reemplaza el contenido, no lo apila."""
    out_dir = tmp_path / "entrega"
    generate_report(
        hourly, report_config, year=2008, out_dir=out_dir,
        algorithms=("gwo",), runs=2,
        agsr_values=(0.10,), min_load_values=(0.20,),
    )
    generate_report(
        hourly, report_config, year=2008, out_dir=out_dir,
        algorithms=("gwo", "random"), runs=2,
        agsr_values=(0.10,), min_load_values=(0.20,),
    )

    import pandas as pd

    stats = pd.read_csv(out_dir / "tablas" / "estadistica_algoritmos.csv")
    assert set(stats["algorithm"]) == {"gwo", "random"}
