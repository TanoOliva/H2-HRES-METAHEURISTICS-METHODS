"""Genera la carpeta ``entrega/``: comparativa, sensibilidad, validacion y el
MD maestro que resume todo para el documento de titulo.

Encadena tres piezas que ya existen por separado -- ``h2hres validate``,
``h2hres compare`` y ``h2hres sensitivity`` -- y consolida sus resultados en un
directorio fijo (sin timestamp), apto para versionar: el documento siempre
apunta a las mismas rutas, y ``git diff`` sobre ``entrega/`` muestra que
cambio entre una corrida y la siguiente. Las corridas individuales siguen
yendo a ``results/<timestamp>_*/`` como antes; esto solo consolida.

Las tablas del README se inyectan desde los DataFrames en el momento de
generar, nunca se escriben a mano: el README no puede quedar desincronizado
de los CSV que lo acompanan.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, Optional, Sequence, Union

import pandas as pd

from ..config.loader import dump_scenario
from ..config.schema import ScenarioConfig
from ..optimization.comparison import run_comparison
from ..optimization.objectives import ObjectiveFunction
from ..simulation.simulator import HourlyData
from .comparison_plots import (
    plot_convergence_by_algorithm,
    plot_quality_vs_time,
    plot_score_boxplot,
    plot_sensitivity_sweep,
)
from .plots import save_figure
from .sensitivity import AGSR_MAX_VALUES, MIN_LOAD_RATIO_VALUES, run_sensitivity_study
from .statistics import comparison_table, pairwise_wilcoxon
from .validation import resource_metrics, validate_scenario

__all__ = ["generate_report", "DEFAULT_ALGORITHMS"]

PathLike = Union[str, Path]

DEFAULT_ALGORITHMS: Sequence[str] = ("gwo", "pso", "ga", "random")


def generate_report(
    hourly: HourlyData,
    config: ScenarioConfig,
    year: int,
    out_dir: PathLike = "entrega",
    algorithms: Sequence[str] = DEFAULT_ALGORITHMS,
    runs: int = 30,
    seed: Optional[int] = None,
    agsr_values: Sequence[float] = AGSR_MAX_VALUES,
    min_load_values: Sequence[float] = MIN_LOAD_RATIO_VALUES,
    on_progress: Optional[Callable[[str], None]] = None,
) -> Path:
    """Corre validacion, comparativa y sensibilidad, y escribe ``entrega/``.

    Devuelve la ruta del directorio escrito. ``on_progress``, si se da, recibe
    un mensaje de una linea por etapa -- la CLI lo usa para mostrar avance;
    esta funcion no imprime nada por su cuenta, siguiendo la convencion del
    resto de ``analysis/`` (devolver datos, no I/O).
    """

    def notify(message: str) -> None:
        if on_progress is not None:
            on_progress(message)

    out = Path(out_dir)
    figures_dir = out / "figuras"
    tables_dir = out / "tablas"
    configs_dir = out / "configs"
    data_dir = out / "datos"
    for directory in (figures_dir, tables_dir, configs_dir, data_dir):
        directory.mkdir(parents=True, exist_ok=True)

    dump_scenario(config, configs_dir / "escenario_resuelto.yaml")

    notify("Validando la replicacion contra el paper...")
    resource = resource_metrics(hourly, config) if isinstance(hourly, pd.DataFrame) else {}
    validation_table = validate_scenario(hourly, config)
    validation_table.to_csv(tables_dir / "validacion_paper.csv", index=False)

    notify(
        "Corriendo la comparativa de metaheuristicas ({} algoritmos x {} "
        "semillas)...".format(len(algorithms), runs)
    )
    objective = ObjectiveFunction(hourly, config)
    base_seed = seed if seed is not None else config.metaheuristic.seed
    seeds = [base_seed + offset for offset in range(runs)]
    history, run_table = run_comparison(objective, algorithms, seeds)
    history.to_csv(data_dir / "history.csv", index=False)
    run_table.to_csv(data_dir / "runs.csv", index=False)

    stats_table = comparison_table(run_table)
    stats_table.to_csv(tables_dir / "estadistica_algoritmos.csv", index=False)

    pairwise_table: Optional[pd.DataFrame] = None
    if len(algorithms) >= 2 and runs >= 2:
        pairwise_table = pairwise_wilcoxon(run_table)
        pairwise_table.to_csv(tables_dir / "tests_pareados.csv", index=False)

    save_figure(
        plot_convergence_by_algorithm(history),
        figures_dir / "convergencia_por_algoritmo.png",
    )
    save_figure(plot_score_boxplot(run_table), figures_dir / "distribucion_scores.png")
    save_figure(plot_quality_vs_time(run_table), figures_dir / "calidad_vs_tiempo.png")

    notify("Barriendo AGSR maximo y carga minima del electrolizador...")
    sensitivity = run_sensitivity_study(hourly, config, agsr_values, min_load_values)
    sensitivity["agsr_max"].to_csv(tables_dir / "sensibilidad_agsr.csv", index=False)
    sensitivity["min_load_ratio"].to_csv(
        tables_dir / "sensibilidad_carga_minima.csv", index=False
    )
    save_figure(
        plot_sensitivity_sweep(sensitivity["agsr_max"], "Limite AGSR"),
        figures_dir / "sensibilidad_agsr.png",
    )
    save_figure(
        plot_sensitivity_sweep(
            sensitivity["min_load_ratio"], "Carga minima del electrolizador"
        ),
        figures_dir / "sensibilidad_carga_minima.png",
    )

    notify("Escribiendo entrega/README.md...")
    readme = _build_readme(
        config=config,
        year=year,
        resource=resource,
        validation_table=validation_table,
        stats_table=stats_table,
        pairwise_table=pairwise_table,
        algorithms=list(algorithms),
        runs=runs,
        sensitivity=sensitivity,
    )
    (out / "README.md").write_text(readme, encoding="utf-8")

    return out


# ---------------------------------------------------------------------------
# Tabla markdown minima, sin depender de ``tabulate`` (no es dependencia del
# paquete; agregarla solo para esto no se justifica).
# ---------------------------------------------------------------------------


def _markdown_table(df: pd.DataFrame, float_format: str = "{:.4f}") -> str:
    def fmt(value: object) -> str:
        if isinstance(value, bool):
            return "si" if value else "no"
        if isinstance(value, float):
            return float_format.format(value)
        return str(value)

    header = "| " + " | ".join(str(c) for c in df.columns) + " |"
    sep = "| " + " | ".join("---" for _ in df.columns) + " |"
    rows = [
        "| " + " | ".join(fmt(v) for v in row) + " |"
        for row in df.itertuples(index=False, name=None)
    ]
    return "\n".join([header, sep] + rows)


def _build_readme(
    config: ScenarioConfig,
    year: int,
    resource: Dict[str, object],
    validation_table: pd.DataFrame,
    stats_table: pd.DataFrame,
    pairwise_table: Optional[pd.DataFrame],
    algorithms: list,
    runs: int,
    sensitivity: Dict[str, pd.DataFrame],
) -> str:
    n_ok = int((validation_table["veredicto"] == "OK").sum())
    n_total = len(validation_table)

    best_row = stats_table.iloc[0]
    worst_row = stats_table.iloc[-1]

    if pairwise_table is not None and len(pairwise_table) > 0:
        n_significant = int(pairwise_table["significativo_alpha_0.05"].sum())
        n_pairs = len(pairwise_table)
    else:
        n_significant = n_pairs = 0

    agsr = sensitivity["agsr_max"].sort_values("value")
    min_load = sensitivity["min_load_ratio"].sort_values("value")

    agsr_lcoe_delta = (
        agsr["best_lcoe_cny_per_kwh"].iloc[-1] - agsr["best_lcoe_cny_per_kwh"].iloc[0]
    )
    agsr_feasible_delta = agsr["feasible"].iloc[-1] - agsr["feasible"].iloc[0]

    min_load_lcoe_delta = (
        min_load["best_lcoe_cny_per_kwh"].iloc[-1] - min_load["best_lcoe_cny_per_kwh"].iloc[0]
    )
    min_load_feasible_delta = min_load["feasible"].iloc[-1] - min_load["feasible"].iloc[0]

    budget = config.metaheuristic.evaluation_budget

    lines = []
    add = lines.append

    # -- 1. Que es esto -----------------------------------------------------
    add("# Comparativa de metaheuristicas sobre el sistema WPEB")
    add("")
    add(
        "Extension discreta de Li et al. (2024), *Capacity optimization of a "
        "wind-photovoltaic-electrolysis-battery (WPEB) hybrid energy system for "
        "power and hydrogen generation*, resuelta con cuatro metaheuristicas y "
        "contrastada con un estudio de sensibilidad sobre las dos restricciones "
        "que fijan el dominio factible del paper."
    )
    add("")
    add(
        "**Estado de la replicacion del paper** ({} de {} objetivos publicados "
        "dentro de tolerancia): ver `tablas/validacion_paper.csv` y "
        "`CHANGELOG.md` en la raiz del repositorio para el detalle de cada "
        "correccion de modelado y su efecto medido.".format(n_ok, n_total)
    )
    add("")
    add(_markdown_table(validation_table[["metrica", "paper", "replicacion", "desvio_pct", "veredicto"]]))
    add("")

    # -- 2. Metodologia -------------------------------------------------------
    add("## Metodologia")
    add("")
    add(
        "- **Modelo**: simulacion horaria (8760-8784 h, ano {}) del despacho "
        "WPEB descrito en `src/h2_hres/simulation/`.".format(year)
    )
    add(
        "- **Espacio de decision** (4 variables, `optimization/encoding.py`): "
        "capacidad eolica continua (PV = 200 - eolica), unidades de "
        "electrolizador enteras (5 MW cada una), potencia de bateria en "
        "multiplos de 5 MW, duracion de bateria discreta {1, 2, 4} h."
    )
    add(
        "- **Objetivo**: LCOE, igual que el paper. Una solucion infactible "
        "(AGSR > {:.0%}) recibe una penalizacion proporcional a cuanto la "
        "viola, para que el optimizador tenga gradiente hacia la region "
        "factible en vez de un muro.".format(config.constraints.agsr_max)
    )
    add(
        "- **Presupuesto**: {} evaluaciones por corrida ({} individuos x {} "
        "iteraciones), identico para los cuatro algoritmos -- es la condicion "
        "para que la comparacion sea justa, y los tests del paquete la "
        "verifican automaticamente para cualquier algoritmo nuevo que se "
        "registre.".format(budget, config.metaheuristic.population, config.metaheuristic.iterations)
    )
    add(
        "- **Reproducibilidad**: {} semillas consecutivas por algoritmo, "
        "compartiendo un unico cache de perfiles de generacion (mismo dato "
        "meteorologico, mismo modelo, para los cuatro).".format(runs)
    )
    add("")

    # -- 3. Que se comparo ----------------------------------------------------
    add("## Que se comparo")
    add("")
    add("| Algoritmo | Familia | Hiperparametros | Fuente |")
    add("|---|---|---|---|")
    add(
        "| GWO | Enjambre jerarquico | jerarquia alpha-beta-delta, "
        "`a` decae 2->0 | Mirjalili et al. (2014) |"
    )
    add(
        "| PSO | Enjambre | constriccion Clerc-Kennedy: chi={:.3f}, "
        "c1=c2={:.5f} | Clerc & Kennedy (2002) |".format(
            config.metaheuristic.pso.inertia, config.metaheuristic.pso.cognitive
        )
    )
    add(
        "| GA | Evolutivo | torneo k={}, BLX-alpha, mutacion gaussiana "
        "sigma={:.0%} del rango, elite={} | estandar real-coded GA |".format(
            config.metaheuristic.ga.tournament_size,
            config.metaheuristic.ga.mutation_sigma_ratio,
            config.metaheuristic.ga.elite_count,
        )
    )
    add("| random | Linea base | muestreo uniforme sobre la malla discreta | -- |")
    add("")
    add(
        "Los hiperparametros de PSO y GA son los valores canonicos de la "
        "literatura, no un ajuste fino a este problema: la comparativa no "
        "debe leerse como un torneo con un favorito afinado. Ver "
        "`configs/metaheuristicas.yaml` para el escenario completo."
    )
    add("")

    # -- 4. Resultados --------------------------------------------------------
    add("## Resultados")
    add("")
    add(
        "Ranking por mejor score alcanzado (menor LCOE penalizado es mejor), "
        "sobre {} semillas por algoritmo:".format(runs)
    )
    add("")
    add(_markdown_table(
        stats_table[["ranking", "algorithm", "runs", "best", "mean", "std", "worst", "feasible_runs"]]
    ))
    add("")
    add(
        "**{}** obtuvo el mejor score ({:.6f}); **{}** el peor ({:.6f}). Ver "
        "`figuras/convergencia_por_algoritmo.png` (mediana y rango "
        "intercuartil de convergencia) y `figuras/distribucion_scores.png` "
        "(dispersion de resultados finales).".format(
            best_row["algorithm"].upper(), best_row["best"],
            worst_row["algorithm"].upper(), worst_row["best"],
        )
    )
    add("")
    if pairwise_table is not None and len(pairwise_table) > 0:
        add(
            "**Significancia estadistica** (Wilcoxon pareado por semilla, "
            "corregido por Holm-Bonferroni sobre los {} pares; A12 es el "
            "tamano del efecto de Vargha-Delaney -- 0.5 = indistinguibles, "
            "1.0 = el primero domina siempre):".format(n_pairs)
        )
        add("")
        add(_markdown_table(
            pairwise_table[
                ["algoritmo_a", "algoritmo_b", "mediana_a", "mediana_b", "p_value_holm", "a12", "significativo_alpha_0.05"]
            ]
        ))
        add("")
        add(
            "{} de {} pares muestran una diferencia significativa a alpha=0.05 "
            "tras la correccion. Ver `figuras/calidad_vs_tiempo.png` para el "
            "trade-off entre calidad alcanzada y tiempo de computo por "
            "corrida.".format(n_significant, n_pairs)
        )
    else:
        add(
            "No se corrieron tests pareados (hacen falta al menos dos "
            "algoritmos y dos semillas comunes)."
        )
    add("")

    # -- 5. Sensibilidad --------------------------------------------------------
    add("## Sensibilidad")
    add("")
    add(
        "Barridos deterministas con `run_grid_search` sobre el modelo base "
        "(sin metaheuristica, sin ruido de semilla), variando un parametro a "
        "la vez desde el escenario de replicacion."
    )
    add("")
    add("### Limite de AGSR")
    add("")
    add(_markdown_table(
        agsr[["value", "feasible", "feasible_share", "best_lcoe_cny_per_kwh", "best_wind_mw", "best_electrolyzer_mw"]]
    ))
    add("")
    add(
        "De {:.0%} a {:.0%}, el dominio factible crece en {} configuraciones y "
        "el LCOE optimo {} en {:.4f} CNY/kWh -- coherente con que el paper "
        "(SS3.1) fija el limite inferior del electrolizador precisamente por "
        "esta restriccion. Ver `figuras/sensibilidad_agsr.png`.".format(
            agsr["value"].iloc[0], agsr["value"].iloc[-1], int(agsr_feasible_delta),
            "baja" if agsr_lcoe_delta < 0 else "sube", abs(agsr_lcoe_delta),
        )
    )
    add("")
    add("### Carga minima del electrolizador")
    add("")
    add(_markdown_table(
        min_load[["value", "feasible", "feasible_share", "best_lcoe_cny_per_kwh", "best_wind_mw", "best_electrolyzer_mw"]]
    ))
    add("")
    add(
        "De {:.0%} a {:.0%} (el paper usa {:.0%}), el dominio factible cambia "
        "en {} configuraciones y el LCOE optimo {} en {:.4f} CNY/kWh. Ver "
        "`figuras/sensibilidad_carga_minima.png`.".format(
            min_load["value"].iloc[0], min_load["value"].iloc[-1],
            config.electrolyzer.min_load_ratio, int(min_load_feasible_delta),
            "baja" if min_load_lcoe_delta < 0 else "sube", abs(min_load_lcoe_delta),
        )
    )
    add("")

    # -- 6. Como estan configurados los graficos -------------------------------
    add("## Como estan configurados los graficos")
    add("")
    add(
        "Paleta y `rcParams` compartidos en `src/h2_hres/analysis/style.py`, "
        "validados con el script de la skill `dataviz` (metodo OKLab/CVD de "
        "Arcuri) para las cuatro series apareciendo juntas a la vez (boxplot, "
        "dispersion) -- el contexto mas exigente. Solo los tres primeros "
        "colores del catalogo de referencia superan esa validacion en "
        "conjunto; `random` es la linea base, no un algoritmo competidor, asi "
        "que se codifica con gris neutro y linea discontinua en vez de un "
        "cuarto matiz categorico."
    )
    add("")
    add("| Figura | Datos | Que muestra | Regenerar |")
    add("|---|---|---|---|")
    add(
        "| `convergencia_por_algoritmo.png` | `datos/history.csv` agrupado "
        "por algoritmo x iteracion | mediana del mejor score y banda "
        "intercuartil (25-75%) entre semillas | `h2hres compare` |"
    )
    add(
        "| `distribucion_scores.png` | `datos/runs.csv` | boxplot del score "
        "final por algoritmo, una caja por algoritmo | `h2hres compare` |"
    )
    add(
        "| `calidad_vs_tiempo.png` | `datos/runs.csv` | dispersion "
        "tiempo-de-corrida vs. score final, un punto por corrida | "
        "`h2hres compare` |"
    )
    add(
        "| `sensibilidad_agsr.png` | `tablas/sensibilidad_agsr.csv` | tres "
        "paneles de un eje cada uno (costo, capacidades, factibilidad) vs. el "
        "limite de AGSR barrido | `h2hres sensitivity` |"
    )
    add(
        "| `sensibilidad_carga_minima.png` | `tablas/sensibilidad_carga_minima.csv` "
        "| idem, vs. la carga minima del electrolizador | `h2hres sensitivity` |"
    )
    add("")
    add(
        "Ningun grafico usa un eje Y doble: donde hay mas de una magnitud "
        "(capacidades y factibilidad en la sensibilidad) se resuelve en "
        "paneles separados, cada uno con un solo eje."
    )
    add("")

    # -- 7. Que NO se hizo y por que --------------------------------------------
    add("## Que NO se hizo y por que")
    add("")
    add(
        "- **Multiobjetivo (NSGA-II / MOPSO)**: el paper lo sugiere en SS3.3, "
        "pero exige frente de Pareto, metricas de hipervolumen y una interfaz "
        "distinta de `Optimizer`. Queda como una fase propia."
    )
    add(
        "- **NPV, IRR, ROI, payback**: exigen precio del H2, *feed-in tariff* "
        "y prioridad de despacho, que el paper no publica."
    )
    add(
        "- **Capacidad total variable** (SS3.3, punto 2) y **perfil de carga "
        "de H2** (SS3.3, punto 3): fuera de alcance de esta fase."
    )
    add(
        "- **Duracion de bateria como eje de sensibilidad explicito**: queda "
        "como variable de decision dentro de la optimizacion (ver el reparto "
        "de costos en la seccion de supuestos), no como un tercer barrido "
        "determinista."
    )
    add("")

    # -- 8. Supuestos declarados ------------------------------------------------
    add("## Supuestos declarados")
    add("")
    add(
        "- **Costo de bateria por potencia y energia**: el paper solo cotiza "
        "la bateria por kW (2549/500/10 CNY/kW capex/reemplazo/O&M) porque sus "
        "tres casos publicados son todos de 1 h, donde potencia y energia son "
        "numericamente iguales. Para que la duracion de bateria tenga sentido "
        "economico como variable de decision, este escenario reparte esos "
        "costos 30% potencia / 70% energia -- a 1 h la suma da exactamente los "
        "valores del paper (NPC-neutro, verificado en "
        "`tests/test_paper_validation.py`), y a mas horas la bateria cuesta "
        "mas. Es un supuesto explicito, no un dato del paper."
    )
    add(
        "- **`wind.wind_speed_source = measured_50m`**: la Tabla 3 del paper "
        "declara buje a 105 m, pero extrapolar a esa altura (via el parametro "
        "`WSC` de NASA POWER) da un CF eolico de ~56% contra el 40% publicado, "
        "mientras que la serie de 50 m sin extrapolar lo reproduce al 1%. Ver "
        "CHANGELOG.md, correccion 1."
    )
    add(
        "- **`converter.plant_load_ratio = 0.0`**: el paper no publica el "
        "consumo parasito de la planta."
    )
    add(
        "- **Hiperparametros de PSO/GA sin ajustar**: valores canonicos de la "
        "literatura, no afinados a este problema (seccion 3)."
    )
    add("")

    # -- 9. Cuestiones abiertas ---------------------------------------------
    add("## Cuestiones abiertas")
    add("")
    add(
        "Documentadas en detalle en `CHANGELOG.md`: el reparto "
        "positivo/negativo de la complementariedad viento-solar sale espejado "
        "respecto del paper aun con hora local corregida; el NPC de "
        "W60-P140-E85-B27.5 es inconsistente con la propia Tabla 4 del paper "
        "(unico objetivo fuera de tolerancia en la validacion); el viento "
        "medio replicado (7.00 m/s) difiere del publicado (7.56 m/s), "
        "compatible con revisiones de NASA POWER posteriores a 2023; y el "
        "LCOH del caso optimo tiene dos valores distintos dentro del propio "
        "paper (14.1574 vs. 10.6248 CNY/kg)."
    )
    add("")

    # -- 10. Reproducir -------------------------------------------------------
    add("## Reproducir")
    add("")
    add("```bash")
    add("pip install -e \".[dev]\"")
    add("h2hres download --config configs/metaheuristicas.yaml   # ~1 min, una vez")
    add("h2hres report   --config configs/metaheuristicas.yaml --out entrega")
    add("```")
    add("")
    add(
        "`report` encadena validacion, comparativa ({} algoritmos x {} "
        "semillas, {} evaluaciones cada una) y los dos barridos de "
        "sensibilidad. En esta maquina toma aproximadamente 4-5 minutos. Cada "
        "corrida individual tambien queda en `results/<timestamp>_*/` via "
        "`h2hres compare` y `h2hres sensitivity` por separado, si hace falta "
        "aislar una sin regenerar todo.".format(len(algorithms), runs, budget)
    )
    add("")

    return "\n".join(lines) + "\n"
