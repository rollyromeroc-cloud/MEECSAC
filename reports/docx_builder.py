"""Generación de reportes Word (.docx) a partir de los resultados calculados.

Usa python-docx puro (sin LibreOffice), para que funcione igual en local y en
Streamlit Community Cloud. Replica la estructura del informe técnico de
referencia: una sección por labor + cuadros resumen consolidados al final.
"""

from __future__ import annotations

import datetime as _dt
from io import BytesIO

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

from core.memoria import memoria_calculo
from core.models import LaborMinera, Polvorin, PuntoRiesgo, ResultadoDistancia, ResultadoVoladura
from core.polvorin import area_shoelace, perimetro
from viz.tunnel_plot import build_tunnel_figure


def _fmt(value, decimals=2) -> str:
    if isinstance(value, float):
        return f"{value:,.{decimals}f}"
    return str(value)


def _add_table(document: Document, headers: list[str], rows: list[list]) -> None:
    table = document.add_table(rows=1, cols=len(headers))
    table.style = "Light Grid Accent 1"
    hdr_cells = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr_cells[i].text = h
        for p in hdr_cells[i].paragraphs:
            for run in p.runs:
                run.bold = True
    for row in rows:
        cells = table.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = _fmt(val) if not isinstance(val, str) else val


def _add_title_page(document: Document, titulo: str, subtitulo: str = "") -> None:
    h = document.add_heading(titulo, level=0)
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if subtitulo:
        p = document.add_paragraph(subtitulo)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fecha = document.add_paragraph(f"Generado el {_dt.date.today().isoformat()}")
    fecha.alignment = WD_ALIGN_PARAGRAPH.CENTER
    document.add_paragraph("")


def _add_labor_section(
    document: Document, labor: LaborMinera, resultado: ResultadoVoladura
) -> None:
    document.add_heading(f"{labor.tipo}: {labor.nombre}", level=1)
    document.add_paragraph(f"Etapa: {labor.etapa}")
    if labor.observaciones:
        document.add_paragraph(labor.observaciones)

    try:
        png_bytes = build_tunnel_figure(labor, resultado).to_image(
            format="png", width=900, height=550, scale=2
        )
        document.add_picture(BytesIO(png_bytes), width=Inches(6))
    except Exception:
        document.add_paragraph("(Esquema 3D no disponible en este entorno)")

    document.add_heading("Diseño del trazo", level=2)
    _add_table(
        document,
        ["Concepto", "Valor"],
        [
            ["Sección", f"{labor.ancho_m} × {labor.alto_m} m"],
            ["Área", f"{_fmt(resultado.area_m2, 3)} m²"],
            ["Longitud existente", f"{_fmt(labor.longitud_existente_m)} m"],
            ["Avance proyectado", f"{_fmt(labor.avance_proyectado_m)} m"],
            ["Longitud final", f"{_fmt(resultado.longitud_final_m)} m"],
            ["Longitud de barreno", f"{labor.longitud_barreno_pies} pies"],
            ["Diámetro de barreno", f"{labor.diametro_barreno_mm} mm"],
            ["Equipo de perforación", labor.equipo_perforacion],
            ["Tipo de corte", labor.tipo_corte],
            ["Taladros cargados por disparo", labor.taladros_cargados],
            ["Taladros de alivio", labor.taladros_alivio],
        ],
    )

    document.add_heading("Aspectos técnicos", level=2)
    _add_table(
        document,
        ["Concepto", "Valor"],
        [
            ["Tipo de roca", labor.tipo_roca],
            ["Destino del material", labor.destino_material],
            [
                "Peso específico usado",
                f"{_fmt(resultado.densidad_usada_tm_m3)} TM/m³",
            ],
            ["Método de avance", "Perforación y voladura convencional"],
        ],
    )

    document.add_heading("Cálculo de avance, volumen y tonelaje", level=2)
    _add_table(
        document,
        ["Concepto", "Valor"],
        [
            ["Número de disparos", resultado.n_disparos],
            ["Volumen por disparo", f"{_fmt(resultado.volumen_por_disparo_m3)} m³"],
            ["Volumen total", f"{_fmt(resultado.volumen_total_m3)} m³"],
            ["Tonelaje por disparo", f"{_fmt(resultado.tonelaje_por_disparo_tm)} TM"],
            ["Tonelaje total", f"{_fmt(resultado.tonelaje_total_tm)} TM"],
        ],
    )

    document.add_heading("Explosivos para la voladura", level=2)
    _add_table(
        document,
        ["Concepto", "Valor"],
        [
            ["Cartuchos por taladro", labor.cartuchos_por_taladro],
            ["Cartuchos por disparo", resultado.cartuchos_por_disparo],
            ["Explosivo por disparo", f"{_fmt(resultado.explosivo_por_disparo_kg)} kg"],
            ["Explosivo total", f"{_fmt(resultado.explosivo_total_kg)} kg"],
            [
                f"{labor.tipo_explosivo_1} ({labor.pct_explosivo_1:.0f}%)",
                f"{_fmt(resultado.explosivo_tipo1_kg)} kg",
            ],
            [
                f"{labor.tipo_explosivo_2} ({labor.pct_explosivo_2:.0f}%)",
                f"{_fmt(resultado.explosivo_tipo2_kg)} kg",
            ],
            ["Factor de potencia", f"{_fmt(resultado.factor_potencia_kg_tm)} kg/TM"],
            [
                "Consumo específico por volumen",
                f"{_fmt(resultado.consumo_especifico_kg_m3)} kg/m³",
            ],
        ],
    )

    document.add_heading("Accesorios para la voladura", level=2)
    _add_table(
        document,
        ["Concepto", "Valor"],
        [
            [labor.tipo_fulminante, f"{resultado.fulminantes_total} unidades"],
            ["Mecha de seguridad por taladro", f"{_fmt(resultado.mecha_por_taladro_m, 3)} m"],
            ["Mecha de seguridad por disparo", f"{_fmt(resultado.mecha_por_disparo_m)} m"],
            ["Mecha de seguridad total", f"{_fmt(resultado.mecha_total_m)} m"],
        ],
    )

    document.add_heading("Memoria de cálculo", level=2)
    document.add_paragraph(
        "Desglose paso a paso (fórmula → sustitución → resultado) de cada "
        "cifra reportada arriba."
    )
    pasos = memoria_calculo(labor, resultado)
    _add_table(
        document,
        ["Concepto", "Fórmula", "Sustitución", "Resultado"],
        [[p.concepto, p.formula, p.sustitucion, p.resultado] for p in pasos],
    )
    document.add_paragraph("")


def build_voladura_report(
    labores: list[LaborMinera],
    resultados: list[ResultadoVoladura],
    titulo_proyecto: str = "Programa de perforación y voladura",
) -> BytesIO:
    document = Document()
    _add_title_page(document, titulo_proyecto, "Reporte generado automáticamente")

    for labor, resultado in zip(labores, resultados):
        _add_labor_section(document, labor, resultado)

    document.add_heading("Cuadro resumen del programa", level=1)
    _add_table(
        document,
        [
            "Labor",
            "Sección",
            "Avance (m)",
            "N.° disparos",
            "Explosivo total (kg)",
            "Tonelaje total (TM)",
            "Factor de potencia (kg/TM)",
        ],
        [
            [
                labor.nombre,
                f"{labor.ancho_m} × {labor.alto_m}",
                _fmt(labor.avance_proyectado_m),
                resultado.n_disparos,
                _fmt(resultado.explosivo_total_kg),
                _fmt(resultado.tonelaje_total_tm),
                _fmt(resultado.factor_potencia_kg_tm),
            ]
            for labor, resultado in zip(labores, resultados)
        ],
    )

    total_avance = sum(l.avance_proyectado_m for l in labores)
    total_disparos = sum(r.n_disparos for r in resultados)
    total_explosivo = sum(r.explosivo_total_kg for r in resultados)
    total_tipo1 = sum(r.explosivo_tipo1_kg for r in resultados)
    total_tipo2 = sum(r.explosivo_tipo2_kg for r in resultados)
    total_tonelaje = sum(r.tonelaje_total_tm for r in resultados)
    total_fulminantes = sum(r.fulminantes_total for r in resultados)
    total_mecha = sum(r.mecha_total_m for r in resultados)

    document.add_heading("Totales generales", level=1)
    _add_table(
        document,
        ["Concepto", "Valor"],
        [
            ["Avance total programado", f"{_fmt(total_avance)} m"],
            ["Disparos totales", total_disparos],
            ["Tonelaje total programado", f"{_fmt(total_tonelaje)} TM"],
            ["Explosivo total", f"{_fmt(total_explosivo)} kg"],
            ["Dinamita/explosivo tipo 1 total", f"{_fmt(total_tipo1)} kg"],
            ["Emulsión/explosivo tipo 2 total", f"{_fmt(total_tipo2)} kg"],
            ["Fulminantes totales", f"{total_fulminantes} unidades"],
            ["Mecha de seguridad total", f"{_fmt(total_mecha)} m"],
        ],
    )

    buffer = BytesIO()
    document.save(buffer)
    buffer.seek(0)
    return buffer


def build_polvorin_report(
    polvorines: list[Polvorin],
    resultados_por_polvorin: dict[str, list[ResultadoDistancia]],
    titulo_proyecto: str = "Verificación de seguridad de polvorín",
) -> BytesIO:
    document = Document()
    _add_title_page(document, titulo_proyecto, "Reporte generado automáticamente")
    document.add_paragraph(
        "Nota: las distancias mínimas requeridas mostradas en este reporte son "
        "las capturadas manualmente en la aplicación. Deben verificarse contra "
        "el reglamento vigente (D.S. N.° 024-2016-EM y modificatorias) antes de "
        "tomar decisiones operativas."
    )

    for polvorin in polvorines:
        document.add_heading(f"Polvorín de {polvorin.tipo}: {polvorin.nombre}", level=1)
        _add_table(
            document,
            ["Concepto", "Valor"],
            [
                ["Coordenadas (Este, Norte UTM)", f"{polvorin.este_utm}, {polvorin.norte_utm}"],
                [
                    "Área del cerco perimétrico",
                    f"{_fmt(area_shoelace(polvorin.vertices_cerco))} m²"
                    if polvorin.vertices_cerco
                    else "No consignada",
                ],
                [
                    "Perímetro del cerco",
                    f"{_fmt(perimetro(polvorin.vertices_cerco))} m"
                    if polvorin.vertices_cerco
                    else "No consignado",
                ],
                [
                    "Cantidad almacenada",
                    f"{_fmt(polvorin.cantidad_almacenada_kg)} kg"
                    if polvorin.cantidad_almacenada_kg
                    else "No consignada",
                ],
                [
                    "Radio de influencia",
                    f"{_fmt(polvorin.radio_influencia_m)} m"
                    if polvorin.radio_influencia_m
                    else "No consignado",
                ],
            ],
        )

        resultados = resultados_por_polvorin.get(polvorin.nombre, [])
        if resultados:
            document.add_heading("Distancias a puntos de riesgo", level=2)
            _add_table(
                document,
                [
                    "Punto de riesgo",
                    "Tipo",
                    "Distancia real (m)",
                    "Distancia mínima requerida (m)",
                    "¿Cumple?",
                ],
                [
                    [
                        r.punto_nombre,
                        r.punto_tipo,
                        _fmt(r.distancia_real_m),
                        _fmt(r.distancia_minima_m),
                        "Sí" if r.cumple else "No",
                    ]
                    for r in resultados
                ],
            )
        document.add_paragraph("")

    buffer = BytesIO()
    document.save(buffer)
    buffer.seek(0)
    return buffer
