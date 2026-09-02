"""Interfaz de linea de comandos.

Cada corrida escribe un directorio autocontenido bajo ``results/`` con la
configuracion resuelta, las tablas y las figuras: reproducir un resultado no
depende de recordar que celdas se ejecutaron ni en que orden.

    h2hres download     --config configs/paper_li2024.yaml
    h2hres typical-year --config configs/paper_li2024.yaml
    h2hres grid-search  --config configs/paper_li2024.yaml
    h2hres cases        --config configs/paper_li2024.yaml
    h2hres validate     --config configs/paper_li2024.yaml
    h2hres optimize     --config configs/trabajo1_discrete.yaml --algorithm gwo --runs 10
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .analysis.plots import (
    plot_convergence,
    plot_feasible_domain,
    plot_lcoe_heatmap,
    plot_typical_year_selection,
    save_figure,
)
from .analysis.validation import resource_metrics, validate_scenario
from .analysis.summaries import (
    aggregate_runs,
    compare_to_paper,
    evaluate_named_cases,
    summarize_grid,
)
from .config.loader import default_scenario, dump_scenario, load_scenario
from .config.schema import ScenarioConfig
from .data.cache import DEFAULT_FOLDER, get_or_download, load_years
from .data.typical_year import choose_typical_year, validate_against_paper
from .optimization.encoding import DecisionSpace
from .optimization.exhaustive import run_grid_search
from .optimization.metaheuristics import REGISTRY, get_optimizer
from .optimization.objectives import ObjectiveFunction
from .simulation.dispatch import NUMBA_STATUS

__all__ = ["main", "build_parser"]


# ---------------------------------------------------------------------------
# Utilidades compartidas
# ---------------------------------------------------------------------------


def _load_config(args: argparse.Namespace) -> ScenarioConfig:
    if args.config:
        return load_scenario(args.config)
    return default_scenario()


def _run_directory(base: str, label: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = Path(base) / "{}_{}".format(stamp, label)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _resolve_year(
    config: ScenarioConfig, yearly: Dict[int, pd.DataFrame], explicit: Optional[int]
) -> int:
    """Ano de analisis: explicito, el del escenario, o el tipico por calculo."""
    if explicit is not None:
        return explicit
    if config.site.analysis_year is not None:
        return config.site.analysis_year
    return choose_typical_year(yearly, config.site.utc_offset_hours).typical_year


def _load_analysis_year(
    config: ScenarioConfig, args: argparse.Namespace
) -> tuple:
    yearly = load_years(args.data_dir)
    year = _resolve_year(config, yearly, args.year)
    if year not in yearly:
        raise ValueError(
            "el ano {} no esta en {}. Anos disponibles: {}".format(
                year, args.data_dir, sorted(yearly)
            )
        )
    return year, yearly[year]


# ---------------------------------------------------------------------------
# Subcomandos
# ---------------------------------------------------------------------------


def cmd_download(args: argparse.Namespace) -> int:
    config = _load_config(args)
    yearly = get_or_download(
        config.site,
        folder=args.data_dir,
        force_download=args.force,
        hub_height_m=config.wind.hub_height_m,
        wind_surface=config.wind.wind_surface,
    )
    print(
        "Viento corregido a {:.0f} m sobre superficie '{}'".format(
            config.wind.hub_height_m, config.wind.wind_surface
        )
    )
    print("Anos disponibles en {}: {}".format(args.data_dir, sorted(yearly)))
    print("Horas por ano: {}".format({y: len(d) for y, d in sorted(yearly.items())}))
    return 0


def cmd_typical_year(args: argparse.Namespace) -> int:
    config = _load_config(args)
    yearly = load_years(args.data_dir)
    selection = choose_typical_year(yearly, config.site.utc_offset_hours)

    print("Ano tipico por complementariedad viento-solar: {}".format(selection.typical_year))
    print("Dias agrupados en hora local (UTC{:+.0f})".format(config.site.utc_offset_hours))
    print()
    print(selection.summary["euclidean_distance"].round(6).to_string())

    validation = validate_against_paper(selection.global_distribution)
    print()
    print("Distribucion de largo plazo contra las cifras del paper (§2.2.3):")
    print(
        validation.to_string(
            index=False, float_format=lambda v: "{:,.4f}".format(v)
        )
    )
    if selection.typical_year != 2008:
        print()
        print(
            "NOTA: el paper reporta 2008. Si la distribucion de arriba calza, la "
            "diferencia viene de revisiones de los datos NASA POWER, no del metodo."
        )

    run_dir = _run_directory(args.out, "typical-year")
    dump_scenario(config, run_dir / "config.yaml")
    selection.summary.to_csv(run_dir / "complementarity_summary.csv")
    validation.to_csv(run_dir / "complementarity_validation.csv", index=False)
    save_figure(
        plot_typical_year_selection(selection.summary),
        run_dir / "typical_year_selection.png",
    )
    print()
    print("Resultados en {}".format(run_dir))
    return 0


def cmd_grid_search(args: argparse.Namespace) -> int:
    config = _load_config(args)
    year, hourly = _load_analysis_year(config, args)
    print("Ano de analisis: {} ({} horas)".format(year, len(hourly)))

    results = run_grid_search(hourly, config, progress=not args.quiet)
    summary = summarize_grid(results)

    print()
    for key, value in summary.items():
        print("  {:26s} {}".format(key, value))

    run_dir = _run_directory(args.out, "grid-search")
    dump_scenario(config, run_dir / "config.yaml")
    results.to_csv(run_dir / "grid_results.csv", index=False)
    (run_dir / "summary.json").write_text(
        json.dumps({"analysis_year": year, **summary}, indent=2), encoding="utf-8"
    )
    save_figure(plot_feasible_domain(results), run_dir / "feasible_domain.png")
    heatmap = plot_lcoe_heatmap(results)
    if heatmap is not None:
        save_figure(heatmap, run_dir / "lcoe_heatmap.png")

    print()
    print("Resultados en {}".format(run_dir))
    return 0


def cmd_cases(args: argparse.Namespace) -> int:
    config = _load_config(args)
    year, hourly = _load_analysis_year(config, args)
    print("Ano de analisis: {}".format(year))

    table = evaluate_named_cases(hourly, config)
    columns = [
        "case", "wind_mw", "pv_mw", "electrolyzer_mw", "battery_mw",
        "feasible", "agsr", "electrolyzer_cf", "lcoe_cny_per_kwh", "lcoh_cny_per_kg",
    ]
    print()
    print(table[columns].to_string(index=False, float_format=lambda v: "{:,.4f}".format(v)))

    comparison = compare_to_paper(table)
    print()
    print("Contraste con los valores reportados por el paper:")
    print(comparison.to_string(index=False, float_format=lambda v: "{:,.4f}".format(v)))

    run_dir = _run_directory(args.out, "cases")
    dump_scenario(config, run_dir / "config.yaml")
    table.to_csv(run_dir / "case_comparison.csv", index=False)
    comparison.to_csv(run_dir / "paper_comparison.csv", index=False)
    print()
    print("Resultados en {}".format(run_dir))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Contrasta la replicacion completa contra las cifras publicadas."""
    config = _load_config(args)
    year, hourly = _load_analysis_year(config, args)

    resource = resource_metrics(hourly, config)
    print("Ano de analisis: {} | viento desde la columna '{}'".format(
        year, resource["wind_column"]))
    print("  viento medio a 50 m   {:6.2f} m/s   (paper: 7.56)".format(
        resource["mean_wind_speed_50m"]))
    if np.isfinite(resource["mean_hub_wind_speed"]):
        print("  viento medio a {:.0f} m   {:6.2f} m/s".format(
            config.wind.hub_height_m, resource["mean_hub_wind_speed"]))
    print("  GHI anual             {:6.0f} kWh/m2 (paper: 1731)".format(
        resource["annual_ghi_kwh_m2"]))
    print()

    table = validate_scenario(hourly, config)
    print(table.to_string(index=False, float_format=lambda v: "{:,.4f}".format(v)))

    failures = table[table["veredicto"] == "REVISAR"]
    print()
    print("{} de {} objetivos dentro de tolerancia.".format(
        len(table) - len(failures), len(table)))

    run_dir = _run_directory(args.out, "validate")
    dump_scenario(config, run_dir / "config.yaml")
    table.to_csv(run_dir / "paper_validation.csv", index=False)
    print("Resultados en {}".format(run_dir))
    return 0


def cmd_optimize(args: argparse.Namespace) -> int:
    config = _load_config(args)
    year, hourly = _load_analysis_year(config, args)

    optimizer_class = get_optimizer(args.algorithm)
    base_seed = args.seed if args.seed is not None else config.metaheuristic.seed
    seeds = [base_seed + offset for offset in range(args.runs)]

    for message in DecisionSpace(config).warnings():
        print("AVISO: {}".format(message))

    print("Ano de analisis: {} | algoritmo: {} | semillas: {}".format(
        year, args.algorithm, seeds))
    print("Presupuesto por corrida: {} evaluaciones ({} x {})".format(
        config.metaheuristic.evaluation_budget,
        config.metaheuristic.population,
        config.metaheuristic.iterations,
    ))
    print()

    # Un solo objetivo compartido: el cache de perfiles persiste entre corridas.
    objective = ObjectiveFunction(hourly, config)

    histories: List[pd.DataFrame] = []
    summaries: List[Dict[str, object]] = []

    for seed in seeds:
        result = optimizer_class(objective, seed=seed).optimize()
        best = result.best.result
        print(
            "  semilla {:<5} score={:.6f} feasible={!s:<5} "
            "W{:.1f} E{:.0f} B{:.0f}MW/{:.0f}h AGSR={:.4f} CF={:.4f} ({:.1f}s)".format(
                seed, result.best_score, best.feasible, best.wind_mw,
                best.electrolyzer_mw, best.battery_mw, best.battery_duration_h,
                best.agsr, best.electrolyzer_cf, result.elapsed_s,
            )
        )
        history = result.history.copy()
        history["seed"] = seed
        histories.append(history)
        summaries.append(result.summary())

    all_history = pd.concat(histories, ignore_index=True)
    all_summaries = pd.DataFrame(summaries)
    statistics = aggregate_runs(summaries)

    print()
    print("Estadistica sobre {} corridas:".format(args.runs))
    print(statistics.to_string(index=False, float_format=lambda v: "{:,.6f}".format(v)))

    run_dir = _run_directory(args.out, "{}-{}".format(args.algorithm, base_seed))
    dump_scenario(config, run_dir / "config.yaml")
    all_history.to_csv(run_dir / "history.csv", index=False)
    all_summaries.to_csv(run_dir / "runs.csv", index=False)
    statistics.to_csv(run_dir / "statistics.csv", index=False)

    best_overall = min(summaries, key=lambda row: row["score"])
    (run_dir / "best.json").write_text(
        json.dumps({"analysis_year": year, **best_overall}, indent=2, default=str),
        encoding="utf-8",
    )
    save_figure(
        plot_convergence(all_history, args.algorithm), run_dir / "convergence.png"
    )

    print()
    print("Resultados en {}".format(run_dir))
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """Estado del entorno: util para explicar diferencias de rendimiento."""
    from . import __version__

    config = _load_config(args)
    print("h2_hres {}".format(__version__))
    print("Aceleracion: {}".format(NUMBA_STATUS))
    print("Algoritmos registrados: {}".format(", ".join(sorted(REGISTRY))))
    print("Escenario: {}".format(config.name))
    print("  capacidad total   {:.0f} MW".format(
        config.constraints.total_generation_capacity_mw))
    print("  AGSR maximo       {:.0%}".format(config.constraints.agsr_max))
    print("  consumo especifico {:.4f} kWh/kg".format(
        config.electrolyzer.specific_consumption_kwh_per_kg))
    print("  base del LCOE     {}".format(config.economics.lcoe_energy_basis))
    for message in DecisionSpace(config).warnings():
        print("AVISO: {}".format(message))
    return 0


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="h2hres",
        description="Replicacion y extension discreta del sistema WPEB (Li et al. 2024).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument(
            "--config", help="escenario YAML; si se omite, se usan los defaults del paper"
        )
        subparser.add_argument(
            "--data-dir", default=DEFAULT_FOLDER,
            help="directorio de datos NASA POWER (default: %(default)s)",
        )
        subparser.add_argument(
            "--out", default="results", help="directorio de salida (default: %(default)s)"
        )

    download = subparsers.add_parser("download", help="descarga los datos NASA POWER")
    add_common(download)
    download.add_argument(
        "--force", action="store_true", help="vuelve a descargar los anos ya presentes"
    )
    download.set_defaults(func=cmd_download)

    typical = subparsers.add_parser(
        "typical-year", help="selecciona el ano tipico por complementariedad"
    )
    add_common(typical)
    typical.set_defaults(func=cmd_typical_year)

    grid = subparsers.add_parser("grid-search", help="barrido exhaustivo del modelo base")
    add_common(grid)
    grid.add_argument("--year", type=int, help="fuerza el ano de analisis")
    grid.add_argument("--quiet", action="store_true", help="oculta la barra de progreso")
    grid.set_defaults(func=cmd_grid_search)

    cases = subparsers.add_parser("cases", help="evalua los casos con nombre del paper")
    add_common(cases)
    cases.add_argument("--year", type=int, help="fuerza el ano de analisis")
    cases.set_defaults(func=cmd_cases)

    optimize = subparsers.add_parser(
        "optimize", help="optimiza el diseno discreto con una metaheuristica"
    )
    add_common(optimize)
    optimize.add_argument("--year", type=int, help="fuerza el ano de analisis")
    optimize.add_argument(
        "--algorithm", default="gwo", choices=sorted(REGISTRY),
        help="algoritmo a usar (default: %(default)s)",
    )
    optimize.add_argument(
        "--runs", type=int, default=1,
        help="numero de semillas consecutivas a correr (default: %(default)s)",
    )
    optimize.add_argument("--seed", type=int, help="semilla inicial")
    optimize.set_defaults(func=cmd_optimize)

    validate = subparsers.add_parser(
        "validate", help="contrasta la replicacion contra las cifras del paper"
    )
    add_common(validate)
    validate.add_argument("--year", type=int, help="fuerza el ano de analisis")
    validate.set_defaults(func=cmd_validate)

    info = subparsers.add_parser("info", help="estado del entorno y del escenario")
    add_common(info)
    info.set_defaults(func=cmd_info)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as exc:
        print("Error: {}".format(exc), file=sys.stderr)
        print(
            "Sugerencia: ejecuta primero 'h2hres download' para obtener los datos.",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print("Error: {}".format(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
