"""Construye la presentación de la defensa a partir del deck de avance.

Conserva la plantilla (paleta, logo, banda inferior, tipografía) del deck
``presentacion/Presentacion_avance_tesis_LOliva.pptx`` y reescribe el guion:
el problema queda en dos láminas formales y el grueso pasa a las metaheurísticas
clásicas e híbridas, el óptimo exacto por fuerza bruta y los resultados en las
cuatro instancias. Todos los números salen de ``notebooks/results/*.csv``.

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
from pptx.enum.shapes import PP_PLACEHOLDER
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "notebooks" / "results"
FIGS_TESIS = ROOT / "latex" / "figures"
FIGS_PRES = ROOT / "presentacion" / "figuras"
ORIGEN = ROOT / "presentacion" / "Presentacion_avance_tesis_LOliva.pptx"
DESTINO = ROOT / "presentacion" / "Presentacion_defensa_tesis_LOliva.pptx"

LABELS = {"gwo": "GWO", "pso": "PSO", "ga": "GA", "sho": "SHO", "woa": "WOA",
          "ga_ls": "GA+LS", "pso_ga": "PSO+GA", "sho_ls": "SHO+LS", "random": "RANDOM"}
ORDER = ("gwo", "pso", "ga", "sho", "woa", "ga_ls", "pso_ga", "sho_ls", "random")
HYBRID_PAIRS = (("ga_ls", "ga"), ("pso_ga", "pso"), ("pso_ga", "ga"), ("sho_ls", "sho"))


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


def set_paragraphs(shape, paras) -> None:
    """Reemplaza el texto conservando el formato de los runs de la plantilla.

    ``paras``: lista de párrafos; cada uno es un str (un run) o una lista de str
    (un run por elemento, para combinar etiqueta en negrita + texto normal).
    """
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
        # Las diapositivas duplicadas nacen sin notas y el patrón de notas de esta
        # plantilla no aporta el marcador de cuerpo: se clona el de una original.
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
    por_id = {}
    for sldId in list(sldIdLst):
        por_id[sldId.rId] = sldId
    keep_rids = set()
    orden = []
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
    d["valid"] = pd.read_csv(RESULTS / "validation_metrics_8760.csv")
    return d


def top_por_instancia(d, code):
    r = d["rank"][d["rank"]["instance"] == code].sort_values("ranking_descriptivo")
    return r


def lideres(d):
    return {c: top_por_instancia(d, c).iloc[0]["algorithm"] for c in d["codes"]}


# --------------------------------------------------------------------------- construcción
def main() -> None:
    d = cargar_datos()
    codes = d["codes"]
    meta = d["meta"]
    bf = d["bf"]
    inst = d["inst"].set_index("instance")
    cross = d["cross"]
    hyb = d["hyb"]
    lid = lideres(d)
    replicas = int(meta["replicates_per_algorithm"])
    presupuesto = int(meta["requests_per_run"])
    n_alg = int(meta["algorithms"])
    total_req = int(meta["total_requests"])
    bf_total = int(meta["brute_force_designs_total"])
    bf_horas = bf["elapsed_s"].sum() / 3600.0
    etiqueta = {c: inst.loc[c, "label"] for c in codes}

    global NOTAS_MODELO
    prs = Presentation(str(ORIGEN))
    orig = list(prs.slides)            # posiciones 1..31 del deck de avance
    S = lambda n: orig[n - 1]
    NOTAS_MODELO = S(1).notes_slide

    # ----------------------------------------------------------- duplicados (plantillas)
    s_taxonomia = duplicate_slide(prs, S(4))
    s_hibridos = duplicate_slide(prs, S(4))
    s_ls = duplicate_slide(prs, S(5))
    s_instancias = duplicate_slide(prs, S(26))
    s_optimo = duplicate_slide(prs, S(15))
    s_exito = duplicate_slide(prs, S(15))
    s_vs_random = duplicate_slide(prs, S(15))
    s_hib_padre = duplicate_slide(prs, S(16))
    s_presupuesto = duplicate_slide(prs, S(15))
    s_limitaciones = duplicate_slide(prs, S(23))
    s_calidad = {c: duplicate_slide(prs, S(26)) for c in codes}
    s_matrices = duplicate_slide(prs, S(21))

    # =========================================================== 1. PORTADA
    s = S(1)
    set_text(s, "TextBox 7", [["Defensa de Proyecto de ", "Título"]])
    set_notes(s, "[0:30] Buenos días. Mi nombre es Luciano Oliva y presento la defensa de mi proyecto de título: "
                 "Diseño y evaluación de arquitecturas de optimización basadas en metaheurísticas para sistemas "
                 "híbridos de energías renovables con hidrógeno verde. La idea que defiendo es doble: primero, que "
                 "este problema de dimensionamiento se puede enunciar como una optimización de caja negra con un "
                 "óptimo conocido; y segundo, que sobre ese enunciado se puede medir, con un protocolo reproducible, "
                 "qué estrategias de búsqueda, clásicas o híbridas, llegan a ese óptimo con mayor fiabilidad.")

    # =========================================================== 2. ÍNDICE
    s = S(2)
    filas = [("TextBox 8", "TextBox 9", "El problema", "Minimizar el LCOE de un sistema WPEB: formulación, dificultad y cuatro instancias."),
             ("TextBox 13", "TextBox 14", "Metaheurísticas clásicas e híbridas", "Seis clásicos, taxonomía de Talbi y tres híbridos con búsqueda local u operadores genéticos."),
             ("TextBox 18", "TextBox 19", "Protocolo e instancias", "Óptimo exacto por fuerza bruta, presupuesto idéntico y contrastes planificados."),
             ("TextBox 23", "TextBox 24", "Resultados", "Convergencia, distribución, brecha al óptimo e híbrido frente a padre en I1 a I4."),
             ("TextBox 28", "TextBox 29", "Conclusiones", "Qué queda respaldado, limitaciones y trabajo futuro.")]
    for a, b, t, sub in filas:
        set_text(s, a, t)
        set_text(s, b, sub)
    set_notes(s, "[0:30] La presentación tiene cinco partes. Primero el problema: qué se minimiza, por qué es difícil y "
                 "sobre qué instancias. Segundo, las metaheurísticas: los seis clásicos y los tres híbridos que construí "
                 "sobre ellos. Tercero, el protocolo: cómo obtuve el óptimo exacto de cada instancia y cómo comparé con "
                 "presupuesto idéntico. Cuarto, los resultados en las cuatro instancias. Y cierro con conclusiones, "
                 "limitaciones y trabajo futuro. Tengo diapositivas de respaldo con las tablas completas.")

    # =========================================================== 3. DIVISOR 01
    s = S(3)
    set_text(s, "TextBox 5", "El problema")
    set_text(s, "TextBox 7", "Qué se minimiza, sobre qué variables, con qué restricciones, y por qué es un problema de caja negra con cuatro instancias de dificultad distinta.")
    set_text(s, "TextBox 11", "Formulación: mín LCOE sobre un dominio mixto")
    set_text(s, "TextBox 13", "Cuatro instancias y la pregunta de investigación")
    set_notes(s, "[0:10] Parto por el problema, enunciado en una sola lámina.")

    # =========================================================== 4. EL PROBLEMA EN UNA LÁMINA (ex 9)
    s = S(9)
    set_text(s, "TextBox 3", "EL PROBLEMA")
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
    set_notes(s, "[1:30] Este es el problema completo. El sistema instala una capacidad renovable total fija, repartida entre "
                 "eólica, W, que es continua, y fotovoltaica, que es el complemento. La electricidad alimenta un electrolizador "
                 "comprado en módulos de u megavatios, y una batería elegida de un catálogo de potencias y duraciones. El vector "
                 "de decisión tiene cuatro coordenadas: W continua y tres discretas. Se minimiza el costo nivelado de la energía, "
                 "sujeto a cinco grupos de restricciones: el balance horario, la capacidad total, el tamaño del electrolizador, "
                 "la operación de la batería y, la que manda, la fracción anual vendida a la red. Lo esencial: el LCOE y esa "
                 "fracción no tienen fórmula; salen de simular las ocho mil setecientas sesenta horas del año. Es una caja negra "
                 "y la restricción cinco sólo se conoce al final.")

    # =========================================================== 5. POR QUÉ ES DIFÍCIL (ex 5)
    s = S(5)
    fa, fb = bf.loc[codes[0], "feasible_share"], bf.loc[codes[1], "feasible_share"]
    set_text(s, "TextBox 4", "Por qué es difícil y qué se pregunta")
    set_text(s, "TextBox 8", "Cada diseño exige simular el año hora a hora: el estado de carga de la batería acopla las horas. Sin derivadas; el presupuesto se cuenta en solicitudes de simulación.")
    set_text(s, "TextBox 10", pct(fa, 1))
    set_text(s, "TextBox 11", "Región factible estrecha")
    set_text(s, "TextBox 12", f"de los diseños enumerados en I1 respetan el límite de venta a red; en I2 (límite a la mitad) baja a {pct(fb, 1)}. El óptimo vive en el borde de esa restricción.")
    set_text(s, "TextBox 16", "W continua junto a catálogos discretos de módulos, potencia y duración: propuestas distintas colapsan en el mismo diseño y gastan evaluaciones repetidas.")
    set_text(s, "TextBox 17", [["Pregunta: ", f"con {presupuesto} solicitudes por corrida, ¿qué estrategia llega al óptimo exacto con más fiabilidad, y aporta algo la hibridación respecto de los clásicos?"]])
    set_notes(s, "[1:00] Tres razones hacen difícil el problema. Evaluar es caro: un año completo por diseño. La región factible es "
                 f"estrecha: en la instancia de referencia sólo {pct(fa, 0)} de los diseños enumerados cumple el límite de venta a red, "
                 f"y al bajar ese límite a la mitad queda {pct(fb, 0)}. Y el dominio es mixto. De ahí la pregunta de la tesis: con un "
                 "presupuesto pequeño e idéntico, qué estrategia llega al óptimo con más fiabilidad, y si hibridar los métodos clásicos "
                 "aporta algo. Para responderla hace falta un óptimo conocido, que es lo que añade esta versión del trabajo.")

    # =========================================================== 6. OBJETIVOS (ex 7)
    s = S(7)
    set_text(s, "TextBox 6", "Desarrollar y validar un marco metodológico para implementar y comparar metaheurísticas clásicas e híbridas en el dimensionamiento de sistemas híbridos con hidrógeno verde, sustentando las conclusiones en evidencia replicada y auditable.")
    set_text(s, "TextBox 8", ["1. Implementar y verificar el simulador del sistema WPEB",
                              "2. Cuantificar su reproducción del caso de referencia",
                              "3. Formular el problema, cuatro instancias y su óptimo exacto"])
    set_text(s, "TextBox 10", ["4. Ejecutar seis clásicos y tres híbridos con presupuesto idéntico en las cuatro instancias",
                               "5. Comparar calidad final, convergencia, confiabilidad y uso del presupuesto"])
    set_text(s, "TextBox 12", ["6. Contrastes planificados: cada método frente a RANDOM y cada híbrido frente a su padre",
                               "7. Medir la sensibilidad a restricciones y supuestos de datos"])
    set_notes(s, "[0:50] El objetivo general es desarrollar y validar un marco para implementar y comparar metaheurísticas, "
                 "ahora clásicas e híbridas. Los específicos se agrupan en tres: la base experimental, que incluye el simulador "
                 "verificado, su reproducción y la formulación con cuatro instancias y su óptimo exacto; la comparación de los "
                 "nueve algoritmos con presupuesto idéntico; y la evidencia: contrastes planificados frente a la línea base y "
                 "de cada híbrido frente al método del que parte, más la sensibilidad.")

    # =========================================================== 7. DIVISOR 02 (ex 6)
    s = S(6)
    set_text(s, "TextBox 5", "Metaheurísticas clásicas e híbridas")
    set_text(s, "TextBox 7", "Qué significa hibridar, cómo se construyeron los tres híbridos sobre sus padres y cómo funciona la búsqueda local en el espacio mixto.")
    set_text(s, "TextBox 11", "Seis clásicos, una línea base y la taxonomía de Talbi")
    set_notes(s, "[0:10] Ahora las metaheurísticas: los clásicos y, sobre ellos, los híbridos.")

    # =========================================================== 8. TAXONOMÍA (nuevo, plantilla 4)
    s = s_taxonomia
    set_text(s, "TextBox 3", "METAHEURÍSTICAS")
    set_text(s, "TextBox 4", "Qué es hibridar una metaheurística")
    set_text(s, "TextBox 6", "Exploración y explotación")
    set_text(s, "TextBox 7", "Los métodos poblacionales localizan regiones prometedoras; una búsqueda local refina con precisión. Con presupuesto fijo, cada evaluación va a una u otra fase.")
    set_text(s, "TextBox 9", "Hibridar = combinar componentes")
    set_text(s, "TextBox 10", "Talbi (2002): un híbrido inserta un componente de un método dentro de otro (bajo nivel) o los encadena (alto nivel), en relevo o cooperando.")
    set_text(s, "TextBox 12", "La prueba honesta: híbrido vs padre")
    set_text(s, "TextBox 13", "Conservar intacto el método base y comparar con el mismo presupuesto: así el efecto se atribuye al componente añadido, no a un reajuste.")
    set_text(s, "TextBox 15", "Taxonomía de Talbi")
    set_text(s, "TextBox 16", "Cuatro clases de diseño")
    set_text(s, "TextBox 17", ["LRH · LTH · HRH · HTH: nivel bajo/alto × relevo/cooperativo",
                               "Homogéneo o heterogéneo (mismo método o distintos)",
                               "Global o parcial (espacio completo o descompuesto)",
                               "Generalista o especialista (mismo problema o subproblema)",
                               "Los tres híbridos de esta tesis: LTH, globales, generalistas"])
    set_notes(s, "[1:20] Antes de los híbridos, qué significa hibridar. Toda metaheurística reparte su presupuesto entre explorar "
                 "y explotar. Los métodos poblacionales exploran bien; las búsquedas locales explotan bien. Hibridar, según la "
                 "taxonomía de Talbi, es combinar componentes de dos métodos: de bajo nivel cuando un componente se inserta dentro "
                 "del bucle del otro, de alto nivel cuando se encadenan; en relevo o cooperando. Los tres híbridos de esta tesis "
                 "son de bajo nivel y cooperativos. Y la prueba honesta de un híbrido es compararlo con el método del que parte, "
                 "sin modificarlo y con el mismo presupuesto: sólo así el efecto se atribuye al componente añadido.")

    # =========================================================== 9. NUEVE ALGORITMOS (ex 12)
    s = S(12)
    set_text(s, "TextBox 4", "Nueve algoritmos, un mismo presupuesto")
    set_text(s, "TextBox 5", str(n_alg)); set_text(s, "TextBox 6", "algoritmos: 6 clásicos y 3 híbridos")
    set_text(s, "TextBox 7", str(len(codes))); set_text(s, "TextBox 8", "instancias del problema")
    set_text(s, "TextBox 9", str(replicas)); set_text(s, "TextBox 10", "ejecuciones por algoritmo e instancia")
    set_text(s, "TextBox 11", str(presupuesto)); set_text(s, "TextBox 12", "solicitudes por ejecución")
    set_text(s, "TextBox 13", entero(total_req)); set_text(s, "TextBox 14", "diseños anuales simulados")
    set_text(s, "TextBox 15", "Clásicos y línea base")
    set_text(s, "TextBox 35", "Híbridos (cada uno conserva intacto a su padre)")
    set_text(s, "TextBox 36", [["GA+LS: ", "GA memético. Búsqueda local lamarckiana sobre el mejor de cada generación."],
                               ["PSO+GA: ", "PSO con reemplazo de las 5 peores partículas por hijos del GA (torneo, BLX, mutación)."],
                               ["SHO+LS: ", "SHO con búsqueda local sobre la presa de cada generación."],
                               ["Contrato de presupuesto: ", "tope duro de 600 y punto de control cada 20 solicitudes."]])
    set_notes(s, "[1:10] Los nueve algoritmos. Seis clásicos: GWO, PSO, GA, SHO, WOA y la búsqueda aleatoria como línea base "
                 "sin aprendizaje. Y tres híbridos: GA más búsqueda local, un memético; PSO más operadores genéticos; y SHO más "
                 "búsqueda local. Todos reciben exactamente seiscientas solicitudes por corrida, treinta corridas por instancia, "
                 f"en cuatro instancias: {entero(total_req)} diseños anuales simulados. Los híbridos no pueden eludir el presupuesto: "
                 "toda solicitud pasa por un contrato que la rechaza por encima de seiscientas y registra el historial cada veinte, "
                 "para que sus curvas sean comparables con las de los clásicos.")

    # =========================================================== 10. TRES HÍBRIDOS (nuevo, plantilla 4)
    s = s_hibridos
    set_text(s, "TextBox 3", "METAHEURÍSTICAS · HÍBRIDOS")
    set_text(s, "TextBox 4", "Tres híbridos construidos sobre sus padres")
    set_text(s, "TextBox 6", "GA+LS: algoritmo genético memético")
    set_text(s, "TextBox 7", "GA intacto; tras evaluar los 20, el mejor recibe hasta 4 solicitudes de búsqueda local lamarckiana. 24 por generación: 25 generaciones en vez de 30.")
    set_text(s, "TextBox 9", "PSO+GA: inyección genética")
    set_text(s, "TextBox 10", "PSO intacto; al cierre de cada iteración, las 5 peores partículas se reemplazan por hijos del GA (torneo sobre pbest, BLX, mutación), sin memoria.")
    set_text(s, "TextBox 12", "SHO+LS: hienas con intensificación")
    set_text(s, "TextBox 13", "SHO intacto, con la regla declarada para count_nos; la presa recibe la búsqueda local y guía el cerco. h decae de 5 a 0 en 25 generaciones.")
    set_text(s, "TextBox 15", "Infraestructura común")
    set_text(s, "TextBox 16", "Mixins y contrato de presupuesto")
    set_text(s, "TextBox 17", ["GeneticOperatorsMixin: los operadores del GA, reutilizados",
                               "LocalSearchMixin: la búsqueda local del espacio mixto",
                               "_evaluate_budgeted: tope de 600 y checkpoint cada 20",
                               "Codificación canónica: moverse de catálogo en catálogo",
                               "Un híbrido nuevo: unas 30 líneas sin tocar el banco"])
    set_notes(s, "[1:40] Los tres híbridos. GA más búsqueda local es un algoritmo memético: el GA no cambia; en cada generación, "
                 "tras evaluar la población, el mejor individuo recibe hasta cuatro solicitudes de búsqueda local y la mejora se "
                 "escribe de vuelta. Cada generación cuesta veinticuatro, así que caben veinticinco en vez de treinta: la hipótesis "
                 "es que la intensificación compensa las generaciones perdidas. PSO más GA conserva el bucle del enjambre y, al "
                 "cierre de cada iteración, reemplaza las cinco peores partículas por hijos de los operadores genéticos, sin memoria. "
                 "Y SHO más búsqueda local aplica la misma búsqueda a la presa de cada generación. Los tres se construyen sobre una "
                 "infraestructura común: operadores y búsqueda local como mixins, y un contrato de presupuesto que ningún híbrido "
                 "puede eludir. Escribir un híbrido nuevo son unas treinta líneas.")

    # =========================================================== 11. BÚSQUEDA LOCAL (nuevo, plantilla 5)
    s = s_ls
    set_text(s, "TextBox 3", "METAHEURÍSTICAS · BÚSQUEDA LOCAL")
    set_text(s, "TextBox 4", "La búsqueda local del espacio mixto")
    set_text(s, "TextBox 6", "4 vecinos")
    set_text(s, "TextBox 7", "W, nE, BP y k: ± un paso")
    set_text(s, "TextBox 8", "Desde el diseño canónico, en orden fijo y recordando la dirección del último éxito (Hooke–Jeeves). Primera mejora con orden de Deb; la mejora se escribe en el individuo.")
    set_text(s, "TextBox 10", "4")
    set_text(s, "TextBox 11", "por generación")
    set_text(s, "TextBox 12", "Cuentan contra las 600 de la corrida. Si el vecindario está agotado a resolución mínima, devuelve sin gastar y el presupuesto sobrante lo consume la población.")
    set_text(s, "TextBox 14", "2 → 0,01")
    set_text(s, "TextBox 15", "MW: paso adaptativo")
    set_text(s, "TextBox 16", "δW empieza en el 1 % del rango y se contrae a la mitad cuando nadie mejora. El mínimo es el paso de la fuerza bruta: nunca resuelve W más fino que el óptimo certificado.")
    set_text(s, "TextBox 17", [["Sin desperdicio: ", "vecinos fuera de límites, con el mismo diseño (k ± 1 con B = 0) o ya en el caché de la corrida no se solicitan. Se registran solicitudes y mejoras de cada corrida."]])
    set_notes(s, "[1:10] La búsqueda local es la misma para GA más LS y SHO más LS. Parte del representante canónico de un diseño "
                 "y prueba, en orden fijo, cuatro vecinos: mover W, un módulo de electrólisis más o menos, un paso del catálogo de "
                 "batería y una duración vecina. Acepta el primer vecino que mejora en el orden de Deb y reanuda desde él. Tiene "
                 "a lo sumo cuatro solicitudes por generación. El paso en W empieza en dos megavatios y se contrae a la mitad cuando "
                 "nadie mejora, hasta una centésima: el mismo paso de la fuerza bruta, así que nunca resuelve más fino que el óptimo "
                 "certificado. Y no desperdicia: los vecinos que ya están en caché o que decodifican al mismo diseño no se piden.")

    # =========================================================== 12. DIVISOR 03 (ex 8)
    s = S(8)
    set_text(s, "TextBox 5", "Protocolo e instancias")
    set_text(s, "TextBox 7", "Las cuatro instancias, el óptimo exacto de cada una por fuerza bruta y el protocolo de comparación con presupuesto idéntico.")
    set_text(s, "TextBox 11", "Cuatro instancias paramétricas")
    set_text(s, "TextBox 13", "Óptimo exacto por fuerza bruta")
    set_text(s, "TextBox 15", "Presupuesto idéntico y contrastes planificados")
    set_text(s, "TextBox 17", "Simulador validado")
    set_notes(s, "[0:10] Vamos al protocolo: las instancias, el óptimo exacto y cómo se compara.")

    # =========================================================== 13. INSTANCIAS (nuevo, plantilla 26)
    s = s_instancias
    set_text(s, "TextBox 3", "PROTOCOLO · INSTANCIAS")
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
    set_notes(s, "[1:00] Las cuatro instancias. I1 es la instancia mixta de referencia. I2 reduce a la mitad el límite de venta a "
                 "red: cambia sólo la restricción que manda y la región factible se estrecha. I3 refina los catálogos: módulos de "
                 "dos y medio megavatios, batería en pasos de dos y medio y cuatro duraciones; cinco veces más combinaciones sobre "
                 "la misma región física. I4 escala la planta a trescientos megavatios. Cada instancia cambia un aspecto, así que "
                 "cualquier diferencia de comportamiento tiene una causa declarada.")

    # =========================================================== 14. ÓPTIMO EXACTO (nuevo, plantilla 15)
    s = s_optimo
    set_text(s, "TextBox 3", "PROTOCOLO · ÓPTIMO EXACTO")
    set_text(s, "TextBox 4", "El óptimo exacto de cada instancia por fuerza bruta")
    replace_picture(s, "Picture 5", FIGS_TESIS / "fig10_envolvente_fuerza_bruta.png")
    optimos = "; ".join("{}: {}".format(c, num(bf.loc[c, "optimum_lcoe_cny_per_kwh"], 5)) for c in codes)
    set_text(s, "TextBox 6", [[f"{entero(bf_total)} diseños anuales ", f"enumerados en {num(bf_horas, 1)} h: todos los catálogos sobre W cada 0,01 MW, con despacho vectorizado y reducción por bloque."],
                              ["Verificado ", f"contra el simulador oficial en 200 celdas por instancia (dif. máx. {bf['control_max_rel_diff_lcoe'].max():.0e}) y recertificando los 10 mejores catálogos."],
                              ["Óptimos (CNY/kWh) ", optimos + ". Todos sobre el borde de AGSR: un paso más en W viola C5."]])
    set_notes(s, "[1:10] Esto es lo que convierte la comparación en una medición contra un valor conocido. Para cada instancia "
                 f"enumeré todos los catálogos discretos sobre todos los valores de W con paso de una centésima: {entero(bf_total)} "
                 f"diseños anuales en total, unas {num(bf_horas, 0)} horas de cómputo gracias a un despacho vectorizado que resuelve "
                 "cada hora para un bloque de diseños a la vez. La réplica vectorizada se contrasta contra el simulador oficial en "
                 "doscientas celdas y los diez mejores catálogos se recertifican con él. La curva es la envolvente: el mejor LCOE "
                 "factible para cada W. Los cuatro óptimos están sobre el borde de la restricción de venta a red: un paso más en W "
                 "la viola. Es la fracción vendida, no el costo, lo que detiene la mejora.")

    # =========================================================== 15. VALIDACIÓN (ex 11, se conserva)
    s = S(11)
    set_notes(s, "[0:50] Antes de comparar algoritmos hay que poder confiar en el simulador. Reconstruí el modelo de Li y lo "
                 "contrasté con los indicadores publicados: ocho de once quedan a menos de cinco por ciento y ninguno supera el "
                 "veinticinco. Sin las coordenadas exactas ni la serie de los autores, lo llamo reproducción parcial, no equivalencia. "
                 "Para esta defensa lo importante es que el simulador es el mismo para los nueve algoritmos y las cuatro instancias.")

    # =========================================================== 16. DIVISOR 04 (ex 13)
    s = S(13)
    set_text(s, "TextBox 7", "Cómo se comportan las nueve estrategias en las cuatro instancias, medidas contra el óptimo exacto, y qué diferencias resisten la prueba estadística.")
    set_text(s, "TextBox 11", "Convergencia"); set_text(s, "TextBox 13", "Distribución final y ranking")
    set_text(s, "TextBox 15", "Brecha y tasa de éxito"); set_text(s, "TextBox 17", "Frente a RANDOM")
    set_text(s, "TextBox 19", "Híbrido frente a padre"); set_text(s, "TextBox 21", "Uso del presupuesto")
    set_notes(s, "[0:10] Con el protocolo definido, los resultados.")

    # =========================================================== 17. CONVERGENCIA (ex 15)
    s = S(15)
    replace_picture(s, "Picture 5", FIGS_TESIS / "fig05_convergencia.png")
    set_text(s, "TextBox 4", "Convergencia a igual número de solicitudes")
    lider_txt = " · ".join("{} {}".format(c, lab(lid[c])) for c in codes)
    rk_random = {c: int(top_por_instancia(d, c).set_index("algorithm").loc["random", "ranking_descriptivo"]) for c in codes}
    set_text(s, "TextBox 6", [["Mediana y rango intercuartil ", "del mejor LCOE factible frente a las solicitudes acumuladas; la línea punteada es el óptimo exacto."],
                              ["Lidera por mediana: ", lider_txt + "."],
                              ["RANDOM ", ("ocupa el lugar {} en las {} instancias.".format(rk_random[codes[0]], len(codes))
                                           if len(set(rk_random.values())) == 1 else
                                           "ocupa el lugar " + ", ".join("{} en {}".format(rk_random[c], c) for c in codes) + ".")]])
    set_notes(s, "[1:20] Las curvas de convergencia, un panel por instancia, con las solicitudes acumuladas en el eje horizontal: "
                 "en cada punto los nueve han visto el mismo número de diseños, incluidos los híbridos con búsqueda local. La línea "
                 f"punteada es el óptimo exacto. Por mediana final lidera {lider_txt}. La búsqueda aleatoria, en gris, queda "
                 + ", ".join("en el lugar {} en {}".format(rk_random[c], c) for c in codes) + ". Lo que importa no es quién llega "
                 "primero sino cuán cerca del óptimo y con qué consistencia.")

    # =========================================================== 18. DISTRIBUCIÓN Y RANKING (ex 16)
    s = S(16)
    replace_picture(s, "Picture 5", FIGS_TESIS / "fig06_distribucion_scores.png")
    set_text(s, "TextBox 4", "La distribución importa más que el mejor valor")
    filas = [["Alg."] + codes + ["Medio"]]
    for _, r in cross.iterrows():
        filas.append([lab(r["algorithm"])] + [entero(r["rank_" + c]) for c in codes] + [num(r["mean_rank"], 2)])
    fill_table(s, "Table 6", filas, [0.95, 0.5, 0.5, 0.5, 0.5, 0.8], font_pt=9, row_height_in=0.215)
    primero, segundo = cross.iloc[0], cross.iloc[1]
    set_text(s, "TextBox 7", [[lab(primero["algorithm"]) + " ", f"obtiene el mejor rango medio ({num(primero['mean_rank'], 2)}); le sigue {lab(segundo['algorithm'])} ({num(segundo['mean_rank'], 2)})."],
                              ["El orden cambia de instancia a instancia: ", "ninguna estrategia domina en las cuatro geometrías."]])
    set_notes(s, "[1:20] Esta es la lámina central. A la izquierda, la distribución del LCOE final de las treinta corridas de cada "
                 "algoritmo, por instancia, ordenadas por mediana; la línea punteada es el óptimo. A la derecha, el rango por mediana "
                 f"en cada instancia y el rango medio. {lab(primero['algorithm'])} tiene el mejor rango medio y {lab(segundo['algorithm'])} "
                 "el segundo. Pero fíjense en que el orden cambia de instancia a instancia: ninguna estrategia domina en las cuatro. "
                 "Eso es, en sí mismo, un resultado, y es coherente con el teorema de la no existencia de almuerzo gratis.")

    # =========================================================== 19. BRECHA Y ÉXITO (nuevo, plantilla 15)
    s = s_exito
    set_text(s, "TextBox 3", "RESULTADOS · CONFIABILIDAD")
    set_text(s, "TextBox 4", "¿Con qué frecuencia se llega cerca del óptimo?")
    replace_picture(s, "Picture 5", FIGS_PRES / "pres_exito.png")
    mejor_exito = d["rank"].sort_values("success_0.5pct", ascending=False).iloc[0]
    peor_gap = d["rank"].groupby("algorithm")["median_gap_pct"].mean().sort_values()
    set_text(s, "TextBox 6", [["Tasa de éxito: ", "fracción de las 30 corridas que termina a menos de 0,5 % del óptimo exacto de su instancia."],
                              ["Máximo observado: ", f"{lab(mejor_exito['algorithm'])} en {mejor_exito['instance']}, {pct(mejor_exito['success_0.5pct'], 0)} de las corridas."],
                              ["Brecha mediana promedio: ", f"la menor es de {lab(peor_gap.index[0])} ({num(peor_gap.iloc[0], 3)} %) y la mayor de {lab(peor_gap.index[-1])} ({num(peor_gap.iloc[-1], 3)} %)."]])
    set_notes(s, "[1:00] Otra lectura: la tasa de éxito, es decir, en qué fracción de las corridas un algoritmo termina a menos de "
                 f"medio por ciento del óptimo exacto. El máximo lo alcanza {lab(mejor_exito['algorithm'])} en {mejor_exito['instance']}. "
                 f"En brecha mediana promedio sobre las cuatro instancias, la menor es la de {lab(peor_gap.index[0])} y la mayor la de "
                 f"{lab(peor_gap.index[-1])}. Esto es lo que un usuario quiere saber: si corro este método una vez, cuán cerca quedo.")

    # =========================================================== 20. FRENTE A RANDOM (nuevo, plantilla 15)
    s = s_vs_random
    set_text(s, "TextBox 3", "RESULTADOS · INFERENCIA")
    set_text(s, "TextBox 4", "¿Le ganan a la búsqueda aleatoria?")
    replace_picture(s, "Picture 5", FIGS_PRES / "pres_vs_random.png")
    planned = d["tests"][(d["tests"]["family"] == "planned") & (d["tests"]["algoritmo_b"] == "random")]
    gana = {c: [lab(a) for a in planned[(planned["instance"] == c) & planned["significativo_alpha_0.05"].map(truthy) & (planned["a12"] > 0.5)]["algoritmo_a"]] for c in codes}
    resumen_gana = "; ".join("{}: {}".format(c, ", ".join(gana[c]) if gana[c] else "ninguno") for c in codes)
    set_text(s, "TextBox 6", [["A12 frente a RANDOM ", "con intervalo bootstrap al 95 %; marcador lleno = significativo tras Holm en la familia planificada de la instancia (12 contrastes)."],
                              ["Ventaja detectable ", resumen_gana + "."],
                              ["Lectura: ", "no superar a RANDOM bajo este presupuesto no prueba igualdad; expresa ausencia de evidencia."]])
    set_notes(s, "[1:10] Primera pregunta de inferencia: ¿aprenden algo, o daría lo mismo muestrear al azar? Para cada instancia, el "
                 "tamaño de efecto A12 de cada metaheurística frente a RANDOM, con su intervalo. Más de cero coma cinco significa que "
                 "gana más seguido. Los contrastes se corrigen por Holm dentro de una familia planificada de doce por instancia: ocho "
                 "frente a RANDOM y cuatro híbrido frente a padre; corregir sobre los treinta y seis pares sacrificaría potencia en "
                 f"contrastes que no interesan. Con ventaja detectable: {resumen_gana}.")

    # =========================================================== 21. HÍBRIDO VS PADRE (nuevo, plantilla 16)
    s = s_hib_padre
    set_text(s, "TextBox 3", "RESULTADOS · HÍBRIDOS")
    set_text(s, "TextBox 4", "¿Aporta la hibridación? Híbrido frente a padre")
    replace_picture(s, "Picture 5", FIGS_PRES / "pres_hibrido_vs_padre.png")
    filas = [["Par"] + codes]
    for h, p in HYBRID_PAIRS:
        fila = ["{} vs {}".format(lab(h), lab(p))]
        for c in codes:
            sub = hyb[(hyb["instance"] == c) & (hyb["hibrido"] == h) & (hyb["padre"] == p)]
            if sub.empty:
                fila.append("--")
            else:
                r = sub.iloc[0]
                fila.append(num(r["a12_hibrido_vs_padre"], 2) + ("*" if truthy(r["significativo_alpha_0.05"]) else ""))
        filas.append(fila)
    fill_table(s, "Table 6", filas, [1.55, 0.55, 0.55, 0.55, 0.55], font_pt=9.5, row_height_in=0.3)
    n_win = int(hyb["hibrido_mejor_mediana"].map(truthy).sum())
    n_sig = int(hyb["significativo_alpha_0.05"].map(truthy).sum())
    n_sig_win = int((hyb["significativo_alpha_0.05"].map(truthy) & hyb["hibrido_mejor_mediana"].map(truthy)).sum())
    set_text(s, "TextBox 7", [["El híbrido mejora la mediana de su padre ", f"en {n_win} de {len(hyb)} contrastes; {n_sig} son significativos tras Holm ({n_sig_win} a favor del híbrido)."],
                              ["A12 > 0,5: ", "gana el híbrido. * = significativo. El saldo depende del par y de la instancia."]])
    set_notes(s, "[1:30] La pregunta central de esta extensión: ¿aporta la hibridación? Cada híbrido contra su padre, en cada "
                 f"instancia: dieciséis contrastes. El híbrido obtiene mejor mediana que su padre en {n_win} de {len(hyb)}, y la "
                 f"diferencia es significativa tras Holm en {n_sig}, {n_sig_win} a favor del híbrido. La conclusión es que añadir una "
                 "búsqueda local o un operador genético no es una mejora gratuita: redistribuye un presupuesto fijo entre explorar y "
                 "explotar, y el saldo depende del par y de la geometría de la instancia. Donde el óptimo está en un borde estrecho, "
                 "la intensificación sobre el mejor individuo tiende a rendir; donde el presupuesto escasea frente al número de "
                 "combinaciones, cada evaluación cedida a la intensificación se resta a la exploración. Dos lecturas concretas: "
                 "PSO más GA supera a GA en I2 e I4, pero nunca a PSO; es decir, la ventaja viene del bucle del enjambre y la "
                 "inyección genética no suma ni resta. Y SHO más búsqueda local es el mejor de todos en I2, la instancia de región "
                 "estrecha, pero cae al sexto lugar en I3, donde los catálogos finos multiplican las combinaciones.")

    # =========================================================== 22. USO DEL PRESUPUESTO (nuevo, plantilla 15)
    s = s_presupuesto
    set_text(s, "TextBox 3", "RESULTADOS · USO DEL PRESUPUESTO")
    set_text(s, "TextBox 4", "Cómo se gastan las 600 solicitudes")
    replace_picture(s, "Picture 5", FIGS_PRES / "pres_presupuesto.png")
    dup = d["rank"].groupby("algorithm")["mean_duplicates"].mean()
    ls_req = d["rank"].groupby("algorithm")["mean_ls_requests"].mean() if "mean_ls_requests" in d["rank"].columns else None
    set_text(s, "TextBox 6", [["Duplicados: ", f"GA repite en promedio {num(dup['ga'], 0)} de 600 solicitudes; GA+LS, {num(dup['ga_ls'], 0)}; PSO+GA, {num(dup['pso_ga'], 0)}."],
                              ["Búsqueda local: ", (f"GA+LS gasta {num(ls_req['ga_ls'], 0)} solicitudes por corrida en intensificación y SHO+LS, {num(ls_req['sho_ls'], 0)}." if ls_req is not None else "")],
                              ["Lectura: ", "con presupuesto idéntico, las diferencias de tiempo vienen del operador de movimiento, no de la búsqueda."]])
    set_notes(s, "[0:50] Cómo se gasta el presupuesto. Las solicitudes duplicadas, un diseño ya evaluado que se vuelve a pedir, "
                 f"cuentan contra las seiscientas: GA repite en promedio {num(dup['ga'], 0)}. Y los híbridos con búsqueda local "
                 f"invierten parte del presupuesto en intensificar: GA más LS unas {num(ls_req['ga_ls'], 0) if ls_req is not None else '--'} "
                 "solicitudes por corrida. Es el costo que se paga por explotar.")

    # =========================================================== 23. DIVISOR 05 (ex 22)
    s = S(22)
    set_text(s, "TextBox 5", "Conclusiones")
    set_text(s, "TextBox 7", "Qué afirmaciones quedan respaldadas por la evidencia, cuáles son las limitaciones y qué sigue.")
    set_text(s, "TextBox 11", "Qué se puede afirmar"); set_text(s, "TextBox 13", "Limitaciones y trabajo futuro"); set_text(s, "TextBox 15", "Síntesis")
    set_notes(s, "[0:10] Cierro con las conclusiones.")

    # =========================================================== 24. QUÉ SE PUEDE AFIRMAR (ex 23)
    s = S(23)
    set_text(s, "TextBox 3", "CONCLUSIONES")
    set_text(s, "TextBox 7", [f"El problema queda enunciado como mín LCOE sobre un dominio mixto, con cuatro instancias y su óptimo exacto ({entero(bf_total)} diseños enumerados)",
                              f"Tres híbridos construidos sin modificar a sus padres, con presupuesto idéntico de {presupuesto} solicitudes",
                              f"Por rango medio lidera {lab(primero['algorithm'])}; el orden cambia entre instancias",
                              f"La hibridación mejora la mediana del padre en {n_win} de {len(hyb)} contrastes ({n_sig} significativos)",
                              "Un flujo auditable: cada cifra sale del cuaderno ejecutado; I1 reproduce bit a bit la comparativa previa"])
    set_text(s, "TextBox 10", ["Un solo sitio aproximado y un solo año meteorológico; instancias paramétricas, no otros recursos ni costos",
                               "Capacidad renovable fija por instancia; sin demanda explícita de hidrógeno",
                               "LCOE como único objetivo",
                               "Hiperparámetros de clásicos e híbridos fijados a priori; sin ablación de la búsqueda local",
                               "SHO requiere una regla de agrupación declarada"])
    set_notes(s, "[1:20] ¿Qué queda respaldado? El problema está enunciado formalmente y tiene un óptimo conocido en cada "
                 "instancia. Los tres híbridos se construyeron sin tocar a sus padres y con el mismo presupuesto, lo que hace "
                 f"atribuible cualquier diferencia al componente añadido. Por rango medio lidera {lab(primero['algorithm'])}, pero el "
                 f"orden cambia entre instancias. La hibridación mejora la mediana del padre en {n_win} de {len(hyb)} contrastes. Y "
                 "todo sale de un cuaderno ejecutado, verificado contra la versión anterior bit a bit. ¿Qué no se puede afirmar? "
                 "Superioridad general: un sitio, un año, instancias paramétricas, LCOE como único objetivo e hiperparámetros sin ajuste.")

    # =========================================================== 25. LIMITACIONES Y TRABAJO FUTURO (nuevo, plantilla 23)
    s = s_limitaciones
    set_text(s, "TextBox 3", "CONCLUSIONES")
    set_text(s, "TextBox 4", "Aporte a la Ingeniería Informática y trabajo futuro")
    set_text(s, "TextBox 6", "Aporte")
    set_text(s, "TextBox 7", ["Infraestructura de hibridación reutilizable: mixins de operadores y búsqueda local, contrato de presupuesto, codificación canónica del espacio mixto",
                              "Óptimo exacto por enumeración vectorizada con reducción por bloque, verificado y cacheado",
                              "Protocolo con familia planificada de contrastes y lectura transversal descriptiva",
                              "Tablas, figuras y macros del documento generadas desde los CSV: cero transcripción manual"])
    set_text(s, "TextBox 9", "Trabajo futuro")
    set_text(s, "TextBox 10", ["Más años y sitios; instancias que cambien la estructura de costos",
                               "Ablación de la profundidad de la búsqueda local y del número de individuos refinados",
                               "Híbridos de alto nivel en relevo y componentes de aprendizaje (selección de operadores)",
                               "Capacidad renovable libre, demanda de hidrógeno y formulación multiobjetivo",
                               "Modelos sustitutos con su error dentro del presupuesto"])
    set_notes(s, "[1:00] El aporte informático es una infraestructura de hibridación reutilizable, un óptimo exacto obtenido por "
                 "enumeración vectorizada y un flujo en el que cada cifra del documento se genera desde los datos. Como trabajo futuro: "
                 "más años y sitios, una ablación de la búsqueda local, híbridos de alto nivel y componentes de aprendizaje, y la "
                 "formulación multiobjetivo.")

    # =========================================================== 26. CIERRE (ex 25)
    s = S(25)
    set_text(s, "TextBox 4", "Óptimo conocido, presupuesto idéntico y una pregunta medible: ¿aporta la hibridación?")
    set_text(s, "TextBox 5", "Gracias. ¿Preguntas?")
    set_notes(s, "[0:30] En síntesis: un problema con óptimo conocido, nueve estrategias con el mismo presupuesto y una pregunta "
                 "honesta sobre la hibridación, cuya respuesta depende del par y de la instancia y ahora se puede medir. Muchas "
                 "gracias; quedo atento a sus preguntas.")

    # =========================================================== RESPALDO
    for c in codes:
        s = s_calidad[c]
        set_text(s, "TextBox 4", f"Calidad final completa en {c} ({etiqueta[c]})")
        rk = top_por_instancia(d, c)
        filas = [["Algoritmo", "Mediana", "IQR", "Mejor", "Peor", "Brecha med. %", "≤ 0,1 %", "≤ 0,5 %", "≤ 1 %"]]
        for _, r in rk.iterrows():
            filas.append([lab(r["algorithm"]), num(r["median"], 6), num(r["iqr"], 6), num(r["best"], 6), num(r["worst"], 6),
                          num(r["median_gap_pct"], 3), pct(r["success_0.1pct"], 0), pct(r["success_0.5pct"], 0), pct(r["success_1.0pct"], 0)])
        fill_table(s, "Table 5", filas, [1.1, 1.0, 1.0, 1.0, 1.0, 1.1, 0.9, 0.9, 0.9], font_pt=8.5, row_height_in=0.24)
        o = bf.loc[c]
        set_text(s, "TextBox 6", f"LCOE en CNY/kWh. Brecha respecto del óptimo exacto de {c} ({num(o['optimum_lcoe_cny_per_kwh'], 6)}; W={num(o['optimum_wind_mw'], 2)}, E={num(o['optimum_electrolyzer_mw'], 1)}, B={num(o['optimum_battery_mw'], 1)} MW × {num(o['optimum_battery_duration_h'], 0)} h). {replicas} ejecuciones por algoritmo. Factibles mínimas por algoritmo: {int(rk['feasible_runs'].min())}/{replicas}.")
        set_notes(s, f"[RESPALDO] Usar si preguntan por valores exactos en {c}. Mediana, IQR, mejor, peor, brecha mediana al óptimo exacto y tasas de éxito.")

    s = S(27)
    set_text(s, "TextBox 4", "Configuración de los nueve algoritmos")
    filas = [["Código", "Familia", "Configuración"]]
    for _, r in d["hyper"].iterrows():
        filas.append([lab(r["codigo"]), str(r["familia"]), str(r["hiperparametros"])])
    fill_table(s, "Table 5", filas, [1.0, 1.9, 6.1], font_pt=7.5, row_height_in=0.235)
    set_text(s, "TextBox 6", [f"Población {int(meta['population'])} × {int(meta['iterations'])} iteraciones = {presupuesto} solicitudes por ejecución (o su equivalente en los híbridos) · semillas de réplica 42–71 · flujo propio por algoritmo y réplica, independiente de la instancia · sin ajuste posterior.",
                              "Búsqueda local: 4 solicitudes por generación, δW del 1 % del rango a 0,01 MW (×0,5). PSO+GA: 5 hijos por iteración, sin memoria."])
    set_notes(s, "[RESPALDO] Usar si preguntan por hiperparámetros. Valores canónicos de la literatura para los clásicos; búsqueda local e inyección genética con valores fijados a priori.")

    s = S(28)
    set_text(s, "TextBox 4", f"Pruebas frente a la búsqueda aleatoria en {codes[0]}")
    vr = planned[planned["instance"] == codes[0]]
    filas = [["Algoritmo", "p (Mann–Whitney)", "p ajustado (Holm)", "A12 vs RANDOM", "IC 95 % bootstrap", "Lectura"]]
    for _, r in vr.iterrows():
        sig = truthy(r["significativo_alpha_0.05"])
        lectura = ("ventaja detectable" if sig and r["a12"] > 0.5 else "desventaja detectable" if sig else "sin diferencia detectable")
        filas.append([lab(r["algoritmo_a"]), pvalor(r["p_value"]), pvalor(r["p_value_holm"]), num(r["a12"], 2),
                      f"[{num(r['a12_ci_low'], 2)}; {num(r['a12_ci_high'], 2)}]", lectura])
    fill_table(s, "Table 5", filas, [1.1, 1.5, 1.5, 1.3, 1.6, 2.0], font_pt=8.5, row_height_in=0.24)
    set_text(s, "TextBox 6", ["A12 = probabilidad de que el algoritmo logre menor LCOE que RANDOM en un enfrentamiento al azar. Holm dentro de la familia planificada de 12 contrastes por instancia.",
                              "Las otras instancias y la matriz completa de 36 pares están en el documento (anexo de contrastes)."])
    set_notes(s, "[RESPALDO] Usar si preguntan por los valores p o por la corrección. Familia planificada: ocho contrastes frente a RANDOM y cuatro híbrido frente a padre por instancia.")

    s = s_matrices
    set_text(s, "TextBox 3", "RESPALDO")
    set_text(s, "TextBox 4", "Todos los pares: matrices A12 por instancia")
    replace_picture(s, "Picture 5", FIGS_TESIS / "fig11_matrices_a12.png")
    n_all = d["tests"][d["tests"]["family"] == "all"]
    sig_all = {c: int(n_all[n_all["instance"] == c]["significativo_alpha_0.05"].map(truthy).sum()) for c in codes}
    set_text(s, "TextBox 8", "Los 36 pares, con Holm sobre los 36")
    set_text(s, "TextBox 9", "Pares significativos: " + "; ".join("{}: {}".format(c, sig_all[c]) for c in codes) + ".")
    set_text(s, "TextBox 11", [["¿Por qué una familia planificada? ", "Con 36 pares, Holm exige p muy pequeños y sacrifica potencia en contrastes que no interesan; los 12 planificados responden las dos preguntas de la tesis."]])
    set_text(s, "TextBox 13", "El ranking por mediana es descriptivo; la inferencia es por instancia.")
    set_text(s, "TextBox 14", "Mann–Whitney bilateral · Holm · A12 con IC bootstrap al 95 %")
    set_notes(s, "[RESPALDO] Usar si preguntan por las comparaciones entre metaheurísticas. Matrices completas de A12 y número de pares significativos con Holm sobre los 36.")

    s = S(19)
    set_text(s, "TextBox 5", f"Las {replicas} ejecuciones de cada algoritmo dan valores distintos. Antes de afirmar que uno es mejor, tres preguntas por instancia.")
    set_text(s, "TextBox 10", "Mira los nueve grupos juntos y responde sí o no, sin decir entre quiénes.")
    set_text(s, "TextBox 11", "Resultado por instancia en el documento")
    set_text(s, "TextBox 17", "12 contrastes planificados por instancia")
    set_text(s, "TextBox 25", [["Corrección de Holm: ", "dentro de la familia planificada (8 frente a RANDOM + 4 híbrido frente a padre). La matriz completa de 36 pares, con Holm sobre los 36, va al anexo."]])
    set_notes(s, "[RESPALDO] Usar si preguntan cómo se hace la inferencia: Kruskal-Wallis global, Mann-Whitney por pares, A12 como tamaño de efecto y Holm dentro de la familia planificada.")

    s = S(10)
    set_text(s, "TextBox 3", "RESPALDO")
    set_notes(s, "[RESPALDO] Usar si preguntan cómo opera un diseño: tres días de mayo del mejor diseño de la comparativa previa en I1, que coincide con la región del óptimo exacto (W cerca de 142 MW, 18 módulos, batería de 20 MW por 1 h).")

    for n in (29, 30, 31):
        s = S(n)
        set_notes(s, s.notes_slide.notes_text_frame.text if s.has_notes_slide else "[RESPALDO]")

    # =========================================================== ORDEN FINAL
    cuerpo = [S(1), S(2), S(3), S(9), S(5), S(7), S(6), s_taxonomia, S(12), s_hibridos, s_ls,
              S(8), s_instancias, s_optimo, S(11), S(13), S(15), S(16), s_exito, s_vs_random,
              s_hib_padre, s_presupuesto, S(22), S(23), s_limitaciones, S(25)]
    respaldo = [s_calidad[c] for c in codes] + [S(27), S(28), s_matrices, S(19), S(10), S(29), S(30), S(31)]
    reorder_and_prune(prs, cuerpo + respaldo)

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(DESTINO))
    print(DESTINO, "->", len(cuerpo), "diapositivas de cuerpo +", len(respaldo), "de respaldo")


if __name__ == "__main__":
    main()
