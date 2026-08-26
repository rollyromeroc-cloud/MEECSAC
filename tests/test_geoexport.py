import io
import zipfile

import pytest
import shapefile

from core.geoexport import (
    circulo_utm,
    construir_geojson,
    construir_shapefile_zip,
    epsg_utm,
)
from core.models import Polvorin, PuntoRiesgo
from core.polvorin import evaluar_distancias


def _escenario():
    polvorines = [
        Polvorin(
            nombre="Polvorín Explosivos 1", tipo="Explosivos", tipo_instalacion="Superficial",
            este_utm=500249, norte_utm=8387256, radio_influencia_m=120.0,
            vertices_cerco=[(500229, 8387236), (500269, 8387236), (500269, 8387276), (500229, 8387276)],
            items_almacenados=[("Dinamita gelatina 80%", 2500)],
        ),
        Polvorin(nombre="Polvorín Accesorios", tipo="Accesorios", este_utm=500480, norte_utm=8387400),
    ]
    puntos = [
        PuntoRiesgo(
            nombre="Centro poblado", tipo="Edificio habitado",
            este_utm=500700, norte_utm=8387600, distancia_minima_requerida_m=300,
        ),
    ]
    resultados = {p.nombre: evaluar_distancias(p, puntos) for p in polvorines}
    return polvorines, puntos, resultados


def test_epsg_utm_norte_y_sur():
    assert epsg_utm(18, "S") == 32718
    assert epsg_utm(18, "N") == 32618


def test_circulo_utm_es_anillo_cerrado_del_radio_pedido():
    anillo = circulo_utm(1000.0, 2000.0, 50.0, n_lados=8)
    assert anillo[0] == anillo[-1], "el polígono debe cerrar repitiendo el primer vértice"
    assert len(anillo) == 9
    for e, n in anillo:
        assert ((e - 1000.0) ** 2 + (n - 2000.0) ** 2) ** 0.5 == pytest.approx(50.0)


def test_shapefile_zip_trae_las_cuatro_capas_con_prj():
    polvorines, puntos, resultados = _escenario()
    zf = zipfile.ZipFile(construir_shapefile_zip(polvorines, puntos, resultados, 18, "S"))
    nombres = set(zf.namelist())
    for capa in ("polvorines", "cercos", "radios_influencia", "puntos_riesgo"):
        # un shapefile no es un archivo sino varios; sin .prj QGIS lo abre sin CRS
        for ext in ("shp", "shx", "dbf", "prj"):
            assert f"{capa}.{ext}" in nombres
        assert "WGS_1984_UTM_Zone_18S" in zf.read(f"{capa}.prj").decode()


def test_shapefile_polvorines_relee_atributos_y_geometria():
    polvorines, puntos, resultados = _escenario()
    zf = zipfile.ZipFile(construir_shapefile_zip(polvorines, puntos, resultados, 18, "S"))
    r = shapefile.Reader(
        shp=io.BytesIO(zf.read("polvorines.shp")),
        shx=io.BytesIO(zf.read("polvorines.shx")),
        dbf=io.BytesIO(zf.read("polvorines.dbf")),
    )
    campos = [f[0] for f in r.fields[1:]]
    # ningún nombre de campo debe pasar de 10 caracteres, o el DBF lo trunca solo
    assert all(len(c) <= 10 for c in campos), campos
    assert campos == ["nombre", "tipo", "tipo_inst", "emr_kg", "cumple"]

    assert len(r.shapes()) == 2
    registro = r.records()[0]
    assert registro["nombre"] == "Polvorín Explosivos 1"
    assert registro["emr_kg"] == pytest.approx(2500 * 0.787)
    assert registro["cumple"] == "SI"  # 567 m reales vs 300 m requeridos
    assert r.shapes()[0].points[0] == pytest.approx((500249.0, 8387256.0))


def test_shapefile_omite_capas_sin_entidades():
    # dos polvorines sin cerco ni radio, y sin puntos de riesgo: solo debe
    # salir la capa de polvorines, no capas vacías inútiles
    polvorines = [Polvorin(nombre="P1", este_utm=500000, norte_utm=8390000)]
    zf = zipfile.ZipFile(construir_shapefile_zip(polvorines, [], {}, 18, "S"))
    capas = {n.rsplit(".", 1)[0] for n in zf.namelist()}
    assert capas == {"polvorines"}


def test_geojson_reproyecta_a_lonlat_y_etiqueta_cada_capa():
    polvorines, puntos, resultados = _escenario()
    gj = construir_geojson(polvorines, puntos, resultados, 18, "S")
    assert gj["type"] == "FeatureCollection"
    capas = [f["properties"]["capa"] for f in gj["features"]]
    assert sorted(set(capas)) == ["cercos", "polvorines", "puntos_riesgo", "radios_influencia"]

    punto = next(f for f in gj["features"] if f["properties"]["capa"] == "polvorines")
    lon, lat = punto["geometry"]["coordinates"]
    # GeoJSON exige lon/lat WGS84 (RFC 7946), no UTM
    assert -81 < lon < -68, lon
    assert -19 < lat < 0, lat
    assert punto["properties"]["emr_kg"] == pytest.approx(2500 * 0.787)


def test_geojson_polvorin_sin_composicion_reporta_emr_none():
    polvorines, puntos, resultados = _escenario()
    gj = construir_geojson(polvorines, puntos, resultados, 18, "S")
    sin_comp = next(
        f for f in gj["features"]
        if f["properties"]["capa"] == "polvorines" and f["properties"]["nombre"] == "Polvorín Accesorios"
    )
    # no se asume 0 kg: sin composición registrada el EMR es desconocido
    assert sin_comp["properties"]["emr_kg"] is None
