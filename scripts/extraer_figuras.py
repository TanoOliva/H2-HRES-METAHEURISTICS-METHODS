"""Extrae las figuras PNG embebidas en el notebook ejecutado hacia latex/figures/.

Las figuras se toman directamente de los outputs persistidos en el .ipynb para
garantizar que corresponden exactamente a la corrida cuyos numeros se citan en
el documento LaTeX.

Uso:
    python scripts/extraer_figuras.py
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
NOTEBOOK = RAIZ / "notebooks" / "H2_HRES_trabajo.ipynb"
DESTINO = RAIZ / "latex" / "figures"

# (celda, indice de imagen dentro de la celda) -> nombre de archivo
NOMBRES = {
    (11, 0): "fig01_recurso_meteorologico.png",
    (14, 0): "fig02_curva_potencia_generacion.png",
    (26, 0): "fig03_dominio_instancia_base.png",
    (45, 0): "fig04_identidad_visual.png",
    (55, 0): "fig05_convergencia.png",
    (57, 0): "fig06_dispersion_y_tiempo.png",
    (60, 0): "fig07_heatmap_a12.png",
    (63, 0): "fig08_sensibilidad_agsr.png",
    (63, 1): "fig09_sensibilidad_carga_minima.png",
}


def main() -> int:
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    DESTINO.mkdir(parents=True, exist_ok=True)

    escritas = 0
    for indice_celda, celda in enumerate(notebook["cells"]):
        indice_imagen = 0
        for salida in celda.get("outputs", []):
            png = salida.get("data", {}).get("image/png")
            if png is None:
                continue
            nombre = NOMBRES.get((indice_celda, indice_imagen))
            indice_imagen += 1
            if nombre is None:
                print(f"  aviso: imagen sin nombre asignado en celda {indice_celda}")
                continue
            destino = DESTINO / nombre
            destino.write_bytes(base64.b64decode(png))
            print(f"  {nombre}  ({destino.stat().st_size} bytes)")
            escritas += 1

    faltantes = len(NOMBRES) - escritas
    print(f"\n{escritas} figuras escritas en {DESTINO}")
    if faltantes:
        print(f"ERROR: faltan {faltantes} figuras esperadas")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
