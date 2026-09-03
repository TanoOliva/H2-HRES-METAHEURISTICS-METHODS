"""Graficos (celdas 11, 25, 26 y 43 del notebook).

Cada funcion devuelve la figura en lugar de llamar a ``plt.show()``, para que
sirva igual en un script -- que la guarda a disco -- y en una sesion
interactiva. El backend se fija a Agg solo si no hay ninguno interactivo, de
modo que la CLI funcione sin display.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

import os
import sys

import matplotlib

# Backend sin ventana por defecto: la CLI escribe PNG y nunca abre un display,
# y el backend interactivo por defecto puede fallar directamente al importarse
# (por ejemplo, un Python sin tkinter funcional). Se respeta la eleccion del
# usuario si fijo MPLBACKEND o si ya importo pyplot -- el caso de un Jupyter con
# %matplotlib inline.
if "MPLBACKEND" not in os.environ and "matplotlib.pyplot" not in sys.modules:
    matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from .style import apply_style

__all__ = [
    "plot_typical_year_selection",
    "plot_feasible_domain",
    "plot_lcoe_heatmap",
    "plot_convergence",
    "save_figure",
]

PathLike = Union[str, Path]

# Aplicado una vez al importar: todas las figuras del paquete -- las de aqui y
# las de comparison_plots.py -- comparten tipografia, grilla y dpi.
apply_style()


def save_figure(figure: plt.Figure, path: PathLike, dpi: int = 150) -> Path:
    """Guarda y cierra la figura, devolviendo la ruta escrita."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(target, dpi=dpi, bbox_inches="tight")
    plt.close(figure)
    return target


def plot_typical_year_selection(summary: pd.DataFrame) -> plt.Figure:
    """Distancia euclidiana de cada ano al patron global de complementariedad."""
    figure, axes = plt.subplots(figsize=(10, 5))
    distances = summary["euclidean_distance"]
    axes.plot(distances.index, distances.to_numpy(), marker="o")

    typical_year = distances.idxmin()
    axes.scatter(
        [typical_year],
        [distances.min()],
        s=140,
        marker="*",
        zorder=5,
        label="Ano tipico: {}".format(typical_year),
    )

    axes.set_title("Distancia al patron global de complementariedad viento-solar")
    axes.set_xlabel("Ano")
    axes.set_ylabel("Distancia euclidiana")
    axes.grid(True, alpha=0.3)
    axes.legend()
    return figure


def plot_feasible_domain(results: pd.DataFrame) -> plt.Figure:
    """Dominio factible sobre el plano Wind x Electrolyzer."""
    figure, axes = plt.subplots(figsize=(10, 6))

    infeasible = results[~results["feasible"]]
    feasible = results[results["feasible"]]

    axes.scatter(
        infeasible["wind_mw"],
        infeasible["electrolyzer_mw"],
        alpha=0.3,
        label="No factible ({})".format(len(infeasible)),
    )
    axes.scatter(
        feasible["wind_mw"],
        feasible["electrolyzer_mw"],
        alpha=0.85,
        label="Factible ({})".format(len(feasible)),
    )

    if len(feasible) > 0:
        best = feasible.sort_values("lcoe_cny_per_kwh").iloc[0]
        axes.scatter(
            [best["wind_mw"]],
            [best["electrolyzer_mw"]],
            s=220,
            marker="*",
            zorder=5,
            label="Optimo: LCOE {:.4f}".format(best["lcoe_cny_per_kwh"]),
        )

    axes.set_xlabel("Capacidad eolica (MW)")
    axes.set_ylabel("Capacidad de electrolisis (MW)")
    axes.set_title("Dominio factible WPEB")
    axes.grid(True, alpha=0.3)
    axes.legend()
    return figure


def plot_lcoe_heatmap(results: pd.DataFrame) -> Optional[plt.Figure]:
    """Mapa de LCOE sobre el dominio factible. None si no hay puntos factibles."""
    feasible = results[results["feasible"]]
    if len(feasible) == 0:
        return None

    pivot = feasible.pivot_table(
        index="electrolyzer_mw", columns="wind_mw", values="lcoe_cny_per_kwh"
    )

    figure, axes = plt.subplots(figsize=(11, 7))
    image = axes.imshow(pivot.to_numpy(), aspect="auto", origin="lower")

    axes.set_xticks(range(len(pivot.columns)))
    axes.set_xticklabels(["{:.0f}".format(c) for c in pivot.columns], rotation=90)
    axes.set_yticks(range(len(pivot.index)))
    axes.set_yticklabels(["{:.0f}".format(r) for r in pivot.index])

    axes.set_xlabel("Capacidad eolica (MW)")
    axes.set_ylabel("Capacidad de electrolisis (MW)")
    axes.set_title("LCOE sobre el dominio factible")
    figure.colorbar(image, ax=axes, label="LCOE (CNY/kWh)")
    return figure


def plot_convergence(history: pd.DataFrame, algorithm: str = "") -> plt.Figure:
    """Curva de convergencia de una o varias corridas.

    Si el historial trae una columna ``seed``, dibuja una linea por semilla:
    una sola trayectoria dice poco sobre una metaheuristica estocastica.
    """
    figure, axes = plt.subplots(figsize=(9, 5))

    if "seed" in history.columns:
        for seed, run in history.groupby("seed"):
            axes.plot(
                run["iteration"], run["best_score"], marker="o", markersize=3,
                alpha=0.75, label="semilla {}".format(seed),
            )
        axes.legend(fontsize=8)
    else:
        axes.plot(history["iteration"], history["best_score"], marker="o", markersize=4)

    title = "Convergencia"
    if algorithm:
        title += " - {}".format(algorithm.upper())
    axes.set_title(title)
    axes.set_xlabel("Iteracion")
    axes.set_ylabel("Mejor LCOE penalizado (CNY/kWh)")
    axes.grid(True, alpha=0.3)
    return figure
