"""Genera tablas y macros LaTeX directamente desde los CSV del notebook."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from scipy import stats


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "notebooks" / "results"
OUTPUT = ROOT / "latex" / "generated" / "resultados_auto.tex"


def read(name: str) -> pd.DataFrame:
    path = RESULTS / name
    if not path.exists():
        raise FileNotFoundError(f"Falta {path}; ejecute primero el notebook completo")
    return pd.read_csv(path)


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
    }.items():
        text = text.replace(source, target)
    return (text.replace("&", r"\&").replace("%", r"\%")
            .replace("_", r"\_").replace("#", r"\#"))


def num(value: float, digits: int = 4) -> str:
    return f"{float(value):.{digits}f}".replace(".", ",")


def integer(value: float) -> str:
    return f"{int(round(float(value))):,}".replace(",", ".")


def macro(lines: list[str], name: str, value: object) -> None:
    lines.append(rf"\newcommand{{\{name}}}{{{value}}}")


def spanish_list(values: list[str]) -> str:
    if not values:
        return "ninguno"
    if len(values) == 1:
        return values[0]
    return ", ".join(values[:-1]) + " y " + values[-1]


def table_begin(lines: list[str], command: str, caption: str, label: str,
                columns: str, size: str = r"\scriptsize") -> None:
    lines.extend([
        rf"\newcommand{{\{command}}}{{%",
        r"\begin{table}[H]", r"\centering", size,
        rf"\caption{{{caption}}}", rf"\label{{{label}}}",
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
    reference = read("reference_grid_summary.csv").iloc[0]
    reference_top = read("reference_grid_top10.csv")
    runs = read("algorithm_runs.csv")
    ranking = read("algorithm_summary.csv")
    pairwise = read("pairwise_tests.csv")
    sens_agsr = read("sensitivity_agsr.csv")
    sens_load = read("sensitivity_min_load.csv")
    best_horizon = read("best_design_horizon_sensitivity.csv").iloc[0]
    metadata = read("experiment_metadata.csv").iloc[0]

    base_feasible = base[base["feasible"].astype(str).str.lower().isin(("true", "1"))]
    base_best = base_feasible.sort_values("lcoe_cny_per_kwh").iloc[0]
    best_run = runs.sort_values("score").iloc[0]
    if float(reference["best_lcoe_cny_per_kwh"]) <= float(best_run["score"]):
        best = reference_top.iloc[0].copy()
        best["algorithm"] = "referencia de malla"
        best["score"] = best["lcoe_cny_per_kwh"]
    else:
        best = best_run
    samples = [group["score"].dropna().to_numpy()
               for _, group in runs.groupby("algorithm")]
    h_stat, h_p = stats.kruskal(*samples)
    sig_pairs = int(pairwise["significativo_alpha_0.05"].astype(str)
                    .str.lower().isin(("true", "1")).sum())
    random_better: list[str] = []
    random_worse: list[str] = []
    random_equal: list[str] = []
    for _, row in pairwise.iterrows():
        a, b = str(row["algoritmo_a"]), str(row["algoritmo_b"])
        if "random" not in (a, b):
            continue
        other = b if a == "random" else a
        significant = str(row["significativo_alpha_0.05"]).lower() in ("true", "1")
        if not significant:
            random_equal.append(other.upper())
            continue
        a_better = float(row["a12"]) > 0.5
        other_better = a_better if a == other else not a_better
        (random_worse if other_better else random_better).append(other.upper())

    lines = ["% Archivo generado. No editar manualmente."]
    macro(lines, "HoursMain", integer(metadata["hours_main"]))
    macro(lines, "HoursSensitivity", integer(metadata["hours_sensitivity"]))
    macro(lines, "TotalDesignRequests", integer(metadata["total_requests"]))
    macro(lines, "RequestedHourlySteps", integer(metadata["main_hourly_steps_requested"]))
    macro(lines, "BaseEvaluated", integer(len(base)))
    macro(lines, "BaseFeasible", integer(len(base_feasible)))
    macro(lines, "BaseFeasiblePct", num(100 * len(base_feasible) / len(base), 1))
    macro(lines, "BaseBestLCOE", num(base_best["lcoe_cny_per_kwh"], 6))
    macro(lines, "BaseBestWind", num(base_best["wind_mw"], 0))
    macro(lines, "BaseBestElectrolyzer", num(base_best["electrolyzer_mw"], 0))
    macro(lines, "ReferenceEvaluated", integer(reference["evaluated"]))
    macro(lines, "ReferenceFeasible", integer(reference["feasible"]))
    macro(lines, "ReferenceBestLCOE", num(reference["best_lcoe_cny_per_kwh"], 6))
    macro(lines, "BestObservedAlgorithm", tex(str(best["algorithm"]).upper()))
    macro(lines, "BestObservedLCOE", num(best["score"], 6))
    macro(lines, "BestObservedWind", num(best["wind_mw"], 2))
    macro(lines, "BestObservedPV", num(best["pv_mw"], 2))
    macro(lines, "BestObservedElectrolyzer", num(best["electrolyzer_mw"], 0))
    macro(lines, "BestObservedBattery", num(best["battery_mw"], 0))
    macro(lines, "BestObservedDuration", num(best["battery_duration_h"], 0))
    macro(lines, "BestObservedLCOH", num(best["lcoh_cny_per_kg"], 2))
    macro(lines, "BestObservedAGSR", num(best["agsr"], 4))
    macro(lines, "BestHorizonDeltaPct", num(best_horizon["delta_LCOE_pct"], 3))
    macro(lines, "KruskalH", num(h_stat, 3))
    macro(lines, "KruskalP", f"{h_p:.3g}")
    macro(lines, "SignificantPairs", sig_pairs)
    macro(lines, "TotalPairs", len(pairwise))
    macro(lines, "MaxBalanceResidual", f"{runs['max_balance_residual_mw'].max():.2e}")
    macro(lines, "TopMedianAlgorithm", tex(str(ranking.iloc[0]["algorithm"]).upper()))
    macro(lines, "BottomMedianAlgorithm", tex(str(ranking.iloc[-1]["algorithm"]).upper()))
    macro(lines, "RandomMedianRank", integer(ranking.index[ranking["algorithm"] == "random"][0] + 1))
    macro(lines, "BetterThanRandomAlgorithms", tex(spanish_list(sorted(random_worse))))
    macro(lines, "WorseThanRandomAlgorithms", tex(spanish_list(sorted(random_better))))
    macro(lines, "NoDifferenceFromRandomAlgorithms", tex(spanish_list(sorted(random_equal))))
    lines.append("")

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

    table_begin(lines, "TablaReferenciaAuto", "Mejores puntos de la referencia determinista de malla",
                "tab:referencia_auto", "r r r r r r r", r"\footnotesize")
    lines.append(r"\textbf{$W$} & \textbf{$P$} & \textbf{$E$} & \textbf{$B^P$} & \textbf{$h_B$} & \textbf{AGSR} & \textbf{LCOE} \\")
    lines.append(r"\hline")
    for row in reference_top.head(5).itertuples(index=False):
        lines.append(f"{num(row.wind_mw, 1)} & {num(row.pv_mw, 1)} & {num(row.electrolyzer_mw, 0)} & "
                     f"{num(row.battery_mw, 0)} & {num(row.battery_duration_h, 0)} & {num(row.agsr, 4)} & {num(row.lcoe_cny_per_kwh, 6)} " + r"\\")
    table_end(lines)

    table_begin(lines, "TablaRankingAuto", "Calidad final por algoritmo en 30 ejecuciones independientes",
                "tab:ranking_auto", "l r r r r r")
    lines.append(r"\textbf{Alg.} & \textbf{Mediana} & \textbf{IQR} & \textbf{Mejor} & \textbf{Peor} & \textbf{Brecha [\%]} \\")
    lines.append(r"\hline")
    for _, row in ranking.iterrows():
        lines.append(f"{tex(str(row['algorithm']).upper())} & {num(row['median'], 6)} & {num(row['iqr'], 6)} & "
                     f"{num(row['best'], 6)} & {num(row['worst'], 6)} & {num(row['median_gap_pct'], 3)} " + r"\\")
    table_end(lines)

    table_begin(lines, "TablaExitoAuto", "Probabilidad empírica de proximidad a la mejor referencia observada",
                "tab:exito_auto", "l r r r")
    lines.append(r"\textbf{Alg.} & \textbf{Brecha $\leq$0,1\%} & \textbf{Brecha $\leq$0,5\%} & \textbf{Brecha $\leq$1\%} \\")
    lines.append(r"\hline")
    for _, row in ranking.iterrows():
        lines.append(f"{tex(str(row['algorithm']).upper())} & {num(100 * row['success_0.1pct'], 1)}\\% & "
                     f"{num(100 * row['success_0.5pct'], 1)}\\% & {num(100 * row['success_1.0pct'], 1)}\\% " + r"\\")
    table_end(lines)

    table_begin(lines, "TablaComputoAuto", "Conteo y costo de las evaluaciones por algoritmo",
                "tab:computo_auto", "l r r r r")
    lines.append(r"\textbf{Alg.} & \textbf{Factibles} & \textbf{Únicas (media)} & \textbf{Duplicadas (media)} & \textbf{Tiempo [s]} \\")
    lines.append(r"\hline")
    for _, row in ranking.iterrows():
        lines.append(f"{tex(str(row['algorithm']).upper())} & {integer(row['feasible_runs'])}/30 & "
                     f"{num(row['mean_unique'], 1)} & {num(row['mean_duplicates'], 1)} & {num(row['mean_elapsed_s'], 2)} " + r"\\")
    table_end(lines)

    table_begin(lines, "TablaParesAuto", "Comparaciones Mann--Whitney bilaterales, corrección de Holm y $A_{12}$",
                "tab:pares_auto", "l l r r r p{2.8cm}")
    lines.append(r"\textbf{A} & \textbf{B} & \textbf{$p_{Holm}$} & \textbf{$A_{12}$} & \textbf{IC 95\%} & \textbf{Significativa} \\")
    lines.append(r"\hline")
    for _, row in pairwise.iterrows():
        significant = str(row['significativo_alpha_0.05']).lower() in ("true", "1")
        lines.append(f"{tex(str(row['algoritmo_a']).upper())} & {tex(str(row['algoritmo_b']).upper())} & "
                     f"{float(row['p_value_holm']):.3g} & {num(row['a12'], 3)} & "
                     f"[{num(row['a12_ci_low'], 3)}; {num(row['a12_ci_high'], 3)}] & "
                     f"{'sí' if significant else 'no'} " + r"\\")
    table_end(lines)

    for frame, command, caption, label in (
        (sens_agsr, "TablaSensAGSRAuto", "Sensibilidad al límite anual de venta a red", "tab:sens_agsr_auto"),
        (sens_load, "TablaSensCargaAuto", "Sensibilidad a la carga mínima del electrolizador", "tab:sens_carga_auto"),
    ):
        table_begin(lines, command, caption, label, "r r r r r r")
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
