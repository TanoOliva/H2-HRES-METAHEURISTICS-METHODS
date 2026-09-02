# H2-HRES: optimización de capacidad de un sistema WPEB

Réplica reproducible y extensión discreta de:

> **Li et al. (2024)**, *Capacity optimization of a wind-photovoltaic-electrolysis-battery
> (WPEB) hybrid energy system for power and hydrogen generation*.

El sistema combina generación eólica y fotovoltaica con un electrolizador y una batería,
sobre datos horarios de NASA POWER para Damao Banner (Baotou, Mongolia Interior).

Este repositorio nació como un notebook de Colab y hoy es un paquete Python instalable.
El notebook original vive en el commit `3381fc7`; su modelo base se conserva ejecutable
en [tests/notebook_reference.py](tests/notebook_reference.py) como referencia de paridad.

## Qué replica

- **Selección del año meteorológico típico** por complementariedad viento-solar: Pearson
  diario, discretización en 9 clases, distancia euclidiana al patrón de largo plazo.
- **Simulación horaria (8760 h)** del despacho WPEB con carga mínima del electrolizador.
- **Optimización de capacidad** con `Wind + PV = 200 MW`, `AGSR ≤ 20%` y
  `Electrolyzer ≤ 50% · (Wind + PV)`.
- **Métricas**: LCOE, LCOH, energía vendida a red, factor de capacidad del electrolizador.

Y lo extiende con una **formulación discreta** — electrolizador modular de 5 MW, potencia
y duración de batería discretas — resuelta con metaheurísticas.

## Instalación

```bash
pip install -e .            # uso normal
pip install -e ".[dev]"     # + pytest
pip install -e ".[fast]"    # + numba (opcional, ver Rendimiento)
```

Requiere Python ≥ 3.10.

## Uso

```bash
h2hres info                                              # estado del entorno
h2hres download     --config configs/paper_li2024.yaml   # datos NASA POWER 2001-2021
h2hres typical-year --config configs/paper_li2024.yaml   # año típico por complementariedad
h2hres cases        --config configs/paper_li2024.yaml   # casos con nombre del paper
h2hres validate     --config configs/paper_li2024.yaml   # contraste contra las cifras del paper
h2hres grid-search  --config configs/paper_li2024.yaml   # barrido exhaustivo del modelo base
h2hres optimize     --config configs/trabajo1_discrete.yaml --algorithm gwo --runs 10
```

`download` se reanuda: solo descarga los años que falten en `wpeb_data/`.

> Si `h2hres` no se encuentra —habitual con el Python de la Microsoft Store, cuyo
> directorio `Scripts/` no queda en el `PATH`— todo funciona igual con
> `python -m h2_hres.cli <subcomando>`.

Cada corrida crea `results/<timestamp>_<etiqueta>/` con la **configuración resuelta**
(`config.yaml`), las tablas en CSV y las figuras. Ese directorio contiene todo lo
necesario para reproducir el resultado — no hace falta recordar qué se ejecutó.

### Como biblioteca

```python
from h2_hres.config import load_scenario
from h2_hres.data import load_years, choose_typical_year
from h2_hres.optimization import GreyWolfOptimizer, ObjectiveFunction

config = load_scenario("configs/trabajo1_discrete.yaml")
year = load_years("wpeb_data")[2008]

result = GreyWolfOptimizer(ObjectiveFunction(year, config), seed=42).optimize()
print(result.best.design, result.best_score)
```

## Estructura

| Módulo | Contenido |
|---|---|
| [config/schema.py](src/h2_hres/config/schema.py) | Dataclasses congeladas con validación |
| [config/loader.py](src/h2_hres/config/loader.py) | Carga y volcado de escenarios YAML |
| [data/nasa_power.py](src/h2_hres/data/nasa_power.py) | Descarga con reintentos |
| [data/typical_year.py](src/h2_hres/data/typical_year.py) | Complementariedad viento-solar |
| [models/wind.py](src/h2_hres/models/wind.py), [models/pv.py](src/h2_hres/models/pv.py) | Curvas de generación |
| [models/economics.py](src/h2_hres/models/economics.py) | CRF, valores presentes, NPC |
| [models/profiles.py](src/h2_hres/models/profiles.py) | Caché de perfiles de generación |
| [simulation/dispatch.py](src/h2_hres/simulation/dispatch.py) | Núcleo horario del SOC |
| [simulation/simulator.py](src/h2_hres/simulation/simulator.py) | Modelos base y discreto |
| [optimization/encoding.py](src/h2_hres/optimization/encoding.py) | Espacio de decisión mixto |
| [optimization/metaheuristics/](src/h2_hres/optimization/metaheuristics/) | GWO, búsqueda aleatoria |
| [analysis/](src/h2_hres/analysis/) | Resúmenes, comparación con el paper, figuras |

### Agregar una metaheurística

Es el punto de extensión principal. Escribir la subclase, registrarla, y queda disponible
en `--algorithm` y en las comparaciones estadísticas:

```python
# src/h2_hres/optimization/metaheuristics/pso.py
from .base import Optimizer

class ParticleSwarm(Optimizer):
    name = "pso"

    def _search(self) -> None:
        positions = self.space.sample(self.rng, self.config.population)
        for iteration in range(self.config.iterations):
            for i in range(len(positions)):
                self._evaluate(positions[i])     # actualiza self.best
            ...                                   # operador de movimiento
            self._record(iteration + 1)
```

```python
# metaheuristics/__init__.py
REGISTRY = {..., ParticleSwarm.name: ParticleSwarm}
```

La clase base aporta semilla, caché, historial por iteración, conteo de evaluaciones y
cronometraje, de modo que dos algoritmos produzcan historiales comparables sin trabajo
extra. El presupuesto (`population × iterations`) es el mismo para todos, que es la
condición para que la comparación sea justa.

## Configuración

Los escenarios son YAML y solo declaran lo que difiere de los valores del paper. **Una
clave desconocida hace fallar la carga** — un typo no debe convertirse en un valor por
defecto silencioso.

```yaml
name: sensibilidad_carga_minima
electrolyzer:
  min_load_ratio: 0.20     # el paper usa 0.30
```

Dos decisiones de modelado que conviene conocer:

- **`economics.lcoe_energy_basis`** — denominador del LCOE:
  `electrolyzer_plus_grid` (por defecto) o `electrolyzer_only`.
- **`costs.battery.capex_cny_per_kwh`** — vale `0.0` por defecto, como en el paper. Si se
  deja en cero **y** la duración de la batería es variable de decisión, alargarla es
  gratis y el optimizador la lleva al máximo sin que ese resultado signifique nada. El
  paquete lo avisa por consola; `configs/trabajo1_discrete.yaml` fija una sola duración
  para evitarlo.

## Verificación

```bash
pytest -q                                            # 126 tests, sin acceso a red
h2hres validate --config configs/paper_li2024.yaml   # contraste contra el paper
```

Dos niveles, con propósitos distintos:

- [tests/test_paper_validation.py](tests/test_paper_validation.py) fija como regresión cada
  una de las siete correcciones de modelado, para que una refactorización futura no las
  deshaga en silencio.
- [tests/test_parity.py](tests/test_parity.py) verifica que la **lógica de despacho** siga
  siendo idéntica a la del notebook, hora por hora. Ya no compara el modelo completo: ese
  cambió a propósito para acercarse al paper, y su validación es ahora `h2hres validate`.

El notebook original sigue ejecutable en
[tests/notebook_reference.py](tests/notebook_reference.py) como referencia congelada.

## Rendimiento

El bucle de despacho es secuencial por naturaleza: el SOC de cada hora depende de la
anterior. Dos medidas lo acotan:

1. **Caché de perfiles de generación** — el notebook recalculaba los perfiles eólico y PV
   para cada capacidad de electrolizador; ahora se memoizan por par `(wind, pv)`. En el
   barrido: 21 cálculos en vez de 420.
2. **numba opcional** — el núcleo se compila con `@njit` si numba está disponible. Es un
   extra, nunca una dependencia dura: sin él se ejecuta la misma función en CPython, con
   resultados idénticos bit a bit (verificado en `test_dispatch.py`).

`h2hres info` reporta cuál de las dos rutas está activa. Si numba no carga, dice por qué.

> **Nota para esta máquina:** numba está instalado pero su DLL nativa (`_dynfunc`) la
> bloquea Windows Application Control, así que corre siempre la ruta CPython. No afecta a
> los resultados. Sobre el barrido de 420 configuraciones el paquete es ~1.1× más rápido
> que el notebook original gracias a la caché de perfiles.

## Correcciones respecto del notebook

El notebook tenía errores que impedían ejecutar su propia extensión. Están documentados
uno por uno en [CHANGELOG.md](CHANGELOG.md), con el comportamiento previo y el actual. El
más grave: la celda 34 leía una clave de configuración inexistente, de modo que el GWO
lanzaba `KeyError` en la primera evaluación y **nunca llegó a ejecutarse**.

## Contraste con el paper

`h2hres validate` contrasta la réplica contra diez cifras publicadas y reporta el desvío de
cada una. Estado actual: **9 de 10 dentro de tolerancia**.

| métrica | paper | réplica | desvío |
|---|---|---|---|
| CF parque eólico | 40% | 39.58% | −1.0% |
| CF parque fotovoltaico | 19% | 18.74% | −1.3% |
| CF electrolizador | 62.40% | 58.89% | −5.6% |
| LCOE `W190-P10-E95-B30` | 0.2692 ¥/kWh | 0.2624 | −2.5% |
| LCOE `W120-P80-E80-B25` | 0.2886 ¥/kWh | 0.2848 | −1.3% |
| LCOE `W60-P140-E85-B27.5` | 0.3617 ¥/kWh | 0.3530 | −2.4% |
| NPC `W190-P10-E95-B30` | 2675.73 M¥ | 2664.98 | −0.4% |
| NPC `W120-P80-E80-B25` | 2350.38 M¥ | 2346.87 | −0.1% |
| CAPEX sobre NPC | 73.30% | 74.10% | +1.1% |

El único objetivo fuera de tolerancia es el NPC de `W60-P140-E85-B27.5` (+9.7%), y la causa
está en la cifra publicada: los costos de la propia Tabla 4 del paper implican un ΔNPC de
−26.7 M¥ respecto de `W120-P80`, no los −235.9 M¥ que reporta. Los otros dos NPC calzan al
0.4%. El detalle está en [CHANGELOG.md](CHANGELOG.md), junto con otras tres inconsistencias
internas del paper y las cuestiones que quedan abiertas.

Llegar a estos números exigió cerrar siete brechas de modelado; la más grave era que la
irradiancia de NASA POWER viene en **W/m²** y se trataba como kWh/m², lo que anulaba por
completo la producción fotovoltaica. Todas están documentadas con su efecto medido.

**Fuera de alcance**: NPV, IRR, ROI y payback exigen precio del H₂, *feed-in tariff* y
prioridad de despacho, que el paper no publica.
