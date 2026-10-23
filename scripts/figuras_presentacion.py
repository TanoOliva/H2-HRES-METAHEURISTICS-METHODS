"""Figuras especificas de la presentacion, generadas desde notebooks/results/*.csv.

Las figuras de la tesis se extraen del cuaderno; estas se dibujan aparte porque la
diapositiva necesita un recorte distinto (un panel por pregunta, fuentes grandes) y
porque la defensa se centra en un hibrido, PSO+GA, frente a sus padres y a la linea base.

Uso:
    python scripts/figuras_presentacion.py [--salida presentacion/figuras]
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

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "notebooks" / "results"

ORDER = ("gwo", "pso", "ga", "sho", "woa", "ga_ls", "pso_ga", "sho_ls", "random")
LABELS = {"gwo": "GWO", "pso": "PSO", "ga": "GA", "sho": "SHO", "woa": "WOA",
          "ga_ls": "GA+LS", "pso_ga": "PSO+GA", "sho_ls": "SHO+LS", "random": "RANDOM"}
COLORS = {"gwo": "#2a78d6", "pso": "#eb6834", "ga": "#1baf7a", "sho": "#eda100", "woa": "#e87ba4",
          "ga_ls": "#0d7a52", "pso_ga": "#a8431a", "sho_ls": "#a86f00", "random": "#898781"}
HYBRID_PAIRS = (("ga_ls", "ga"), ("pso_ga", "pso"), ("pso_ga", "ga"), ("sho_ls", "sho"))
MARKERS = ("o", "s", "^", "D")
# Protagonista de la defensa y sus comparadores: bucle base, donante de operadores,
# mejor clasico por rango medio y linea base.
FOCO = ("pso_ga", "pso", "ga", "sho", "random")

plt.rcParams.update({
    "figure.dpi": 200, "savefig.dpi": 200, "font.size": 11, "axes.grid": True,
    "grid.alpha": 0.25, "axes.spines.top": False, "axes.spines.right": False,
    "font.family": "DejaVu Sans",
})


def read(name: str) -> pd.DataFrame:
    return pd.read_csv(RESULTS / name)


def truthy(s: pd.Series) -> pd.Series:
    return s.astype(str).str.lower().isin(("true", "1", "1.0"))


def fig_exito(summary: pd.DataFrame, instances: list[str], salida: Path, algs=ORDER, nombre="pres_exito.png") -> None:
    """Tasa de exito al 0,5 % del optimo exacto: barras por algoritmo, un color por instancia."""
    fig, ax = plt.subplots(figsize=(10, 4.6))
    n_inst = len(instances)
    width = 0.8 / n_inst
    tonos = ["#3C4975", "#497DB5", "#57B6D0", "#1BAF7A"]
    for k, inst in enumerate(instances):
        sub = summary[summary["instance"] == inst].set_index("algorithm")
        valores = [100 * sub.loc[a, "success_0.5pct"] if a in sub.index else 0 for a in algs]
        xs = np.arange(len(algs)) + (k - (n_inst - 1) / 2) * width
        ax.bar(xs, valores, width=width * 0.95, color=tonos[k % len(tonos)], label=inst)
    ax.set_xticks(range(len(algs)), [LABELS[a] for a in algs], rotation=20 if len(algs) > 5 else 0)
    ax.set_ylabel("Corridas a menos de 0,5 % del óptimo [%]")
    ax.set_ylim(0, 100)
    ax.legend(title="Instancia", ncol=4, loc="upper right", fontsize=9)
    ax.set_title("¿Con qué frecuencia una corrida queda a menos de 0,5 % del óptimo exacto?", fontsize=12)
    plt.tight_layout()
    fig.savefig(salida / nombre)
    plt.close(fig)


def _a12_panel(ax, filas: pd.DataFrame, etiquetas, clave_x, color_de, instances):
    despl = np.linspace(-0.27, 0.27, len(instances))
    for k, inst in enumerate(instances):
        sub = filas[filas["instance"] == inst]
        for _, fila in sub.iterrows():
            if not np.isfinite(fila["a12"]):
                continue
            x = etiquetas.index(clave_x(fila)) + despl[k]
            color = color_de(fila)
            lleno = truthy(pd.Series([fila["significativo_alpha_0.05"]])).iloc[0]
            ax.errorbar([x], [fila["a12"]],
                        yerr=[[fila["a12"] - fila["a12_ci_low"]], [fila["a12_ci_high"] - fila["a12"]]],
                        fmt="none", ecolor=color, elinewidth=1.2, capsize=3)
            ax.scatter([x], [fila["a12"]], marker=MARKERS[k], s=70,
                       facecolor=color if lleno else "white", edgecolor=color, linewidths=1.5, zorder=3)
    ax.axhline(0.5, color="#555555", lw=1, linestyle="--")
    ax.set_xticks(range(len(etiquetas)))
    ax.set_ylim(0, 1.0)


def _leyenda_instancias(fig, instances):
    handles = [Line2D([], [], marker=MARKERS[k], color="#333333", linestyle="", markerfacecolor="white",
                      markersize=8, label=inst) for k, inst in enumerate(instances)]
    handles.append(Line2D([], [], marker="o", color="#333333", linestyle="", markersize=8,
                          label="lleno: significativo (Holm)"))
    fig.legend(handles=handles, loc="lower center", ncol=5, fontsize=9, frameon=False, bbox_to_anchor=(0.5, 0.0))


def fig_vs_random(tests: pd.DataFrame, instances: list[str], salida: Path) -> None:
    planned = tests[(tests["family"] == "planned") & (tests["algoritmo_b"] == "random")]
    orden = [a for a in ORDER if a != "random"]
    fig, ax = plt.subplots(figsize=(10, 4.6))
    _a12_panel(ax, planned, orden, lambda f: f["algoritmo_a"], lambda f: COLORS[f["algoritmo_a"]], instances)
    ax.set_xticklabels([LABELS[a] for a in orden])
    ax.set_ylabel("A12 frente a RANDOM")
    ax.set_title("¿Le ganan a la búsqueda aleatoria? (> 0,5: gana la metaheurística)", fontsize=12)
    _leyenda_instancias(fig, instances)
    plt.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(salida / "pres_vs_random.png")
    plt.close(fig)


def fig_hibrido_vs_padre(tests: pd.DataFrame, instances: list[str], salida: Path) -> None:
    planned = tests[tests["family"] == "planned"]
    pares = list(HYBRID_PAIRS)
    filas = planned[[(a, b) in pares for a, b in zip(planned["algoritmo_a"], planned["algoritmo_b"])]]
    fig, ax = plt.subplots(figsize=(8, 4.6))
    _a12_panel(ax, filas, pares, lambda f: (f["algoritmo_a"], f["algoritmo_b"]),
               lambda f: COLORS[f["algoritmo_a"]], instances)
    ax.set_xticklabels(["{} vs {}".format(LABELS[h], LABELS[p]) for h, p in pares])
    ax.set_ylabel("A12 híbrido frente a padre")
    ax.set_title("¿Aporta la hibridación? (> 0,5: gana el híbrido)", fontsize=12)
    _leyenda_instancias(fig, instances)
    plt.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(salida / "pres_hibrido_vs_padre.png")
    plt.close(fig)


def fig_psoga_a12(tests: pd.DataFrame, instances: list[str], salida: Path) -> None:
    """PSO+GA frente a RANDOM, PSO y GA: los tres contrastes planificados que lo validan."""
    planned = tests[(tests["family"] == "planned") & (tests["algoritmo_a"] == "pso_ga")]
    pares = ["random", "ga", "pso"]
    filas = planned[planned["algoritmo_b"].isin(pares)]
    fig, ax = plt.subplots(figsize=(8, 4.6))
    _a12_panel(ax, filas, pares, lambda f: f["algoritmo_b"], lambda f: COLORS[f["algoritmo_b"]], instances)
    ax.set_xticklabels(["PSO+GA vs RANDOM\n(¿aprende?)", "PSO+GA vs GA\n(¿mejor que el donante?)",
                        "PSO+GA vs PSO\n(¿aporta la inyección?)"], fontsize=10)
    ax.set_ylabel("A12 de PSO+GA frente a ...")
    ax.set_title("Tres contrastes planificados por instancia (> 0,5: gana PSO+GA)", fontsize=12)
    _leyenda_instancias(fig, instances)
    plt.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(salida / "pres_psoga_a12.png")
    plt.close(fig)


def fig_convergencia_foco(history: pd.DataFrame, brute: pd.DataFrame, instances: list[str], salida: Path) -> None:
    """Mediana e IQR del mejor LCOE por solicitudes: PSO+GA y sus comparadores, un panel por instancia."""
    optimo = brute.set_index("instance")["optimum_lcoe_cny_per_kwh"]
    fig, axes = plt.subplots(2, 2, figsize=(11, 7.2), sharex=True)
    for ax, inst in zip(axes.ravel(), instances):
        sub = history[history["instance"] == inst]
        for a in FOCO:
            g = sub[sub["algorithm"] == a]
            if g.empty:
                continue
            res = g.groupby("n_evaluations")["best_score"].agg(
                med="median", q25=lambda s: s.quantile(0.25), q75=lambda s: s.quantile(0.75)).reset_index()
            lw = 2.6 if a == "pso_ga" else 1.5
            ax.plot(res["n_evaluations"], res["med"], color=COLORS[a], lw=lw, label=LABELS[a],
                    linestyle="--" if a == "random" else "-")
            ax.fill_between(res["n_evaluations"], res["q25"], res["q75"], color=COLORS[a], alpha=0.10, linewidth=0)
        ax.axhline(optimo[inst], color="#111111", lw=0.9, linestyle=":", label="Óptimo exacto")
        fact = sub.loc[sub["best_score"] < 1.0, "best_score"]
        if not fact.empty:
            ax.set_ylim(min(fact.min(), optimo[inst]) * 0.998, fact.quantile(0.98) * 1.015)
        ax.set_title("{} (óptimo {:.5f})".format(inst, optimo[inst]), fontsize=11)
    for ax in axes[1]:
        ax.set_xlabel("Solicitudes de objetivo acumuladas")
    for ax in axes[:, 0]:
        ax.set_ylabel("Mejor LCOE factible [CNY/kWh]")
    h, l = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=6, fontsize=9, frameon=False, bbox_to_anchor=(0.5, 0.0))
    fig.suptitle("Convergencia de PSO+GA frente a sus padres, el mejor clásico y RANDOM (mediana e IQR, 30 semillas)", fontsize=11.5)
    plt.tight_layout(rect=(0, 0.06, 1, 0.96))
    fig.savefig(salida / "pres_convergencia_foco.png")
    plt.close(fig)


def fig_distribucion_foco(runs: pd.DataFrame, brute: pd.DataFrame, instances: list[str], salida: Path) -> None:
    """Boxplots del LCOE final de PSO+GA y sus comparadores, un panel por instancia."""
    optimo = brute.set_index("instance")["optimum_lcoe_cny_per_kwh"]
    fig, axes = plt.subplots(2, 2, figsize=(11, 7.2))
    for ax, inst in zip(axes.ravel(), instances):
        sub = runs[runs["instance"] == inst]
        datos = [sub.loc[sub["algorithm"] == a, "score"].dropna().to_numpy() for a in FOCO]
        caja = ax.boxplot(datos, tick_labels=[LABELS[a] for a in FOCO], patch_artist=True,
                          medianprops={"color": "#222222", "lw": 1.6})
        for parche, a in zip(caja["boxes"], FOCO):
            parche.set_facecolor(COLORS[a])
            parche.set_alpha(0.75 if a == "pso_ga" else 0.5)
            parche.set_edgecolor("#444444")
        ax.axhline(optimo[inst], color="#111111", lw=0.9, linestyle=":")
        todos = pd.concat([pd.Series(d) for d in datos])
        if not todos.empty:
            ax.set_ylim(min(todos.min(), optimo[inst]) * 0.998, todos.quantile(0.97) * 1.01)
        ax.set_title("{} (óptimo {:.5f}, línea punteada)".format(inst, optimo[inst]), fontsize=11)
    for ax in axes[:, 0]:
        ax.set_ylabel("LCOE final [CNY/kWh]")
    fig.suptitle("Distribución del LCOE final en 30 corridas (eje recortado al percentil 97)", fontsize=11.5)
    plt.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(salida / "pres_distribucion_foco.png")
    plt.close(fig)


def fig_presupuesto(summary: pd.DataFrame, instances: list[str], salida: Path) -> None:
    """Solicitudes duplicadas y de busqueda local por algoritmo (media sobre instancias)."""
    medio = summary.groupby("algorithm")[["mean_duplicates", "mean_unique"]].mean()
    ls = summary.groupby("algorithm")["mean_ls_requests"].mean() if "mean_ls_requests" in summary.columns else None
    fig, ax = plt.subplots(figsize=(10, 4.6))
    xs = np.arange(len(ORDER))
    unicos = [medio.loc[a, "mean_unique"] for a in ORDER]
    dups = [medio.loc[a, "mean_duplicates"] for a in ORDER]
    ax.bar(xs, unicos, color=[COLORS[a] for a in ORDER], alpha=0.85, label="diseños únicos")
    ax.bar(xs, dups, bottom=unicos, color="#d9d9d9", edgecolor="#777777", label="solicitudes duplicadas")
    for x, u, d in zip(xs, unicos, dups):
        if d > 5:
            ax.text(x, u + d / 2, "{:.0f}".format(d), ha="center", va="center", fontsize=9, color="#333333")
    if ls is not None:
        for x, a in zip(xs, ORDER):
            v = ls.get(a, np.nan)
            if np.isfinite(v) and v > 0:
                ax.text(x, 612, "LS: {:.0f}".format(v), ha="center", va="bottom", fontsize=9, color="#a86f00")
    ax.set_xticks(xs, [LABELS[a] for a in ORDER], rotation=20)
    ax.set_ylabel("Solicitudes por corrida (media de 4 instancias)")
    ax.set_ylim(0, 680)
    ax.axhline(600, color="#555555", lw=0.8, linestyle=":")
    ax.legend(loc="lower right", fontsize=9)
    ax.set_title("Cómo se gasta el presupuesto de 600 solicitudes", fontsize=12)
    plt.tight_layout()
    fig.savefig(salida / "pres_presupuesto.png")
    plt.close(fig)


def fig_ranking(cross: pd.DataFrame, instances: list[str], salida: Path) -> None:
    """Mapa de rangos por instancia (1 = mejor)."""
    algs = list(cross["algorithm"])
    matriz = np.array([[cross.set_index("algorithm").loc[a, "rank_" + i] for i in instances] for a in algs], dtype=float)
    fig, ax = plt.subplots(figsize=(6.2, 4.8))
    ax.imshow(matriz, cmap="YlGnBu_r", vmin=1, vmax=len(algs))
    ax.set_xticks(range(len(instances)), instances)
    ax.set_yticks(range(len(algs)), [LABELS[a] for a in algs])
    ax.grid(False)
    for i in range(len(algs)):
        for j in range(len(instances)):
            v = matriz[i, j]
            ax.text(j, i, "{:.0f}".format(v), ha="center", va="center", fontsize=10,
                    color="white" if v <= 3 else "#222222")
    medios = cross.set_index("algorithm").loc[algs, "mean_rank"]
    for i, a in enumerate(algs):
        ax.text(len(instances) - 0.4, i, "  media {:.2f}".format(medios[a]), va="center", fontsize=9, color="#333333")
    ax.set_xlim(-0.5, len(instances) + 1.2)
    ax.set_title("Rango por mediana en cada instancia (1 = mejor)", fontsize=12)
    plt.tight_layout()
    fig.savefig(salida / "pres_ranking.png")
    plt.close(fig)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--salida", type=Path, default=ROOT / "presentacion" / "figuras")
    args = parser.parse_args(argv)
    args.salida.mkdir(parents=True, exist_ok=True)
    instances = list(read("instances.csv")["instance"])
    summary = read("algorithm_summary.csv")
    tests = read("pairwise_tests.csv")
    cross = read("cross_instance_ranking.csv")
    brute = read("brute_force_summary.csv")
    runs = read("algorithm_runs.csv")
    history = read("algorithm_history.csv")
    fig_exito(summary, instances, args.salida)
    fig_exito(summary, instances, args.salida, algs=FOCO, nombre="pres_exito_foco.png")
    fig_vs_random(tests, instances, args.salida)
    fig_hibrido_vs_padre(tests, instances, args.salida)
    fig_psoga_a12(tests, instances, args.salida)
    fig_convergencia_foco(history, brute, instances, args.salida)
    fig_distribucion_foco(runs, brute, instances, args.salida)
    fig_presupuesto(summary, instances, args.salida)
    fig_ranking(cross, instances, args.salida)
    for nombre in sorted(args.salida.glob("pres_*.png")):
        print(nombre)


if __name__ == "__main__":
    main()
