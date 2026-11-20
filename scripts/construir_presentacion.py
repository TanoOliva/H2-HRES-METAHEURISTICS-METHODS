"""Construye la presentación de la defensa a partir del deck de avance.

Conserva la plantilla (paleta, logo, banda inferior, tipografía) del deck
``presentacion/Presentacion_avance_tesis_LOliva.pptx`` y reescribe el guion con la
estructura clásica de examen: el problema antes que el método y los resultados
ordenados por las tres preguntas del protocolo estadístico.

    1. El problema            contexto y pregunta · qué se optimiza · por qué es difícil · objetivos
    2. El método: PSO+GA      los padres · el híbrido en cada iteración · una iteración en detalle · competidores
    3. Diseño experimental    protocolo de siete pasos · ocho instancias · condiciones justas · mapa de decisión
    4. Resultados             explorar (2) · P1 (2) · P2 · P3 · lectura
    5. Conclusiones           qué se puede afirmar · aporte y trabajo futuro · cierre

Regla del guion: ningún resultado va escrito a mano. Las constantes del diseño (siete
algoritmos, ocho instancias, R = 30, 600 solicitudes, hiperparámetros) son texto fijo;
todo título, viñeta, tabla o nota que diga cuánto o quién gana se redacta desde los CSV
de ``notebooks/results`` con las funciones ``frase_*``, ``voz_*`` y ``titulo_*``. Al
llegar una corrida nueva basta volver a ejecutar los dos scripts:

    python scripts/figuras_presentacion.py          # figuras pres_*.png
    python scripts/construir_presentacion.py        # escribe el .pptx de la defensa

Si los CSV no corresponden al diseño (por ejemplo, una corrida rápida de prueba), las
láminas de resultados llevan una marca «DATOS PROVISIONALES» que desaparece sola.
"""

from __future__ import annotations

import argparse
import copy
import math
import re
from pathlib import Path

import matplotlib
import pandas as pd
from PIL import Image, ImageFont
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE, PP_PLACEHOLDER
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

from figuras_presentacion import TAMANOS

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "notebooks" / "results"
FIGS_PRES = ROOT / "presentacion" / "figuras"
ORIGEN = ROOT / "presentacion" / "Presentacion_avance_tesis_LOliva.pptx"
DESTINO = ROOT / "presentacion" / "Presentacion_defensa_tesis_LOliva_v3.pptx"

# ---- Constantes del diseño experimental (fijas; no dependen de la corrida) ----------
N_ALG, N_INST = 7, 8
R_DISENO, PRESUPUESTO, POB, ITER, HIJOS = 30, 600, 20, 30, 5
SEMILLAS = "42–71"
H = "pso_ga"                               # el híbrido es el algoritmo de control
CONFIRMATORIOS = ("pso", "ga", "random")   # sus padres y la línea base
RESTO_CONTROL = ("gwo", "sho", "woa")
CLASICAS = ("gwo", "pso", "ga", "sho", "woa")

LABELS = {"gwo": "GWO", "pso": "PSO", "ga": "GA", "sho": "SHO", "woa": "WOA",
          "pso_ga": "PSO+GA", "random": "RANDOM"}
COLOR_ALG = {"gwo": "2A78D6", "pso": "EB6834", "ga": "1BAF7A", "sho": "EDA100", "woa": "E87BA4",
             "pso_ga": "A8431A", "random": "898781"}
SIMB = {"+": "+", "=": "≈", "-": "−"}
NBSP = chr(0x00A0)                         # espacio de no separación

# Paleta de la plantilla
NAVY, BLUE, LIGHT, TEXT = "3C4975", "497DB5", "F1F4F9", "33333D"
RED, GREEN, BROWN = "E53A34", "1BAF7A", "A8431A"
VERDE_SUAVE, ROJO_SUAVE, GRIS_SUAVE = "D5EFE3", "F9D9D7", "F1F4F9"


# --------------------------------------------------------------------------- formato
def lab(a: str) -> str:
    return LABELS.get(str(a), str(a).upper())


def num(x, d=2) -> str:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return "--"
    if pd.isna(x):
        return "--"
    return f"{x:.{d}f}".replace(".", ",").replace("-", "−")


def entero(x) -> str:
    return f"{int(round(float(x))):,}".replace(",", ".")


def pct(x, d=1) -> str:
    return num(100 * float(x), d) + " %"


def truthy(v) -> bool:
    return str(v).strip().lower() in ("true", "1", "1.0")


def pvalor(p) -> str:
    """Valor p para tablas."""
    try:
        p = float(p)
    except (TypeError, ValueError):
        return "--"
    if pd.isna(p):
        return "--"
    if p < 0.001:
        return "< 0,001"
    return num(p, 3)


def ptxt(p) -> str:
    """Valor p para prosa: «p = 0,032» o «p < 0,001»."""
    v = pvalor(p)
    texto = "p " + v if v.startswith("<") else "p = " + v
    return texto.replace(" ", NBSP)        # sin salto de línea entre «p», el signo y el valor


_ACENTOS = (("jerarquico", "jerárquico"), ("lideres", "líderes"), ("mutacion", "mutación"), ("hibrido", "híbrido"),
            ("heterogeneo", "heterogéneo"), ("linea base", "línea base"), ("identico", "idéntico"),
            ("iteracion", "iteración"), ("geneticos", "genéticos"), ("catalogo", "catálogo"), ("->", "→"),
            ("<=", "≤"), ("chi=", "χ = "), ("sigma=", "σ = "))


def acentuar(texto) -> str:
    """Los CSV guardan descripciones en ASCII; aquí se devuelven las tildes y símbolos para mostrarlas."""
    texto = str(texto)
    for sin, con in _ACENTOS:
        texto = texto.replace(sin, con)
    return texto


def enumerar(items, final="y") -> str:
    items = [str(i) for i in items]
    if not items:
        return "ninguno"
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + f" {final} " + items[-1]


def entre_parentesis(codigos, maximo=4) -> str:
    """Lista de instancias entre paréntesis solo si es corta: el texto no crece con los datos."""
    return " ({})".format(", ".join(codigos)) if 1 <= len(codigos) <= maximo else ""


def rango(valores, d=2) -> str:
    valores = [float(v) for v in valores if not pd.isna(v)]
    if not valores:
        return "--"
    a, b = min(valores), max(valores)
    return num(a, d) if num(a, d) == num(b, d) else "{} a {}".format(num(a, d), num(b, d))


# --------------------------------------------------------------------------- medida de texto
_FUENTES: dict = {}


def ancho_texto_in(texto: str, pt: float, bold: bool = False) -> float:
    """Ancho prudente del texto en pulgadas.

    Roboto puede no estar instalada donde se proyecte; se mide con DejaVu Sans, la más ancha de
    las sustitutas habituales (es la que usa LibreOffice), para que el texto quepa con cualquiera.
    """
    if bold not in _FUENTES:
        _FUENTES[bold] = None
        candidatas = [Path(matplotlib.get_data_path()) / "fonts" / "ttf" / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
                      "arialbd.ttf" if bold else "arial.ttf"]
        for candidata in candidatas:
            try:
                _FUENTES[bold] = ImageFont.truetype(str(candidata), 100)
                break
            except OSError:
                continue
    fuente = _FUENTES[bold]
    if fuente is None:
        return len(texto) * (0.68 if bold else 0.6) * pt / 72.0
    return fuente.getlength(texto) / 100.0 * pt / 72.0


def alto_estimado(paras, pt: float, ancho_in: float, espacio_pt: float = 4.0) -> float:
    total = 0.0
    for item in paras:
        texto = item if isinstance(item, str) else "".join(item)
        lineas = max(1, math.ceil(ancho_texto_in(texto, pt) * 1.03 / ancho_in))
        total += lineas * pt * 1.2 / 72.0 + espacio_pt / 72.0
    return total


# --------------------------------------------------------------------------- utilidades pptx
def shape_by_name(slide, name: str):
    for sh in slide.shapes:
        if sh.name == name:
            return sh
    raise KeyError(f"{name!r} no está en {slide.part.partname}")


def delete_shapes(slide, names) -> None:
    for name in names:
        sh = shape_by_name(slide, name)
        sh._element.getparent().remove(sh._element)


def set_paragraphs(shape, paras) -> None:
    """Reemplaza el texto conservando el formato de los runs de la plantilla."""
    tf = shape.text_frame
    ps = list(tf.paragraphs)
    while len(ps) < len(paras):
        nuevo = copy.deepcopy(ps[-1]._p)
        ps[-1]._p.addnext(nuevo)
        ps = list(tf.paragraphs)
    for p in ps[len(paras):]:
        p._p.getparent().remove(p._p)
    for p, item in zip(list(tf.paragraphs), paras):
        for br in p._p.findall(qn("a:br")):
            p._p.remove(br)
        textos = [item] if isinstance(item, str) else list(item)
        runs = list(p.runs)
        if not runs:
            p.add_run()
            runs = list(p.runs)
        while len(runs) < len(textos):
            nuevo = copy.deepcopy(runs[-1]._r)
            runs[-1]._r.addnext(nuevo)
            runs = list(p.runs)
        for r in runs[len(textos):]:
            r._r.getparent().remove(r._r)
        for r, t in zip(list(p.runs), textos):
            r.text = t


def set_text(slide, name: str, paras) -> None:
    set_paragraphs(shape_by_name(slide, name), paras if isinstance(paras, list) else [paras])


def set_size(shape, pt: float) -> None:
    for p in shape.text_frame.paragraphs:
        for r in p.runs:
            r.font.size = Pt(pt)


def encoger(shape, alto_max_in: float, minimo_pt: float = 8.5) -> None:
    """Reduce la letra de una caja de la plantilla hasta que su texto quepa en ``alto_max_in``."""
    paras = [p.text for p in shape.text_frame.paragraphs]
    runs = [r for p in shape.text_frame.paragraphs for r in p.runs if r.font.size]
    if not runs:
        return
    pt = max(r.font.size.pt for r in runs)
    ancho = shape.width / 914400.0
    while pt > minimo_pt and alto_estimado(paras, pt, ancho) > alto_max_in:
        pt -= 0.5
    for r in runs:
        r.font.size = Pt(min(r.font.size.pt, pt))


def titulo(slide, kicker: str, texto: str, dos_lineas: bool = False) -> None:
    """Antetítulo y título. ``dos_lineas`` solo en láminas cuyo contenido empieza en y >= 1,08 pulgadas."""
    set_text(slide, "TextBox 3", kicker)
    set_text(slide, "TextBox 4", texto)
    ajustar_titulo(slide, dos_lineas)


def ajustar_titulo(slide, dos_lineas: bool = False) -> None:
    """Ajusta solo el tamaño de letra del título (TextBox 4) al ancho disponible; no cambia el texto.

    Una línea: de 22 pt hacia abajo hasta que quepa. Si se admiten dos líneas (títulos redactados
    desde los datos, de largo variable), se prefiere 18 pt en dos líneas antes que una letra menor.
    """
    caja = shape_by_name(slide, "TextBox 4")
    texto = caja.text_frame.text
    ancho = caja.width / 914400.0 * 0.98
    cabe = lambda pt, lineas=1.0: ancho_texto_in(texto, pt, bold=True) <= lineas * ancho
    pt = next((t for t in (22, 20, 18) if cabe(t)), None)
    if pt is None and dos_lineas:
        pt = next((t for t in (18, 17, 16) if cabe(t, 1.85)), None)
    if pt is None:
        pt = next((t for t in (17, 16, 15, 14) if cabe(t)), 14)
        if not cabe(pt):
            print("AVISO: el título no cabe en el espacio previsto:", texto)
    set_size(caja, pt)


def clonar(slide, name: str, dx: float = 0.0, dy: float = 0.0, nuevo: str | None = None):
    """Duplica una forma dentro de la misma lámina, desplazada (dx, dy) pulgadas."""
    src = shape_by_name(slide, name)
    siguiente = max(int(e.get("id")) for e in slide.shapes._spTree.iter(qn("p:cNvPr"))) + 1
    el = copy.deepcopy(src._element)
    next(el.iter(qn("p:cNvPr"))).set("id", str(siguiente))
    src._element.addnext(el)
    sh = next(s for s in slide.shapes if s._element is el)
    sh.left, sh.top = src.left + Inches(dx), src.top + Inches(dy)
    sh.name = nuevo or f"{name} copia {siguiente}"
    return sh


def ensure_rows(table, n: int) -> None:
    tbl = table._tbl
    trs = tbl.tr_lst
    while len(trs) < n:
        tbl.append(copy.deepcopy(trs[-1]))
        trs = tbl.tr_lst
    for tr in trs[n:]:
        tbl.remove(tr)


def ensure_cols(table, n: int) -> None:
    tbl = table._tbl
    grid = tbl.tblGrid
    cols = grid.findall(qn("a:gridCol"))
    total = sum(int(c.get("w")) for c in cols)
    while len(cols) < n:
        grid.append(copy.deepcopy(cols[-1]))
        for tr in tbl.tr_lst:
            tcs = tr.findall(qn("a:tc"))
            tr.append(copy.deepcopy(tcs[-1]))
        cols = grid.findall(qn("a:gridCol"))
    for c in cols[n:]:
        grid.remove(c)
    for tr in tbl.tr_lst:
        for tc in tr.findall(qn("a:tc"))[n:]:
            tr.remove(tc)
    cols = grid.findall(qn("a:gridCol"))
    for c in cols:
        c.set("w", str(total // len(cols)))


def set_cell(cell, text: str) -> None:
    p = cell.text_frame.paragraphs[0]
    for extra in list(cell.text_frame.paragraphs)[1:]:
        extra._p.getparent().remove(extra._p)
    runs = list(p.runs)
    if not runs:
        p.add_run()
        runs = list(p.runs)
    for r in runs[1:]:
        r._r.getparent().remove(r._r)
    p.runs[0].text = text


def fill_table(slide, name: str, filas: list[list[str]], col_widths_in: list[float] | None = None,
               font_pt: float | None = None, row_height_in: float | None = None, top_in: float | None = None):
    marco = shape_by_name(slide, name)
    table = marco.table
    ensure_rows(table, len(filas))
    ensure_cols(table, len(filas[0]))
    for i, fila in enumerate(filas):
        for j, valor in enumerate(fila):
            celda = table.cell(i, j)
            set_cell(celda, valor)
            if font_pt is not None:
                for p in celda.text_frame.paragraphs:
                    for r in p.runs:
                        r.font.size = Pt(font_pt)
                celda.margin_top = Emu(int(0.02 * 914400))
                celda.margin_bottom = Emu(int(0.02 * 914400))
    if col_widths_in:
        for j, w in enumerate(col_widths_in):
            table.columns[j].width = Emu(int(w * 914400))
    if row_height_in is not None:
        for fila in table.rows:
            fila.height = Emu(int(row_height_in * 914400))
        marco.height = Emu(int(row_height_in * 914400 * len(filas)))
    if top_in is not None:
        marco.top = Inches(top_in)
    return table


def pintar_celda(cell, fill: str | None = None, bold: bool | None = None, color: str | None = None,
                 align=None) -> None:
    if fill:
        cell.fill.solid()
        cell.fill.fore_color.rgb = RGBColor.from_string(fill)
    for p in cell.text_frame.paragraphs:
        if align is not None:
            p.alignment = align
        for r in p.runs:
            if bold is not None:
                r.font.bold = bold
            if color:
                r.font.color.rgb = RGBColor.from_string(color)


NOTAS_MODELO = None   # notes slide de una diapositiva original, para clonar su marcador de cuerpo


def set_notes(slide, texto: str) -> None:
    notas = slide.notes_slide
    if notas.notes_text_frame is None:
        modelo = next(sh for sh in NOTAS_MODELO.shapes
                      if sh.is_placeholder and sh.placeholder_format.type == PP_PLACEHOLDER.BODY)
        notas.shapes._spTree.insert_element_before(copy.deepcopy(modelo._element), "p:extLst")
    notas.notes_text_frame.text = texto


def duplicate_slide(prs, src):
    """Copia una diapositiva (formas e imágenes) al final de la presentación."""
    nuevo = prs.slides.add_slide(src.slide_layout)
    for sh in list(nuevo.shapes):
        sh._element.getparent().remove(sh._element)
    remap = {}
    for rel in list(src.part.rels.values()):
        if rel.is_external:
            continue
        if rel.reltype.endswith("/image"):
            remap[rel.rId] = nuevo.part.rels.get_or_add(rel.reltype, rel._target)
    for sh in src.shapes:
        el = copy.deepcopy(sh._element)
        for blip in el.iter(qn("a:blip")):
            old = blip.get(qn("r:embed"))
            if old in remap:
                blip.set(qn("r:embed"), remap[old])
        nuevo.shapes._spTree.insert_element_before(el, "p:extLst")
    return nuevo


def reorder_and_prune(prs, keep: list) -> None:
    """Deja en ``prs`` exactamente las diapositivas de ``keep`` en ese orden."""
    sldIdLst = prs.slides._sldIdLst
    por_id = {sldId.rId: sldId for sldId in list(sldIdLst)}
    keep_rids, orden = set(), []
    for slide in keep:
        rid = prs.part.relate_to(slide.part, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide")
        keep_rids.add(rid)
        orden.append(por_id[rid])
    for sldId in list(sldIdLst):
        sldIdLst.remove(sldId)
        if sldId.rId not in keep_rids:
            prs.part.drop_rel(sldId.rId)
    for sldId in orden:
        sldIdLst.append(sldId)


def set_vinetas(slide, items: list[str], paso: float = 0.405) -> None:
    """Viñetas «En esta sección» de un divisor: tantas como ``items``, con el recuadro a su medida."""
    for oval, caja in (("Oval 12", "TextBox 13"), ("Oval 14", "TextBox 15"), ("Oval 16", "TextBox 17"),
                       ("Oval 18", "TextBox 19"), ("Oval 20", "TextBox 21")):
        if any(sh.name == oval for sh in slide.shapes):
            delete_shapes(slide, (oval, caja))
    set_text(slide, "TextBox 11", items[0])
    for k, item in enumerate(items[1:], 1):
        clonar(slide, "Oval 10", dy=paso * k, nuevo=f"Oval viñeta {k + 1}")
        caja = clonar(slide, "TextBox 11", dy=paso * k, nuevo=f"TextBox viñeta {k + 1}")
        set_paragraphs(caja, [item])
    shape_by_name(slide, "Rounded Rectangle 8").height = Inches(0.86 + paso * len(items))


def divisor(slide, n: int, nombre: str, descripcion: str, vinetas: list[str], nota: str) -> None:
    set_text(slide, "TextBox 3", f"SECCIÓN {n} DE 5")
    set_text(slide, "TextBox 4", f"{n:02d}")
    set_text(slide, "TextBox 5", nombre)
    set_text(slide, "TextBox 7", descripcion)
    set_vinetas(slide, vinetas)
    set_notes(slide, nota)


# --------------------------------------------------------------------------- dibujo con formas
def add_box(slide, x, y, w, h, lines, fill=NAVY, color="FFFFFF", size=9.5, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
            bold_first=True, name=None, first_size=None):
    sh = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.fill.solid()
    sh.fill.fore_color.rgb = RGBColor.from_string(fill)
    sh.line.fill.background()
    sh.shadow.inherit = False
    if name:
        sh.name = name
    tf = sh.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = tf.margin_right = Inches(0.06)
    tf.margin_top = tf.margin_bottom = Inches(0.03)
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = line
        r.font.size = Pt((first_size or size + 1) if i == 0 else size)
        r.font.bold = bool(i == 0 and bold_first)
        r.font.color.rgb = RGBColor.from_string(color)
        r.font.name = "Roboto"
    return sh


def add_arrow(slide, x1, y1, x2, y2, color=NAVY, dashed=False, head=True, width=1.5):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = RGBColor.from_string(color)
    c.line.width = Pt(width)
    ln = c.line._get_or_add_ln()
    if dashed:
        ln.append(ln.makeelement(qn("a:prstDash"), {"val": "dash"}))
    if head:
        ln.append(ln.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"}))
    return c


def add_label(slide, x, y, w, h, paras, size=10.5, color=TEXT, align=PP_ALIGN.LEFT, bold_label=True,
              italic=False, ajustar=False, minimo=8.5):
    """Caja de texto con párrafos; cada párrafo es str o [etiqueta_negrita, texto].

    Con ``ajustar`` la letra baja (hasta ``minimo``) si el texto, que puede venir de los datos,
    no cabe en el alto ``h``.
    """
    if ajustar:
        while size > minimo and alto_estimado(paras, size, w - 0.04) > h:
            size -= 0.5
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.02)
    tf.margin_top = tf.margin_bottom = Inches(0.01)
    for i, item in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(4)
        runs = [item] if isinstance(item, str) else list(item)
        for k, texto in enumerate(runs):
            r = p.add_run()
            r.text = texto
            r.font.size = Pt(size)
            r.font.bold = bool(k % 2 == 0 and len(runs) > 1 and bold_label)   # etiqueta, texto, etiqueta, texto…
            r.font.italic = italic
            r.font.color.rgb = RGBColor.from_string(color)
            r.font.name = "Roboto"
    return tb


def add_fig(slide, nombre: str, x: float, y: float, ancho: float | None = None):
    """Inserta una figura ``pres_*.png`` a su tamaño de diseño, centrada en ``ancho`` si se indica."""
    ruta = FIGS_PRES / nombre
    w, h = TAMANOS[nombre]
    iw, ih = Image.open(ruta).size
    h = w * ih / iw
    if ancho is not None:
        x += (ancho - w) / 2.0
    return slide.shapes.add_picture(str(ruta), Inches(x), Inches(y), Inches(w), Inches(h))


def marca_provisional(slide, d) -> None:
    """Etiqueta roja en las láminas con resultados mientras los CSV no sean los de la corrida completa."""
    if d["provisional"]:
        add_box(slide, 5.9, 0.2, 3.6, 0.27, [d["aviso"]], fill="FDECEA", color=RED, size=8, first_size=8,
                name="Marca provisional")


def dibujar_pipeline_psoga(slide):
    """Bucle de PSO en la fila superior, inyección genética en la inferior, cierre con el presupuesto."""
    pop, it, budget = POB, ITER, PRESUPUESTO
    # Fila 1: bucle de PSO (se conserva íntegro)
    y1, h1, w1, g1 = 1.08, 0.86, 2.12, 0.18
    fila1 = [
        ("1 · Inicializar", f"{pop} partículas y velocidades", "uniformes en el dominio"),
        ("2 · Evaluar", "decodificar x → simular 8.760 h", "→ LCOE, AGSR → mérito (Deb) · +1 solicitud"),
        ("3 · Memoria", "actualizar pbest de cada partícula", "y gbest del enjambre"),
        ("4 · Mover", "v = χ[v + c1r1(pbest−x) + c2r2(gbest−x)]", "x ← x + v, recorte a límites"),
    ]
    x1s = []
    for k, (t1, t2, t3) in enumerate(fila1):
        x = 0.5 + k * (w1 + g1)
        x1s.append(x)
        add_box(slide, x, y1, w1, h1, [t1, t2, t3], fill=NAVY, size=8.5, name=f"PSO {k + 1}")
        if k:
            add_arrow(slide, x - g1 + 0.01, y1 + h1 / 2, x - 0.01, y1 + h1 / 2)
    # Fila 2: inyección genética (lo que añade el híbrido), de derecha a izquierda
    y2, h2, w2, g2 = 2.42, 0.86, 1.68, 0.15
    fila2 = [
        ("5 · Elegir", f"las {HIJOS} partículas de", "peor mérito actual"),
        ("6 · Torneo", "k = 3 sobre las mejores", "posiciones personales (pbest)"),
        ("7 · Cruce BLX-α", "pc = 0,9 · α = 0,5", "si no, clona al padre"),
        ("8 · Mutación", "gaussiana por gen", "pm = 0,1 · σ = 10 % del rango"),
        ("9 · Hijos", f"reemplazan a las {HIJOS} peores", "v = 0 · sin memoria (pbest = ∞)"),
    ]
    x2s = []
    for k, (t1, t2, t3) in enumerate(fila2):
        x = 0.5 + (4 - k) * (w2 + g2)      # el flujo corre hacia la izquierda
        x2s.append(x)
        add_box(slide, x, y2, w2, h2, [t1, t2, t3], fill=BROWN, size=8.5, name=f"GA {k + 5}")
        if k:
            add_arrow(slide, x2s[k - 1] - 0.01, y2 + h2 / 2, x + w2 + 0.01, y2 + h2 / 2, color=BROWN)
    add_arrow(slide, x1s[3] + w1 / 2, y1 + h1 + 0.01, x2s[0] + w2 / 2, y2 - 0.01, color=BROWN)
    add_label(slide, x2s[4] + 0.75, y2 + h2 + 0.02, 7.0, 0.24, [["Inyección genética: ", "lo único que añade el híbrido; el bucle de PSO no cambia."]], size=9, color=BROWN)
    # Fila 3: cierre del bucle
    y3, h3 = 3.72, 0.6
    add_box(slide, 0.5, y3, 1.9, h3, [f"¿{budget} solicitudes?", f"{it} iteraciones × {pop}"], fill=LIGHT, color=TEXT, size=8.5, name="Decision")
    add_arrow(slide, x2s[4] + w2 / 2, y2 + h2 + 0.3, x2s[4] + w2 / 2 - 0.2, y3 - 0.01)
    add_box(slide, 2.95, y3, 1.75, h3, ["Mejor diseño", "gbest y su LCOE"], fill=GREEN, size=8.5, name="Mejor diseno")
    add_arrow(slide, 2.41, y3 + h3 / 2, 2.94, y3 + h3 / 2, color=GREEN)
    add_label(slide, 2.45, y3 - 0.22, 0.5, 0.25, ["sí"], size=9, color=GREEN)
    # "no": vuelve a Evaluar por el margen izquierdo
    add_arrow(slide, 0.5, y3 + 0.1, 0.28, y3 + 0.1, head=False, dashed=True)
    add_arrow(slide, 0.28, y3 + 0.1, 0.28, y1 + h1 / 2, head=False, dashed=True)
    add_arrow(slide, 0.28, y1 + h1 / 2, 0.49, y1 + h1 / 2, dashed=True)
    add_label(slide, 0.02, 2.0, 0.3, 0.3, ["no"], size=9, color=NAVY)
    add_label(slide, 5.0, y3 - 0.05, 4.5, 1.0, [
        ["Presupuesto: ", f"{it} iteraciones × {pop} = {budget} solicitudes, las mismas que PSO; los diseños repetidos también cuentan."],
        ["Contrato: ", "toda solicitud pasa por un evaluador con tope duro; al cierre se verifica el total."],
        ["Padres intactos: ", "PSO con constricción de Clerc–Kennedy; operadores y valores del GA sin cambios."],
    ], size=9)


def dibujar_detalle_psoga(slide):
    """Cuándo actúa PSO y cuándo GA: línea de tiempo de una iteración, reparto y cuentas de la corrida."""
    pop, it, k = POB, ITER, HIJOS
    budget = pop * it
    iniciales, movidas, hijos = pop, (it - 1) * (pop - k), (it - 1) * k

    # --- Franja 1: línea de tiempo de una iteración ------------------------------
    y, h = 1.12, 0.74
    add_label(slide, 0.5, 0.86, 5.0, 0.26, [["Una iteración = ", f"{pop} solicitudes · PSO primero, GA al final"]], size=9.5, color=NAVY)
    segmentos = [
        (f"Evaluar las {pop} partículas", f"{pop} solicitudes al simulador (mérito de Deb)", NAVY, 2.55),
        ("Actualizar memorias", "pbest de cada partícula · gbest del enjambre", NAVY, 2.05),
        (f"Mover las {pop} con PSO", "velocidad con constricción · x ← x + v", NAVY, 2.1),
        (f"Reemplazar las {k} peores", "torneo, BLX-α y mutación del GA · 0 solicitudes", BROWN, 2.3),
    ]
    x = 0.5
    for i, (t1, t2, fill, w) in enumerate(segmentos):
        add_box(slide, x, y, w - 0.06, h, [t1, t2], fill=fill, size=8.5, name=f"Tiempo {i + 1}")
        if i:
            add_arrow(slide, x - 0.06, y + h / 2, x - 0.005, y + h / 2, color=fill, width=1.2)
        x += w
    # Retorno: los hijos se evalúan al inicio de la iteración siguiente.
    x_fin, x_ini, yr = 0.5 + 9.0 - 1.15, 0.5 + 1.25, y + h + 0.14
    add_arrow(slide, x_fin, y + h + 0.01, x_fin, yr, color=BROWN, head=False, dashed=True)
    add_arrow(slide, x_fin, yr, x_ini, yr, color=BROWN, head=False, dashed=True)
    add_arrow(slide, x_ini, yr, x_ini, y + h + 0.01, color=BROWN, dashed=True)
    add_label(slide, 2.0, yr + 0.02, 6.0, 0.26,
              [[f"Los {k} hijos se evalúan al inicio de la iteración siguiente, dentro de las {pop} solicitudes"]],
              size=9, color=BROWN, align=PP_ALIGN.CENTER)

    # --- Franja 2: reparto de trabajo --------------------------------------------
    y2, h2, w2 = 2.3, 1.52, 4.4
    for x2, titulo_tarjeta, color, filas in (
        (0.5, "PSO actúa sobre todo el enjambre", NAVY, [
            ["Sobre quién: ", f"las {pop} partículas, en todas las iteraciones"],
            ["Con qué: ", "su velocidad, su pbest y el gbest del enjambre"],
            ["Qué produce: ", "una posición nueva, con memoria y velocidad"],
            ["Cuánto cuesta: ", f"las {pop} solicitudes de la iteración"]]),
        (5.1, f"GA actúa sobre las {k} peores", BROWN, [
            ["Sobre quién: ", f"las {k} partículas de peor mérito en la iteración"],
            ["Con qué: ", "los pbest del enjambre; torneo k = 3, BLX-α, mutación"],
            ["Qué produce: ", f"{k} hijos con velocidad 0 y sin memoria"],
            ["Cuánto cuesta: ", "0 solicitudes; se evalúan en la siguiente"]]),
    ):
        add_box(slide, x2, y2, w2, h2, [], fill=LIGHT, name="Tarjeta " + titulo_tarjeta[:3])
        add_label(slide, x2 + 0.15, y2 + 0.06, w2 - 0.3, 0.3, [[titulo_tarjeta]], size=11.5, color=color, bold_label=False)
        tb = add_label(slide, x2 + 0.15, y2 + 0.4, w2 - 0.3, h2 - 0.45, filas, size=9)
        for p in tb.text_frame.paragraphs:
            if p.runs:
                p.runs[0].font.bold = True

    # --- Franja 3: cuentas de la corrida ------------------------------------------
    y3, h3, ancho = 3.94, 0.34, 9.0
    partes = [(iniciales, "D9D9D9", TEXT, f"{iniciales}"),
              (movidas, NAVY, "FFFFFF", f"{movidas} posiciones movidas por PSO"),
              (hijos, BROWN, "FFFFFF", f"{hijos} hijos del GA")]
    x = 0.5
    for n, fill, color, texto in partes:
        w = ancho * n / budget
        add_box(slide, x, y3, w, h3, [texto], fill=fill, color=color, size=8.5, shape=MSO_SHAPE.RECTANGLE, name="Cuenta " + texto[:6])
        x += w
    add_label(slide, 0.5, y3 + h3 + 0.02, 9.0, 0.32, [[
        f"{budget} solicitudes = ", f"{pop} iniciales + {it - 1} × {pop - k} movidas por PSO + {it - 1} × {k} hijos del GA. "
        f"Desde la segunda iteración, {pop - k} partículas siguen al enjambre y {k} vienen del GA: tres de cada cuatro evaluaciones siguen siendo del PSO."]], size=9)


def dibujar_protocolo(slide, d):
    """Los siete pasos del protocolo de comparación y, bajo cada uno, lo que se hizo en la tesis."""
    alfa, eps = d["alfa"], d["eps"]
    pasos = [
        ("1 · Diseñar", "¿Con qué reglas se corre?",
         [f"{N_INST} instancias, {N_ALG} algoritmos", f"R = {R_DISENO} réplicas ({SEMILLAS})", f"{PRESUPUESTO} solicitudes por corrida"]),
        ("2 · Preguntar", "Hipótesis antes de los datos",
         ["P1, P2 y P3 declaradas", f"Bilateral, α = {alfa}", f"Tolerancia ε = {eps}"]),
        ("3 · Explorar", "Mirar antes de contrastar",
         ["Convergencia", "Distribución de la brecha", "Shapiro–Wilk por muestra"]),
        ("4 · Elegir la prueba", "¿Cuántos? ¿Pareado?",
         ["P1: Mann–Whitney", "P2: Wilcoxon con signo", "P3: Friedman"]),
        ("5 · Cuantificar", "Tamaño de efecto e intervalo",
         ["Â12 de Vargha–Delaney", "IC bootstrap al 95 %", "Hodges–Lehmann"]),
        ("6 · Corregir", "Comparaciones múltiples",
         ["Holm por familia", f"P1: {N_INST} instancias por par", "P2: contrastes globales"]),
        ("7 · Reportar", "También lo no significativo",
         ["Símbolos +, ≈ y −", "p ajustado, efecto e IC", "Tablas y figuras desde CSV"]),
        ("Dos familias", "Contrastes planificados",
         ["Control: PSO+GA vs rival", "Confirman: padres y RANDOM", "Base: clásica vs RANDOM"]),
    ]
    w, h, gx, gy, x0, y0, cab = 2.16, 1.52, 0.12, 0.16, 0.5, 1.12, 0.36
    for k, (nombre, guia, hecho) in enumerate(pasos):
        fila, col = divmod(k, 4)
        x, y = x0 + col * (w + gx), y0 + fila * (h + gy)
        es_paso = k < 7
        add_box(slide, x, y, w, h, [], fill=LIGHT, name=f"Paso {k + 1} tarjeta")
        add_box(slide, x, y, w, cab, [nombre], fill=NAVY if es_paso else BROWN, size=11, first_size=11.5,
                name=f"Paso {k + 1} cabecera")
        add_label(slide, x + 0.08, y + cab + 0.06, w - 0.16, 0.24, [guia], size=9.5, color=BLUE if es_paso else BROWN,
                  italic=True, ajustar=True, minimo=8.0)
        add_label(slide, x + 0.08, y + cab + 0.34, w - 0.16, 0.66, hecho, size=9.5, ajustar=True, minimo=8.0)
        if es_paso and col:
            add_arrow(slide, x - gx + 0.015, y + cab / 2, x - 0.015, y + cab / 2, width=1.3)
    # Del paso 4 al 5: baja por el margen derecho y vuelve al inicio de la segunda fila.
    xd, ym = x0 + 4 * w + 3 * gx + 0.1, y0 + h + gy / 2
    add_arrow(slide, x0 + 4 * w + 3 * gx, y0 + cab / 2, xd, y0 + cab / 2, head=False, width=1.3)
    add_arrow(slide, xd, y0 + cab / 2, xd, ym, head=False, width=1.3)
    add_arrow(slide, xd, ym, x0 - 0.12, ym, head=False, width=1.3)
    add_arrow(slide, x0 - 0.12, ym, x0 - 0.12, y0 + h + gy + cab / 2, head=False, width=1.3)
    add_arrow(slide, x0 - 0.12, y0 + h + gy + cab / 2, x0 - 0.01, y0 + h + gy + cab / 2, width=1.3)
    add_label(slide, 0.5, y0 + 2 * h + gy + 0.06, 9.0, 0.25,
              ["Protocolo de la guía «Comparación estadística de algoritmos estocásticos de optimización» (E. Vega); bajo cada paso, lo que se hizo en la tesis."],
              size=8.5, color="6B7280", italic=True)


def dibujar_mapa_decision(slide, d):
    """Hipótesis y decisiones a priori arriba; abajo, el mapa de decisión aplicado a P1, P2 y P3."""
    alfa, eps = d["alfa"], d["eps"]
    add_box(slide, 0.5, 1.1, 9.0, 0.78, [], fill=LIGHT, name="Hipotesis tarjeta")
    add_label(slide, 0.65, 1.15, 8.7, 0.7, [
        ["Hipótesis: ", "H0, los algoritmos comparados tienen la misma distribución de brecha; H1, difieren (contraste bilateral)."],
        ["Fijado antes de I5–I8: ", f"α = {alfa} · tolerancia ε = {eps} del óptimo (una brecha ≤ ε cuenta como 0) · variable: brecha relativa al óptimo exacto."],
    ], size=10, ajustar=True)
    anchos = [2.0, 1.75, 1.85, 1.5, 1.6]
    hueco = (9.0 - sum(anchos)) / 4
    xs = [0.5 + sum(anchos[:k]) + k * hueco for k in range(5)]
    for x, w, cab in zip(xs, anchos, ["PREGUNTA", "¿CUÁNTOS?", "¿PAREADO?", "PRUEBA", "EFECTO Y CORRECCIÓN"]):
        add_label(slide, x, 1.95, w, 0.22, [cab], size=8.5, color="6B7280", align=PP_ALIGN.CENTER)
    filas = [
        (["P1 · En una instancia", "¿PSO+GA difiere del rival?"],
         ["2 algoritmos", f"1 instancia, {R_DISENO} corridas"],
         ["No pareado", "flujo aleatorio propio:", "muestras independientes"],
         ["Mann–Whitney"],
         ["Â12 + IC al 95 %", f"Holm: {N_INST} instancias"]),
        (["P2 · En general", f"¿y sobre las {N_INST} instancias?"],
         ["2 algoritmos", f"{N_INST} instancias, 1 mediana"],
         ["Pareado", "por instancia"],
         ["Wilcoxon", "rangos con signo"],
         ["Hodges–Lehmann", "Holm: familia"]),
        ([f"P3 · Entre los {N_ALG}", "¿hay alguna diferencia?"],
         [f"{N_ALG} algoritmos", f"{N_INST} instancias"],
         ["Bloques", "cada instancia es un bloque"],
         ["Friedman", "+ Iman–Davenport"],
         ["Si p < α: post-hoc", "diferencia crítica"]),
    ]
    y0, h, gy = 2.2, 0.66, 0.09
    for i, fila in enumerate(filas):
        y = y0 + i * (h + gy)
        for j, (x, w, lineas) in enumerate(zip(xs, anchos, fila)):
            if j == 0:
                add_box(slide, x, y, w, h, lineas, fill=NAVY, size=9, first_size=10.5, name=f"Mapa P{i + 1} pregunta")
            elif j == 3:
                add_box(slide, x, y, w, h, lineas, fill=BROWN, size=9, first_size=11, name=f"Mapa P{i + 1} prueba")
            else:
                add_box(slide, x, y, w, h, lineas, fill=LIGHT, color=TEXT, size=8.5, first_size=9.5, name=f"Mapa P{i + 1} c{j}")
            if j:
                add_arrow(slide, x - hueco + 0.01, y + h / 2, x - 0.01, y + h / 2, width=1.3)
    add_label(slide, 0.5, y0 + 3 * h + 2 * gy + 0.08, 9.0, 0.25,
              ["Siempre con tamaño de efecto: un valor p dice si hay evidencia de una diferencia, no cuánto mide."],
              size=9.5, color=NAVY, italic=True, align=PP_ALIGN.CENTER)


# --------------------------------------------------------------------------- datos
def cargar_datos(resultados: Path = RESULTS) -> dict:
    leer = lambda nombre: pd.read_csv(resultados / nombre)
    d = {}
    d["inst"] = leer("instances.csv").set_index("instance")
    d["bf"] = leer("brute_force_summary.csv").set_index("instance")
    d["codes"] = [c for c in d["inst"].index if c in d["bf"].index]
    d["sum"] = leer("algorithm_summary.csv")
    d["hyper"] = leer("algorithm_hyperparameters.csv")
    d["runs"] = leer("algorithm_runs.csv")
    d["design"] = leer("stat_design.csv").iloc[0]
    d["norm"] = leer("stat_normality.csv")
    d["p1"] = leer("stat_per_instance.csv")
    d["p2"] = leer("stat_global.csv")
    d["fried"] = leer("stat_friedman.csv").iloc[0]
    d["ranks"] = leer("stat_ranks.csv").sort_values("mean_rank").reset_index(drop=True)
    d["power"] = leer("stat_power.csv")
    # Sensibilidad a igual número de diseños únicos (scripts/analisis_estadistico.py).
    d["p2_unicos"] = leer("stat_unicos_global.csv")
    d["ranks_unicos"] = leer("stat_unicos_ranks.csv").sort_values("mean_rank").reset_index(drop=True)
    # Perfil de convergencia: rango medio en cada punto de control (scripts/analisis_estadistico.py).
    d["conv"] = leer("stat_convergencia.csv")

    d["alfa"] = num(d["design"]["alpha"], 2)
    d["eps"] = num(d["design"]["eps_gap_pct"], 2) + " %"
    # Conteos reales de la corrida, leídos de los datos (pueden no ser aún los del diseño).
    por_celda = d["runs"].groupby(["instance", "algorithm"]).size()
    d["replicas"] = int(por_celda.max())
    d["solicitudes"] = int(d["runs"]["n_evaluations"].max())
    d["n_alg"] = int(d["sum"]["algorithm"].nunique())
    d["n_inst"] = len(d["codes"])
    d["corridas"] = int(len(d["runs"]))
    coherente = (por_celda.nunique() == 1
                 and int(d["design"]["replicates"]) == d["replicas"]
                 and set(d["sum"]["runs"].astype(int)) == {d["replicas"]})
    completo = (d["replicas"] == R_DISENO and d["solicitudes"] == PRESUPUESTO
                and d["n_alg"] == N_ALG and d["n_inst"] == N_INST)
    d["provisional"] = not (coherente and completo)
    d["aviso"] = "DATOS PROVISIONALES · R = {} · {} solicitudes".format(d["replicas"], d["solicitudes"])
    if not coherente:
        d["aviso"] = "DATOS PROVISIONALES · CSV en transición"
    return d


def resumen(d, code, alg):
    """Fila de algorithm_summary de una instancia y un algoritmo (o None)."""
    r = d["sum"][(d["sum"]["instance"] == code) & (d["sum"]["algorithm"] == alg)]
    return r.iloc[0] if len(r) else None


def brechas_medianas(d, alg) -> list[float]:
    return [float(r["median_gap_pct"]) for r in (resumen(d, c, alg) for c in d["codes"]) if r is not None]


def duplicados(d) -> pd.DataFrame:
    """Porcentaje de solicitudes duplicadas por instancia (filas) y algoritmo (columnas)."""
    s = d["sum"].copy()
    s["share"] = 100.0 * s["mean_duplicates"] / (s["mean_duplicates"] + s["mean_unique"])
    return s.pivot_table(index="instance", columns="algorithm", values="share")


def respuesta_recorte(d) -> str:
    """Respuesta oral a si el recorte a los límites favorece a GWO, WOA y SHO (amenaza declarada)."""
    en_limite = [c for c in d["codes"]
                 if int(d["bf"].loc[c, "optimum_n_units"]) == int(d["inst"].loc[c, "max_units"])]
    gana_gwo = conteo_p1(d, H, "gwo")["-"]
    con = [c for c in gana_gwo if c in en_limite]
    sin = [c for c in gana_gwo if c not in en_limite]
    texto = ("[Si preguntan si el recorte a los límites favorece a GWO, WOA y SHO:] Es posible, y lo declaro como "
             "amenaza a la validez. Los óptimos están en la frontera del dominio: la duración más corta de batería "
             f"en todas las instancias y el máximo de electrolizadores en {enumerar(en_limite, final='e')}. Como el "
             "vector se recorta antes de decodificar, toda propuesta que se sale cae justo en ese extremo, y GWO, WOA "
             f"y SHO previsiblemente proponen más puntos fuera de rango en su fase exploratoria. GWO supera al híbrido en {len(gana_gwo)} "
             f"instancias, {len(con)} de ellas con el electrolizador en el límite")
    if sin:
        texto += f", pero también en {enumerar(sin)}, que no lo tiene"
    return texto + "; y no registré cuántas propuestas se recortan, así que no lo uso como explicación."


# ---- P1: una instancia --------------------------------------------------------------
def filas_p1(d, a, b) -> pd.DataFrame:
    t = d["p1"]
    s = t[(t["algoritmo_a"] == a) & (t["algoritmo_b"] == b)].drop_duplicates("instance").set_index("instance")
    return s.reindex([c for c in d["codes"] if c in s.index])


def conteo_p1(d, a, b) -> dict:
    s = filas_p1(d, a, b)
    c = {k: [i for i, v in s["simbolo"].items() if str(v).strip() == k] for k in ("+", "=", "-")}
    c["n"] = len(s)
    return c


def frase_p1(d, b, a=H, sujeto=True) -> str:
    """«PSO+GA frente a GA: + en 5 de 8 (I1, …), ≈ en 3, − en 0»."""
    c = conteo_p1(d, a, b)
    cuerpo = "+ en {} de {}{}, ≈ en {}, − en {}{}".format(
        len(c["+"]), c["n"], entre_parentesis(c["+"]), len(c["="]), len(c["-"]), entre_parentesis(c["-"]))
    return "{} frente a {}: {}".format(lab(a), lab(b), cuerpo) if sujeto else cuerpo


def voz_p1(d, b, a=H) -> str:
    """La misma lectura, para decirla en voz alta."""
    c = conteo_p1(d, a, b)
    n = c["n"]
    if not c["+"] and not c["-"]:
        return (f"Frente a {lab(b)}, ninguna de las {n} instancias muestra una diferencia significativa tras Holm: "
                "no hay evidencia de diferencia, que no es lo mismo que decir que son iguales.")
    sig = []
    if c["+"]:
        sig.append(f"significativamente mejor en las {n} instancias" if len(c["+"]) == n else
                   f"significativamente mejor en {len(c['+'])} de las {n} instancias{entre_parentesis(c['+'])}")
    if c["-"]:
        sig.append(f"significativamente peor en las {n} instancias" if len(c["-"]) == n else
                   "significativamente peor en {}{}{}".format(
                       len(c["-"]), "" if c["+"] else f" de las {n} instancias", entre_parentesis(c["-"])))
    texto = f"Frente a {lab(b)}, {lab(a)} es " + " y ".join(sig)
    if c["="]:
        texto += "; en {} no hay evidencia de diferencia".format(
            "la restante" if len(c["="]) == 1 else f"las {len(c['='])} restantes")
    return texto + "."


def voz_p1_grupo(d, rivales, a=H) -> str:
    """Como ``voz_p1`` para varios rivales, juntando en una sola frase los que no muestran diferencias."""
    conteos = {b: conteo_p1(d, a, b) for b in rivales}
    sin = [b for b in rivales if not conteos[b]["+"] and not conteos[b]["-"]]
    frases = [voz_p1(d, b, a) for b in rivales if b not in sin]
    if len(sin) == 1:
        frases.append(voz_p1(d, sin[0], a))
    elif sin:
        n = max(conteos[b]["n"] for b in sin)
        frases.append(f"Frente a {enumerar([lab(b) for b in sin])}, ninguna de las {n} instancias muestra una diferencia "
                      "significativa tras Holm: no hay evidencia de diferencia, que no es lo mismo que decir que son iguales.")
    return " ".join(frases)


def voz_base_grupo(d, algs=CLASICAS, base="random") -> str:
    """Cada clásica frente a la línea base, por instancia."""
    conteos = {a: conteo_p1(d, a, base) for a in algs}
    sin = [a for a in algs if not conteos[a]["+"] and not conteos[a]["-"]]
    frases = [voz_p1(d, base, a=a) for a in algs if a not in sin]
    if sin:
        frases.append("{} no {} diferencias significativas frente a {} en ninguna instancia tras Holm.".format(
            enumerar([lab(a) for a in sin]), "muestra" if len(sin) == 1 else "muestran", lab(base)))
    return " ".join(frases)


def totales_p1(d, rivales, a=H) -> dict:
    tot = {"+": 0, "=": 0, "-": 0, "n": 0}
    for b in rivales:
        c = conteo_p1(d, a, b)
        for k in ("+", "=", "-"):
            tot[k] += len(c[k])
        tot["n"] += c["n"]
    return tot


def titulo_p1(d) -> str:
    c = {b: conteo_p1(d, H, b) for b in CONFIRMATORIOS}
    tot = totales_p1(d, CONFIRMATORIOS)
    n = max(v["n"] for v in c.values())
    if tot["+"] == 0 and tot["-"] == 0:
        return "Por instancia, ninguna diferencia de PSO+GA resiste la corrección de Holm"
    if tot["-"] == 0:
        return "PSO+GA supera a RANDOM en {} de {} instancias, a GA en {} y a PSO en {}".format(
            len(c["random"]["+"]), n, len(c["ga"]["+"]), len(c["pso"]["+"]))
    return "Por instancia, PSO+GA gana {} y pierde {} de sus {} contrastes confirmatorios".format(
        tot["+"], tot["-"], tot["n"])


def mayor_efecto_p1(d, rivales, a=H):
    """Fila significativa de mayor desplazamiento de Hodges–Lehmann (o None)."""
    t = d["p1"]
    s = t[(t["algoritmo_a"] == a) & (t["algoritmo_b"].isin(rivales)) & (t["simbolo"].astype(str).str.strip() != "=")]
    s = s[s["hl_gap_pp"].notna()]
    return None if s.empty else s.loc[s["hl_gap_pp"].abs().idxmax()]


def frase_magnitud(d, rivales) -> str:
    f = mayor_efecto_p1(d, rivales)
    if f is None:
        return "ninguna diferencia resiste la corrección, así que no hay desplazamiento que reportar como efecto."
    return "el mayor desplazamiento significativo es de {} puntos porcentuales de brecha ({} CNY/kWh), frente a {} en {}.".format(
        num(abs(f["hl_gap_pp"]), 2), num(abs(f["hl_cny_per_kwh"]), 4), lab(f["algoritmo_b"]), f["instance"])


# ---- P2: en general -----------------------------------------------------------------
def fila_p2(d, a, b):
    t = d["p2"]
    s = t[(t["algoritmo_a"] == a) & (t["algoritmo_b"] == b)]
    return s.iloc[0] if len(s) else None


def veredicto_p2(f) -> str | None:
    """'mejor', 'peor' o 'sin' (sin evidencia de diferencia) para el algoritmo a del contraste."""
    if f is None:
        return None
    if not truthy(f["significativo"]):
        return "sin"
    hl = float(f["hl_pareado_gap_pp"])
    if pd.isna(hl) or hl == 0:
        hl = float(f["pierde_mediana"]) - float(f["gana_mediana"])
    return "mejor" if hl < 0 else "peor"


LECTURA_P2 = {"mejor": "{a} mejor", "peor": "{a} peor", "sin": "sin evidencia de diferencia", None: "--"}


def voz_p2(d, b, a=H) -> str:
    f = fila_p2(d, a, b)
    if f is None:
        return ""
    cierre = {"sin": "no hay evidencia de una diferencia general",
              "mejor": f"la diferencia a favor de {lab(a)} es significativa",
              "peor": f"la diferencia en contra de {lab(a)} es significativa"}[veredicto_p2(f)]
    return "Frente a {}, {} tiene mejor mediana en {} de {} instancias; con p ajustado {}, {}.".format(
        lab(b), lab(a), int(f["gana_mediana"]), int(f["n_instances"]), pvalor(f["p_value_holm"]), cierre)


def voz_p2_grupo(d, rivales, a=H) -> str:
    """Como ``voz_p2`` para varios rivales, juntando en una frase los contrastes sin evidencia de diferencia."""
    filas = {b: fila_p2(d, a, b) for b in rivales}
    sin = [b for b in rivales if veredicto_p2(filas[b]) == "sin"]
    frases = [voz_p2(d, b, a) for b in rivales if veredicto_p2(filas[b]) in ("mejor", "peor")]
    if len(sin) == 1:
        frases.append(voz_p2(d, sin[0], a))
    elif sin:
        ps = sorted(float(filas[b]["p_value_holm"]) for b in sin)
        detalle = ("el p ajustado es {} en todos".format(pvalor(ps[0])) if pvalor(ps[0]) == pvalor(ps[-1])
                   else "los p ajustados van de {} a {}".format(pvalor(ps[0]), pvalor(ps[-1])))
        frases.append("Frente a {} no hay evidencia de una diferencia general: {}.".format(
            enumerar([lab(b) for b in sin]), detalle))
    return " ".join(frases)


def frase_potencia_breve(d) -> str:
    pi = potencia(d, "instancias")
    if pi is None:
        return "la potencia es limitada."
    return "con {} instancias la potencia para un efecto mediano es {}, así que solo se detectan efectos grandes.".format(
        int(pi["n"]), num(pi["potencia_dz_0.5"], 2))


def grupos_p2(d, rivales, a=H) -> dict:
    v = {b: veredicto_p2(fila_p2(d, a, b)) for b in rivales}
    return {k: [lab(b) for b in rivales if v[b] == k] for k in ("mejor", "peor", "sin")}


def veredicto_general(d, rivales=CONFIRMATORIOS) -> str:
    """«supera a …; es superado por …; sin evidencia de diferencia frente a …» (sin sujeto)."""
    g = grupos_p2(d, rivales)
    if not g["mejor"] and not g["peor"]:
        return "sin evidencia de diferencia frente a " + enumerar(g["sin"], "ni")
    partes = []
    if g["mejor"]:
        partes.append("supera a " + enumerar(g["mejor"]))
    if g["peor"]:
        partes.append("es superado por " + enumerar(g["peor"]))
    if g["sin"]:
        partes.append("sin evidencia de diferencia frente a " + enumerar(g["sin"]))
    return "; ".join(partes)


def titulo_p2(d) -> str:
    v = veredicto_general(d)
    return "En general, " + (v if v.startswith("sin") else "PSO+GA " + v)


def frase_robustez(d, family="control") -> str:
    t = d["p2"][d["p2"]["family"] == family]
    alfa = float(d["design"]["alpha"])
    decide = lambda col: (t[col].astype(float) < alfa)
    iguales = int(((decide("p_value") == decide("p_value_relativa")) & (decide("p_value") == decide("p_value_signos"))).sum())
    return "Wilcoxon sobre el LCOE, sobre la brecha relativa y la prueba de signos toman la misma decisión (α = {} sin corregir) en {} de {} contrastes.".format(
        d["alfa"], iguales, len(t))


def voz_robustez(d, family="control") -> str:
    t = d["p2"][d["p2"]["family"] == family]
    alfa = float(d["design"]["alpha"])
    decide = lambda col: (t[col].astype(float) < alfa)
    coincide = (decide("p_value") == decide("p_value_relativa")) & (decide("p_value") == decide("p_value_signos"))
    iguales = int(coincide.sum())
    texto = ("Como control de robustez, el mismo contraste sobre la brecha relativa y la prueba de signos llevan a la misma "
             "decisión que Wilcoxon en {} de {} contrastes.").format(iguales, len(t))
    distintos = [lab(b) for b in t.loc[~coincide, "algoritmo_b"]]
    if distintos:
        texto += (" La excepción es el contraste frente a {}, donde las tres pruebas no coinciden: ese resultado es "
                  "significativo, pero no robusto, y lo presento con esa cautela.").format(enumerar(distintos))
    return texto


def respuesta_hibridacion(d) -> tuple[str, str]:
    """Respuesta a la pregunta de investigación (viñeta, frase hablada), según P2 y los rangos medios."""
    rangos = p3(d)["rangos"]
    rh, padres = rangos[H], {a: rangos[a] for a in ("pso", "ga")}
    mejor_padre = min(padres, key=padres.get)
    g = grupos_p2(d, ("pso", "ga"))
    cifras = "rango medio {} frente a {} de PSO y {} de GA".format(num(rh, 2), num(padres["pso"], 2), num(padres["ga"], 2))
    if len(g["mejor"]) == 2:
        return ("Respuesta: en este banco, PSO+GA supera en general a sus dos padres (" + cifras + ")",
                "La respuesta a la pregunta de investigación es que, en este banco, el híbrido supera a sus dos padres.")
    if rh > padres[mejor_padre]:
        lugar = "queda entre ambos" if rh < max(padres.values()) else "queda detrás de ambos"
        return ("Respuesta: con esta configuración, PSO+GA no mejora al mejor de sus padres ({}); {} ({})".format(
                    lab(mejor_padre), lugar, cifras),
                "Y la respuesta a la pregunta de investigación: con esta configuración y este presupuesto, el híbrido no "
                "mejora al mejor de sus padres, que es {}; {} por rango medio. Hibridar no fue una mejora gratuita: "
                "redistribuye un presupuesto fijo entre el enjambre y la recombinación.".format(lab(mejor_padre), lugar))
    return ("Respuesta: PSO+GA obtiene mejor rango medio que sus padres, pero la ventaja no queda establecida en general (" + cifras + ")",
            "La respuesta a la pregunta de investigación es que el híbrido obtiene mejor rango medio que sus padres, pero "
            "la ventaja no queda establecida en general.")


def potencia(d, unidad: str):
    p = d["power"][d["power"]["unidad"].astype(str).str.startswith(unidad)]
    return p.iloc[0] if len(p) else None


def frase_potencia(d) -> str:
    pi, pr = potencia(d, "instancias"), potencia(d, "replicas")
    if pi is None or pr is None:
        return "sin tabla de potencia."
    return ("con {} instancias la potencia para un efecto mediano es {} y para uno grande, {}: solo se detectan efectos de tamaño "
            "dz ≥ {}. Por instancia, con R = {}, la potencia para un efecto mediano es {}.").format(
        int(pi["n"]), num(pi["potencia_dz_0.5"], 2), num(pi["potencia_dz_0.8"], 2),
        num(pi["dz_detectable_potencia_0.8"], 2), int(pr["n"]), num(pr["potencia_dz_0.5"], 2))


# ---- P3: todos los algoritmos -------------------------------------------------------
def p3(d) -> dict:
    f, r = d["fried"], d["ranks"]
    cd = float(f["critical_difference"])
    rangos = dict(zip(r["algorithm"], r["mean_rank"].astype(float)))
    rh = rangos.get(H, float("nan"))
    algs = list(rangos)
    pares = [(a, b) for i, a in enumerate(algs) for b in algs[i + 1:]]
    return {
        "procede": truthy(f["posthoc_procede"]), "k": int(f["k_algorithms"]), "n": int(f["n_instances"]),
        "cd": cd, "rangos": rangos, "rh": rh,
        "puesto": 1 + sum(1 for v in rangos.values() if v < rh),
        "mejor": r.iloc[0]["algorithm"], "mejor_rango": float(r.iloc[0]["mean_rank"]),
        "distintos_de_h": [a for a in algs if a != H and abs(rangos[a] - rh) > cd],
        "pares_sobre_cd": sum(1 for a, b in pares if abs(rangos[a] - rangos[b]) > cd), "pares": len(pares),
    }


def titulo_p3(d) -> str:
    q = p3(d)
    if q["procede"]:
        return "Hay diferencias globales entre los {} algoritmos ({})".format(q["k"], ptxt(d["fried"]["iman_davenport_p"]))
    return "Sin evidencia de diferencias globales entre los {} algoritmos ({})".format(q["k"], ptxt(d["fried"]["iman_davenport_p"]))


def frase_friedman(d) -> str:
    f = d["fried"]
    return "χ² = {}, {}".format(num(f["friedman_chi2"], 2), ptxt(f["friedman_p"]))


def frase_iman(d) -> str:
    f = d["fried"]
    return "F({}; {}) = {}, {}".format(int(f["iman_davenport_df1"]), int(f["iman_davenport_df2"]),
                                       num(f["iman_davenport_f"], 2), ptxt(f["iman_davenport_p"]))


def frase_decision_p3(d) -> str:
    q = p3(d)
    if q["procede"]:
        return f"se rechaza H0: hay diferencias entre los {q['k']} algoritmos y procede el post-hoc."
    return f"no se rechaza H0: sin evidencia de diferencias entre los {q['k']}; el post-hoc no procede."


def frase_posthoc(d) -> str:
    q = p3(d)
    if not q["procede"]:
        return "no procede; el diagrama queda como descripción de los rangos medios, no como contraste."
    base = "{} de {} pares superan la diferencia crítica ({}); ".format(q["pares_sobre_cd"], q["pares"], num(q["cd"], 2))
    if q["distintos_de_h"]:
        return base + "PSO+GA se separa de " + enumerar([lab(a) for a in q["distintos_de_h"]]) + "."
    return base + "ningún par con PSO+GA la supera."


def frase_puesto(d) -> str:
    q = p3(d)
    texto = "rango medio {}, puesto {} de {}".format(num(q["rh"], 2), q["puesto"], q["k"])
    if q["mejor"] != H:
        texto += "; el mejor rango medio es de {} ({})".format(lab(q["mejor"]), num(q["mejor_rango"], 2))
    return texto + "."


# ---- Explorar y lectura -------------------------------------------------------------
def normalidad(d) -> tuple[int, int]:
    n = d["norm"]
    evaluables = n[n["p_value"].notna()]
    return int(evaluables["rechaza_normalidad"].map(truthy).sum()), int(len(evaluables))


def titulo_normalidad(d) -> str:
    rech, total = normalidad(d)
    if rech:
        return f"Shapiro–Wilk rechaza la normalidad en {rech} de {total} muestras"
    return "Shapiro–Wilk no rechaza la normalidad en ninguna muestra"


def frase_normalidad(d) -> str:
    rech, total = normalidad(d)
    if rech:
        return (f"rechaza la normalidad en {rech} de las {total} muestras (instancia × algoritmo, α = {d['alfa']}): "
                "se usan pruebas no paramétricas, basadas en rangos.")
    return (f"no rechaza la normalidad en ninguna de las {total} muestras; con {d['replicas']} réplicas eso no la demuestra, "
            "y se mantienen las pruebas de rangos fijadas a priori.")


def mejores_medianas(d, algs) -> dict:
    """Para cada algoritmo, instancias en las que tiene la menor brecha mediana del grupo."""
    gana = {a: [] for a in algs}
    for c in d["codes"]:
        filas = {a: resumen(d, c, a) for a in algs}
        validas = {a: float(r["median_gap_pct"]) for a, r in filas.items() if r is not None}
        if validas:
            gana[min(validas, key=validas.get)].append(c)
    return gana


def frase_mejores_medianas(d, algs) -> str:
    gana = mejores_medianas(d, algs)
    partes = ["{} en {}{}".format(lab(a), len(v), entre_parentesis(v, 3)) for a, v in gana.items() if v]
    return "menor brecha mediana del grupo: " + "; ".join(partes) + "."


def voz_mejores_medianas(d, algs) -> str:
    gana = mejores_medianas(d, algs)
    partes = ["{} en {}".format(lab(a), len(v)) for a, v in gana.items() if v]
    return "la menor brecha mediana la tiene " + enumerar(partes) + ", contando instancias."


def frase_brechas_finales(d, algs) -> str:
    return "; ".join("{} {} %".format(lab(a), rango(brechas_medianas(d, a))) for a in algs)


def lectura_convergencia(d) -> dict:
    """Tramo en que el híbrido encabeza el rango medio, orden a mitad de presupuesto y punto de
    estabilización (desde el cual ningún algoritmo se aparta más de un lugar de su puesto final)."""
    rank = d["conv"].pivot(index="n_evaluations", columns="algorithm", values="mean_rank")
    pos = d["conv"].pivot(index="n_evaluations", columns="algorithm", values="position")
    gap = d["conv"].pivot(index="n_evaluations", columns="algorithm", values="mean_median_gap_pct")
    puntos = list(rank.index)
    final, mitad = puntos[-1], max(k for k in puntos if k <= d["solicitudes"] / 2)
    lidera = [k for k in puntos if pos.loc[k, H] == 1]
    desplazamiento = (pos - pos.loc[final]).abs().max(axis=1)
    estable = next(k for k in puntos if (desplazamiento.loc[k:] <= 1).all())
    reduccion = 100 * (gap.loc[mitad] - gap.loc[final]) / gap.loc[mitad]
    return {"desde": lidera[0] if lidera else None, "hasta": lidera[-1] if lidera else None,
            "mitad": mitad, "lider_mitad": [a for a in rank.columns if pos.loc[mitad, a] == 1],
            "puesto_h_mitad": int(pos.loc[mitad, H]), "estable": estable, "reduccion": reduccion}


def titulo_convergencia(d) -> str:
    c = lectura_convergencia(d)
    if c["hasta"] is not None:
        return "PSO+GA converge primero y se estanca después de {} solicitudes".format(entero(c["hasta"]))
    g = brechas_medianas(d, H)
    if not g:
        return "Convergencia a igual número de solicitudes"
    return "PSO+GA termina entre {} y {} % sobre el óptimo".format(num(min(g), 2), num(max(g), 2))


def lectura_duplicados(d) -> dict:
    t = duplicados(d)
    medias = t.mean().sort_values(ascending=False)
    mas = medias.index[0]
    comunes = t[[H, "pso"]].dropna() if {H, "pso"} <= set(t.columns) else pd.DataFrame()
    return {"medias": medias, "mas": mas,
            "h_mas_que_pso": int((comunes[H] > comunes["pso"]).sum()) if len(comunes) else 0,
            "n": len(comunes)}


def titulo_duplicados(d) -> str:
    q = lectura_duplicados(d)
    m = q["medias"]
    if q["mas"] == H:
        return "PSO+GA es el que más repite: {} % de sus solicitudes son duplicadas".format(num(m[H], 1))
    return "{} repite {} % de sus solicitudes; PSO+GA, {} %".format(lab(q["mas"]), num(m[q["mas"]], 1), num(m.get(H, float("nan")), 1))


# --------------------------------------------------------------------------- construcción
def main(argv=None) -> None:
    global NOTAS_MODELO, FIGS_PRES
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--resultados", type=Path, default=RESULTS, help="carpeta con los CSV del experimento")
    parser.add_argument("--figuras", type=Path, default=FIGS_PRES, help="carpeta con las figuras pres_*.png")
    parser.add_argument("--salida", type=Path, default=DESTINO, help="archivo .pptx de salida")
    args = parser.parse_args(argv)
    FIGS_PRES = args.figuras

    d = cargar_datos(args.resultados)
    codes, bf, inst = d["codes"], d["bf"], d["inst"]
    etiqueta = {c: acentuar(inst.loc[c, "label"]) for c in codes}
    alfa, eps = d["alfa"], d["eps"]
    replicas, solicitudes = d["replicas"], d["solicitudes"]
    bf_total = int(bf.loc[codes, "evaluated"].sum())
    paso_w = num(bf.loc[codes, "wind_step_mw"].min(), 2)
    cuota = bf.loc[codes, "feasible_share"].astype(float)
    borde = int((bf.loc[codes, "optimum_agsr"].astype(float) >= 0.99 * inst.loc[codes, "agsr_max"].astype(float)).sum())
    # Costo de la enumeración frente al de una corrida: respuesta a «¿para qué metaheurísticas?»
    bf_seg = bf.loc[codes, "elapsed_s"].astype(float)
    bf_min_lo, bf_min_hi = entero(bf_seg.min() / 60), entero(bf_seg.max() / 60)
    seg_corrida = num(d["runs"]["elapsed_s"].median(), 1)
    ref_bf = bf.loc[codes[0]]
    dias_2d = entero(float(ref_bf["elapsed_s"]) * float(ref_bf["wind_values"]) / 86400)
    veces_lo = entero(bf.loc[codes, "evaluated"].min() / solicitudes)
    veces_hi = entero(bf.loc[codes, "evaluated"].max() / solicitudes)

    prs = Presentation(str(ORIGEN))
    orig = list(prs.slides)
    S = lambda n: orig[n - 1]
    NOTAS_MODELO = S(1).notes_slide

    def blanca():
        """Lámina con antetítulo, título y banda inferior, sin contenido (molde: la 23 del avance)."""
        s = duplicate_slide(prs, S(23))
        delete_shapes(s, ("Rounded Rectangle 5", "TextBox 6", "TextBox 7", "Rounded Rectangle 8", "TextBox 9", "TextBox 10"))
        return s

    def tabla():
        """Lámina con una tabla a todo el ancho y una caja de texto al pie (molde: la 26 del avance)."""
        return duplicate_slide(prs, S(26))

    # ----------------------------------------------------------- duplicados (antes de editar los moldes)
    s_padres = duplicate_slide(prs, S(23))
    s_futuro = duplicate_slide(prs, S(23))
    s_pipe_alg, s_pipe_detalle = blanca(), blanca()
    s_protocolo, s_mapa = blanca(), blanca()
    s_instancias = tabla()
    s_justas = duplicate_slide(prs, S(5))
    s_conv, s_brecha, s_a12, s_p3, s_lectura = blanca(), blanca(), blanca(), blanca(), blanca()
    s_p1_tabla, s_p2 = tabla(), tabla()
    s_calidad = {c: tabla() for c in codes}
    s_resto, s_base = blanca(), blanca()
    s_rangos = tabla()

    # ======================================================================================
    # PORTADA E ÍNDICE
    # ======================================================================================
    # ==== 1. PORTADA
    s = S(1)
    set_text(s, "TextBox 7", [["Defensa de Proyecto de ", "Título"]])
    set_notes(s, "[0:30] Buenos días. Mi nombre es Luciano Oliva y presento la defensa de mi proyecto de título. El trabajo "
                 "es sobre metaheurísticas: tomo un problema de dimensionamiento de un sistema renovable con hidrógeno, lo uso "
                 f"como banco de pruebas con óptimo conocido y comparo {N_ALG} algoritmos, entre ellos un híbrido, PSO con "
                 "operadores genéticos, bajo un protocolo estadístico que se fijó antes de correr las cuatro instancias nuevas.")

    # ==== 2. ÍNDICE (5 secciones)
    s = S(2)
    filas = [("TextBox 8", "TextBox 9", "El problema", "Qué se optimiza, por qué es difícil y qué se propuso el trabajo."),
             ("TextBox 13", "TextBox 14", "El método: PSO+GA", "Los padres, el híbrido paso a paso y sus competidores."),
             ("TextBox 18", "TextBox 19", "Diseño experimental", "Protocolo de siete pasos, ocho instancias y pruebas fijadas antes de I5–I8."),
             ("TextBox 23", "TextBox 24", "Resultados", "Explorar y luego tres preguntas: por instancia, en general y entre los siete."),
             ("TextBox 28", "TextBox 29", "Conclusiones", "Qué se puede afirmar, qué no, aporte y trabajo futuro.")]
    for a, b, t, sub in filas:
        set_text(s, a, t)
        set_text(s, b, sub)
    set_notes(s, "[0:30] Cinco partes. Primero el problema: qué se optimiza y por qué es difícil. Segundo, el método: el "
                 "híbrido PSO+GA y contra quién compite. Tercero, el diseño experimental: cómo se compara de forma justa. "
                 "Cuarto, los resultados, ordenados por tres preguntas: qué pasa en una instancia, qué pasa en general y si "
                 "hay diferencias entre los siete algoritmos. Y quinto, las conclusiones. Al final tengo láminas de respaldo "
                 "con las tablas completas.")

    # ======================================================================================
    # SECCIÓN 1 · EL PROBLEMA
    # ======================================================================================
    # ==== 3. DIVISOR 01 (ex 3)
    divisor(S(3), 1, "El problema",
            "Qué decisión se optimiza, con qué restricciones y por qué es un buen banco de pruebas para metaheurísticas.",
            ["Contexto y pregunta de investigación", "Qué se optimiza: minimizar el LCOE", "Por qué es difícil", "Objetivos"],
            "[0:10] Parto por el problema.")

    # ==== 4. CONTEXTO Y PREGUNTA DE INVESTIGACIÓN (ex 4)
    s = S(4)
    titulo(s, "EL PROBLEMA · CONTEXTO", "Del hidrógeno verde a una pregunta de búsqueda")
    set_text(s, "TextBox 6", "Hidrógeno verde con recurso variable")
    set_text(s, "TextBox 7", "Viento y sol alimentan un electrolizador; como no coinciden en el tiempo, una batería suaviza la entrega.")
    set_text(s, "TextBox 9", "Dimensionar es optimizar")
    set_text(s, "TextBox 10", "Cuánta capacidad eólica, fotovoltaica, de electrólisis y de batería instalar define el costo de la energía.")
    set_text(s, "TextBox 12", "El desafío es de búsqueda")
    set_text(s, "TextBox 13", "Cada diseño se evalúa simulando un año completo: sin fórmula ni gradiente, es terreno de metaheurísticas.")
    set_text(s, "TextBox 15", "Pregunta de investigación")
    set_text(s, "TextBox 16", "¿Aporta algo hibridar PSO y GA?")
    set_text(s, "TextBox 17", [f"Con el mismo presupuesto, pequeño, de {PRESUPUESTO} solicitudes por corrida, ¿un híbrido PSO+GA llega al óptimo exacto con más fiabilidad que PSO, que GA y que la búsqueda aleatoria?",
                               f"Banco de pruebas: el sistema WPEB de Li et al. (2024), en {N_INST} instancias.",
                               "Foco: las metaheurísticas y cómo se comparan, no la ingeniería eléctrica."])
    set_notes(s, "[1:10] El contexto, breve. El hidrógeno verde se produce con electricidad renovable; como el viento y el sol "
                 "no coinciden en el tiempo, se combinan con una batería. Dimensionar ese sistema es decidir cuánta capacidad "
                 "instalar de cada componente, y esa decisión define el costo de la energía. Lo que me interesa como "
                 "informático es que eso es un problema de optimización difícil: cada diseño se evalúa simulando un año "
                 "completo, no hay fórmula ni gradiente, y por eso se resuelve con metaheurísticas. Uso como banco de pruebas "
                 "el sistema publicado por Li y colaboradores en 2024. Y la pregunta de investigación es de método: con un "
                 f"presupuesto idéntico y pequeño de {PRESUPUESTO} solicitudes por corrida, ¿un híbrido de PSO y GA alcanza el "
                 "óptimo exacto con más fiabilidad que los dos métodos de los que parte y que una búsqueda aleatoria? Por "
                 "fiabilidad entiendo la distribución de la brecha final en las corridas independientes, no una tasa de acierto "
                 "con un umbral fijo, porque el orden por tasa de acierto cambia según el umbral. El foco "
                 "de la defensa está en las metaheurísticas y en cómo se comparan, no en el detalle eléctrico.")

    # ==== 5. QUÉ SE OPTIMIZA (ex 9)
    s = S(9)
    titulo(s, "EL PROBLEMA · FORMULACIÓN", "Cuatro decisiones para minimizar el LCOE")
    set_text(s, "TextBox 7", "W (continua)")
    set_text(s, "TextBox 10", "P = Ctot − W")
    set_text(s, "TextBox 15", "nE módulos → H₂")
    set_text(s, "TextBox 18", "BP y duración k")
    set_text(s, "TextBox 21", "venta ≤ AGSRmáx")
    set_text(s, "TextBox 27", [["Caja negra: ", "el LCOE y la venta a red salen de simular 8.760 h; no hay fórmula ni gradiente."],
                               ["Comparación de diseños: ", "primero factibilidad, luego menor LCOE (reglas de Deb)."]])
    set_text(s, "TextBox 31", [["x = (W, nE, BP, k)", "  → una continua y tres discretas"]])
    set_text(s, "TextBox 32", "Restricciones")
    set_text(s, "TextBox 33", [["C", "1 ", "Capacidad renovable total fija: W + P = Ctot"],
                               ["C", "2 ", "Catálogos: nE entero, BP en pasos fijos, k de una lista"],
                               ["C", "3 ", "Operación válida en cada hora del año"],
                               ["C", "4 ", "Venta anual a la red ≤ AGSRmáx (se conoce al terminar la simulación)"]])
    set_notes(s, "[1:20] Esto es lo que se optimiza. Una planta con una capacidad renovable total fija, que se reparte entre "
                 "eólica y fotovoltaica. La electricidad alimenta un electrolizador que produce hidrógeno, una batería guarda "
                 "excedentes y lo que sobra se vende a la red, con un tope anual. Para la optimización importan cuatro "
                 "decisiones: cuánta capacidad eólica, que es una variable continua; cuántos módulos de electrolizador, que es "
                 "un entero; y la potencia y la duración de la batería, que se eligen de un catálogo. Una variable continua y "
                 "tres discretas. El objetivo es minimizar el costo nivelado de la energía, el LCOE. Las restricciones: la "
                 "capacidad total fija, los catálogos, que la operación sea válida en cada hora, y que la venta anual a la red "
                 "no supere un límite. Lo importante para lo que sigue: ni el LCOE ni la venta a red tienen fórmula; salen de "
                 "simular el año completo. Para el optimizador es una caja negra, y dos diseños se comparan con las reglas de "
                 "Deb: primero factibilidad, después costo.")

    # ==== 6. POR QUÉ ES DIFÍCIL (ex 5)
    s = S(5)
    c_min, c_max = cuota.idxmin(), cuota.idxmax()
    titulo(s, "EL PROBLEMA · DIFICULTAD", "Por qué es difícil: tres obstáculos")
    set_text(s, "TextBox 6", "8.760 h")
    set_text(s, "TextBox 7", "Evaluación costosa")
    set_text(s, "TextBox 8", "Cada diseño exige simular el año hora a hora, porque la batería acopla una hora con la siguiente. Sin gradiente: el presupuesto se cuenta en simulaciones.")
    set_text(s, "TextBox 10", pct(cuota.min(), 1))
    set_text(s, "TextBox 11", "Factibilidad estrecha")
    set_text(s, "TextBox 12", f"de los diseños enumerados cumple el límite de venta a red en {c_min}; en la más holgada ({c_max}) llega a {pct(cuota.max(), 1)}. "
                              f"En {borde} de {len(codes)} instancias el óptimo usa más del 99 % de ese límite.")
    set_text(s, "TextBox 14", "1 + 3")
    set_text(s, "TextBox 15", "Dominio mixto")
    set_text(s, "TextBox 16", "Una variable continua y tres de catálogo: propuestas distintas se decodifican al mismo diseño y gastan evaluaciones repetidas.")
    set_text(s, "TextBox 17", [["Consecuencia: ", "pocas evaluaciones, sin gradiente y un óptimo pegado a una restricción; explorar y explotar compiten por el presupuesto."]])
    set_notes(s, "[1:00] ¿Por qué es difícil? Tres obstáculos. Uno: evaluar es caro. Cada diseño exige simular las 8.760 horas "
                 "del año, así que el presupuesto se cuenta en simulaciones. Dos: la región factible es estrecha. La fuerza "
                 f"bruta muestra que en la instancia más restrictiva, {c_min}, solo {pct(cuota.min(), 1)} de los diseños cumple "
                 f"el límite de venta a la red, y en la más holgada, {c_max}, {pct(cuota.max(), 1)}; además, en {borde} de las "
                 f"{len(codes)} instancias el óptimo queda pegado a ese límite. Tres: el dominio es mixto, una variable continua "
                 "y tres de catálogo, y propuestas distintas se decodifican al mismo diseño, lo que gasta evaluaciones "
                 "repetidas. La consecuencia es que un optimizador tiene pocas evaluaciones para explorar una región estrecha "
                 "y afinar sobre un borde: explorar y explotar compiten por el presupuesto, que es justo lo que un híbrido "
                 "pretende equilibrar.")

    # ==== 7. OBJETIVOS (ex 7)
    s = S(7)
    titulo(s, "EL PROBLEMA · OBJETIVOS", "Objetivo general y objetivos específicos")
    set_text(s, "TextBox 6", "Desarrollar y validar un marco metodológico para implementar y comparar metaheurísticas, clásicas e híbridas, en el dimensionamiento óptimo de sistemas renovables con hidrógeno verde, sustentando las conclusiones en evidencia experimental replicada y auditable.")
    set_text(s, "TextBox 7", "El problema")
    set_text(s, "TextBox 8", ["1. Analizar el modelo: variables, objetivo y restricciones",
                              "2. Implementar y verificar el simulador",
                              "3. Evaluar críticamente sus supuestos",
                              "4. Formular instancias con su óptimo exacto"])
    set_text(s, "TextBox 9", "El método y la comparación")
    set_text(s, "TextBox 10", ["5. Implementar y comparar metaheurísticas clásicas y un híbrido PSO+GA, con presupuesto idéntico y frente a una línea base no informada"])
    set_text(s, "TextBox 11", "La evidencia")
    set_text(s, "TextBox 12", ["6. Caracterizar el desempeño con estadística descriptiva, contrastes planificados y tamaños de efecto",
                               "7. Determinar la sensibilidad a restricciones y supuestos de datos"])
    set_notes(s, "[0:50] El objetivo general es desarrollar y validar un marco metodológico para implementar y comparar "
                 "metaheurísticas, clásicas e híbridas, en este problema, con conclusiones sustentadas en evidencia replicada "
                 "y auditable. Los siete objetivos específicos se ordenan en tres grupos. Los cuatro primeros construyen el "
                 "problema: analizar el modelo, implementar y verificar el simulador, evaluar sus supuestos y formular las "
                 "instancias con su óptimo exacto. El quinto es el método y la comparación: las metaheurísticas clásicas y el "
                 "híbrido PSO+GA, con presupuesto idéntico y frente a una línea base. Y los dos últimos son la evidencia: "
                 "caracterizar el desempeño con estadística y medir la sensibilidad de las conclusiones. La presentación "
                 "sigue ese mismo orden.")

    # ======================================================================================
    # SECCIÓN 2 · EL MÉTODO
    # ======================================================================================
    # ==== 8. DIVISOR 02 (ex 6)
    divisor(S(6), 2, "El método: PSO+GA",
            "Un PSO que, al cierre de cada iteración, reemplaza a sus peores partículas por hijos de los operadores del GA.",
            ["Los padres: PSO y GA", "El híbrido en cada iteración", "Cuándo actúa cada uno", "Competidores y contrato común"],
            "[0:10] Con el problema planteado, paso al método.")

    # ==== 9. LOS PADRES PSO Y GA (molde 23)
    s = s_padres
    titulo(s, "EL MÉTODO · LOS PADRES", "Qué se conserva de PSO y qué se toma de GA")
    set_text(s, "TextBox 6", "PSO: el bucle que se conserva")
    set_text(s, "TextBox 7", [f"Enjambre de {POB} partículas con memoria personal (pbest) y social (gbest)",
                              "Constricción de Clerc y Kennedy: χ = 0,729, c1 = c2 = 1,49445",
                              "Velocidad acotada al 20 % del rango de cada variable",
                              f"{ITER} iteraciones × {POB} = {PRESUPUESTO} solicitudes; sin ningún cambio en el híbrido"])
    set_text(s, "TextBox 9", "GA: los operadores que se inyectan")
    set_text(s, "TextBox 10", ["Selección por torneo de tamaño 3",
                               "Cruce BLX-α con α = 0,5 y probabilidad 0,9",
                               "Mutación gaussiana por gen: p = 0,1, σ = 10 % del rango",
                               "Los mismos valores que usa el GA puro: nada se reajusta para el híbrido"])
    set_notes(s, "[1:00] El híbrido tiene dos padres, y ninguno se modifica. Del PSO se conserva el bucle completo: un enjambre "
                 f"de {POB} partículas, cada una con su mejor posición personal y la mejor del enjambre, la constricción de Clerc "
                 "y Kennedy y la velocidad acotada. Del GA se toman sus tres operadores, selección por torneo, cruce BLX-alfa "
                 "y mutación gaussiana, con exactamente los mismos valores que usa el GA puro que compite en el experimento. "
                 "Nada se reajusta para el híbrido; los valores son los canónicos de la literatura y se fijaron antes de ver "
                 "resultados. Esto importa para leer las dos comparaciones, que no preguntan lo mismo. Frente a PSO, la única "
                 "diferencia es el componente inyectado, así que ese contraste funciona como una ablación en bloque. Frente a "
                 "GA, el híbrido usa los mismos operadores con los mismos valores, pero dentro de otra dinámica de búsqueda: ese "
                 "contraste dice si los operadores rinden más dentro del enjambre, no el efecto de una pieza aislada. Y en "
                 "ninguno de los dos casos la diferencia puede venir de un reajuste de parámetros.")

    # ==== 10. PIPELINE DE PSO+GA (lámina en blanco + formas)
    s = s_pipe_alg
    titulo(s, "EL MÉTODO · EL HÍBRIDO", "Qué hace PSO+GA en cada iteración")
    dibujar_pipeline_psoga(s)
    set_notes(s, f"[1:30] Este es el algoritmo. La fila de arriba es el PSO sin cambios: se inicializan {POB} partículas; se "
                 "evalúa cada una decodificando el vector y simulando el año completo, lo que cuenta una solicitud; se "
                 "actualizan la memoria personal y la global; y las partículas se mueven. La fila de abajo es lo que añade el "
                 f"híbrido, la inyección genética: se toman las {HIJOS} partículas de peor mérito en esa iteración, se eligen "
                 "padres por torneo sobre las mejores posiciones personales del enjambre, se cruzan con BLX-alfa, se mutan con "
                 f"la gaussiana del GA, y los hijos reemplazan a esas {HIJOS} partículas con velocidad cero y sin memoria. El "
                 f"ciclo se repite hasta completar exactamente {PRESUPUESTO} solicitudes, las mismas que el PSO puro, y la "
                 f"salida es el mejor diseño encontrado. Dos garantías: un contrato de presupuesto impide pedir la solicitud "
                 f"{PRESUPUESTO + 1}, y ni el PSO ni los operadores del GA se tocan.")

    # ==== 11. UNA ITERACIÓN EN DETALLE (lámina en blanco + formas)
    s = s_pipe_detalle
    titulo(s, "EL MÉTODO · UNA ITERACIÓN EN DETALLE", "Cuándo actúa PSO y cuándo actúa GA")
    dibujar_detalle_psoga(s)
    set_notes(s, "[1:10] Esta lámina responde cuándo actúa cada uno. Dentro de una iteración, primero PSO: se evalúan las "
                 f"{POB} partículas, que son las {POB} solicitudes de la iteración; se actualizan las memorias; y las {POB} se "
                 f"mueven con la velocidad. Solo entonces actúa GA, y sobre {HIJOS} partículas: las de peor mérito en esa "
                 "iteración. Los hijos no gastan solicitudes al crearse; se evalúan al inicio de la iteración siguiente, "
                 f"dentro de las {POB}. En toda la corrida, de las {PRESUPUESTO} solicitudes, {POB} son la población inicial, "
                 f"{(ITER - 1) * (POB - HIJOS)} son posiciones movidas por el PSO y {(ITER - 1) * HIJOS} son hijos del GA. "
                 "Es decir, tres de cada cuatro evaluaciones siguen siendo del enjambre: conviene tener esa proporción "
                 "presente al leer los resultados.")

    # ==== 12. COMPETIDORES Y CONTRATO COMÚN (ex 12)
    s = S(12)
    titulo(s, "EL MÉTODO · COMPETIDORES", "Siete competidores bajo un mismo contrato")
    for caja, valor, leyenda in (("TextBox 5", str(N_ALG), "algoritmos en competencia"),
                                 ("TextBox 7", str(len(CLASICAS)), "metaheurísticas clásicas"),
                                 ("TextBox 9", "1", "híbrido: PSO+GA"),
                                 ("TextBox 11", "1", "línea base aleatoria"),
                                 ("TextBox 13", str(PRESUPUESTO), "solicitudes por corrida")):
        set_text(s, caja, valor)
        set_text(s, "TextBox " + str(int(caja.split()[1]) + 1), leyenda)
    set_text(s, "TextBox 15", "Los siete competidores")
    competidores = [("gwo", "Tres líderes guían la manada"), ("pso", "Memoria personal y social"),
                    ("ga", "Torneo, cruce BLX-α y mutación"), ("sho", "Agrupación dinámica de hienas"),
                    ("woa", "Cerco, exploración y espiral"), ("pso_ga", "PSO con inyección genética (híbrido)"),
                    ("random", "Línea base sin aprendizaje")]
    filas12 = [("Oval 16", "TextBox 17", "TextBox 18"), ("Oval 19", "TextBox 20", "TextBox 21"),
               ("Oval 22", "TextBox 23", "TextBox 24"), ("Oval 25", "TextBox 26", "TextBox 27"),
               ("Oval 28", "TextBox 29", "TextBox 30"), ("Oval 31", "TextBox 32", "TextBox 33")]
    filas12.append(tuple(clonar(s, nombre, nuevo=nombre + " bis").name for nombre in filas12[-1]))
    for k, ((oval, caja_nombre, caja_desc), (alg, desc)) in enumerate(zip(filas12, competidores)):
        y = 2.6 + 0.29 * k
        punto = shape_by_name(s, oval)
        punto.top = Inches(y + 0.04)
        punto.fill.solid()
        punto.fill.fore_color.rgb = RGBColor.from_string(COLOR_ALG[alg])
        for nombre, texto in ((caja_nombre, lab(alg)), (caja_desc, desc)):
            caja = shape_by_name(s, nombre)
            caja.top = Inches(y)
            set_paragraphs(caja, [texto])
    set_text(s, "TextBox 35", "El mismo contrato para todos")
    set_text(s, "TextBox 36", ["El mismo simulador y la misma función objetivo",
                               "La misma codificación del dominio mixto",
                               f"{PRESUPUESTO} solicitudes por corrida; los duplicados cuentan",
                               "Factibilidad por reglas de Deb, sin penalizaciones",
                               "Hiperparámetros canónicos, fijados a priori"])
    set_notes(s, f"[1:10] El híbrido compite contra seis algoritmos. Cinco metaheurísticas clásicas: GWO, PSO, GA, SHO y WOA; "
                 "dos de ellas, PSO y GA, son sus padres. Y una búsqueda aleatoria, RANDOM, que es la línea base: sin ella no "
                 "se puede saber si un algoritmo aprende o solo muestrea. Los colores de esta lista son los mismos de todos "
                 "los gráficos que siguen. Los siete trabajan bajo el mismo contrato: el mismo simulador y la misma función "
                 f"objetivo, la misma codificación del dominio mixto, {PRESUPUESTO} solicitudes por corrida contando los "
                 "diseños repetidos, la factibilidad tratada con las reglas de Deb y los hiperparámetros canónicos de cada "
                 "método, fijados antes de ver resultados. Lo único que cambia entre competidores es el operador de búsqueda. "
                 "[Si preguntan por qué GWO, WOA y SHO, si se los ha criticado como metáforas sin novedad:] Es una crítica "
                 "conocida: Sörensen en 2015 y, en 2023, Camacho-Villalón, Dorigo y Stützle, que muestran que GWO y WOA "
                 "reutilizan ideas de PSO. Por eso no los incluyo por su metáfora ni por su novedad, sino por sus mecanismos, "
                 "y los describo por sus ecuaciones. De hecho, los tres comparten la misma regla de cerco y difieren en la "
                 "guía y en el calendario de contracción. Y los evalúo con el mismo presupuesto, la misma línea base y el "
                 "óptimo exacto, que es lo que piden las guías metodológicas del área.")

    # ======================================================================================
    # SECCIÓN 3 · DISEÑO EXPERIMENTAL
    # ======================================================================================
    # ==== 13. DIVISOR 03 (ex 8)
    divisor(S(8), 3, "Diseño experimental",
            "Cómo se compara de forma justa: un protocolo de siete pasos con las decisiones estadísticas fijadas antes de correr las instancias nuevas.",
            ["Protocolo en siete pasos", "Ocho instancias con óptimo exacto", "Condiciones justas", "Hipótesis y mapa de decisión"],
            "[0:10] Ahora, cómo se compara.")

    # ==== 14. PROTOCOLO EN 7 PASOS (lámina en blanco + formas)
    s = s_protocolo
    titulo(s, "DISEÑO EXPERIMENTAL · PROTOCOLO", "Siete pasos para separar el algoritmo del azar")
    dibujar_protocolo(s, d)
    set_notes(s, "[1:10] La comparación sigue un protocolo de siete pasos, el de la guía de comparación estadística de "
                 "algoritmos estocásticos de mi profesor guía. Uno, diseñar: instancias, réplicas, semillas y el mismo "
                 f"presupuesto; aquí son {N_INST} instancias, {R_DISENO} réplicas y {PRESUPUESTO} solicitudes. Dos, preguntar: las "
                 f"hipótesis y el nivel de significación se fijaron antes de correr las instancias nuevas, I5 a I8; contrastes bilaterales, alfa {alfa} "
                 f"y una tolerancia de {eps} del óptimo. Tres, explorar con descriptivos y gráficos. Cuatro, elegir la prueba "
                 "según cuántos algoritmos y cuántas instancias se comparan y si las muestras son pareadas. Cinco, cuantificar "
                 "con un tamaño de efecto y su intervalo. Seis, corregir por comparaciones múltiples con Holm. Y siete, "
                 "reportar todo, también lo no significativo. Las familias de contrastes también se planificaron: el híbrido "
                 "frente a cada rival, con sus padres y RANDOM como contrastes confirmatorios.")

    # ==== 15. OCHO INSTANCIAS Y ÓPTIMO EXACTO (molde 26)
    s = s_instancias
    titulo(s, "DISEÑO EXPERIMENTAL · INSTANCIAS", "Ocho instancias, cada una con su óptimo exacto")
    que_cambia = {"I1": "referencia: 200 MW, AGSR ≤ 0,20", "I2": "límite de venta a red a la mitad",
                  "I3": "catálogos más finos", "I4": "planta de 300 MW", "I5": "planta de 100 MW",
                  "I6": "100 MW y límite a la mitad", "I7": "300 MW y límite a la mitad", "I8": "límite de venta a red relajado"}
    filas = [["Inst.", "Qué cambia", "Ctot [MW]", "AGSRmáx", "Catálogos", "Diseños enumerados", "Factibles", "Óptimo [CNY/kWh]"]]
    for c in codes:
        filas.append([c, que_cambia.get(c, str(etiqueta[c])), num(inst.loc[c, "total_capacity_mw"], 0), num(inst.loc[c, "agsr_max"], 2),
                      entero(bf.loc[c, "catalogs"]), entero(bf.loc[c, "evaluated"]), pct(bf.loc[c, "feasible_share"], 1),
                      num(bf.loc[c, "optimum_lcoe_cny_per_kwh"], 5)])
    fill_table(s, "Table 5", filas, [0.5, 2.55, 0.8, 1.0, 1.0, 1.3, 0.9, 0.95], font_pt=10, row_height_in=0.29, top_in=1.08)
    caja = shape_by_name(s, "TextBox 6")
    caja.top = Inches(1.08 + 0.29 * len(filas) + 0.2)
    set_paragraphs(caja, [f"Óptimo exacto por fuerza bruta: todos los catálogos sobre W cada {paso_w} MW, {entero(bf_total)} diseños simulados en total. "
                          "La brecha de cada corrida se mide contra un valor conocido, no contra el mejor resultado observado.",
                          "Una variación por vez respecto de I1: límite de venta a red (I2, I8), finura de los catálogos (I3), escala (I4, I5) y sus combinaciones (I6, I7)."])
    set_notes(s, f"[1:00] El banco de pruebas son {len(codes)} instancias del mismo problema. I1 es la de referencia. Las demás "
                 "cambian una cosa a la vez: I2 reduce a la mitad el límite de venta a la red y I8 lo relaja; I3 refina los "
                 "catálogos; I4 e I5 cambian la escala de la planta; e I6 e I7 combinan escala y límite. Así, si un algoritmo "
                 "se comporta distinto en una instancia, la causa está declarada. Y lo que hace posible todo el análisis: "
                 f"cada instancia tiene su óptimo exacto, obtenido por fuerza bruta, enumerando todos los catálogos sobre la "
                 f"capacidad eólica con paso de {paso_w} megavatios; en total, {entero(bf_total)} diseños simulados. Por eso "
                 "la variable de respuesta es la brecha respecto de un óptimo conocido y no respecto del mejor resultado que "
                 "se haya visto. [Si preguntan para qué metaheurísticas si la fuerza bruta resuelve cada instancia] La "
                 "enumeración es el instrumento de medida, no la alternativa. Es posible aquí porque hay una sola variable "
                 "continua, catálogos pequeños y un despacho por reglas que se puede vectorizar; aun así toma entre "
                 f"{bf_min_lo} y {bf_min_hi} minutos por instancia. Con una segunda variable continua, por ejemplo liberando "
                 f"la capacidad total, solo {codes[0]} tardaría unos {dias_2d} días. Una corrida usa {solicitudes} solicitudes, "
                 f"entre {veces_lo} y {veces_hi} veces menos que los diseños de la instancia, y tarda unos {seg_corrida} segundos.")

    # ==== 16. CONDICIONES JUSTAS (molde 5)
    s = s_justas
    titulo(s, "DISEÑO EXPERIMENTAL · CONDICIONES", "Mismo presupuesto y mismas reglas para todos")
    set_text(s, "TextBox 6", str(PRESUPUESTO))
    set_text(s, "TextBox 7", "solicitudes por corrida")
    set_text(s, "TextBox 8", f"Las mismas para los {N_ALG}: {POB} individuos × {ITER} iteraciones. Los diseños duplicados también cuentan, y un contrato rechaza la solicitud {PRESUPUESTO + 1}.")
    set_text(s, "TextBox 10", f"R = {R_DISENO}")
    set_text(s, "TextBox 11", "réplicas por celda")
    set_text(s, "TextBox 12", f"Semillas {SEMILLAS}. Cada algoritmo usa su propio flujo aleatorio: dentro de una instancia las muestras son independientes; entre instancias, pareadas.")
    set_text(s, "TextBox 14", "A priori")
    set_text(s, "TextBox 15", "parámetros y reglas")
    set_text(s, "TextBox 16", "Hiperparámetros canónicos, sin reajuste para el híbrido. Factibilidad por reglas de Deb, igual para todos.")
    total_corridas = N_ALG * N_INST * R_DISENO
    set_text(s, "TextBox 17", [["En total: ", f"{N_ALG} algoritmos × {N_INST} instancias × {R_DISENO} réplicas = {entero(total_corridas)} corridas y {entero(total_corridas * PRESUPUESTO)} simulaciones anuales."]])
    set_notes(s, f"[0:50] Las condiciones de la comparación. El presupuesto: {PRESUPUESTO} solicitudes de evaluación por corrida "
                 f"para todos, {POB} individuos por {ITER} iteraciones; un diseño repetido también gasta una solicitud. Las "
                 f"réplicas: {R_DISENO} por algoritmo e instancia, con semillas fijas. Cada algoritmo usa su propio flujo "
                 "aleatorio, y eso decide la estadística: dentro de una instancia las muestras de dos algoritmos son "
                 "independientes, no forman pares; entre instancias, en cambio, sí se comparan de forma pareada. Y los "
                 f"parámetros y las reglas se fijaron a priori. En total son {entero(total_corridas)} corridas y algo más de un "
                 "millón de simulaciones anuales.")

    # ==== 17. HIPÓTESIS Y MAPA DE DECISIÓN (lámina en blanco + formas)
    s = s_mapa
    titulo(s, "DISEÑO EXPERIMENTAL · PRUEBAS", "Tres preguntas, tres pruebas: el mapa de decisión")
    dibujar_mapa_decision(s, d)
    set_notes(s, f"[1:10] Antes de mirar los datos quedaron fijadas las hipótesis y las pruebas. La hipótesis nula es que los "
                 "algoritmos comparados tienen la misma distribución de brecha; la alternativa, que difieren, en contraste "
                 f"bilateral, con alfa {alfa} y una tolerancia de {eps}. Y el mapa de decisión de la guía, aplicado a tres "
                 "preguntas. P1: en una instancia, ¿el híbrido difiere del rival? Son dos algoritmos y las muestras son "
                 "independientes, así que corresponde Mann-Whitney, con el tamaño de efecto A12 y Holm sobre las "
                 f"{N_INST} instancias. P2: ¿y en general? Dos algoritmos sobre {N_INST} instancias, con una mediana por instancia: "
                 "muestras pareadas, prueba de Wilcoxon de rangos con signo. P3: ¿hay diferencias entre los siete? Tres o más "
                 "algoritmos: Friedman con la corrección de Iman-Davenport, y post-hoc solo si resulta significativo. En los "
                 "tres casos, siempre con un tamaño de efecto.")

    # ======================================================================================
    # SECCIÓN 4 · RESULTADOS (todo el texto de esta sección sale de los CSV)
    # ======================================================================================
    # ==== 18. DIVISOR 04 (ex 13)
    divisor(S(13), 4, "Resultados",
            "Primero explorar; después, tres preguntas, cada una con su prueba, su tamaño de efecto y su corrección.",
            ["Explorar: convergencia y distribución", "P1: en una instancia", "P2: en general", "P3: entre los siete",
             "Lectura: uso del presupuesto"],
            "[0:10] Con eso definido, los resultados.")

    # ==== 19. EXPLORAR: CONVERGENCIA
    s = s_conv
    titulo(s, "RESULTADOS · EXPLORAR", titulo_convergencia(d), dos_lineas=True)
    marca_provisional(s, d)
    add_fig(s, "pres_convergencia.png", 0.5, 1.08)
    conv = lectura_convergencia(d)
    red = conv["reduccion"]
    lider_mitad = enumerar([lab(a) for a in conv["lider_mitad"]])
    add_label(s, 0.5, 4.22, 9.0, 0.5, [
        ["Mediana e IQR ", f"de la brecha al óptimo exacto en {replicas} corridas por algoritmo. Brecha mediana final por instancia: "
                           + frase_brechas_finales(d, ("pso_ga", "pso", "ga", "random")) + "."],
        ["Rango medio de los siete: ", f"PSO+GA es 1.º entre {entero(conv['desde'])} y {entero(conv['hasta'])} solicitudes; "
                                       f"a {entero(conv['mitad'])} lidera {lider_mitad}; desde {entero(conv['estable'])}, "
                                       "ningún algoritmo se aparta más de un lugar de su puesto final."]],
        size=10, ajustar=True)
    g_h = brechas_medianas(d, H)
    set_notes(s, "[1:20] Tercer paso del protocolo: explorar antes de contrastar. Cada panel es una instancia; el eje horizontal "
                 "son las solicitudes acumuladas, de modo que en cada punto todos los algoritmos han gastado lo mismo; el "
                 "vertical es la brecha respecto del óptimo exacto, que es la línea punteada en cero. Las curvas son la "
                 f"mediana de {replicas} corridas y la banda, el rango intercuartil. PSO+GA va en marrón, sus padres PSO y GA en "
                 f"naranja y verde, y RANDOM en gris. Al agotar las {solicitudes} solicitudes, la brecha mediana de PSO+GA "
                 f"va de {rango(g_h)} por ciento según la instancia; la de PSO, de {rango(brechas_medianas(d, 'pso'))}; "
                 f"la de GA, de {rango(brechas_medianas(d, 'ga'))}; y la de RANDOM, de {rango(brechas_medianas(d, 'random'))}. "
                 "Pero las curvas también muestran cuándo se forma el orden. Si en cada punto ordeno a los siete por su brecha "
                 f"mediana y promedio el puesto sobre las ocho instancias, PSO+GA es el primero entre {entero(conv['desde'])} y "
                 f"{entero(conv['hasta'])} solicitudes: es el que converge más rápido. A mitad del presupuesto ya lidera "
                 f"{lider_mitad} y el híbrido es {conv['puesto_h_mitad']}.º; en la segunda mitad su brecha mediana media baja "
                 f"solo un {num(red[H], 0)} por ciento, mientras GWO, SHO y WOA la reducen un {num(red['gwo'], 0)}, un "
                 f"{num(red['sho'], 0)} y un {num(red['woa'], 0)} por ciento. El orden final solo queda fijado desde "
                 f"{entero(conv['estable'])} solicitudes. Todo esto es descriptivo: todavía no dice qué diferencias son reales. "
                 "[Si preguntan si con menos presupuesto ganaría el híbrido:] No se puede concluir. GWO, WOA y SHO bajan su "
                 "parámetro a o h según la fracción de iteraciones transcurridas, así que con menos presupuesto habrían pasado "
                 f"antes a explotar. Lo que sí sostengo es que el orden es relativo a {solicitudes} solicitudes, y que la "
                 "inyección genética se asocia con una convergencia más rápida al principio, sin contrastarla, pero no evita "
                 "que el enjambre se estanque.")

    # ==== 20. EXPLORAR: DISTRIBUCIÓN DE LA BRECHA Y NORMALIDAD
    s = s_brecha
    titulo(s, "RESULTADOS · EXPLORAR", titulo_normalidad(d), dos_lineas=True)
    marca_provisional(s, d)
    add_fig(s, "pres_brecha.png", 0.5, 1.12)
    add_label(s, 0.5, 3.95, 9.0, 0.78, [
        ["Distribución de la brecha final: ", frase_mejores_medianas(d, ("pso_ga", "pso", "ga", "random"))],
        ["Shapiro–Wilk ", frase_normalidad(d)]], size=10, ajustar=True)
    set_notes(s, f"[1:10] La distribución de la brecha final, una caja por algoritmo en cada instancia, con las {replicas} "
                 "corridas dibujadas encima. Lo que importa no es el mejor valor aislado sino la distribución completa. "
                 "Dentro de este grupo de cuatro, " + voz_mejores_medianas(d, ("pso_ga", "pso", "ga", "random")) + " "
                 "Y esta exploración decide el tipo de prueba: las brechas están acotadas por abajo y son asimétricas. "
                 "La prueba de Shapiro-Wilk " + frase_normalidad(d) + " Por eso todas las pruebas que siguen trabajan "
                 "con rangos y ninguna supone normalidad.")

    # ==== 21. P1: Â12 POR INSTANCIA
    s = s_a12
    titulo(s, "RESULTADOS · P1 · EN UNA INSTANCIA", titulo_p1(d), dos_lineas=True)
    marca_provisional(s, d)
    add_fig(s, "pres_a12_foco.png", 0.5, 1.12)
    ancho_panel = 9.0 * 0.94 / 3.14          # geometría de fig_a12 con tres paneles
    for k, b in enumerate(CONFIRMATORIOS):
        add_label(s, 0.5 + 9.0 * 0.05 + k * ancho_panel * 1.07, 3.76, ancho_panel, 0.26,
                  [frase_p1(d, b, sujeto=False)], size=10.5, color=COLOR_ALG[b], align=PP_ALIGN.CENTER, ajustar=True)
    n_p1 = max(conteo_p1(d, H, b)["n"] for b in CONFIRMATORIOS)
    add_label(s, 0.5, 4.1, 9.0, 0.6, [
        ["Cómo leerlo: ", f"Â12 > 0,5 significa que PSO+GA obtiene menor LCOE. Marcador lleno: significativo tras Holm sobre las {n_p1} instancias del par (+ o −); "
                          "vacío: sin evidencia de diferencia (≈). Banda gris: efecto despreciable."],
        ["Prueba: ", f"Mann–Whitney bilateral, α = {alfa}, {replicas} corridas por algoritmo; brechas ≤ {eps} cuentan como 0."]],
        size=9.5, ajustar=True)
    set_notes(s, "[1:10] Primera pregunta: en una instancia, ¿PSO+GA difiere del rival? Cada punto es el tamaño de efecto A12 "
                 "de una instancia con su intervalo bootstrap al 95 por ciento: a la derecha de 0,5, PSO+GA obtiene menor "
                 f"LCOE. El marcador lleno indica que la diferencia es significativa tras corregir con Holm sobre las {n_p1} "
                 "instancias del par, y la banda gris es la zona de efecto despreciable. Son los tres contrastes "
                 "confirmatorios: los dos padres y la línea base. " + voz_p1_grupo(d, ("random", "ga", "pso")))

    # ==== 22. P1: TABLA +/≈/−
    s = s_p1_tabla
    rivales = list(CONFIRMATORIOS) + list(RESTO_CONTROL)
    tot = totales_p1(d, rivales)
    titulo(s, "RESULTADOS · P1 · EN UNA INSTANCIA",
           "PSO+GA frente a sus seis rivales: {} +, {} ≈ y {} − en {} contrastes".format(tot["+"], tot["="], tot["-"], tot["n"]), dos_lineas=True)
    marca_provisional(s, d)
    papel = {"pso": "PSO (padre)", "ga": "GA (padre)", "random": "RANDOM (base)"}
    filas = [["PSO+GA frente a"] + codes + ["+ / ≈ / −"]]
    for b in rivales:
        f = filas_p1(d, H, b)
        c = conteo_p1(d, H, b)
        celdas = ["{} {}".format(SIMB.get(str(f.loc[i, "simbolo"]).strip(), "?"), num(f.loc[i, "a12"], 2)) if i in f.index else "--"
                  for i in codes]
        filas.append([papel.get(b, lab(b))] + celdas + ["{} / {} / {}".format(len(c["+"]), len(c["="]), len(c["-"]))])
    ancho_inst = 6.1 / max(len(codes), 1)
    t = fill_table(s, "Table 5", filas, [1.75] + [ancho_inst] * len(codes) + [1.15], font_pt=10.5, row_height_in=0.33, top_in=1.12)
    for i, b in enumerate(rivales, 1):
        f = filas_p1(d, H, b)
        for j, code in enumerate(codes, 1):
            simbolo = str(f.loc[code, "simbolo"]).strip() if code in f.index else "="
            pintar_celda(t.cell(i, j), fill={"+": VERDE_SUAVE, "-": ROJO_SUAVE}.get(simbolo, "FFFFFF"),
                         bold=simbolo != "=", align=PP_ALIGN.CENTER)
        pintar_celda(t.cell(i, len(codes) + 1), fill=GRIS_SUAVE, bold=True, align=PP_ALIGN.CENTER)
    caja = shape_by_name(s, "TextBox 6")
    caja.top = Inches(1.12 + 0.33 * len(filas) + 0.14)
    set_paragraphs(caja, [f"Cada celda: símbolo y Â12. «+» PSO+GA significativamente mejor, «−» significativamente peor, «≈» sin evidencia de diferencia (Mann–Whitney, Holm sobre las {n_p1} instancias de cada par, α = {alfa}).",
                          "Significativo no es lo mismo que relevante: " + frase_magnitud(d, rivales),
                          "Las tres primeras filas son los contrastes confirmatorios; GWO, SHO y WOA completan la familia de control."])
    encoger(caja, 4.72 - (1.12 + 0.33 * len(filas) + 0.14), 9.0)
    set_notes(s, "[1:10] La misma pregunta para los seis rivales, en una tabla. Un más significa que PSO+GA es "
                 "significativamente mejor en esa instancia; un menos, significativamente peor; y el aproximado, que no hay "
                 "evidencia de diferencia. En total, PSO+GA suma "
                 f"{tot['+']} más, {tot['=']} aproximados y {tot['-']} menos en {tot['n']} contrastes. Las tres primeras "
                 "filas son las de la lámina anterior. En las otras tres: " + voz_p1_grupo(d, RESTO_CONTROL)
                 + " Y una precaución de lectura: significativo no es lo mismo que relevante; por eso cada resultado va con "
                 "su tamaño de efecto. En unidades del problema, " + frase_magnitud(d, rivales))

    # ==== 23. P2: EN GENERAL
    s = s_p2
    titulo(s, "RESULTADOS · P2 · EN GENERAL", titulo_p2(d), dos_lineas=True)
    marca_provisional(s, d)
    filas = [["PSO+GA frente a", "Medianas: gana–empata–pierde", "Wilcoxon p", "p Holm", "p brecha relativa", "p signos", "HL pareado [pp]", "Lectura"]]
    veredictos = []
    for b in rivales:
        f = fila_p2(d, H, b)
        v = veredicto_p2(f)
        veredictos.append(v)
        if f is None:
            filas.append([papel.get(b, lab(b))] + ["--"] * 7)
            continue
        filas.append([papel.get(b, lab(b)), "{}–{}–{}".format(int(f["gana_mediana"]), int(f["empata_mediana"]), int(f["pierde_mediana"])),
                      pvalor(f["p_value"]), pvalor(f["p_value_holm"]), pvalor(f["p_value_relativa"]), pvalor(f["p_value_signos"]),
                      num(f["hl_pareado_gap_pp"], 2), {"mejor": "PSO+GA mejor", "peor": "PSO+GA peor", "sin": "sin evidencia"}.get(v, "--")])
    t = fill_table(s, "Table 5", filas, [1.5, 1.45, 0.95, 0.85, 1.0, 0.85, 1.0, 1.4], font_pt=10, row_height_in=0.3, top_in=1.12)
    t.rows[0].height = Inches(0.44)
    for i, v in enumerate(veredictos, 1):
        for j in range(1, len(filas[0])):
            pintar_celda(t.cell(i, j), align=PP_ALIGN.CENTER)
        pintar_celda(t.cell(i, len(filas[0]) - 1), fill={"mejor": VERDE_SUAVE, "peor": ROJO_SUAVE}.get(v, GRIS_SUAVE), bold=v in ("mejor", "peor"))
    y_pie = 1.12 + 0.44 + 0.3 * (len(filas) - 1) + 0.14
    caja = shape_by_name(s, "TextBox 6")
    caja.top = Inches(y_pie)
    pi = potencia(d, "instancias")
    set_paragraphs(caja, [f"Unidad de análisis: la instancia (una mediana por algoritmo, pareadas). Wilcoxon de rangos con signo, Holm dentro de la familia de control, α = {alfa}. HL < 0: menor brecha de PSO+GA.",
                          "Robustez: " + frase_robustez(d),
                          "Potencia: " + frase_potencia(d) + " «Sin evidencia de diferencia» no significa «iguales»."])
    encoger(caja, 4.74 - y_pie, 8.5)
    set_notes(s, "[1:10] Segunda pregunta: ¿y en general? Aquí la unidad de análisis ya no es la corrida sino la instancia: una "
                 "mediana por algoritmo e instancia, comparadas de forma pareada con la prueba de Wilcoxon de rangos con signo "
                 "y con Holm dentro de la familia. " + voz_p2_grupo(d, CONFIRMATORIOS) + " "
                 + voz_robustez(d) + " Y hay que leer esto con la potencia a la vista: " + frase_potencia_breve(d)
                 + " Por eso, donde no hay significancia, la lectura correcta es «sin evidencia de diferencia», no «son iguales».")

    # ==== 24. P3: FRIEDMAN Y DIFERENCIA CRÍTICA
    s = s_p3
    q3 = p3(d)
    titulo(s, "RESULTADOS · P3 · ENTRE LOS SIETE", titulo_p3(d), dos_lineas=True)
    marca_provisional(s, d)
    add_fig(s, "pres_diferencia_critica.png", 0.5, 1.1)
    add_box(s, 0.5, 3.5, 4.4, 1.2, [], fill=LIGHT, name="P3 tarjeta contraste")
    add_label(s, 0.65, 3.56, 4.1, 1.1, [
        ["Rangos: ", f"por brecha mediana en {q3['n']} instancias (1 = mejor)."],
        ["Friedman: ", frase_friedman(d) + ". ", "Iman–Davenport: ", frase_iman(d) + "."],
        [f"Decisión (α = {alfa}): ", frase_decision_p3(d)]], size=10, ajustar=True)
    add_box(s, 5.1, 3.5, 4.4, 1.2, [], fill=LIGHT, name="P3 tarjeta lectura")
    add_label(s, 5.25, 3.56, 4.1, 1.1, [
        ["PSO+GA: ", frase_puesto(d)],
        ["Post-hoc de Nemenyi: ", frase_posthoc(d)]], size=10, ajustar=True)
    set_notes(s, f"[1:10] Tercera pregunta: ¿hay diferencias entre los {q3['k']} algoritmos? En cada instancia se ordenan los "
                 f"{q3['k']} por su brecha mediana y se promedian esos rangos sobre las {q3['n']} instancias; el diagrama los "
                 "muestra de mejor a peor. El contraste global de Friedman da " + frase_friedman(d).replace("χ²", "ji cuadrado")
                 + "; con la corrección de Iman-Davenport, " + frase_iman(d) + ". Entonces, " + frase_decision_p3(d)
                 + (" En el post-hoc de Nemenyi, " + frase_posthoc(d) if q3["procede"]
                    else " Por eso el diagrama queda como una descripción de los rangos medios, no como un contraste.")
                 + " Las barras negras unen algoritmos cuyos rangos medios difieren menos que la diferencia crítica. "
                 "En cuanto al híbrido: " + frase_puesto(d))

    # ==== 25. LECTURA: USO DEL PRESUPUESTO
    s = s_lectura
    qd = lectura_duplicados(d)
    titulo(s, "RESULTADOS · LECTURA", titulo_duplicados(d), dos_lineas=True)
    marca_provisional(s, d)
    add_fig(s, "pres_duplicados.png", 0.5, 1.15)
    medias = qd["medias"]
    hijos_total = (ITER - 1) * HIJOS
    # Sensibilidad: el mismo protocolo cortando a todos en los diseños únicos del GA.
    fila_u = lambda df, a, b: df[(df["algoritmo_a"] == a) & (df["algoritmo_b"] == b)].iloc[0]
    ga_rnd, ga_rnd_u = fila_u(d["p2"], "ga", "random"), fila_u(d["p2_unicos"], "ga", "random")
    pso_u = fila_u(d["p2_unicos"], H, "pso")
    puesto_ga_u = int(d["ranks_unicos"].index[d["ranks_unicos"]["algorithm"] == "ga"][0]) + 1
    n_alg_u = len(d["ranks_unicos"])
    add_label(s, 6.05, 1.2, 3.45, 3.45, [
        ["Qué se mide: ", "solicitudes que repiten un diseño ya evaluado; cuentan contra el presupuesto y no aportan información."],
        ["Duplicados (media entre instancias): ", "; ".join("{} {} %".format(lab(a), num(medias[a], 1)) for a in ("pso_ga", "pso", "ga", "random") if a in medias.index) + "."],
        ["PSO+GA frente a PSO: ", f"duplica más que su padre en {qd['h_mas_que_pso']} de {qd['n']} instancias."],
        ["Por diseño: ", f"{hijos_total} de las {PRESUPUESTO} solicitudes de PSO+GA ({pct(hijos_total / PRESUPUESTO, 0)}) son hijos del GA."],
        ["A igual nº de diseños únicos: ", f"GA sigue {puesto_ga_u}.º de {n_alg_u}; supera a RANDOM en "
                                          f"{entero(ga_rnd_u['mejor_significativo'])} instancias en vez de {entero(ga_rnd['mejor_significativo'])}."]],
              size=10, ajustar=True, minimo=9.0)
    set_notes(s, "[1:00] Para interpretar lo anterior miré cómo gasta cada algoritmo su presupuesto. Una solicitud duplicada "
                 "es un diseño que ya se había evaluado y se vuelve a pedir: cuenta contra el presupuesto y no aporta "
                 "información nueva. Como la capacidad eólica es continua, un diseño solo se repite cuando un vector se copia: "
                 "la élite del GA, que se vuelve a pedir en cada generación, o un hijo que reproduce a su padre. "
                 f"El que más repite es {lab(qd['mas'])}, con {num(medias[qd['mas']], 1)} por ciento de sus solicitudes en "
                 f"promedio; PSO+GA repite {num(medias.get(H, float('nan')), 1)} por ciento y PSO, {num(medias.get('pso', float('nan')), 1)}. "
                 f"El híbrido duplica más que su padre PSO en {qd['h_mas_que_pso']} de {qd['n']} instancias. Hay que recordar que, "
                 f"por diseño, solo {hijos_total} de sus {PRESUPUESTO} solicitudes son hijos del GA. ¿Cambian las conclusiones si "
                 "solo cuento diseños distintos? Repetí todo el protocolo cortando a cada algoritmo en el número de diseños "
                 f"únicos que alcanza el GA, lo que favorece al GA. El GA sigue {puesto_ga_u}.º de {n_alg_u}. Lo que cambia es su "
                 f"comparación con RANDOM: la supera en {entero(ga_rnd_u['mejor_significativo'])} instancias en vez de "
                 f"{entero(ga_rnd['mejor_significativo'])}, y en general pasa a ser significativa, con p ajustado "
                 f"{num(ga_rnd_u['p_value_holm'], 3)}, aunque la prueba de signos no la respalda. Y la desventaja del híbrido "
                 f"frente a PSO queda en p ajustado {num(pso_u['p_value_holm'], 3)}, por encima de alfa: otra señal de que no es robusta.")

    # ======================================================================================
    # SECCIÓN 5 · CONCLUSIONES
    # ======================================================================================
    # ==== 26. DIVISOR 05 (ex 22)
    divisor(S(22), 5, "Conclusiones",
            "Qué afirmaciones quedan respaldadas por la evidencia, cuáles no, y qué deja el trabajo.",
            ["Qué se puede afirmar y qué no", "Aporte y trabajo futuro"],
            "[0:10] Cierro con las conclusiones.")

    # ==== 27. QUÉ SE PUEDE AFIRMAR Y QUÉ NO (ex 23)
    s = S(23)
    titulo(s, "CONCLUSIONES", "Qué se puede afirmar y qué no")
    marca_provisional(s, d)
    c1 = {b: conteo_p1(d, H, b) for b in CONFIRMATORIOS}
    perdidas = sum(len(c1[b]["-"]) for b in CONFIRMATORIOS)
    p1_resumen = "P1, por instancia (Holm): PSO+GA es mejor que RANDOM en {} de {}, que GA en {} y que PSO en {}".format(
        len(c1["random"]["+"]), n_p1, len(c1["ga"]["+"]), len(c1["pso"]["+"]))
    p1_resumen += f"; es peor en {perdidas} de esos contrastes" if perdidas else ""
    if not perdidas and not any(c1[b]["+"] for b in CONFIRMATORIOS):
        p1_resumen = f"P1, por instancia (Holm): sin evidencia de diferencia frente a RANDOM, GA ni PSO en ninguna de las {n_p1} instancias"
    general = veredicto_general(d)
    p2_resumen = "P2, en general: " + (general if general.startswith("sin") else "PSO+GA " + general)
    p3_resumen = "P3, entre los {}: {} ({}); PSO+GA, puesto {} por rango medio".format(
        q3["k"], "hay diferencias globales" if q3["procede"] else "sin evidencia de diferencias globales",
        ptxt(d["fried"]["iman_davenport_p"]), q3["puesto"])
    set_text(s, "TextBox 6", "Lo que respalda la evidencia")
    set_text(s, "TextBox 7", [f"El problema queda formulado con {len(codes)} instancias y su óptimo exacto ({entero(bf_total)} diseños enumerados)",
                              p1_resumen, p2_resumen, p3_resumen,
                              respuesta_hibridacion(d)[0]])
    encoger(shape_by_name(s, "TextBox 7"), 2.4, 9.0)
    set_text(s, "TextBox 9", "Lo que no se puede afirmar")
    set_text(s, "TextBox 10", ["Que «no significativo» sea «iguales»: " + (f"con {int(pi['n'])} instancias la potencia para un efecto mediano es {num(pi['potencia_dz_0.5'], 2)}" if pi is not None else "la potencia es limitada"),
                               "Que significativo sea relevante: cada p va con su tamaño de efecto y su intervalo",
                               "Generalidad: un sitio, un año meteorológico, instancias paramétricas, un solo presupuesto y LCOE como único objetivo",
                               f"Que la configuración sea la mejor: hiperparámetros a priori y {HIJOS} hijos por iteración, sin ablación"])
    encoger(shape_by_name(s, "TextBox 10"), 2.4, 9.0)
    set_notes(s, "[1:20] ¿Qué queda respaldado? Primero, el problema está formulado y cada instancia tiene su óptimo exacto. "
                 "Segundo, la respuesta a las tres preguntas. Por instancia: " + voz_p1_grupo(d, CONFIRMATORIOS)
                 + " En general, " + ("no hay " + general[4:] if general.startswith("sin ") else "PSO+GA " + general)
                 + ". Y entre los " + str(q3["k"]) + " algoritmos, "
                 + frase_decision_p3(d) + " " + respuesta_hibridacion(d)[1] + " ¿Qué no se puede afirmar? Que no significativo sea lo mismo que iguales: "
                 + frase_potencia_breve(d)
                 + " Que significativo sea relevante: por eso cada valor p va con su tamaño de efecto. Tampoco hay generalidad "
                 "más allá de este banco: un sitio, un año meteorológico, instancias paramétricas, un solo objetivo y un solo "
                 f"presupuesto, con un orden que recién se fija desde {entero(lectura_convergencia(d)['estable'])} solicitudes. Y la "
                 f"configuración del híbrido no se optimizó: {HIJOS} hijos por iteración, sin ablación.")

    # ==== 28. APORTE Y TRABAJO FUTURO (molde 23)
    s = s_futuro
    titulo(s, "CONCLUSIONES", "Aporte y trabajo futuro")
    set_text(s, "TextBox 6", "Aporte")
    set_text(s, "TextBox 7", ["Un híbrido PSO+GA con padres intactos y un contrato de presupuesto que ningún algoritmo puede eludir",
                              f"Óptimo exacto por enumeración vectorizada en {N_INST} instancias: la brecha se mide contra un valor conocido",
                              "El protocolo estadístico de siete pasos implementado como módulo reutilizable: pruebas, tamaño de efecto y Holm",
                              "Tablas, figuras y láminas generadas desde los CSV: cero transcripción manual"])
    set_text(s, "TextBox 9", "Trabajo futuro")
    set_text(s, "TextBox 10", ["Ablación del número de hijos por iteración y de la memoria de los hijos",
                               "Más instancias, años y sitios, para ganar potencia, y varios presupuestos",
                               "Ajuste de hiperparámetros con un presupuesto declarado e igual para todos",
                               "Otros esquemas de hibridación sobre la misma infraestructura",
                               "Capacidad renovable libre, demanda de hidrógeno y formulación multiobjetivo"])
    set_notes(s, "[0:50] El aporte a la Ingeniería Informática tiene cuatro piezas. Un híbrido implementado sin tocar a sus "
                 "padres y bajo un contrato de presupuesto que ningún algoritmo puede eludir. Un óptimo exacto por enumeración "
                 f"vectorizada en {N_INST} instancias, que convierte la comparación en una medición contra un valor conocido. El "
                 "protocolo estadístico implementado como un módulo reutilizable. Y un flujo en el que tablas, figuras y estas "
                 "mismas láminas se generan desde los datos. Como trabajo futuro: una ablación del número de hijos; más "
                 "instancias, años y sitios para ganar potencia, y varios presupuestos, porque el orden depende del que se fije; "
                 "ajuste de hiperparámetros con presupuesto declarado; otros "
                 "esquemas de hibridación; y la formulación multiobjetivo.")

    # ==== 29. CIERRE (ex 25)
    s = S(25)
    set_text(s, "TextBox 4", "Un híbrido medido contra un óptimo conocido, con el mismo presupuesto que sus padres y las preguntas fijadas antes de correr las instancias nuevas.")
    set_text(s, "TextBox 5", "Gracias. ¿Preguntas?")
    set_notes(s, "[0:30] En síntesis: un híbrido medido contra un óptimo conocido, con el mismo presupuesto que sus padres y con "
                 "las preguntas estadísticas fijadas antes de correr las instancias nuevas; y una respuesta que distingue lo que la "
                 "evidencia respalda de lo que no. Muchas gracias; quedo atento a sus preguntas.")

    # ======================================================================================
    # RESPALDO
    # ======================================================================================
    # ==== R1. VALIDACIÓN DEL MODELO CONTRA LI ET AL. (ex 11)
    s = S(11)
    set_text(s, "TextBox 3", "RESPALDO · VALIDACIÓN DEL MODELO")
    ajustar_titulo(s)
    set_notes(s, "[RESPALDO] Usar si preguntan por el simulador. Reconstrucción del modelo de Li et al. (2024) contrastada con "
                 "sus indicadores publicados; es una reproducción parcial, no una equivalencia, y es el mismo simulador para "
                 "los siete algoritmos, las ocho instancias y la fuerza bruta.")

    # ==== R2–R9. CALIDAD FINAL POR INSTANCIA (molde 26)
    for c in codes:
        s = s_calidad[c]
        titulo(s, "RESPALDO · CALIDAD FINAL", f"Calidad final en {c} ({etiqueta[c]})")
        marca_provisional(s, d)
        rk = d["sum"][d["sum"]["instance"] == c].sort_values("ranking_descriptivo")
        filas = [["Algoritmo", "Mediana", "IQR", "Mejor", "Peor", "Brecha med. %", "≤ 0,1 %", "≤ 0,5 %", "≤ 1 %"]]
        for _, r in rk.iterrows():
            filas.append([lab(r["algorithm"]), num(r["median"], 6), num(r["iqr"], 6), num(r["best"], 6), num(r["worst"], 6),
                          num(r["median_gap_pct"], 3), pct(r["success_0.1pct"], 0), pct(r["success_0.5pct"], 0), pct(r["success_1.0pct"], 0)])
        fill_table(s, "Table 5", filas, [1.1, 1.0, 1.0, 1.0, 1.0, 1.1, 0.9, 0.9, 0.9], font_pt=10, row_height_in=0.3)
        o = bf.loc[c]
        corridas_c = int(rk["runs"].max()) if len(rk) else 0
        set_text(s, "TextBox 6", f"LCOE en CNY/kWh. Brecha respecto del óptimo exacto de {c} ({num(o['optimum_lcoe_cny_per_kwh'], 6)}; "
                                 f"W = {num(o['optimum_wind_mw'], 2)} MW, E = {num(o['optimum_electrolyzer_mw'], 1)} MW, B = {num(o['optimum_battery_mw'], 1)} MW × {num(o['optimum_battery_duration_h'], 0)} h). "
                                 f"{corridas_c} corridas por algoritmo; factibles, como mínimo, {int(rk['feasible_runs'].min()) if len(rk) else 0} de {corridas_c}. "
                                 "Las tres últimas columnas son la fracción de corridas a menos de esa brecha.")
        set_notes(s, f"[RESPALDO] Usar si preguntan por valores exactos en {c}. Mediana, IQR, mejor, peor, brecha mediana al "
                     f"óptimo exacto y tasas de éxito de los {len(rk)} algoritmos, ordenados por mediana.")

    # ==== R10. HIPERPARÁMETROS DE LOS SIETE (ex 27)
    s = S(27)
    titulo(s, "RESPALDO · CONFIGURACIÓN", "Configuración de los siete algoritmos")
    filas = [["Código", "Familia", "Configuración"]]
    for _, r in d["hyper"].iterrows():
        filas.append([lab(r["codigo"]), acentuar(r["familia"]), acentuar(r["hiperparametros"])])
    fill_table(s, "Table 5", filas, [1.0, 1.9, 6.1], font_pt=9.5, row_height_in=0.3)
    set_text(s, "TextBox 6", [f"Población {POB} × {ITER} iteraciones = {PRESUPUESTO} solicitudes por corrida · semillas de réplica {SEMILLAS} · flujo aleatorio propio por algoritmo y réplica · sin ajuste posterior.",
                              f"PSO+GA: {HIJOS} hijos por iteración, sin memoria; PSO y operadores del GA con los mismos valores que sus versiones puras."])
    set_notes(s, "[RESPALDO] Usar si preguntan por hiperparámetros. Valores canónicos de la literatura; nada se reajusta para el híbrido.")

    # ==== R11. PSO+GA FRENTE A GWO, SHO Y WOA
    s = s_resto
    tot_r = totales_p1(d, RESTO_CONTROL)
    titulo(s, "RESPALDO · P1 Y P2", "PSO+GA frente a GWO, SHO y WOA: {} +, {} ≈ y {} − por instancia".format(tot_r["+"], tot_r["="], tot_r["-"]), dos_lineas=True)
    marca_provisional(s, d)
    add_fig(s, "pres_a12_control_resto.png", 0.5, 1.12)
    for k, b in enumerate(RESTO_CONTROL):
        add_label(s, 0.5 + 9.0 * 0.05 + k * ancho_panel * 1.07, 3.76, ancho_panel, 0.26,
                  [frase_p1(d, b, sujeto=False)], size=10.5, color=COLOR_ALG[b], align=PP_ALIGN.CENTER, ajustar=True)
    add_label(s, 0.5, 4.1, 9.0, 0.62, [["En general (Wilcoxon, Holm): ", "; ".join(
        "frente a {}, {} ({})".format(lab(b), LECTURA_P2[veredicto_p2(fila_p2(d, H, b))].format(a="PSO+GA"),
                                      "p Holm = " + pvalor(fila_p2(d, H, b)["p_value_holm"]) if fila_p2(d, H, b) is not None else "sin datos")
        for b in RESTO_CONTROL) + "."],
        ["Lectura: ", "contrastes de la familia de control que no son confirmatorios; misma prueba y misma corrección que en el cuerpo."]],
        size=9.5, ajustar=True)
    set_notes(s, "[RESPALDO] Usar si preguntan por el híbrido frente a los otros clásicos. Por instancia: "
                 + voz_p1_grupo(d, RESTO_CONTROL) + " En general: " + voz_p2_grupo(d, RESTO_CONTROL)
                 + " " + respuesta_recorte(d))

    # ==== R12. CADA CLÁSICA FRENTE A RANDOM
    s = s_base
    n_aprenden = [a for a in CLASICAS if veredicto_p2(fila_p2(d, a, "random")) == "mejor"]
    titulo(s, "RESPALDO · LÍNEA BASE", "Frente a RANDOM, en general: {} de {} clásicas con ventaja significativa".format(len(n_aprenden), len(CLASICAS)), dos_lineas=True)
    marca_provisional(s, d)
    add_fig(s, "pres_a12_linea_base.png", 0.5, 1.12)
    ancho5 = 9.0 * 0.94 / 5.28               # geometría de fig_a12 con cinco paneles
    for k, a in enumerate(CLASICAS):
        c = conteo_p1(d, a, "random")
        add_label(s, 0.5 + 9.0 * 0.05 + k * ancho5 * 1.07, 3.76, ancho5, 0.26,
                  ["+ {} · ≈ {} · − {}".format(len(c["+"]), len(c["="]), len(c["-"]))], size=10.5, color=COLOR_ALG[a], align=PP_ALIGN.CENTER)
    add_label(s, 0.5, 4.1, 9.0, 0.62, [["En general (Wilcoxon, Holm en la familia «línea base»): ", "; ".join(
        "{} {}".format(lab(a), "p = " + pvalor(fila_p2(d, a, "random")["p_value_holm"]) if fila_p2(d, a, "random") is not None else "sin datos")
        for a in CLASICAS) + "."],
        ["Lectura: ", "«+» la metaheurística es significativamente mejor que la búsqueda aleatoria en esa instancia; «≈» sin evidencia de diferencia."]],
        size=9.5, ajustar=True)
    set_notes(s, "[RESPALDO] Usar si preguntan si las clásicas aprenden. Familia «línea base»: cada clásica frente a RANDOM. "
                 + voz_base_grupo(d))

    # ==== R13. RANGOS POR INSTANCIA (molde 26)
    s = s_rangos
    titulo(s, "RESPALDO · P3", "Rangos por instancia del contraste de Friedman")
    marca_provisional(s, d)
    cols_rango = [c for c in codes if "rank_" + c in d["ranks"].columns]
    filas = [["Algoritmo"] + cols_rango + ["Rango medio"]]
    for _, r in d["ranks"].iterrows():
        filas.append([lab(r["algorithm"])] + [num(r["rank_" + c], 1).replace(",0", "") for c in cols_rango] + [num(r["mean_rank"], 2)])
    t = fill_table(s, "Table 5", filas, [1.5] + [6.2 / max(len(cols_rango), 1)] * len(cols_rango) + [1.3], font_pt=10.5, row_height_in=0.31)
    for i, (_, r) in enumerate(d["ranks"].iterrows(), 1):
        if r["algorithm"] == H:
            for j in range(len(filas[0])):
                pintar_celda(t.cell(i, j), fill=GRIS_SUAVE, bold=True)
    set_text(s, "TextBox 6", f"Rango de cada algoritmo por brecha mediana (con tolerancia ε = {eps}) en cada instancia; 1 = mejor, los empates comparten rango. "
                             f"Friedman: {frase_friedman(d)}. Iman–Davenport: {frase_iman(d)}. Diferencia crítica de Nemenyi: {num(q3['cd'], 2)}.")
    set_notes(s, "[RESPALDO] Usar si preguntan de dónde sale el diagrama de diferencia crítica: son los rangos por instancia sobre la brecha mediana.")

    # ==== R14. OPERACIÓN DE TRES DÍAS (ex 10)
    s = S(10)
    set_text(s, "TextBox 3", "RESPALDO · OPERACIÓN")
    ajustar_titulo(s)
    set_notes(s, "[RESPALDO] Usar si preguntan cómo opera un diseño: tres días de mayo de un diseño de la instancia de referencia, del estudio de avance.")

    # ==== R15–R17. SENSIBILIDAD, SUPUESTOS Y PARÁMETROS (ex 29, 30, 31: intactas)
    for n in (29, 30, 31):
        s = S(n)
        ajustar_titulo(s)                  # el texto no cambia; solo el cuerpo de letra si no cabe en una línea
        set_notes(s, s.notes_slide.notes_text_frame.text if s.has_notes_slide else "[RESPALDO]")

    # ======================================================================================
    # ORDEN FINAL
    # ======================================================================================
    cuerpo = [S(1), S(2),
              S(3), S(4), S(9), S(5), S(7),
              S(6), s_padres, s_pipe_alg, s_pipe_detalle, S(12),
              S(8), s_protocolo, s_instancias, s_justas, s_mapa,
              S(13), s_conv, s_brecha, s_a12, s_p1_tabla, s_p2, s_p3, s_lectura,
              S(22), S(23), s_futuro, S(25)]
    respaldo = ([S(11)] + [s_calidad[c] for c in codes]
                + [S(27), s_resto, s_base, s_rangos, S(10), S(29), S(30), S(31)])
    reorder_and_prune(prs, cuerpo + respaldo)

    args.salida.parent.mkdir(parents=True, exist_ok=True)
    try:
        prs.save(str(args.salida))
    except PermissionError:
        raise SystemExit(f"No se pudo escribir {args.salida.name}: está abierto en PowerPoint. Ciérrelo y vuelva a ejecutar.")

    # ---- Esquema y tiempos (las notas del cuerpo empiezan con [m:ss]) --------------------
    total = 0
    for n, slide in enumerate(cuerpo + respaldo, 1):
        nota = slide.notes_slide.notes_text_frame.text if slide.has_notes_slide else ""
        m = re.match(r"\[(\d+):(\d\d)\]", nota)
        total += int(m.group(1)) * 60 + int(m.group(2)) if m else 0
        etiqueta_t = m.group(0) if m else "[resp.]"
        textos = [sh.text_frame.text for sh in slide.shapes if sh.has_text_frame and sh.name in ("TextBox 4", "TextBox 5", "TextBox 8")]
        nombre = next((t for t in textos if len(t) > 3), textos[0] if textos else "")
        print(f"{n:>2} {etiqueta_t:>8}  {nombre[:95]}")
    print("{} -> {} láminas de cuerpo ({}:{:02d} min) + {} de respaldo".format(
        args.salida, len(cuerpo), total // 60, total % 60, len(respaldo)))
    if d["provisional"]:
        print("AVISO:", d["aviso"], "- las láminas de resultados llevan la marca; vuelva a ejecutar con la corrida completa.")


if __name__ == "__main__":
    main()
