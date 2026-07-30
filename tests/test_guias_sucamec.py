from io import BytesIO
from zipfile import ZipFile

import openpyxl
import pytest

from core.guias_sucamec import ProductoGuia, desglosar_guias, generar_zip_guias
from core.models import PolvorinGuiaSucamec

POLVORIN_PRUEBA = PolvorinGuiaSucamec(
    nombre="Polvorín N.° 1",
    direccion="KM 10 CARRETERA DE PRUEBA",
    distrito="DISTRITO TEST",
    provincia="PROVINCIA TEST",
    departamento="DEPARTAMENTO TEST",
    resolucion_explosivos_numero="N° 00001-2026-SUCAMEC/DEPP-SDAEPP",
    resolucion_explosivos_fecha="15/01/2026",
    resolucion_accesorios_numero="N° 00002-2026-SUCAMEC/DEPP-SDAEPP",
    resolucion_accesorios_fecha="16/01/2026",
    concesion_nombre="CONCESION DE PRUEBA",
    concesion_codigo="99999999X01",
    concesion_distrito="DISTRITO CONCESION",
    concesion_provincia="PROVINCIA CONCESION",
    concesion_departamento="DEPARTAMENTO CONCESION",
)


def test_desglosar_guias_emulsion_con_restante():
    # Mismo caso dorado que test_polvorin.py: 8 completas de 575 kg + 1 restante de 225 kg.
    guias = desglosar_guias(cantidad_solicitada=4825, capacidad_por_guia=575)
    assert len(guias) == 9
    assert all(g.cantidad == 575 and g.tipo == "completa" for g in guias[:8])
    assert guias[8].cantidad == 225
    assert guias[8].tipo == "restante"


def test_desglosar_guias_exacta_sin_restante():
    guias = desglosar_guias(cantidad_solicitada=1150, capacidad_por_guia=575)
    assert len(guias) == 2
    assert all(g.tipo == "completa" for g in guias)


def _producto_emulsion(nombre_variante: str) -> ProductoGuia:
    return ProductoGuia(
        nombre_variante=nombre_variante,
        categoria="Explosivos",
        producto_sucamec="Emulsión o hidrogel encartuchada",
        cantidad_solicitada=4825,
        capacidad_por_guia=575,
        unidad_abrev="KG",
        polvorin=POLVORIN_PRUEBA,
    )


def test_generar_zip_guias_dos_variantes_no_se_combinan():
    # Ej. del usuario: Emulnor 3000 y Emulnor 5000, cada uno 9 guias (18 en total).
    productos = [_producto_emulsion("Emulnor 3000"), _producto_emulsion("Emulnor 5000")]
    zip_buffer, resumen = generar_zip_guias(productos)
    assert len(resumen) == 18

    with ZipFile(BytesIO(zip_buffer.getvalue())) as zf:
        nombres = zf.namelist()
        assert len(nombres) == 36  # 18 guias x (tipo 1 + tipo 2)

        nombre_g1 = next(n for n in nombres if n.startswith("TIPO1_Emulnor_3000_guia_01_completa"))
        wb = openpyxl.load_workbook(BytesIO(zf.read(nombre_g1)))
        ws = wb.active
        assert ws["I21"].value == "EMULSIÓN O HIDROGEL ENCARTUCHADA"
        assert ws["AG21"].value == 575
        assert ws["AL21"].value == "KILOGRAMOS"
        assert ws["E51"].value == POLVORIN_PRUEBA.direccion
        assert ws["S59"].value == POLVORIN_PRUEBA.resolucion_explosivos_numero
        assert len(ws._images) == 2  # logos del modelo preservados

        nombre_restante = next(n for n in nombres if n.startswith("TIPO1_Emulnor_3000_guia_09_restante"))
        wb_restante = openpyxl.load_workbook(BytesIO(zf.read(nombre_restante)))
        assert wb_restante.active["AG21"].value == 225

        nombre_tipo2 = next(n for n in nombres if n.startswith("TIPO2_Emulnor_5000_guia_01_completa"))
        wb2 = openpyxl.load_workbook(BytesIO(zf.read(nombre_tipo2)))
        ws2 = wb2.active
        assert ws2["E40"].value == POLVORIN_PRUEBA.direccion
        assert "CONCESION DE PRUEBA" in ws2["E51"].value
        assert "99999999X01" in ws2["E51"].value
        assert ws2["E55"].value == POLVORIN_PRUEBA.concesion_distrito


def test_generar_zip_guias_categoria_accesorios_usa_plantilla_y_resolucion_correcta():
    producto = ProductoGuia(
        nombre_variante="Detonador X",
        categoria="Accesorios",
        producto_sucamec="Detonador de mecha o fulminante común",
        cantidad_solicitada=2500,
        capacidad_por_guia=500000,
        unidad_abrev="PZAS",
        polvorin=POLVORIN_PRUEBA,
    )
    zip_buffer, resumen = generar_zip_guias([producto])
    assert len(resumen) == 1  # menor a una capacidad -> 1 sola guia restante

    with ZipFile(BytesIO(zip_buffer.getvalue())) as zf:
        nombre_tipo1 = next(n for n in zf.namelist() if n.startswith("TIPO1_Detonador_X"))
        wb = openpyxl.load_workbook(BytesIO(zf.read(nombre_tipo1)))
        ws = wb.active
        assert ws["I21"].value == "DETONADOR DE MECHA O FULMINANTE COMÚN"
        assert ws["AG21"].value == 2500
        assert ws["AL21"].value == "UNIDADES"
        # Categoria Accesorios -> debe usar la resolucion de accesorios, no la de explosivos.
        assert ws["S59"].value == POLVORIN_PRUEBA.resolucion_accesorios_numero
