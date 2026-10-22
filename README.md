# Tesis: optimización de un sistema WPEB con metaheurísticas clásicas e híbridas

Contenido principal:

- **notebooks/H2_HRES_trabajo.ipynb**: cuaderno ejecutable con el modelo, las pruebas y los experimentos.
- **notebooks/src/hourly_2008.csv**: 8.784 registros horarios de 2008. El caso principal excluye el 29 de febrero y utiliza 8.760 horas.
- **notebooks/results/**: tablas CSV reproducibles de la última corrida completa (columna `instance` donde corresponde).
- **notebooks/cache/** (no versionado): resultados reducidos de la fuerza bruta por instancia, para no repetir las horas de cómputo al corregir un algoritmo.
- **scripts/execute_notebook.py**: ejecución reproducible en modo rápido o completo.
- **latex/**: fuentes de la tesis y script de compilación.
- **presentacion/**: presentación de la defensa.

## Qué se compara

Nueve algoritmos con presupuesto idéntico (30 réplicas × 600 solicitudes de objetivo) sobre cuatro instancias del problema de dimensionamiento:

- seis clásicos: GWO, PSO, GA, SHO, WOA y búsqueda aleatoria (línea base);
- tres híbridos integrativos de bajo nivel: GA+LS (GA memético), PSO+GA (enjambre con operadores genéticos) y SHO+LS (SHO con búsqueda local sobre la presa).

Instancias: I1 (mixta de referencia, AGSR ≤ 0,20), I2 (AGSR ≤ 0,10), I3 (catálogos finos: módulos de 2,5 MW, batería en pasos de 2,5 MW, duraciones 1/2/4/8 h) e I4 (300 MW). Cada instancia tiene su **óptimo exacto por fuerza bruta** (todos los catálogos discretos sobre $W$ con paso de 0,01 MW), que es el único referente de brechas y tasas de éxito.

## Cómo ejecutarlo

Requisitos: Python 3.13, `numpy`, `pandas`, `matplotlib`, `scipy`, `nbformat` y `nbclient`.

```bash
pip install numpy pandas matplotlib scipy nbformat nbclient
python scripts/execute_notebook.py --mode rapido --output tmp/rapido.ipynb
```

Para regenerar los resultados definitivos (unas 4,5 horas la primera vez; la fuerza bruta se cachea):

```bash
python scripts/execute_notebook.py --mode completo --output notebooks/H2_HRES_trabajo.ipynb --timeout 18000
python scripts/verificar_resultados.py
powershell -ExecutionPolicy Bypass -File latex/compilar.ps1
```

La compilación genera las tablas LaTeX desde `notebooks/results/` (`scripts/generar_tablas_latex.py`), extrae las figuras del notebook ejecutado buscando los marcadores `# FIG: nombre` en las celdas (`scripts/extraer_figuras.py`) y crea `pdf/main.pdf`. El LCOE es la única función objetivo; NPC y el LCOH definido por esta tesis se informan como indicadores secundarios.
