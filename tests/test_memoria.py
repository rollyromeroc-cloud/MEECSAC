import pytest

from core.memoria import memoria_calculo
from core.models import LaborMinera
from core.voladura import calcular_resultado


def test_memoria_calculo_coincide_con_resultado_galeria():
    labor = LaborMinera(
        nombre="Galería Nivel 2",
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
    resultado = calcular_resultado(labor)
    pasos = memoria_calculo(labor, resultado)

    por_concepto = {p.concepto: p for p in pasos}

    assert "1.947 m²" in por_concepto["Área de la sección"].resultado
    assert por_concepto["Número de disparos"].resultado == "60"
    assert "441.60 kg" in por_concepto["Explosivo total"].resultado
    assert "1.27" in por_concepto["Factor de potencia"].resultado
    # cada paso trae los tres campos no vacíos
    for paso in pasos:
        assert paso.formula
        assert paso.sustitucion
        assert paso.resultado
