"""Comparacion estadistica entre metaheuristicas.

``aggregate_runs`` en :mod:`h2_hres.analysis.summaries` ya agrupa por
``algorithm``; lo que falta es decidir si la diferencia entre dos algoritmos es
real (test de hipotesis) y, si lo es, cuan grande (tamano del efecto). Sin
ambas cosas, "el algoritmo A dio mejor media" no es una conclusion defendible:
podria ser ruido de semilla.
"""

from __future__ import annotations

from itertools import combinations
from typing import List

import numpy as np
import pandas as pd
from scipy import stats

from .summaries import aggregate_runs

__all__ = [
    "vargha_delaney_a12",
    "pairwise_wilcoxon",
    "comparison_table",
]


def vargha_delaney_a12(a: np.ndarray, b: np.ndarray) -> float:
    """Tamano del efecto A12 de Vargha-Delaney.

    Probabilidad de que una corrida tomada al azar de ``a`` obtenga un score
    mejor (menor, porque el objetivo es LCOE) que una de ``b``, mas la mitad de
    la probabilidad de empate. Vale 0.5 si las dos muestras son
    indistinguibles, 1.0 si ``a`` domina siempre a ``b`` y 0.0 si es al reves.

    Es el tamano del efecto estandar en la literatura de metaheuristicas
    (Arcuri & Briand, 2011) precisamente porque no asume normalidad ni varianzas
    iguales -- los scores de un optimizador estocastico no cumplen ninguna de
    las dos.
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    n_a, n_b = len(a), len(b)
    if n_a == 0 or n_b == 0:
        raise ValueError("ambas muestras deben tener al menos una corrida")

    # rango de a dentro de la union: suma de comparaciones a[i] < b[j] (gana),
    # con 0.5 por cada empate.
    wins = 0.0
    for value in a:
        wins += np.sum(value < b) + 0.5 * np.sum(value == b)
    return wins / (n_a * n_b)


def pairwise_wilcoxon(runs: pd.DataFrame, score_column: str = "score") -> pd.DataFrame:
    """Wilcoxon pareado por semilla entre cada par de algoritmos.

    Pareado porque la misma semilla define el mismo problema para todos los
    algoritmos (arranque, orden de muestreo), asi que comparar semilla a
    semilla controla esa fuente de varianza en vez de promediarla. No
    parametrico porque los scores de un optimizador estocastico no son
    normales en general.

    Se corrige por comparaciones multiples con Holm-Bonferroni: con 4
    algoritmos hay 6 pares, y sin corregir el riesgo de un falso positivo entre
    los seis crece muy por encima del 5% nominal.
    """
    algorithms = sorted(runs["algorithm"].unique())
    if len(algorithms) < 2:
        raise ValueError("hacen falta al menos dos algoritmos para comparar")

    pivot = runs.pivot(index="seed", columns="algorithm", values=score_column)
    pivot = pivot.dropna()  # solo semillas presentes en todos los algoritmos
    if len(pivot) < 2:
        raise ValueError(
            "hacen falta al menos dos semillas comunes a todos los algoritmos "
            "para el test pareado; hay {}".format(len(pivot))
        )

    pairs = list(combinations(algorithms, 2))
    rows: List[dict] = []
    for algo_a, algo_b in pairs:
        sample_a = pivot[algo_a].to_numpy()
        sample_b = pivot[algo_b].to_numpy()
        differences = sample_a - sample_b

        if np.allclose(differences, 0.0):
            # scipy.stats.wilcoxon lanza ValueError si todas las diferencias
            # son cero; es un resultado legitimo, no un error de calculo.
            p_value = 1.0
        else:
            _, p_value = stats.wilcoxon(sample_a, sample_b)

        rows.append(
            {
                "algoritmo_a": algo_a,
                "algoritmo_b": algo_b,
                "mediana_a": float(np.median(sample_a)),
                "mediana_b": float(np.median(sample_b)),
                "p_value": float(p_value),
                "a12": vargha_delaney_a12(sample_a, sample_b),
                "n_semillas": len(pivot),
            }
        )

    table = pd.DataFrame(rows)
    table["p_value_holm"] = _holm_bonferroni(table["p_value"].to_numpy())
    table["significativo_alpha_0.05"] = table["p_value_holm"] < 0.05
    return table


def _holm_bonferroni(p_values: np.ndarray) -> np.ndarray:
    """Correccion de Holm-Bonferroni: menos conservadora que Bonferroni simple.

    Ordena los p-valores de menor a mayor y multiplica el i-esimo por
    ``(m - i)``, garantizando monotonia (un p-valor corregido nunca es menor
    que el de un p-valor mas pequeno) antes de recortar a 1.0.
    """
    m = len(p_values)
    order = np.argsort(p_values)
    adjusted = np.empty(m)
    running_max = 0.0
    for rank, index in enumerate(order):
        corrected = min((m - rank) * p_values[index], 1.0)
        running_max = max(running_max, corrected)
        adjusted[index] = running_max
    return adjusted


def comparison_table(runs: pd.DataFrame, score_column: str = "score") -> pd.DataFrame:
    """Estadistica descriptiva por algoritmo, con ranking por mediana.

    Envuelve ``aggregate_runs`` -- que ya agrupa por ``algorithm`` -- y agrega
    solo el ranking, que es lo que falta para leer la tabla de un vistazo.
    """
    summaries = runs.to_dict("records")
    stats_table = aggregate_runs(summaries)
    if stats_table.empty:
        return stats_table
    stats_table = stats_table.sort_values("best").reset_index(drop=True)
    stats_table.insert(0, "ranking", range(1, len(stats_table) + 1))
    return stats_table
