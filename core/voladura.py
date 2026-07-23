"""Motor de cálculo de perforación y voladura.

Generaliza la secuencia de cálculo usada en el informe técnico de referencia
(sección → malla de perforación → explosivos → accesorios → avance/volumen/
tonelaje → factor de potencia) para cualquier labor minera. Python puro,
sin dependencias de Streamlit/QGIS, para poder testearse de forma aislada.
"""

from __future__ import annotations

from core.constants import PIE_A_METROS
from core.models import LaborMinera, ResultadoVoladura


def pies_a_metros(pies: float) -> float:
    return pies * PIE_A_METROS


def calcular_resultado(labor: LaborMinera) -> ResultadoVoladura:
    area_m2 = labor.ancho_m * labor.alto_m

    if labor.avance_por_disparo_m > 0:
        n_disparos = round(labor.avance_proyectado_m / labor.avance_por_disparo_m)
    else:
        n_disparos = 0

    longitud_final_m = labor.longitud_existente_m + labor.avance_proyectado_m

    cartuchos_por_disparo = labor.taladros_cargados * labor.cartuchos_por_taladro
    explosivo_por_disparo_kg = cartuchos_por_disparo * labor.peso_cartucho_kg
    explosivo_total_kg = explosivo_por_disparo_kg * n_disparos
    explosivo_tipo1_kg = explosivo_total_kg * (labor.pct_explosivo_1 / 100.0)
    explosivo_tipo2_kg = explosivo_total_kg * (labor.pct_explosivo_2 / 100.0)

    volumen_por_disparo_m3 = area_m2 * labor.avance_por_disparo_m
    volumen_total_m3 = area_m2 * labor.avance_proyectado_m

    densidad_usada_tm_m3 = (
        labor.densidad_mineral_tm_m3
        if labor.destino_material == "Mineral"
        else labor.densidad_desmonte_tm_m3
    )
    tonelaje_por_disparo_tm = volumen_por_disparo_m3 * densidad_usada_tm_m3
    tonelaje_total_tm = volumen_total_m3 * densidad_usada_tm_m3

    factor_potencia_kg_tm = (
        explosivo_total_kg / tonelaje_total_tm if tonelaje_total_tm > 0 else 0.0
    )
    consumo_especifico_kg_m3 = (
        explosivo_total_kg / volumen_total_m3 if volumen_total_m3 > 0 else 0.0
    )

    fulminantes_total = labor.taladros_cargados * n_disparos

    mecha_por_taladro_m = pies_a_metros(
        labor.longitud_barreno_pies + labor.tramo_encendido_pies
    )
    mecha_por_disparo_m = labor.taladros_cargados * mecha_por_taladro_m
    mecha_total_m = mecha_por_disparo_m * n_disparos

    return ResultadoVoladura(
        labor_nombre=labor.nombre,
        area_m2=area_m2,
        longitud_final_m=longitud_final_m,
        n_disparos=n_disparos,
        cartuchos_por_disparo=cartuchos_por_disparo,
        explosivo_por_disparo_kg=explosivo_por_disparo_kg,
        explosivo_total_kg=explosivo_total_kg,
        explosivo_tipo1_kg=explosivo_tipo1_kg,
        explosivo_tipo2_kg=explosivo_tipo2_kg,
        volumen_por_disparo_m3=volumen_por_disparo_m3,
        volumen_total_m3=volumen_total_m3,
        densidad_usada_tm_m3=densidad_usada_tm_m3,
        tonelaje_por_disparo_tm=tonelaje_por_disparo_tm,
        tonelaje_total_tm=tonelaje_total_tm,
        factor_potencia_kg_tm=factor_potencia_kg_tm,
        consumo_especifico_kg_m3=consumo_especifico_kg_m3,
        fulminantes_total=fulminantes_total,
        mecha_por_taladro_m=mecha_por_taladro_m,
        mecha_por_disparo_m=mecha_por_disparo_m,
        mecha_total_m=mecha_total_m,
    )


def calcular_programa(labores: list[LaborMinera]) -> list[ResultadoVoladura]:
    return [calcular_resultado(labor) for labor in labores]
