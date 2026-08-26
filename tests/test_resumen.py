import pandas as pd
import pyarrow as pa
import pytest

from core.models import LaborMinera
from core.voladura import calcular_programa
from viz.resumen import COLUMNAS_ADITIVAS, con_fila_total, tabla_resultados


def _labores() -> list[LaborMinera]:
    return [
        LaborMinera(
            nombre="Galería 1", tipo="Galería", etapa="Desarrollo",
            ancho_m=2.5, alto_m=2.5, longitud_existente_m=10.0,
            avance_proyectado_m=60.0, avance_por_disparo_m=1.5,
            diametro_barreno_mm=38.0, longitud_barreno_pies=6.0,
            taladros_cargados=33, taladros_alivio=3, destino_material="Desmonte",
        ),
        LaborMinera(
            nombre="Tajeo 1", tipo="Tajeo", etapa="Explotación",
            ancho_m=3.0, alto_m=2.5, longitud_existente_m=0.0,
            avance_proyectado_m=40.0, avance_por_disparo_m=1.2,
            diametro_barreno_mm=38.0, longitud_barreno_pies=6.0,
            taladros_cargados=25, taladros_alivio=2, destino_material="Mineral",
        ),
    ]


def test_tabla_resultados_una_fila_por_labor():
    labores = _labores()
    tabla = tabla_resultados(labores, calcular_programa(labores))
    assert len(tabla) == 2
    assert list(tabla["Labor"]) == ["Galería 1", "Tajeo 1"]


def test_produccion_se_separa_segun_el_destino_del_material():
    labores = _labores()
    tabla = tabla_resultados(labores, calcular_programa(labores))
    desmonte, mineral = tabla.iloc[0], tabla.iloc[1]
    assert desmonte["Producción mineral (TM)"] == 0.0
    assert desmonte["Producción desmonte (TM)"] > 0
    assert mineral["Producción desmonte (TM)"] == 0.0
    assert mineral["Producción mineral (TM)"] > 0


def test_fila_total_suma_solo_las_columnas_aditivas():
    labores = _labores()
    resultados = calcular_programa(labores)
    tabla = tabla_resultados(labores, resultados)
    con_total = con_fila_total(tabla, resultados)

    assert len(con_total) == len(tabla) + 1
    total = con_total.iloc[-1]
    assert total["Labor"] == "TOTAL"
    for columna in COLUMNAS_ADITIVAS:
        assert total[columna] == pytest.approx(tabla[columna].sum())

    # sumar estas no significaría nada, así que van vacías
    for columna in ("Avance x disparo (m)", "N.° taladros x disparo", "Área (m²)"):
        assert total[columna] is None


def test_factor_de_potencia_total_es_cociente_de_sumas():
    labores = _labores()
    resultados = calcular_programa(labores)
    total = con_fila_total(tabla_resultados(labores, resultados), resultados).iloc[-1]

    explosivo = sum(r.explosivo_total_kg for r in resultados)
    tonelaje = sum(r.tonelaje_total_tm for r in resultados)
    assert total["Factor de potencia (kg/TM)"] == pytest.approx(round(explosivo / tonelaje, 2))


def test_fila_total_no_rompe_la_serializacion_arrow():
    # Regresión: mezclar un texto ("—") con números en una columna numérica
    # revienta `st.dataframe`, que serializa vía pyarrow. Ya pasó varias
    # veces en este proyecto, por eso las celdas sin valor van como None.
    labores = _labores()
    resultados = calcular_programa(labores)
    con_total = con_fila_total(tabla_resultados(labores, resultados), resultados)
    pa.Table.from_pandas(con_total)  # lanza si algún tipo de columna quedó mezclado


def test_con_fila_total_sobre_tabla_vacia_no_falla():
    assert con_fila_total(pd.DataFrame(), []).empty
