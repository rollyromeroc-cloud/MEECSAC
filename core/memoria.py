"""Memoria de cálculo: desglose paso a paso (fórmula → sustitución →
resultado) de cada cifra del motor de voladura, para mostrarse en una
sección aparte de los resultados — trazabilidad tipo informe técnico.

Python puro; reutiliza las mismas fórmulas que `core.voladura`. Cualquier
cambio en el motor de cálculo debe reflejarse aquí también: el objetivo de
este módulo es mostrar la sustitución numérica explícita (no solo el
resultado final), así que la lógica no se puede derivar automáticamente sin
duplicarla.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.constants import (
    COEFICIENTE_ROCA,
    DISTANCIA_TALADROS_RANGO_M,
    METODO_TALADROS_SECCION,
    PIE_A_METROS,
)
from core.geometry import perimetro_seccion
from core.models import LaborMinera, ResultadoVoladura


@dataclass
class PasoCalculo:
    concepto: str
    formula: str
    sustitucion: str
    resultado: str


def _n(valor: float, decimales: int = 2) -> str:
    return f"{valor:,.{decimales}f}"


def memoria_calculo(labor: LaborMinera, resultado: ResultadoVoladura) -> list[PasoCalculo]:
    """Devuelve la lista ordenada de pasos que reproducen `resultado` a
    partir de los datos de entrada de `labor`."""
    densidad_label = (
        "Peso específico mineral" if labor.destino_material == "Mineral" else "Peso específico desmonte"
    )

    pasos = [
        PasoCalculo(
            "Área de la sección",
            "Ancho × Alto",
            f"{_n(labor.ancho_m)} × {_n(labor.alto_m)}",
            f"{_n(resultado.area_m2, 3)} m²",
        ),
        PasoCalculo(
            "Número de disparos",
            "Avance proyectado / Avance por disparo",
            f"{_n(labor.avance_proyectado_m)} / {_n(labor.avance_por_disparo_m)}",
            f"{resultado.n_disparos}",
        ),
        PasoCalculo(
            "Longitud final",
            "Longitud existente + Avance proyectado",
            f"{_n(labor.longitud_existente_m)} + {_n(labor.avance_proyectado_m)}",
            f"{_n(resultado.longitud_final_m)} m",
        ),
        PasoCalculo(
            "Cartuchos por disparo",
            "Taladros cargados × Cartuchos por taladro",
            f"{labor.taladros_cargados} × {labor.cartuchos_por_taladro}",
            f"{resultado.cartuchos_por_disparo}",
        ),
        PasoCalculo(
            "Explosivo por disparo",
            "Cartuchos por disparo × Peso por cartucho",
            f"{resultado.cartuchos_por_disparo} × {_n(labor.peso_cartucho_kg, 3)}",
            f"{_n(resultado.explosivo_por_disparo_kg)} kg",
        ),
        PasoCalculo(
            "Explosivo total",
            "Explosivo por disparo × N.° de disparos",
            f"{_n(resultado.explosivo_por_disparo_kg)} × {resultado.n_disparos}",
            f"{_n(resultado.explosivo_total_kg)} kg",
        ),
        PasoCalculo(
            f"{labor.tipo_explosivo_1} ({labor.pct_explosivo_1:.0f}%)",
            "Explosivo total × % tipo 1",
            f"{_n(resultado.explosivo_total_kg)} × {labor.pct_explosivo_1:.0f}%",
            f"{_n(resultado.explosivo_tipo1_kg)} kg",
        ),
        PasoCalculo(
            f"{labor.tipo_explosivo_2} ({labor.pct_explosivo_2:.0f}%)",
            "Explosivo total × % tipo 2",
            f"{_n(resultado.explosivo_total_kg)} × {labor.pct_explosivo_2:.0f}%",
            f"{_n(resultado.explosivo_tipo2_kg)} kg",
        ),
        PasoCalculo(
            "Volumen por disparo",
            "Área × Avance por disparo",
            f"{_n(resultado.area_m2, 3)} × {_n(labor.avance_por_disparo_m)}",
            f"{_n(resultado.volumen_por_disparo_m3)} m³",
        ),
        PasoCalculo(
            "Volumen total",
            "Área × Avance proyectado",
            f"{_n(resultado.area_m2, 3)} × {_n(labor.avance_proyectado_m)}",
            f"{_n(resultado.volumen_total_m3)} m³",
        ),
        PasoCalculo(
            "Tonelaje por disparo",
            f"Volumen por disparo × {densidad_label}",
            f"{_n(resultado.volumen_por_disparo_m3)} × {_n(resultado.densidad_usada_tm_m3)}",
            f"{_n(resultado.tonelaje_por_disparo_tm)} TM",
        ),
        PasoCalculo(
            "Tonelaje total",
            f"Volumen total × {densidad_label}",
            f"{_n(resultado.volumen_total_m3)} × {_n(resultado.densidad_usada_tm_m3)}",
            f"{_n(resultado.tonelaje_total_tm)} TM",
        ),
        PasoCalculo(
            "Factor de potencia",
            "Explosivo total / Tonelaje total",
            f"{_n(resultado.explosivo_total_kg)} / {_n(resultado.tonelaje_total_tm)}",
            f"{_n(resultado.factor_potencia_kg_tm)} kg/TM",
        ),
        PasoCalculo(
            "Consumo específico",
            "Explosivo total / Volumen total",
            f"{_n(resultado.explosivo_total_kg)} / {_n(resultado.volumen_total_m3)}",
            f"{_n(resultado.consumo_especifico_kg_m3)} kg/m³",
        ),
        PasoCalculo(
            "Total de taladros",
            "Taladros por disparo × N.° de disparos",
            f"{labor.taladros_cargados} × {resultado.n_disparos}",
            f"{resultado.total_taladros} unidades",
        ),
        PasoCalculo(
            labor.tipo_fulminante,
            "Taladros cargados × N.° de disparos",
            f"{labor.taladros_cargados} × {resultado.n_disparos}",
            f"{resultado.fulminantes_total} unidades",
        ),
        PasoCalculo(
            "Mecha de seguridad por taladro",
            f"(Longitud de barreno + Tramo de encendido) × {PIE_A_METROS}",
            f"({_n(labor.longitud_barreno_pies, 1)} + {_n(labor.tramo_encendido_pies, 1)}) × {PIE_A_METROS}",
            f"{_n(resultado.mecha_por_taladro_m, 3)} m",
        ),
        PasoCalculo(
            "Mecha de seguridad por disparo",
            "Taladros cargados × Mecha por taladro",
            f"{labor.taladros_cargados} × {_n(resultado.mecha_por_taladro_m, 3)}",
            f"{_n(resultado.mecha_por_disparo_m)} m",
        ),
        PasoCalculo(
            "Mecha de seguridad total",
            "Mecha por disparo × N.° de disparos",
            f"{_n(resultado.mecha_por_disparo_m)} × {resultado.n_disparos}",
            f"{_n(resultado.mecha_total_m)} m",
        ),
    ]

    if labor.metodo_taladros == METODO_TALADROS_SECCION:
        pasos.insert(
            3,
            PasoCalculo(
                "N.° de taladros por disparo (criterio de sección de la OTS)",
                "10 × √(Ancho × Alto)",
                f"10 × √({_n(labor.ancho_m)} × {_n(labor.alto_m)})",
                f"{labor.taladros_cargados} unidades",
            ),
        )

    if labor.alterar_por_roca:
        rango = DISTANCIA_TALADROS_RANGO_M.get(labor.tipo_roca)
        dt = labor.distancia_taladros_m or (sum(rango) / 2.0 if rango else 0.0)
        coeficiente = COEFICIENTE_ROCA.get(labor.tipo_roca, 0.0)
        perimetro = perimetro_seccion(labor.forma_seccion, labor.ancho_m, labor.alto_m)
        pasos.insert(
            3,
            PasoCalculo(
                f"N.° de taladros por disparo (criterio por tipo de roca {labor.tipo_roca.lower()} de la OTS)",
                "(Perímetro / dt) + (Coeficiente de roca × Área)",
                f"({_n(perimetro)} / {_n(dt, 3)}) + ({coeficiente:.1f} × {_n(resultado.area_m2, 3)})",
                f"{labor.taladros_cargados} unidades",
            ),
        )

    return pasos
