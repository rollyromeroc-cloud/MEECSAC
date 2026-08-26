from pypdf import PdfReader

from core.models import DatosGenerales, Polvorin, PuntoRiesgo
from core.polvorin import evaluar_distancias
from reports.mapa_pdf import build_mapa_pdf, elegir_escala
from reportlab.lib.units import mm


def _escenario():
    polvorines = [
        Polvorin(
            nombre="Polvorín Explosivos 1", tipo="Explosivos", tipo_instalacion="Superficial",
            este_utm=500249, norte_utm=8387256, radio_influencia_m=120.0,
            vertices_cerco=[(500229, 8387236), (500269, 8387236), (500269, 8387276), (500229, 8387276)],
            items_almacenados=[("Dinamita gelatina 80%", 2500)],
        ),
    ]
    puntos = [
        PuntoRiesgo(
            nombre="Centro poblado", tipo="Edificio habitado",
            este_utm=500700, norte_utm=8387600, distancia_minima_requerida_m=300,
        ),
    ]
    resultados = {p.nombre: evaluar_distancias(p, puntos) for p in polvorines}
    return polvorines, puntos, resultados


def test_elegir_escala_devuelve_escala_normalizada_que_encuadra():
    ancho_pt, alto_pt = 200 * mm, 150 * mm
    escala = elegir_escala(ancho_m=250.0, alto_m=100.0, ancho_pt=ancho_pt, alto_pt=alto_pt)
    # un plano se rotula a escala redonda, no a una arbitraria
    assert escala in (100, 200, 250, 500, 1000, 1250, 2000, 2500, 5000,
                      10000, 20000, 25000, 50000, 100000, 200000)
    # y el contenido debe caber realmente en el marco a esa escala
    assert (250.0 * 1000.0 / escala) * mm <= ancho_pt
    assert (100.0 * 1000.0 / escala) * mm <= alto_pt


def test_elegir_escala_prefiere_la_mas_detallada_que_entra():
    ancho_pt, alto_pt = 200 * mm, 150 * mm
    # 100 m x 100 m no entra a 1:500 (serían 200 mm y el marco mide 150 mm de
    # alto), pero sí a 1:1000 (100 mm) — debe elegir esa, la más detallada
    # que realmente encuadra, no una más chica.
    assert elegir_escala(100.0, 100.0, ancho_pt, alto_pt) == 1000


def test_build_mapa_pdf_genera_pdf_de_una_pagina():
    polvorines, puntos, resultados = _escenario()
    buffer = build_mapa_pdf(polvorines, puntos, resultados, zona_utm=18, hemisferio="S")
    lector = PdfReader(buffer)
    assert len(lector.pages) == 1
    texto = lector.pages[0].extract_text()
    # los elementos cartográficos obligatorios del plano
    assert "PLANO DE SEGURIDAD DE POLVORÍN" in texto
    assert "ESCALA 1:" in texto
    assert "LEYENDA" in texto
    assert "EPSG:32718" in texto
    assert "N" in texto


def test_build_mapa_pdf_incluye_datos_del_cajetin():
    polvorines, puntos, resultados = _escenario()
    datos = DatosGenerales(
        nombre_concesion="Concesión Ejemplo", empresa="MEECSAC",
        numero_plano="PL-SEG-001", revision="A", elaborado_por="R. Romero",
    )
    buffer = build_mapa_pdf(polvorines, puntos, resultados, 18, "S", datos=datos)
    texto = PdfReader(buffer).pages[0].extract_text()
    assert "Concesión Ejemplo" in texto
    assert "PL-SEG-001" in texto
    assert "R. Romero" in texto


def test_build_mapa_pdf_sin_datos_no_inventa_responsables():
    polvorines, puntos, resultados = _escenario()
    texto = PdfReader(build_mapa_pdf(polvorines, puntos, resultados, 18, "S")).pages[0].extract_text()
    # las etiquetas del cajetín están, pero sin valores inventados
    assert "Elaborado" in texto
    assert "Aprobado" in texto


def test_build_mapa_pdf_sin_polvorines_no_falla():
    # el encuadre no debe dividir por cero cuando no hay nada que dibujar
    buffer = build_mapa_pdf([], [], {}, zona_utm=18, hemisferio="S")
    assert len(PdfReader(buffer).pages) == 1


def test_build_mapa_pdf_muestra_emr_solo_si_hay_composicion():
    polvorines, puntos, resultados = _escenario()
    con = PdfReader(build_mapa_pdf(polvorines, puntos, resultados, 18, "S")).pages[0].extract_text()
    assert "EMR total" in con

    sin_comp = [Polvorin(nombre="P1", este_utm=500000, norte_utm=8390000)]
    sin = PdfReader(build_mapa_pdf(sin_comp, [], {}, 18, "S")).pages[0].extract_text()
    assert "EMR total" not in sin
