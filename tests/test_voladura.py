"""Golden tests: el motor debe reproducir exactamente los valores del
informe técnico real (INFORME TECNICO OTS V&M.docx) para varias labores."""

import pytest

from core.models import LaborMinera
from core.voladura import (
    avance_desde_n_disparos,
    avance_desde_produccion_objetivo,
    calcular_resultado,
    taladros_desde_roca,
    taladros_por_disparo_seccion,
)


def test_galeria_nivel_2():
    labor = LaborMinera(
        nombre="Galería Nivel 2",
        tipo="Galería",
        ancho_m=1.77,
        alto_m=1.10,
        longitud_existente_m=9.00,
        avance_proyectado_m=66.00,
        avance_por_disparo_m=1.10,
        taladros_cargados=23,
        cartuchos_por_taladro=4,
        peso_cartucho_kg=0.08,
        pct_explosivo_1=40,
        pct_explosivo_2=60,
        destino_material="Desmonte",
        densidad_desmonte_tm_m3=2.70,
    )
    r = calcular_resultado(labor)

    assert r.area_m2 == pytest.approx(1.947, abs=1e-3)
    assert r.n_disparos == 60
    assert r.longitud_final_m == pytest.approx(75.00)
    assert r.cartuchos_por_disparo == 92
    assert r.explosivo_por_disparo_kg == pytest.approx(7.36)
    assert r.explosivo_total_kg == pytest.approx(441.60)
    assert r.explosivo_tipo1_kg == pytest.approx(176.64)
    assert r.explosivo_tipo2_kg == pytest.approx(264.96)
    assert r.fulminantes_total == 1380
    assert r.mecha_por_taladro_m == pytest.approx(1.524)
    assert r.mecha_total_m == pytest.approx(2103.12, abs=0.01)
    assert r.volumen_total_m3 == pytest.approx(128.50, abs=0.01)
    assert r.tonelaje_total_tm == pytest.approx(346.96, abs=0.01)
    assert r.tonelaje_por_disparo_tm == pytest.approx(5.78, abs=0.01)
    assert r.factor_potencia_kg_tm == pytest.approx(1.27, abs=0.01)


def test_cortada_frente_shaquira():
    labor = LaborMinera(
        nombre="Cortada – Frente Shaquira",
        tipo="Cortada",
        ancho_m=2.20,
        alto_m=1.55,
        longitud_existente_m=50.00,
        avance_proyectado_m=66.00,
        avance_por_disparo_m=1.10,
        taladros_cargados=23,
        cartuchos_por_taladro=4,
        peso_cartucho_kg=0.08,
        pct_explosivo_1=40,
        pct_explosivo_2=60,
        destino_material="Mineral",
        densidad_mineral_tm_m3=3.00,
    )
    r = calcular_resultado(labor)

    assert r.area_m2 == pytest.approx(3.41, abs=1e-2)
    assert r.n_disparos == 60
    assert r.volumen_total_m3 == pytest.approx(225.06, abs=0.01)
    assert r.tonelaje_total_tm == pytest.approx(675.18, abs=0.01)
    assert r.tonelaje_por_disparo_tm == pytest.approx(11.25, abs=0.01)
    assert r.factor_potencia_kg_tm == pytest.approx(0.65, abs=0.01)
    assert r.consumo_especifico_kg_m3 == pytest.approx(1.96, abs=0.01)


def test_pique_bajada_subnivel_02():
    labor = LaborMinera(
        nombre="Pique de Bajada al Subnivel Shaquira N.° 02",
        tipo="Pique",
        ancho_m=2.00,
        alto_m=2.00,
        avance_proyectado_m=61.60,
        avance_por_disparo_m=1.10,
        taladros_cargados=23,
        cartuchos_por_taladro=4,
        peso_cartucho_kg=0.08,
        pct_explosivo_1=40,
        pct_explosivo_2=60,
        destino_material="Desmonte",
        densidad_desmonte_tm_m3=2.70,
    )
    r = calcular_resultado(labor)

    assert r.n_disparos == 56
    assert r.explosivo_total_kg == pytest.approx(412.16, abs=0.01)
    assert r.explosivo_tipo1_kg == pytest.approx(164.86, abs=0.01)
    assert r.explosivo_tipo2_kg == pytest.approx(247.30, abs=0.01)
    assert r.fulminantes_total == 1288
    assert r.mecha_total_m == pytest.approx(1962.91, abs=0.01)
    assert r.volumen_total_m3 == pytest.approx(246.40, abs=0.01)
    assert r.tonelaje_total_tm == pytest.approx(665.28, abs=0.01)
    assert r.tonelaje_por_disparo_tm == pytest.approx(11.88, abs=0.01)
    assert r.factor_potencia_kg_tm == pytest.approx(0.62, abs=0.01)


def test_avance_desde_n_disparos_coincide_con_galeria_nivel_2():
    # Golden: Galería Nivel 2 -> n_disparos=60, avance_por_disparo=1.10 -> avance_proyectado=66.00
    assert avance_desde_n_disparos(60, 1.10) == pytest.approx(66.00)


def test_avance_desde_produccion_objetivo_coincide_con_galeria_nivel_2():
    # Golden: Galería Nivel 2 -> tonelaje_total=346.96 TM, área=1.947 m², densidad=2.70 -> avance=66.00
    avance = avance_desde_produccion_objetivo(346.96, 1.77, 1.10, 2.70)
    assert avance == pytest.approx(66.00, abs=0.01)


def test_avance_desde_produccion_objetivo_area_o_densidad_invalida_devuelve_cero():
    assert avance_desde_produccion_objetivo(100.0, 0.0, 1.10, 2.70) == 0.0
    assert avance_desde_produccion_objetivo(100.0, 1.77, 1.10, 0.0) == 0.0


def test_taladros_desde_roca_formula():
    # N.° T = (P/dt) + (C×S) -> (14.00/0.375) + (1.5×10.78) = 37.33 + 16.17 = 53.5 -> 54
    assert taladros_desde_roca(14.00, 10.78, 0.375, 1.5) == 54


def test_taladros_desde_roca_distancia_invalida_devuelve_cero():
    assert taladros_desde_roca(14.00, 10.78, 0.0, 1.5) == 0


def test_taladros_por_disparo_seccion_formula_del_cuadro_ots():
    # Cuadro de parámetros de la OTS: N.° taladros por disparo = 10 × √(A × H)
    # Sección 2.50 × 2.50 -> área 6.25 -> 10 × 2.5 = 25
    assert taladros_por_disparo_seccion(2.50, 2.50) == 25
    # Sección de área 10.78 m² (la del cuadro de referencia) -> 10 × 3.283 = 32.8 -> 33
    assert taladros_por_disparo_seccion(3.50, 3.08) == 33
    # no depende del tipo de roca ni del espaciamiento, solo del área: dos
    # secciones de la misma área dan el mismo número
    assert taladros_por_disparo_seccion(4.0, 1.0) == taladros_por_disparo_seccion(2.0, 2.0)


def test_taladros_por_disparo_seccion_area_invalida_devuelve_cero():
    assert taladros_por_disparo_seccion(0.0, 2.5) == 0
    assert taladros_por_disparo_seccion(2.5, 0.0) == 0


def test_total_de_taladros_y_detonadores_siguen_el_cuadro_ots():
    labor = LaborMinera(
        nombre="Galería", tipo="Galería", etapa="Desarrollo",
        ancho_m=2.5, alto_m=2.5, avance_proyectado_m=60.0, avance_por_disparo_m=1.5,
        diametro_barreno_mm=38.0, longitud_barreno_pies=6.0,
        taladros_cargados=25, taladros_alivio=2, destino_material="Desmonte",
    )
    r = calcular_resultado(labor)
    # Total de Taladros = taladros por disparo × N.° de disparos
    assert r.total_taladros == 25 * r.n_disparos
    # Cantidad de Detonadores por Disparo = N.° de taladros por disparo
    assert r.detonadores_por_disparo == 25
    # y el total de detonadores coincide con el total de taladros
    assert r.fulminantes_total == r.total_taladros


def test_mecha_por_taladro_es_longitud_de_barreno_mas_un_pie():
    # Cuadro de la OTS: mecha de seguridad por taladro = longitud de barreno
    # (pies) + 1 pie
    labor = LaborMinera(
        nombre="Galería", tipo="Galería", etapa="Desarrollo",
        ancho_m=2.5, alto_m=2.5, avance_proyectado_m=60.0, avance_por_disparo_m=1.5,
        diametro_barreno_mm=38.0, longitud_barreno_pies=6.0,
        taladros_cargados=25, taladros_alivio=2, destino_material="Desmonte",
    )
    r = calcular_resultado(labor)
    assert r.mecha_por_taladro_m == pytest.approx((6.0 + 1) * 0.3048)
    assert r.mecha_por_disparo_m == pytest.approx(25 * r.mecha_por_taladro_m)
    assert r.mecha_total_m == pytest.approx(r.mecha_por_disparo_m * r.n_disparos)
