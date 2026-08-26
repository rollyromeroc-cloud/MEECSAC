"""Lámina cartográfica en PDF (A3 apaisado) de la seguridad de polvorín:
mapa georreferenciado a escala, con grilla UTM rotulada, norte, escala
gráfica y numérica, leyenda y cajetín MEECSAC.

Se dibuja VECTORIAL directamente con el canvas de reportlab, no exportando
una imagen de Plotly: `fig.to_image()` depende de kaleido/Chrome, que ya
provocó una caída en producción (ver el pin y la nota en
`requirements.txt`) y en algunas versiones se cuelga en vez de fallar — un
cuelgue no lo atrapa un `try/except`. Dibujar aquí no añade ninguna
dependencia (reportlab ya se usa para las otras fichas) y además sale en
vector, que es lo que se espera de un plano.

No calcula distancias ni EMR: recibe lo que ya calculó `core.polvorin`.
"""

from __future__ import annotations

import datetime as _dt
import math
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as _canvas

from core.geoexport import circulo_utm, epsg_utm
from core.models import DatosGenerales, Polvorin, PuntoRiesgo, ResultadoDistancia
from core.polvorin import emr_kg_polvorin

LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "logo_meecsac.jpg"
PAGE_SIZE = landscape(A3)

MEECSAC_DARK = colors.HexColor("#33454E")
MEECSAC_CYAN = colors.HexColor("#00A7E3")
MEECSAC_GRIS = colors.HexColor("#F2F5F6")
COLOR_POLVORIN = colors.HexColor("#E63946")
COLOR_PUNTO = colors.HexColor("#1D3557")
COLOR_RADIO = colors.HexColor("#2A9D8F")
COLOR_GRILLA = colors.HexColor("#C8D2D7")
COLOR_OK = colors.HexColor("#2A9D8F")
COLOR_ALERTA = colors.HexColor("#E63946")

# Escalas normalizadas de plano (1:N). Se elige la primera que encuadre
# todo el contenido — un plano se rotula a escala redonda, no a una escala
# arbitraria tipo 1:3721.
ESCALAS_NORMALIZADAS = (
    100, 200, 250, 500, 1000, 1250, 2000, 2500, 5000,
    10000, 20000, 25000, 50000, 100000, 200000,
)
MARGEN_FRACCION = 0.08  # holgura alrededor del contenido, antes de encuadrar


def _extension(
    polvorines: list[Polvorin], puntos: list[PuntoRiesgo]
) -> tuple[float, float, float, float]:
    """(este_min, este_max, norte_min, norte_max) de todo lo que se dibuja,
    incluyendo cercos y radios de influencia (no solo los puntos, o el
    círculo de seguridad se saldría del encuadre)."""
    estes: list[float] = []
    nortes: list[float] = []
    for p in polvorines:
        estes.append(p.este_utm)
        nortes.append(p.norte_utm)
        for e, n in p.vertices_cerco:
            estes.append(e)
            nortes.append(n)
        if p.radio_influencia_m:
            estes += [p.este_utm - p.radio_influencia_m, p.este_utm + p.radio_influencia_m]
            nortes += [p.norte_utm - p.radio_influencia_m, p.norte_utm + p.radio_influencia_m]
    for punto in puntos:
        estes.append(punto.este_utm)
        nortes.append(punto.norte_utm)
    if not estes:
        return 0.0, 1.0, 0.0, 1.0
    return min(estes), max(estes), min(nortes), max(nortes)


def elegir_escala(ancho_m: float, alto_m: float, ancho_pt: float, alto_pt: float) -> int:
    """Menor escala normalizada 1:N en la que `ancho_m × alto_m` entra en el
    marco de dibujo. Devuelve la mayor de la lista si nada encuadra (mejor
    un plano apretado que uno que recorta contenido)."""
    ancho_m = max(ancho_m, 1e-6)
    alto_m = max(alto_m, 1e-6)
    for escala in ESCALAS_NORMALIZADAS:
        # 1 m real = (1/escala) m de papel = (1000/escala) mm de papel
        if (ancho_m * 1000.0 / escala) * mm <= ancho_pt and (alto_m * 1000.0 / escala) * mm <= alto_pt:
            return escala
    return ESCALAS_NORMALIZADAS[-1]


def _paso_grilla(escala: int) -> float:
    """Separación (m) entre líneas de grilla UTM: se busca un paso redondo
    que caiga cerca de 40 mm de papel, que es la densidad legible típica de
    un plano."""
    objetivo_m = 40.0 * escala / 1000.0
    candidatos = [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000, 10000]
    return float(min(candidatos, key=lambda c: abs(c - objetivo_m)))


def _flecha_norte(c: _canvas.Canvas, x: float, y: float, tam: float) -> None:
    """Norte cartográfico: como todo se dibuja en UTM sin rotación, el
    norte de cuadrícula es exactamente +Y del papel."""
    c.saveState()
    c.setFillColor(MEECSAC_DARK)
    c.setStrokeColor(MEECSAC_DARK)
    p = c.beginPath()
    p.moveTo(x, y + tam)
    p.lineTo(x - tam * 0.28, y - tam * 0.35)
    p.lineTo(x, y - tam * 0.12)
    p.lineTo(x + tam * 0.28, y - tam * 0.35)
    p.close()
    c.drawPath(p, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(x, y + tam + 3, "N")
    c.restoreState()


def _escala_grafica(c: _canvas.Canvas, x: float, y: float, escala: int, ancho_max: float) -> None:
    """Escala gráfica de barras alternadas, rotulada en metros. La longitud
    se elige redonda (1/2/5 × 10^n) para que los rótulos sean legibles."""
    candidatos = [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000]
    largo_m = 10.0
    for cand in candidatos:
        if (cand * 1000.0 / escala) * mm <= ancho_max:
            largo_m = float(cand)
    largo_pt = (largo_m * 1000.0 / escala) * mm

    n_div = 4
    alto = 3.2 * mm
    c.saveState()
    for i in range(n_div):
        x0 = x + largo_pt * i / n_div
        c.setFillColor(MEECSAC_DARK if i % 2 == 0 else colors.white)
        c.setStrokeColor(MEECSAC_DARK)
        c.rect(x0, y, largo_pt / n_div, alto, fill=1, stroke=1)
    c.setFillColor(MEECSAC_DARK)
    c.setFont("Helvetica", 6.5)
    for i in range(n_div + 1):
        valor = largo_m * i / n_div
        etiqueta = f"{valor:,.0f}" if valor == int(valor) else f"{valor:,.1f}"
        c.drawCentredString(x + largo_pt * i / n_div, y - 7, etiqueta)
    c.drawString(x + largo_pt + 4, y, "m")
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x, y + alto + 4, f"ESCALA 1:{escala:,}".replace(",", " "))
    c.restoreState()


ALTO_ENCABEZADO_CAJETIN = 21 * mm
ALTO_FILA_CAJETIN = 5.2 * mm


def _cajetin(
    c: _canvas.Canvas, x: float, y_top: float, ancho: float,
    datos: DatosGenerales | None, escala: int, zona_utm: int, hemisferio: str,
) -> float:
    """Cajetín del plano: identificación, CRS y firmas. Se dibuja hacia
    abajo desde `y_top` y calcula su propia altura a partir del número de
    filas — con un alto fijo, agregar un campo desbordaba el recuadro.
    Devuelve la altura ocupada. Los campos vacíos se dejan en blanco (no se
    inventa un responsable)."""
    d = datos or DatosGenerales()
    filas = [
        ("Concesión", d.nombre_concesion or ""),
        ("Empresa", d.empresa or ""),
        ("Cliente", d.cliente or ""),
        ("Ubicación", " / ".join(v for v in (d.distrito, d.provincia, d.departamento) if v)),
        ("Sistema", f"UTM WGS 84 — Zona {zona_utm}{hemisferio} (EPSG:{epsg_utm(zona_utm, hemisferio)})"),
        ("Escala", f"1:{escala:,}".replace(",", " ")),
        ("Plano N.°", d.numero_plano or ""),
        ("Revisión", d.revision or ""),
        ("Elaborado", d.elaborado_por or ""),
        ("Revisado", d.revisado_por or ""),
        ("Aprobado", d.aprobado_por or ""),
        ("Fecha", _dt.date.today().strftime("%d/%m/%Y")),
    ]
    alto = ALTO_ENCABEZADO_CAJETIN + ALTO_FILA_CAJETIN * len(filas) + 2 * mm
    y = y_top - alto

    c.saveState()
    c.setStrokeColor(MEECSAC_DARK)
    c.setLineWidth(1)
    c.rect(x, y, ancho, alto, fill=0, stroke=1)

    if LOGO_PATH.exists():
        try:
            c.drawImage(
                str(LOGO_PATH), x + 3 * mm, y_top - 15 * mm,
                width=21 * mm, height=12 * mm, preserveAspectRatio=True, mask="auto",
            )
        except Exception:
            # el cajetín no debe caerse por un logo ilegible
            pass

    c.setFillColor(MEECSAC_DARK)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x + 26 * mm, y_top - 6 * mm, "MEECSAC")
    c.setFont("Helvetica", 6.5)
    c.drawString(x + 26 * mm, y_top - 10 * mm, "Más que Explosivos")
    c.drawString(x + 26 * mm, y_top - 13.5 * mm, "Plano de seguridad de polvorín")

    y_fila = y_top - ALTO_ENCABEZADO_CAJETIN
    for etiqueta, valor in filas:
        c.setFont("Helvetica-Bold", 6.5)
        c.setFillColor(MEECSAC_DARK)
        c.drawString(x + 3 * mm, y_fila, f"{etiqueta}:")
        c.setFont("Helvetica", 6.5)
        c.setFillColor(colors.black)
        c.drawString(x + 22 * mm, y_fila, str(valor)[:52])
        y_fila -= ALTO_FILA_CAJETIN
    c.restoreState()
    return alto


def _leyenda(
    c: _canvas.Canvas, x: float, y: float, ancho: float, hay_radio: bool, hay_cerco: bool
) -> float:
    """Leyenda del plano. Devuelve la altura ocupada, para que el llamador
    apile el cajetín debajo sin solaparse."""
    c.saveState()
    alto_fila = 6.5 * mm
    entradas: list[tuple[str, str]] = [
        ("punto_rojo", "Polvorín"),
        ("punto_azul", "Punto de riesgo"),
        ("linea_gris", "Distancia verificada"),
    ]
    if hay_cerco:
        entradas.append(("poligono", "Cerco perimétrico"))
    if hay_radio:
        entradas.append(("circulo", "Radio de influencia"))

    alto_total = alto_fila * len(entradas) + 9 * mm
    c.setStrokeColor(MEECSAC_DARK)
    c.setFillColor(MEECSAC_GRIS)
    c.rect(x, y - alto_total, ancho, alto_total, fill=1, stroke=1)
    c.setFillColor(MEECSAC_DARK)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x + 3 * mm, y - 6 * mm, "LEYENDA")

    y_fila = y - 11.5 * mm
    for clave, etiqueta in entradas:
        cx = x + 6 * mm
        if clave == "punto_rojo":
            c.setFillColor(COLOR_POLVORIN)
            c.circle(cx, y_fila + 1, 2.4, fill=1, stroke=0)
        elif clave == "punto_azul":
            c.setFillColor(COLOR_PUNTO)
            c.circle(cx, y_fila + 1, 2.4, fill=1, stroke=0)
        elif clave == "linea_gris":
            c.setStrokeColor(colors.grey)
            c.setDash(2, 2)
            c.line(cx - 3, y_fila + 1, cx + 3, y_fila + 1)
            c.setDash()
        elif clave == "poligono":
            c.setStrokeColor(COLOR_POLVORIN)
            c.setFillColor(colors.Color(0.9, 0.22, 0.27, alpha=0.12))
            c.rect(cx - 3, y_fila - 1.5, 6, 5, fill=1, stroke=1)
        else:
            c.setStrokeColor(COLOR_RADIO)
            c.setDash(3, 2)
            c.circle(cx, y_fila + 1, 3, fill=0, stroke=1)
            c.setDash()
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 7)
        c.drawString(x + 12 * mm, y_fila - 1, etiqueta)
        y_fila -= alto_fila

    c.restoreState()
    return alto_total


def build_mapa_pdf(
    polvorines: list[Polvorin],
    puntos: list[PuntoRiesgo],
    resultados_por_polvorin: dict[str, list[ResultadoDistancia]],
    zona_utm: int,
    hemisferio: str,
    datos: DatosGenerales | None = None,
) -> BytesIO:
    """Lámina A3 apaisada con el mapa a escala normalizada, grilla UTM,
    norte, escala gráfica, leyenda y cajetín."""
    buffer = BytesIO()
    c = _canvas.Canvas(buffer, pagesize=PAGE_SIZE)
    ancho_pag, alto_pag = PAGE_SIZE

    margen = 10 * mm
    ancho_panel = 78 * mm  # columna derecha: leyenda + cajetín
    marco_x0 = margen
    marco_y0 = margen
    marco_x1 = ancho_pag - margen - ancho_panel - 4 * mm
    marco_y1 = alto_pag - margen - 16 * mm

    # Barra de título
    c.setFillColor(MEECSAC_DARK)
    c.rect(margen, alto_pag - margen - 13 * mm, ancho_pag - 2 * margen, 13 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(margen + 4 * mm, alto_pag - margen - 9 * mm, "PLANO DE SEGURIDAD DE POLVORÍN")
    c.setFillColor(MEECSAC_CYAN)
    c.rect(margen, alto_pag - margen - 14.6 * mm, ancho_pag - 2 * margen, 1.6 * mm, fill=1, stroke=0)

    # Encuadre y escala
    este_min, este_max, norte_min, norte_max = _extension(polvorines, puntos)
    ancho_m = max(este_max - este_min, 1.0)
    alto_m = max(norte_max - norte_min, 1.0)
    ancho_m *= 1 + 2 * MARGEN_FRACCION
    alto_m *= 1 + 2 * MARGEN_FRACCION
    escala = elegir_escala(ancho_m, alto_m, marco_x1 - marco_x0, marco_y1 - marco_y0)

    centro_e = (este_min + este_max) / 2.0
    centro_n = (norte_min + norte_max) / 2.0
    centro_x = (marco_x0 + marco_x1) / 2.0
    centro_y = (marco_y0 + marco_y1) / 2.0
    factor = (1000.0 / escala) * mm  # puntos de papel por metro real

    def a_papel(este: float, norte: float) -> tuple[float, float]:
        return centro_x + (este - centro_e) * factor, centro_y + (norte - centro_n) * factor

    # Marco del mapa (recorta todo lo que se dibuje dentro)
    c.saveState()
    c.setStrokeColor(MEECSAC_DARK)
    c.setLineWidth(1)
    c.rect(marco_x0, marco_y0, marco_x1 - marco_x0, marco_y1 - marco_y0, fill=0, stroke=1)
    path_clip = c.beginPath()
    path_clip.rect(marco_x0, marco_y0, marco_x1 - marco_x0, marco_y1 - marco_y0)
    c.clipPath(path_clip, stroke=0, fill=0)

    # Grilla UTM
    paso = _paso_grilla(escala)
    e_ini = math.floor((centro_e - (centro_x - marco_x0) / factor) / paso) * paso
    e_fin = (centro_e + (marco_x1 - centro_x) / factor)
    n_ini = math.floor((centro_n - (centro_y - marco_y0) / factor) / paso) * paso
    n_fin = (centro_n + (marco_y1 - centro_y) / factor)

    c.setStrokeColor(COLOR_GRILLA)
    c.setLineWidth(0.4)
    etiquetas_e: list[tuple[float, float]] = []
    e = e_ini
    while e <= e_fin:
        x, _ = a_papel(e, centro_n)
        c.line(x, marco_y0, x, marco_y1)
        etiquetas_e.append((x, e))
        e += paso
    etiquetas_n: list[tuple[float, float]] = []
    n = n_ini
    while n <= n_fin:
        _, y = a_papel(centro_e, n)
        c.line(marco_x0, y, marco_x1, y)
        etiquetas_n.append((y, n))
        n += paso

    # Radios de influencia (debajo de todo lo demás)
    for p in polvorines:
        if not p.radio_influencia_m:
            continue
        anillo = [a_papel(e_, n_) for e_, n_ in circulo_utm(p.este_utm, p.norte_utm, p.radio_influencia_m)]
        c.setStrokeColor(COLOR_RADIO)
        c.setLineWidth(1)
        c.setDash(3, 2)
        path = c.beginPath()
        path.moveTo(*anillo[0])
        for punto_papel in anillo[1:]:
            path.lineTo(*punto_papel)
        c.drawPath(path, stroke=1, fill=0)
        c.setDash()

    # Líneas de distancia polvorín → punto de riesgo, rotuladas
    c.setLineWidth(0.6)
    for p in polvorines:
        px, py = a_papel(p.este_utm, p.norte_utm)
        for r in resultados_por_polvorin.get(p.nombre, []):
            punto = next((q for q in puntos if q.nombre == r.punto_nombre), None)
            if punto is None:
                continue
            qx, qy = a_papel(punto.este_utm, punto.norte_utm)
            c.setStrokeColor(COLOR_OK if r.cumple else COLOR_ALERTA)
            c.setDash(2, 2)
            c.line(px, py, qx, qy)
            c.setDash()
            c.setFillColor(COLOR_OK if r.cumple else COLOR_ALERTA)
            c.setFont("Helvetica", 6)
            c.drawCentredString((px + qx) / 2, (py + qy) / 2 + 2, f"{r.distancia_real_m:,.1f} m")

    # Cercos perimétricos
    for p in polvorines:
        if not p.vertices_cerco:
            continue
        pts = [a_papel(e_, n_) for e_, n_ in p.vertices_cerco]
        c.setStrokeColor(COLOR_POLVORIN)
        c.setFillColor(colors.Color(0.9, 0.22, 0.27, alpha=0.12))
        c.setLineWidth(1.2)
        path = c.beginPath()
        path.moveTo(*pts[0])
        for punto_papel in pts[1:]:
            path.lineTo(*punto_papel)
        path.close()
        c.drawPath(path, stroke=1, fill=1)

    # Puntos de riesgo y polvorines
    c.setFont("Helvetica", 6.5)
    for punto in puntos:
        x, y = a_papel(punto.este_utm, punto.norte_utm)
        c.setFillColor(COLOR_PUNTO)
        c.circle(x, y, 2.6, fill=1, stroke=0)
        c.drawString(x + 4, y + 3, punto.nombre[:28])
    for p in polvorines:
        x, y = a_papel(p.este_utm, p.norte_utm)
        c.setFillColor(COLOR_POLVORIN)
        c.setStrokeColor(colors.white)
        c.setLineWidth(0.8)
        c.rect(x - 3, y - 3, 6, 6, fill=1, stroke=1)
        c.setFillColor(MEECSAC_DARK)
        c.setFont("Helvetica-Bold", 7)
        c.drawString(x + 5, y + 3, p.nombre[:28])
        c.setFont("Helvetica", 6.5)
    c.restoreState()

    # Rótulos de la grilla, por fuera del marco
    c.setFillColor(MEECSAC_DARK)
    c.setFont("Helvetica", 6)
    for x, valor in etiquetas_e:
        if marco_x0 <= x <= marco_x1:
            c.drawCentredString(x, marco_y0 - 6, f"{valor:,.0f}".replace(",", " "))
    for y, valor in etiquetas_n:
        if marco_y0 <= y <= marco_y1:
            c.saveState()
            c.translate(marco_x0 - 4, y)
            c.rotate(90)
            c.drawCentredString(0, 0, f"{valor:,.0f}".replace(",", " "))
            c.restoreState()

    # Panel derecho: norte, escala, leyenda y cajetín
    panel_x = marco_x1 + 4 * mm
    _flecha_norte(c, panel_x + 12 * mm, marco_y1 - 16 * mm, 9 * mm)
    _escala_grafica(c, panel_x + 26 * mm, marco_y1 - 16 * mm, escala, ancho_panel - 30 * mm)

    alto_leyenda = _leyenda(
        c, panel_x, marco_y1 - 26 * mm, ancho_panel,
        hay_radio=any(p.radio_influencia_m for p in polvorines),
        hay_cerco=any(p.vertices_cerco for p in polvorines),
    )
    _cajetin(
        c, panel_x, marco_y1 - 26 * mm - alto_leyenda - 4 * mm,
        ancho_panel, datos, escala, zona_utm, hemisferio,
    )

    # Nota al pie: el mismo disclaimer que la app muestra en pantalla
    c.setFillColor(colors.grey)
    c.setFont("Helvetica", 6)
    c.drawString(
        margen, margen - 4 * mm,
        "Las distancias mínimas son las confirmadas por el usuario según el reglamento vigente "
        "(D.S. N.° 024-2016-EM y modificatorias); este plano no reemplaza esa verificación.",
    )

    # EMR total, cuando hay composición registrada
    emrs = [emr_kg_polvorin(p) for p in polvorines]
    con_emr = [e_ for e_ in emrs if e_ is not None]
    if con_emr:
        c.setFillColor(MEECSAC_DARK)
        c.setFont("Helvetica-Bold", 7)
        c.drawRightString(
            ancho_pag - margen, margen - 4 * mm,
            f"EMR total: {sum(con_emr):,.2f} kg equiv. dinamita 60%",
        )

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer
