"""Módulo de seguridad de polvorín: distancias y área del cerco perimétrico.

Coordenadas asumidas en UTM (misma zona/huso) para poder tratarlas como un
plano cartesiano local — válido para el rango de distancias típico de un
polvorín (cientos a pocos miles de metros), sin corrección de curvatura.

Importante: las distancias mínimas de seguridad NO se hardcodean en este
módulo. Deben ingresarse en la UI (campo editable por punto de riesgo) y
verificarse contra el reglamento vigente (D.S. N.° 024-2016-EM y
modificatorias) antes de tomar decisiones operativas con este resultado.
"""

from __future__ import annotations

import math

from core.emr import TABLA_K_SUBTERRANEO, TABLA_K_SUPERFICIAL, distancia_seguridad_m, emr_total_kg
from core.models import Polvorin, PuntoRiesgo, ResultadoDistancia


def distancia_utm(este1: float, norte1: float, este2: float, norte2: float) -> float:
    """Distancia euclidiana plana entre dos puntos UTM."""
    return math.hypot(este2 - este1, norte2 - norte1)


def area_shoelace(vertices: list[tuple[float, float]]) -> float:
    """Área de un polígono (fórmula del cordón/shoelace) a partir de sus vértices UTM.

    Los vértices deben estar en orden (horario o antihorario), sin repetir el
    primero al final.
    """
    n = len(vertices)
    if n < 3:
        return 0.0
    total = 0.0
    for i in range(n):
        x1, y1 = vertices[i]
        x2, y2 = vertices[(i + 1) % n]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def perimetro(vertices: list[tuple[float, float]]) -> float:
    n = len(vertices)
    if n < 2:
        return 0.0
    total = 0.0
    for i in range(n):
        x1, y1 = vertices[i]
        x2, y2 = vertices[(i + 1) % n]
        total += math.hypot(x2 - x1, y2 - y1)
    return total


def calcular_guias(cantidad_solicitada: float, capacidad_por_guia: float) -> dict:
    """Replica el cálculo de guías de remisión por tipo de explosivo/accesorio
    (una guía cubre como máximo `capacidad_por_guia` unidades; si sobra una
    cantidad menor a la capacidad, se necesita una guía adicional incompleta).

    Cada tipo/variante se calcula de forma independiente — dos productos que
    requieren 9 guías cada uno suman 18 guías en total, no se combinan entre sí.
    """
    if capacidad_por_guia <= 0 or cantidad_solicitada <= 0:
        return {
            "guias_completas": 0,
            "cantidad_guias_completas": 0.0,
            "guia_restante": 0,
            "cantidad_restante": 0.0,
            "guias_totales": 0,
        }
    guias_completas = int(cantidad_solicitada // capacidad_por_guia)
    cantidad_guias_completas = guias_completas * capacidad_por_guia
    cantidad_restante = cantidad_solicitada - cantidad_guias_completas
    guia_restante = 1 if cantidad_restante > 0 else 0
    return {
        "guias_completas": guias_completas,
        "cantidad_guias_completas": cantidad_guias_completas,
        "guia_restante": guia_restante,
        "cantidad_restante": cantidad_restante,
        "guias_totales": guias_completas + guia_restante,
    }


def emr_kg_polvorin(polvorin: Polvorin) -> float | None:
    """EMR (kg equivalente dinamita 60%) de `polvorin`, a partir de su
    composición (`items_almacenados`) — `None` si no se registró
    composición (no se asume `cantidad_almacenada_kg` como equivalente,
    porque es kg de producto real, no necesariamente kg equivalente)."""
    if not polvorin.items_almacenados:
        return None
    return emr_total_kg(polvorin.items_almacenados)


def distancia_sugerida_tabla_k_m(polvorin: Polvorin, tipo_punto_riesgo: str) -> tuple[float, float] | None:
    """(D barricado, D libre) sugeridas por la Tabla N.° 2 de valores de K
    (ver `core.emr`), a partir del EMR del polvorín y su
    `tipo_instalacion` (Superficial/Subterráneo). `None` si no hay EMR
    calculable o la tabla no define K para `tipo_punto_riesgo` en ese tipo
    de instalación. Es una SUGERENCIA de referencia — la distancia que
    determina el cumplimiento sigue siendo la que el usuario confirma en
    `PuntoRiesgo.distancia_minima_requerida_m` (ver docstring del módulo)."""
    emr_kg = emr_kg_polvorin(polvorin)
    if not emr_kg:
        return None
    tabla = TABLA_K_SUPERFICIAL if polvorin.tipo_instalacion == "Superficial" else TABLA_K_SUBTERRANEO
    k = tabla.get(tipo_punto_riesgo)
    if k is None:
        return None
    return distancia_seguridad_m(emr_kg, k)


def evaluar_distancias(
    polvorin: Polvorin, puntos_riesgo: list[PuntoRiesgo]
) -> list[ResultadoDistancia]:
    """Calcula la distancia real de un polvorín a cada punto de riesgo y la
    compara contra la distancia mínima requerida (capturada en cada punto)."""
    resultados = []
    for punto in puntos_riesgo:
        d_real = distancia_utm(
            polvorin.este_utm, polvorin.norte_utm, punto.este_utm, punto.norte_utm
        )
        resultados.append(
            ResultadoDistancia(
                punto_nombre=punto.nombre,
                punto_tipo=punto.tipo,
                distancia_real_m=d_real,
                distancia_minima_m=punto.distancia_minima_requerida_m,
                cumple=d_real >= punto.distancia_minima_requerida_m,
            )
        )
    return resultados
