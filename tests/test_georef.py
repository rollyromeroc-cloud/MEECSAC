import numpy as np
import pytest

from core.georef import (
    calcular_rumbo_pendiente,
    matriz_rotacion,
    matriz_rotacion_vertical,
    transformar_vertices,
)


def test_calcular_rumbo_pendiente_hacia_el_este():
    rumbo, pendiente, distancia = calcular_rumbo_pendiente(0.0, 0.0, 100.0, 100.0, 0.0, 100.0)
    assert rumbo == pytest.approx(90.0)
    assert pendiente == pytest.approx(0.0)
    assert distancia == pytest.approx(100.0)


def test_calcular_rumbo_pendiente_hacia_el_norte():
    rumbo, pendiente, distancia = calcular_rumbo_pendiente(0.0, 0.0, 100.0, 0.0, 100.0, 100.0)
    assert rumbo == pytest.approx(0.0)
    assert pendiente == pytest.approx(0.0)
    assert distancia == pytest.approx(100.0)


def test_calcular_rumbo_pendiente_noreste_45():
    rumbo, pendiente, distancia = calcular_rumbo_pendiente(0.0, 0.0, 100.0, 100.0, 100.0, 100.0)
    assert rumbo == pytest.approx(45.0)
    assert distancia == pytest.approx(np.hypot(100, 100))


def test_calcular_rumbo_pendiente_descendiendo():
    # baja 10 m de cota en 100 m horizontales -> pendiente positiva (minera: + = bajando)
    rumbo, pendiente, distancia = calcular_rumbo_pendiente(0.0, 0.0, 100.0, 0.0, 100.0, 90.0)
    assert pendiente > 0
    assert pendiente == pytest.approx(np.degrees(np.arctan2(10.0, 100.0)))


def test_calcular_rumbo_pendiente_ascendiendo():
    rumbo, pendiente, distancia = calcular_rumbo_pendiente(0.0, 0.0, 100.0, 0.0, 100.0, 110.0)
    assert pendiente < 0


def test_matriz_rotacion_es_ortonormal_propia():
    for rumbo in (0.0, 45.0, 90.0, 180.0, 270.0):
        for pendiente in (-30.0, 0.0, 30.0):
            R = matriz_rotacion(rumbo, pendiente)
            assert np.allclose(R.T @ R, np.eye(3), atol=1e-9)
            assert np.linalg.det(R) == pytest.approx(1.0, abs=1e-9)


def test_matriz_rotacion_rumbo_0_pendiente_0_mapea_avance_a_norte():
    # rumbo=0 (hacia el norte), pendiente=0 (nivel): el eje local de avance
    # (columna 0) debe coincidir exactamente con el Norte del mundo (0,1,0).
    R = matriz_rotacion(0.0, 0.0)
    assert R[:, 0] == pytest.approx([0.0, 1.0, 0.0], abs=1e-9)
    # el eje "alto" (columna 2) debe ser vertical puro (0,0,1)
    assert R[:, 2] == pytest.approx([0.0, 0.0, 1.0], abs=1e-9)


def test_matriz_rotacion_rumbo_90_pendiente_0_mapea_avance_a_este():
    R = matriz_rotacion(90.0, 0.0)
    assert R[:, 0] == pytest.approx([1.0, 0.0, 0.0], abs=1e-9)


def test_matriz_rotacion_vertical_es_ortonormal_propia():
    for sentido in ("abajo", "arriba"):
        R = matriz_rotacion_vertical(sentido)
        assert np.allclose(R.T @ R, np.eye(3), atol=1e-9)
        assert np.linalg.det(R) == pytest.approx(1.0, abs=1e-9)


def test_matriz_rotacion_vertical_abajo_mapea_extrusion_a_cota_negativa():
    # columna 2 = eje de extrusión local de malla_solida_pique
    R = matriz_rotacion_vertical("abajo")
    assert R[:, 2] == pytest.approx([0.0, 0.0, -1.0], abs=1e-9)


def test_matriz_rotacion_vertical_arriba_mapea_extrusion_a_cota_positiva():
    R = matriz_rotacion_vertical("arriba")
    assert R[:, 2] == pytest.approx([0.0, 0.0, 1.0], abs=1e-9)


def test_matriz_rotacion_vertical_sentido_invalido():
    with pytest.raises(ValueError):
        matriz_rotacion_vertical("lateral")


def test_matriz_rotacion_pendiente_vertical_lanza_error():
    with pytest.raises(ValueError):
        matriz_rotacion(0.0, 90.0)


def test_transformar_vertices_traslada_y_rota():
    locales = np.array([[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    R = matriz_rotacion(0.0, 0.0)  # avance local -> Norte mundo
    origen = (500000.0, 8390000.0, 4200.0)
    mundo = transformar_vertices(locales, origen, R)
    assert mundo[0] == pytest.approx(origen)
    # 10 m de avance local -> 10 m más al Norte
    assert mundo[1] == pytest.approx([500000.0, 8390010.0, 4200.0])
    # 1 m de ancho local -> 1 m menos de Este (columna 1 de R con rumbo=0
    # apunta hacia el Oeste; el lado físico es arbitrario, ver docstring
    # de matriz_rotacion — lo que importa es que quede perpendicular y
    # horizontal, lo cual ya se verifica en test_matriz_rotacion_es_ortonormal_propia)
    assert mundo[2] == pytest.approx([499999.0, 8390000.0, 4200.0])
