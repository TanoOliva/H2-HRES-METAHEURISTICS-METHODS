"""Analisis estadistico de la comparativa de metaheuristicas.

Sigue el protocolo de siete pasos de la guia "Comparacion estadistica de algoritmos
estocasticos de optimizacion" (E. Vega, OII464):

1. Disenar   -- instancias, R replicas, semillas fijas y el mismo presupuesto de
                solicitudes: lo fija el notebook; aqui solo se comprueba el balance.
2. Preguntar -- contrastes bilaterales, alfa = 0,05 y tolerancia epsilon declarados
                como constantes de este modulo, antes de mirar los datos.
3. Explorar  -- Shapiro-Wilk por (instancia, algoritmo).
4. Elegir    -- P1, una instancia: Mann-Whitney (cada algoritmo usa su propio flujo
                aleatorio, de modo que las replicas no forman pares).
                P2, en general: Wilcoxon de rangos con signo sobre una mediana por
                instancia (pareado por instancia).
                P3, todos a la vez: Friedman e Iman-Davenport sobre esas medianas.
5. Cuantificar -- A12 de Vargha-Delaney con IC bootstrap y Hodges-Lehmann.
6. Corregir  -- Holm dentro de cada familia de contrastes.
7. Reportar  -- tablas ``stat_*.csv`` y dos figuras.

Ejecutado por separado, calcula ademas dos analisis que no forman parte del plan
confirmatorio: la sensibilidad a igual numero de disenos unicos y el perfil de
convergencia (rango medio en cada punto de control), ambos a partir de los historiales.

La variable de respuesta es la brecha relativa al optimo exacto de la instancia, en
porcentaje, con la tolerancia aplicada: toda brecha menor o igual que EPS_GAP_PCT se
trata como cero. Dentro de una instancia es una transformacion monotona del LCOE, asi
que las pruebas de rangos solo cambian por los empates que introduce la tolerancia.

Uso independiente (lee ``notebooks/results`` y escribe alli las tablas):

    python scripts/analisis_estadistico.py

El notebook importa este mismo modulo, de modo que hay una unica implementacion.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import optimize, stats

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "notebooks" / "results"
FIGURES = ROOT / "latex" / "figures"

# ---------------------------------------------------------------------------
# Decisiones del analisis, fijadas antes de correr las instancias I5 a I8.
# ---------------------------------------------------------------------------
ALPHA = 0.05            # nivel de significacion, contrastes bilaterales
EPS_GAP_PCT = 0.01      # tolerancia: brechas <= 0,01 % del optimo cuentan como 0
N_BOOT = 5000           # remuestreos bootstrap de los intervalos al 95 %
CONTROL = "pso_ga"      # el hibrido es el algoritmo de control
BASELINE = "random"     # linea base sin aprendizaje
PARENTS = ("pso", "ga")

ORDER = ("gwo", "pso", "ga", "sho", "woa", "pso_ga", "random")
LABELS = {"gwo": "GWO", "pso": "PSO", "ga": "GA", "sho": "SHO", "woa": "WOA",
          "pso_ga": "PSO+GA", "random": "RANDOM"}
COLORS = {"gwo": "#2a78d6", "pso": "#eb6834", "ga": "#1baf7a", "sho": "#eda100",
          "woa": "#e87ba4", "pso_ga": "#a8431a", "random": "#898781"}

# Umbrales de magnitud de Vargha y Delaney sobre |A12 - 0,5|.
A12_THRESHOLDS = ((0.06, "despreciable"), (0.14, "pequeno"), (0.21, "mediano"))


def label(algorithm: str) -> str:
    return LABELS.get(algorithm, str(algorithm).upper())


# ---------------------------------------------------------------------------
# Estadisticos elementales
# ---------------------------------------------------------------------------
def vargha_delaney_a12(a, b) -> float:
    """P(a < b) + 0,5 P(a = b). Se minimiza: > 0,5 significa que ``a`` gana."""
    a = np.asarray(a, dtype=float)[:, None]
    b = np.asarray(b, dtype=float)[None, :]
    return float((np.sum(a < b) + 0.5 * np.sum(a == b)) / (a.size * b.size))


def a12_magnitude(a12: float) -> str:
    distance = abs(a12 - 0.5)
    for threshold, name in A12_THRESHOLDS:
        if distance < threshold:
            return name
    return "grande"


def hodges_lehmann(a, b) -> float:
    """Mediana de todas las diferencias a_i - b_j (desplazamiento de ``a`` respecto de ``b``)."""
    a = np.asarray(a, dtype=float)[:, None]
    b = np.asarray(b, dtype=float)[None, :]
    return float(np.median(a - b))


def bootstrap_ci(a, b, n_boot=N_BOOT, seed=0):
    """IC percentil al 95 % de A12 y de Hodges-Lehmann, remuestreando cada grupo por separado."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    rng = np.random.default_rng(seed)
    sample_a = a[rng.integers(0, a.size, size=(n_boot, a.size))]
    sample_b = b[rng.integers(0, b.size, size=(n_boot, b.size))]
    less = sample_a[:, :, None] < sample_b[:, None, :]
    equal = sample_a[:, :, None] == sample_b[:, None, :]
    a12 = (less.sum(axis=(1, 2)) + 0.5 * equal.sum(axis=(1, 2))) / (a.size * b.size)
    shift = np.median((sample_a[:, :, None] - sample_b[:, None, :]).reshape(n_boot, -1), axis=1)
    return (tuple(np.quantile(a12, [0.025, 0.975])), tuple(np.quantile(shift, [0.025, 0.975])))


def holm(p_values) -> np.ndarray:
    """p ajustados de Holm-Bonferroni (los NaN se devuelven como NaN y no cuentan en m)."""
    p_values = np.asarray(p_values, dtype=float)
    adjusted = np.full(p_values.shape, np.nan)
    valid = np.flatnonzero(np.isfinite(p_values))
    m = len(valid)
    running_max = 0.0
    for rank, index in enumerate(valid[np.argsort(p_values[valid], kind="stable")]):
        running_max = max(running_max, min((m - rank) * p_values[index], 1.0))
        adjusted[index] = running_max
    return adjusted


def paired_t_power(effect_dz: float, n: int, alpha: float = ALPHA) -> float:
    """Potencia de la t pareada bilateral para un efecto estandarizado ``dz`` y ``n`` pares."""
    if n < 2:
        return float("nan")
    df = n - 1
    noncentrality = effect_dz * math.sqrt(n)
    critical = stats.t.ppf(1.0 - alpha / 2.0, df)
    return float(stats.nct.sf(critical, df, noncentrality) + stats.nct.cdf(-critical, df, noncentrality))


def two_sample_t_power(effect_d: float, n: int, alpha: float = ALPHA) -> float:
    """Potencia de la t bilateral de dos muestras independientes de tamano ``n`` cada una."""
    if n < 2:
        return float("nan")
    df = 2 * n - 2
    noncentrality = effect_d * math.sqrt(n / 2.0)
    critical = stats.t.ppf(1.0 - alpha / 2.0, df)
    return float(stats.nct.sf(critical, df, noncentrality) + stats.nct.cdf(-critical, df, noncentrality))


def detectable_effect(n: int, power: float = 0.8, alpha: float = ALPHA,
                      power_function=paired_t_power) -> float:
    """Efecto estandarizado que la prueba t indicada detecta con la potencia pedida."""
    if n < 2:
        return float("nan")

    def excess(dz):
        value = power_function(dz, n, alpha)
        # La t no central desborda con no centralidades grandes: ahi la potencia ya es 1.
        return (value if np.isfinite(value) else 1.0) - power

    return float(optimize.brentq(excess, 1e-3, 20.0))


# ---------------------------------------------------------------------------
# Preparacion
# ---------------------------------------------------------------------------
def prepare(runs: pd.DataFrame, optima: dict) -> pd.DataFrame:
    """Corridas con la brecha al optimo exacto y la brecha con tolerancia."""
    frame = runs.loc[runs["algorithm"].isin(ORDER),
                     ["instance", "algorithm", "replicate", "score"]].copy()
    frame["optimum"] = frame["instance"].map(optima).astype(float)
    if frame["optimum"].isna().any():
        missing = sorted(frame.loc[frame["optimum"].isna(), "instance"].unique())
        raise ValueError("falta el optimo exacto de: {}".format(", ".join(missing)))
    frame["gap_pct"] = (frame["score"] / frame["optimum"] - 1.0) * 100.0
    frame["gap_eps_pct"] = np.where(frame["gap_pct"] <= EPS_GAP_PCT, 0.0, frame["gap_pct"])
    return frame.reset_index(drop=True)


def contrast_pairs(algorithms) -> list:
    """Familias planificadas: el hibrido frente a cada rival y cada metaheuristica frente a la linea base."""
    algorithms = [a for a in ORDER if a in set(algorithms)]
    pairs = []
    if CONTROL in algorithms:
        pairs += [("control", CONTROL, rival) for rival in algorithms if rival != CONTROL]
    if BASELINE in algorithms:
        pairs += [("linea_base", a, BASELINE) for a in algorithms if a not in (CONTROL, BASELINE)]
    return pairs


# ---------------------------------------------------------------------------
# Paso 3: normalidad
# ---------------------------------------------------------------------------
def normality_table(frame: pd.DataFrame, instances, algorithms) -> pd.DataFrame:
    rows = []
    for code in instances:
        for algorithm in algorithms:
            values = frame.loc[(frame["instance"] == code) & (frame["algorithm"] == algorithm),
                               "gap_eps_pct"].dropna().to_numpy()
            statistic = p_value = np.nan
            if len(values) >= 3 and np.ptp(values) > 0:
                statistic, p_value = stats.shapiro(values)
            rows.append({"instance": code, "algorithm": algorithm, "n": len(values),
                         "shapiro_w": statistic, "p_value": p_value,
                         "rechaza_normalidad": bool(np.isfinite(p_value) and p_value < ALPHA)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# P1: una instancia, muestras independientes
# ---------------------------------------------------------------------------
def per_instance_tests(frame: pd.DataFrame, instances, pairs, n_boot=N_BOOT) -> pd.DataFrame:
    rows = []
    optima = frame.groupby("instance")["optimum"].first()
    for pair_index, (family, algo_a, algo_b) in enumerate(pairs):
        block = []
        for instance_index, code in enumerate(instances):
            sub = frame[frame["instance"] == code]
            a = sub.loc[sub["algorithm"] == algo_a, "gap_eps_pct"].dropna().to_numpy()
            b = sub.loc[sub["algorithm"] == algo_b, "gap_eps_pct"].dropna().to_numpy()
            score_a = sub.loc[sub["algorithm"] == algo_a, "score"]
            score_b = sub.loc[sub["algorithm"] == algo_b, "score"]
            row = {"family": family, "instance": code, "algoritmo_a": algo_a, "algoritmo_b": algo_b,
                   "n_a": len(a), "n_b": len(b),
                   "median_a": score_a.median(), "median_b": score_b.median(),
                   "iqr_a": score_a.quantile(0.75) - score_a.quantile(0.25),
                   "iqr_b": score_b.quantile(0.75) - score_b.quantile(0.25),
                   "median_gap_a_pct": float(np.median(a)) if len(a) else np.nan,
                   "median_gap_b_pct": float(np.median(b)) if len(b) else np.nan}
            if len(a) >= 2 and len(b) >= 2:
                u_stat, p_value = stats.mannwhitneyu(a, b, alternative="two-sided")
                a12 = vargha_delaney_a12(a, b)
                (a12_low, a12_high), (hl_low, hl_high) = bootstrap_ci(
                    a, b, n_boot=n_boot, seed=[2026, pair_index, instance_index])
                shift = hodges_lehmann(a, b)
                row.update({"U": u_stat, "p_value": p_value, "a12": a12,
                            "a12_ci_low": a12_low, "a12_ci_high": a12_high,
                            "magnitud": a12_magnitude(a12),
                            "hl_gap_pp": shift, "hl_ci_low_pp": hl_low, "hl_ci_high_pp": hl_high,
                            "hl_cny_per_kwh": shift / 100.0 * float(optima[code])})
            else:
                row.update({"U": np.nan, "p_value": np.nan, "a12": np.nan,
                            "a12_ci_low": np.nan, "a12_ci_high": np.nan, "magnitud": "",
                            "hl_gap_pp": np.nan, "hl_ci_low_pp": np.nan, "hl_ci_high_pp": np.nan,
                            "hl_cny_per_kwh": np.nan})
            block.append(row)
        # Holm dentro de la familia de una pregunta: el mismo par en todas las instancias.
        adjusted = holm([r["p_value"] for r in block])
        for row, p_holm in zip(block, adjusted):
            row["p_value_holm"] = p_holm
            significant = bool(np.isfinite(p_holm) and p_holm < ALPHA)
            row["significativo"] = significant
            row["simbolo"] = ("+" if row["a12"] > 0.5 else "-") if significant else "="
        rows.extend(block)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# P2: en general, pareado por instancia
# ---------------------------------------------------------------------------
def _wilcoxon_p(differences) -> tuple:
    differences = np.asarray(differences, dtype=float)
    nonzero = differences[differences != 0.0]
    if len(nonzero) == 0:
        return np.nan, 1.0
    ranks = stats.rankdata(np.abs(nonzero))
    exact = len(nonzero) == len(differences) and len(np.unique(ranks)) == len(ranks)
    result = stats.wilcoxon(differences, zero_method="wilcox", alternative="two-sided",
                            method="exact" if exact else "approx")
    return float(result.statistic), float(result.pvalue)


def global_tests(frame: pd.DataFrame, per_instance: pd.DataFrame, instances, pairs) -> pd.DataFrame:
    median_score = frame.pivot_table(index="instance", columns="algorithm", values="score",
                                     aggfunc="median").reindex(instances)
    median_gap = frame.pivot_table(index="instance", columns="algorithm", values="gap_eps_pct",
                                   aggfunc="median").reindex(instances)
    rows = []
    for family, algo_a, algo_b in pairs:
        d_score = (median_score[algo_a] - median_score[algo_b]).to_numpy()
        d_gap = (median_gap[algo_a] - median_gap[algo_b]).to_numpy()
        wins, ties, losses = int((d_gap < 0).sum()), int((d_gap == 0).sum()), int((d_gap > 0).sum())
        w_stat, p_value = _wilcoxon_p(d_score)
        _, p_relative = _wilcoxon_p(d_gap)
        p_sign = (stats.binomtest(wins, wins + losses, 0.5).pvalue if wins + losses else 1.0)
        walsh = [(d_gap[i] + d_gap[j]) / 2.0 for i in range(len(d_gap)) for j in range(i, len(d_gap))]
        symbols = per_instance.loc[(per_instance["algoritmo_a"] == algo_a)
                                   & (per_instance["algoritmo_b"] == algo_b), "simbolo"]
        rows.append({"family": family, "algoritmo_a": algo_a, "algoritmo_b": algo_b,
                     "n_instances": len(instances),
                     "gana_mediana": wins, "empata_mediana": ties, "pierde_mediana": losses,
                     "wilcoxon_w": w_stat, "p_value": p_value,
                     "p_value_relativa": p_relative, "p_value_signos": float(p_sign),
                     "hl_pareado_gap_pp": float(np.median(walsh)),
                     "mejor_significativo": int((symbols == "+").sum()),
                     "sin_diferencia": int((symbols == "=").sum()),
                     "peor_significativo": int((symbols == "-").sum())})
    table = pd.DataFrame(rows)
    table["p_value_holm"] = np.nan
    for family in table["family"].unique():
        mask = (table["family"] == family).to_numpy()
        table.loc[mask, "p_value_holm"] = holm(table.loc[mask, "p_value"].to_numpy())
    table["significativo"] = table["p_value_holm"] < ALPHA
    return table


# ---------------------------------------------------------------------------
# P3: todos los algoritmos
# ---------------------------------------------------------------------------
def friedman_tests(frame: pd.DataFrame, instances, algorithms):
    median_gap = frame.pivot_table(index="instance", columns="algorithm", values="gap_eps_pct",
                                   aggfunc="median").reindex(index=instances, columns=algorithms)
    ranks = median_gap.rank(axis=1, method="average")
    n, k = ranks.shape
    rank_table = ranks.T.copy()
    rank_table.columns = ["rank_" + code for code in rank_table.columns]
    rank_table.insert(0, "algorithm", rank_table.index)
    rank_table["mean_rank"] = ranks.mean(axis=0).to_numpy()
    rank_table = rank_table.sort_values("mean_rank").reset_index(drop=True)

    chi2 = p_chi2 = f_stat = p_f = np.nan
    if n >= 2 and k >= 3:
        chi2, p_chi2 = stats.friedmanchisquare(*(median_gap[a].to_numpy() for a in algorithms))
        denominator = n * (k - 1) - chi2
        if denominator > 0:
            f_stat = (n - 1) * chi2 / denominator
            p_f = float(stats.f.sf(f_stat, k - 1, (k - 1) * (n - 1)))
        else:
            f_stat, p_f = np.inf, 0.0
    q_alpha = float(stats.studentized_range.ppf(1.0 - ALPHA, k, np.inf) / math.sqrt(2.0))
    critical_difference = q_alpha * math.sqrt(k * (k + 1) / (6.0 * n))
    summary = pd.DataFrame([{
        "n_instances": n, "k_algorithms": k, "friedman_chi2": float(chi2),
        "friedman_p": float(p_chi2), "iman_davenport_f": float(f_stat),
        "iman_davenport_df1": k - 1, "iman_davenport_df2": (k - 1) * (n - 1),
        "iman_davenport_p": float(p_f), "q_alpha": q_alpha,
        "critical_difference": critical_difference,
        "posthoc_procede": bool(np.isfinite(p_f) and p_f < ALPHA),
    }])
    return summary, rank_table


def power_table(n_replicates: int, n_instances: int) -> pd.DataFrame:
    # P1 compara dos muestras independientes de R corridas; P2 y P3, N instancias pareadas.
    rows = []
    for unit, design, n, function in (
        ("replicas por instancia", "dos muestras independientes", n_replicates, two_sample_t_power),
        ("instancias", "pareado", n_instances, paired_t_power),
    ):
        rows.append({"unidad": unit, "diseno": design, "n": n,
                     "potencia_dz_0.5": function(0.5, n),
                     "potencia_dz_0.8": function(0.8, n),
                     "dz_detectable_potencia_0.8": detectable_effect(n, power_function=function),
                     "p_minimo_wilcoxon_exacto": 2.0 / 2.0 ** n if design == "pareado" else float("nan")})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Analisis completo
# ---------------------------------------------------------------------------
def analyze(runs: pd.DataFrame, optima: dict, instances=None, n_boot=N_BOOT) -> dict:
    """Devuelve todas las tablas del analisis; ``optima`` asocia cada instancia con su LCOE optimo."""
    frame = prepare(runs, optima)
    if instances is None:
        instances = sorted(frame["instance"].unique())
    instances = list(instances)
    algorithms = [a for a in ORDER if a in set(frame["algorithm"])]
    counts = frame.groupby(["instance", "algorithm"]).size()
    if counts.nunique() != 1:
        raise ValueError("el diseno no es balanceado: {}".format(counts.to_dict()))
    pairs = contrast_pairs(algorithms)
    per_instance = per_instance_tests(frame, instances, pairs, n_boot=n_boot)
    global_table = global_tests(frame, per_instance, instances, pairs)
    friedman, ranks = friedman_tests(frame, instances, algorithms)
    design = pd.DataFrame([{
        "alpha": ALPHA, "eps_gap_pct": EPS_GAP_PCT, "n_boot": n_boot, "control": CONTROL,
        "baseline": BASELINE, "n_instances": len(instances), "n_algorithms": len(algorithms),
        "replicates": int(counts.iloc[0]),
        "tests_per_instance": len(per_instance), "tests_global": len(global_table),
        "tests_omnibus": 1, "tests_total": len(per_instance) + len(global_table) + 1,
    }])
    return {
        "frame": frame, "instances": instances, "algorithms": algorithms,
        "design": design,
        "normality": normality_table(frame, instances, algorithms),
        "per_instance": per_instance,
        "global": global_table,
        "friedman": friedman,
        "ranks": ranks,
        "power": power_table(int(counts.iloc[0]), len(instances)),
    }


def csv_tables(result: dict) -> dict:
    """Tablas que se exportan, indexadas por nombre de archivo."""
    return {
        "stat_design.csv": result["design"],
        "stat_normality.csv": result["normality"],
        "stat_per_instance.csv": result["per_instance"],
        "stat_global.csv": result["global"],
        "stat_friedman.csv": result["friedman"],
        "stat_ranks.csv": result["ranks"],
        "stat_power.csv": result["power"],
    }


# ---------------------------------------------------------------------------
# Sensibilidad a la contabilidad del presupuesto: igual numero de disenos unicos
# ---------------------------------------------------------------------------
REFERENCE_UNIQUE = "ga"  # el algoritmo que mas solicitudes repite fija el punto de corte


def equal_unique_runs(runs: pd.DataFrame, history: pd.DataFrame,
                      reference: str = REFERENCE_UNIQUE) -> tuple:
    """Resultado de cada corrida al llegar al numero mediano de disenos unicos de ``reference``.

    La regla principal cuenta toda solicitud, aunque repita un diseno ya evaluado. Esta
    variante compara a todos los algoritmos cuando han simulado tantos disenos distintos
    como la corrida mediana de ``reference`` en esa instancia; una corrida que nunca llega a
    ese numero aporta su valor final. La comparacion favorece a ``reference``, que conserva
    todas sus solicitudes mientras los demas quedan truncados.
    """
    key = ["instance", "algorithm", "replicate"]
    cut = (runs.loc[runs["algorithm"] == reference]
           .groupby("instance")["n_unique_evaluations"].median())
    frame = history.copy()
    frame["corte_unicos"] = frame["instance"].map(cut)
    frame = frame.loc[frame["n_unique_evaluations"] <= frame["corte_unicos"]]
    last = frame.sort_values("iteration").groupby(key).tail(1)
    if len(last) != len(runs):
        raise ValueError("no todas las corridas tienen un punto de historial bajo el corte")
    if not last["feasible"].astype(str).str.lower().isin(("true", "1")).all():
        raise ValueError("hay corridas cuyo mejor diseno en el corte es infactible")
    truncated = last[key + ["n_evaluations", "n_unique_evaluations"]].copy()
    truncated["score"] = last["best_score"].to_numpy()
    cutoff = (truncated.groupby(["instance", "algorithm"])["n_evaluations"].median()
              .rename("solicitudes_mediana").reset_index())
    cutoff["corte_unicos"] = cutoff["instance"].map(cut)
    return truncated.reset_index(drop=True), cutoff


def equal_unique_sensitivity(runs: pd.DataFrame, history: pd.DataFrame, optima: dict,
                             instances=None, n_boot=N_BOOT) -> dict:
    """El protocolo completo aplicado a las corridas truncadas a igual numero de disenos unicos."""
    truncated, cutoff = equal_unique_runs(runs, history)
    result = analyze(truncated, optima, instances=instances, n_boot=n_boot)
    return {"cutoff": cutoff, "per_instance": result["per_instance"], "global": result["global"],
            "friedman": result["friedman"], "ranks": result["ranks"]}


def sensitivity_csv_tables(sensitivity: dict) -> dict:
    return {
        "stat_unicos_corte.csv": sensitivity["cutoff"],
        "stat_unicos_per_instance.csv": sensitivity["per_instance"],
        "stat_unicos_global.csv": sensitivity["global"],
        "stat_unicos_friedman.csv": sensitivity["friedman"],
        "stat_unicos_ranks.csv": sensitivity["ranks"],
    }


# ---------------------------------------------------------------------------
# Convergencia (descriptiva, sin contrastes en los puntos intermedios)
# ---------------------------------------------------------------------------
def convergence_profile(history: pd.DataFrame, optima: dict, instances=None) -> pd.DataFrame:
    """Rango medio y brecha mediana media de cada algoritmo en cada punto de control.

    En cada punto de control (cada ``population`` solicitudes) se toma, por instancia, la
    mediana entre replicas de la brecha del mejor diseno factible encontrado hasta ese
    punto, con la misma tolerancia que el analisis principal; una corrida sin diseno
    factible todavia cuenta con brecha infinita. Los algoritmos se ordenan dentro de cada
    instancia por esa mediana y se promedia el rango sobre las instancias, igual que en
    el contraste de Friedman. En el ultimo punto de control coincide con ese contraste.
    No se contrasta nada en los puntos intermedios: el perfil es descriptivo.
    """
    frame = history.loc[history["algorithm"].isin(ORDER)].copy()
    instances = list(instances) if instances is not None else sorted(frame["instance"].unique())
    algorithms = [a for a in ORDER if a in set(frame["algorithm"])]
    frame["optimum"] = frame["instance"].map(optima).astype(float)
    if frame["optimum"].isna().any():
        raise ValueError("falta el optimo exacto de alguna instancia del historial")
    feasible = frame["feasible"].astype(str).str.lower().isin(("true", "1"))
    gap = (frame["best_score"] / frame["optimum"] - 1.0) * 100.0
    gap = gap.where(feasible & gap.notna(), np.inf)
    frame["gap_eps_pct"] = np.where(gap <= EPS_GAP_PCT, 0.0, gap)
    median_gap = frame.pivot_table(index=["n_evaluations", "instance"], columns="algorithm",
                                   values="gap_eps_pct", aggfunc="median")
    rows = []
    for requests, block in median_gap.groupby(level="n_evaluations"):
        block = block.droplevel("n_evaluations").reindex(index=instances, columns=algorithms)
        mean_rank = block.rank(axis=1, method="average").mean(axis=0)
        position = mean_rank.rank(method="min")
        mean_gap = block.mean(axis=0)
        for algorithm in algorithms:
            rows.append({"n_evaluations": int(requests), "algorithm": algorithm,
                         "mean_rank": float(mean_rank[algorithm]),
                         "position": int(position[algorithm]),
                         "mean_median_gap_pct": float(mean_gap[algorithm])})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Figuras
# ---------------------------------------------------------------------------
def figure_a12(result: dict, family: str = "control", ncols: int = 3):
    """A12 por instancia con IC al 95 %; marcador lleno = significativo tras Holm."""
    import matplotlib.pyplot as plt

    table = result["per_instance"]
    table = table[table["family"] == family]
    instances = result["instances"]
    pairs = list(dict.fromkeys(zip(table["algoritmo_a"], table["algoritmo_b"])))
    nrows = math.ceil(len(pairs) / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(4.3 * ncols, 0.36 * len(instances) * nrows + 1.6 * nrows),
                             sharex=True, sharey=True, squeeze=False)
    positions = np.arange(len(instances))[::-1]
    for ax, (algo_a, algo_b) in zip(axes.ravel(), pairs):
        sub = table[(table["algoritmo_a"] == algo_a) & (table["algoritmo_b"] == algo_b)] \
            .set_index("instance").reindex(instances)
        focus = algo_b if family == "control" else algo_a
        color = COLORS.get(focus, "#444444")
        ax.axvspan(0.44, 0.56, color="#e9e7e1", zorder=0)
        ax.axvline(0.5, color="#555555", lw=0.9, linestyle="--", zorder=1)
        for y, (_, row) in zip(positions, sub.iterrows()):
            if not np.isfinite(row["a12"]):
                continue
            ax.plot([row["a12_ci_low"], row["a12_ci_high"]], [y, y], color=color, lw=1.4, zorder=2)
            ax.scatter([row["a12"]], [y], s=46, zorder=3, edgecolor=color, linewidths=1.4,
                       facecolor=color if row["significativo"] else "white")
        ax.set_title("{} frente a {}".format(label(algo_a), label(algo_b)), fontsize=10)
        ax.set_xlim(0.0, 1.0)
        ax.set_yticks(positions, instances, fontsize=9)
        ax.set_ylim(-0.7, len(instances) - 0.3)
        ax.grid(axis="y", visible=False)
    for ax in axes.ravel()[len(pairs):]:
        ax.axis("off")
    for ax in axes[-1]:
        ax.set_xlabel("A12 (> 0,5: gana {})".format(
            label(CONTROL) if family == "control" else "la metaheuristica"), fontsize=9)
    fig.suptitle("Probabilidad de superioridad A12 por instancia, IC bootstrap al 95 %. "
                 "Lleno: significativo tras Holm; banda gris: efecto despreciable", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    return fig


def _cd_groups(mean_ranks: np.ndarray, critical_difference: float) -> list:
    """Grupos maximales de algoritmos consecutivos cuyo rango medio difiere menos que CD."""
    groups = []
    n = len(mean_ranks)
    for start in range(n):
        end = start
        while end + 1 < n and mean_ranks[end + 1] - mean_ranks[start] <= critical_difference:
            end += 1
        if end > start and not any(s <= start and end <= e for s, e in groups):
            groups.append((start, end))
    return groups


def figure_cd(result: dict):
    """Diagrama de diferencia critica de Nemenyi sobre los rangos medios."""
    import matplotlib.pyplot as plt

    ranks = result["ranks"].sort_values("mean_rank").reset_index(drop=True)
    summary = result["friedman"].iloc[0]
    k = len(ranks)
    cd = float(summary["critical_difference"])
    values = ranks["mean_rank"].to_numpy()
    fig, ax = plt.subplots(figsize=(10, 0.42 * k + 2.3))
    ax.hlines(0, 1, k, color="#222222", lw=1.2)
    for tick in range(1, k + 1):
        ax.vlines(tick, -0.08, 0.08, color="#222222", lw=1.2)
        ax.text(tick, 0.16, str(tick), ha="center", va="bottom", fontsize=9)
    ax.hlines(0.62, 1, 1 + cd, color="#8a1c1c", lw=2.4)
    ax.text(1 + cd / 2.0, 0.70, "CD = {:.2f}".format(cd).replace(".", ","), ha="center",
            va="bottom", fontsize=9, color="#8a1c1c")
    half = math.ceil(k / 2)
    for index, row in ranks.iterrows():
        left = index < half
        depth = (index if left else k - 1 - index) + 1
        y = -0.45 - 0.33 * depth
        x_text = 0.75 if left else k + 0.25
        color = COLORS.get(row["algorithm"], "#444444")
        ax.plot([row["mean_rank"], row["mean_rank"], x_text], [0, y, y], color=color, lw=1.3)
        ax.text(x_text - 0.05 if left else x_text + 0.05, y,
                "{} ({:.2f})".format(label(row["algorithm"]), row["mean_rank"]).replace(".", ","),
                ha="right" if left else "left", va="center", fontsize=9.5, color=color,
                fontweight="bold")
    for level, (start, end) in enumerate(_cd_groups(values, cd)):
        y = -0.16 - 0.11 * level
        ax.hlines(y, values[start] - 0.04, values[end] + 0.04, color="#222222", lw=3.2)
    ax.set_xlim(0.0, k + 1.0)
    ax.set_ylim(-0.45 - 0.33 * (half + 1), 1.15)
    ax.axis("off")
    ax.set_title("Rangos medios sobre {} instancias (1 = mejor). Las barras negras unen "
                 "algoritmos sin diferencia significativa (Nemenyi, alfa = 0,05)".format(
                     int(summary["n_instances"])), fontsize=10)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Uso independiente
# ---------------------------------------------------------------------------
def main() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    runs = pd.read_csv(RESULTS / "algorithm_runs.csv")
    brute = pd.read_csv(RESULTS / "brute_force_summary.csv")
    optima = dict(zip(brute["instance"], brute["optimum_lcoe_cny_per_kwh"]))
    ignored = sorted(set(runs["algorithm"]) - set(ORDER))
    if ignored:
        print("Algoritmos fuera del analisis (se ignoran):", ", ".join(ignored))
    result = analyze(runs, optima, instances=list(brute["instance"]))
    for filename, table in csv_tables(result).items():
        table.to_csv(RESULTS / filename, index=False)
    FIGURES.mkdir(parents=True, exist_ok=True)
    for name, figure in (("fig07_a12_por_instancia.png", figure_a12(result)),
                         ("fig11_diferencia_critica.png", figure_cd(result))):
        figure.savefig(FIGURES / name, dpi=150, bbox_inches="tight")
        plt.close(figure)

    design = result["design"].iloc[0]
    friedman = result["friedman"].iloc[0]
    print("{} instancias, {} algoritmos, {} replicas; {} pruebas en total".format(
        design["n_instances"], design["n_algorithms"], design["replicates"], design["tests_total"]))
    print("Shapiro-Wilk: {} de {} muestras rechazan normalidad".format(
        int(result["normality"]["rechaza_normalidad"].sum()), len(result["normality"])))
    print("Friedman chi2={:.3f} p={:.4g}; Iman-Davenport F={:.3f} p={:.4g}; CD={:.3f}".format(
        friedman["friedman_chi2"], friedman["friedman_p"], friedman["iman_davenport_f"],
        friedman["iman_davenport_p"], friedman["critical_difference"]))
    columns = ["family", "algoritmo_a", "algoritmo_b", "gana_mediana", "pierde_mediana",
               "p_value", "p_value_holm", "mejor_significativo", "sin_diferencia",
               "peor_significativo"]
    print(result["global"][columns].to_string(index=False))
    print(result["ranks"][["algorithm", "mean_rank"]].to_string(index=False))

    # Sensibilidad: la misma inferencia a igual numero de disenos unicos.
    history = pd.read_csv(RESULTS / "algorithm_history.csv")
    sensitivity = equal_unique_sensitivity(runs, history, optima, instances=list(brute["instance"]))
    for filename, table in sensitivity_csv_tables(sensitivity).items():
        table.to_csv(RESULTS / filename, index=False)
    print("Sensibilidad a igual numero de disenos unicos (corte = mediana de {}):".format(
        label(REFERENCE_UNIQUE)))
    print(sensitivity["global"][columns].to_string(index=False))
    print(sensitivity["ranks"][["algorithm", "mean_rank"]].to_string(index=False))

    # Convergencia: el mismo rango medio en cada punto de control del historial.
    profile = convergence_profile(history, optima, instances=list(brute["instance"]))
    final = profile.loc[profile["n_evaluations"] == profile["n_evaluations"].max()]
    official = result["ranks"].set_index("algorithm")["mean_rank"]
    if not np.allclose(final.set_index("algorithm")["mean_rank"].reindex(official.index), official):
        raise ValueError("el rango medio del ultimo punto de control no coincide con el de Friedman")
    profile.to_csv(RESULTS / "stat_convergencia.csv", index=False)
    print("Convergencia: rango medio por punto de control (cada 100 solicitudes):")
    shown = profile.loc[profile["n_evaluations"] % 100 == 0]
    print(shown.pivot(index="algorithm", columns="n_evaluations", values="mean_rank")
          .round(2).to_string())


if __name__ == "__main__":
    main()
