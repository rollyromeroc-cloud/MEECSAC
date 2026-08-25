"""Ficha técnica en PDF (A3 apaisado) de la malla de perforación de una
labor — imagen de la malla + tablas de distancias, parámetros, explosivos
y resultados, más un cajetín, con los colores de marca de MEECSAC. Layout
inspirado en el formato de una lámina de diseño de malla tipo
JKSimBlast/DIMAP, pero con datos y estilo propios (ver disclaimer en
`core.malla_perforacion`: no es un diseño certificado de campo).
"""

from __future__ import annotations

import datetime as _dt
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle

from core.constants import LABORES_VERTICALES
from core.malla_perforacion import ZonaInfo
from core.models import DatosGenerales, LaborMinera, ResultadoVoladura
from viz.malla_plot import build_malla_perforacion_figure

import plotly.graph_objects as go

LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "logo_meecsac.jpg"
PAGE_SIZE = landscape(A3)

# Colores de marca MEECSAC (muestreados del logo: acento cian de la "M" y
# el fondo oscuro de la tarjeta) — usados para las barras de título y los
# encabezados de tabla, no para las categorías de taladro (esas mantienen
# su paleta funcional/segura para daltonismo, ver viz.malla_plot).
MEECSAC_DARK = colors.HexColor("#33454E")
MEECSAC_CYAN = colors.HexColor("#00A7E3")
MEECSAC_GRIS_CLARO = colors.HexColor("#F2F5F6")

_ESTILO_TITULO = ParagraphStyle(
    "TituloMeecsac", fontName="Helvetica-Bold", fontSize=16, textColor=colors.white, leading=19,
)
_ESTILO_SUBTITULO = ParagraphStyle(
    "SubtituloMeecsac", fontName="Helvetica", fontSize=9, textColor=colors.white, leading=11,
)
_ESTILO_SECCION = ParagraphStyle(
    "SeccionMeecsac", fontName="Helvetica-Bold", fontSize=10, textColor=MEECSAC_DARK, leading=12,
    spaceBefore=4, spaceAfter=3,
)
_ESTILO_NOTA = ParagraphStyle("NotaMeecsac", fontName="Helvetica", fontSize=6.5, textColor=colors.grey, leading=8)


def _tabla(datos_filas: list[list], anchos: list[float] | None = None, resaltar_total: bool = False) -> Table:
    """Tabla estándar: encabezado oscuro MEECSAC, filas alternadas."""
    t = Table(datos_filas, colWidths=anchos)
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), MEECSAC_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B8C2C6")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, MEECSAC_GRIS_CLARO]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if resaltar_total:
        estilo.append(("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"))
        estilo.append(("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#D8ECF5")))
    t.setStyle(TableStyle(estilo))
    return t


def _explosivo_por_zona(labor: LaborMinera, zonas: list[ZonaInfo]) -> list[list]:
    """Distribución de explosivo por zona: cada taladro de una zona lleva
    los mismos cartuchos_por_taladro/peso_cartucho_kg que el resto de la
    labor (la app no modela variación de carga por zona todavía)."""
    kg_por_taladro = labor.cartuchos_por_taladro * labor.peso_cartucho_kg
    filas = [["Zona", "N.° taladros", "Cartuchos", "kg"]]
    total_taladros = total_cartuchos = total_kg = 0
    for z in zonas:
        cartuchos = z.n_taladros * labor.cartuchos_por_taladro
        kg = z.n_taladros * kg_por_taladro
        filas.append([z.zona, str(z.n_taladros), str(cartuchos), f"{kg:.2f}"])
        total_taladros += z.n_taladros
        total_cartuchos += cartuchos
        total_kg += kg
    filas.append(["TOTAL", str(total_taladros), str(total_cartuchos), f"{total_kg:.2f}"])
    return filas


def _marco_y_pie(canvas, doc) -> None:
    """Marco de lámina técnica + pie de página (N.° de página, MEECSAC) —
    dibujado en cada página vía el callback onPage de SimpleDocTemplate."""
    ancho_pag, alto_pag = PAGE_SIZE
    canvas.saveState()
    canvas.setStrokeColor(MEECSAC_DARK)
    canvas.setLineWidth(1.2)
    canvas.rect(5 * mm, 5 * mm, ancho_pag - 10 * mm, alto_pag - 10 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.grey)
    canvas.drawString(8 * mm, 6.5 * mm, "MEECSAC — Más que Explosivos")
    canvas.drawRightString(ancho_pag - 8 * mm, 6.5 * mm, f"Página {doc.page} — generado {_dt.date.today().isoformat()}")
    canvas.restoreState()


def build_malla_pdf(
    labor: LaborMinera,
    resultado: ResultadoVoladura,
    datos: DatosGenerales | None = None,
    fig: go.Figure | None = None,
    zonas: list[ZonaInfo] | None = None,
) -> BytesIO:
    """Genera la ficha PDF A3 apaisada de la malla de perforación de
    `labor`. Devuelve un BytesIO listo para `st.download_button`.

    `fig`/`zonas`, si el llamador ya los calculó (p. ej. para mostrar la
    malla en pantalla), se reutilizan tal cual en vez de recalcularlos —
    evita repetir la generación de la malla dos veces por cada render."""
    datos = datos or DatosGenerales()
    es_vertical = labor.tipo in LABORES_VERTICALES
    forma = "Circular" if es_vertical else labor.forma_seccion
    alto_malla = labor.ancho_m if es_vertical else labor.alto_m

    if fig is None or zonas is None:
        fig, zonas = build_malla_perforacion_figure(
            labor.ancho_m, alto_malla, labor.taladros_cargados, labor.taladros_alivio,
            diametro_barreno_mm=labor.diametro_barreno_mm, diametro_alivio_mm=labor.diametro_alivio_mm,
            forma_seccion=forma, nombre_labor=labor.nombre,
        )
    try:
        png_bytes = fig.to_image(format="png", width=1100, height=950, scale=2)
        imagen_malla: Image | Paragraph = Image(BytesIO(png_bytes), width=150 * mm, height=130 * mm)
    except Exception:
        # el entorno de despliegue puede no tener lo necesario para exportar
        # gráficos Plotly a PNG (p. ej. Chrome, requerido por kaleido>=1) —
        # se degrada a una nota en vez de romper toda la ficha (mismo
        # criterio que reports.docx_builder para el esquema 3D del Word).
        imagen_malla = Paragraph(
            "(Imagen de la malla no disponible en este entorno — sigue disponible la "
            "tabla de distancias por zona más abajo)",
            _ESTILO_NOTA,
        )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=PAGE_SIZE,
        leftMargin=12 * mm, rightMargin=12 * mm, topMargin=11 * mm, bottomMargin=11 * mm,
    )

    # --- barra de título (MEECSAC), con logo si está disponible ---
    titulo_txt = f"FICHA DE MALLA DE PERFORACIÓN Y VOLADURA — {labor.nombre.upper()}"
    subtitulo_txt = (
        f"Sección {labor.ancho_m:.2f} × {alto_malla:.2f} m — {forma} · "
        f"Roca: {labor.tipo_roca} · Avance: {labor.avance_proyectado_m:.2f} m"
    )
    textos_titulo = [Paragraph(titulo_txt, _ESTILO_TITULO), Paragraph(subtitulo_txt, _ESTILO_SUBTITULO)]
    if LOGO_PATH.exists():
        logo = Image(str(LOGO_PATH), width=16 * mm, height=16 * mm)
        barra_titulo = Table([[logo, textos_titulo]], colWidths=[20 * mm, 253 * mm])
        barra_titulo.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), MEECSAC_DARK),
            ("LINEBELOW", (0, 0), (-1, 0), 2, MEECSAC_CYAN),
            ("LEFTPADDING", (0, 0), (0, 0), 4), ("LEFTPADDING", (1, 0), (1, 0), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
    else:
        barra_titulo = Table([textos_titulo], colWidths=[273 * mm])
        barra_titulo.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), MEECSAC_DARK),
            ("LINEBELOW", (0, 0), (-1, 0), 2, MEECSAC_CYAN),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))

    # --- panel derecho: distancias por zona (la leyenda de categorías ya
    # va incluida en la propia imagen de la malla, ver viz.malla_plot) ---
    tabla_zonas = _tabla(
        [["Zona", "Forma", "N.° tal.", "Burden (mm)", "Lado (mm)"]] + [
            [z.zona, z.forma or "—", str(z.n_taladros), f"{z.burden_mm:.0f}", f"{z.lado_mm:.0f}" if z.lado_mm else "—"]
            for z in zonas
        ],
        anchos=[26 * mm, 22 * mm, 18 * mm, 24 * mm, 22 * mm],
    )
    panel_derecho = [
        Paragraph("DISTANCIAS POR ZONA", _ESTILO_SECCION), tabla_zonas, Spacer(1, 6 * mm),
    ]

    fila_imagen_zonas = Table(
        [[imagen_malla, panel_derecho]], colWidths=[155 * mm, 122 * mm],
    )
    fila_imagen_zonas.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))

    # --- fila inferior: parámetros | explosivos por zona | resultados+cajetín ---
    tabla_parametros = _tabla(
        [
            ["Parámetro de perforación", "Valor"],
            ["Diámetro de barreno (mm)", f"{labor.diametro_barreno_mm:.0f}"],
            ["Diámetro de alivio (mm)", f"{(labor.diametro_alivio_mm or labor.diametro_barreno_mm):.0f}"],
            ["Longitud de barreno (pies)", f"{labor.longitud_barreno_pies:.1f}"],
            ["Taladros cargados", str(labor.taladros_cargados)],
            ["Taladros de alivio", str(labor.taladros_alivio)],
            ["Taladros perforados", str(labor.taladros_cargados + labor.taladros_alivio)],
        ],
        anchos=[42 * mm, 20 * mm],
    )
    tabla_explosivos = _tabla(_explosivo_por_zona(labor, zonas), anchos=[26 * mm, 20 * mm, 18 * mm, 18 * mm], resaltar_total=True)
    tabla_resultados = _tabla(
        [
            ["Resultado", "Unidad", "Valor"],
            ["Área de sección", "m²", f"{resultado.area_m2:.2f}"],
            ["Volumen total", "m³", f"{resultado.volumen_total_m3:.2f}"],
            ["Tonelaje total", "TM", f"{resultado.tonelaje_total_tm:.2f}"],
            ["Explosivo total", "kg", f"{resultado.explosivo_total_kg:.2f}"],
            ["Factor de potencia", "kg/TM", f"{resultado.factor_potencia_kg_tm:.3f}"],
            ["Consumo específico", "kg/m³", f"{resultado.consumo_especifico_kg_m3:.3f}"],
        ],
        anchos=[34 * mm, 18 * mm, 20 * mm],
    )

    cajetin_filas = [
        ["Proyecto", datos.nombre_concesion or "—"],
        ["Cliente", datos.cliente or "—"],
        ["Sección", f"{labor.ancho_m:.2f} × {alto_malla:.2f} m — {labor.tipo_roca}"],
        ["Elaborado por", datos.elaborado_por or "—"],
        ["Cargo / área", datos.cargo_elaborado_por or "—"],
        ["Revisado por", datos.revisado_por or "—"],
        ["Aprobado por", datos.aprobado_por or "—"],
        ["Fecha", _dt.date.today().isoformat()],
        ["N.° de plano", datos.numero_plano or "—"],
        ["Revisión", datos.revision or "0"],
    ]
    tabla_cajetin = _tabla([["Cajetín", ""]] + cajetin_filas, anchos=[30 * mm, 45 * mm])

    fila_inferior = Table(
        [[
            [Paragraph("PARÁMETROS DE PERFORACIÓN", _ESTILO_SECCION), tabla_parametros],
            [Paragraph("EXPLOSIVO POR ZONA", _ESTILO_SECCION), tabla_explosivos],
            [Paragraph("RESULTADOS", _ESTILO_SECCION), tabla_resultados],
            [Paragraph("CAJETÍN", _ESTILO_SECCION), tabla_cajetin],
        ]],
        colWidths=[68 * mm, 88 * mm, 78 * mm, 78 * mm],
    )
    fila_inferior.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))

    nota = Paragraph(
        "Malla paramétrica de referencia (ver core.malla_perforacion) — no es un diseño certificado de campo, "
        "requiere validación por un ingeniero responsable antes de su ejecución. Burden de arranque: regla de "
        "Holmberg (1982); escalado por zona: factores de seguridad de Ojeda Mestas, R.W. (IV CONEINGEMMET, "
        "Huancayo, 2003). Generado con la app de perforación y voladura de MEECSAC.",
        _ESTILO_NOTA,
    )

    doc.build(
        [
            barra_titulo, Spacer(1, 4 * mm),
            fila_imagen_zonas, Spacer(1, 4 * mm),
            fila_inferior, Spacer(1, 3 * mm),
            nota,
        ],
        onFirstPage=_marco_y_pie, onLaterPages=_marco_y_pie,
    )
    buffer.seek(0)
    return buffer
