import math

import pytest

from core.malla_perforacion import (
    FACTOR_BURDEN_HOLMBERG,
    MARGEN_CONTORNO_DEFAULT_M,
    burden_inicial_m,
    generar_malla_perforacion,
)


def test_burden_inicial_regla_de_holmberg():
    # De = 36mm * sqrt(2) = 50.91mm ; B1 = 1.5 * 50.91mm = 76.37mm = 0.07637m
    b1 = burden_inicial_m(diametro_alivio_mm=36.0, n_alivio=2)
    assert b1 == pytest.approx(1.5 * 36.0 * math.sqrt(2) / 1000.0, abs=1e-6)


def test_burden_inicial_sin_alivio_no_falla():
    assert burden_inicial_m(diametro_alivio_mm=36.0, n_alivio=0) > 0


def test_genera_el_total_correcto_de_taladros():
    malla, _ = generar_malla_perforacion(
        ancho=1.77, alto=1.10, taladros_cargados=23, taladros_alivio=2,
        diametro_barreno_mm=36.0, forma_seccion="Baúl (hastiales rectos)",
    )
    assert len(malla) == 23 + 2
    n_alivio = sum(1 for t in malla if t.categoria == "alivio")
    n_arranque = sum(1 for t in malla if t.categoria == "arranque")
    n_contorno = sum(1 for t in malla if t.categoria == "contorno")
    assert n_alivio == 2
    assert n_arranque + n_contorno == 23


def test_arranque_no_supera_8_el_resto_va_a_contorno():
    malla, anillos = generar_malla_perforacion(
        ancho=2.00, alto=2.00, taladros_cargados=20, taladros_alivio=2,
        diametro_barreno_mm=36.0, forma_seccion="Baúl (hastiales rectos)",
    )
    n_arranque = sum(1 for t in malla if t.categoria == "arranque")
    n_contorno = sum(1 for t in malla if t.categoria == "contorno")
    assert n_arranque == 8
    assert n_contorno == 12
    assert len(anillos) == 2


def test_pocos_taladros_cargados_sin_contorno():
    malla, anillos = generar_malla_perforacion(
        ancho=1.20, alto=1.20, taladros_cargados=3, taladros_alivio=1,
        diametro_barreno_mm=36.0, forma_seccion="Baúl (hastiales rectos)",
    )
    n_arranque = sum(1 for t in malla if t.categoria == "arranque")
    n_contorno = sum(1 for t in malla if t.categoria == "contorno")
    assert n_arranque == 3
    assert n_contorno == 0
    assert len(anillos) == 1
    assert anillos[0].n_taladros == 3


def test_alivio_unico_queda_en_el_centro():
    malla, _ = generar_malla_perforacion(
        ancho=1.77, alto=1.10, taladros_cargados=0, taladros_alivio=1,
        diametro_barreno_mm=36.0, forma_seccion="Baúl (hastiales rectos)",
    )
    alivio = next(t for t in malla if t.categoria == "alivio")
    assert alivio.y == pytest.approx(0.0)
    assert alivio.z == pytest.approx(0.55)  # alto / 2


def test_anillos_de_arranque_alternan_cuadrado_y_rombo_con_burden_real():
    diametro_barreno = 36.0
    n_alivio = 2
    malla, anillos = generar_malla_perforacion(
        ancho=2.00, alto=2.00, taladros_cargados=8, taladros_alivio=n_alivio,
        diametro_barreno_mm=diametro_barreno, forma_seccion="Baúl (hastiales rectos)",
    )
    assert [a.forma for a in anillos] == ["Cuadrado", "Rombo"]
    assert [a.n_taladros for a in anillos] == [4, 4]

    b1_esperado_mm = burden_inicial_m(diametro_barreno, n_alivio) * 1000.0
    assert anillos[0].burden_mm == pytest.approx(b1_esperado_mm)
    assert anillos[1].burden_mm == pytest.approx(b1_esperado_mm * math.sqrt(2.0))
    # lado = burden * sqrt(2), mismo factor para cuadrado y rombo (misma
    # forma geométrica, solo rotada 45°)
    assert anillos[0].lado_mm == pytest.approx(anillos[0].burden_mm * math.sqrt(2.0))

    anillo_1 = [t for t in malla if t.categoria == "arranque" and t.anillo == 1]
    anillo_2 = [t for t in malla if t.categoria == "arranque" and t.anillo == 2]
    centro_z = 1.0
    # anillo 1 (cuadrado, rotación 0°): un punto debe caer sobre el eje y
    # (z == centro) — a diferencia del anillo 2 (rombo, rotado 45°).
    assert any(abs(t.z - centro_z) < 1e-6 for t in anillo_1)
    assert not any(abs(t.z - centro_z) < 1e-6 for t in anillo_2)


def test_diametro_alivio_por_defecto_usa_el_del_barreno():
    malla_a, anillos_a = generar_malla_perforacion(
        ancho=2.00, alto=2.00, taladros_cargados=4, taladros_alivio=2,
        diametro_barreno_mm=36.0, forma_seccion="Baúl (hastiales rectos)",
    )
    malla_b, anillos_b = generar_malla_perforacion(
        ancho=2.00, alto=2.00, taladros_cargados=4, taladros_alivio=2,
        diametro_barreno_mm=36.0, diametro_alivio_mm=36.0, forma_seccion="Baúl (hastiales rectos)",
    )
    assert anillos_a[0].burden_mm == pytest.approx(anillos_b[0].burden_mm)


def test_puntos_de_contorno_quedan_dentro_del_perfil_real():
    from core.geometry import perfil_seccion

    ancho, alto = 2.20, 1.55
    forma = "Baúl (hastiales rectos)"
    malla, _ = generar_malla_perforacion(
        ancho=ancho, alto=alto, taladros_cargados=20, taladros_alivio=2,
        diametro_barreno_mm=36.0, forma_seccion=forma,
    )
    contorno = [t for t in malla if t.categoria == "contorno"]
    assert len(contorno) > 0

    perfil = perfil_seccion(forma, ancho, alto)
    centro_y = perfil[:, 0].mean()
    centro_z = perfil[:, 1].mean()
    radio_perfil_max = max(math.hypot(y - centro_y, z - centro_z) for y, z in perfil)

    for t in contorno:
        radio_taladro = math.hypot(t.y - centro_y, t.z - centro_z)
        assert radio_taladro < radio_perfil_max  # con margen hacia adentro


def test_margen_contorno_y_factor_holmberg_por_defecto_son_positivos():
    assert MARGEN_CONTORNO_DEFAULT_M > 0
    assert FACTOR_BURDEN_HOLMBERG > 0
