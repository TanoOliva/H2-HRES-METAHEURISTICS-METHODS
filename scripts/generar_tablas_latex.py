"""Genera tablas y macros LaTeX directamente desde los CSV del notebook.

Los resultados tienen una columna ``instance`` (I1..I8). Como los nombres de macro
LaTeX no admiten digitos, cada instancia recibe un sufijo de letra en el orden del
archivo ``instances.csv``: I1 -> A, I2 -> B, ..., I8 -> H. Asi ``\\BFALCOE`` es el
optimo exacto de I1 y ``\\TablaRankingAutoC`` la tabla de ranking de I3.

La inferencia se lee de las tablas ``stat_*.csv`` que produce
``scripts/analisis_estadistico.py``. Cada par de algoritmos recibe un prefijo de macro:
``\\CtrlPso...`` es el hibrido (control) frente a PSO y ``\\BaseGwo...`` es GWO frente a
la linea base aleatoria.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import pandas as pd
from scipy.stats import binomtest


ROOT =Path(__file__).resolve().parents[1]
RESULTS = ROOT / "notebooks" / "results"
OUTPUT = ROOT / "latex" / "generated" / "resultados_auto.tex"

LABELS = {"pso_ga": "PSO+GA"}
SUFFIXES = "ABCDEFGH"
# Nombre de cada algoritmo dentro de un nombre de macro (sin digitos ni signos).
MACRO_NAMES = {"gwo": "Gwo", "pso": "Pso", "ga": "Ga", "sho": "Sho", "woa": "Woa",
               "pso_ga": "PsoGa", "random": "Random"}
SYMBOLS = {"+": r"$+$", "=": r"$\approx$", "-": r"$-$"}
# Palabras que los CSV escriben sin tilde; se reemplazan sólo como palabras completas
# para no alterar derivados (``linea`` no debe tocar ``lineal``).
ACCENTED_WORDS = {
    "jerarquico": "jerárquico", "lideres": "líderes", "mutacion": "mutación",
    "heterogeneo": "heterogéneo", "identico": "idéntico", "iteracion": "iteración",
    "linea": "línea", "estandar": "estándar", "catalogo": "catálogo",
    "reconstruccion": "reconstrucción", "eolica": "eólica", "elite": "élite",
}
NUMBERS_ES = {1: "una", 2: "dos", 3: "tres", 4: "cuatro", 5: "cinco", 6: "seis", 7: "siete",
              8: "ocho"}
ORDINALS_EN = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth",
               6: "sixth", 7: "seventh"}


def read(name: str) -> pd.DataFrame:
    path = RESULTS / name
    if not path.exists():
        raise FileNotFoundError(f"Falta {path}; ejecute primero el notebook completo")
    return pd.read_csv(path)


def label(algorithm: object) -> str:
    name = str(algorithm)
    return LABELS.get(name, name.upper())


def tex(value: object) -> str:
    text = str(value)
    for source, target in {
        "real-coded GA estandar": "GA de codificación real estándar",
        "reproduccion": "reproducción",
        "Reproduccion": "Reproducción",
        "eolico": "eólico",
        "Eolico": "Eólico",
        "fraccion": "fracción",
        "Fraccion": "Fracción",
        "disenos": "diseños",
        "Disenos": "Diseños",
        "busqueda": "búsqueda",
        "genetico": "genético",
        "hibrido": "híbrido",
    }.items():
        text = text.replace(source, target)
    for source, target in ACCENTED_WORDS.items():
        text = re.sub(rf"\b{source}\b", target, text)
    return (text.replace("&", r"\&").replace("%", r"\%")
            .replace("_", r"\_").replace("#", r"\#"))


def config_tex(value: object) -> str:
    """Configuración de un algoritmo con notación española y símbolos matemáticos.

    El CSV la escribe en texto plano (``chi=0.729; a decae 2 -> 0``); aquí se pasa a coma
    decimal, flechas, desigualdades y letras griegas, sin tocar los valores.
    """
    text = tex(value)
    text = re.sub(r"(\d)\.(\d)", r"\1,\2", text)
    text = text.replace("->", r"$\rightarrow$").replace("<=", r"$\leq$").replace("|v|", r"$|v|$")
    for source, target in {"chi": r"$\chi$", "sigma": r"$\sigma$", "c1": r"$c_1$", "c2": r"$c_2$"}.items():
        text = re.sub(rf"\b{source}\b", lambda _m, t=target: t, text)
    return re.sub(r"\b([ah]) decae\b", r"$\1$ decae", text)


def thousands_es(text: str) -> str:
    """Separador de miles en los horizontes horarios que los CSV escriben sin él."""
    return re.sub(r"\b(8)(7[68]\d)\b", r"\1.\2", text)


def integer_en(value: float) -> str:
    return f"{int(round(float(value))):,}"


def pvalue_en(value: float) -> str:
    return pvalue(value).replace(",", ".")


def num(value: float, digits: int = 4) -> str:
    return f"{float(value):.{digits}f}".replace(".", ",")


def sci(value: float, digits: int = 1) -> str:
    """Notacion cientifica con coma decimal: ``$1{,}5\\times10^{-14}$``; el cero se escribe 0."""
    value = float(value)
    if value == 0.0:
        return "0"
    mantissa, exponent = f"{value:.{digits}e}".split("e")
    return rf"${mantissa.replace('.', '{,}')}\times10^{{{int(exponent)}}}$"


def integer(value: float) -> str:
    return f"{int(round(float(value))):,}".replace(",", ".")


def pvalue(value: float) -> str:
    value = float(value)
    if pd.isna(value):
        return "--"
    if value < 0.001:
        return "<0,001"
    return f"{value:.3f}".replace(".", ",")


def pexpr(symbol: str, value: float) -> str:
    """Expresion en modo matematico: ``p = 0,125`` o ``p < 0,001``."""
    text = pvalue(value)
    if text.startswith("<"):
        return f"${symbol} < {text[1:].replace(',', '{,}')}$"
    return f"${symbol} = {text.replace(',', '{,}')}$"


def truthy(value: object) -> bool:
    return str(value).strip().lower() in ("true", "1", "1.0")


def macro(lines: list[str], name: str, value: object) -> None:
    lines.append(rf"\newcommand{{\{name}}}{{{value}}}")


def spanish_list(values: list[str], empty: str = "ninguno") -> str:
    if not values:
        return empty
    if len(values) == 1:
        return values[0]
    conjunction = " e " if values[-1].lower().startswith(("i", "hi")) else " y "
    return ", ".join(values[:-1]) + conjunction + values[-1]


def table_begin(lines: list[str], command: str, caption: str, label_: str,
                columns: str, size: str = r"\scriptsize", colsep: str | None = None) -> None:
    lines.extend([
        rf"\newcommand{{\{command}}}{{%",
        r"\begin{table}[H]", r"\centering", size,
        *([rf"\setlength{{\tabcolsep}}{{{colsep}}}"] if colsep else []),
        rf"\caption{{{caption}}}", rf"\label{{{label_}}}",
        r"\renewcommand{\arraystretch}{1.15}", rf"\begin{{tabular}}{{{columns}}}",
        r"\hline",
    ])


def table_end(lines: list[str]) -> None:
    lines.extend([r"\hline", r"\end{tabular}", r"\end{table}", "}", ""])


def main() -> None:
    validation = read("validation_metrics_8760.csv")
    cases = read("validation_cases_8760.csv")
    horizons = read("validation_horizon_sensitivity.csv")
    wind_height = read("wind_height_sensitivity.csv")
    evolution = read("validation_evolution.csv")
    base = read("base_grid.csv")
    instances = read("instances.csv")
    brute = read("brute_force_summary.csv").set_index("instance")
    comparison = read("brute_force_comparison.csv")
    runs = read("algorithm_runs.csv")
    ranking = read("algorithm_summary.csv")
    cross = read("cross_instance_ranking.csv")
    design = read("stat_design.csv").iloc[0]
    normality = read("stat_normality.csv")
    per_instance = read("stat_per_instance.csv")
    global_tests = read("stat_global.csv")
    friedman = read("stat_friedman.csv").iloc[0]
    ranks = read("stat_ranks.csv")
    power = read("stat_power.csv").set_index("unidad")
    hyper = read("algorithm_hyperparameters.csv")
    sens_agsr = read("sensitivity_agsr.csv")
    sens_load = read("sensitivity_min_load.csv")
    best_horizon = read("best_design_horizon_sensitivity.csv").iloc[0]
    metadata = read("experiment_metadata.csv").iloc[0]
    # Sensibilidad a la contabilidad del presupuesto (scripts/analisis_estadistico.py).
    unique_cut = read("stat_unicos_corte.csv")
    unique_per_instance = read("stat_unicos_per_instance.csv")
    unique_global = read("stat_unicos_global.csv")
    unique_friedman = read("stat_unicos_friedman.csv").iloc[0]
    unique_ranks = read("stat_unicos_ranks.csv")
    # Perfil de convergencia (scripts/analisis_estadistico.py).
    convergence = read("stat_convergencia.csv")

    codes =[str(c) for c in instances["instance"]]
    suffix = {code: SUFFIXES[k] for k, code in enumerate(codes)}
    replicates = int(metadata["replicates_per_algorithm"])

    base_feasible = base[base["feasible"].astype(str).str.lower().isin(("true", "1"))]
    base_best = base_feasible.sort_values("lcoe_cny_per_kwh").iloc[0]

    lines = ["% Archivo generado por scripts/generar_tablas_latex.py. No editar manualmente."]
    # ------------------------------------------------------------------ globales
    macro(lines, "HoursMain", integer(metadata["hours_main"]))
    macro(lines, "HoursSensitivity", integer(metadata["hours_sensitivity"]))
    macro(lines, "NInstances", integer(metadata["instances"]))
    macro(lines, "NAlgorithms", integer(metadata["algorithms"]))
    macro(lines, "NClassic", integer(metadata["classic_algorithms"]))
    macro(lines, "NHybrid", integer(metadata["hybrid_algorithms"]))
    macro(lines, "Replicates", integer(replicates))
    macro(lines, "Population", integer(metadata["population"]))
    macro(lines, "Iterations", integer(metadata["iterations"]))
    macro(lines, "RequestsPerRun", integer(metadata["requests_per_run"]))
    macro(lines, "RequestsPerInstance", integer(metadata["requests_per_instance"]))
    macro(lines, "TotalRuns", integer(len(runs)))
    macro(lines, "TotalDesignRequests", integer(metadata["total_requests"]))
    macro(lines, "RequestedHourlySteps", integer(metadata["main_hourly_steps_requested"]))
    macro(lines, "BruteForceDesignsTotal", integer(metadata["brute_force_designs_total"]))
    macro(lines, "BruteForceElapsedHours", num(brute["elapsed_s"].sum() / 3600.0, 1))
    # Costo de la enumeración frente al de una corrida: sostiene por qué la fuerza bruta
    # es el instrumento de medida y no una alternativa a las metaheurísticas.
    requests_per_run = float(metadata["requests_per_run"])
    brute_rate = brute["evaluated"] / brute["elapsed_s"]
    simulator_ms = float((1000.0 * runs["elapsed_s"] / runs["n_unique_evaluations"]).median())
    macro(lines, "BruteForceMinutesMin", integer(brute["elapsed_s"].min() / 60.0))
    macro(lines, "BruteForceMinutesMax", integer(brute["elapsed_s"].max() / 60.0))
    macro(lines, "BudgetShareMinPct", num(100.0 * requests_per_run / brute["evaluated"].max(), 4))
    macro(lines, "BudgetShareMaxPct", num(100.0 * requests_per_run / brute["evaluated"].min(), 3))
    macro(lines, "DesignsPerBudgetMin", integer(brute["evaluated"].min() / requests_per_run))
    macro(lines, "DesignsPerBudgetMax", integer(brute["evaluated"].max() / requests_per_run))
    macro(lines, "RunSecondsMedian", num(runs["elapsed_s"].median(), 1))
    macro(lines, "SimulatorCallMs", num(simulator_ms, 1))
    macro(lines, "VectorSpeedup", integer(float(brute_rate.median()) * simulator_ms / 1000.0))
    # Extrapolación: una segunda coordenada continua con la misma resolución que W
    # multiplica los diseños de la instancia de referencia por su número de valores.
    reference = brute.loc[codes[0]]
    macro(lines, "SecondCoordFactor", integer(reference["wind_values"]))
    macro(lines, "SecondCoordDays",
          integer(reference["elapsed_s"] * reference["wind_values"] / 86400.0))
    macro(lines, "BaseEvaluated", integer(len(base)))
    macro(lines, "BaseFeasible", integer(len(base_feasible)))
    macro(lines, "BaseFeasiblePct", num(100 * len(base_feasible) / len(base), 1))
    macro(lines, "BaseBestLCOE", num(base_best["lcoe_cny_per_kwh"], 6))
    macro(lines, "BaseBestWind", num(base_best["wind_mw"], 0))
    macro(lines, "BaseBestElectrolyzer", num(base_best["electrolyzer_mw"], 0))
    macro(lines, "BestHorizonDeltaPct", num(best_horizon["delta_LCOE_pct"], 3))
    macro(lines, "MaxBalanceResidual", sci(runs["max_balance_residual_mw"].max()))
    macro(lines, "MaxControlRelDiff", sci(brute["control_max_rel_diff_lcoe"].max()))
    macro(lines, "MinFeasibleRuns", integer(ranking["feasible_runs"].min()))

    # Vecinos en el orden por mediana de cada instancia cuya separación es menor que el
    # rango intercuartílico de ambos (exploración, Sección de resultados).
    neighbor_pairs = within_iqr = 0
    for _, block in ranking.groupby("instance"):
        block = block.sort_values("median").reset_index(drop=True)
        for k in range(len(block) - 1):
            a, b = block.iloc[k], block.iloc[k + 1]
            neighbor_pairs += 1
            within_iqr += bool(b["median"] - a["median"] < min(a["iqr"], b["iqr"]))
    macro(lines, "NeighborPairs", integer(neighbor_pairs))
    macro(lines, "NeighborPairsWithinIqr", integer(within_iqr))

    # Solicitudes repetidas por corrida: media sobre instancias de la media por instancia.
    duplicates = ranking.pivot(index="instance", columns="algorithm", values="mean_duplicates")
    for algorithm, values in duplicates.items():
        name = MACRO_NAMES[algorithm]
        macro(lines, f"Dup{name}Mean", integer(values.mean()))
        macro(lines, f"Dup{name}Pct", num(100.0 * values.mean() / requests_per_run, 1))
        macro(lines, f"Dup{name}Min", integer(values.min()))
        macro(lines, f"Dup{name}Max", integer(values.max()))
        macro(lines, f"Dup{name}MaxInstance", tex(values.idxmax()))

    # Óptimos exactos en la frontera del dominio (amenaza del recorte previo a decodificar).
    by_instance = instances.set_index("instance")
    units_at_max = [code for code in codes
                    if int(brute.loc[code, "optimum_n_units"]) == int(by_instance.loc[code, "max_units"])]
    shortest = [code for code in codes
                if float(brute.loc[code, "optimum_battery_duration_h"])
                == min(float(h) for h in str(by_instance.loc[code, "durations_h"]).split("/"))]
    # Fracción factible por nivel del límite de ventas a red y holgura del óptimo en C5.
    share = 100.0 * brute.loc[codes, "feasible_share"]
    agsr_level = by_instance.loc[codes, "agsr_max"].astype(float)
    for name, level in zip(("Tight", "Mid", "Loose"), sorted(agsr_level.unique())):
        group = share[agsr_level == level]
        macro(lines, f"FeasibleShare{name}Min", num(group.min(), 1))
        macro(lines, f"FeasibleShare{name}Max", num(group.max(), 1))
    slack = (agsr_level - brute.loc[codes, "optimum_agsr"].astype(float)).max()
    macro(lines, "OptimumAgsrSlackBound", num(math.ceil(slack * 1e5) / 1e5, 5))
    macro(lines, "BoundaryUnitsInstances", spanish_list(units_at_max))
    macro(lines, "BoundaryDurationInstances",
          "todas las instancias" if len(shortest) == len(codes) else spanish_list(shortest))

    # Solicitudes frente a simulaciones: una solicitud repetida dentro de una corrida se
    # responde desde la memoria de resultados de esa corrida, sin volver a simular.
    macro(lines, "SimulationsTotal", integer(runs["n_unique_evaluations"].sum()))
    macro(lines, "DuplicatesTotal", integer(runs["n_duplicates"].sum()))

    # Estructura del problema: catálogos cuyo mejor diseño factible queda sobre el borde de
    # C5 (holgura de AGSR menor que BORDER_SLACK). Se separan las instancias en que casi
    # todos los catálogos lo cumplen de las que no.
    border_slack = 1e-3
    per_catalog = read("brute_force_per_catalog.csv")
    per_catalog = per_catalog[per_catalog["has_feasible"].map(truthy)]
    catalog_limit = per_catalog["instance"].map(by_instance["agsr_max"].astype(float))
    on_border = (catalog_limit - per_catalog["agsr"].astype(float)) < border_slack
    border_pct = 100.0 * on_border.groupby(per_catalog["instance"]).mean()
    border_high = border_pct[border_pct >= 95.0]
    border_low = border_pct[border_pct < 95.0]
    # El texto dice «en siete de las ocho instancias ... en la restante»: exige una sola excepción.
    if len(border_low) != 1:
        raise ValueError("el texto supone exactamente una instancia con menos del 95 % de "
                         "catálogos sobre el borde de C5; revise la Sección 2.3.2")
    macro(lines, "BorderCatalogSlack", num(border_slack, 3))
    macro(lines, "BorderCatalogHighCountWord", NUMBERS_ES[len(border_high)])
    macro(lines, "BorderCatalogHighMin", num(border_high.min(), 0))
    macro(lines, "BorderCatalogHighMax", num(border_high.max(), 0))
    macro(lines, "BorderCatalogLowInstance", tex(border_low.index[0]))
    macro(lines, "BorderCatalogLowPct", num(border_low.iloc[0], 0))

    # Óptimo en la frontera del electrolizador: quién encabeza por mediana las instancias
    # en que el óptimo exacto usa un número interior de módulos. El texto afirma que son
    # las dos primeras del rango medio; si deja de ser cierto, el texto debe revisarse.
    interior_units = [code for code in codes if code not in units_at_max]
    interior_leaders: dict[str, list[str]] = {}
    for code in interior_units:
        leader = (ranking[ranking["instance"] == code]
                  .sort_values("ranking_descriptivo").iloc[0]["algorithm"])
        interior_leaders.setdefault(str(leader), []).append(code)
    top_two = set(read("stat_ranks.csv").sort_values("mean_rank")["algorithm"].head(2))
    if not set(interior_leaders) <= top_two:
        raise ValueError("las instancias con electrolizador interior ya no las encabezan "
                         "los dos primeros del rango medio; revise el texto de Limitaciones")
    macro(lines, "InteriorUnitsLeaders", tex(spanish_list(
        [f"{label(a)} en {spanish_list(items)}" for a, items in interior_leaders.items()])))

    # Tasa de éxito según el umbral: al 0,5 % (Tabla de rangos) y en el óptimo (g <= eps).
    eps_gap = float(design["eps_gap_pct"])
    optimum = brute["optimum_lcoe_cny_per_kwh"].astype(float)
    run_gap = 100.0 * (runs["lcoe_cny_per_kwh"] / runs["instance"].map(optimum) - 1.0)
    in_optimum = 100.0 * (run_gap <= eps_gap).groupby(runs["algorithm"]).mean()
    success_half = 100.0 * cross.set_index("algorithm")["mean_success_0.5pct"]
    for algorithm in in_optimum.index:
        name = MACRO_NAMES[algorithm]
        macro(lines, f"InOptPct{name}", num(in_optimum[algorithm], 1))
        macro(lines, f"SuccessHalfPct{name}", num(success_half[algorithm], 1))
    in_optimum_best = in_optimum.idxmax()
    macro(lines, "InOptBestAlgorithm", tex(label(in_optimum_best)))
    macro(lines, "InOptBestPct", num(in_optimum.max(), 1))
    macro(lines, "InOptRunsPerAlgorithm", integer(runs.groupby("algorithm").size().min()))
    ahead_at_half = success_half[success_half > success_half[in_optimum_best]].sort_values(ascending=False)
    macro(lines, "InOptBestBehindAtHalf", tex(spanish_list([label(a) for a in ahead_at_half.index])))

    # P2 frente a PSO: instancias en que las medianas difieren por menos que la tolerancia
    # (que sólo iguala corridas en el óptimo) y prueba de signos contándolas como empates.
    medians = ranking.pivot(index="instance", columns="algorithm", values="median")
    control_name = str(design["control"])
    pso_diff = 100.0 * (medians[control_name] - medians["pso"]) / optimum.loc[medians.index]
    below_tol = pso_diff[pso_diff.abs() < eps_gap]
    above_tol = pso_diff[pso_diff.abs() >= eps_gap]
    macro(lines, "CtrlPsoSubTolInstances", tex(spanish_list(list(below_tol.index), "ninguna")))
    macro(lines, "CtrlPsoSubTolDiff", num(below_tol.abs().max(), 4) if len(below_tol) else "--")
    macro(lines, "CtrlPsoSignTiesP",
          pvalue(binomtest(int((above_tol < 0).sum()), len(above_tol), 0.5).pvalue))
    # P2: la versión sobre LCOE mediano y la versión sobre brecha relativa dan el mismo p.
    macro(lines, "PTwoSamePCount", integer(sum(
        pvalue(row.p_value) == pvalue(row.p_value_relativa) for row in global_tests.itertuples())))

    # Reproducción: el diseño que Li et al. publican como óptimo (W190) bajo la reconstrucción.
    # La malla base usa el mismo límite de AGSR que la instancia de referencia.
    published_optimum = cases[cases["caso"] == "W190"].iloc[0]
    base_limit = float(by_instance.loc[codes[0], "agsr_max"])
    macro(lines, "ReproOptimumAGSR", num(published_optimum["AGSR"], 4))
    macro(lines, "ReproOptimumExcessPct", num(100.0 * (published_optimum["AGSR"] / base_limit - 1.0), 0))
    macro(lines, "ReproOptimumPublishedLCOE",
          num(validation.loc[validation["metrica"] == "LCOE W190", "publicado"].iloc[0], 4))
    pv_cf = validation[validation["metrica"] == "CF fotovoltaico"].iloc[0]
    macro(lines, "ReproCFPv", num(pv_cf["reconstruido"], 4))
    macro(lines, "ReproCFPvErr", "$" + num(pv_cf["error_rel_pct"], 2).replace(",", "{,}") + "$")

    # ------------------------------------------------------------------ transversal
    # Los rangos son los del contraste de Friedman (mediana de la brecha con tolerancia).
    ranks = ranks.sort_values("mean_rank").reset_index(drop=True)
    top = ranks.iloc[0]
    macro(lines, "BestMeanRankAlgorithm", tex(label(top["algorithm"])))
    macro(lines, "BestMeanRank", num(top["mean_rank"], 2))
    macro(lines, "SecondMeanRankAlgorithm", tex(label(ranks.iloc[1]["algorithm"])))
    macro(lines, "SecondMeanRank", num(ranks.iloc[1]["mean_rank"], 2))
    macro(lines, "WorstMeanRankAlgorithm", tex(label(ranks.iloc[-1]["algorithm"])))
    for _, row in ranks.iterrows():
        macro(lines, f"MeanRank{MACRO_NAMES[row['algorithm']]}", num(row["mean_rank"], 2))
    control = str(design["control"])
    baseline = str(design["baseline"])
    control_position = int(ranks.index[ranks["algorithm"] == control][0] + 1)
    macro(lines, "ControlRankPosition", integer(control_position))
    macro(lines, "ControlRankOrdinalEn", ORDINALS_EN[control_position])  # para el Abstract

    # ------------------------------------------------------------------ diseno del analisis
    macro(lines, "StatAlpha", num(design["alpha"], 2))
    macro(lines, "StatEpsGapPct", num(design["eps_gap_pct"], 2))
    macro(lines, "StatBootstrap", integer(design["n_boot"]))
    macro(lines, "StatTestsPerInstance", integer(design["tests_per_instance"]))
    macro(lines, "StatTestsGlobal", integer(design["tests_global"]))
    macro(lines, "StatTestsTotal", integer(design["tests_total"]))
    macro(lines, "ShapiroRejects", integer(normality["rechaza_normalidad"].map(truthy).sum()))
    macro(lines, "ShapiroTotal", integer(len(normality)))
    macro(lines, "FriedmanChi", num(friedman["friedman_chi2"], 2))
    macro(lines, "FriedmanP", pvalue(friedman["friedman_p"]))
    macro(lines, "ImanDavenportF", num(friedman["iman_davenport_f"], 2))
    macro(lines, "ImanDavenportDfA", integer(friedman["iman_davenport_df1"]))
    macro(lines, "ImanDavenportDfB", integer(friedman["iman_davenport_df2"]))
    macro(lines, "ImanDavenportP", pvalue(friedman["iman_davenport_p"]))
    global_rejects = float(friedman["iman_davenport_p"]) < float(design["alpha"])
    macro(lines, "FriedmanDecision", "rechaza" if global_rejects else "no rechaza")
    macro(lines, "NemenyiQ", num(friedman["q_alpha"], 3))
    macro(lines, "CriticalDifference", num(friedman["critical_difference"], 2))
    cd = float(friedman["critical_difference"])
    nemenyi = [(a["algorithm"], b["algorithm"])
               for i, a in ranks.iterrows() for j, b in ranks.iterrows()
               if i < j and b["mean_rank"] - a["mean_rank"] > cd]
    macro(lines, "NemenyiPairsCount", integer(len(nemenyi)))
    macro(lines, "NemenyiPairsTotal", integer(len(ranks) * (len(ranks) - 1) // 2))
    macro(lines, "NemenyiPairs", tex(spanish_list(
        [f"{label(a)} sobre {label(b)}" for a, b in nemenyi])))
    macro(lines, "NemenyiControlPairs", tex(spanish_list(
        [f"{label(a)} sobre {label(b)}" for a, b in nemenyi if control in (a, b)])))
    for unit, name in (("replicas por instancia", "Replicates"), ("instancias", "Instances")):
        row = power.loc[unit]
        macro(lines, f"Power{name}Medium", num(row["potencia_dz_0.5"], 2))
        macro(lines, f"Power{name}Large", num(row["potencia_dz_0.8"], 2))
        macro(lines, f"Power{name}Detectable", num(row["dz_detectable_potencia_0.8"], 2))
    macro(lines, "WilcoxonMinP", pvalue(power.loc["instancias", "p_minimo_wilcoxon_exacto"]))

    # ------------------------------------------------------------------ macros por par
    def pair_prefix(row) -> str:
        if row["family"] == "control":
            return "Ctrl" + MACRO_NAMES[row["algoritmo_b"]]
        return "Base" + MACRO_NAMES[row["algoritmo_a"]]

    for _, row in global_tests.iterrows():
        prefix = pair_prefix(row)
        sub = per_instance[(per_instance["family"] == row["family"])
                           & (per_instance["algoritmo_a"] == row["algoritmo_a"])
                           & (per_instance["algoritmo_b"] == row["algoritmo_b"])]
        macro(lines, f"{prefix}Plus", integer(row["mejor_significativo"]))
        macro(lines, f"{prefix}Equal", integer(row["sin_diferencia"]))
        macro(lines, f"{prefix}Minus", integer(row["peor_significativo"]))
        macro(lines, f"{prefix}PlusInstances",
              tex(spanish_list(list(sub.loc[sub["simbolo"] == "+", "instance"]), "ninguna")))
        macro(lines, f"{prefix}MinusInstances",
              tex(spanish_list(list(sub.loc[sub["simbolo"] == "-", "instance"]), "ninguna")))
        macro(lines, f"{prefix}MedianWins", integer(row["gana_mediana"]))
        macro(lines, f"{prefix}MedianTies", integer(row["empata_mediana"]))
        macro(lines, f"{prefix}MedianLosses", integer(row["pierde_mediana"]))
        macro(lines, f"{prefix}AMin", num(sub["a12"].min(), 2))
        macro(lines, f"{prefix}AMax", num(sub["a12"].max(), 2))
        macro(lines, f"{prefix}WilcoxonP", pvalue(row["p_value"]))
        macro(lines, f"{prefix}WilcoxonHolm", pvalue(row["p_value_holm"]))
        macro(lines, f"{prefix}WilcoxonHolmEn", pvalue_en(row["p_value_holm"]))  # para el Abstract
        macro(lines, f"{prefix}RelativeP", pvalue(row["p_value_relativa"]))
        macro(lines, f"{prefix}SignP", pvalue(row["p_value_signos"]))
        macro(lines, f"{prefix}Shift", num(row["hl_pareado_gap_pp"], 3))

    # ------------------------------------------------------------------ sensibilidad: igual numero de disenos unicos
    # El corte es la mediana de disenos unicos del GA en cada instancia; los demas
    # algoritmos quedan truncados en ese punto y el GA conserva sus solicitudes.
    cut_values = unique_cut.drop_duplicates("instance")["corte_unicos"]
    macro(lines, "UniqueCutMin", integer(cut_values.min()))
    macro(lines, "UniqueCutMax", integer(cut_values.max()))
    used = (unique_cut[unique_cut["algorithm"] != "ga"]
            .groupby("algorithm")["solicitudes_mediana"].median())
    macro(lines, "UniqueCutRequestsMin", integer(used.min()))
    macro(lines, "UniqueCutRequestsMax", integer(used.max()))
    unique_ranks = unique_ranks.sort_values("mean_rank").reset_index(drop=True)
    for _, row in unique_ranks.iterrows():
        macro(lines, f"UniqueMeanRank{MACRO_NAMES[row['algorithm']]}", num(row["mean_rank"], 2))
    macro(lines, "UniqueGaRankPosition",
          integer(unique_ranks.index[unique_ranks["algorithm"] == "ga"][0] + 1))
    macro(lines, "UniqueImanDavenportF", num(unique_friedman["iman_davenport_f"], 2))
    macro(lines, "UniqueImanDavenportP", pvalue(unique_friedman["iman_davenport_p"]))
    for _, row in unique_global.iterrows():
        prefix = "Unique" + pair_prefix(row)
        sub = unique_per_instance[(unique_per_instance["family"] == row["family"])
                                  & (unique_per_instance["algoritmo_a"] == row["algoritmo_a"])
                                  & (unique_per_instance["algoritmo_b"] == row["algoritmo_b"])]
        macro(lines, f"{prefix}Plus", integer(row["mejor_significativo"]))
        macro(lines, f"{prefix}Equal", integer(row["sin_diferencia"]))
        macro(lines, f"{prefix}Minus", integer(row["peor_significativo"]))
        macro(lines, f"{prefix}PlusInstances",
              tex(spanish_list(list(sub.loc[sub["simbolo"] == "+", "instance"]), "ninguna")))
        macro(lines, f"{prefix}MedianWins", integer(row["gana_mediana"]))
        macro(lines, f"{prefix}MedianLosses", integer(row["pierde_mediana"]))
        macro(lines, f"{prefix}WilcoxonP", pvalue(row["p_value"]))
        macro(lines, f"{prefix}WilcoxonHolm", pvalue(row["p_value_holm"]))
        macro(lines, f"{prefix}WilcoxonHolmEn", pvalue_en(row["p_value_holm"]))  # para el Abstract
        macro(lines, f"{prefix}RelativeP", pvalue(row["p_value_relativa"]))
        macro(lines, f"{prefix}SignP", pvalue(row["p_value_signos"]))

    # ------------------------------------------------------------------ convergencia (descriptiva)
    # Rango medio en cada punto de control; en el ultimo coincide con el de Friedman.
    rank_at = convergence.pivot(index="n_evaluations", columns="algorithm", values="mean_rank")
    position_at = convergence.pivot(index="n_evaluations", columns="algorithm", values="position")
    gap_at = convergence.pivot(index="n_evaluations", columns="algorithm", values="mean_median_gap_pct")
    checkpoints = list(rank_at.index)
    final_point = checkpoints[-1]
    half_point = max(k for k in checkpoints if k <= requests_per_run / 2)
    macro(lines, "ConvHalfRequests", integer(half_point))
    leaders = [a for a in rank_at.columns if position_at.loc[half_point, a] == 1]
    macro(lines, "ConvHalfLeader", tex(spanish_list([label(a) for a in leaders])))
    macro(lines, "ConvHalfLeaderFinalPosition", integer(position_at.loc[final_point, leaders[0]]))
    macro(lines, "ConvHalfControlPosition", integer(position_at.loc[half_point, control]))
    macro(lines, "ConvTauHalf", num(rank_at.loc[half_point].corr(rank_at.loc[final_point], method="kendall"), 2))
    # Tramo en que el hibrido tiene el menor rango medio; se exige que sea continuo.
    lead = [k for k in checkpoints if position_at.loc[k, control] == 1]
    if lead and lead != [k for k in checkpoints if lead[0] <= k <= lead[-1]]:
        raise ValueError("el tramo en que el hibrido encabeza el rango medio no es continuo")
    macro(lines, "ConvControlLeadFrom", integer(lead[0]) if lead else "--")
    macro(lines, "ConvControlLeadTo", integer(lead[-1]) if lead else "--")
    # Primer punto desde el cual ningun algoritmo se aparta mas de un lugar de su posicion final.
    displacement = (position_at - position_at.loc[final_point]).abs().max(axis=1)
    settled = [k for k in checkpoints if (displacement.loc[k:] <= 1).all()]
    macro(lines, "ConvSettleFrom", integer(settled[0]))
    macro(lines, "ConvTauSettle", num(rank_at.loc[settled[0]].corr(rank_at.loc[final_point], method="kendall"), 2))
    early_point = max(k for k in checkpoints if k <= requests_per_run / 6)
    macro(lines, "ConvEarlyRequests", integer(early_point))
    reduction = 100.0 * (gap_at.loc[half_point] - gap_at.loc[final_point]) / gap_at.loc[half_point]
    for algorithm in rank_at.columns:
        name = MACRO_NAMES[algorithm]
        macro(lines, f"ConvReduction{name}", num(reduction[algorithm], 0))
        macro(lines, f"ConvGapHalf{name}", num(gap_at.loc[half_point, algorithm], 2))
        macro(lines, f"ConvGapFinal{name}", num(gap_at.loc[final_point, algorithm], 2))
        macro(lines, f"ConvRankEarly{name}", num(rank_at.loc[early_point, algorithm], 2))

    # ------------------------------------------------------------------ por instancia
    for code in codes:
        s = suffix[code]
        inst = instances.set_index("instance").loc[code]
        bf = brute.loc[code]
        rk = ranking[ranking["instance"] == code].sort_values("ranking_descriptivo")
        best_run = comparison[(comparison["instance"] == code)
                              & (comparison["algorithm"] != "fuerza_bruta")].iloc[0]
        macro(lines, f"InstLabel{s}", tex(inst["label"]))
        macro(lines, f"InstCapacity{s}", num(inst["total_capacity_mw"], 0))
        macro(lines, f"InstAGSR{s}", num(inst["agsr_max"], 2))
        macro(lines, f"InstCatalogs{s}", integer(inst["n_catalogs"]))
        macro(lines, f"BF{s}Designs", integer(bf["evaluated"]))
        macro(lines, f"BF{s}DesignsEn", integer_en(bf["evaluated"]))  # para el Abstract
        macro(lines, f"BF{s}Feasible", integer(bf["feasible"]))
        macro(lines, f"BF{s}FeasiblePct", num(100 * bf["feasible_share"], 1))
        macro(lines, f"BF{s}Catalogs", integer(bf["catalogs"]))
        macro(lines, f"BF{s}Step", num(bf["wind_step_mw"], 2))
        macro(lines, f"BF{s}ElapsedMin", num(bf["elapsed_s"] / 60.0, 0))
        macro(lines, f"BF{s}LCOE", num(bf["optimum_lcoe_cny_per_kwh"], 6))
        macro(lines, f"BF{s}Wind", num(bf["optimum_wind_mw"], 2))
        macro(lines, f"BF{s}PV", num(bf["optimum_pv_mw"], 2))
        macro(lines, f"BF{s}Electrolyzer", num(bf["optimum_electrolyzer_mw"], 1))
        macro(lines, f"BF{s}Units", integer(bf["optimum_n_units"]))
        macro(lines, f"BF{s}Battery", num(bf["optimum_battery_mw"], 1))
        macro(lines, f"BF{s}Duration", num(bf["optimum_battery_duration_h"], 0))
        macro(lines, f"BF{s}AGSR", num(bf["optimum_agsr"], 4))
        macro(lines, f"BF{s}LCOH", num(bf["optimum_lcoh_cny_per_kg"], 2))
        macro(lines, f"BF{s}ControlLCOE", sci(bf["control_max_rel_diff_lcoe"]))
        macro(lines, f"TopMedian{s}", tex(label(rk.iloc[0]["algorithm"])))
        macro(lines, f"TopMedianLCOE{s}", num(rk.iloc[0]["median"], 6))
        macro(lines, f"TopMedianGap{s}", num(rk.iloc[0]["median_gap_pct"], 3))
        macro(lines, f"SecondMedian{s}", tex(label(rk.iloc[1]["algorithm"])))
        macro(lines, f"BottomMedian{s}", tex(label(rk.iloc[-1]["algorithm"])))
        rank_random = rk.index[rk["algorithm"] == "random"]
        macro(lines, f"RandomRank{s}",
              integer(rk.loc[rank_random[0], "ranking_descriptivo"]) if len(rank_random) else "--")
        macro(lines, f"RandomMedianGap{s}",
              num(rk.loc[rank_random[0], "median_gap_pct"], 3) if len(rank_random) else "--")
        macro(lines, f"FeasibleRunsMin{s}", integer(rk["feasible_runs"].min()))
        macro(lines, f"BestRun{s}Algorithm", tex(label(best_run["algorithm"])))
        macro(lines, f"BestRun{s}LCOE", num(best_run["lcoe_cny_per_kwh"], 6))
        macro(lines, f"BestRun{s}GapPct", num(best_run["brecha_pct"], 4))
    lines.append("")

    # ------------------------------------------------------------------ validacion
    table_begin(lines, "TablaValidacionAuto", "Reproducción cuantitativa frente a Li et al. con 8.760 horas",
                "tab:validacion_auto", "p{3.2cm} p{1.4cm} r r r r p{2.5cm}")
    lines.append(r"\textbf{Indicador} & \textbf{Unidad} & \textbf{Publ.} & \textbf{Reprod.} & \textbf{$\Delta$ abs.} & \textbf{Error [\%]} & \textbf{Lectura} \\")
    lines.append(r"\hline")
    for row in validation.itertuples(index=False):
        lines.append(f"{tex(row.metrica)} & {tex(row.unidad)} & {num(row.publicado, 4)} & "
                     f"{num(row.reconstruido, 4)} & {num(row.diferencia_abs, 4)} & "
                     f"{num(row.error_rel_pct, 2)} & {tex(row.clasificacion_descriptiva)} " + r"\\")
    table_end(lines)

    table_begin(lines, "TablaCasosAuto", "Resultados reconstruidos de los tres casos con el horizonte principal",
                "tab:casos_auto", "l r r r r r r")
    lines.append(r"\textbf{Caso} & \textbf{Eólica} & \textbf{FV} & \textbf{H$_2$} & \textbf{NPC} & \textbf{LCOE} & \textbf{AGSR} \\")
    lines.append(r" & \textbf{[GWh]} & \textbf{[GWh]} & \textbf{[t/año]} & \textbf{[M CNY]} & \textbf{[CNY/kWh]} & \\")
    lines.append(r"\hline")
    for row in cases.itertuples(index=False):
        lines.append(f"{tex(row.caso)} & {num(row.wind_mwh / 1000, 1)} & {num(row.pv_mwh / 1000, 1)} & "
                     f"{num(row.h2_t, 1)} & {num(row.NPC_M_CNY, 1)} & {num(row.LCOE_CNY_kWh, 6)} & {num(row.AGSR, 4)} " + r"\\")
    table_end(lines)

    table_begin(lines, "TablaHorizonteAuto", "Sensibilidad al tratamiento del 29 de febrero de 2008",
                "tab:horizonte_auto", "l r r r r r")
    lines.append(r"\textbf{Caso} & \textbf{LCOE 8.760} & \textbf{LCOE 8.784} & \textbf{$\Delta$ [\%]} & \textbf{AGSR 8.760} & \textbf{AGSR 8.784} \\")
    lines.append(r"\hline")
    for row in horizons.itertuples(index=False):
        lines.append(f"{tex(row.caso)} & {num(row.LCOE_8760, 6)} & {num(row.LCOE_8784, 6)} & "
                     f"{num(row.delta_LCOE_pct, 3)} & {num(row.AGSR_8760, 4)} & {num(row.AGSR_8784, 4)} " + r"\\")
    table_end(lines)

    table_begin(lines, "TablaAlturaVientoAuto", "Sensibilidad de W190 a la altura de la serie eólica",
                "tab:altura_viento_auto", "p{4cm} r r r r")
    lines.append(r"\textbf{Serie} & \textbf{Viento [m/s]} & \textbf{CF eólico} & \textbf{LCOE} & \textbf{AGSR} \\")
    lines.append(r"\hline")
    for row in wind_height.itertuples(index=False):
        lines.append(f"{tex(row.serie)} & {num(row.mean_wind_ms, 3)} & {num(row.wind_cf, 4)} & "
                     f"{num(row.LCOE_W190, 6)} & {num(row.AGSR_W190, 4)} " + r"\\")
    table_end(lines)

    table_begin(lines, "TablaEvolucionAuto", "Evolución documentada del error relativo de LCOE",
                "tab:evolucion_auto", "p{3cm} l r p{7.2cm}")
    lines.append(r"\textbf{Etapa} & \textbf{Caso} & \textbf{Error [\%]} & \textbf{Cambio documentado} \\")
    lines.append(r"\hline")
    for row in evolution.itertuples(index=False):
        lines.append(f"{thousands_es(tex(row.etapa))} & {tex(row.caso)} & {num(row.error_LCOE_pct, 2)} & "
                     f"{thousands_es(tex(row.cambio_documentado))} " + r"\\")
    table_end(lines)

    # ------------------------------------------------------------------ instancias y fuerza bruta
    table_begin(lines, "TablaInstanciasAuto", "Las instancias del problema de dimensionamiento",
                "tab:instancias_auto", "l l r r r r r r l r r", colsep="5pt")  # 11 columnas
    lines.append(r"\textbf{Inst.} & \textbf{Etiqueta} & \textbf{$C_{tot}$} & \textbf{AGSR$_{max}$} & \textbf{$u$} & \textbf{$n_E$} & \textbf{$\Delta_B$} & \textbf{$B_{max}$} & \textbf{$\{h_k\}$ [h]} & \textbf{Catálogos} & \textbf{Diseños} \\")
    lines.append(r" & & \textbf{[MW]} & & \textbf{[MW]} & & \textbf{[MW]} & \textbf{[MW]} & & & \textbf{(paso $W$)} \\")
    lines.append(r"\hline")
    for row in instances.itertuples(index=False):
        lines.append(f"{tex(row.instance)} & {tex(row.label)} & {num(row.total_capacity_mw, 0)} & "
                     f"{num(row.agsr_max, 2)} & {num(row.electrolyzer_unit_mw, 1)} & "
                     f"{integer(row.min_units)}--{integer(row.max_units)} & {num(row.battery_step_mw, 1)} & "
                     f"{num(row.battery_max_mw, 0)} & {tex(row.durations_h)} & {integer(row.n_catalogs)} & "
                     f"{integer(row.n_designs)} ({num(row.brute_force_wind_step_mw, 2)}) " + r"\\")
    table_end(lines)

    table_begin(lines, "TablaFuerzaBrutaAuto", "Óptimo exacto de cada instancia por fuerza bruta sobre el dominio discretizado",
                "tab:fuerza_bruta_auto", "l r r r r r r r r r")
    lines.append(r"\textbf{Inst.} & \textbf{Diseños} & \textbf{Fact. [\%]} & \textbf{$W^*$} & \textbf{$E^*$} & \textbf{$B^{P*}$} & \textbf{$h^*$} & \textbf{AGSR$^*$} & \textbf{LCOE$^*$} & \textbf{Tiempo} \\")
    lines.append(r" & & & \textbf{[MW]} & \textbf{[MW]} & \textbf{[MW]} & \textbf{[h]} & & \textbf{[CNY/kWh]} & \textbf{[min]} \\")
    lines.append(r"\hline")
    for code in codes:
        bf = brute.loc[code]
        lines.append(f"{tex(code)} & {integer(bf['evaluated'])} & {num(100 * bf['feasible_share'], 1)} & "
                     f"{num(bf['optimum_wind_mw'], 2)} & {num(bf['optimum_electrolyzer_mw'], 1)} & "
                     f"{num(bf['optimum_battery_mw'], 1)} & {num(bf['optimum_battery_duration_h'], 0)} & "
                     f"{num(bf['optimum_agsr'], 4)} & {num(bf['optimum_lcoe_cny_per_kwh'], 6)} & "
                     f"{num(bf['elapsed_s'] / 60.0, 0)} " + r"\\")
    table_end(lines)

    table_begin(lines, "TablaComparacionOptimoAuto", "Óptimo exacto frente a la mejor corrida metaheurística de cada instancia",
                "tab:comparacion_optimo_auto", "l l r r r r r r")
    lines.append(r"\textbf{Inst.} & \textbf{Fuente} & \textbf{$W$} & \textbf{$E$} & \textbf{$B^P$} & \textbf{$h_B$} & \textbf{LCOE} & \textbf{Brecha [\%]} \\")
    lines.append(r"\hline")
    for row in comparison.itertuples(index=False):
        fuente = "óptimo exacto" if row.algorithm == "fuerza_bruta" else f"mejor corrida ({label(row.algorithm)})"
        lines.append(f"{tex(row.instance)} & {tex(fuente)} & {num(row.wind_mw, 2)} & {num(row.electrolyzer_mw, 1)} & "
                     f"{num(row.battery_mw, 1)} & {num(row.battery_duration_h, 0)} & "
                     f"{num(row.lcoe_cny_per_kwh, 6)} & {num(row.brecha_pct, 4)} " + r"\\")
    table_end(lines)

    # ------------------------------------------------------------------ hiperparametros
    table_begin(lines, "TablaHiperparametrosAuto", "Algoritmos comparados y configuración efectivamente ejecutada",
                "tab:hiperparametros_auto", r"p{1.2cm} p{2.8cm} p{2.2cm} p{5.6cm} p{2.3cm}", r"\scriptsize")
    lines.append(r"\textbf{Código} & \textbf{Nombre} & \textbf{Familia} & \textbf{Configuración} & \textbf{Fuente} \\")
    lines.append(r"\hline")
    for row in hyper.itertuples(index=False):
        lines.append(f"\\texttt{{{tex(row.codigo)}}} & {tex(row.nombre)} & {tex(row.familia)} & "
                     f"{config_tex(row.hiperparametros)} & {tex(row.fuente)} " + r"\\")
    table_end(lines)

    # ------------------------------------------------------------------ tablas por instancia
    for code in codes:
        s = suffix[code]
        inst_label = instances.set_index("instance").loc[code, "label"]
        rk = ranking[ranking["instance"] == code].sort_values("ranking_descriptivo")
        table_begin(lines, f"TablaRankingAuto{s}",
                    f"Calidad final por algoritmo en {code} ({tex(inst_label)}), {replicates} ejecuciones; brecha respecto del óptimo exacto",
                    f"tab:ranking_auto_{code.lower()}", "l l r r r r r")
        lines.append(r"\textbf{\#} & \textbf{Alg.} & \textbf{Mediana} & \textbf{IQR} & \textbf{Mejor} & \textbf{Peor} & \textbf{Brecha med. [\%]} \\")
        lines.append(r"\hline")
        for _, row in rk.iterrows():
            lines.append(f"{integer(row['ranking_descriptivo'])} & {tex(label(row['algorithm']))} & {num(row['median'], 6)} & {num(row['iqr'], 6)} & "
                         f"{num(row['best'], 6)} & {num(row['worst'], 6)} & {num(row['median_gap_pct'], 3)} " + r"\\")
        table_end(lines)

        table_begin(lines, f"TablaExitoAuto{s}",
                    f"Probabilidad empírica de proximidad al óptimo exacto en {code} ({tex(inst_label)})",
                    f"tab:exito_auto_{code.lower()}", "l r r r r")
        lines.append(r"\textbf{Alg.} & \textbf{Factibles} & \textbf{Brecha $\leq$0,1\%} & \textbf{Brecha $\leq$0,5\%} & \textbf{Brecha $\leq$1\%} \\")
        lines.append(r"\hline")
        for _, row in rk.iterrows():
            lines.append(f"{tex(label(row['algorithm']))} & {integer(row['feasible_runs'])}/{replicates} & "
                         f"{num(100 * row['success_0.1pct'], 1)}\\% & "
                         f"{num(100 * row['success_0.5pct'], 1)}\\% & {num(100 * row['success_1.0pct'], 1)}\\% " + r"\\")
        table_end(lines)


    # ------------------------------------------------------------------ exploracion: brechas y duplicados
    order = [a for a in ranks["algorithm"]]
    inst_columns = "l " + "r " * len(codes) + "r"
    for command, caption, label_, column, digits, mean_title in (
        ("TablaBrechaMedianaAuto",
         f"Brecha mediana respecto del óptimo exacto [\\%] por algoritmo e instancia, {replicates} ejecuciones; algoritmos ordenados por rango medio",
         "tab:brecha_mediana_auto", "median_gap_pct", 3, "Media"),
        ("TablaExitoMedioAuto",
         "Porcentaje de ejecuciones que terminan a 0,5\\,\\% o menos del óptimo exacto, por algoritmo e instancia",
         "tab:exito_medio_auto", "success_0.5pct", 0, "Media"),
        ("TablaDuplicadosAuto",
         f"Solicitudes repetidas por ejecución (media sobre {replicates} ejecuciones de {integer(metadata['requests_per_run'])} solicitudes), por algoritmo e instancia",
         "tab:duplicados_auto", "mean_duplicates", 1, "Media"),
    ):
        pivot = ranking.pivot(index="algorithm", columns="instance", values=column).reindex(index=order, columns=codes)
        scale = 100.0 if column.startswith("success") else 1.0
        table_begin(lines, command, caption, label_, inst_columns)
        lines.append(r"\textbf{Alg.} & " + " & ".join(rf"\textbf{{{c}}}" for c in codes)
                     + rf" & \textbf{{{mean_title}}} \\")
        lines.append(r"\hline")
        for algorithm in order:
            values = pivot.loc[algorithm] * scale
            lines.append(f"{tex(label(algorithm))} & " + " & ".join(num(v, digits) for v in values)
                         + f" & {num(values.mean(), digits)} " + r"\\")
        table_end(lines)

    # ------------------------------------------------------------------ P1: tabla tipica por par
    def typical_table(command: str, row_global, caption: str, label_: str) -> None:
        algo_a, algo_b = row_global["algoritmo_a"], row_global["algoritmo_b"]
        sub = per_instance[(per_instance["family"] == row_global["family"])
                           & (per_instance["algoritmo_a"] == algo_a)
                           & (per_instance["algoritmo_b"] == algo_b)].set_index("instance").reindex(codes)
        table_begin(lines, command, caption, label_, "l r r r l r c")
        lines.append(rf"\textbf{{Inst.}} & \textbf{{{tex(label(algo_a))}}} & \textbf{{{tex(label(algo_b))}}} & "
                     r"\textbf{$\hat{A}_{12}$} & \textbf{IC 95\,\%} & \textbf{$p_{Holm}$} & \textbf{Sig.} \\")
        lines.append(r" & \textbf{mediana (IQR)} & \textbf{mediana (IQR)} & & & & \\")
        lines.append(r"\hline")
        for code, row in sub.iterrows():
            cell_a = f"{num(row['median_a'], 5)} ({num(row['iqr_a'], 5)})"
            cell_b = f"{num(row['median_b'], 5)} ({num(row['iqr_b'], 5)})"
            if row["median_a"] < row["median_b"]:
                cell_a = rf"\textbf{{{num(row['median_a'], 5)}}} ({num(row['iqr_a'], 5)})"
            elif row["median_b"] < row["median_a"]:
                cell_b = rf"\textbf{{{num(row['median_b'], 5)}}} ({num(row['iqr_b'], 5)})"
            lines.append(f"{tex(code)} & {cell_a} & {cell_b} & {num(row['a12'], 2)} & "
                         f"[{num(row['a12_ci_low'], 2)}; {num(row['a12_ci_high'], 2)}] & "
                         f"{pvalue(row['p_value_holm'])} & {SYMBOLS[str(row['simbolo'])]} " + r"\\")
        lines.append(r"\hline")
        lines.append(rf"\multicolumn{{7}}{{l}}{{$+/\approx/-$: {integer(row_global['mejor_significativo'])} / "
                     rf"{integer(row_global['sin_diferencia'])} / {integer(row_global['peor_significativo'])}"
                     rf"\qquad Wilcoxon sobre {len(codes)} medianas: {pexpr('p', row_global['p_value'])} "
                     rf"({pexpr('p_{Holm}', row_global['p_value_holm'])})}} \\")
        table_end(lines)

    for _, row_global in global_tests[global_tests["family"] == "control"].iterrows():
        rival = row_global["algoritmo_b"]
        typical_table(
            f"TablaPUnoAuto{MACRO_NAMES[rival]}", row_global,
            f"{tex(label(control))} frente a {tex(label(rival))}, instancia por instancia: LCOE mediano [CNY/kWh] e IQR, "
            f"$\\hat{{A}}_{{12}}$ (mayor que 0,5: gana {tex(label(control))}) con IC bootstrap, Mann--Whitney bilateral con Holm sobre "
            f"las {len(codes)} instancias. $+$/$-$: {tex(label(control))} significativamente mejor/peor; $\\approx$: sin diferencia significativa. "
            "Negrita: mejor mediana",
            f"tab:puno_{rival}")

    # ------------------------------------------------------------------ cada metaheuristica frente a la linea base
    base_rows = pd.concat([
        global_tests[(global_tests["family"] == "linea_base")],
        global_tests[(global_tests["family"] == "control") & (global_tests["algoritmo_b"] == baseline)],
    ])
    table_begin(lines, "TablaLineaBaseAuto",
                f"Cada metaheurística frente a la búsqueda aleatoria: $\\hat{{A}}_{{12}}$ por instancia (mayor que 0,5: gana la "
                f"metaheurística). Negrita: significativo tras Holm sobre las {len(codes)} instancias del par",
                "tab:linea_base_auto", "l " + "r " * len(codes) + "c r")
    lines.append(r"\textbf{Alg.} & " + " & ".join(rf"\textbf{{{c}}}" for c in codes)
                 + r" & \textbf{$+/\approx/-$} & \textbf{$p$ Wilcoxon} \\")
    lines.append(r"\hline")
    for _, row_global in base_rows.iterrows():
        sub = per_instance[(per_instance["family"] == row_global["family"])
                           & (per_instance["algoritmo_a"] == row_global["algoritmo_a"])
                           & (per_instance["algoritmo_b"] == row_global["algoritmo_b"])].set_index("instance").reindex(codes)
        cells = [rf"\textbf{{{num(r['a12'], 2)}}}" if truthy(r["significativo"]) else num(r["a12"], 2)
                 for _, r in sub.iterrows()]
        lines.append(f"{tex(label(row_global['algoritmo_a']))} & " + " & ".join(cells)
                     + f" & {integer(row_global['mejor_significativo'])} / {integer(row_global['sin_diferencia'])} / "
                       f"{integer(row_global['peor_significativo'])} & {pvalue(row_global['p_value'])} " + r"\\")
    table_end(lines)

    # ------------------------------------------------------------------ P2: en general
    table_begin(lines, "TablaGlobalAuto",
                f"Comparación en general: Wilcoxon de rangos con signo sobre una mediana por instancia ({len(codes)} pares). "
                "G/E/P: instancias donde A tiene mejor, igual o peor mediana que B. Robustez: la misma prueba sobre brechas relativas y la prueba de signos",
                "tab:global_auto", "l l c r r r r r c")
    lines.append(r"\textbf{A} & \textbf{B} & \textbf{G/E/P} & \textbf{$W$} & \textbf{$p$} & \textbf{$p_{Holm}$} & "
                 r"\textbf{$p$ relativa} & \textbf{$p$ signos} & \textbf{$+/\approx/-$} \\")
    lines.append(r"\hline")
    previous_family = None
    for _, row in global_tests.iterrows():
        if previous_family is not None and row["family"] != previous_family:
            lines.append(r"\hline")
        previous_family = row["family"]
        w_stat = num(row["wilcoxon_w"], 1) if pd.notna(row["wilcoxon_w"]) else "--"
        lines.append(f"{tex(label(row['algoritmo_a']))} & {tex(label(row['algoritmo_b']))} & "
                     f"{integer(row['gana_mediana'])}/{integer(row['empata_mediana'])}/{integer(row['pierde_mediana'])} & "
                     f"{w_stat} & {pvalue(row['p_value'])} & {pvalue(row['p_value_holm'])} & "
                     f"{pvalue(row['p_value_relativa'])} & {pvalue(row['p_value_signos'])} & "
                     f"{integer(row['mejor_significativo'])} / {integer(row['sin_diferencia'])} / "
                     f"{integer(row['peor_significativo'])} " + r"\\")
    table_end(lines)

    # ------------------------------------------------------------------ sensibilidad: igual numero de disenos unicos
    pair_key = ["family", "algoritmo_a", "algoritmo_b"]
    both = global_tests.merge(unique_global, on=pair_key, suffixes=("", "_u"))

    def holm_cell(p_value, significant) -> str:
        text = pvalue(p_value)
        return rf"\textbf{{{text}}}" if truthy(significant) else text

    table_begin(lines, "TablaUnicosAuto",
                "Sensibilidad a la contabilidad del presupuesto: cada contraste con la regla principal "
                f"({integer(metadata['requests_per_run'])} solicitudes, repeticiones incluidas) y a igual número de diseños únicos "
                f"(corte en la mediana del GA en cada instancia, entre {integer(cut_values.min())} y {integer(cut_values.max())} diseños). "
                f"P1: recuento $+/\\approx/-$ sobre las {len(codes)} instancias; P2: $p$ de Wilcoxon tras Holm, en negrita si es significativo",
                "tab:unicos_auto", "l l c c r r")
    lines.append(r"\textbf{A} & \textbf{B} & \textbf{P1 principal} & \textbf{P1 únicos} & "
                 r"\textbf{$p_{Holm}$ principal} & \textbf{$p_{Holm}$ únicos} \\")
    lines.append(r"\hline")
    previous_family = None
    for _, row in both.iterrows():
        if previous_family is not None and row["family"] != previous_family:
            lines.append(r"\hline")
        previous_family = row["family"]
        lines.append(
            f"{tex(label(row['algoritmo_a']))} & {tex(label(row['algoritmo_b']))} & "
            f"{integer(row['mejor_significativo'])} / {integer(row['sin_diferencia'])} / {integer(row['peor_significativo'])} & "
            f"{integer(row['mejor_significativo_u'])} / {integer(row['sin_diferencia_u'])} / {integer(row['peor_significativo_u'])} & "
            f"{holm_cell(row['p_value_holm'], row['significativo'])} & "
            f"{holm_cell(row['p_value_holm_u'], row['significativo_u'])} " + r"\\")
    table_end(lines)

    # ------------------------------------------------------------------ convergencia
    shown = [k for k in checkpoints if k % 100 == 0]
    table_begin(lines, "TablaConvergenciaAuto",
                f"Convergencia: rango medio de cada algoritmo tras cada 100 solicitudes (1 = menor brecha mediana de la "
                f"instancia, promedio sobre las {len(codes)} instancias), brecha mediana media a {integer(half_point)} y "
                f"{integer(final_point)} solicitudes y su reducción relativa en la segunda mitad del presupuesto. "
                "Descriptivo: no se contrasta en los puntos intermedios",
                "tab:convergencia_auto", "l " + "r " * len(shown) + "r r r")
    lines.append(rf"\textbf{{Alg.}} & \multicolumn{{{len(shown)}}}{{c}}{{\textbf{{Rango medio tras $n$ solicitudes}}}} & "
                 r"\multicolumn{2}{c}{\textbf{Brecha [\%]}} & \textbf{Reducción} \\")
    lines.append(rf"\cline{{2-{len(shown) + 1}}}\cline{{{len(shown) + 2}-{len(shown) + 3}}}")
    lines.append(" & " + " & ".join(integer(k) for k in shown)
                 + f" & {integer(half_point)} & {integer(final_point)} & " + r"\textbf{[\%]} \\")
    lines.append(r"\hline")
    for algorithm in order:
        lines.append(f"{tex(label(algorithm))} & " + " & ".join(num(rank_at.loc[k, algorithm], 2) for k in shown)
                     + f" & {num(gap_at.loc[half_point, algorithm], 2)} & {num(gap_at.loc[final_point, algorithm], 2)} & "
                       f"{num(reduction[algorithm], 0)} " + r"\\")
    table_end(lines)

    # ------------------------------------------------------------------ P3: rangos de Friedman
    cross_index = cross.set_index("algorithm")
    table_begin(lines, "TablaRankingTransversalAuto",
                "Rango de cada algoritmo por instancia (1 = menor brecha mediana), rango medio del contraste de Friedman, "
                "brecha mediana media y éxito medio al 0,5\\,\\%",
                "tab:ranking_transversal_auto", "l l " + "r " * len(codes) + "r r r")
    lines.append(r"\textbf{\#} & \textbf{Alg.} & " + " & ".join(rf"\textbf{{{c}}}" for c in codes)
                 + r" & \textbf{Rango medio} & \textbf{Brecha med. [\%]} & \textbf{Éxito 0,5\% [\%]} \\")
    lines.append(r"\hline")
    for position, row in ranks.iterrows():
        cells = " & ".join(num(row[f"rank_{c}"], 1).replace(",0", "") for c in codes)
        extra = cross_index.loc[row["algorithm"]]
        lines.append(f"{position + 1} & {tex(label(row['algorithm']))} & {cells} & "
                     f"{num(row['mean_rank'], 2)} & {num(extra['mean_median_gap_pct'], 3)} & "
                     f"{num(100 * extra['mean_success_0.5pct'], 1)} " + r"\\")
    table_end(lines)

    table_begin(lines, "TablaPotenciaAuto",
                "Potencia aproximada de la prueba t bilateral equivalente ($\\alpha = 0{,}05$) según la unidad de análisis; "
                "con pruebas de rangos la potencia es algo menor",
                "tab:potencia_auto", "l l r r r r")
    lines.append(r"\textbf{Unidad de análisis} & \textbf{Diseño} & \textbf{$n$} & \textbf{Potencia $d = 0{,}5$} & "
                 r"\textbf{Potencia $d = 0{,}8$} & \textbf{$d$ detectable (potencia 0,8)} \\")
    lines.append(r"\hline")
    for unit, row in power.iterrows():
        unit_text = {"replicas por instancia": "réplicas por instancia"}.get(unit, unit)
        lines.append(f"{tex(unit_text)} & {tex(row['diseno'])} & {integer(row['n'])} & {num(row['potencia_dz_0.5'], 2)} & "
                     f"{num(row['potencia_dz_0.8'], 2)} & {num(row['dz_detectable_potencia_0.8'], 2)} " + r"\\")
    table_end(lines)


    # ------------------------------------------------------------------ sensibilidad
    for frame, command, caption, label_ in (
        (sens_agsr, "TablaSensAGSRAuto", "Sensibilidad al límite anual de venta a red", "tab:sens_agsr_auto"),
        (sens_load, "TablaSensCargaAuto", "Sensibilidad a la carga mínima del electrolizador", "tab:sens_carga_auto"),
    ):
        table_begin(lines, command, caption, label_, "r r r r r r")
        lines.append(r"\textbf{Valor} & \textbf{Factibles} & \textbf{Fracción} & \textbf{Mejor LCOE} & \textbf{$W$ [MW]} & \textbf{$E$ [MW]} \\")
        lines.append(r"\hline")
        for row in frame.itertuples(index=False):
            lines.append(f"{num(row.value, 2)} & {integer(row.feasible)} & {num(row.feasible_share, 3)} & "
                         f"{num(row.best_lcoe_cny_per_kwh, 6)} & {num(row.best_wind_mw, 0)} & {num(row.best_electrolyzer_mw, 0)} " + r"\\")
        table_end(lines)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
