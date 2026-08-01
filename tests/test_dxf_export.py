import io

import ezdxf
import numpy as np
import pytest

from core.geometry import malla_solida_pique, malla_solida_tunel
from core.georef import matriz_rotacion, matriz_rotacion_vertical, transformar_vertices
from reports.dxf_export import construir_dxf_labor


def _leer_dxf(buffer: io.BytesIO):
    buffer.seek(0)
    texto = buffer.read().decode("utf-8")
    return ezdxf.read(io.StringIO(texto))


def test_dxf_galeria_nivel_sin_tramo_existente():
    malla = malla_solida_tunel(
        ancho=1.77, alto=1.10, longitud_existente=0.0, avance_proyectado=20.0,
        n_anillos_proyectado=5,
    )
    R = matriz_rotacion(rumbo_deg=0.0, pendiente_deg=0.0)  # avance local -> Norte
    origen = (500000.0, 8390000.0, 4200.0)
    vertices_mundo = transformar_vertices(malla["vertices"], origen, R)

    buffer = construir_dxf_labor(
        vertices_mundo, malla["triangulos"], malla["tramo_por_triangulo"],
        origen, "Galería de prueba", "Galería",
    )
    doc = _leer_dxf(buffer)
    msp = doc.modelspace()

    capas = {capa.dxf.name for capa in doc.layers}
    assert {"EXISTENTE", "PROYECTADO", "REFERENCIA"} <= capas

    tipos = [e.dxftype() for e in msp]
    assert tipos.count("POLYLINE") == 1  # solo el tramo proyectado (no hay existente)
    assert "POINT" in tipos and "CIRCLE" in tipos and "MTEXT" in tipos

    polyface = next(e for e in msp if e.dxftype() == "POLYLINE")
    assert polyface.is_poly_face_mesh
    assert polyface.dxf.layer == "PROYECTADO"

    # el sólido debe quedar centrado alrededor del origen, extendiéndose
    # ~20 m hacia el Norte (avance local -> Norte con rumbo=0)
    caras = list(polyface.faces())
    puntos = np.array([v.dxf.location.xyz for cara in caras for v in cara[:3]])
    assert puntos[:, 0].min() == pytest.approx(origen[0] - 1.77 / 2, abs=0.05)
    assert puntos[:, 1].min() == pytest.approx(origen[1], abs=1e-6)
    assert puntos[:, 1].max() == pytest.approx(origen[1] + 20.0, abs=1e-6)


def test_dxf_galeria_con_ambos_tramos_dos_capas():
    malla = malla_solida_tunel(
        ancho=1.77, alto=1.10, longitud_existente=9.0, avance_proyectado=20.0,
        n_anillos_existente=3, n_anillos_proyectado=5,
    )
    R = matriz_rotacion(rumbo_deg=90.0, pendiente_deg=0.0)  # avance local -> Este
    origen = (500000.0, 8390000.0, 4200.0)
    vertices_mundo = transformar_vertices(malla["vertices"], origen, R)

    buffer = construir_dxf_labor(
        vertices_mundo, malla["triangulos"], malla["tramo_por_triangulo"],
        origen, "Galería con avance", "Galería",
    )
    doc = _leer_dxf(buffer)
    msp = doc.modelspace()
    polyfaces = [e for e in msp if e.dxftype() == "POLYLINE"]
    assert len(polyfaces) == 2
    assert {p.dxf.layer for p in polyfaces} == {"EXISTENTE", "PROYECTADO"}


def test_dxf_pique_vertical_hacia_abajo():
    malla = malla_solida_pique(
        diametro=3.0, longitud_existente=0.0, avance_proyectado=30.0, n_anillos_proyectado=5,
    )
    R = matriz_rotacion_vertical("abajo")
    origen = (500000.0, 8390000.0, 4200.0)
    vertices_mundo = transformar_vertices(malla["vertices"], origen, R)

    buffer = construir_dxf_labor(
        vertices_mundo, malla["triangulos"], malla["tramo_por_triangulo"],
        origen, "Pique de prueba", "Pique",
    )
    doc = _leer_dxf(buffer)
    msp = doc.modelspace()
    polyface = next(e for e in msp if e.dxftype() == "POLYLINE")
    caras = list(polyface.faces())
    puntos = np.array([v.dxf.location.xyz for cara in caras for v in cara[:3]])
    # "abajo" -> la cota debe bajar 30 m desde el origen, nunca subir
    assert puntos[:, 2].max() == pytest.approx(origen[2], abs=1e-6)
    assert puntos[:, 2].min() == pytest.approx(origen[2] - 30.0, abs=1e-6)


def test_dxf_marcador_referencia_en_el_origen():
    malla = malla_solida_pique(diametro=2.0, longitud_existente=0.0, avance_proyectado=10.0, n_anillos_proyectado=4)
    R = matriz_rotacion_vertical("arriba")
    origen = (123456.78, 8765432.1, 3800.5)
    vertices_mundo = transformar_vertices(malla["vertices"], origen, R)
    buffer = construir_dxf_labor(
        vertices_mundo, malla["triangulos"], malla["tramo_por_triangulo"],
        origen, "Chimenea de prueba", "Chimenea",
    )
    doc = _leer_dxf(buffer)
    msp = doc.modelspace()
    punto = next(e for e in msp if e.dxftype() == "POINT")
    assert punto.dxf.location.xyz == pytest.approx(origen, abs=1e-6)
