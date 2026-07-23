import pytest

from core.models import Polvorin, PuntoRiesgo
from core.polvorin import area_shoelace, distancia_utm, evaluar_distancias


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
