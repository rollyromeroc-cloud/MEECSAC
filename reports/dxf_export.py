"""Exportación del sólido de una labor minera a DXF (AutoCAD), ya
georreferenciado en coordenadas de mundo (Este, Norte, Cota) — ver
`core.georef` para la transformación de la malla local a mundo.

Usa entidades POLYFACE MESH (vía `ezdxf.render.MeshBuilder`), el formato
con mayor compatibilidad AutoCAD (soportado desde R12) para una superficie
triangulada cerrada. Una entidad por tramo (existente/proyectado), cada
una en su propia capa, más un marcador de referencia en el punto de
inicio para verificar visualmente la posición al abrir el archivo.
"""

from __future__ import annotations

import io

import ezdxf
import numpy as np
from ezdxf.render import MeshBuilder

COLOR_EXISTENTE_RGB = (0x99, 0x99, 0x99)
COLOR_PROYECTADO_RGB = (0x88, 0xCC, 0xEE)
COLOR_REFERENCIA_RGB = (0xCC, 0x67, 0x77)

_ACI_EXISTENTE = 9  # gris claro — aproximación de respaldo para lectores muy antiguos
_ACI_PROYECTADO = 140  # azul claro
_ACI_REFERENCIA = 1  # rojo

_RADIO_MARCADOR_M = 0.5


def _submalla_por_tramo(
    vertices: np.ndarray, triangulos: np.ndarray, tramo_por_triangulo: list[str], tramo: str,
) -> tuple[np.ndarray, np.ndarray]:
    """Extrae los vértices y caras de un tramo, re-indexados desde 0 — cada
    entidad DXF debe ser autocontenida (`MeshBuilder` no tolera bien
    vértices sin referenciar en una sub-malla compartida)."""
    mascara = np.array([t == tramo for t in tramo_por_triangulo])
    caras = triangulos[mascara]
    if len(caras) == 0:
        return np.empty((0, 3)), np.empty((0, 3), dtype=int)
    usados = np.unique(caras)
    remapeo = {viejo: nuevo for nuevo, viejo in enumerate(usados)}
    sub_vertices = vertices[usados]
    sub_caras = np.array([[remapeo[i] for i in cara] for cara in caras])
    return sub_vertices, sub_caras


def _agregar_marcador_origen(
    msp, origen_utm_cota: tuple[float, float, float], nombre: str, tipo: str, zona_hemisferio: str | None,
) -> None:
    este0, norte0, cota0 = origen_utm_cota
    radio = _RADIO_MARCADOR_M
    attrs = {"layer": "REFERENCIA"}
    msp.add_point(origen_utm_cota, dxfattribs=attrs)
    msp.add_circle(center=origen_utm_cota, radius=radio, dxfattribs=attrs)
    msp.add_line((este0 - radio, norte0, cota0), (este0 + radio, norte0, cota0), dxfattribs=attrs)
    msp.add_line((este0, norte0 - radio, cota0), (este0, norte0 + radio, cota0), dxfattribs=attrs)
    texto = f"{nombre} ({tipo})\nE={este0:.2f} N={norte0:.2f} Cota={cota0:.2f}"
    if zona_hemisferio:
        texto += f" — UTM {zona_hemisferio}"
    mtexto = msp.add_mtext(texto, dxfattribs={**attrs, "char_height": radio * 0.8})
    mtexto.set_location((este0 + radio * 1.5, norte0, cota0))


def construir_dxf_labor(
    vertices_mundo: np.ndarray,
    triangulos: np.ndarray,
    tramo_por_triangulo: list[str],
    origen_utm_cota: tuple[float, float, float],
    nombre_labor: str,
    tipo_labor: str,
    zona_hemisferio: str | None = None,
    dxfversion: str = "R2013",
) -> io.BytesIO:
    """Construye un DXF con una entidad POLYFACE MESH por tramo
    (existente/proyectado, cada una en su capa) más un marcador de
    referencia en el punto de inicio, listo para `st.download_button`.

    Recibe vértices YA transformados a coordenadas de mundo (ver
    `core.georef.transformar_vertices`) — este módulo no conoce ni
    necesita la geometría local ni la orientación."""
    doc = ezdxf.new(dxfversion=dxfversion)
    msp = doc.modelspace()

    capa_existente = doc.layers.add(name="EXISTENTE", color=_ACI_EXISTENTE)
    capa_existente.rgb = COLOR_EXISTENTE_RGB
    capa_proyectado = doc.layers.add(name="PROYECTADO", color=_ACI_PROYECTADO)
    capa_proyectado.rgb = COLOR_PROYECTADO_RGB
    capa_referencia = doc.layers.add(name="REFERENCIA", color=_ACI_REFERENCIA)
    capa_referencia.rgb = COLOR_REFERENCIA_RGB

    for tramo, nombre_capa in (("existente", "EXISTENTE"), ("proyectado", "PROYECTADO")):
        sub_vertices, sub_caras = _submalla_por_tramo(vertices_mundo, triangulos, tramo_por_triangulo, tramo)
        if len(sub_caras) == 0:
            continue
        mesh = MeshBuilder()
        mesh.add_mesh(
            vertices=[tuple(float(c) for c in v) for v in sub_vertices],
            faces=[tuple(int(i) for i in cara) for cara in sub_caras],
        )
        mesh.render_polyface(msp, dxfattribs={"layer": nombre_capa})

    _agregar_marcador_origen(msp, origen_utm_cota, nombre_labor, tipo_labor, zona_hemisferio)

    buffer_texto = io.StringIO()
    doc.write(buffer_texto, fmt="asc")
    return io.BytesIO(buffer_texto.getvalue().encode("utf-8"))


__all__ = ["construir_dxf_labor"]
