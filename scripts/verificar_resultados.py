"""Comprueba los criterios cuantitativos del experimento completo.

Verifica, sobre los CSV de ``notebooks/results``:

- metadatos del experimento (modo completo, 4 instancias, 9 algoritmos, 30 replicas,
  600 solicitudes por corrida);
- una corrida por (instancia, algoritmo, replica), con presupuesto exacto, balance
  energetico y restricciones dentro de tolerancia y AGSR bajo el limite de su instancia;
- historial de 30 puntos de control por corrida, cada 20 solicitudes;
- fuerza bruta de cada instancia: control contra el simulador oficial, optimo factible y
  brechas de los algoritmos no mas negativas que la tolerancia declarada;
- contrastes planificados e hibrido-frente-a-padre completos.

Las corridas que terminan infactibles no abortan la verificacion: se listan, porque en
una instancia estrecha son un resultado y no un error.
"""

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "notebooks" / "results"
HYBRIDS = {"ga_ls": ("ga",), "pso_ga": ("pso", "ga"), "sho_ls": ("sho",)}
GAP_TOLERANCE_PCT = -0.01   # W continuo en los optimizadores vs. paso de 0,01 MW en la fuerza bruta


def read(name: str) -> pd.DataFrame:
    path = RESULTS / name
    if not path.exists():
        raise FileNotFoundError(f"Falta {path}")
    return pd.read_csv(path)


def truthy(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin(("true", "1", "1.0"))


def main() -> None:
    metadata = read("experiment_metadata.csv").iloc[0]
    instances = read("instances.csv")
    runs = read("algorithm_runs.csv")
    history = read("algorithm_history.csv")
    summary = read("algorithm_summary.csv")
    brute = read("brute_force_summary.csv")
    gaps = read("brute_force_algorithm_gaps.csv")
    pairwise = read("pairwise_tests.csv")
    hybrids = read("hybrid_vs_parent.csv")
    cross = read("cross_instance_ranking.csv")

    codes = list(instances["instance"])
    algorithms = sorted(runs["algorithm"].unique())
    n_instances, n_algorithms = len(codes), len(algorithms)
    replicates = int(metadata["replicates_per_algorithm"])
    population = int(metadata["population"])
    iterations = int(metadata["iterations"])
    budget = population * iterations

    # ---------------------------------------------------------------- metadatos
    assert metadata["mode"] == "completo", "el experimento debe correrse en modo completo"
    assert int(metadata["hours_main"]) == 8760
    assert int(metadata["hours_sensitivity"]) == 8784
    assert n_instances == 4 and int(metadata["instances"]) == 4
    assert n_algorithms == 9 and int(metadata["algorithms"]) == 9
    assert set(HYBRIDS) <= set(algorithms) and "random" in algorithms
    assert replicates == 30 and population == 20 and iterations == 30
    assert int(metadata["requests_per_run"]) == budget == 600
    assert int(metadata["requests_per_instance"]) == budget * replicates * n_algorithms == 162_000
    assert int(metadata["total_requests"]) == 162_000 * n_instances == 648_000
    assert int(metadata["main_hourly_steps_requested"]) == 648_000 * 8760

    # ---------------------------------------------------------------- corridas
    assert len(runs) == n_instances * n_algorithms * replicates == 1080
    counts = runs.groupby(["instance", "algorithm"]).size()
    assert (counts == replicates).all(), counts[counts != replicates]
    assert set(runs["instance"]) == set(codes)
    assert runs["n_evaluations"].eq(budget).all()
    assert (runs["n_unique_evaluations"] + runs["n_duplicates"]).eq(budget).all()
    assert runs["max_balance_residual_mw"].max() < 1e-8
    violation_columns = ["violation_balance", "violation_capacity", "violation_electrolyzer",
                         "violation_operation", "total_normalized_violation"]
    feasible = truthy(runs["feasible"])
    assert (runs.loc[feasible, violation_columns + ["violation_agsr"]].abs().max() < 1e-8).all()
    assert np.isfinite(runs.loc[feasible, "lcoe_cny_per_kwh"]).all()
    agsr_max = instances.set_index("instance")["agsr_max"]
    limites = runs["instance"].map(agsr_max)
    assert (runs.loc[feasible, "agsr"] <= limites[feasible] + 1e-12).all()
    infactibles = runs[~feasible]
    for name in ("ls_requests", "ls_improvements", "ls_calls"):
        assert name in runs.columns, f"falta la columna {name} de los hibridos"
    con_ls = runs[runs["algorithm"].isin(("ga_ls", "sho_ls"))]
    assert (con_ls["ls_requests"] > 0).all() and (con_ls["ls_calls"] > 0).all()
    assert (con_ls["ls_requests"] <= con_ls["ls_calls"] * 4).all()

    # ---------------------------------------------------------------- historial
    assert len(history) == len(runs) * iterations
    hist_counts = history.groupby(["instance", "algorithm", "replicate"]).size()
    assert (hist_counts == iterations).all()
    assert (history["n_evaluations"] == population * history["iteration"]).all()
    assert history.groupby(["instance", "algorithm", "replicate"])["best_merit"] \
        .apply(lambda s: s.is_monotonic_decreasing).all()

    # ---------------------------------------------------------------- resumen y ranking
    assert len(summary) == n_instances * n_algorithms
    assert (summary.groupby("instance")["ranking_descriptivo"].max() == n_algorithms).all()
    assert len(cross) == n_algorithms and cross["ranking_transversal"].tolist() == list(range(1, n_algorithms + 1))

    # ---------------------------------------------------------------- fuerza bruta
    assert len(brute) == n_instances and set(brute["instance"]) == set(codes)
    assert (brute["wind_step_mw"] == 0.01).all(), "el optimo exacto debe usar paso de 0,01 MW"
    inst = instances.set_index("instance")
    for row in brute.itertuples(index=False):
        assert int(row.catalogs) == int(inst.loc[row.instance, "n_catalogs"])
        assert int(row.evaluated) == int(row.wind_values) * int(row.catalogs)
        assert int(row.evaluated) == int(inst.loc[row.instance, "n_designs"])
        assert int(row.feasible) > 0 and np.isfinite(row.optimum_lcoe_cny_per_kwh)
        assert row.control_max_rel_diff_lcoe < 1e-9 and row.control_max_abs_diff_agsr < 1e-9
        assert row.optimum_agsr <= inst.loc[row.instance, "agsr_max"] + 1e-12
    expected_catalogs = {"I1": 341, "I2": 341, "I3": 1701, "I4": 651}
    for code, n_catalogs in expected_catalogs.items():
        assert int(inst.loc[code, "n_catalogs"]) == n_catalogs, (code, inst.loc[code, "n_catalogs"])
    assert len(gaps) == n_instances * n_algorithms
    assert (gaps["mejor"] >= GAP_TOLERANCE_PCT).all(), gaps[gaps["mejor"] < GAP_TOLERANCE_PCT]
    assert (gaps["mediana"] >= gaps["mejor"]).all() and (gaps["peor"] >= gaps["mediana"]).all()

    # ---------------------------------------------------------------- inferencia
    planned = pairwise[pairwise["family"] == "planned"]
    complete = pairwise[pairwise["family"] == "all"]
    n_pairs = n_algorithms * (n_algorithms - 1) // 2
    assert (planned.groupby("instance").size() == 12).all()
    assert (complete.groupby("instance").size() == n_pairs).all()
    assert len(hybrids) == n_instances * 4
    for code in codes:
        pares = set(zip(hybrids.loc[hybrids["instance"] == code, "hibrido"],
                        hybrids.loc[hybrids["instance"] == code, "padre"]))
        assert pares == {(h, p) for h, parents in HYBRIDS.items() for p in parents}, (code, pares)

    print("Verificación completa superada:")
    print(f"- {len(runs)} corridas: {n_instances} instancias x {n_algorithms} algoritmos x "
          f"{replicates} réplicas, {budget} solicitudes exactas por corrida")
    print(f"- {int(metadata['total_requests']):,} diseños anuales y "
          f"{int(metadata['main_hourly_steps_requested']):,} pasos horarios solicitados".replace(",", "."))
    print(f"- historial de {iterations} puntos de control por corrida, cada {population} solicitudes")
    print("- balance, factibilidad y AGSR dentro de tolerancia en todas las corridas factibles")
    print(f"- fuerza bruta: {int(brute['evaluated'].sum()):,} diseños en {n_instances} instancias, "
          f"control < 1e-9 y brechas >= {GAP_TOLERANCE_PCT} %".replace(",", "."))
    print(f"- {len(planned)} contrastes planificados, {len(complete)} pares completos y "
          f"{len(hybrids)} contrastes híbrido-padre")
    if infactibles.empty:
        print("- todas las corridas terminaron factibles")
    else:
        print(f"- AVISO: {len(infactibles)} corrida(s) terminaron infactibles:")
        for row in infactibles.itertuples(index=False):
            print(f"    {row.instance} {row.algorithm} réplica {row.replicate}: "
                  f"AGSR={row.agsr:.4f}, violación={row.total_normalized_violation:.3g}")


if __name__ == "__main__":
    main()
