# Tesis: optimización de un sistema WPEB con metaheurísticas

Contenido principal:

- **notebooks/H2_HRES_trabajo.ipynb**: cuaderno ejecutable con el modelo, las pruebas y los experimentos.
- **notebooks/src/hourly_2008.csv**: 8.784 registros horarios de 2008. El caso principal excluye el 29 de febrero y utiliza 8.760 horas.
- **scripts/execute_notebook.py**: ejecución reproducible en modo rápido o completo.
- **latex/**: fuentes de la tesis y script de compilación.

## Como ejecutarlo

Requisitos: Python 3.13, `numpy`, `pandas`, `matplotlib`, `scipy`, `nbformat` y `nbclient`.

```bash
pip install numpy pandas matplotlib scipy nbformat nbclient
python scripts/execute_notebook.py --mode rapido
```

Para regenerar los resultados definitivos:

```bash
python scripts/execute_notebook.py --mode completo --output notebooks/H2_HRES_trabajo.ipynb --timeout 7200
python scripts/verificar_resultados.py
powershell -ExecutionPolicy Bypass -File latex/compilar.ps1
```

La compilación genera las tablas LaTeX desde `notebooks/results/`, extrae las figuras del notebook ejecutado y crea `pdf/main.pdf`. La ejecución completa usa 30 réplicas independientes por algoritmo, población 20 y exactamente 600 solicitudes de evaluación por réplica. El LCOE es la única función objetivo; NPC y el LCOH definido por esta tesis se informan como indicadores secundarios.
