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
    # sin alterar_por_roca (comportamiento por defecto), no aparece el paso
    assert "N.° de taladros" not in por_concepto


def test_memoria_calculo_incluye_paso_de_taladros_cuando_se_altera_por_roca():
    labor = LaborMinera(
        nombre="Galería Nivel 2",
        ancho_m=1.77,
        alto_m=1.10,
        forma_seccion="Baúl (hastiales rectos)",
        avance_proyectado_m=66.00,
        avance_por_disparo_m=1.10,
        taladros_cargados=18,  # = taladros_desde_roca(perimetro_seccion(...), area, 0.375, 2.0)
        cartuchos_por_taladro=4,
        peso_cartucho_kg=0.08,
        pct_explosivo_1=40,
        pct_explosivo_2=60,
        destino_material="Desmonte",
        densidad_desmonte_tm_m3=2.70,
        tipo_roca="Dura",
        alterar_por_roca=True,
        distancia_taladros_m=0.375,
    )
    resultado = calcular_resultado(labor)
    pasos = memoria_calculo(labor, resultado)
    por_concepto = {p.concepto: p for p in pasos}

    paso_taladros = por_concepto["N.° de taladros (criterio de roca dura)"]
    assert "÷" not in paso_taladros.sustitucion  # solo la memoria de docx convierte "/" a "÷"
    assert "0.375" in paso_taladros.sustitucion
    assert "2.0" in paso_taladros.sustitucion
    assert paso_taladros.resultado == "18 unidades"
