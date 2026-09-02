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
