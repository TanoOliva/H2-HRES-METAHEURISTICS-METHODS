"""Genera tablas y macros LaTeX directamente desde los CSV del notebook.

Los resultados tienen una columna ``instance`` (I1..I4). Como los nombres de macro
LaTeX no admiten digitos, cada instancia recibe un sufijo de letra en el orden del
archivo ``instances.csv``: I1 -> A, I2 -> B, I3 -> C, I4 -> D. Asi ``\\BFALCOE`` es el
optimo exacto de I1 y ``\\TablaRankingAutoC`` la tabla de ranking de I3.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "notebooks" / "results"
OUTPUT = ROOT / "latex" / "generated" / "resultados_auto.tex"

LABELS = {"ga_ls": "GA+LS", "pso_ga": "PSO+GA", "sho_ls": "SHO+LS"}
SUFFIXES = "ABCDEFGH"


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
    return (text.replace("&", r"\&").replace("%", r"\%")
            .replace("_", r"\_").replace("#", r"\#"))


def num(value: float, digits: int = 4) -> str:
    return f"{float(value):.{digits}f}".replace(".", ",")


def integer(value: float) -> str:
    return f"{int(round(float(value))):,}".replace(",", ".")


def pvalue(value: float) -> str:
    value = float(value)
    if pd.isna(value):
        return "--"
    return f"{value:.3g}".replace(".", ",")


def truthy(value: object) -> bool:
    return str(value).strip().lower() in ("true", "1", "1.0")


def macro(lines: list[str], name: str, value: object) -> None:
    lines.append(rf"\newcommand{{\{name}}}{{{value}}}")


def spanish_list(values: list[str]) -> str:
    if not values:
        return "ninguno"
    if len(values) == 1:
        return values[0]
    return ", ".join(values[:-1]) + " y " + values[-1]


def table_begin(lines: list[str], command: str, caption: str, label_: str,
                columns: str, size: str = r"\scriptsize") -> None:
    lines.extend([
        rf"\newcommand{{\{command}}}{{%",
        r"\begin{table}[H]", r"\centering", size,
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
    pairwise = read("pairwise_tests.csv")
    hybrids = read("hybrid_vs_parent.csv")
    hyper = read("algorithm_hyperparameters.csv")
    sens_agsr = read("sensitivity_agsr.csv")
    sens_load = read("sensitivity_min_load.csv")
    best_horizon = read("best_design_horizon_sensitivity.csv").iloc[0]
    metadata = read("experiment_metadata.csv").iloc[0]

    codes = [str(c) for c in instances["instance"]]
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
    macro(lines, "BaseEvaluated", integer(len(base)))
    macro(lines, "BaseFeasible", integer(len(base_feasible)))
    macro(lines, "BaseFeasiblePct", num(100 * len(base_feasible) / len(base), 1))
    macro(lines, "BaseBestLCOE", num(base_best["lcoe_cny_per_kwh"], 6))
    macro(lines, "BaseBestWind", num(base_best["wind_mw"], 0))
    macro(lines, "BaseBestElectrolyzer", num(base_best["electrolyzer_mw"], 0))
    macro(lines, "BestHorizonDeltaPct", num(best_horizon["delta_LCOE_pct"], 3))
    macro(lines, "MaxBalanceResidual", f"{runs['max_balance_residual_mw'].max():.2e}")
    macro(lines, "MaxControlRelDiff", f"{brute['control_max_rel_diff_lcoe'].max():.1e}")
    macro(lines, "MinFeasibleRuns", integer(ranking["feasible_runs"].min()))

    # ------------------------------------------------------------------ transversal
    top = cross.iloc[0]
    macro(lines, "BestMeanRankAlgorithm", tex(label(top["algorithm"])))
    macro(lines, "BestMeanRank", num(top["mean_rank"], 2))
    macro(lines, "SecondMeanRankAlgorithm", tex(label(cross.iloc[1]["algorithm"])))
    macro(lines, "SecondMeanRank", num(cross.iloc[1]["mean_rank"], 2))
    macro(lines, "WorstMeanRankAlgorithm", tex(label(cross.iloc[-1]["algorithm"])))
    random_row = cross[cross["algorithm"] == "random"]
    macro(lines, "RandomMeanRank", num(random_row.iloc[0]["mean_rank"], 2) if not random_row.empty else "--")
    macro(lines, "HybridContrastsTotal", integer(len(hybrids)))
    macro(lines, "HybridWinsCount", integer(hybrids["hibrido_mejor_mediana"].map(truthy).sum()))
    macro(lines, "HybridSignificantCount", integer(hybrids["significativo_alpha_0.05"].map(truthy).sum()))
    hybrid_sig_wins = hybrids[hybrids["significativo_alpha_0.05"].map(truthy)
                              & hybrids["hibrido_mejor_mediana"].map(truthy)]
    macro(lines, "HybridSignificantWins", integer(len(hybrid_sig_wins)))
    hybrid_sig_losses = hybrids[hybrids["significativo_alpha_0.05"].map(truthy)
                                & ~hybrids["hibrido_mejor_mediana"].map(truthy)]
    macro(lines, "HybridSignificantLosses", integer(len(hybrid_sig_losses)))

    # ------------------------------------------------------------------ por instancia
    for code in codes:
        s = suffix[code]
        inst = instances.set_index("instance").loc[code]
        bf = brute.loc[code]
        rk = ranking[ranking["instance"] == code].sort_values("ranking_descriptivo")
        planned = pairwise[(pairwise["instance"] == code) & (pairwise["family"] == "planned")]
        hv = hybrids[hybrids["instance"] == code]
        best_run = comparison[(comparison["instance"] == code)
                              & (comparison["algorithm"] != "fuerza_bruta")].iloc[0]
        macro(lines, f"InstLabel{s}", tex(inst["label"]))
        macro(lines, f"InstCapacity{s}", num(inst["total_capacity_mw"], 0))
        macro(lines, f"InstAGSR{s}", num(inst["agsr_max"], 2))
        macro(lines, f"InstCatalogs{s}", integer(inst["n_catalogs"]))
        macro(lines, f"BF{s}Designs", integer(bf["evaluated"]))
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
        macro(lines, f"BF{s}ControlLCOE", f"{float(bf['control_max_rel_diff_lcoe']):.1e}")
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

        vs_random = planned[planned["algoritmo_b"] == "random"]
        better, worse, equal = [], [], []
        for _, row in vs_random.iterrows():
            name = label(row["algoritmo_a"])
            if not truthy(row["significativo_alpha_0.05"]):
                equal.append(name)
            elif float(row["a12"]) > 0.5:
                better.append(name)
            else:
                worse.append(name)
        macro(lines, f"BetterThanRandom{s}", tex(spanish_list(better)))
        macro(lines, f"WorseThanRandom{s}", tex(spanish_list(worse)))
        macro(lines, f"NoDifferenceFromRandom{s}", tex(spanish_list(equal)))
        macro(lines, f"BetterThanRandomCount{s}", integer(len(better)))
        hyb_better = [f"{label(r['hibrido'])} ({label(r['padre'])})" for _, r in hv.iterrows()
                      if truthy(r["hibrido_mejor_mediana"])]
        hyb_sig = [f"{label(r['hibrido'])} vs {label(r['padre'])}" for _, r in hv.iterrows()
                   if truthy(r["significativo_alpha_0.05"])]
        macro(lines, f"HybridsBeatParent{s}", tex(spanish_list(hyb_better)))
        macro(lines, f"HybridsSignificant{s}", tex(spanish_list(hyb_sig)))
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
        lines.append(f"{tex(row.etapa)} & {tex(row.caso)} & {num(row.error_LCOE_pct, 2)} & {tex(row.cambio_documentado)} " + r"\\")
    table_end(lines)

    # ------------------------------------------------------------------ instancias y fuerza bruta
    table_begin(lines, "TablaInstanciasAuto", "Las cuatro instancias del problema de dimensionamiento",
                "tab:instancias_auto", "l l r r r r r r l r r")
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
                     f"{tex(row.hiperparametros)} & {tex(row.fuente)} " + r"\\")
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

        has_ls = "mean_ls_requests" in rk.columns
        table_begin(lines, f"TablaComputoAuto{s}",
                    f"Uso del presupuesto y costo de cómputo por algoritmo en {code} ({tex(inst_label)})",
                    f"tab:computo_auto_{code.lower()}", "l r r r r" + (" r" if has_ls else ""))
        lines.append(r"\textbf{Alg.} & \textbf{Factibles} & \textbf{Únicas (media)} & \textbf{Duplicadas (media)} & "
                     + (r"\textbf{Solic. LS (media)} & " if has_ls else "") + r"\textbf{Tiempo [s]} \\")
        lines.append(r"\hline")
        for _, row in rk.iterrows():
            ls_cell = ""
            if has_ls:
                ls_value = row["mean_ls_requests"]
                ls_cell = (num(ls_value, 1) if pd.notna(ls_value) else "--") + " & "
            lines.append(f"{tex(label(row['algorithm']))} & {integer(row['feasible_runs'])}/{replicates} & "
                         f"{num(row['mean_unique'], 1)} & {num(row['mean_duplicates'], 1)} & {ls_cell}"
                         f"{num(row['mean_elapsed_s'], 2)} " + r"\\")
        table_end(lines)

        for family, command, caption, size in (
            ("planned", f"TablaParesPlanificadosAuto{s}",
             f"Contrastes planificados en {code} ({tex(inst_label)}): Mann--Whitney bilateral, Holm dentro de la familia y $A_{{12}}$ (A frente a B)",
             r"\scriptsize"),
            ("all", f"TablaParesCompletaAuto{s}",
             f"Todos los pares en {code} ({tex(inst_label)}): Mann--Whitney bilateral, Holm sobre los 36 pares y $A_{{12}}$ (A frente a B)",
             r"\scriptsize"),
        ):
            sub = pairwise[(pairwise["instance"] == code) & (pairwise["family"] == family)]
            table_begin(lines, command, caption, f"tab:pares_{family}_{code.lower()}",
                        "l l r r r l", size)
            lines.append(r"\textbf{A} & \textbf{B} & \textbf{$p_{Holm}$} & \textbf{$A_{12}$} & \textbf{IC 95\%} & \textbf{Sig.} \\")
            lines.append(r"\hline")
            for _, row in sub.iterrows():
                ci = (f"[{num(row['a12_ci_low'], 3)}; {num(row['a12_ci_high'], 3)}]"
                      if pd.notna(row["a12_ci_low"]) else "--")
                a12 = num(row["a12"], 3) if pd.notna(row["a12"]) else "--"
                lines.append(f"{tex(label(row['algoritmo_a']))} & {tex(label(row['algoritmo_b']))} & "
                             f"{pvalue(row['p_value_holm'])} & {a12} & {ci} & "
                             f"{'sí' if truthy(row['significativo_alpha_0.05']) else 'no'} " + r"\\")
            table_end(lines)

    # ------------------------------------------------------------------ hibridos y transversal
    table_begin(lines, "TablaHibridosAuto", "Híbrido frente a padre por instancia: medianas, $A_{12}$ (híbrido frente a padre) y Holm dentro de la familia planificada",
                "tab:hibridos_auto", "l l l r r r r r r l")
    lines.append(r"\textbf{Inst.} & \textbf{Híbrido} & \textbf{Padre} & \textbf{Med. híb.} & \textbf{Med. padre} & \textbf{$\Delta$ [\%]} & \textbf{$A_{12}$} & \textbf{IC 95\%} & \textbf{$p_{Holm}$} & \textbf{Sig.} \\")
    lines.append(r"\hline")
    for _, row in hybrids.iterrows():
        ci = (f"[{num(row['a12_ci_low'], 2)}; {num(row['a12_ci_high'], 2)}]"
              if pd.notna(row["a12_ci_low"]) else "--")
        lines.append(f"{tex(row['instance'])} & {tex(label(row['hibrido']))} & {tex(label(row['padre']))} & "
                     f"{num(row['mediana_hibrido'], 6)} & {num(row['mediana_padre'], 6)} & "
                     f"{num(row['delta_mediana_pct'], 3)} & {num(row['a12_hibrido_vs_padre'], 3)} & {ci} & "
                     f"{pvalue(row['p_value_holm'])} & {'sí' if truthy(row['significativo_alpha_0.05']) else 'no'} " + r"\\")
    table_end(lines)

    table_begin(lines, "TablaRankingTransversalAuto", "Ranking transversal: rango por mediana en cada instancia, rango medio, brecha mediana media y éxito medio al 0,5\\%",
                "tab:ranking_transversal_auto", "l l " + "r " * len(codes) + "r r r")
    lines.append(r"\textbf{\#} & \textbf{Alg.} & " + " & ".join(rf"\textbf{{{c}}}" for c in codes)
                 + r" & \textbf{Rango medio} & \textbf{Brecha med. [\%]} & \textbf{Éxito 0,5\% [\%]} \\")
    lines.append(r"\hline")
    for _, row in cross.iterrows():
        ranks = " & ".join(integer(row[f"rank_{c}"]) for c in codes)
        lines.append(f"{integer(row['ranking_transversal'])} & {tex(label(row['algorithm']))} & {ranks} & "
                     f"{num(row['mean_rank'], 2)} & {num(row['mean_median_gap_pct'], 3)} & "
                     f"{num(100 * row['mean_success_0.5pct'], 1)} " + r"\\")
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
