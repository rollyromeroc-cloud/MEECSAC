import pytest

from core.emr import (
    TABLA_K_SUBTERRANEO,
    TABLA_K_SUPERFICIAL,
    distancia_seguridad_m,
    emr_total_kg,
    equivalente_din60_kg,
    raiz_cubica_emr,
)


def test_equivalente_indirecto_multiplica_cantidad_por_factor():
    # Dinamita gelatina 80%: factor 0.787 (kg equivalente por kg de producto)
    assert equivalente_din60_kg("Dinamita gelatina 80%", 2500) == pytest.approx(1967.5)


def test_equivalente_directo_divide_cantidad_entre_factor():
    # Fulminante N.° 8: 1416 unidades = 1 kg equivalente
    assert equivalente_din60_kg("Fulminante común N.° 8", 100000) == pytest.approx(
        100000 / 1416, abs=1e-6
    )


def test_equivalente_item_desconocido_o_cantidad_cero_da_cero():
    assert equivalente_din60_kg("Producto inexistente", 100) == 0.0
    assert equivalente_din60_kg("Dinamita gelatina 80%", 0) == 0.0


def test_emr_total_suma_todos_los_items():
    w = emr_total_kg([
        ("Dinamita gelatina 80%", 2500),
        ("Emulsión o hidrogel encartuchada", 6500),
    ])
    assert w == pytest.approx(1967.5 + 4634.5)


def test_raiz_cubica_emr():
    assert raiz_cubica_emr(6602.0) == pytest.approx(6602.0 ** (1 / 3))
    assert raiz_cubica_emr(0.0) == 0.0


def test_distancia_seguridad_libre_es_el_doble_de_barricado():
    d_barricado, d_libre = distancia_seguridad_m(6602.0, 15.0)
    assert d_barricado == pytest.approx(15.0 * 6602.0 ** (1 / 3))
    assert d_libre == pytest.approx(d_barricado * 2.0)


def test_tabla_k_superficial_mas_estricta_que_subterraneo_en_items_comunes():
    # el mismo tipo de instalación exige mayor K (más distancia) en
    # superficie que en subterráneo, según la tabla de referencia.
    comunes = set(TABLA_K_SUPERFICIAL) & set(TABLA_K_SUBTERRANEO)
    assert comunes  # deben compartir al menos las categorías básicas
    for tipo in comunes:
        assert TABLA_K_SUPERFICIAL[tipo] >= TABLA_K_SUBTERRANEO[tipo]
