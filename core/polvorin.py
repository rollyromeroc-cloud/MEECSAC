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
