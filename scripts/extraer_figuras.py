"""Extrae las figuras PNG embebidas en el notebook ejecutado hacia latex/figures/.

Las figuras se toman directamente de los outputs persistidos en el .ipynb para
garantizar que corresponden exactamente a la corrida cuyos numeros se citan en
el documento LaTeX.

Cada celda que produce una figura del documento lleva un marcador en su codigo
fuente, en una linea propia:

    # FIG: fig05_convergencia
    # FIG: fig08_sensibilidad_agsr, fig09_sensibilidad_carga_minima

Con varios nombres, las imagenes de la celda se asignan en el orden en que se
produjeron. Asi el mapeo no depende del indice de la celda y sobrevive a
insertar o mover celdas.

Uso:
    python scripts/extraer_figuras.py [--notebook RUTA] [--destino RUTA]
"""

from __future__ import annotations

import argparse
import base64
import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
NOTEBOOK = RAIZ / "notebooks" / "H2_HRES_trabajo.ipynb"
DESTINO = RAIZ / "latex" / "figures"
MARCADOR = re.compile(r"^[ \t]*#[ \t]*FIG:[ \t]*(.+?)[ \t]*$", re.MULTILINE)


def nombres_de(celda: dict) -> list[str]:
    """Nombres de archivo declarados por los marcadores ``# FIG:`` de una celda."""
    fuente = "".join(celda.get("source", []))
    nombres: list[str] = []
    for coincidencia in MARCADOR.finditer(fuente):
        for nombre in coincidencia.group(1).split(","):
            nombre = nombre.strip()
            if nombre:
                nombres.append(nombre if nombre.endswith(".png") else nombre + ".png")
    return nombres


def imagenes_de(celda: dict) -> list[str]:
    """Imagenes PNG (base64) en el orden en que la celda las produjo."""
    return [
        salida["data"]["image/png"]
        for salida in celda.get("outputs", [])
        if "image/png" in salida.get("data", {})
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--notebook", type=Path, default=NOTEBOOK)
    parser.add_argument("--destino", type=Path, default=DESTINO)
    args = parser.parse_args(argv)

    notebook = json.loads(args.notebook.read_text(encoding="utf-8"))
    args.destino.mkdir(parents=True, exist_ok=True)

    escritas: list[str] = []
    errores: list[str] = []
    for indice, celda in enumerate(notebook["cells"]):
        if celda.get("cell_type") != "code":
            continue
        nombres = nombres_de(celda)
        imagenes = imagenes_de(celda)
        if not nombres:
            if imagenes:
                print(f"  aviso: celda {indice} produce {len(imagenes)} imagen(es) sin marcador FIG")
            continue
        if len(imagenes) < len(nombres):
            errores.append(
                f"celda {indice} declara {nombres} pero tiene {len(imagenes)} imagen(es); "
                "el notebook debe estar ejecutado"
            )
            continue
        if len(imagenes) > len(nombres):
            print(f"  aviso: celda {indice} produce {len(imagenes)} imagenes y declara "
                  f"{len(nombres)}; se usan las primeras")
        for nombre, png in zip(nombres, imagenes):
            if nombre in escritas:
                errores.append(f"figura duplicada: {nombre} (celda {indice})")
                continue
            destino = args.destino / nombre
            destino.write_bytes(base64.b64decode(png))
            print(f"  {nombre}  ({destino.stat().st_size} bytes)")
            escritas.append(nombre)

    print(f"\n{len(escritas)} figuras escritas en {args.destino}")
    if errores:
        for error in errores:
            print("ERROR:", error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
