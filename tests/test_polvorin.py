import pytest

from core.models import Polvorin, PuntoRiesgo
from core.polvorin import (
    area_shoelace,
    calcular_guias,
    distancia_sugerida_tabla_k_m,
    distancia_utm,
    emr_kg_polvorin,
    evaluar_distancias,
)


def test_area_shoelace_cuadrado():
    # Cuadrado de 10 x 10 m -> área 100 m²
    vertices = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert area_shoelace(vertices) == pytest.approx(100.0)


def test_distancia_utm_pitagoras():
    # 3-4-5
    assert distancia_utm(0, 0, 3, 4) == pytest.approx(5.0)


def test_evaluar_distancias_cumple_y_no_cumple():
    polvorin = Polvorin(nombre="Polvorín 1", este_utm=500249, norte_utm=8387256)
    cerca = PuntoRiesgo(
        nombre="Poblado cercano",
        tipo="Local de riesgo / poblado",
        este_utm=500250,
        norte_utm=8387257,
        distancia_minima_requerida_m=50,
    )
    lejos = PuntoRiesgo(
        nombre="Vía pública",
        tipo="Tránsito público (vía)",
        este_utm=500000,
        norte_utm=8387000,
        distancia_minima_requerida_m=50,
    )
    resultados = evaluar_distancias(polvorin, [cerca, lejos])
    assert resultados[0].cumple is False
    assert resultados[1].cumple is True


def test_polvorin_radio_influencia_opcional():
    sin_radio = Polvorin(nombre="Polvorín 1", este_utm=0, norte_utm=0)
    assert sin_radio.radio_influencia_m is None

    con_radio = Polvorin(nombre="Polvorín 1", este_utm=0, norte_utm=0, radio_influencia_m=30.23)
    assert con_radio.radio_influencia_m == pytest.approx(30.23)


def test_emr_kg_polvorin_none_sin_composicion():
    polvorin = Polvorin(nombre="Polvorín 1", este_utm=0, norte_utm=0)
    assert emr_kg_polvorin(polvorin) is None


def test_emr_kg_polvorin_calcula_desde_items_almacenados():
    polvorin = Polvorin(
        nombre="Polvorín 1", este_utm=0, norte_utm=0,
        items_almacenados=[("Dinamita gelatina 80%", 2500)],
    )
    assert emr_kg_polvorin(polvorin) == pytest.approx(2500 * 0.787)


def test_distancia_sugerida_tabla_k_none_sin_emr():
    polvorin = Polvorin(nombre="Polvorín 1", este_utm=0, norte_utm=0)
    assert distancia_sugerida_tabla_k_m(polvorin, "Edificio habitado") is None


def test_distancia_sugerida_tabla_k_superficial_vs_subterraneo():
    base = dict(
        nombre="Polvorín 1", este_utm=0, norte_utm=0,
        items_almacenados=[("Dinamita gelatina 80%", 2500)],
    )
    superficial = Polvorin(tipo_instalacion="Superficial", **base)
    subterraneo = Polvorin(tipo_instalacion="Subterráneo", **base)
    d_sup, _ = distancia_sugerida_tabla_k_m(superficial, "Edificio habitado")
    d_sub, _ = distancia_sugerida_tabla_k_m(subterraneo, "Edificio habitado")
    assert d_sup > d_sub  # K=15 (superficial) vs K=8 (subterráneo)


def test_distancia_sugerida_tabla_k_none_si_no_esta_en_la_tabla():
    polvorin = Polvorin(
        nombre="Polvorín 1", este_utm=0, norte_utm=0, tipo_instalacion="Subterráneo",
        items_almacenados=[("Dinamita gelatina 80%", 2500)],
    )
    # "Agentes externos de riesgo" no está definido para polvorín subterráneo
    assert distancia_sugerida_tabla_k_m(polvorin, "Agentes externos de riesgo") is None


# Casos dorados tomados de un formato real de guías de polvorín (SUCAMEC):
# Emulsión/hidrogel: capacidad 575 kg/guía, solicitado 4825 kg -> 8 guías + 1 restante = 9.
# Conector para cordón de ignición: capacidad 80000 pzas, solicitado 2500 -> 0 + 1 = 1.
# Mecha de seguridad: capacidad 100000 m, solicitado 18000 -> 0 + 1 = 1.
def test_calcular_guias_emulsion_con_restante():
    resultado = calcular_guias(cantidad_solicitada=4825, capacidad_por_guia=575)
    assert resultado["guias_completas"] == 8
    assert resultado["cantidad_guias_completas"] == pytest.approx(4600)
    assert resultado["guia_restante"] == 1
    assert resultado["cantidad_restante"] == pytest.approx(225)
    assert resultado["guias_totales"] == 9


def test_calcular_guias_menor_a_una_capacidad():
    resultado = calcular_guias(cantidad_solicitada=2500, capacidad_por_guia=80000)
    assert resultado["guias_completas"] == 0
    assert resultado["guia_restante"] == 1
    assert resultado["guias_totales"] == 1


def test_calcular_guias_exacta_sin_restante():
    # Multiplo exacto de la capacidad: no debe agregar una guia de mas.
    resultado = calcular_guias(cantidad_solicitada=1150, capacidad_por_guia=575)
    assert resultado["guias_completas"] == 2
    assert resultado["guia_restante"] == 0
    assert resultado["guias_totales"] == 2


def test_calcular_guias_dos_variantes_no_se_combinan():
    # Ej. del usuario: Emulnor 3000 y Emulnor 5000, cada uno pide 9 guias
    # (8 completas + 1 incompleta) -> el total es 18, no se optimizan juntas.
    variante_a = calcular_guias(cantidad_solicitada=4825, capacidad_por_guia=575)
    variante_b = calcular_guias(cantidad_solicitada=4825, capacidad_por_guia=575)
    assert variante_a["guias_totales"] == 9
    assert variante_b["guias_totales"] == 9
    assert variante_a["guias_totales"] + variante_b["guias_totales"] == 18


def test_calcular_guias_cantidad_cero():
    resultado = calcular_guias(cantidad_solicitada=0, capacidad_por_guia=575)
    assert resultado["guias_totales"] == 0
