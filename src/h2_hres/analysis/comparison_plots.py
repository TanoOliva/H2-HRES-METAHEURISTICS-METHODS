"""Figuras de la comparativa de metaheuristicas y de los barridos de sensibilidad.

``plots.py`` tiene cuatro figuras de una sola corrida o un solo barrido; ninguna
agrupa por algoritmo. Estas si: convergencia con banda entre algoritmos,
distribucion de resultados finales, y el trade-off calidad-tiempo. Comparten la
paleta y el ``rcParams`` de :mod:`h2_hres.analysis.style`.

Cada figura usa un solo eje por medida (nunca un eje Y doble): donde el paper
o la comparativa dan mas de una magnitud a la vez -- LCOE, capacidad,
factibilidad -- se resuelve en subplots lado a lado, no superponiendo escalas.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd

from .style import ALGORITHM_ORDER, algorithm_color, algorithm_linestyle, apply_style

__all__ = [
    "plot_convergence_by_algorithm",
    "plot_score_boxplot",
    "plot_quality_vs_time",
    "plot_sensitivity_sweep",
]

apply_style()


def _ordered_algorithms(present: pd.Series) -> list:
    """Los algoritmos presentes, en el orden fijo de la paleta.

    Cualquier nombre fuera de ``ALGORITHM_ORDER`` (un algoritmo agregado a
    futuro sin re-validar la paleta) se anexa al final, para no perder datos.
    """
    present_set = set(present.unique())
    ordered = [name for name in ALGORITHM_ORDER if name in present_set]
    ordered += sorted(present_set - set(ordered))
    return ordered


def plot_convergence_by_algorithm(history: pd.DataFrame) -> plt.Figure:
    """Mediana de convergencia por algoritmo, con banda intercuartil entre semillas.

    Una linea de una sola semilla (``plot_convergence`` en ``plots.py``) dice
    poco sobre un algoritmo estocastico; esta agrega las semillas de cada
    algoritmo con la mediana y muestra su dispersion con el rango
    intercuartil, mas robusto que la desviacion estandar frente a corridas que
    quedan atrapadas en un optimo local.
    """
    figure, axes = plt.subplots(figsize=(9, 5.5))

    for algorithm in _ordered_algorithms(history["algorithm"]):
        subset = history[history["algorithm"] == algorithm]
        grouped = subset.groupby("iteration")["best_score"]
        median = grouped.median()
        q1 = grouped.quantile(0.25)
        q3 = grouped.quantile(0.75)

        color = algorithm_color(algorithm)
        axes.plot(
            median.index, median.to_numpy(),
            color=color, linestyle=algorithm_linestyle(algorithm),
            label=algorithm.upper(),
        )
        axes.fill_between(median.index, q1.to_numpy(), q3.to_numpy(), color=color, alpha=0.15)

    axes.set_title("Convergencia por algoritmo (mediana y RIC entre semillas)")
    axes.set_xlabel("Iteracion")
    axes.set_ylabel("Mejor LCOE penalizado (CNY/kWh)")
    axes.legend()
    return figure


def plot_score_boxplot(runs: pd.DataFrame, score_column: str = "score") -> plt.Figure:
    """Distribucion de los resultados finales de cada algoritmo, una caja por semilla agregada.

    El boxplot es la vista que mejor comunica robustez: dos algoritmos con la
    misma mediana pero cajas de ancho distinto no son intercambiables para un
    uso donde una sola corrida importa.
    """
    algorithms = _ordered_algorithms(runs["algorithm"])
    data = [runs.loc[runs["algorithm"] == algorithm, score_column].to_numpy() for algorithm in algorithms]

    figure, axes = plt.subplots(figsize=(7.5, 5.5))
    boxes = axes.boxplot(
        data, patch_artist=True, widths=0.55, medianprops={"color": "#0b0b0b"},
    )
    # ``labels=``/``tick_labels=`` cambio de nombre entre versiones de
    # matplotlib; fijar las etiquetas aparte evita depender de cual acepta la
    # version instalada.
    axes.set_xticks(range(1, len(algorithms) + 1))
    axes.set_xticklabels([a.upper() for a in algorithms])
    for patch, algorithm in zip(boxes["boxes"], algorithms):
        patch.set_facecolor(algorithm_color(algorithm))
        patch.set_alpha(0.55)
        patch.set_edgecolor(algorithm_color(algorithm))

    axes.set_title("Distribucion del LCOE penalizado final ({} semillas)".format(
        runs.groupby("algorithm").size().max()
    ))
    axes.set_ylabel("LCOE penalizado (CNY/kWh)")
    return figure


def plot_quality_vs_time(runs: pd.DataFrame, score_column: str = "score") -> plt.Figure:
    """Calidad alcanzada vs. tiempo de computo, un punto por corrida.

    No es un argumento sobre cual algoritmo "gana": con presupuesto de
    evaluaciones identico (ver ``MetaheuristicConfig.evaluation_budget``), el
    tiempo por corrida refleja el costo del operador de movimiento, no
    ventaja alguna. Sirve para decidir cuantas semillas correr en la practica.
    """
    figure, axes = plt.subplots(figsize=(8, 5.5))

    for algorithm in _ordered_algorithms(runs["algorithm"]):
        subset = runs[runs["algorithm"] == algorithm]
        axes.scatter(
            subset["elapsed_s"], subset[score_column],
            color=algorithm_color(algorithm), label=algorithm.upper(),
            alpha=0.75, s=42, edgecolors="white", linewidths=0.5,
        )

    axes.set_title("Calidad vs. tiempo de computo (una corrida = un punto)")
    axes.set_xlabel("Tiempo de la corrida (s)")
    axes.set_ylabel("LCOE penalizado (CNY/kWh)")
    axes.legend()
    return figure


def plot_sensitivity_sweep(
    table: pd.DataFrame, x_label: str, x_format: str = "{:.0%}"
) -> plt.Figure:
    """Como se mueve el optimo y el dominio factible al variar un parametro.

    Tres paneles, cada uno con un solo eje Y -- LCOE, capacidades (mismas
    unidades, MW, por eso comparten panel sin violar la regla de un eje por
    medida) y tamano del dominio factible -- en vez de superponer escalas
    distintas en un eje doble.

    Sirve tanto para el barrido de AGSR como para el de carga minima: ambos
    devuelven la misma forma de tabla (``sweep_agsr_max`` /
    ``sweep_min_load_ratio`` en :mod:`h2_hres.analysis.sensitivity`).
    """
    table = table.sort_values("value")
    x = table["value"].to_numpy()

    figure, axes = plt.subplots(1, 3, figsize=(14, 4.5))

    axes[0].plot(x, table["best_lcoe_cny_per_kwh"], marker="o", color="#2a78d6")
    axes[0].set_ylabel("LCOE optimo (CNY/kWh)")
    axes[0].set_title("Costo")

    axes[1].plot(x, table["best_wind_mw"], marker="o", color="#2a78d6", label="Eolica")
    axes[1].plot(x, table["best_electrolyzer_mw"], marker="s", color="#eb6834", label="Electrolizador")
    axes[1].set_ylabel("Capacidad optima (MW)")
    axes[1].set_title("Diseno")
    axes[1].legend(fontsize=8)

    axes[2].plot(x, table["feasible_share"] * 100.0, marker="o", color="#1baf7a")
    axes[2].set_ylabel("Dominio factible (%)")
    axes[2].set_title("Factibilidad")

    for ax in axes:
        ax.set_xlabel(x_label)
        ax.set_xticks(x)
        ax.set_xticklabels([x_format.format(v) for v in x])

    figure.tight_layout()
    return figure
