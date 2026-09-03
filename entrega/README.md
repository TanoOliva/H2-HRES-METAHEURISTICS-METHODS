# Comparativa de metaheuristicas sobre el sistema WPEB

Extension discreta de Li et al. (2024), *Capacity optimization of a wind-photovoltaic-electrolysis-battery (WPEB) hybrid energy system for power and hydrogen generation*, resuelta con cuatro metaheuristicas y contrastada con un estudio de sensibilidad sobre las dos restricciones que fijan el dominio factible del paper.

**Estado de la replicacion del paper** (9 de 10 objetivos publicados dentro de tolerancia): ver `tablas/validacion_paper.csv` y `CHANGELOG.md` en la raiz del repositorio para el detalle de cada correccion de modelado y su efecto medido.

| metrica | paper | replicacion | desvio_pct | veredicto |
| --- | --- | --- | --- | --- |
| CF parque eolico | 0.4000 | 0.3958 | -1.0496 | OK |
| CF parque fotovoltaico | 0.1900 | 0.1874 | -1.3422 | OK |
| CF electrolizador (W190-P10-E95) | 0.6240 | 0.5889 | -5.6309 | OK |
| LCOE W190-P10-E95-B30 | 0.2692 | 0.2624 | -2.5310 | OK |
| LCOE W120-P80-E80-B25 | 0.2886 | 0.2848 | -1.3276 | OK |
| LCOE W60-P140-E85-B27.5 | 0.3617 | 0.3530 | -2.3927 | OK |
| NPC W190-P10-E95-B30 | 2675.7300 | 2664.9764 | -0.4019 | OK |
| NPC W120-P80-E80-B25 | 2350.3800 | 2346.8707 | -0.1493 | OK |
| NPC W60-P140-E85-B27.5 | 2114.5300 | 2320.1710 | 9.7251 | REVISAR |
| CAPEX sobre NPC (W190) | 0.7330 | 0.7209 | -1.6499 | OK |

## Metodologia

- **Modelo**: simulacion horaria (8760-8784 h, ano 2008) del despacho WPEB descrito en `src/h2_hres/simulation/`.
- **Espacio de decision** (4 variables, `optimization/encoding.py`): capacidad eolica continua (PV = 200 - eolica), unidades de electrolizador enteras (5 MW cada una), potencia de bateria en multiplos de 5 MW, duracion de bateria discreta {1, 2, 4} h.
- **Objetivo**: LCOE, igual que el paper. Una solucion infactible (AGSR > 20%) recibe una penalizacion proporcional a cuanto la viola, para que el optimizador tenga gradiente hacia la region factible en vez de un muro.
- **Presupuesto**: 600 evaluaciones por corrida (20 individuos x 30 iteraciones), identico para los cuatro algoritmos -- es la condicion para que la comparacion sea justa, y los tests del paquete la verifican automaticamente para cualquier algoritmo nuevo que se registre.
- **Reproducibilidad**: 30 semillas consecutivas por algoritmo, compartiendo un unico cache de perfiles de generacion (mismo dato meteorologico, mismo modelo, para los cuatro).

## Que se comparo

| Algoritmo | Familia | Hiperparametros | Fuente |
|---|---|---|---|
| GWO | Enjambre jerarquico | jerarquia alpha-beta-delta, `a` decae 2->0 | Mirjalili et al. (2014) |
| PSO | Enjambre | constriccion Clerc-Kennedy: chi=0.729, c1=c2=1.49445 | Clerc & Kennedy (2002) |
| GA | Evolutivo | torneo k=3, BLX-alpha, mutacion gaussiana sigma=10% del rango, elite=2 | estandar real-coded GA |
| random | Linea base | muestreo uniforme sobre la malla discreta | -- |

Los hiperparametros de PSO y GA son los valores canonicos de la literatura, no un ajuste fino a este problema: la comparativa no debe leerse como un torneo con un favorito afinado. Ver `configs/metaheuristicas.yaml` para el escenario completo.

## Resultados

Ranking por mejor score alcanzado (menor LCOE penalizado es mejor), sobre 30 semillas por algoritmo:

| ranking | algorithm | runs | best | mean | std | worst | feasible_runs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ga | 30 | 0.2810 | 0.2839 | 0.0020 | 0.2882 | 30 |
| 2 | pso | 30 | 0.2810 | 0.2832 | 0.0014 | 0.2876 | 30 |
| 3 | gwo | 30 | 0.2810 | 0.2831 | 0.0016 | 0.2880 | 30 |
| 4 | random | 30 | 0.2815 | 0.2854 | 0.0026 | 0.2919 | 30 |

**GA** obtuvo el mejor score (0.281003); **RANDOM** el peor (0.281502). Ver `figuras/convergencia_por_algoritmo.png` (mediana y rango intercuartil de convergencia) y `figuras/distribucion_scores.png` (dispersion de resultados finales).

**Significancia estadistica** (Wilcoxon pareado por semilla, corregido por Holm-Bonferroni sobre los 6 pares; A12 es el tamano del efecto de Vargha-Delaney -- 0.5 = indistinguibles, 1.0 = el primero domina siempre):

| algoritmo_a | algoritmo_b | mediana_a | mediana_b | p_value_holm | a12 | significativo_alpha_0.05 |
| --- | --- | --- | --- | --- | --- | --- |
| ga | gwo | 0.2837 | 0.2830 | 0.1173 | 0.4067 | no |
| ga | pso | 0.2837 | 0.2838 | 0.1173 | 0.3989 | no |
| ga | random | 0.2837 | 0.2848 | 0.1173 | 0.6767 | no |
| gwo | pso | 0.2830 | 0.2838 | 0.7611 | 0.4989 | no |
| gwo | random | 0.2830 | 0.2848 | 0.0023 | 0.7844 | si |
| pso | random | 0.2838 | 0.2848 | 0.0033 | 0.7567 | si |

2 de 6 pares muestran una diferencia significativa a alpha=0.05 tras la correccion. Ver `figuras/calidad_vs_tiempo.png` para el trade-off entre calidad alcanzada y tiempo de computo por corrida.

## Sensibilidad

Barridos deterministas con `run_grid_search` sobre el modelo base (sin metaheuristica, sin ruido de semilla), variando un parametro a la vez desde el escenario de replicacion.

### Limite de AGSR

| value | feasible | feasible_share | best_lcoe_cny_per_kwh | best_wind_mw | best_electrolyzer_mw |
| --- | --- | --- | --- | --- | --- |
| 0.1000 | 16 | 0.0381 | 0.3267 | 110.0000 | 100.0000 |
| 0.1500 | 48 | 0.1143 | 0.3014 | 140.0000 | 100.0000 |
| 0.2000 | 81 | 0.1929 | 0.2859 | 130.0000 | 85.0000 |
| 0.2500 | 115 | 0.2738 | 0.2686 | 190.0000 | 100.0000 |
| 0.3000 | 151 | 0.3595 | 0.2544 | 180.0000 | 85.0000 |

De 10% a 30%, el dominio factible crece en 135 configuraciones y el LCOE optimo baja en 0.0723 CNY/kWh -- coherente con que el paper (SS3.1) fija el limite inferior del electrolizador precisamente por esta restriccion. Ver `figuras/sensibilidad_agsr.png`.

### Carga minima del electrolizador

| value | feasible | feasible_share | best_lcoe_cny_per_kwh | best_wind_mw | best_electrolyzer_mw |
| --- | --- | --- | --- | --- | --- |
| 0.2000 | 82 | 0.1952 | 0.2854 | 130.0000 | 85.0000 |
| 0.3000 | 81 | 0.1929 | 0.2859 | 130.0000 | 85.0000 |
| 0.4000 | 75 | 0.1786 | 0.2863 | 130.0000 | 85.0000 |
| 0.5000 | 55 | 0.1310 | 0.2942 | 120.0000 | 85.0000 |

De 20% a 50% (el paper usa 30%), el dominio factible cambia en -27 configuraciones y el LCOE optimo sube en 0.0088 CNY/kWh. Ver `figuras/sensibilidad_carga_minima.png`.

## Como estan configurados los graficos

Paleta y `rcParams` compartidos en `src/h2_hres/analysis/style.py`, validados con el script de la skill `dataviz` (metodo OKLab/CVD de Arcuri) para las cuatro series apareciendo juntas a la vez (boxplot, dispersion) -- el contexto mas exigente. Solo los tres primeros colores del catalogo de referencia superan esa validacion en conjunto; `random` es la linea base, no un algoritmo competidor, asi que se codifica con gris neutro y linea discontinua en vez de un cuarto matiz categorico.

| Figura | Datos | Que muestra | Regenerar |
|---|---|---|---|
| `convergencia_por_algoritmo.png` | `datos/history.csv` agrupado por algoritmo x iteracion | mediana del mejor score y banda intercuartil (25-75%) entre semillas | `h2hres compare` |
| `distribucion_scores.png` | `datos/runs.csv` | boxplot del score final por algoritmo, una caja por algoritmo | `h2hres compare` |
| `calidad_vs_tiempo.png` | `datos/runs.csv` | dispersion tiempo-de-corrida vs. score final, un punto por corrida | `h2hres compare` |
| `sensibilidad_agsr.png` | `tablas/sensibilidad_agsr.csv` | tres paneles de un eje cada uno (costo, capacidades, factibilidad) vs. el limite de AGSR barrido | `h2hres sensitivity` |
| `sensibilidad_carga_minima.png` | `tablas/sensibilidad_carga_minima.csv` | idem, vs. la carga minima del electrolizador | `h2hres sensitivity` |

Ningun grafico usa un eje Y doble: donde hay mas de una magnitud (capacidades y factibilidad en la sensibilidad) se resuelve en paneles separados, cada uno con un solo eje.

## Que NO se hizo y por que

- **Multiobjetivo (NSGA-II / MOPSO)**: el paper lo sugiere en SS3.3, pero exige frente de Pareto, metricas de hipervolumen y una interfaz distinta de `Optimizer`. Queda como una fase propia.
- **NPV, IRR, ROI, payback**: exigen precio del H2, *feed-in tariff* y prioridad de despacho, que el paper no publica.
- **Capacidad total variable** (SS3.3, punto 2) y **perfil de carga de H2** (SS3.3, punto 3): fuera de alcance de esta fase.
- **Duracion de bateria como eje de sensibilidad explicito**: queda como variable de decision dentro de la optimizacion (ver el reparto de costos en la seccion de supuestos), no como un tercer barrido determinista.

## Supuestos declarados

- **Costo de bateria por potencia y energia**: el paper solo cotiza la bateria por kW (2549/500/10 CNY/kW capex/reemplazo/O&M) porque sus tres casos publicados son todos de 1 h, donde potencia y energia son numericamente iguales. Para que la duracion de bateria tenga sentido economico como variable de decision, este escenario reparte esos costos 30% potencia / 70% energia -- a 1 h la suma da exactamente los valores del paper (NPC-neutro, verificado en `tests/test_paper_validation.py`), y a mas horas la bateria cuesta mas. Es un supuesto explicito, no un dato del paper.
- **`wind.wind_speed_source = measured_50m`**: la Tabla 3 del paper declara buje a 105 m, pero extrapolar a esa altura (via el parametro `WSC` de NASA POWER) da un CF eolico de ~56% contra el 40% publicado, mientras que la serie de 50 m sin extrapolar lo reproduce al 1%. Ver CHANGELOG.md, correccion 1.
- **`converter.plant_load_ratio = 0.0`**: el paper no publica el consumo parasito de la planta.
- **Hiperparametros de PSO/GA sin ajustar**: valores canonicos de la literatura, no afinados a este problema (seccion 3).

## Cuestiones abiertas

Documentadas en detalle en `CHANGELOG.md`: el reparto positivo/negativo de la complementariedad viento-solar sale espejado respecto del paper aun con hora local corregida; el NPC de W60-P140-E85-B27.5 es inconsistente con la propia Tabla 4 del paper (unico objetivo fuera de tolerancia en la validacion); el viento medio replicado (7.00 m/s) difiere del publicado (7.56 m/s), compatible con revisiones de NASA POWER posteriores a 2023; y el LCOH del caso optimo tiene dos valores distintos dentro del propio paper (14.1574 vs. 10.6248 CNY/kg).

## Reproducir

```bash
pip install -e ".[dev]"
h2hres download --config configs/metaheuristicas.yaml   # ~1 min, una vez
h2hres report   --config configs/metaheuristicas.yaml --out entrega
```

`report` encadena validacion, comparativa (4 algoritmos x 30 semillas, 600 evaluaciones cada una) y los dos barridos de sensibilidad. En esta maquina toma aproximadamente 4-5 minutos. Cada corrida individual tambien queda en `results/<timestamp>_*/` via `h2hres compare` y `h2hres sensitivity` por separado, si hace falta aislar una sin regenerar todo.

