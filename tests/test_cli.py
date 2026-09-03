"""CLI: parser, salidas en disco y manejo de errores."""

import json

import pytest

from h2_hres.cli import build_parser, main
from h2_hres.data.cache import save_years
from conftest import make_year


@pytest.fixture
def data_dir(tmp_path):
    """Dos anos en disco; ninguna descarga de red."""
    folder = tmp_path / "wpeb_data"
    save_years({2007: make_year(1), 2008: make_year(2)}, folder)
    return folder


def test_parser_requires_a_subcommand():
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_info_reports_the_environment(capsys):
    assert main(["info"]) == 0
    output = capsys.readouterr().out
    assert "Aceleracion:" in output
    assert "gwo" in output
    assert "consumo especifico" in output


def test_typical_year_writes_its_evidence(tmp_path, data_dir, capsys):
    out = tmp_path / "results"
    assert main(["typical-year", "--data-dir", str(data_dir), "--out", str(out)]) == 0
    assert "Ano tipico" in capsys.readouterr().out

    run_dir = next(out.iterdir())
    for name in ("config.yaml", "complementarity_summary.csv", "typical_year_selection.png"):
        assert (run_dir / name).exists()


def test_grid_search_writes_results_and_figures(tmp_path, data_dir):
    out = tmp_path / "results"
    code = main([
        "grid-search", "--data-dir", str(data_dir), "--out", str(out),
        "--year", "2008", "--quiet",
    ])
    assert code == 0

    run_dir = next(out.iterdir())
    assert (run_dir / "grid_results.csv").exists()
    assert (run_dir / "feasible_domain.png").exists()

    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["analysis_year"] == 2008
    assert summary["evaluated"] == 420


def test_cases_compares_against_the_paper(tmp_path, data_dir, capsys):
    out = tmp_path / "results"
    assert main([
        "cases", "--data-dir", str(data_dir), "--out", str(out), "--year", "2008",
    ]) == 0
    assert "W190-P10-E95" in capsys.readouterr().out

    run_dir = next(out.iterdir())
    assert (run_dir / "case_comparison.csv").exists()
    assert (run_dir / "paper_comparison.csv").exists()


def test_optimize_runs_multiple_seeds(tmp_path, data_dir, capsys):
    out = tmp_path / "results"
    config = tmp_path / "small.yaml"
    config.write_text(
        "name: test\nmetaheuristic:\n  population: 5\n  iterations: 3\n  seed: 42\n",
        encoding="utf-8",
    )

    code = main([
        "optimize", "--config", str(config), "--data-dir", str(data_dir),
        "--out", str(out), "--year", "2008", "--algorithm", "gwo", "--runs", "2",
    ])
    assert code == 0
    assert "Estadistica sobre 2 corridas" in capsys.readouterr().out

    run_dir = next(out.iterdir())
    for name in ("history.csv", "runs.csv", "statistics.csv", "best.json", "convergence.png"):
        assert (run_dir / name).exists()

    best = json.loads((run_dir / "best.json").read_text(encoding="utf-8"))
    assert best["analysis_year"] == 2008
    assert "score" in best


def test_compare_runs_several_algorithms_and_writes_statistics(tmp_path, data_dir, capsys):
    out = tmp_path / "results"
    config = tmp_path / "small.yaml"
    config.write_text(
        "name: test\n"
        "battery:\n  duration_candidates_h: [1.0, 2.0]\n"
        "costs:\n  battery:\n    capex_cny_per_kwh: 500.0\n"
        "metaheuristic:\n  population: 5\n  iterations: 3\n  seed: 42\n",
        encoding="utf-8",
    )

    code = main([
        "compare", "--config", str(config), "--data-dir", str(data_dir),
        "--out", str(out), "--year", "2008", "--algorithms", "gwo,random", "--runs", "3",
    ])
    assert code == 0
    output = capsys.readouterr().out
    assert "Ranking por mejor score" in output
    assert "Wilcoxon pareado" in output

    run_dir = next(out.iterdir())
    for name in (
        "history.csv", "runs.csv", "statistics.csv", "pairwise_tests.csv",
        "best.json", "convergence_by_algorithm.png", "score_boxplot.png",
        "quality_vs_time.png",
    ):
        assert (run_dir / name).exists()

    import pandas as pd

    runs = pd.read_csv(run_dir / "runs.csv")
    assert set(runs["algorithm"]) == {"gwo", "random"}
    assert len(runs) == 6  # 2 algoritmos x 3 semillas

    stats = pd.read_csv(run_dir / "statistics.csv")
    assert len(stats) == 2  # una fila por algoritmo


def test_compare_rejects_unknown_algorithm(tmp_path, data_dir, capsys):
    code = main([
        "compare", "--data-dir", str(data_dir), "--out", str(tmp_path),
        "--year", "2008", "--algorithms", "gwo,no_existe", "--runs", "2",
    ])
    assert code == 1
    assert "no_existe" in capsys.readouterr().err


def test_compare_skips_pairwise_tests_with_a_single_algorithm(tmp_path, data_dir, capsys):
    out = tmp_path / "results"
    config = tmp_path / "small.yaml"
    config.write_text(
        "name: test\nmetaheuristic:\n  population: 5\n  iterations: 3\n  seed: 42\n",
        encoding="utf-8",
    )
    code = main([
        "compare", "--config", str(config), "--data-dir", str(data_dir),
        "--out", str(out), "--year", "2008", "--algorithms", "gwo", "--runs", "2",
    ])
    assert code == 0
    assert "Sin comparaciones pareadas" in capsys.readouterr().out

    run_dir = next(out.iterdir())
    assert not (run_dir / "pairwise_tests.csv").exists()


def test_sensitivity_sweeps_both_parameters(tmp_path, data_dir, capsys):
    out = tmp_path / "results"
    config = tmp_path / "coarse.yaml"
    config.write_text(
        "name: test\nsearch:\n  wind_step_mw: 50.0\n  electrolyzer_step_mw: 25.0\n",
        encoding="utf-8",
    )

    code = main([
        "sensitivity", "--config", str(config), "--data-dir", str(data_dir),
        "--out", str(out), "--year", "2008", "--quiet",
    ])
    assert code == 0
    output = capsys.readouterr().out
    assert "agsr_max" in output
    assert "min_load_ratio" in output

    run_dir = next(out.iterdir())
    for name in (
        "sensitivity_agsr_max.csv", "sensitivity_min_load_ratio.csv",
        "sensitivity_agsr_max.png", "sensitivity_min_load_ratio.png",
    ):
        assert (run_dir / name).exists()

    import pandas as pd

    agsr = pd.read_csv(run_dir / "sensitivity_agsr_max.csv")
    assert len(agsr) == 5  # AGSR_MAX_VALUES por defecto


def test_report_writes_entrega_with_readme(tmp_path, data_dir, capsys):
    out = tmp_path / "entrega"
    config = tmp_path / "small.yaml"
    config.write_text(
        "name: test\n"
        "battery:\n  duration_candidates_h: [1.0, 2.0]\n"
        "costs:\n  battery:\n    capex_cny_per_kwh: 500.0\n"
        "search:\n  wind_step_mw: 50.0\n  electrolyzer_step_mw: 25.0\n"
        "metaheuristic:\n  population: 5\n  iterations: 3\n  seed: 42\n",
        encoding="utf-8",
    )

    code = main([
        "report", "--config", str(config), "--data-dir", str(data_dir),
        "--out", str(out), "--year", "2008", "--algorithms", "gwo,random", "--runs", "2",
    ])
    assert code == 0
    output = capsys.readouterr().out
    assert "Entrega escrita en" in output

    assert (out / "README.md").exists()
    assert (out / "tablas" / "validacion_paper.csv").exists()
    assert (out / "figuras" / "convergencia_por_algoritmo.png").exists()


def test_report_default_output_directory_is_entrega():
    parser = build_parser()
    args = parser.parse_args(["report"])
    assert args.out == "entrega"


def test_missing_data_directory_is_reported(tmp_path, capsys):
    code = main(["grid-search", "--data-dir", str(tmp_path / "vacio"), "--out", str(tmp_path)])
    assert code == 1
    assert "h2hres download" in capsys.readouterr().err


def test_unknown_year_is_reported(tmp_path, data_dir, capsys):
    code = main([
        "grid-search", "--data-dir", str(data_dir), "--out", str(tmp_path),
        "--year", "1999", "--quiet",
    ])
    assert code == 1
    assert "1999" in capsys.readouterr().err
