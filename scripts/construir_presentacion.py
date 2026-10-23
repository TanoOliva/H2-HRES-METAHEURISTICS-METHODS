"""Construye la presentación de la defensa a partir del deck de avance.

Conserva la plantilla (paleta, logo, banda inferior, tipografía) del deck
``presentacion/Presentacion_avance_tesis_LOliva.pptx`` y reescribe el guion con una
organización centrada en el método: la pregunta y el pipeline del híbrido PSO+GA
primero, el problema y las cuatro instancias como banco de pruebas, la validación en
tres bloques (correctitud, calidad, aporte) y las conclusiones. Los otros dos híbridos
del documento quedan en respaldo. Todos los números salen de ``notebooks/results``.

Uso:
    python scripts/figuras_presentacion.py          # figuras pres_*.png
    python scripts/construir_presentacion.py        # escribe el .pptx de la defensa
"""

from __future__ import annotations

import copy
from pathlib import Path

import pandas as pd
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE, PP_PLACEHOLDER
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "notebooks" / "results"
FIGS_TESIS = ROOT / "latex" / "figures"
FIGS_PRES = ROOT / "presentacion" / "figuras"
ORIGEN = ROOT / "presentacion" / "Presentacion_avance_tesis_LOliva.pptx"
DESTINO = ROOT / "presentacion" / "Presentacion_defensa_tesis_LOliva.pptx"

LABELS = {"gwo": "GWO", "pso": "PSO", "ga": "GA", "sho": "SHO", "woa": "WOA",
          "ga_ls": "GA+LS", "pso_ga": "PSO+GA", "sho_ls": "SHO+LS", "random": "RANDOM"}
HYBRID_PAIRS = (("ga_ls", "ga"), ("pso_ga", "pso"), ("pso_ga", "ga"), ("sho_ls", "sho"))

# Paleta de la plantilla
NAVY, BLUE, LIGHT, TEXT = "3C4975", "497DB5", "F1F4F9", "33333D"
RED, CYAN, GREEN, BROWN = "E53A34", "57B6D0", "1BAF7A", "A8431A"


# --------------------------------------------------------------------------- utilidades
def lab(a: str) -> str:
    return LABELS.get(str(a), str(a).upper())


def num(x, d=2) -> str:
    return f"{float(x):.{d}f}".replace(".", ",")


def entero(x) -> str:
    return f"{int(round(float(x))):,}".replace(",", ".")


def pct(x, d=1) -> str:
    return num(100 * float(x), d) + " %"


def truthy(v) -> bool:
    return str(v).strip().lower() in ("true", "1", "1.0")


def pvalor(p) -> str:
    try:
        p = float(p)
    except (TypeError, ValueError):
        return "--"
    if pd.isna(p):
        return "--"
    if p < 0.001:
        return "{:.1e}".format(p).replace(".", ",").replace("e-0", "·10⁻").replace("e-", "·10⁻")
    return num(p, 3)


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


def replace_picture(slide, name: str, path: Path) -> None:
    """Sustituye la imagen de un `Picture` y la ajusta dentro de su caja original."""
    pic = shape_by_name(slide, name)
    _, rid = slide.part.get_or_add_image_part(str(path))
    pic._element.blipFill.blip.rEmbed = rid
    iw, ih = Image.open(path).size
    bw, bh = pic.width, pic.height
    escala = min(bw / iw, bh / ih)
    pic.width = Emu(int(iw * escala))
    pic.height = Emu(int(ih * escala))


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
               font_pt: float | None = None, row_height_in: float | None = None) -> None:
    table = shape_by_name(slide, name).table
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


def set_bullets(slide, items: list[str], pares: list[tuple[str, str]]) -> None:
    """Rellena las viñetas de un divisor (óvalo + texto) y borra las sobrantes."""
    for k, (oval, caja) in enumerate(pares):
        if k < len(items):
            set_text(slide, caja, items[k])
        else:
            delete_shapes(slide, (oval, caja))


# --------------------------------------------------------------------------- dibujo de pipelines
def add_box(slide, x, y, w, h, lines, fill=NAVY, color="FFFFFF", size=9.5, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
            bold_first=True, name=None):
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
        r.font.size = Pt(size + 1 if i == 0 else size)
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


def add_label(slide, x, y, w, h, paras, size=10.5, color=TEXT, align=PP_ALIGN.LEFT, bold_label=True):
    """Caja de texto con párrafos; cada párrafo es str o [etiqueta_negrita, texto]."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.02)
    for i, item in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(4)
        runs = [item] if isinstance(item, str) else list(item)
        for k, texto in enumerate(runs):
            r = p.add_run()
            r.text = texto
            r.font.size = Pt(size)
            r.font.bold = bool(k == 0 and len(runs) > 1 and bold_label)
            r.font.color.rgb = RGBColor.from_string(color)
            r.font.name = "Roboto"
    return tb


def dibujar_pipeline_experimental(slide, d):
    """Flujo datos → simulador → instancia → optimizador → réplicas → estadística, con el óptimo exacto."""
    meta, bf = d["meta"], d["bf"]
    y, h, w, gap, x0 = 1.15, 1.0, 1.36, 0.165, 0.5
    cajas = [
        ("Datos", "NASA POWER 2008", "8.760 h, sin 29/02"),
        ("Simulador horario", "despacho secuencial", "reproducción parcial de Li et al."),
        ("Instancia", "(Ctot, AGSRmax, u,", "ΔB, {hk}) · I1 a I4"),
        ("Optimizador", "{} solicitudes".format(int(meta["requests_per_run"])), "PSO+GA y 8 comparadores"),
        ("{} réplicas".format(int(meta["replicates_per_algorithm"])), "por algoritmo e instancia", "semillas 42–71"),
        ("Estadística", "mediana, brecha, éxito", "A12 + Holm (familia planificada)"),
    ]
    xs = []
    for k, (t1, t2, t3) in enumerate(cajas):
        x = x0 + k * (w + gap)
        xs.append(x)
        add_box(slide, x, y, w, h, [t1, t2, t3], fill=NAVY if k != 3 else BROWN, size=8.5, name=f"Pipeline {k + 1}")
        if k:
            add_arrow(slide, x - gap + 0.01, y + h / 2, x - 0.01, y + h / 2)
    # Óptimo exacto: sale del simulador y entra como referencia de la estadística.
    ox, oy, ow, oh = xs[1] + 0.2, 2.65, 3.1, 0.72
    add_box(slide, ox, oy, ow, oh,
            ["Óptimo exacto por fuerza bruta",
             "todos los catálogos × W cada 0,01 MW · {} diseños · {:.0f} h".format(entero(meta["brute_force_designs_total"]), bf["elapsed_s"].sum() / 3600)],
            fill=LIGHT, color=TEXT, size=8.5, name="Pipeline optimo")
    add_arrow(slide, xs[1] + w / 2, y + h + 0.01, xs[1] + w / 2, oy - 0.01, color=BLUE)
    add_arrow(slide, ox + ow + 0.01, oy + oh / 2, xs[5] + w / 2, y + h + 0.01, color=BLUE)
    add_label(slide, 0.5, 3.6, 9.0, 1.1, [
        ["Un solo simulador para todo: ", "los nueve optimizadores, las cuatro instancias y la fuerza bruta evalúan diseños con el mismo modelo; lo único que cambia entre competidores es el operador de búsqueda."],
        ["El óptimo exacto ", "convierte la brecha en una distancia a un valor conocido; la referencia de malla de 0,5 MW ya no hace falta."],
        ["Salida: ", "CSV por instancia → tablas, macros y figuras del documento y de esta presentación, sin transcripción manual."],
    ], size=10)


def dibujar_pipeline_psoga(slide, d):
    """Bucle de PSO en la fila superior, inyección genética en la inferior, cierre con el presupuesto."""
    meta = d["meta"]
    pop, it, budget = int(meta["population"]), int(meta["iterations"]), int(meta["requests_per_run"])
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
        ("5 · Elegir", "las 5 partículas de", "peor mérito actual"),
        ("6 · Torneo", "k = 3 sobre las mejores", "posiciones personales (pbest)"),
        ("7 · Cruce BLX-α", "pc = 0,9 · α = 0,5", "si no, clona al padre"),
        ("8 · Mutación", "gaussiana por gen", "pm = 0,1 · σ = 10 % del rango"),
        ("9 · Hijos", "reemplazan a las 5 peores", "v = 0 · sin memoria (pbest = ∞)"),
    ]
    x2s = []
    for k, (t1, t2, t3) in enumerate(fila2):
        x = 0.5 + (4 - k) * (w2 + g2)      # el flujo corre hacia la izquierda
        x2s.append(x)
        add_box(slide, x, y2, w2, h2, [t1, t2, t3], fill=BROWN, size=8.5, name=f"GA {k + 5}")
        if k:
            add_arrow(slide, x2s[k - 1] - 0.01, y2 + h2 / 2, x + w2 + 0.01, y2 + h2 / 2, color=BROWN)
    add_arrow(slide, x1s[3] + w1 / 2, y1 + h1 + 0.01, x2s[0] + w2 / 2, y2 - 0.01, color=BROWN)
    add_label(slide, x2s[4], y2 + h2 + 0.02, 5.0, 0.3, [["Inyección genética: ", "lo único que añade el híbrido; el bucle de PSO no cambia."]], size=9, color=BROWN)
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
        ["Contrato: ", "toda solicitud pasa por _evaluate_budgeted (tope duro y checkpoint cada 20); al cierre se verifica el total."],
        ["Padres intactos: ", "PSO con constricción de Clerc–Kennedy; operadores y valores del GA sin cambios."],
    ], size=9)


# --------------------------------------------------------------------------- datos
def cargar_datos():
    d = {}
    d["inst"] = pd.read_csv(RESULTS / "instances.csv")
    d["codes"] = list(d["inst"]["instance"])
    d["bf"] = pd.read_csv(RESULTS / "brute_force_summary.csv").set_index("instance")
    d["rank"] = pd.read_csv(RESULTS / "algorithm_summary.csv")
    d["cross"] = pd.read_csv(RESULTS / "cross_instance_ranking.csv")
    d["tests"] = pd.read_csv(RESULTS / "pairwise_tests.csv")
    d["hyb"] = pd.read_csv(RESULTS / "hybrid_vs_parent.csv")
    d["meta"] = pd.read_csv(RESULTS / "experiment_metadata.csv").iloc[0]
    d["hyper"] = pd.read_csv(RESULTS / "algorithm_hyperparameters.csv")
    d["comp"] = pd.read_csv(RESULTS / "brute_force_comparison.csv")
    return d


def fila_rank(d, code, alg):
    r = d["rank"][(d["rank"]["instance"] == code) & (d["rank"]["algorithm"] == alg)]
    return r.iloc[0]


def contraste(d, code, a, b):
    t = d["tests"]
    s = t[(t["family"] == "planned") & (t["instance"] == code) & (t["algoritmo_a"] == a) & (t["algoritmo_b"] == b)]
    return s.iloc[0] if not s.empty else None


# --------------------------------------------------------------------------- construcción
def main() -> None:
    global NOTAS_MODELO
    d = cargar_datos()
    codes = d["codes"]
    meta, bf, cross, hyb = d["meta"], d["bf"], d["cross"], d["hyb"]
    inst = d["inst"].set_index("instance")
    etiqueta = {c: inst.loc[c, "label"] for c in codes}
    replicas = int(meta["replicates_per_algorithm"])
    presupuesto = int(meta["requests_per_run"])
    n_alg = int(meta["algorithms"])
    total_req = int(meta["total_requests"])
    bf_total = int(meta["brute_force_designs_total"])
    bf_horas = bf["elapsed_s"].sum() / 3600.0
    H = "pso_ga"
    hr = {c: fila_rank(d, c, H) for c in codes}
    vs = {(c, b): contraste(d, c, H, b) for c in codes for b in ("random", "pso", "ga")}
    gana = {b: [c for c in codes if vs[(c, b)] is not None and truthy(vs[(c, b)]["significativo_alpha_0.05"]) and vs[(c, b)]["a12"] > 0.5]
            for b in ("random", "pso", "ga")}
    mejor_med = {b: [c for c in codes if hr[c]["median"] < fila_rank(d, c, b)["median"]] for b in ("pso", "ga")}
    mejores_corridas = {}
    for c in codes:
        sub = d["comp"][(d["comp"]["instance"] == c) & (d["comp"]["algorithm"] != "fuerza_bruta")].iloc[0]
        mejores_corridas[c] = sub
    corridas_psoga = [c for c in codes if mejores_corridas[c]["algorithm"] == H]
    primero = cross.iloc[0]
    rank_h = cross[cross["algorithm"] == H].iloc[0]

    prs = Presentation(str(ORIGEN))
    orig = list(prs.slides)
    S = lambda n: orig[n - 1]
    NOTAS_MODELO = S(1).notes_slide

    # ----------------------------------------------------------- duplicados (plantillas)
    s_pregunta = duplicate_slide(prs, S(5))
    s_pipe_exp = duplicate_slide(prs, S(23))
    s_pipe_alg = duplicate_slide(prs, S(23))
    s_padres = duplicate_slide(prs, S(23))
    s_instancias = duplicate_slide(prs, S(26))
    s_optimo = duplicate_slide(prs, S(15))
    s_correcto = duplicate_slide(prs, S(5))
    s_exito = duplicate_slide(prs, S(15))
    s_aporte = duplicate_slide(prs, S(16))
    s_presupuesto = duplicate_slide(prs, S(15))
    s_futuro = duplicate_slide(prs, S(23))
    s_calidad = {c: duplicate_slide(prs, S(26)) for c in codes}
    s_matrices = duplicate_slide(prs, S(21))
    s_otros = duplicate_slide(prs, S(16))

    # =========================================================== 1. PORTADA
    s = S(1)
    set_text(s, "TextBox 7", [["Defensa de Proyecto de ", "Título"]])
    set_notes(s, "[0:30] Buenos días. Mi nombre es Luciano Oliva y presento la defensa de mi proyecto de título. La idea que "
                 "defiendo cabe en una frase: una metaheurística híbrida, PSO con inyección genética, se puede validar de forma "
                 "honesta sobre un problema de dimensionamiento con óptimo conocido, en cuatro instancias y con el mismo "
                 "presupuesto que los métodos de los que parte. Voy a mostrar el método, el banco de pruebas y esa validación.")

    # =========================================================== 2. ÍNDICE (4 secciones)
    s = S(2)
    filas = [("TextBox 8", "TextBox 9", "El método: PSO+GA", "La pregunta, el pipeline experimental y el pipeline del híbrido; qué se conserva de PSO y de GA."),
             ("TextBox 13", "TextBox 14", "Banco de pruebas", "El problema de dimensionamiento, por qué es difícil, cuatro instancias y su óptimo exacto."),
             ("TextBox 18", "TextBox 19", "Validación", "Correctitud, calidad (convergencia, brecha, éxito) y aporte frente a RANDOM, GA y PSO."),
             ("TextBox 23", "TextBox 24", "Conclusiones", "Qué se puede afirmar, límites y trabajo futuro.")]
    for a, b, t, sub in filas:
        set_text(s, a, t)
        set_text(s, b, sub)
    delete_shapes(s, ("Rounded Rectangle 26", "Oval 27", "TextBox 28", "TextBox 29"))
    set_notes(s, "[0:30] Cuatro partes. Primero el método: la pregunta y los dos pipelines, el experimental y el del algoritmo. "
                 "Segundo, el banco de pruebas: el problema, sus instancias y el óptimo exacto. Tercero, la validación en tres "
                 "bloques: que el híbrido es correcto, qué tan cerca del óptimo llega y si aporta algo frente a sus padres. "
                 "Y cuarto, las conclusiones. Tengo respaldo con tablas completas y con los otros dos híbridos del documento.")

    # =========================================================== 3. DIVISOR 01
    s = S(3)
    set_text(s, "TextBox 3", "SECCIÓN 1 DE 4")
    set_text(s, "TextBox 5", "El método: PSO+GA")
    set_text(s, "TextBox 7", "Qué pregunta se responde, cómo fluye el experimento y qué hace exactamente el híbrido en cada iteración.")
    set_bullets(s, ["Pipeline experimental y pipeline del algoritmo", "Qué se conserva de PSO y de GA"],
                [("Oval 10", "TextBox 11"), ("Oval 12", "TextBox 13")])
    set_notes(s, "[0:10] Empiezo por el método.")

    # =========================================================== 4. LA PREGUNTA (plantilla 5)
    s = s_pregunta
    set_text(s, "TextBox 3", "EL MÉTODO · LA PREGUNTA")
    set_text(s, "TextBox 4", "Una pregunta medible")
    set_text(s, "TextBox 6", "1")
    set_text(s, "TextBox 7", "híbrido: PSO+GA")
    set_text(s, "TextBox 8", "El bucle de PSO intacto; al cierre de cada iteración, las 5 peores partículas se reemplazan por hijos de los operadores del GA.")
    set_text(s, "TextBox 10", str(len(codes)))
    set_text(s, "TextBox 11", "instancias resueltas")
    set_text(s, "TextBox 12", "Variantes de un mismo problema de dimensionamiento, cada una con su óptimo exacto por fuerza bruta: la brecha se mide contra un valor conocido.")
    set_text(s, "TextBox 14", "3")
    set_text(s, "TextBox 15", "contrastes planificados")
    set_text(s, "TextBox 16", "¿Aprende? (vs RANDOM). ¿Supera al donante de operadores? (vs GA). ¿Aporta la inyección? (vs PSO). Mismo presupuesto en todos.")
    set_text(s, "TextBox 17", [["Pregunta: ", f"con {presupuesto} solicitudes por corrida, ¿PSO+GA llega al óptimo exacto con más fiabilidad que RANDOM y que los métodos de los que parte?"]])
    set_notes(s, "[1:00] La pregunta en una frase. El objeto de validación es un híbrido: PSO con inyección genética. Se valida "
                 "sobre cuatro instancias de un problema de dimensionamiento, cada una con su óptimo exacto obtenido por fuerza "
                 "bruta, de modo que la brecha se mide contra un valor conocido. Y la validación son tres contrastes planificados "
                 "por instancia: contra la búsqueda aleatoria, para saber si aprende; contra el GA, que dona los operadores; y "
                 "contra el PSO, que es el bucle base, para saber si la inyección aporta algo. Todo con el mismo presupuesto.")

    # =========================================================== 5. PIPELINE EXPERIMENTAL (plantilla 23 vacía)
    s = s_pipe_exp
    set_text(s, "TextBox 3", "EL MÉTODO · PIPELINE EXPERIMENTAL")
    set_text(s, "TextBox 4", "De los datos a la evidencia: el pipeline experimental")
    delete_shapes(s, ("Rounded Rectangle 5", "TextBox 6", "TextBox 7", "Rounded Rectangle 8", "TextBox 9", "TextBox 10"))
    dibujar_pipeline_experimental(s, d)
    set_notes(s, "[1:30] Este es el flujo completo. Los datos meteorológicos horarios de un año alimentan un simulador que reconstruye "
                 "el sistema de Li y colaboradores y que validé contra sus indicadores. Sobre ese simulador se define una instancia "
                 "con sus parámetros; el optimizador recibe seiscientas solicitudes por corrida; se hacen treinta corridas por "
                 "algoritmo e instancia; y la estadística compara medianas, brechas y tasas de éxito con contrastes planificados. "
                 "La pieza nueva es la de abajo: el mismo simulador, vectorizado, enumera todos los diseños de cada instancia y "
                 f"entrega el óptimo exacto, {entero(bf_total)} diseños en unas {num(bf_horas, 0)} horas. Ese óptimo entra en la "
                 "estadística como referencia de todas las brechas.")

    # =========================================================== 6. PIPELINE DEL ALGORITMO
    s = s_pipe_alg
    set_text(s, "TextBox 3", "EL MÉTODO · PIPELINE DEL ALGORITMO")
    set_text(s, "TextBox 4", "Qué hace PSO+GA en cada iteración")
    delete_shapes(s, ("Rounded Rectangle 5", "TextBox 6", "TextBox 7", "Rounded Rectangle 8", "TextBox 9", "TextBox 10"))
    dibujar_pipeline_psoga(s, d)
    set_notes(s, "[2:00] Y este es el algoritmo. La fila de arriba es el PSO sin cambios: se inicializan veinte partículas, se evalúa "
                 "cada una decodificando el vector y simulando el año completo, lo que cuenta una solicitud; se actualizan la memoria "
                 "personal y la global; y se mueven con la constricción de Clerc y Kennedy. La fila de abajo es lo que añade el "
                 "híbrido, la inyección genética: se toman las cinco partículas de peor mérito en esa iteración, se eligen padres por "
                 "torneo sobre las mejores posiciones personales del enjambre, se cruzan con BLX-alfa, se mutan con la gaussiana del GA "
                 "y los hijos reemplazan a esas cinco partículas con velocidad cero y sin memoria. Se repite hasta completar exactamente "
                 "seiscientas solicitudes, las mismas que el PSO puro, y la salida es el mejor diseño. Dos cosas importantes: el "
                 "contrato de presupuesto impide pedir la solicitud seiscientos uno, y ni el PSO ni los operadores del GA se tocan: así "
                 "cualquier diferencia se atribuye a la inyección.")

    # =========================================================== 7. LOS PADRES (plantilla 23)
    s = s_padres
    set_text(s, "TextBox 3", "EL MÉTODO · LOS PADRES")
    set_text(s, "TextBox 4", "Qué se conserva de PSO y qué se toma de GA")
    set_text(s, "TextBox 6", "PSO: el bucle que se conserva")
    set_text(s, "TextBox 7", ["Enjambre de 20 partículas con memoria personal (pbest) y social (gbest)",
                              "Constricción de Clerc y Kennedy: χ = 0,729, c1 = c2 = 1,49445",
                              "Velocidad acotada al 20 % del rango de cada variable",
                              "30 iteraciones × 20 = 600 solicitudes; sin ningún cambio en el híbrido"])
    set_text(s, "TextBox 9", "GA: los operadores que se inyectan")
    set_text(s, "TextBox 10", ["Selección por torneo de tamaño 3",
                               "Cruce BLX-α con α = 0,5 y probabilidad 0,9",
                               "Mutación gaussiana por gen: p = 0,1, σ = 10 % del rango",
                               "Los mismos valores que usa el GA puro del banco: nada se reajusta para el híbrido"])
    set_notes(s, "[1:00] Para que la comparación híbrido contra padre sea honesta, los padres no se tocan. Del PSO se conserva todo: "
                 "el enjambre, las memorias, la constricción y la velocidad acotada. Del GA se toman sus tres operadores, torneo, "
                 "cruce BLX-alfa y mutación gaussiana, con exactamente los mismos hiperparámetros que usa el GA puro en el banco. "
                 "Nada se reajusta para el híbrido; los valores son los canónicos de la literatura y se fijaron antes de ver resultados.")

    # =========================================================== 8. REGLAS DEL CONTRATO (ex 12)
    s = S(12)
    set_text(s, "TextBox 3", "EL MÉTODO · REGLAS")
    set_text(s, "TextBox 4", "Un contrato idéntico para todos los competidores")
    set_text(s, "TextBox 5", "1"); set_text(s, "TextBox 6", "híbrido validado: PSO+GA")
    set_text(s, "TextBox 7", str(len(codes))); set_text(s, "TextBox 8", "instancias con óptimo exacto")
    set_text(s, "TextBox 9", str(replicas)); set_text(s, "TextBox 10", "réplicas por algoritmo e instancia")
    set_text(s, "TextBox 11", str(presupuesto)); set_text(s, "TextBox 12", "solicitudes por corrida")
    set_text(s, "TextBox 13", str(n_alg)); set_text(s, "TextBox 14", "algoritmos en el banco (6 clásicos, 3 híbridos)")
    set_text(s, "TextBox 15", "Reglas del protocolo")
    reglas = [(str(presupuesto), "solicitudes; los duplicados cuentan"),
              ("42–71", "semillas propias por algoritmo y réplica"),
              ("Deb", "reglas de factibilidad, sin penalización"),
              ("A priori", "parámetros canónicos, sin reajuste"),
              ("0,01 MW", "referencia: óptimo exacto por instancia"),
              ("Holm", "familia planificada; A12 con bootstrap")]
    nombres = ["TextBox 17", "TextBox 20", "TextBox 23", "TextBox 26", "TextBox 29", "TextBox 32"]
    descs = ["TextBox 18", "TextBox 21", "TextBox 24", "TextBox 27", "TextBox 30", "TextBox 33"]
    for (n, t), nn, dd in zip(reglas, nombres, descs):
        set_text(s, nn, n)
        set_text(s, dd, t)
    set_text(s, "TextBox 35", "Contra quién se compara PSO+GA")
    set_text(s, "TextBox 36", [["RANDOM: ", "muestreo uniforme, sin aprendizaje. ¿Aprende el híbrido?"],
                               ["GA: ", "el donante de los operadores. ¿Supera al método del que toma el cruce y la mutación?"],
                               ["PSO: ", "el bucle base. ¿Aporta la inyección genética, o da lo mismo?"],
                               ["Contexto: ", "GWO, SHO y WOA, los mejores clásicos del banco, y GA+LS y SHO+LS en el documento."]])
    set_notes(s, "[1:00] Las reglas del contrato. Seiscientas solicitudes por corrida, contando los diseños repetidos; un flujo "
                 "aleatorio propio por algoritmo y réplica; factibilidad por reglas de Deb; parámetros canónicos fijados a priori; "
                 "el óptimo exacto como referencia; y una familia planificada de contrastes con corrección de Holm. PSO+GA se compara "
                 "contra tres referencias: RANDOM, para saber si aprende; GA, el donante de operadores; y PSO, el bucle base. Los "
                 "demás clásicos aparecen como contexto, y los otros dos híbridos del documento quedan en respaldo.")

    # =========================================================== 9. DIVISOR 02 (ex 6)
    s = S(6)
    set_text(s, "TextBox 3", "SECCIÓN 2 DE 4")
    set_text(s, "TextBox 5", "Banco de pruebas")
    set_text(s, "TextBox 7", "El problema de dimensionamiento sobre el que se valida el híbrido: qué se minimiza, por qué es difícil y qué instancias se resuelven.")
    set_bullets(s, ["Problema, cuatro instancias y óptimo exacto"], [("Oval 10", "TextBox 11")])
    set_notes(s, "[0:10] El banco de pruebas: el problema sobre el que se valida el método.")

    # =========================================================== 10. EL PROBLEMA EN UNA LÁMINA (ex 9)
    s = S(9)
    set_text(s, "TextBox 3", "BANCO DE PRUEBAS · EL PROBLEMA")
    set_text(s, "TextBox 4", "Minimizar el LCOE de un sistema WPEB: una lámina")
    set_text(s, "TextBox 10", "P = Ctot − W")
    set_text(s, "TextBox 15", "E = u·nE MW → H₂")
    set_text(s, "TextBox 18", "BP, hB de catálogo")
    set_text(s, "TextBox 21", "AGSR ≤ AGSRmax")
    set_text(s, "TextBox 27", [["Caja negra: ", "LCOE y AGSR son salidas de un simulador de 8.760 h; C5 sólo se verifica al terminar el año."],
                               ["Decodificación: ", "nE entero, BP múltiplo de ΔB, k índice de duración; B = 0 anula la duración."]])
    set_text(s, "TextBox 31", [["x = (W, nE, BP, k)", "  → una continua y tres discretas"]])
    set_text(s, "TextBox 33", [["C", "1 ", "Balance de potencia en cada hora"],
                               ["C", "2 ", "W + P = Ctot"],
                               ["C", "3 ", "0 < E ≤ 0,5·Ctot"],
                               ["C", "4 ", "SOC, potencia de batería y carga mínima del electrolizador"],
                               ["C", "5 ", "Venta anual a red ≤ AGSRmax (verificable a posteriori)"]])
    set_notes(s, "[1:30] El problema en una lámina. Una planta con capacidad renovable total fija, repartida entre eólica, W, continua, "
                 "y fotovoltaica, el complemento. La electricidad alimenta un electrolizador comprado en módulos y una batería elegida "
                 "de un catálogo de potencias y duraciones. El vector de decisión tiene cuatro coordenadas, una continua y tres "
                 "discretas. Se minimiza el costo nivelado de la energía con cinco grupos de restricciones; la que manda es la fracción "
                 "anual vendida a la red. Y lo esencial para la metaheurística: el LCOE y esa fracción no tienen fórmula, salen de "
                 "simular el año hora a hora. Es una caja negra, y la restricción cinco sólo se conoce al final.")

    # =========================================================== 11. POR QUÉ ES DIFÍCIL (ex 5)
    s = S(5)
    fa, fb = bf.loc[codes[0], "feasible_share"], bf.loc[codes[1], "feasible_share"]
    set_text(s, "TextBox 3", "BANCO DE PRUEBAS · DIFICULTAD")
    set_text(s, "TextBox 4", "Por qué es un buen banco de pruebas")
    set_text(s, "TextBox 8", "Cada diseño exige simular el año hora a hora: el estado de carga de la batería acopla las horas. Sin derivadas; el presupuesto se cuenta en solicitudes de simulación.")
    set_text(s, "TextBox 10", pct(fa, 1))
    set_text(s, "TextBox 11", "Región factible estrecha")
    set_text(s, "TextBox 12", f"de los diseños enumerados en I1 respetan el límite de venta a red; en I2 (límite a la mitad) baja a {pct(fb, 1)}. El óptimo vive en el borde de esa restricción.")
    set_text(s, "TextBox 16", "W continua junto a catálogos discretos de módulos, potencia y duración: propuestas distintas colapsan en el mismo diseño y gastan evaluaciones repetidas.")
    set_text(s, "TextBox 17", [["Consecuencia: ", "un optimizador debe explorar una región estrecha y afinar W sobre un borde; es el escenario donde explorar y explotar compiten por el presupuesto."]])
    set_notes(s, "[0:50] Tres razones lo hacen un buen banco de pruebas. Evaluar es caro: un año completo por diseño. La región "
                 f"factible es estrecha: en la instancia de referencia sólo {pct(fa, 0)} de los diseños cumple el límite de venta a "
                 f"red y, con el límite a la mitad, {pct(fb, 0)}. Y el dominio es mixto. Es exactamente el escenario donde explorar y "
                 "explotar compiten por el presupuesto, que es lo que un híbrido pretende equilibrar.")

    # =========================================================== 12. INSTANCIAS (plantilla 26)
    s = s_instancias
    set_text(s, "TextBox 3", "BANCO DE PRUEBAS · INSTANCIAS")
    set_text(s, "TextBox 4", "Cuatro instancias del mismo problema")
    que_cambia = {codes[0]: "referencia (AGSR ≤ 0,20)", codes[1]: "límite de venta a red a la mitad",
                  codes[2]: "módulos de 2,5 MW, batería 2,5 MW, duraciones 1/2/4/8 h", codes[3]: "planta de 300 MW, electrolizador hasta 150 MW"}
    filas = [["Inst.", "Qué cambia", "Ctot [MW]", "AGSRmax", "Catálogos", "Diseños (paso 0,01 MW)", "Factibles"]]
    for c in codes:
        filas.append([c, que_cambia.get(c, etiqueta[c]), num(inst.loc[c, "total_capacity_mw"], 0), num(inst.loc[c, "agsr_max"], 2),
                      entero(inst.loc[c, "n_catalogs"]), entero(bf.loc[c, "evaluated"]), pct(bf.loc[c, "feasible_share"], 1)])
    fill_table(s, "Table 5", filas, [0.6, 3.1, 0.9, 0.9, 1.0, 1.5, 1.0])
    set_text(s, "TextBox 6", [["Una instancia es una tupla ", "(Ctot, AGSRmax, u, nmin, nmax, ΔB, Bmax, {hk}). ",
                               "Las cuatro derivan de I1 cambiando un aspecto cada vez: región factible (I2), finura del espacio discreto (I3) y escala (I4). Comparten simulador, codificación y tratamiento de restricciones."]])
    set_notes(s, "[1:00] Las cuatro instancias. I1 es la de referencia. I2 reduce a la mitad el límite de venta a red: cambia sólo la "
                 "restricción que manda. I3 refina los catálogos: cinco veces más combinaciones discretas sobre la misma región física. "
                 "I4 escala la planta a trescientos megavatios. Cada una cambia un aspecto, así que si el híbrido se comporta "
                 "distinto en una de ellas, la causa está declarada.")

    # =========================================================== 13. ÓPTIMO EXACTO (plantilla 15)
    s = s_optimo
    set_text(s, "TextBox 3", "BANCO DE PRUEBAS · ÓPTIMO EXACTO")
    set_text(s, "TextBox 4", "El óptimo exacto de cada instancia por fuerza bruta")
    replace_picture(s, "Picture 5", FIGS_TESIS / "fig10_envolvente_fuerza_bruta.png")
    optimos = "; ".join("{}: {}".format(c, num(bf.loc[c, "optimum_lcoe_cny_per_kwh"], 5)) for c in codes)
    set_text(s, "TextBox 6", [[f"{entero(bf_total)} diseños anuales ", f"enumerados en {num(bf_horas, 1)} h: todos los catálogos sobre W cada 0,01 MW, con despacho vectorizado y reducción por bloque."],
                              ["Verificado ", f"contra el simulador oficial en 200 celdas por instancia (dif. máx. {bf['control_max_rel_diff_lcoe'].max():.0e}) y recertificando los 10 mejores catálogos."],
                              ["Óptimos (CNY/kWh) ", optimos + ". Todos sobre el borde de AGSR: un paso más en W viola C5."]])
    set_notes(s, "[1:00] Esto es lo que convierte la validación en una medición contra un valor conocido. Para cada instancia "
                 f"enumeré todos los catálogos sobre todos los valores de W con paso de una centésima: {entero(bf_total)} diseños en "
                 f"unas {num(bf_horas, 0)} horas, con el despacho vectorizado. La curva es la envolvente: el mejor LCOE factible para "
                 "cada W. Los cuatro óptimos están sobre el borde de la restricción de venta a red: un paso más en W la viola.")

    # =========================================================== 14. SIMULADOR VALIDADO (ex 11)
    s = S(11)
    set_notes(s, "[0:40] Y el simulador en el que todo descansa está validado: reconstruí el modelo de Li y lo contrasté con los "
                 "indicadores publicados; ocho de once quedan a menos de cinco por ciento. Es una reproducción parcial, no una "
                 "equivalencia, pero es el mismo simulador para los nueve algoritmos, las cuatro instancias y la fuerza bruta.")

    # =========================================================== 15. DIVISOR 03 (ex 8)
    s = S(8)
    set_text(s, "TextBox 3", "SECCIÓN 3 DE 4")
    set_text(s, "TextBox 5", "Validación")
    set_text(s, "TextBox 7", "Tres bloques: que el híbrido es correcto, qué tan cerca del óptimo llega y si aporta algo frente a RANDOM, GA y PSO.")
    set_bullets(s, ["Correctitud: presupuesto, operadores, reproducción", "Calidad: convergencia, brecha y tasa de éxito",
                    "Aporte: contrastes planificados", "Uso del presupuesto"],
                [("Oval 10", "TextBox 11"), ("Oval 12", "TextBox 13"), ("Oval 14", "TextBox 15"), ("Oval 16", "TextBox 17")])
    set_notes(s, "[0:10] La validación, en tres bloques.")

    # =========================================================== 16. CORRECTITUD (plantilla 5)
    s = s_correcto
    set_text(s, "TextBox 3", "VALIDACIÓN 1 · CORRECTITUD")
    set_text(s, "TextBox 4", "Antes de medir calidad: el híbrido hace lo que dice")
    set_text(s, "TextBox 6", str(presupuesto))
    set_text(s, "TextBox 7", "solicitudes exactas")
    set_text(s, "TextBox 8", f"Verificado al cierre de cada una de las {entero(len(codes) * n_alg * replicas)} corridas; el contrato rechaza la solicitud {presupuesto + 1} y registra un checkpoint cada 20.")
    set_text(s, "TextBox 10", "1 paso")
    set_text(s, "TextBox 11", "contra las ecuaciones")
    set_text(s, "TextBox 12", "La inyección genética reproducida con semilla fija (torneo, cruce, mutación, velocidad 0, memoria borrada); dirección y límites en Sphere y Rastrigin.")
    set_text(s, "TextBox 14", "bit a bit")
    set_text(s, "TextBox 15", "los padres no cambian")
    set_text(s, "TextBox 16", "La corrida de I1 reproduce la comparativa previa de los seis clásicos con los mismos valores; el flujo aleatorio no depende de la instancia.")
    set_text(s, "TextBox 17", [["Además: ", f"las {entero(len(codes) * n_alg * replicas)} corridas terminaron factibles, con residuo de balance menor que 1e-8 MW y AGSR bajo el límite de su instancia."]])
    set_notes(s, "[1:00] Primer bloque: correctitud. Tres pruebas. El presupuesto: cada corrida hizo exactamente seiscientas solicitudes; "
                 "el contrato rechaza la seiscientos uno. Los operadores: un paso de la inyección genética reproducido contra sus "
                 "ecuaciones con semilla fija, más pruebas de dirección y límites sobre Sphere y Rastrigin. Y la reproducción: como los "
                 "padres no se tocan, la corrida de I1 reproduce bit a bit la comparativa anterior de los seis clásicos. Todas las "
                 "corridas terminaron en un diseño factible.")

    # =========================================================== 17. CONVERGENCIA (ex 15)
    s = S(15)
    set_text(s, "TextBox 3", "VALIDACIÓN 2 · CALIDAD")
    replace_picture(s, "Picture 5", FIGS_PRES / "pres_convergencia_foco.png")
    set_text(s, "TextBox 4", "Convergencia a igual número de solicitudes")
    set_text(s, "TextBox 6", [["Mediana y rango intercuartil ", "del mejor LCOE factible frente a las solicitudes acumuladas; PSO+GA en marrón, la línea punteada es el óptimo exacto."],
                              ["PSO+GA sigue al PSO ", "en las cuatro instancias: la inyección no cambia el ritmo de la convergencia."],
                              ["RANDOM ", "se separa desde las primeras decenas de solicitudes; SHO, el mejor clásico, marca la referencia superior."]])
    set_notes(s, "[1:10] Segundo bloque: calidad. Las curvas de convergencia, un panel por instancia, con las solicitudes en el eje "
                 "horizontal: en cada punto todos han visto el mismo número de diseños. PSO+GA, en marrón, sigue de cerca al PSO en "
                 "las cuatro instancias: la inyección no cambia el ritmo. Ambos se separan de RANDOM desde el inicio. SHO, el mejor "
                 "clásico del banco, marca la referencia superior.")

    # =========================================================== 18. DISTRIBUCIÓN Y BRECHA (ex 16)
    s = S(16)
    set_text(s, "TextBox 3", "VALIDACIÓN 2 · CALIDAD")
    replace_picture(s, "Picture 5", FIGS_PRES / "pres_distribucion_foco.png")
    set_text(s, "TextBox 4", "Qué tan cerca del óptimo queda PSO+GA")
    filas = [["Inst.", "Rango", "Brecha", "Éxito", "Mejor"]]
    for c in codes:
        r = hr[c]
        filas.append([c, entero(r["ranking_descriptivo"]), num(r["median_gap_pct"], 2) + " %", pct(r["success_0.5pct"], 0),
                      num(r["best_gap_pct"], 3) + " %"])
    fill_table(s, "Table 6", filas, [0.55, 0.7, 0.85, 0.85, 0.8], font_pt=9.5, row_height_in=0.3)
    set_text(s, "TextBox 7", [["Tabla: ", "rango entre los 9 algoritmos, brecha mediana al óptimo exacto, corridas a menos de 0,5 % y brecha de la mejor corrida."],
                              ["Brecha mediana ", "de {} a {} %: una corrida típica queda a menos de 1 % del óptimo exacto.".format(
                                   num(min(hr[c]["median_gap_pct"] for c in codes), 2), num(max(hr[c]["median_gap_pct"] for c in codes), 2))],
                              ["Mejor corrida ", ("la mejor de los nueve algoritmos en " + ", ".join(corridas_psoga) + ", por debajo del óptimo discretizado gracias a W continuo." if corridas_psoga else "a milésimas del óptimo exacto en las cuatro instancias.")]])
    set_notes(s, "[1:20] La distribución del LCOE final en treinta corridas, con PSO+GA en marrón junto a PSO, GA, SHO y RANDOM. "
                 "La tabla resume al híbrido: su rango entre los nueve, la brecha mediana al óptimo exacto, la tasa de éxito al medio "
                 "por ciento y la brecha de su mejor corrida. Una corrida típica queda a menos de un uno por ciento del óptimo en las "
                 f"cuatro instancias. Y su mejor corrida es la mejor de todos los algoritmos en {', '.join(corridas_psoga) if corridas_psoga else 'varias instancias'}, "
                 "incluso por debajo del óptimo discretizado, porque el optimizador maneja W continuo.")

    # =========================================================== 19. TASA DE ÉXITO (plantilla 15)
    s = s_exito
    set_text(s, "TextBox 3", "VALIDACIÓN 2 · CALIDAD")
    set_text(s, "TextBox 4", "¿Con qué frecuencia se llega cerca del óptimo?")
    replace_picture(s, "Picture 5", FIGS_PRES / "pres_exito_foco.png")
    ex = {c: hr[c]["success_0.5pct"] for c in codes}
    ex_pso = {c: fila_rank(d, c, "pso")["success_0.5pct"] for c in codes}
    ex_ga = {c: fila_rank(d, c, "ga")["success_0.5pct"] for c in codes}
    ex_rnd = {c: fila_rank(d, c, "random")["success_0.5pct"] for c in codes}
    set_text(s, "TextBox 6", [["Tasa de éxito: ", "fracción de las 30 corridas que termina a menos de 0,5 % del óptimo exacto de su instancia."],
                              ["PSO+GA: ", "entre {} y {} de las corridas; GA entre {} y {}; RANDOM entre {} y {}.".format(
                                  pct(min(ex.values()), 0), pct(max(ex.values()), 0), pct(min(ex_ga.values()), 0), pct(max(ex_ga.values()), 0),
                                  pct(min(ex_rnd.values()), 0), pct(max(ex_rnd.values()), 0))],
                              ["Frente a PSO: ", "PSO alcanza entre {} y {}; la diferencia va en ambos sentidos según la instancia.".format(pct(min(ex_pso.values()), 0), pct(max(ex_pso.values()), 0))]])
    set_notes(s, "[0:50] La tasa de éxito: en qué fracción de las corridas se queda a menos de medio por ciento del óptimo. PSO+GA "
                 f"alcanza entre {pct(min(ex.values()), 0)} y {pct(max(ex.values()), 0)} según la instancia, claramente por encima de "
                 "RANDOM y por encima de GA, y en el entorno del PSO, con diferencias en ambos sentidos. Es lo que un usuario "
                 "querría saber: si corro este método una vez, cuán probable es quedar cerca.")

    # =========================================================== 20. APORTE: CONTRASTES (plantilla 16)
    s = s_aporte
    set_text(s, "TextBox 3", "VALIDACIÓN 3 · APORTE")
    set_text(s, "TextBox 4", "¿Aporta la inyección genética?")
    replace_picture(s, "Picture 5", FIGS_PRES / "pres_psoga_a12.png")
    filas = [["PSO+GA vs"] + codes]
    for b, nombre in (("random", "RANDOM"), ("ga", "GA"), ("pso", "PSO")):
        fila = [nombre]
        for c in codes:
            r = vs[(c, b)]
            fila.append("--" if r is None else num(r["a12"], 2) + ("*" if truthy(r["significativo_alpha_0.05"]) else ""))
        filas.append(fila)
    fill_table(s, "Table 6", filas, [1.15, 0.65, 0.65, 0.65, 0.65], font_pt=10, row_height_in=0.32)
    set_text(s, "TextBox 7", [["A12 > 0,5: ", "gana PSO+GA; * = significativo tras Holm en la familia planificada de la instancia."],
                              ["Lectura: ", "supera a RANDOM en {}; supera a GA en mediana en {} y de forma significativa en {}; frente a PSO no hay diferencia detectable.".format(
                                  "las cuatro" if len(gana["random"]) == len(codes) else ", ".join(gana["random"]) or "ninguna",
                                  "las cuatro" if len(mejor_med["ga"]) == len(codes) else ", ".join(mejor_med["ga"]) or "ninguna",
                                  ", ".join(gana["ga"]) or "ninguna")]])
    set_notes(s, "[1:30] Tercer bloque, la pregunta central: ¿aporta la inyección? Tres contrastes por instancia, con el tamaño de "
                 "efecto A12 y su intervalo; marcador lleno si es significativo tras Holm. Contra RANDOM, PSO+GA gana en las cuatro "
                 f"instancias con A12 cercano a 0,8: aprende. Contra GA, el donante de los operadores, tiene mejor mediana en "
                 f"{'las cuatro' if len(mejor_med['ga']) == len(codes) else ', '.join(mejor_med['ga'])} y la diferencia es significativa en "
                 f"{', '.join(gana['ga']) or 'ninguna'}. Y contra PSO, el bucle base, no hay diferencia detectable en ninguna: el A12 "
                 "oscila alrededor de 0,5. La respuesta honesta es: la inyección genética no empeora ni mejora al PSO bajo este presupuesto.")

    # =========================================================== 21. LECTURA (ex 4)
    s = S(4)
    set_text(s, "TextBox 3", "VALIDACIÓN 3 · LECTURA")
    set_text(s, "TextBox 4", "Qué dice la evidencia sobre el híbrido")
    set_text(s, "TextBox 6", "Aprende y supera al donante")
    en_ga = "las cuatro instancias" if len(mejor_med["ga"]) == len(codes) else ", ".join(mejor_med["ga"])
    sig_ga = ", ".join(gana["ga"]) or "ninguna"
    set_text(s, "TextBox 7", f"Gana a RANDOM en las cuatro instancias y a GA en mediana en {en_ga}, con significancia en {sig_ga}: el híbrido hereda la calidad del bucle del enjambre.")
    set_text(s, "TextBox 9", "La inyección ni suma ni resta")
    set_text(s, "TextBox 10", "Frente a PSO, A12 entre 0,37 y 0,52 sin significancia: reemplazar las 5 peores partículas por hijos genéticos no cambia el resultado típico.")
    set_text(s, "TextBox 12", "Pero sí mejora el mejor caso")
    set_text(s, "TextBox 13", ("Su mejor corrida es la mejor de los nueve en " + ", ".join(corridas_psoga) + ": la diversidad inyectada ayuda a afinar W sobre el borde de AGSR en algunas semillas.") if corridas_psoga else "Sus mejores corridas quedan a milésimas del óptimo exacto en las cuatro instancias.")
    set_text(s, "TextBox 15", "Dónde queda entre los nueve")
    set_text(s, "TextBox 16", "Rango medio {} (puesto {} de 9)".format(num(rank_h["mean_rank"], 2), entero(rank_h["ranking_transversal"])))
    set_text(s, "TextBox 17", ["{} lidera el banco con rango medio {}".format(lab(primero["algorithm"]), num(primero["mean_rank"], 2)),
                               "PSO+GA: rangos " + ", ".join("{} en {}".format(entero(rank_h["rank_" + c]), c) for c in codes),
                               "Por encima de GA ({}) y de GA+LS ({}) en rango medio".format(num(cross.set_index('algorithm').loc['ga', 'mean_rank'], 2), num(cross.set_index('algorithm').loc['ga_ls', 'mean_rank'], 2)),
                               "El orden cambia entre instancias: nadie domina en las cuatro",
                               "Los seis clásicos y los otros dos híbridos: tablas en respaldo"])
    set_notes(s, "[1:20] Qué dice la evidencia. Primero, PSO+GA aprende y supera al donante: gana a RANDOM en las cuatro instancias y a "
                 f"GA por mediana en {en_ga}, con significancia en {sig_ga}. Segundo, la inyección ni suma ni resta frente al PSO: el "
                 "resultado típico es el mismo. Tercero, sí mejora el mejor caso: su mejor corrida es la mejor de los nueve algoritmos "
                 f"en {', '.join(corridas_psoga) if corridas_psoga else 'varias instancias'}; la diversidad inyectada ayuda a afinar W sobre el borde "
                 f"en algunas semillas. Y en el banco completo queda en el puesto {entero(rank_h['ranking_transversal'])} de nueve por rango "
                 f"medio; {lab(primero['algorithm'])} lidera. Nadie domina en las cuatro instancias.")

    # =========================================================== 22. USO DEL PRESUPUESTO (plantilla 15)
    s = s_presupuesto
    set_text(s, "TextBox 3", "VALIDACIÓN · USO DEL PRESUPUESTO")
    set_text(s, "TextBox 4", "Cómo se gastan las 600 solicitudes")
    replace_picture(s, "Picture 5", FIGS_PRES / "pres_presupuesto.png")
    dup = d["rank"].groupby("algorithm")["mean_duplicates"].mean()
    set_text(s, "TextBox 6", [["Duplicados: ", f"PSO+GA repite en promedio {num(dup['pso_ga'], 0)} de 600 solicitudes; GA, {num(dup['ga'], 0)}; PSO, {num(dup['pso'], 0)}."],
                              ["Por qué: ", "los hijos genéticos decodifican a diseños ya vistos con más frecuencia que una partícula en movimiento, pero mucho menos que el elitismo del GA."],
                              ["Costo: ", "con presupuesto idéntico, las diferencias de tiempo vienen del operador de movimiento, no de la búsqueda."]])
    set_notes(s, "[0:40] Cómo se gasta el presupuesto. Las solicitudes duplicadas, un diseño ya evaluado que se vuelve a pedir, cuentan "
                 f"contra las seiscientas. PSO+GA repite en promedio {num(dup['pso_ga'], 0)}, frente a {num(dup['ga'], 0)} del GA y "
                 f"{num(dup['pso'], 0)} del PSO: los hijos genéticos caen a veces en diseños ya vistos, pero muy lejos del elitismo del GA.")

    # =========================================================== 23. DIVISOR 04 (ex 13)
    s = S(13)
    set_text(s, "TextBox 3", "SECCIÓN 4 DE 4")
    set_text(s, "TextBox 5", "Conclusiones")
    set_text(s, "TextBox 7", "Qué afirmaciones quedan respaldadas por la evidencia, cuáles son los límites y qué sigue.")
    set_bullets(s, ["Qué se puede afirmar", "Límites", "Trabajo futuro"],
                [("Oval 10", "TextBox 11"), ("Oval 12", "TextBox 13"), ("Oval 14", "TextBox 15"),
                 ("Oval 16", "TextBox 17"), ("Oval 18", "TextBox 19"), ("Oval 20", "TextBox 21")])
    set_notes(s, "[0:10] Cierro con las conclusiones.")

    # =========================================================== 24. QUÉ SE PUEDE AFIRMAR (ex 23)
    s = S(23)
    set_text(s, "TextBox 3", "CONCLUSIONES")
    set_text(s, "TextBox 4", "Qué se puede afirmar y qué no")
    set_text(s, "TextBox 7", [f"El problema queda enunciado como mín LCOE sobre un dominio mixto, con cuatro instancias y su óptimo exacto ({entero(bf_total)} diseños enumerados)",
                              f"PSO+GA es correcto: {presupuesto} solicitudes exactas, operadores verificados, padres intactos y reproducción bit a bit",
                              "PSO+GA aprende (gana a RANDOM en las cuatro instancias) y supera a GA, el donante de sus operadores, con significancia en " + (", ".join(gana["ga"]) or "ninguna"),
                              "La inyección genética no cambia el resultado típico del PSO, pero produce la mejor corrida en " + (", ".join(corridas_psoga) if corridas_psoga else "varias instancias"),
                              "Un flujo auditable: cada cifra sale del cuaderno ejecutado"])
    set_text(s, "TextBox 10", ["Un solo sitio aproximado y un solo año meteorológico; instancias paramétricas, no otros recursos ni costos",
                               "Capacidad renovable fija por instancia; sin demanda explícita de hidrógeno; LCOE como único objetivo",
                               "Hiperparámetros fijados a priori: 5 hijos por iteración sin ablación",
                               f"Rango medio {num(rank_h['mean_rank'], 2)}: PSO+GA no es el mejor del banco; {lab(primero['algorithm'])} y GWO lo superan",
                               "Treinta corridas por instancia: efectos pequeños entre PSO y PSO+GA no son detectables"])
    set_notes(s, "[1:20] ¿Qué queda respaldado? El problema está enunciado y tiene óptimo conocido en cada instancia. El híbrido es "
                 "correcto: presupuesto exacto, operadores verificados, padres intactos. Aprende y supera al donante de sus operadores. "
                 "La inyección no cambia el resultado típico del PSO, pero produce las mejores corridas individuales. Y todo es "
                 "auditable. ¿Qué no se puede afirmar? Superioridad general: un sitio, un año, instancias paramétricas, LCOE como único "
                 f"objetivo, cinco hijos por iteración sin ablación, y un banco en el que {lab(primero['algorithm'])} y GWO superan al híbrido en rango medio.")

    # =========================================================== 25. APORTE Y TRABAJO FUTURO (plantilla 23)
    s = s_futuro
    set_text(s, "TextBox 3", "CONCLUSIONES")
    set_text(s, "TextBox 4", "Aporte a la Ingeniería Informática y trabajo futuro")
    set_text(s, "TextBox 6", "Aporte")
    set_text(s, "TextBox 7", ["Infraestructura de hibridación: operadores del GA como mixin reutilizable y contrato de presupuesto que ningún híbrido puede eludir",
                              "Óptimo exacto por enumeración vectorizada con reducción por bloque, verificado y cacheado",
                              "Protocolo con familia planificada de contrastes (frente a RANDOM y frente a los padres)",
                              "Tablas, figuras y macros del documento generadas desde los CSV: cero transcripción manual"])
    set_text(s, "TextBox 9", "Trabajo futuro")
    set_text(s, "TextBox 10", ["Ablación del número de hijos por iteración y de la memoria de los hijos",
                               "Los otros dos híbridos del documento (GA+LS, SHO+LS) y GWO+LS con la misma infraestructura",
                               "Más años y sitios; instancias que cambien la estructura de costos",
                               "Híbridos de alto nivel en relevo y componentes de aprendizaje (selección de operadores)",
                               "Capacidad renovable libre, demanda de hidrógeno y formulación multiobjetivo"])
    set_notes(s, "[0:50] El aporte informático es una infraestructura de hibridación reutilizable, un óptimo exacto por enumeración "
                 "vectorizada y un flujo en el que cada cifra se genera desde los datos. Como trabajo futuro: una ablación del número "
                 "de hijos, los otros dos híbridos que ya están evaluados en el documento, más años y sitios, híbridos de alto nivel "
                 "y la formulación multiobjetivo.")

    # =========================================================== 26. CIERRE (ex 25)
    s = S(25)
    set_text(s, "TextBox 4", "Un híbrido validado contra un óptimo conocido, con el mismo presupuesto que sus padres.")
    set_text(s, "TextBox 5", "Gracias. ¿Preguntas?")
    set_notes(s, "[0:30] En síntesis: un híbrido validado contra un óptimo conocido, con el mismo presupuesto que sus padres, y una "
                 "respuesta honesta sobre lo que aporta y lo que no. Muchas gracias; quedo atento a sus preguntas.")

    # =========================================================== RESPALDO
    for c in codes:
        s = s_calidad[c]
        set_text(s, "TextBox 4", f"Calidad final completa en {c} ({etiqueta[c]})")
        rk = d["rank"][d["rank"]["instance"] == c].sort_values("ranking_descriptivo")
        filas = [["Algoritmo", "Mediana", "IQR", "Mejor", "Peor", "Brecha med. %", "≤ 0,1 %", "≤ 0,5 %", "≤ 1 %"]]
        for _, r in rk.iterrows():
            filas.append([lab(r["algorithm"]), num(r["median"], 6), num(r["iqr"], 6), num(r["best"], 6), num(r["worst"], 6),
                          num(r["median_gap_pct"], 3), pct(r["success_0.1pct"], 0), pct(r["success_0.5pct"], 0), pct(r["success_1.0pct"], 0)])
        fill_table(s, "Table 5", filas, [1.1, 1.0, 1.0, 1.0, 1.0, 1.1, 0.9, 0.9, 0.9], font_pt=8.5, row_height_in=0.24)
        o = bf.loc[c]
        set_text(s, "TextBox 6", f"LCOE en CNY/kWh. Brecha respecto del óptimo exacto de {c} ({num(o['optimum_lcoe_cny_per_kwh'], 6)}; W={num(o['optimum_wind_mw'], 2)}, E={num(o['optimum_electrolyzer_mw'], 1)}, B={num(o['optimum_battery_mw'], 1)} MW × {num(o['optimum_battery_duration_h'], 0)} h). {replicas} ejecuciones por algoritmo. Factibles mínimas por algoritmo: {int(rk['feasible_runs'].min())}/{replicas}.")
        set_notes(s, f"[RESPALDO] Usar si preguntan por valores exactos en {c} o por los seis clásicos. Mediana, IQR, mejor, peor, brecha mediana al óptimo exacto y tasas de éxito de los nueve algoritmos.")

    s = s_otros
    set_text(s, "TextBox 3", "RESPALDO")
    set_text(s, "TextBox 4", "Los otros dos híbridos: GA+LS y SHO+LS")
    replace_picture(s, "Picture 5", FIGS_PRES / "pres_hibrido_vs_padre.png")
    filas = [["Par"] + codes]
    for h, p in HYBRID_PAIRS:
        fila = ["{} vs {}".format(lab(h), lab(p))]
        for c in codes:
            sub = hyb[(hyb["instance"] == c) & (hyb["hibrido"] == h) & (hyb["padre"] == p)]
            fila.append("--" if sub.empty else num(sub.iloc[0]["a12_hibrido_vs_padre"], 2) + ("*" if truthy(sub.iloc[0]["significativo_alpha_0.05"]) else ""))
        filas.append(fila)
    fill_table(s, "Table 6", filas, [1.55, 0.55, 0.55, 0.55, 0.55], font_pt=9.5, row_height_in=0.3)
    n_win = int(hyb["hibrido_mejor_mediana"].map(truthy).sum())
    n_sig = int(hyb["significativo_alpha_0.05"].map(truthy).sum())
    set_text(s, "TextBox 7", [["GA+LS y SHO+LS ", "añaden una búsqueda local lamarckiana (4 solicitudes por generación) al mejor individuo o a la presa."],
                              ["Resultado: ", f"el híbrido mejora la mediana de su padre en {n_win} de {len(hyb)} contrastes y {n_sig} son significativos. SHO+LS es primero en I2 y sexto en I3."]])
    set_notes(s, "[RESPALDO] Usar si preguntan por los otros híbridos. GA+LS y SHO+LS están implementados y evaluados en el documento con la misma infraestructura; la búsqueda local rinde en la instancia de región estrecha (I2) y se resta a la exploración en la de catálogos finos (I3).")

    s = S(27)
    set_text(s, "TextBox 4", "Configuración de los nueve algoritmos")
    filas = [["Código", "Familia", "Configuración"]]
    for _, r in d["hyper"].iterrows():
        filas.append([lab(r["codigo"]), str(r["familia"]), str(r["hiperparametros"])])
    fill_table(s, "Table 5", filas, [1.0, 1.9, 6.1], font_pt=7.5, row_height_in=0.235)
    set_text(s, "TextBox 6", [f"Población {int(meta['population'])} × {int(meta['iterations'])} iteraciones = {presupuesto} solicitudes por ejecución · semillas de réplica 42–71 · flujo propio por algoritmo y réplica, independiente de la instancia · sin ajuste posterior.",
                              "PSO+GA: 5 hijos por iteración, sin memoria. Búsqueda local (GA+LS, SHO+LS): 4 solicitudes por generación, δW del 1 % del rango a 0,01 MW."])
    set_notes(s, "[RESPALDO] Usar si preguntan por hiperparámetros. Valores canónicos de la literatura; nada se reajusta para los híbridos.")

    s = S(28)
    set_text(s, "TextBox 4", f"Cada metaheurística frente a RANDOM en {codes[0]}")
    planned = d["tests"][(d["tests"]["family"] == "planned") & (d["tests"]["algoritmo_b"] == "random") & (d["tests"]["instance"] == codes[0])]
    filas = [["Algoritmo", "p (Mann–Whitney)", "p ajustado (Holm)", "A12 vs RANDOM", "IC 95 % bootstrap", "Lectura"]]
    for _, r in planned.iterrows():
        sig = truthy(r["significativo_alpha_0.05"])
        lectura = ("ventaja detectable" if sig and r["a12"] > 0.5 else "desventaja detectable" if sig else "sin diferencia detectable")
        filas.append([lab(r["algoritmo_a"]), pvalor(r["p_value"]), pvalor(r["p_value_holm"]), num(r["a12"], 2),
                      f"[{num(r['a12_ci_low'], 2)}; {num(r['a12_ci_high'], 2)}]", lectura])
    fill_table(s, "Table 5", filas, [1.1, 1.5, 1.5, 1.3, 1.6, 2.0], font_pt=8.5, row_height_in=0.24)
    set_text(s, "TextBox 6", ["A12 = probabilidad de que el algoritmo logre menor LCOE que RANDOM en un enfrentamiento al azar. Holm dentro de la familia planificada de 12 contrastes por instancia (8 frente a RANDOM + 4 híbrido frente a padre).",
                              "Las otras instancias y la matriz completa de 36 pares están en el documento (anexo de contrastes)."])
    set_notes(s, "[RESPALDO] Usar si preguntan por los valores p o por la corrección. GA y GA+LS no se distinguen de RANDOM en ninguna instancia; los demás sí.")

    s = s_matrices
    set_text(s, "TextBox 3", "RESPALDO")
    set_text(s, "TextBox 4", "Todos los pares: matrices A12 por instancia")
    replace_picture(s, "Picture 5", FIGS_TESIS / "fig11_matrices_a12.png")
    n_all = d["tests"][d["tests"]["family"] == "all"]
    sig_all = {c: int(n_all[n_all["instance"] == c]["significativo_alpha_0.05"].map(truthy).sum()) for c in codes}
    set_text(s, "TextBox 8", "Los 36 pares, con Holm sobre los 36")
    set_text(s, "TextBox 9", "Pares significativos: " + "; ".join("{}: {}".format(c, sig_all[c]) for c in codes) + ".")
    set_text(s, "TextBox 11", [["¿Por qué una familia planificada? ", "Con 36 pares, Holm exige p muy pequeños y sacrifica potencia en contrastes que no interesan; los 12 planificados responden las preguntas de la tesis."]])
    set_text(s, "TextBox 13", "El ranking por mediana es descriptivo; la inferencia es por instancia.")
    set_text(s, "TextBox 14", "Mann–Whitney bilateral · Holm · A12 con IC bootstrap al 95 %")
    set_notes(s, "[RESPALDO] Usar si preguntan por las comparaciones entre metaheurísticas.")

    s = S(19)
    set_text(s, "TextBox 5", f"Las {replicas} ejecuciones de cada algoritmo dan valores distintos. Antes de afirmar que uno es mejor, tres preguntas por instancia.")
    set_text(s, "TextBox 10", "Mira los nueve grupos juntos y responde sí o no, sin decir entre quiénes.")
    set_text(s, "TextBox 11", "Resultado por instancia en el documento")
    set_text(s, "TextBox 17", "12 contrastes planificados por instancia")
    set_text(s, "TextBox 25", [["Corrección de Holm: ", "dentro de la familia planificada (8 frente a RANDOM + 4 híbrido frente a padre). La matriz completa de 36 pares, con Holm sobre los 36, va al anexo."]])
    set_notes(s, "[RESPALDO] Usar si preguntan cómo se hace la inferencia: Kruskal-Wallis global, Mann-Whitney por pares, A12 como tamaño de efecto y Holm dentro de la familia planificada.")

    s = S(10)
    set_text(s, "TextBox 3", "RESPALDO")
    set_notes(s, "[RESPALDO] Usar si preguntan cómo opera un diseño: tres días de mayo del mejor diseño de la comparativa previa en I1, en la región del óptimo exacto.")

    for n in (29, 30, 31):
        s = S(n)
        set_notes(s, s.notes_slide.notes_text_frame.text if s.has_notes_slide else "[RESPALDO]")

    # =========================================================== ORDEN FINAL
    cuerpo = [S(1), S(2), S(3), s_pregunta, s_pipe_exp, s_pipe_alg, s_padres, S(12),
              S(6), S(9), S(5), s_instancias, s_optimo, S(11),
              S(8), s_correcto, S(15), S(16), s_exito, s_aporte, S(4), s_presupuesto,
              S(13), S(23), s_futuro, S(25)]
    respaldo = [s_calidad[c] for c in codes] + [s_otros, S(27), S(28), s_matrices, S(19), S(10), S(29), S(30), S(31)]
    reorder_and_prune(prs, cuerpo + respaldo)

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    destino = DESTINO
    try:
        prs.save(str(destino))
    except PermissionError:
        # El archivo esta abierto en PowerPoint: se escribe al lado con otro nombre.
        destino = DESTINO.with_name(DESTINO.stem + "_nuevo.pptx")
        prs.save(str(destino))
        print("AVISO: el destino estaba bloqueado; cierre el archivo en PowerPoint y renombre", destino.name)
    print(destino, "->", len(cuerpo), "diapositivas de cuerpo +", len(respaldo), "de respaldo")


if __name__ == "__main__":
    main()
