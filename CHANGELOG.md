# Changelog

## 0.3.0 — Comparativa de metaheurísticas

Con la réplica ya validada (9/10 objetivos del paper), esta fase agrega dos metaheurísticas
al GWO existente, un estudio de sensibilidad, comparación estadística entre algoritmos y una
carpeta `entrega/` versionada que consolida todo para el documento de título.

Ejecutar `h2hres report --config configs/metaheuristicas.yaml` regenera `entrega/` entera
(~4-5 min, 4 algoritmos × 30 semillas). Resultado a esa escala: GA obtuvo el mejor score
(0.2810), pero solo GWO y PSO baten a `random` con significancia estadística tras la
corrección de Holm-Bonferroni (2 de 6 pares, Wilcoxon pareado por semilla).

---

### PSO y GA agregados al registro de metaheurísticas

**Antes.** Solo `gwo` y `random` estaban registrados; no había base para afirmar que una
metaheurística resuelve mejor el espacio discreto que el paper deja abierto en §3.3.

**Ahora.**

- **PSO** (`optimization/metaheuristics/pso.py`): constricción de Clerc-Kennedy
  (χ=0.729, c₁=c₂=1.49445), velocidad acotada a un 20% del rango de cada variable.
- **GA** (`optimization/metaheuristics/ga.py`): codificación real, selección por torneo
  (k=3), cruce BLX-α, mutación gaussiana (σ=10% del rango), elitismo (2 individuos).

Ambos siguen exactamente el patrón de `gwo.py` — clip → evaluar → mover → `_record` —
así que consumen `population × iterations` evaluaciones, ni una más ni una menos, y
heredan automáticamente los 5 tests parametrizados por `sorted(REGISTRY)` sin escribir
nada adicional. Los hiperparámetros son los valores canónicos de la literatura, no un
ajuste fino a este problema: la comparativa no debe leerse como un torneo con un
favorito afinado.

Nuevos bloques `PSOConfig` y `GAConfig` anidados en `MetaheuristicConfig`, con la misma
validación en `__post_init__` que el resto del esquema (`ga.elite_count` y
`ga.tournament_size` no pueden superar `population`).

### El costo de batería se reparte en potencia y energía

**Antes.** `configs/trabajo1_discrete.yaml` fijaba la duración de batería en 1 h porque
`costs.battery` solo cobraba por kW: con costo de energía en cero, alargar la batería
era gratis y el optimizador la llevaba al máximo sin que el resultado significara nada.
El paper no permite resolver esto directamente — sus tres casos publicados son todos de
1 h, así que potencia y energía son numéricamente iguales en los datos que reporta.

**Ahora.** `configs/metaheuristicas.yaml` reparte los 2549/500/10 ¥/kW del paper
(capex/reemplazo/O&M) en 30% potencia / 70% energía. A 1 h la suma da exactamente los
valores originales — **NPC-neutro**, verificado en
`test_paper_validation.py::test_battery_cost_split_is_npc_neutral_at_one_hour` — así que
la validación de la Fase 1 no se mueve; a 4 h la batería cuesta 3.1× más. Es un supuesto
explícito, documentado como tal en `entrega/README.md`, no un dato del paper.

Con esto, `duration_candidates_h: [1.0, 2.0, 4.0]` deja de necesitar fijarse en un solo
valor y `DecisionSpace.warnings()` deja de emitir su aviso para este escenario.

### Comparación estadística entre algoritmos

**Antes.** `aggregate_runs()` ya agrupaba por algoritmo, pero nada decidía si una
diferencia de medias era real o ruido de semilla.

**Ahora.** Módulo `analysis/statistics.py`:

- **Wilcoxon pareado por semilla** entre cada par de algoritmos, corregido por
  Holm-Bonferroni sobre las C(n,2) comparaciones. Pareado porque la misma semilla define
  el mismo problema para todos los algoritmos (arranque, orden de muestreo); no
  paramétrico porque los scores de un optimizador estocástico no son normales en general.
- **A₁₂ de Vargha-Delaney**: tamaño del efecto — probabilidad de que una corrida de A
  gane a una de B, más la mitad de los empates. 0.5 = indistinguibles, 1.0 = A domina
  siempre. Es el estándar en la literatura de metaheurísticas porque no asume
  normalidad ni varianzas iguales.

`scipy` vuelve a ser dependencia (solo para `wilcoxon`, seis llamadas al final de una
corrida) — no contradice haberlo quitado en la Fase 1, donde el problema era `pearsonr`
llamado ~7700 veces dentro de un bucle caliente.

### Estudio de sensibilidad

**Nuevo.** `analysis/sensitivity.py` + `h2hres sensitivity`: barre `constraints.agsr_max`
∈ {10%, 15%, 20%, 25%, 30%} y `electrolyzer.min_load_ratio` ∈ {20%, 30%, 40%, 50%} con
`run_grid_search` sobre el modelo base — determinista, sin ruido de semilla — y reporta
cómo se mueve el óptimo y el tamaño del dominio factible. Confirma lo que el paper
afirma en §3.1: relajar el AGSR crece el dominio factible y baja el LCOE óptimo
monotónicamente (16→151 configuraciones factibles, LCOE 0.327→0.254 ¥/kWh entre 10% y
30% sobre los datos de 2008).

### Subcomandos `compare`, `sensitivity` y `report`

- `h2hres compare --algorithms gwo,pso,ga,random --runs 30`: corre N algoritmos sobre las
  mismas semillas y el mismo `ObjectiveFunction` compartido, y escribe
  `statistics.csv` / `pairwise_tests.csv` además de lo que ya escribía `optimize`.
- `h2hres sensitivity`: los dos barridos, con sus figuras.
- `h2hres report --out entrega`: encadena validación + comparativa + sensibilidad y
  consolida todo en una carpeta fija versionada (no timestamped) con un `README.md`
  cuyas tablas se inyectan desde los CSV en el momento de generar — no puede quedar
  desincronizado de sus propios datos.

El bucle algoritmo × semilla vivía duplicado entre `cmd_compare` y lo que iba a ser el
generador de reporte; se extrajo a `optimization/comparison.py::run_comparison()`, que
ahora es la única fuente de verdad para ambos.

### Paleta y estilo compartido de las figuras

**Antes.** `plots.py` no fijaba ningún tema: colores del ciclo por defecto de
matplotlib, sin orden garantizado entre figuras.

**Ahora.** `analysis/style.py`, validado con el script de la skill `dataviz` (método
OKLab/CVD de Arcuri) para las cuatro series apareciendo juntas a la vez — el contexto
más exigente (boxplot, dispersión). Solo los tres primeros colores del catálogo de
referencia superan esa validación en conjunto (azul, naranja, verde-agua); `random` no
recibe un cuarto matiz categórico porque es la línea base, no un algoritmo competidor —
se codifica con gris neutro y línea discontinua, la convención habitual para una
referencia. Cinco figuras nuevas en `analysis/comparison_plots.py`: convergencia por
algoritmo (mediana + banda intercuartil), boxplot de scores finales, dispersión
calidad-tiempo, y los dos barridos de sensibilidad — ninguna con eje Y doble.

---

## 0.2.0 — Replicación fiel del paper

Con el PDF de Li et al. (2024) a la vista, se cerraron las brechas de modelado que separaban
la implementación de las cifras publicadas. La validación pasó de **6/10 a 9/10 objetivos
dentro de tolerancia**, y los tres LCOE del paper se reproducen dentro del 2.6%.

Ejecutar `h2hres validate --config configs/paper_li2024.yaml` para la tabla completa.

| métrica | paper | antes | ahora |
|---|---|---|---|
| CF parque eólico | 40% | — | 39.58% (−1.0%) |
| CF parque fotovoltaico | 19% | 0.72% | 18.74% (−1.3%) |
| CF electrolizador | 62.40% | 57.85% | 58.89% (−5.6%) |
| LCOE W190-P10-E95-B30 | 0.2692 | 0.2657 (−1.3%) | 0.2624 (−2.5%) |
| LCOE W120-P80-E80-B25 | 0.2886 | 0.3712 (+28.6%) | 0.2848 (−1.3%) |
| LCOE W60-P140-E85-B27.5 | 0.3617 | 0.7215 (+99.5%) | 0.3530 (−2.4%) |
| NPC W190-P10-E95-B30 | 2675.73 M¥ | 2640.44 (−1.3%) | 2664.98 (−0.4%) |
| NPC W120-P80-E80-B25 | 2350.38 M¥ | — | 2346.87 (−0.1%) |
| CAPEX sobre NPC | 73.30% | — | 74.10% (+1.1%) |

---

### 7. La irradiancia venía en W/m², tratada como kW/m² — **el PV producía cero**

**Antes.** NASA POWER entrega `ALLSKY_SFC_SW_DWN` horario en **W/m²**, pero el modelo
—heredado del notebook— lo interpretaba como kWh/m². En la corrección térmica tipo NOCT eso
daba `t_cell = t_amb + 33.75 × 500 ≈ 16.900 °C`, con lo que el factor térmico se volvía
negativo y `max(temp_factor, 0)` anulaba la salida: **el campo fotovoltaico entregaba cero en
toda hora con sol apreciable**.

El error pasaba desapercibido porque el caso óptimo del paper (W190-**P10**) casi no tiene
PV. Se delataba en los casos PV-intensivos: W60-P140 daba un LCOE de 0.7215 contra los
0.3617 publicados, un 99.5% de desvío.

**Ahora.** La conversión a kW/m² se aplica al ingerir los datos, de modo que el nombre de la
columna (`ghi_kwh_m2`) sea veraz. El CF fotovoltaico pasó de 0.72% a **18.74%**, contra el
19% que reporta el paper.

*Tests*: `test_paper_validation.py::test_ghi_must_be_in_kw_per_m2`,
`test_parity.py::test_notebook_ignored_hub_height_and_ghi_units`.

### 1. Velocidad de viento a la altura de buje

**Antes.** La curva de potencia se aplicaba sobre `WS50M`, a 50 m, aunque la Tabla 3 del
paper declara buje a **105 m**.

**Ahora.** Se descarga además el parámetro **`WSC`** de NASA POWER, que entrega la velocidad
corregida a la altura pedida con el exponente de cizalladura propio de cada tipo de
superficie (`wind-elevation` + `wind-surface`). Evita inventar un exponente: lo aporta el
proveedor de datos.

α derivados empíricamente contra la API en las coordenadas del sitio:

| superficie | descripción | WSC/WS50M @105 m | α |
|---|---|---|---|
| `vegtype_7` / `vegtype_9` | pastizal / matorral con suelo desnudo | 1.2216 | 0.270 |
| `vegtype_11` | suelo desnudo rugoso | 1.1777 | 0.220 |
| `airportgrass` | pasto plano de aeropuerto | 1.1173 | 0.149 |

**Hallazgo contraintuitivo**: extrapolar a 105 m *aleja* la réplica del paper. El CF eólico
con la serie de 50 m da **39.58%**, contra el 40% publicado; corregido a 105 m salta a 56%
—y aun la superficie más lisa del catálogo da 49%—. Es decir, el paper declara buje a 105 m
pero su CF solo es reproducible con la serie de 50 m: su modelo debe incluir pérdidas de
estela, curva real de turbina u otros descuentos que no publica.

Por eso `wind.wind_speed_source` es configurable y su default es **`measured_50m`**, elegido
por evidencia y no por comodidad. La ruta `hub_height` queda disponible para sensibilidad.

*Tests*: `test_paper_validation.py::test_wind_surface_alphas_follow_the_power_law`,
`::test_default_uses_the_measured_series`.

### 2. Relación DC/AC del campo fotovoltaico

**Antes.** `dc_ac_ratio` existía en la configuración pero **nunca se usaba**: la salida se
calculaba directo sobre la capacidad AC.

**Ahora.** La potencia DC se calcula sobre `pv_ac_capacity_mw · dc_ac_ratio` (Tabla 3:
96.15 MW DC para 80 MW AC) y el inversor recorta al llegar a la capacidad AC. Sube la
producción en horas de irradiancia media sin superar nunca la nominal.

### 3. Pérdidas de conversión

**Antes.** El balance de la Eq. (6) del paper contabiliza `P_inverter_loss`,
`P_rectifier_loss`, `P_battery_loss` y `P_plant_load`; no se modelaba ninguna.

**Ahora.** Nuevo bloque `ConverterConfig`: inversor 95% (PV DC→AC), rectificador 95% (AC→DC
del electrolizador) y convertidor bidireccional 95% (batería), según la Tabla 3. El
hidrógeno se calcula sobre la energía que llega a las celdas, no sobre la carga AC.

`plant_load_ratio` queda en **0.0**: el paper no publica su valor, así que es un supuesto
explícito y no un dato.

### 4. NPC — almacenamiento de H₂ y valor residual

**Antes.** Faltaban dos componentes que el paper sí incluye (Fig. 16e muestra barras de
*Salvage*; la Tabla 4 cotiza el *Hydrogen storage system*).

**Ahora.**

- **H₂ storage**: 6611.77 ¥/kg capex + 141.68 ¥/kg-año O&M sobre 10⁴ kg (Tabla 3) → 87.45 M¥.
- **Salvage**, método lineal de HOMER: `S = C_rep · (vida_restante / vida) / (1+i)^N`.
  El electrolizador (vida 15, reemplazo en el año 15) llega al año 25 con 5 de 15 años sin
  usar → 65.19 M¥; la batería → 2.59 M¥. Eólica y PV (vida 25 = horizonte) no tienen residual.

El NPC del caso óptimo pasó de −1.3% a **−0.4%** de desvío.

### 5. Redondeo de la potencia de batería

**Antes.** Se usaba el 30% exacto de la capacidad del electrolizador (28.5, 24, 25.5 MW).

**Ahora.** Redondeo hacia arriba a múltiplo de **2.5 MW**, que es la única regla compatible
con los tres casos publicados: 0.30×95=28.5→**B30**, 0.30×80=24→**B25**, 0.30×85=25.5→**B27.5**.

### 6. Zona horaria de la complementariedad viento-solar

**Antes.** Los días se agrupaban por fecha **UTC**, pero Damao Banner está en **UTC+8**: el
período diurno local cae entre las 22:00 y las 10:00 UTC y cruza la medianoche, de modo que
cada día solar quedaba partido entre dos días calendario — justo el eje sobre el que se mide
la correlación diaria.

**Ahora.** `site.utc_offset_hours` (default 8.0) desplaza a hora local antes de agrupar.
Además, la numeración de clases se alineó con la **Tabla 5** del paper (clase 1 = correlación
más positiva; antes era al revés). La distancia euclidiana no cambia —es una suma de
cuadrados— pero la tesis debe usar la convención de la fuente.

**Efecto medido** sobre la distribución de largo plazo, contra las cifras del paper (§2.2.3):

| agrupamiento | negativa | neutra | positiva | año típico |
|---|---|---|---|---|
| paper | 0.4147 | 0.2180 | 0.3673 | 2008 |
| UTC (antes) | 0.4061 | 0.1493 | 0.4446 | 2015 |
| **UTC+8 (ahora)** | 0.3619 | **0.2185** | 0.4195 | 2001 |

La clase neutra pasa a calzar con el paper dentro de **0.05 puntos porcentuales**, lo que
confirma que el agrupamiento local es el correcto.

---

## Cuestiones abiertas

1. **Reparto positivo/negativo de la complementariedad.** Con hora local la clase neutra
   calza casi exacto, pero el reparto entre correlación positiva y negativa sale espejado
   respecto del paper (41.95% / 36.19% frente a 36.73% / 41.47%). Ninguno de los offsets
   probados reproduce el año 2008. Como los escenarios fijan `analysis_year: 2008`
   explícitamente, no afecta a los resultados principales.

2. **NPC de W60-P140-E85-B27.5 — inconsistencia del paper.** Es el único objetivo fuera de
   tolerancia (+9.7%). Los costos de la propia Tabla 4 implican un ΔNPC de **−26.7 M¥**
   respecto de W120-P80-E80-B25 (swap de 60 MW eólica→PV = −97.5, +5 MW electrolizador =
   +62.9, +2.5 MW batería = +7.9), pero el paper reporta **−235.9 M¥**. Los otros dos NPC
   calzan al 0.4%, de modo que la inconsistencia está en la cifra publicada.

3. **Viento medio.** Obtenemos 7.00 m/s a 50 m sobre 2001–2021 contra los **7.56 m/s** que
   reporta el paper (−7.4%), con los mismos parámetros y coordenadas. Compatible con
   revisiones de NASA POWER posteriores a 2023.

4. **LCOH del caso óptimo — inconsistencia interna del paper.** El resumen y las conclusiones
   dicen **14.1574 ¥/kg**; la sección 3.2 dice **10.6248 ¥/kg**.

5. **NPV, IRR, ROI y payback** quedan fuera de alcance: exigen precio del H₂, *feed-in
   tariff* y prioridad de despacho, que el paper no publica.

---

## 0.1.0 — Modularización del notebook

El notebook `WPEB_trabajo1_metaheuristics_colab.ipynb` (46 celdas) pasa a ser el paquete
`h2_hres`. El notebook se eliminó del repositorio tras confirmar la paridad numérica;
queda en el commit `3381fc7`, y su modelo base sigue ejecutable en
`tests/notebook_reference.py` como referencia congelada del test de paridad.

**Paridad verificada**: sobre las 420 configuraciones de la malla, las 17 métricas del
modelo base coinciden con el notebook con error relativo máximo `3.8e-15`, misma
factibilidad fila a fila y mismo óptimo. Ver `tests/test_parity.py`.

---

## Correcciones

### 1. `KeyError` que impedía ejecutar la extensión discreta — **bloqueante**

**Antes.** `simulate_wpeb_extended` (celda 34) calculaba el hidrógeno con
`config["electrolyzer_specific_consumption_kwh_per_kg"]`, una clave que no existía ni en
`CONFIG` ni en `EXT_CONFIG`. La función lanzaba `KeyError` en su primera evaluación, de
modo que las celdas 40–43 — baseline aleatorio, GWO, resumen y gráfico de convergencia —
no podían ejecutarse. **El GWO nunca corrió.**

El modelo base (celda 15), en cambio, calculaba el H₂ como
`e_elz · 1000 · eficiencia / HHV`. Eran dos definiciones distintas del mismo fenómeno.

**Ahora.** `ElectrolyzerConfig.specific_consumption_kwh_per_kg` es una propiedad derivada,
`h2_hhv_kwh_per_kg / efficiency` = 39.4 / 0.75 = **52.5333 kWh/kg**, numéricamente idéntica
a la del modelo base. Ambos simuladores la usan. No es configurable, así que no puede
desincronizarse de la eficiencia.

*Tests*: `test_config.py::test_specific_consumption_is_derived`,
`test_simulator.py::test_discrete_model_runs_without_a_missing_key`.

### 2. Denominador del LCOE inconsistente entre los dos modelos

**Antes.** El modelo base usaba energía útil = `E_electrolizador + E_red`; el extendido,
solo `E_electrolizador`. Nada justificaba la diferencia, y hacía que los LCOE de ambos
modelos no fueran comparables — precisamente la comparación que el notebook proponía en su
sección 13.

**Ahora.** Criterio único y explícito en `EconomicsConfig.lcoe_energy_basis`, con default
`electrolyzer_plus_grid`, que es el del modelo base y el que coincide con el comentario del
propio notebook sobre la Eq. (5) del paper. Quien prefiera el otro criterio pone
`electrolyzer_only` en el YAML.

*Test*: `test_simulator.py::test_lcoe_basis_changes_the_denominator`.

### 3. La duración de la batería era una variable de decisión sin costo

**Antes.** `battery_duration_h` ∈ {1, 2, 4} h era variable de decisión, pero el NPC solo
cobraba la batería por potencia (CNY/kW). Alargarla de 1 h a 4 h no costaba nada, así que
el optimizador la llevaba al máximo por construcción y ese óptimo no significaba nada.

**Ahora.** `ComponentCost` admite base de energía — `capex_cny_per_kwh`,
`replacement_cny_per_kwh`, `om_cny_per_kwh_year` — con **default `0.0`**, de modo que el NPC
con los costos del paper es exactamente el del notebook. Además:

- `DecisionSpace.warnings()` avisa si la duración es libre y no tiene costo por kWh; la CLI
  lo imprime al empezar `optimize`.
- `configs/trabajo1_discrete.yaml` fija una sola duración hasta que se defina un costo.

El valor del costo por kWh es una decisión de modelado que el paper no aporta, así que se
deja al investigador en vez de inventarlo.

*Tests*: `test_economics.py::test_energy_basis_defaults_to_zero_and_preserves_the_notebook_npc`,
`test_optimizers.py::test_decision_space_warns_about_free_battery_duration`.

### 4. Curtailment que siempre valía cero

**Antes.** La celda 34 registraba una serie `curtailment` en la que `p_curt` se asignaba
`0.0` en la única rama que lo tocaba. `curtailment_mwh` era idénticamente cero: código
muerto que aparentaba medir algo.

**Ahora.** El curtailment se calcula contra `ConstraintsConfig.grid_export_limit_mw`. El
default es `None` — exportación ilimitada, curtailment cero, idéntico al notebook — y al
fijar un límite de conexión el excedente que no cabe se recorta de verdad.

*Tests*: `test_dispatch.py::test_curtailment_is_zero_without_an_export_limit`,
`test_dispatch.py::test_export_limit_produces_curtailment`.

### 5. La clase de correlación +1.0 se descartaba en silencio

**Antes.** `pd.cut(..., bins=[-1.0, ..., 1.0], right=False)` genera intervalos semiabiertos
`[a, b)`. Un Pearson diario de exactamente `+1.0` quedaba fuera de las nueve clases y se
perdía, mientras que `-1.0` sí entraba por `include_lowest=True`. La discretización era
asimétrica en sus extremos.

**Ahora.** El borde superior interno se empuja al siguiente float representable, de modo
que la última clase sea `[0.8, 1.0]` cerrada; las correlaciones se recortan a `[-1, 1]`
para absorber el error de redondeo del cociente. `PEARSON_BINS` sigue documentando los
bordes nominales.

*Test*: `test_typical_year.py::test_perfectly_correlated_days_land_in_the_top_class`.

### 6. Estado global, `display()` y estado implícito

**Antes.** Varias funciones llamaban a `display()`, que solo existe dentro de IPython, así
que no eran usables desde un script ni testeables. La celda 24 invocaba
`summarize_results(results)` con `results` sin definir, porque la celda 22 que lo producía
estaba comentada — un `NameError` en una ejecución de arriba a abajo. Las celdas 42 y 43
consultaban `globals()` para adivinar si había resultados.

**Ahora.** Las funciones de análisis devuelven DataFrames; las de gráfico devuelven la
figura sin llamar a `plt.show()`. El estado se pasa como argumento. No hay `globals()`.

### 7. Infactibilidad sin explicación

**Antes.** Las cinco guardas de restricción devolvían `feasible=False` con todos los campos
en cero, sin indicar cuál se había violado: depurar por qué una configuración se rechazaba
exigía releer el código.

**Ahora.** `SimulationResult.infeasibility_reason` trae el motivo concreto
("electrolizador 125.0 MW supera el maximo de 100.0 MW", "AGSR=0.2312 supera el maximo de
0.20"). Los puntos infactibles por AGSR conservan su LCOE, para poder mapear el dominio
completo.

---

## Cambios de diseño

- **Configuración tipada.** `CONFIG`, `COSTS` y `EXT_CONFIG` (tres dicts, ~50 claves
  planas) pasan a dataclasses congeladas agrupadas por dominio físico, con validación de
  rangos y de coherencia entre bloques. Una clave desconocida en el YAML falla al cargar.
- **Un solo `SimulationResult`.** El notebook tenía dos dataclasses con campos solapados
  pero distintos, lo que impedía comparar ambos modelos en una misma tabla. Ahora hay una,
  superconjunto de las dos.
- **Un solo núcleo de despacho.** Las dos reglas de carga mínima —que estaban duplicadas e
  inconsistentes entre las celdas 15 y 34— conviven como `MinLoadPolicy.TOP_UP` y
  `MinLoadPolicy.THRESHOLD` sobre la misma función.
- **Interfaz común de optimizadores.** `Optimizer` aporta semilla, historial, conteo de
  evaluaciones y cronometraje; agregar PSO/WOA/GA es escribir `_search` y registrar la
  clase.
- **Corridas multi-semilla.** `--runs N` ejecuta N semillas y agrega estadística
  (mejor/media/desv/peor). Una sola corrida de una metaheurística estocástica no es un
  resultado reportable.
- **Salida reproducible.** Cada corrida escribe la configuración resuelta junto a sus
  resultados y figuras.
- **`scipy` deja de ser dependencia.** El Pearson diario se calcula con NumPy: mismo valor
  (verificado bit a bit), sin el sobrecoste de validación de `scipy.stats.pearsonr` en
  ~7700 llamadas.
- **Descarga reanudable y saneada.** `get_or_download` baja solo los años faltantes, con
  reintentos y backoff. Los centinelas `-999` de NASA POWER se convierten a `NaN` y se
  interpolan; el notebook los dejaba pasar como si fueran mediciones.
- **Backend de matplotlib sin ventana** por defecto, respetando `MPLBACKEND` y las sesiones
  Jupyter que ya importaron `pyplot`.

## Rendimiento

- **Caché de perfiles de generación**: el notebook recalculaba los perfiles eólico y PV
  para cada valor de electrolizador. Memoizados por par `(wind, pv)`: 21 cálculos en vez de
  420 en el barrido. Sin cambio numérico.
- **numba opcional** sobre el núcleo de despacho, con fallback a CPython idéntico bit a
  bit. En la máquina de desarrollo la DLL nativa de numba está bloqueada por Windows
  Application Control, así que corre la ruta CPython; el barrido completo es ~1.1× más
  rápido que el notebook gracias a la caché.
