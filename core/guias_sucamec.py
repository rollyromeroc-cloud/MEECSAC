"""Generador de guias SUCAMEC (Formato N.° 23) tipo 1 (FAMESA -> Polvorin) y
tipo 2 (Polvorin -> Unidad minera), a partir del calculo de guias por
producto (core.polvorin.calcular_guias) y de los datos del polvorin/concesion
asignados.

Las plantillas en assets/plantillas_sucamec/ son los modelos reales ya
llenados por el usuario: se abren tal cual y solo se sobreescriben las
celdas de producto/cantidad/unidades y, segun corresponda, los datos del
polvorin (origen/destino) y de la concesion de destino. Todo lo demas del
modelo (encabezados, secciones I, IV, notas, logos) se preserva intacto.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import openpyxl

from core.constants import PLANTILLA_GUIA_TIPO1, PLANTILLA_GUIA_TIPO2, UNIDAD_SUCAMEC_TEXTO
from core.models import PolvorinGuiaSucamec
from core.polvorin import calcular_guias

RAIZ_PLANTILLAS = Path(__file__).resolve().parent.parent / "assets" / "plantillas_sucamec"


@dataclass
class GuiaIndividual:
    numero: int
    cantidad: float
    tipo: str  # "completa" o "restante"


@dataclass
class ProductoGuia:
    """Un producto/variante con su cantidad solicitada y el polvorin asignado."""

    nombre_variante: str
    categoria: str  # "Explosivos" o "Accesorios"
    producto_sucamec: str
    cantidad_solicitada: float
    capacidad_por_guia: float
    unidad_abrev: str  # "KG", "M" o "PZAS"
    polvorin: PolvorinGuiaSucamec


def desglosar_guias(cantidad_solicitada: float, capacidad_por_guia: float) -> list[GuiaIndividual]:
    """Convierte el resultado de calcular_guias en la lista de guias
    individuales a generar (N completas con la capacidad maxima por guia, mas
    1 restante si sobra una cantidad menor a la capacidad)."""
    resultado = calcular_guias(cantidad_solicitada, capacidad_por_guia)
    guias: list[GuiaIndividual] = []
    numero = 1
    for _ in range(resultado["guias_completas"]):
        guias.append(GuiaIndividual(numero=numero, cantidad=capacidad_por_guia, tipo="completa"))
        numero += 1
    if resultado["guia_restante"]:
        guias.append(GuiaIndividual(numero=numero, cantidad=resultado["cantidad_restante"], tipo="restante"))
    return guias


def _partes_fecha(fecha_ddmmaaaa: str) -> tuple[int | None, int | None, int | None]:
    """Convierte 'DD/MM/AAAA' en (dia, mes, anio) enteros; None si no es valida."""
    if not fecha_ddmmaaaa or not str(fecha_ddmmaaaa).strip():
        return None, None, None
    partes = str(fecha_ddmmaaaa).strip().split("/")
    if len(partes) != 3:
        return None, None, None
    try:
        return int(partes[0]), int(partes[1]), int(partes[2])
    except ValueError:
        return None, None, None


def _rellenar_producto(ws, producto: str, cantidad: float, unidad_abrev: str) -> None:
    ws["I21"] = producto.upper()
    ws["AG21"] = cantidad
    ws["AL21"] = UNIDAD_SUCAMEC_TEXTO.get(unidad_abrev, unidad_abrev)


def _rellenar_destino_polvorin_tipo1(ws, polvorin: PolvorinGuiaSucamec, categoria: str) -> None:
    numero, fecha = polvorin.resolucion_para(categoria)
    dia, mes, anio = _partes_fecha(fecha)
    if polvorin.direccion:
        ws["E51"] = polvorin.direccion
    if polvorin.distrito:
        ws["E55"] = polvorin.distrito
    if polvorin.provincia:
        ws["S55"] = polvorin.provincia
    if polvorin.departamento:
        ws["AE55"] = polvorin.departamento
    if numero:
        ws["S59"] = numero
    if dia:
        ws["AE59"] = dia
    if mes:
        ws["AH59"] = mes
    if anio:
        ws["AK59"] = anio


def _rellenar_origen_polvorin_tipo2(ws, polvorin: PolvorinGuiaSucamec, categoria: str) -> None:
    numero, fecha = polvorin.resolucion_para(categoria)
    dia, mes, anio = _partes_fecha(fecha)
    if polvorin.direccion:
        ws["E40"] = polvorin.direccion
    if polvorin.distrito:
        ws["E44"] = polvorin.distrito
    if polvorin.provincia:
        ws["S44"] = polvorin.provincia
    if polvorin.departamento:
        ws["AE44"] = polvorin.departamento
    if numero:
        ws["S48"] = numero
    if dia:
        ws["AE48"] = dia
    if mes:
        ws["AH48"] = mes
    if anio:
        ws["AK48"] = anio


def _rellenar_destino_concesion_tipo2(ws, polvorin: PolvorinGuiaSucamec) -> None:
    if polvorin.concesion_nombre or polvorin.concesion_codigo:
        ws["E51"] = (
            f"CONCESIÓN MINERA {polvorin.concesion_nombre} CON CODIGO UNICO:\n"
            f"{polvorin.concesion_codigo}\n"
        )
    if polvorin.concesion_distrito:
        ws["E55"] = polvorin.concesion_distrito
    if polvorin.concesion_provincia:
        ws["S55"] = polvorin.concesion_provincia
    if polvorin.concesion_departamento:
        ws["AE55"] = polvorin.concesion_departamento


def generar_guia_tipo1(producto: ProductoGuia, guia: GuiaIndividual) -> BytesIO:
    ruta_plantilla = RAIZ_PLANTILLAS / PLANTILLA_GUIA_TIPO1[producto.categoria]
    wb = openpyxl.load_workbook(ruta_plantilla)
    ws = wb.active
    _rellenar_producto(ws, producto.producto_sucamec, guia.cantidad, producto.unidad_abrev)
    _rellenar_destino_polvorin_tipo1(ws, producto.polvorin, producto.categoria)
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def generar_guia_tipo2(producto: ProductoGuia, guia: GuiaIndividual) -> BytesIO:
    ruta_plantilla = RAIZ_PLANTILLAS / PLANTILLA_GUIA_TIPO2
    wb = openpyxl.load_workbook(ruta_plantilla)
    ws = wb.active
    _rellenar_producto(ws, producto.producto_sucamec, guia.cantidad, producto.unidad_abrev)
    _rellenar_origen_polvorin_tipo2(ws, producto.polvorin, producto.categoria)
    _rellenar_destino_concesion_tipo2(ws, producto.polvorin)
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def _nombre_base(nombre_variante: str) -> str:
    limpio = "".join(caracter if caracter.isalnum() else "_" for caracter in nombre_variante.strip())
    limpio = "_".join(filter(None, limpio.split("_")))
    return limpio or "producto"


def generar_zip_guias(productos: list[ProductoGuia]) -> tuple[BytesIO, list[dict]]:
    """Genera un .zip con los Excel tipo 1 y tipo 2 de cada guia individual de
    cada producto/variante. Devuelve el .zip en memoria y un resumen de filas
    (para mostrar una tabla en la UI) con producto, guia, cantidad y archivos."""
    buffer_zip = BytesIO()
    resumen: list[dict] = []
    with ZipFile(buffer_zip, "w", ZIP_DEFLATED) as zf:
        for producto in productos:
            guias = desglosar_guias(producto.cantidad_solicitada, producto.capacidad_por_guia)
            base = _nombre_base(producto.nombre_variante)
            for guia in guias:
                sufijo = f"guia_{guia.numero:02d}_{guia.tipo}"

                buffer1 = generar_guia_tipo1(producto, guia)
                nombre1 = f"TIPO1_{base}_{sufijo}.xlsx"
                zf.writestr(nombre1, buffer1.getvalue())

                buffer2 = generar_guia_tipo2(producto, guia)
                nombre2 = f"TIPO2_{base}_{sufijo}.xlsx"
                zf.writestr(nombre2, buffer2.getvalue())

                resumen.append({
                    "Producto/variante": producto.nombre_variante,
                    "Polvorín": producto.polvorin.nombre,
                    "N.° de guía": guia.numero,
                    "Tipo de guía": guia.tipo,
                    "Cantidad": guia.cantidad,
                    "Unidad": producto.unidad_abrev,
                    "Archivo TIPO 1": nombre1,
                    "Archivo TIPO 2": nombre2,
                })
    buffer_zip.seek(0)
    return buffer_zip, resumen
