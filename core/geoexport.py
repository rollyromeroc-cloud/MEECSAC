"""Exportación geoespacial de la seguridad de polvorín: GeoJSON y
shapefile, para subir a un geoportal o abrir en QGIS/AutoCAD.

Se exportan tres capas, con la misma semántica que ya usa la página de
Polvorín:
  - `polvorines`  (puntos)    — ubicación de cada polvorín + su EMR.
  - `cercos`      (polígonos) — cerco perimétrico, cuando tiene vértices.
  - `puntos_riesgo` (puntos)  — cada punto externo verificado.
  - `radios_influencia` (polígonos) — el radio de seguridad, discretizado
    como círculo, para que el geoportal lo muestre como área y no como un
    atributo suelto.

Las coordenadas de entrada son UTM (`este_utm`/`norte_utm`, ver
`core.polvorin`). El shapefile se escribe en UTM y lleva su `.prj`, que es
lo que espera un geoportal minero peruano; el GeoJSON se reproyecta a
lon/lat WGS84 porque el formato lo exige (RFC 7946).

No calcula nada nuevo: el EMR sale de `core.polvorin.emr_kg_polvorin` y las
distancias de `evaluar_distancias`.
"""

from __future__ import annotations

import io
import math
import zipfile

from pyproj import Transformer

from core.models import Polvorin, PuntoRiesgo, ResultadoDistancia
from core.polvorin import emr_kg_polvorin

N_LADOS_CIRCULO = 72  # discretización del radio de influencia (5° por lado)


def epsg_utm(zona_utm: int, hemisferio: str) -> int:
    """Código EPSG del huso UTM WGS84 — 326xx norte, 327xx sur."""
    base = 32700 if hemisferio.upper().startswith("S") else 32600
    return base + int(zona_utm)


def _wkt_utm(zona_utm: int, hemisferio: str) -> str:
    """WKT del sistema de coordenadas, para el `.prj` del shapefile. Sin
    esto QGIS abre la capa como "sin CRS" y el usuario tiene que asignarlo
    a mano cada vez."""
    sur = hemisferio.upper().startswith("S")
    meridiano = zona_utm * 6 - 183
    nombre = f"WGS_1984_UTM_Zone_{int(zona_utm)}{'S' if sur else 'N'}"
    falso_norte = 10000000.0 if sur else 0.0
    return (
        f'PROJCS["{nombre}",'
        'GEOGCS["GCS_WGS_1984",'
        'DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
        'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],'
        'PROJECTION["Transverse_Mercator"],'
        'PARAMETER["False_Easting",500000.0],'
        f'PARAMETER["False_Northing",{falso_norte}],'
        f'PARAMETER["Central_Meridian",{meridiano}.0],'
        'PARAMETER["Scale_Factor",0.9996],'
        'PARAMETER["Latitude_Of_Origin",0.0],'
        'UNIT["Meter",1.0]]'
    )


def circulo_utm(
    este: float, norte: float, radio_m: float, n_lados: int = N_LADOS_CIRCULO
) -> list[tuple[float, float]]:
    """Anillo cerrado (primer vértice repetido al final, como exige el
    formato de polígono) que aproxima un círculo de `radio_m`."""
    puntos = [
        (
            este + radio_m * math.cos(2 * math.pi * i / n_lados),
            norte + radio_m * math.sin(2 * math.pi * i / n_lados),
        )
        for i in range(n_lados)
    ]
    return puntos + [puntos[0]]


def _cerrar(anillo: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if not anillo:
        return anillo
    return anillo if anillo[0] == anillo[-1] else [*anillo, anillo[0]]


def _peor_resultado(
    nombre: str, resultados_por_polvorin: dict[str, list[ResultadoDistancia]]
) -> ResultadoDistancia | None:
    """El punto de riesgo más comprometido de un polvorín (el de menor
    holgura) — es el dato que decide si el polvorín cumple o no."""
    lista = resultados_por_polvorin.get(nombre) or []
    if not lista:
        return None
    return min(lista, key=lambda r: r.distancia_real_m - r.distancia_minima_m)


# --------------------------------------------------------------------------
# GeoJSON
# --------------------------------------------------------------------------


def construir_geojson(
    polvorines: list[Polvorin],
    puntos: list[PuntoRiesgo],
    resultados_por_polvorin: dict[str, list[ResultadoDistancia]],
    zona_utm: int,
    hemisferio: str,
) -> dict:
    """FeatureCollection en lon/lat WGS84 (RFC 7946). Cada feature lleva en
    `properties` la capa a la que pertenece, para poder filtrarla en el
    geoportal."""
    transformer = Transformer.from_crs(
        f"EPSG:{epsg_utm(zona_utm, hemisferio)}", "EPSG:4326", always_xy=True
    )

    def a_lonlat(este: float, norte: float) -> list[float]:
        lon, lat = transformer.transform(este, norte)
        return [lon, lat]

    features: list[dict] = []

    for p in polvorines:
        peor = _peor_resultado(p.nombre, resultados_por_polvorin)
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": a_lonlat(p.este_utm, p.norte_utm)},
            "properties": {
                "capa": "polvorines",
                "nombre": p.nombre,
                "tipo": p.tipo,
                "instalacion": p.tipo_instalacion,
                "este_utm": p.este_utm,
                "norte_utm": p.norte_utm,
                "emr_kg": emr_kg_polvorin(p),
                "cumple": None if peor is None else peor.cumple,
            },
        })
        if p.vertices_cerco:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[a_lonlat(e, n) for e, n in _cerrar(p.vertices_cerco)]],
                },
                "properties": {"capa": "cercos", "nombre": p.nombre, "tipo": p.tipo},
            })
        if p.radio_influencia_m:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        a_lonlat(e, n)
                        for e, n in circulo_utm(p.este_utm, p.norte_utm, p.radio_influencia_m)
                    ]],
                },
                "properties": {
                    "capa": "radios_influencia",
                    "nombre": p.nombre,
                    "radio_m": p.radio_influencia_m,
                },
            })

    for punto in puntos:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": a_lonlat(punto.este_utm, punto.norte_utm)},
            "properties": {
                "capa": "puntos_riesgo",
                "nombre": punto.nombre,
                "tipo": punto.tipo,
                "este_utm": punto.este_utm,
                "norte_utm": punto.norte_utm,
                "dist_min_m": punto.distancia_minima_requerida_m,
            },
        })

    return {"type": "FeatureCollection", "features": features}


# --------------------------------------------------------------------------
# Shapefile
# --------------------------------------------------------------------------


def _escribir_capa(zf: zipfile.ZipFile, nombre: str, escritor_fn, wkt: str) -> None:
    """Escribe una capa shapefile (.shp/.shx/.dbf/.prj) dentro del zip.
    pyshp escribe a tres streams separados, así que se arman en memoria y
    se agregan uno por uno — un shapefile no es un archivo, son varios."""
    import shapefile  # dependencia opcional aislada al punto de uso

    shp, shx, dbf = io.BytesIO(), io.BytesIO(), io.BytesIO()
    with shapefile.Writer(shp=shp, shx=shx, dbf=dbf) as w:
        escritor_fn(w)
    zf.writestr(f"{nombre}.shp", shp.getvalue())
    zf.writestr(f"{nombre}.shx", shx.getvalue())
    zf.writestr(f"{nombre}.dbf", dbf.getvalue())
    zf.writestr(f"{nombre}.prj", wkt)


def construir_shapefile_zip(
    polvorines: list[Polvorin],
    puntos: list[PuntoRiesgo],
    resultados_por_polvorin: dict[str, list[ResultadoDistancia]],
    zona_utm: int,
    hemisferio: str,
) -> io.BytesIO:
    """ZIP con una capa shapefile por tipo de entidad, en coordenadas UTM y
    con su `.prj`. Solo se incluyen las capas que tienen entidades (una capa
    vacía haría que el geoportal muestre una entrada inútil)."""
    wkt = _wkt_utm(zona_utm, hemisferio)
    buffer = io.BytesIO()

    con_cerco = [p for p in polvorines if p.vertices_cerco]
    con_radio = [p for p in polvorines if p.radio_influencia_m]

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        if polvorines:
            def _polvorines(w):
                w.field("nombre", "C", 80)
                w.field("tipo", "C", 30)
                # los nombres de campo DBF no pueden pasar de 10 caracteres;
                # "instalacion" (11) se truncaba solo a "instalacio".
                w.field("tipo_inst", "C", 20)
                w.field("emr_kg", "N", 18, 3)
                w.field("cumple", "C", 3)
                for p in polvorines:
                    peor = _peor_resultado(p.nombre, resultados_por_polvorin)
                    emr = emr_kg_polvorin(p)
                    w.point(p.este_utm, p.norte_utm)
                    w.record(
                        p.nombre, p.tipo, p.tipo_instalacion,
                        0.0 if emr is None else emr,
                        "" if peor is None else ("SI" if peor.cumple else "NO"),
                    )
            _escribir_capa(zf, "polvorines", _polvorines, wkt)

        if con_cerco:
            def _cercos(w):
                w.field("nombre", "C", 80)
                w.field("tipo", "C", 30)
                for p in con_cerco:
                    w.poly([[list(v) for v in _cerrar(p.vertices_cerco)]])
                    w.record(p.nombre, p.tipo)
            _escribir_capa(zf, "cercos", _cercos, wkt)

        if con_radio:
            def _radios(w):
                w.field("nombre", "C", 80)
                w.field("radio_m", "N", 18, 3)
                for p in con_radio:
                    anillo = circulo_utm(p.este_utm, p.norte_utm, p.radio_influencia_m)
                    w.poly([[list(v) for v in anillo]])
                    w.record(p.nombre, p.radio_influencia_m)
            _escribir_capa(zf, "radios_influencia", _radios, wkt)

        if puntos:
            def _puntos(w):
                w.field("nombre", "C", 80)
                w.field("tipo", "C", 40)
                w.field("dist_min_m", "N", 18, 3)
                for punto in puntos:
                    w.point(punto.este_utm, punto.norte_utm)
                    w.record(punto.nombre, punto.tipo, punto.distancia_minima_requerida_m)
            _escribir_capa(zf, "puntos_riesgo", _puntos, wkt)

    buffer.seek(0)
    return buffer
