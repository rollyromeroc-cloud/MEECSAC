import numpy as np
import pytest

from core.geometry import malla_tunel, perfil_herradura, relacion_aspecto


def test_perfil_herradura_dimensiones():
    perfil = perfil_herradura(ancho=1.77, alto=1.10)
    ancho_real = perfil[:, 0].max() - perfil[:, 0].min()
    alto_real = perfil[:, 1].max() - perfil[:, 1].min()
    # tolerancia amplia: el arco es discretizado (n_arco puntos), así que el
    # máximo muestreado puede quedar levemente por debajo del ideal continuo
    assert ancho_real == pytest.approx(1.77, abs=1e-6)
    assert alto_real == pytest.approx(1.10, abs=0.01)
    # el piso está a z=0 en ambos extremos
    assert perfil[0, 1] == pytest.approx(0.0)
    assert perfil[-1, 1] == pytest.approx(0.0)


def test_perfil_herradura_arco_completo_si_ancho_grande():
    # ancho/2 >= alto -> el arco ocupa toda la altura, sin muros rectos
    perfil = perfil_herradura(ancho=10.0, alto=1.0)
    alto_muro_esperado = 0.0
    # el primer punto de muro (índice 1) debe coincidir en altura con el piso
    assert perfil[1, 1] == pytest.approx(alto_muro_esperado, abs=1e-9)


def test_malla_tunel_forma_y_extremos():
    malla = malla_tunel(ancho=2.0, alto=2.0, longitud=66.0, n_anillos=5)
    anillos = malla["anillos"]
    assert len(anillos) == 5
    # el primer anillo está en x=0, el último en x=longitud
    assert anillos[0][:, 0].max() == pytest.approx(0.0)
    assert anillos[-1][:, 0].max() == pytest.approx(66.0)

    longitudinales = malla["longitudinales"]
    assert len(longitudinales) == 3
    for linea in longitudinales:
        assert linea[:, 0].min() == pytest.approx(0.0)
        assert linea[:, 0].max() == pytest.approx(66.0)


def test_relacion_aspecto_preserva_escala_ancho_alto():
    # ancho y alto deben quedar a escala real entre sí (misma relación,
    # aunque los tres componentes estén normalizados por el máximo)
    rx, ry, rz = relacion_aspecto(ancho=2.75, alto=2.75, longitud=66.0)
    assert ry == pytest.approx(rz)  # sección cuadrada -> se ve cuadrada

    rx2, ry2, rz2 = relacion_aspecto(ancho=1.77, alto=1.10, longitud=66.0)
    assert ry2 / rz2 == pytest.approx(1.77 / 1.10)

    # el componente máximo de cada terna normalizada vale 1.0
    assert max(rx, ry, rz) == pytest.approx(1.0)
    assert max(rx2, ry2, rz2) == pytest.approx(1.0)


def test_relacion_aspecto_avance_no_mide_igual_que_seccion():
    # con avance >> sección, el eje x debe verse claramente más largo
    rx, ry, rz = relacion_aspecto(ancho=1.20, alto=1.20, longitud=66.0)
    assert rx > max(ry, rz) * 2

    # dos avances distintos deben producir proporciones distintas (no "todas
    # miden igual" independientemente del valor real): con más avance, la
    # sección ocupa relativamente menos del cuadro (eje x siempre normalizado a 1.0)
    _, ry_corto, _ = relacion_aspecto(ancho=1.20, alto=1.20, longitud=1.10)
    _, ry_largo, _ = relacion_aspecto(ancho=1.20, alto=1.20, longitud=66.0)
    assert ry_largo < ry_corto
