"""Estilo compartido de las figuras: paleta por algoritmo y ``rcParams``.

Antes de este modulo, ``plots.py`` no fijaba ningun tema: colores del ciclo por
defecto de matplotlib, sin orden garantizado entre figuras. Para un documento
de titulo eso se nota -- si "gwo" es azul en una figura y verde en la
siguiente, el lector pierde la referencia.

La paleta categorica se valido con el script de la skill ``dataviz``
(``validate_palette.js``, metodo OKLab/CVD de Arcuri) para las cuatro series
que van a aparecer juntas en boxplots y dispersion (contexto "todos los pares
visibles a la vez", el mas exigente). Solo los tres primeros colores del
catalogo de referencia superan esa validacion en conjunto -- el cuarto
(amarillo) queda demasiado cerca del naranja para deuteranopia. Por eso
``random`` no recibe un cuarto matiz categorico: es la linea base, no un
algoritmo competidor, asi que se codifica con un gris neutro y linea
discontinua (codificacion secundaria), que es ademas la convencion habitual
para una referencia en un grafico de convergencia.

Agregar un quinto algoritmo exige volver a correr el validador con la paleta
completa antes de asignarle un color.
"""

from __future__ import annotations

from typing import Dict, Tuple

import matplotlib.pyplot as plt

__all__ = [
    "ALGORITHM_ORDER",
    "ALGORITHM_COLORS",
    "ALGORITHM_LINESTYLES",
    "apply_style",
    "algorithm_color",
    "algorithm_linestyle",
]

# Orden fijo: los colores se asignan por identidad, nunca por rango dentro de
# una figura (si un filtro deja solo dos algoritmos, los sobrevivientes
# conservan su color).
ALGORITHM_ORDER: Tuple[str, ...] = ("gwo", "pso", "ga", "random")

ALGORITHM_COLORS: Dict[str, str] = {
    "gwo": "#2a78d6",      # azul -- valida CVD y contraste en el conjunto de 3
    "pso": "#eb6834",      # naranja
    "ga": "#1baf7a",       # verde-agua (relief: WARN de contraste, mitigado
                           # con etiquetas de leyenda visibles, nunca color solo)
    "random": "#898781",  # gris neutro -- linea base, no una serie categorica
}

ALGORITHM_LINESTYLES: Dict[str, str] = {
    "gwo": "-",
    "pso": "-",
    "ga": "-",
    "random": "--",
}

# Reserva para algoritmos futuros, sin validar en conjunto: usar solo tras
# volver a correr el validador con la paleta completa (ver docstring del modulo).
_FALLBACK_COLOR = "#4a3aa7"  # violeta, slot 7 del catalogo de referencia


def apply_style() -> None:
    """Aplica un ``rcParams`` compartido: tipografia, grilla recesiva, 300 dpi.

    Se llama al importar ``comparison_plots`` y desde ``plots.py``; volver a
    llamarla no tiene efecto adicional, es idempotente.
    """
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "sans-serif"],
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.titleweight": "bold",
            "axes.labelsize": 10,
            "axes.edgecolor": "#c3c2b7",
            "axes.linewidth": 0.8,
            "axes.grid": True,
            "grid.color": "#e1e0d9",
            "grid.linewidth": 0.6,
            "grid.alpha": 0.7,
            "legend.frameon": False,
            "legend.fontsize": 9,
            "xtick.color": "#52514e",
            "ytick.color": "#52514e",
            "figure.dpi": 100,
            "savefig.dpi": 300,
            "lines.linewidth": 1.8,
            "lines.markersize": 5,
        }
    )


def algorithm_color(name: str) -> str:
    """Color estable para un algoritmo. Ver el docstring del modulo."""
    return ALGORITHM_COLORS.get(name, _FALLBACK_COLOR)


def algorithm_linestyle(name: str) -> str:
    """Estilo de linea: discontinuo solo para la linea base ``random``."""
    return ALGORITHM_LINESTYLES.get(name, "-")
