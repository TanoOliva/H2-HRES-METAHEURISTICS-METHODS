# Tesis: optimización de un sistema WPEB con metaheurísticas clásicas e híbridas

Contenido principal:

- **notebooks/H2_HRES_trabajo.ipynb**: cuaderno ejecutable con el modelo, las pruebas y los experimentos.
- **notebooks/src/hourly_2008.csv**: 8.784 registros horarios de 2008. El caso principal excluye el 29 de febrero y utiliza 8.760 horas.
- **notebooks/results/**: tablas CSV reproducibles de la última corrida completa (columna `instance` donde corresponde).
- **notebooks/cache/** (no versionado): resultados reducidos de la fuerza bruta por instancia, para no repetir las horas de cómputo al corregir un algoritmo.
- **scripts/execute_notebook.py**: ejecución reproducible en modo rápido o completo.
- **scripts/analisis_estadistico.py**: inferencia estadística (la importa el cuaderno y también corre sola sobre los CSV).
- **latex/**: fuentes de la tesis y script de compilación.
- **presentacion/**: presentación de la defensa.

## Qué se compara

Siete algoritmos con presupuesto idéntico (30 réplicas × 600 solicitudes de objetivo) sobre ocho instancias del problema de dimensionamiento:

- cinco metaheurísticas clásicas: GWO, PSO, GA, SHO y WOA;
- un híbrido integrativo de bajo nivel: PSO+GA (enjambre con operadores genéticos);
- búsqueda aleatoria como línea base.

El cuaderno conserva además el código de dos híbridos con búsqueda local (GA+LS y SHO+LS), que no participan en el experimento.

Instancias: I1 (mixta de referencia, 200 MW, AGSR ≤ 0,20), I2 (AGSR ≤ 0,10), I3 (catálogos finos: módulos de 2,5 MW, batería en pasos de 2,5 MW, duraciones 1/2/4/8 h), I4 (300 MW), I5 (100 MW), I6 (100 MW, AGSR ≤ 0,10), I7 (300 MW, AGSR ≤ 0,10) e I8 (AGSR ≤ 0,30). Cada instancia tiene su **óptimo exacto por fuerza bruta** (todos los catálogos discretos sobre $W$ con paso de 0,01 MW), que es el único referente de brechas y tasas de éxito.

## Cómo se comparan

El análisis sigue un protocolo de siete pasos (diseñar, preguntar, explorar, elegir prueba, cuantificar, corregir, reportar) con contrastes bilaterales, α = 0,05 y una tolerancia de 0,01 % sobre la brecha al óptimo:

- **en una instancia** (30 corridas independientes por algoritmo): Mann–Whitney, A12 de Vargha–Delaney con IC bootstrap y Hodges–Lehmann, con Holm sobre las ocho instancias de cada par;
- **en general** (una mediana por instancia, pareado): Wilcoxon de rangos con signo, con brechas relativas y prueba de signos como comprobación de robustez;
- **los siete a la vez**: Friedman e Iman–Davenport, con la diferencia crítica de Nemenyi.

`python scripts/analisis_estadistico.py` recalcula las tablas `stat_*.csv` y las dos figuras de inferencia desde los CSV, sin repetir el experimento.

## Cómo ejecutarlo

Requisitos: Python 3.13, `numpy`, `pandas`, `matplotlib`, `scipy`, `nbformat` y `nbclient`.

```bash
pip install numpy pandas matplotlib scipy nbformat nbclient
python scripts/execute_notebook.py --mode rapido --output tmp/rapido.ipynb
```

Para regenerar los resultados definitivos (unas 6 horas la primera vez: 4,2 h de fuerza bruta, que se cachea, y 1,7 h de corridas):

```bash
python scripts/execute_notebook.py --mode completo --output notebooks/H2_HRES_trabajo.ipynb --timeout 18000
python scripts/verificar_resultados.py
powershell -ExecutionPolicy Bypass -File latex/compilar.ps1
```

La compilación recalcula la inferencia (`scripts/analisis_estadistico.py`), genera las tablas LaTeX desde `notebooks/results/` (`scripts/generar_tablas_latex.py`), extrae las figuras del notebook ejecutado buscando los marcadores `# FIG: nombre` en las celdas (`scripts/extraer_figuras.py`) y crea `pdf/main.pdf`. El LCOE es la única función objetivo; NPC y el LCOH definido por esta tesis se informan como indicadores secundarios.
