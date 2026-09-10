"""Estilo compartido de las figuras: paleta por algoritmo y ``rcParams``.

Antes de este modulo, ``plots.py`` no fijaba ningun tema: colores del ciclo por
defecto de matplotlib, sin orden garantizado entre figuras. Para un documento
de titulo eso se nota -- si "gwo" es azul en una figura y verde en la
siguiente, el lector pierde la referencia.

La paleta categorica se valido con el script de la skill ``dataviz``
(``validate_palette.js``, metodo OKLab/CVD de Arcuri), y el resultado depende
del tipo de grafico:

- **Lineas y barras** (``convergencia_por_algoritmo.png``, un grafico de
  lineas; ``distribucion_scores.png``, un boxplot -- cajas en un orden
  categorico fijo, se leen por adyacencia) se validan con la lista de pares
  *adyacentes*: los 5 matices categoricos que usan gwo/pso/ga/sho/woa pasan
  todos los umbrales en claro y oscuro.
- **Dispersion** (``calidad_vs_tiempo.png``) es el contexto "todos los pares
  visibles a la vez", el mas exigente: con los mismos 5 colores, el piso de
  vision normal falla (ΔE 12.9 entre magenta y naranja, bajo el minimo de 15).
  Por eso ahi la identidad no depende solo del color: cada algoritmo tiene
  ademas una forma de marcador propia (``ALGORITHM_MARKERS``), que es la
  codificacion primaria en ese grafico.

``random`` no recibe un matiz categorico en ningun caso: es la linea base, no
un algoritmo competidor, asi que se codifica con un gris neutro, linea
discontinua y una "x" como marcador -- la convencion habitual para una
referencia.

Agregar un septimo algoritmo exige volver a correr el validador (adyacente
para lineas/barras, todos-los-pares para dispersion) antes de asignarle color.
"""

from __future__ import annotations

from typing import Dict, Tuple

import matplotlib.pyplot as plt

__all__ = [
    "ALGORITHM_ORDER",
    "ALGORITHM_COLORS",
    "ALGORITHM_LINESTYLES",
    "ALGORITHM_MARKERS",
    "apply_style",
    "algorithm_color",
    "algorithm_linestyle",
    "algorithm_marker",
]

# Orden fijo: los colores se asignan por identidad, nunca por rango dentro de
# una figura (si un filtro deja solo dos algoritmos, los sobrevivientes
# conservan su color).
ALGORITHM_ORDER: Tuple[str, ...] = ("gwo", "pso", "ga", "sho", "woa", "random")

ALGORITHM_COLORS: Dict[str, str] = {
    "gwo": "#2a78d6",      # azul
    "pso": "#eb6834",      # naranja
    "ga": "#1baf7a",       # verde-agua (relief: WARN de contraste, mitigado
                           # con etiquetas de leyenda visibles, nunca color solo)
    "sho": "#eda100",      # amarillo (mismo relief que ga)
    "woa": "#e87ba4",      # magenta (mismo relief que ga)
    "random": "#898781",  # gris neutro -- linea base, no una serie categorica
}

ALGORITHM_LINESTYLES: Dict[str, str] = {
    "gwo": "-",
    "pso": "-",
    "ga": "-",
    "sho": "-",
    "woa": "-",
    "random": "--",
}

# Marcadores de matplotlib: la codificacion primaria de identidad en
# graficos de dispersion, donde el color solo no alcanza para 5 series (ver
# docstring del modulo). "x" para random subraya que es la linea base.
ALGORITHM_MARKERS: Dict[str, str] = {
    "gwo": "o",
    "pso": "s",
    "ga": "^",
    "sho": "D",
    "woa": "*",
    "random": "x",
}

# Reserva para algoritmos futuros, sin validar en conjunto: usar solo tras
# volver a correr el validador con la paleta completa (ver docstring del modulo).
_FALLBACK_COLOR = "#4a3aa7"  # violeta, slot 7 del catalogo de referencia
_FALLBACK_MARKER = "P"


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


def algorithm_marker(name: str) -> str:
    """Forma de marcador estable: la codificacion primaria en dispersion."""
    return ALGORITHM_MARKERS.get(name, _FALLBACK_MARKER)
