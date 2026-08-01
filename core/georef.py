"""Georreferenciación de labores mineras: rumbo/pendiente entre dos puntos
UTM+cota, y la matriz de rotación que lleva la malla local (de
`core.geometry`) a coordenadas de mundo (Este, Norte, Cota), para exportar
a DXF/AutoCAD en su posición real.

Python puro (numpy), sin dependencias de `ezdxf` ni Streamlit.
"""

from __future__ import annotations

import numpy as np


def calcular_rumbo_pendiente(
    este1: float, norte1: float, cota1: float,
    este2: float, norte2: float, cota2: float,
) -> tuple[float, float, float]:
    """Rumbo (grados horarios desde el Norte, 0-360), pendiente (grados,
    positiva = descendiendo del punto 1 al punto 2) y distancia horizontal
    (m) entre dos puntos UTM+cota. Convención minera estándar.

    Si los dos puntos están (casi) en la misma vertical, la pendiente no
    está definida (labor subvertical) — usar `matriz_rotacion_vertical` en
    ese caso, no esta función."""
    delta_este = este2 - este1
    delta_norte = norte2 - norte1
    delta_cota = cota2 - cota1
    distancia_horizontal = float(np.hypot(delta_este, delta_norte))
    rumbo = float(np.degrees(np.arctan2(delta_este, delta_norte)) % 360.0)
    if distancia_horizontal < 1e-9:
        pendiente = float("nan")
    else:
        pendiente = float(np.degrees(np.arctan2(-delta_cota, distancia_horizontal)))
    return rumbo, pendiente, distancia_horizontal


def matriz_rotacion(rumbo_deg: float, pendiente_deg: float) -> np.ndarray:
    """Matriz 3x3 cuyas columnas son los ejes locales de una GALERÍA
    (avance, ancho, alto) expresados en el mundo (Este, Norte, Cota).

    Convención minera: el eje "alto" se mantiene lo más vertical posible
    sujeto a ser perpendicular al eje de avance; el eje "ancho" se
    mantiene horizontal. Es una rotación propia (det=+1, sin espejo), para
    no invertir las normales salientes de la malla.

    Lanza ValueError si la pendiente es (casi) vertical — ese caso es un
    Pique/Chimenea y debe usar `matriz_rotacion_vertical`, no esta función.
    """
    azimut = np.radians(rumbo_deg)
    dip = np.radians(pendiente_deg)
    eje_avance = np.array([
        np.sin(azimut) * np.cos(dip),
        np.cos(azimut) * np.cos(dip),
        -np.sin(dip),
    ])
    arriba = np.array([0.0, 0.0, 1.0])
    eje_ancho = np.cross(arriba, eje_avance)
    norma = np.linalg.norm(eje_ancho)
    if norma < 1e-6:
        raise ValueError(
            "Pendiente ~90°: usar matriz_rotacion_vertical (labor subvertical), no matriz_rotacion."
        )
    eje_ancho = eje_ancho / norma
    eje_alto = np.cross(eje_avance, eje_ancho)
    return np.column_stack([eje_avance, eje_ancho, eje_alto])


def matriz_rotacion_vertical(sentido: str) -> np.ndarray:
    """Matriz 3x3 cuyas columnas son los ejes locales de un PIQUE/CHIMENEA
    (X, Y, extrusión) expresados en el mundo (Este, Norte, Cota) — el eje
    de extrusión de `malla_solida_pique` es la columna 2 (local Z), no la
    columna 0 como en las galerías.

    `sentido`: "abajo" (Pique típico, o cota_final < cota_inicio) o
    "arriba" (Chimenea típico, o cota_final > cota_inicio)."""
    if sentido == "abajo":
        return np.array([
            [1.0, 0.0, 0.0],
            [0.0, -1.0, 0.0],
            [0.0, 0.0, -1.0],
        ])
    if sentido == "arriba":
        return np.eye(3)
    raise ValueError(f"sentido inválido: {sentido!r} (debe ser 'abajo' o 'arriba')")


def transformar_vertices(
    vertices_locales: np.ndarray,
    origen_utm_cota: tuple[float, float, float],
    rotacion: np.ndarray,
) -> np.ndarray:
    """Lleva los vértices locales de una malla (`core.geometry`) a
    coordenadas de mundo: `origen + R @ local`, vectorizado sobre todas
    las filas."""
    origen = np.asarray(origen_utm_cota, dtype=float)
    return vertices_locales @ rotacion.T + origen


__all__ = [
    "calcular_rumbo_pendiente",
    "matriz_rotacion",
    "matriz_rotacion_vertical",
    "transformar_vertices",
]
