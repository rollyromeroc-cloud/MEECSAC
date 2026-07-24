import numpy as np
import pytest

from core.geometry import malla_tunel, perfil_herradura


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
