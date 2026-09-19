"""Comprueba los criterios cuantitativos del experimento completo."""

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "notebooks" / "results"
ALGORITHMS = ("gwo", "pso", "ga", "sho", "woa", "random")


def read(name: str) -> pd.DataFrame:
    path = RESULTS / name
    if not path.exists():
        raise FileNotFoundError(f"Falta {path}")
    return pd.read_csv(path)


def main() -> None:
    metadata = read("experiment_metadata.csv").iloc[0]
    runs = read("algorithm_runs.csv")
    reference = read("reference_grid_summary.csv").iloc[0]

    assert metadata["mode"] == "completo"
    assert int(metadata["hours_main"]) == 8760
    assert int(metadata["hours_sensitivity"]) == 8784
    assert int(metadata["population"]) == 20
    assert int(metadata["iterations"]) == 30
    assert int(metadata["requests_per_run"]) == 600
    assert int(metadata["total_requests"]) == 108_000
    assert int(metadata["main_hourly_steps_requested"]) == 108_000 * 8760

    assert len(runs) == 180
    counts = runs.groupby("algorithm").size().to_dict()
    assert counts == {algorithm: 30 for algorithm in ALGORITHMS}
    assert runs["n_evaluations"].eq(600).all()
    assert (runs["n_unique_evaluations"] + runs["n_duplicates"]).eq(600).all()
    assert runs["feasible"].all()
    assert np.isfinite(runs["lcoe_cny_per_kwh"]).all()
    assert runs["max_balance_residual_mw"].max() < 1e-8
    violation_columns = [
        "violation_balance",
        "violation_capacity",
        "violation_electrolyzer",
        "violation_operation",
        "violation_agsr",
        "total_normalized_violation",
    ]
    assert (runs[violation_columns].abs().max() < 1e-8).all()
    assert (runs["agsr"] <= 0.20 + 1e-12).all()

    assert float(reference["wind_step_mw"]) == 0.5
    assert int(reference["evaluated"]) == 136_741
    assert int(reference["feasible"]) > 0
    assert np.isfinite(float(reference["best_lcoe_cny_per_kwh"]))

    print("Verificación completa superada:")
    print("- 180 corridas, 30 por algoritmo y 600 solicitudes por corrida")
    print("- 108.000 diseños anuales y 946.080.000 pasos horarios solicitados")
    print("- balance, factibilidad y AGSR dentro de tolerancia")
    print("- malla determinista de 136.741 diseños con paso eólico de 0,5 MW")


if __name__ == "__main__":
    main()
