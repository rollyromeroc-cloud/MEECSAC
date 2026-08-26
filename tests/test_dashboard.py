import pytest

from core.models import LaborMinera, Polvorin, PuntoRiesgo
from core.polvorin import evaluar_distancias
from core.voladura import calcular_programa
from viz.dashboard import fig_estado_cumplimiento, kpis_polvorin, kpis_voladura


def _labores() -> list[LaborMinera]:
    return [
        LaborMinera(
            nombre="Galería 1", tipo="Galería", etapa="Desarrollo",
            ancho_m=2.5, alto_m=2.5, longitud_existente_m=10.0,
            avance_proyectado_m=60.0, avance_por_disparo_m=1.5,
            diametro_barreno_mm=38.0, longitud_barreno_pies=6.0,
            taladros_cargados=30, taladros_alivio=3,
            destino_material="Desmonte",
        ),
        LaborMinera(
            nombre="Tajeo 1", tipo="Tajeo", etapa="Explotación",
            ancho_m=3.0, alto_m=2.5, longitud_existente_m=0.0,
            avance_proyectado_m=40.0, avance_por_disparo_m=1.2,
            diametro_barreno_mm=38.0, longitud_barreno_pies=6.0,
            taladros_cargados=25, taladros_alivio=2,
            destino_material="Mineral",
        ),
    ]


def test_kpis_voladura_usa_cociente_de_sumas_no_promedio_de_cocientes():
    labores = _labores()
    resultados = calcular_programa(labores)
    kpis = kpis_voladura(labores, resultados)
    etiquetas = [k.etiqueta for k in kpis]
    assert etiquetas == [
        "Labores", "Avance programado", "Disparos",
        "Explosivo total", "Tonelaje total", "Factor de potencia",
    ]
    assert kpis[0].valor == "2"

    explosivo = sum(r.explosivo_total_kg for r in resultados)
    tonelaje = sum(r.tonelaje_total_tm for r in resultados)
    esperado = explosivo / tonelaje
    promedio_de_cocientes = sum(r.factor_potencia_kg_tm for r in resultados) / len(resultados)
    assert kpis[5].valor == f"{esperado:,.3f} kg/TM"
    # el promedio de los factores por labor da un valor distinto — este test
    # falla si alguien lo "simplifica" a un promedio.
    assert esperado != pytest.approx(promedio_de_cocientes)


def _escenario_polvorin():
    polvorines = [
        Polvorin(
            nombre="Polvorín 1", tipo="Explosivos", este_utm=500000, norte_utm=8390000,
            items_almacenados=[("Dinamita gelatina 80%", 2500)],
        ),
        Polvorin(nombre="Polvorín 2", tipo="Accesorios", este_utm=500100, norte_utm=8390000),
    ]
    puntos = [
        PuntoRiesgo(
            nombre="Poblado", tipo="Edificio habitado",
            este_utm=500050, norte_utm=8390000, distancia_minima_requerida_m=200,
        ),
        PuntoRiesgo(
            nombre="Vía", tipo="Tránsito público (vía)",
            este_utm=503000, norte_utm=8390000, distancia_minima_requerida_m=100,
        ),
    ]
    resultados = {p.nombre: evaluar_distancias(p, puntos) for p in polvorines}
    return polvorines, puntos, resultados


def test_kpis_polvorin_emr_solo_suma_polvorines_con_composicion():
    polvorines, puntos, resultados = _escenario_polvorin()
    kpis = kpis_polvorin(polvorines, puntos, resultados)
    por_etiqueta = {k.etiqueta: k for k in kpis}
    assert por_etiqueta["Polvorines"].valor == "2"
    assert por_etiqueta["Puntos de riesgo"].valor == "2"
    # solo Polvorín 1 tiene composición; Polvorín 2 no se cuenta como 0 kg
    assert por_etiqueta["EMR total"].valor == f"{2500 * 0.787:,.2f} kg"
    assert "1 de 2 polvorines" in por_etiqueta["EMR total"].ayuda


def test_kpis_polvorin_cumplimiento_sobre_el_total_de_verificaciones():
    polvorines, puntos, resultados = _escenario_polvorin()
    kpis = {k.etiqueta: k.valor for k in kpis_polvorin(polvorines, puntos, resultados)}
    # 2 polvorines x 2 puntos = 4 verificaciones
    assert kpis["Verificaciones"] == "4"
    todos = [r for lista in resultados.values() for r in lista]
    cumplen = sum(1 for r in todos if r.cumple)
    assert kpis["Cumplen"] == f"{cumplen:,}"
    assert kpis["Cumplimiento"] == f"{cumplen / 4 * 100:,.1f} %"


def test_figura_cumplimiento_se_construye_con_datos():
    _, _, resultados = _escenario_polvorin()
    assert fig_estado_cumplimiento(resultados).data


def test_figura_cumplimiento_sin_datos_no_falla():
    # sin datos se devuelve una figura con el mensaje explicativo, no una
    # excepción ni un gráfico vacío sin contexto
    assert fig_estado_cumplimiento({}).layout.annotations


def test_la_plataforma_no_usa_graficos_de_barras():
    # guardia de regresión: los gráficos de barras no forman parte de un
    # informe OTS y se retiraron de toda la plataforma.
    import plotly.graph_objects as go

    import viz.dashboard as dashboard

    polvorines, puntos, resultados = _escenario_polvorin()
    figuras = [fig_estado_cumplimiento(resultados)]
    labores = _labores()
    assert not any(
        isinstance(traza, go.Bar) for fig in figuras for traza in fig.data
    )
    # y el módulo ya no expone ningún constructor de barras
    assert not [n for n in vars(dashboard) if n.startswith("fig_") and "barra" in n]
    assert kpis_voladura(labores, calcular_programa(labores))
    assert kpis_polvorin(polvorines, puntos, resultados)
