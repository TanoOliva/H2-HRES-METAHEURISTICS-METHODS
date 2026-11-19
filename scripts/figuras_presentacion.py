"""Figuras de la presentacion de defensa, generadas desde notebooks/results/*.csv.

Las figuras de la tesis salen del cuaderno; estas se dibujan aparte porque la lamina
necesita otro recorte: ocho instancias a la vez, el hibrido PSO+GA frente a sus padres
y a la linea base, y texto que se lea proyectado. Cada figura se guarda al tamano en
pulgadas con que entra en la lamina (``TAMANOS``), de modo que los 11 pt del grafico
son 11 pt en la diapositiva.

Ningun veredicto va escrito en las figuras: solo datos, ejes y leyendas. Los conteos
(replicas, solicitudes, instancias) se leen de los CSV.

Uso:
    python scripts/figuras_presentacion.py [--resultados notebooks/results] [--salida presentacion/figuras]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import MaxNLocator

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "notebooks" / "results"

ORDER = ("gwo", "pso", "ga", "sho", "woa", "pso_ga", "random")
LABELS = {"gwo": "GWO", "pso": "PSO", "ga": "GA", "sho": "SHO", "woa": "WOA",
          "pso_ga": "PSO+GA", "random": "RANDOM"}
COLORS = {"gwo": "#2a78d6", "pso": "#eb6834", "ga": "#1baf7a", "sho": "#eda100", "woa": "#e87ba4",
          "pso_ga": "#a8431a", "random": "#898781"}
CONTROL, BASELINE = "pso_ga", "random"
# Protagonista de la defensa y sus contrastes confirmatorios: los dos padres y la linea base.
FOCO = ("pso_ga", "pso", "ga", "random")
TINTA, GRIS = "#33333d", "#555555"

# Tamano (ancho, alto) en pulgadas de cada figura dentro de la lamina de 10 x 5,625.
TAMANOS = {
    "pres_convergencia.png": (9.0, 3.1),
    "pres_brecha.png": (9.0, 2.75),
    "pres_a12_foco.png": (9.0, 2.6),
    "pres_a12_control_resto.png": (9.0, 2.6),
    "pres_a12_linea_base.png": (9.0, 2.6),
    "pres_diferencia_critica.png": (9.0, 2.3),
    "pres_duplicados.png": (5.3, 3.3),
}

plt.rcParams.update({
    "figure.dpi": 100, "savefig.dpi": 250, "font.size": 11, "font.family": "DejaVu Sans",
    "axes.titlesize": 11.5, "axes.labelsize": 11, "xtick.labelsize": 11, "ytick.labelsize": 11,
    "legend.fontsize": 11, "axes.grid": True, "grid.alpha": 0.25,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": GRIS, "axes.labelcolor": TINTA, "xtick.color": TINTA, "ytick.color": TINTA,
    "text.color": TINTA,
})


def coma(x, d=2) -> str:
    return f"{float(x):.{d}f}".replace(".", ",").replace("-", "−")


def truthy(v) -> bool:
    return str(v).strip().lower() in ("true", "1", "1.0")


def guardar(fig, salida: Path, nombre: str) -> None:
    fig.set_size_inches(*TAMANOS[nombre])
    fig.savefig(salida / nombre)
    plt.close(fig)


def con_brecha(tabla: pd.DataFrame, brute: pd.DataFrame, columna: str) -> pd.DataFrame:
    """Anade ``gap``: brecha relativa al optimo exacto de la instancia, en porcentaje."""
    optimo = brute.set_index("instance")["optimum_lcoe_cny_per_kwh"]
    tabla = tabla.copy()
    tabla["gap"] = (tabla[columna] / tabla["instance"].map(optimo) - 1.0) * 100.0
    return tabla


# --------------------------------------------------------------------------- explorar
def fig_convergencia(history: pd.DataFrame, brute: pd.DataFrame, instances: list[str], salida: Path) -> None:
    """Mediana e IQR de la brecha al optimo frente a las solicitudes, un panel por instancia."""
    nombre = "pres_convergencia.png"
    h = con_brecha(history[history["algorithm"].isin(FOCO)], brute, "best_score")
    h["gap"] = h["gap"].fillna(np.inf)            # sin diseno factible todavia
    presupuesto = int(h["n_evaluations"].max())
    ncols = 4
    nrows = int(np.ceil(len(instances) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=TAMANOS[nombre], sharex=True, sharey=True, squeeze=False)
    resumen, techo, piso = {}, [], [0.0]
    for inst in instances:
        for a in FOCO:
            g = h[(h["instance"] == inst) & (h["algorithm"] == a)]
            if g.empty:
                continue
            res = g.groupby("n_evaluations")["gap"].quantile([0.25, 0.5, 0.75]).unstack()
            resumen[(inst, a)] = res
            temprano = res.loc[res.index >= 0.15 * presupuesto, 0.5]
            if len(temprano) and np.isfinite(temprano.iloc[0]):
                techo.append(float(temprano.iloc[0]))
            if np.isfinite(res[0.25].iloc[-1]):
                piso.append(float(res[0.25].iloc[-1]))
    ymax = (max(techo) if techo else 5.0) * 1.12
    ymin = min(piso) - 0.04 * ymax
    for ax, inst in zip(axes.ravel(), instances):
        for a in FOCO:
            res = resumen.get((inst, a))
            if res is None:
                continue
            recorte = res.clip(upper=ymax * 3)
            ax.fill_between(res.index, recorte[0.25], recorte[0.75], color=COLORS[a], alpha=0.13, linewidth=0)
            ax.plot(res.index, recorte[0.5], color=COLORS[a], lw=2.6 if a == CONTROL else 1.6,
                    linestyle="--" if a == BASELINE else "-", zorder=3 if a == CONTROL else 2)
        ax.axhline(0.0, color="#111111", lw=0.9, linestyle=":")
        ax.text(0.96, 0.9, inst, transform=ax.transAxes, ha="right", va="top", fontsize=11.5, fontweight="bold")
        ax.set_ylim(ymin, ymax)
        ax.set_xlim(0, presupuesto)
        ax.set_xticks([0, presupuesto // 2, presupuesto])
        for etiqueta, alineacion in zip(ax.get_xticklabels(), ("left", "center", "right")):
            etiqueta.set_horizontalalignment(alineacion)   # evita que 600 y 0 se pisen entre paneles
        ax.yaxis.set_major_locator(MaxNLocator(4))
    for ax in axes.ravel()[len(instances):]:
        ax.axis("off")
    handles = [Line2D([], [], color=COLORS[a], lw=2.6 if a == CONTROL else 1.6,
                      linestyle="--" if a == BASELINE else "-", label=LABELS[a]) for a in FOCO]
    handles.append(Line2D([], [], color="#111111", lw=0.9, linestyle=":", label="óptimo exacto"))
    fig.legend(handles=handles, loc="upper center", ncol=len(handles), frameon=False,
               bbox_to_anchor=(0.5, 1.0), columnspacing=1.6, handlelength=1.8)
    fig.supxlabel("Solicitudes de evaluación acumuladas", fontsize=11, y=0.005)
    fig.supylabel("Brecha al óptimo [%]", fontsize=11, x=0.004)
    fig.subplots_adjust(left=0.075, right=0.99, top=0.885, bottom=0.185, wspace=0.08, hspace=0.16)
    guardar(fig, salida, nombre)


def fig_brecha(runs: pd.DataFrame, brute: pd.DataFrame, instances: list[str], salida: Path) -> None:
    """Distribucion de la brecha final al optimo: cuatro cajas por instancia, con las corridas encima."""
    nombre = "pres_brecha.png"
    r = con_brecha(runs[runs["algorithm"].isin(FOCO)], brute, "score")
    r = r[np.isfinite(r["gap"])]
    fig, ax = plt.subplots(figsize=TAMANOS[nombre])
    ancho = 0.19
    despl = (np.arange(len(FOCO)) - (len(FOCO) - 1) / 2) * ancho
    techo = float(r["gap"].quantile(0.97)) * 1.1 if len(r) else 5.0
    rng = np.random.default_rng(7)
    recortadas = 0
    for k, a in enumerate(FOCO):
        datos, pos = [], []
        for i, inst in enumerate(instances):
            v = r.loc[(r["instance"] == inst) & (r["algorithm"] == a), "gap"].to_numpy()
            if len(v) == 0:
                continue
            datos.append(v)
            pos.append(i + despl[k])
            recortadas += int((v > techo).sum())
            ax.scatter(i + despl[k] + rng.uniform(-ancho * 0.28, ancho * 0.28, len(v)), np.minimum(v, techo),
                       s=7, color=COLORS[a], alpha=0.45, linewidths=0, zorder=3)
        if not datos:
            continue
        caja = ax.boxplot(datos, positions=pos, widths=ancho * 0.86, patch_artist=True, showfliers=False,
                          medianprops={"color": "#111111", "lw": 1.5}, whiskerprops={"color": GRIS, "lw": 0.9},
                          capprops={"color": GRIS, "lw": 0.9}, manage_ticks=False)
        for parche in caja["boxes"]:
            parche.set_facecolor(COLORS[a])
            parche.set_alpha(0.85 if a == CONTROL else 0.55)
            parche.set_edgecolor(GRIS)
            parche.set_linewidth(0.8)
    ax.axhline(0.0, color="#111111", lw=0.9, linestyle=":")
    for i in range(1, len(instances)):
        ax.axvline(i - 0.5, color="#dddddd", lw=0.8, zorder=0)
    ax.set_xticks(range(len(instances)), instances)
    ax.set_xlim(-0.5, len(instances) - 0.5)
    piso = min(0.0, float(r["gap"].min()) if len(r) else 0.0)
    ax.set_ylim(piso - 0.04 * techo, techo)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Brecha al óptimo [%]")
    if recortadas:
        ax.text(0.012, 0.975, "eje recortado: {} corridas quedan por encima".format(recortadas), transform=ax.transAxes,
                ha="left", va="top", fontsize=11, color=GRIS, style="italic",
                bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.8, "pad": 1.5})
    handles = [Patch(facecolor=COLORS[a], edgecolor=GRIS, alpha=0.85 if a == CONTROL else 0.55, label=LABELS[a])
               for a in FOCO]
    handles.append(Line2D([], [], color="#111111", lw=0.9, linestyle=":", label="óptimo exacto"))
    fig.legend(handles=handles, loc="upper center", ncol=len(handles), frameon=False,
               bbox_to_anchor=(0.5, 1.0), columnspacing=1.6, handlelength=1.6)
    fig.subplots_adjust(left=0.075, right=0.99, top=0.87, bottom=0.11)
    guardar(fig, salida, nombre)


# --------------------------------------------------------------------------- P1
def fig_a12(tests: pd.DataFrame, pares: list[tuple[str, str]], instances: list[str], salida: Path,
            nombre: str, foco: str = "b") -> None:
    """A12 por instancia con IC al 95 %, un panel por par (a frente a b).

    Marcador lleno: significativo tras Holm. Banda gris: efecto despreciable (0,44 a 0,56).
    ``foco`` indica que algoritmo del par cambia entre paneles y da color y titulo al panel.
    """
    fig, axes = plt.subplots(1, len(pares), figsize=TAMANOS[nombre], sharex=True, sharey=True, squeeze=False)
    posiciones = np.arange(len(instances))[::-1]
    for ax, (a, b) in zip(axes.ravel(), pares):
        sub = tests[(tests["algoritmo_a"] == a) & (tests["algoritmo_b"] == b)].drop_duplicates("instance") \
            .set_index("instance").reindex(instances)
        color = COLORS[b if foco == "b" else a]
        ax.axvspan(0.44, 0.56, color="#e9e7e1", zorder=0)
        ax.axvline(0.5, color=GRIS, lw=1.0, linestyle="--", zorder=1)
        for y, (_, fila) in zip(posiciones, sub.iterrows()):
            if not np.isfinite(fila.get("a12", np.nan)):
                continue
            ax.plot([fila["a12_ci_low"], fila["a12_ci_high"]], [y, y], color=color, lw=1.8, zorder=2,
                    solid_capstyle="butt")
            ax.scatter([fila["a12"]], [y], s=62, zorder=3, edgecolor=color, linewidths=1.7, clip_on=False,
                       facecolor=color if truthy(fila["significativo"]) else "white")
        # Con mas de tres paneles el titulo completo no cabe: el rival comun pasa al pie de la figura.
        nombre_panel = "{} frente a {}".format(LABELS[a], LABELS[b]) if len(pares) <= 3 else LABELS[b if foco == "b" else a]
        ax.set_title(nombre_panel, fontsize=11.5, color=color, fontweight="bold", pad=5)
        ax.set_xlim(-0.03, 1.03)
        ax.set_xticks([0, 0.5, 1] if len(pares) > 3 else [0, 0.25, 0.5, 0.75, 1])
        ax.set_xticklabels(["0", "0,5", "1"] if len(pares) > 3 else ["0", "0,25", "0,5", "0,75", "1"])
        ax.set_yticks(posiciones, instances)
        ax.set_ylim(-0.7, len(instances) - 0.3)
        ax.grid(axis="y", visible=False)
        ax.tick_params(axis="y", length=0)
    if foco == "b":
        pie = r"$\hat{A}_{12}$ con IC bootstrap al 95 %" + "  ·  a la derecha de 0,5: {} obtiene menor LCOE".format(LABELS[pares[0][0]])
    else:
        pie = r"$\hat{A}_{12}$" + " frente a {}, IC al 95 %  ·  a la derecha de 0,5: la metaheurística obtiene menor LCOE".format(LABELS[pares[0][1]])
    fig.supxlabel(pie, fontsize=11, y=0.005)
    fig.subplots_adjust(left=0.05, right=0.99, top=0.89, bottom=0.225, wspace=0.07)
    guardar(fig, salida, nombre)


# --------------------------------------------------------------------------- P3
def grupos_cd(rangos: np.ndarray, cd: float) -> list[tuple[int, int]]:
    """Grupos maximales de algoritmos consecutivos cuyo rango medio difiere menos que la diferencia critica."""
    grupos, n = [], len(rangos)
    for inicio in range(n):
        fin = inicio
        while fin + 1 < n and rangos[fin + 1] - rangos[inicio] <= cd:
            fin += 1
        if fin > inicio and not any(s <= inicio and fin <= e for s, e in grupos):
            grupos.append((inicio, fin))
    return grupos


def fig_diferencia_critica(ranks: pd.DataFrame, friedman: pd.Series, salida: Path) -> None:
    """Diagrama de diferencia critica (Nemenyi) sobre los rangos medios por instancia."""
    nombre = "pres_diferencia_critica.png"
    ranks = ranks.sort_values("mean_rank").reset_index(drop=True)
    k = len(ranks)
    cd = float(friedman["critical_difference"])
    valores = ranks["mean_rank"].to_numpy()
    fig, ax = plt.subplots(figsize=TAMANOS[nombre])
    ax.hlines(0, 1, k, color="#222222", lw=1.3)
    for marca in range(1, k + 1):
        ax.vlines(marca, -0.07, 0.07, color="#222222", lw=1.3)
        ax.text(marca, 0.13, str(marca), ha="center", va="bottom", fontsize=11)
    ax.text(1, 0.43, "mejor", ha="center", va="bottom", fontsize=11, color=GRIS, style="italic")
    ax.text(k, 0.43, "peor", ha="center", va="bottom", fontsize=11, color=GRIS, style="italic")
    # Regla de la diferencia critica, centrada sobre el eje.
    x0 = (1 + k) / 2 - min(cd, k - 1) / 2
    ax.hlines(0.62, x0, x0 + min(cd, k - 1), color="#8a1c1c", lw=2.6)
    ax.vlines([x0, x0 + min(cd, k - 1)], 0.56, 0.68, color="#8a1c1c", lw=1.6)
    ax.text((1 + k) / 2, 0.72, "diferencia crítica (Nemenyi) = {}".format(coma(cd, 2)), ha="center", va="bottom",
            fontsize=11, color="#8a1c1c")
    mitad = int(np.ceil(k / 2))
    paso = 0.27
    for i, fila in ranks.iterrows():
        izquierda = i < mitad
        profundidad = (i if izquierda else k - 1 - i) + 1
        y = -0.42 - paso * profundidad
        x_texto = 0.55 if izquierda else k + 0.45
        color = COLORS.get(fila["algorithm"], "#444444")
        ax.plot([fila["mean_rank"], fila["mean_rank"], x_texto], [0, y, y], color=color, lw=1.5)
        ax.text(x_texto - 0.06 if izquierda else x_texto + 0.06, y,
                "{} ({})".format(LABELS.get(fila["algorithm"], fila["algorithm"]), coma(fila["mean_rank"], 2)),
                ha="right" if izquierda else "left", va="center", fontsize=11.5, color=color, fontweight="bold")
    for nivel, (inicio, fin) in enumerate(grupos_cd(valores, cd)):
        y = -0.15 - 0.1 * nivel
        ax.hlines(y, valores[inicio] - 0.04, valores[fin] + 0.04, color="#222222", lw=3.4)
    ax.set_xlim(1 - 2.3, k + 2.3)
    ax.set_ylim(-0.42 - paso * (mitad + 0.55), 1.02)
    ax.axis("off")
    fig.subplots_adjust(left=0.0, right=1.0, top=1.0, bottom=0.0)
    guardar(fig, salida, nombre)


# --------------------------------------------------------------------------- lectura
def fig_duplicados(summary: pd.DataFrame, salida: Path) -> None:
    """Porcentaje de las solicitudes que repite un diseno ya evaluado: media y rango entre instancias."""
    nombre = "pres_duplicados.png"
    s = summary[summary["algorithm"].isin(ORDER)].copy()
    s["share"] = 100.0 * s["mean_duplicates"] / (s["mean_duplicates"] + s["mean_unique"])
    res = s.groupby("algorithm")["share"].agg(["mean", "min", "max"]).reindex([a for a in ORDER if a in set(s["algorithm"])])
    res = res.sort_values("mean")
    fig, ax = plt.subplots(figsize=TAMANOS[nombre])
    ys = np.arange(len(res))
    ax.barh(ys, res["mean"], color=[COLORS[a] for a in res.index], alpha=0.9, height=0.62)
    ax.errorbar(res["mean"], ys, xerr=[res["mean"] - res["min"], res["max"] - res["mean"]], fmt="none",
                ecolor="#333333", elinewidth=1.2, capsize=3)
    tope = max(float(res["max"].max()), 1.0)
    for y, (_, fila) in zip(ys, res.iterrows()):
        ax.text(fila["max"] + tope * 0.03, y, coma(fila["mean"], 1) + " %", va="center", ha="left", fontsize=11)
    ax.set_yticks(ys, [LABELS[a] for a in res.index])
    for etiqueta, a in zip(ax.get_yticklabels(), res.index):
        if a == CONTROL:
            etiqueta.set_fontweight("bold")
    ax.set_xlim(0, tope * 1.28)
    ax.xaxis.set_major_locator(MaxNLocator(5))
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("Solicitudes duplicadas [% del presupuesto]\nmedia y rango entre instancias")
    fig.subplots_adjust(left=0.2, right=0.98, top=0.98, bottom=0.2)
    guardar(fig, salida, nombre)


# --------------------------------------------------------------------------- principal
def main(argv=None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resultados", type=Path, default=RESULTS)
    parser.add_argument("--salida", type=Path, default=ROOT / "presentacion" / "figuras")
    args = parser.parse_args(argv)
    args.salida.mkdir(parents=True, exist_ok=True)

    def read(name: str) -> pd.DataFrame:
        return pd.read_csv(args.resultados / name)

    instances = list(read("instances.csv")["instance"])
    brute = read("brute_force_summary.csv")
    instances = [i for i in instances if i in set(brute["instance"])]
    summary = read("algorithm_summary.csv")
    runs = read("algorithm_runs.csv")
    history = read("algorithm_history.csv")
    tests = read("stat_per_instance.csv")
    ranks = read("stat_ranks.csv")
    friedman = read("stat_friedman.csv").iloc[0]

    fig_convergencia(history, brute, instances, args.salida)
    fig_brecha(runs, brute, instances, args.salida)
    control = tests[tests["family"] == "control"]
    base = tests[tests["family"] == "linea_base"]
    fig_a12(control, [(CONTROL, b) for b in ("pso", "ga", "random")], instances, args.salida, "pres_a12_foco.png")
    fig_a12(control, [(CONTROL, b) for b in ("gwo", "sho", "woa")], instances, args.salida, "pres_a12_control_resto.png")
    fig_a12(base, [(a, BASELINE) for a in ("gwo", "pso", "ga", "sho", "woa")], instances, args.salida,
            "pres_a12_linea_base.png", foco="a")
    fig_diferencia_critica(ranks, friedman, args.salida)
    fig_duplicados(summary, args.salida)

    # Las figuras pres_* de versiones anteriores del guion ya no se usan: se retiran.
    for viejo in sorted(args.salida.glob("pres_*.png")):
        if viejo.name not in TAMANOS:
            viejo.unlink()
            print("eliminada", viejo.name)
    replicas = sorted(set(runs.groupby(["instance", "algorithm"]).size()))
    print("datos: {} instancias, réplicas por celda {}, hasta {} solicitudes".format(
        len(instances), replicas, int(runs["n_evaluations"].max())))
    for nombre in TAMANOS:
        print(args.salida / nombre)


if __name__ == "__main__":
    main()
