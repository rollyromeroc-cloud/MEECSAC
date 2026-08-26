import sys

import pytest
from pypdf import PdfReader
from reportlab.graphics.shapes import Circle, PolyLine, String
from reportlab.lib.units import mm

from core.malla_perforacion import generar_malla_perforacion
from core.models import DatosGenerales, LaborMinera
from core.voladura import calcular_resultado
from reports.malla_drawing import build_malla_drawing
from reports.malla_pdf import build_malla_pdf


def _labor() -> LaborMinera:
    return LaborMinera(
        nombre="Galería Nv 1", tipo="Galería", etapa="Desarrollo",
        ancho_m=2.5, alto_m=2.5, forma_seccion="Baúl (hastiales rectos)",
        longitud_existente_m=10.0, avance_proyectado_m=60.0, avance_por_disparo_m=1.5,
        diametro_barreno_mm=38.0, longitud_barreno_pies=6.0,
        taladros_cargados=33, taladros_alivio=3, destino_material="Desmonte",
    )


def _malla(labor: LaborMinera):
    return generar_malla_perforacion(
        labor.ancho_m, labor.alto_m, labor.taladros_cargados, labor.taladros_alivio,
        diametro_barreno_mm=labor.diametro_barreno_mm,
        forma_seccion=labor.forma_seccion,
    )


def test_malla_pdf_no_depende_de_plotly_ni_kaleido():
    # Guardia de regresión: la ficha se dibuja en vector con reportlab.
    # Volver a exportar la figura de Plotly a PNG reintroduciría kaleido, que
    # ya tumbó la app en producción y en Python 3.14 se cuelga en to_image()
    # (un cuelgue no lo atrapa un try/except).
    import reports.malla_drawing  # noqa: F401  — se importa para inspeccionarlo
    import reports.malla_pdf

    for modulo in (reports.malla_pdf, reports.malla_drawing):
        fuentes = [
            nombre for nombre, valor in vars(modulo).items()
            if getattr(valor, "__module__", "").startswith("plotly")
            or getattr(valor, "__name__", "").startswith("plotly")
        ]
        assert not fuentes, f"{modulo.__name__} volvió a depender de plotly: {fuentes}"
    assert "kaleido" not in sys.modules


def test_build_malla_pdf_genera_una_pagina_con_las_tablas():
    labor = _labor()
    buffer = build_malla_pdf(labor, calcular_resultado(labor))
    lector = PdfReader(buffer)
    assert len(lector.pages) == 1
    texto = lector.pages[0].extract_text()
    assert "FICHA DE MALLA DE PERFORACIÓN" in texto
    assert "DISTANCIAS POR ZONA" in texto
    assert "EXPLOSIVO POR ZONA" in texto
    assert "CAJETÍN" in texto
    # la leyenda del dibujo vectorial también sale como texto seleccionable
    assert "LEYENDA" in texto
    assert "BURDEN POR ZONA" in texto


def test_build_malla_pdf_incluye_datos_del_cajetin():
    labor = _labor()
    datos = DatosGenerales(nombre_concesion="Concesión Ejemplo", numero_plano="ML-001")
    texto = PdfReader(build_malla_pdf(labor, calcular_resultado(labor), datos)).pages[0].extract_text()
    assert "Concesión Ejemplo" in texto
    assert "ML-001" in texto


def test_dibujo_tiene_un_circulo_por_taladro_mas_los_de_la_leyenda():
    labor = _labor()
    taladros, zonas = _malla(labor)
    dibujo = build_malla_drawing(
        taladros, zonas, labor.ancho_m, labor.alto_m, labor.forma_seccion,
        ancho_pt=150 * mm, alto_pt=130 * mm,
    )
    circulos = [c for c in dibujo.contents if isinstance(c, Circle)]
    categorias_presentes = {t.categoria for t in taladros}
    # un círculo por taladro perforado + uno por entrada de leyenda
    assert len(circulos) == len(taladros) + len(categorias_presentes)


def test_dibujo_traza_el_contorno_y_los_anillos_del_corte():
    labor = _labor()
    taladros, zonas = _malla(labor)
    dibujo = build_malla_drawing(
        taladros, zonas, labor.ancho_m, labor.alto_m, labor.forma_seccion,
        ancho_pt=150 * mm, alto_pt=130 * mm,
    )
    polilineas = [c for c in dibujo.contents if isinstance(c, PolyLine)]
    # contorno de la sección + un trazo por cada anillo del corte con >=3 taladros
    anillos_trazables = sum(
        1 for zona in ("arranque", "ayuda", "subayuda")
        if sum(1 for t in taladros if t.categoria == zona) >= 3
    )
    assert len(polilineas) == 1 + anillos_trazables

    textos = " ".join(c.text for c in dibujo.contents if isinstance(c, String))
    assert "Arranque" in textos


def test_dibujo_mantiene_la_escala_uniforme_en_los_dos_ejes():
    # deformar la malla para llenar el marco falsearía las distancias que la
    # ficha justamente documenta: el factor real→papel debe ser el mismo en
    # los dos ejes, incluso con un marco muy alargado.
    labor = _labor()
    taladros, zonas = _malla(labor)
    dibujo = build_malla_drawing(
        taladros, zonas, labor.ancho_m, labor.alto_m, labor.forma_seccion,
        ancho_pt=600.0, alto_pt=260.0,
    )
    # los círculos se agregan por categoría, en el orden de ORDEN_CATEGORIAS,
    # y los de la leyenda van al final
    from viz.malla_plot import ORDEN_CATEGORIAS

    ordenados = [t for cat in ORDEN_CATEGORIAS for t in taladros if t.categoria == cat]
    circulos = [c for c in dibujo.contents if isinstance(c, Circle)][: len(ordenados)]
    assert len(circulos) == len(ordenados)

    posiciones = {(t.y, t.z): (c.cx, c.cy) for t, c in zip(ordenados, circulos)}
    claves = list(posiciones)
    base = claves[0]

    factores = []
    for otra in claves[1:]:
        dy, dz = otra[0] - base[0], otra[1] - base[1]
        dpx = posiciones[otra][0] - posiciones[base][0]
        dpy = posiciones[otra][1] - posiciones[base][1]
        if abs(dy) > 0.05:
            factores.append(dpx / dy)
        if abs(dz) > 0.05:
            factores.append(dpy / dz)

    assert factores
    assert max(factores) == pytest.approx(min(factores), rel=1e-6)
