"""Mapa de isotiempos de detonación: interpolación del retardo (ms) de
cada taladro cargado sobre la sección, enmascarada al contorno real (sin
extrapolar fuera de la sección perforada).

Adaptado del enfoque de interpolación con `scipy.interpolate.griddata` +
enmascarado por polígono usado en proyectos de referencia de diseño de
voladura subterránea (mismo principio que un mapa de calor de secuencia
de disparo en software de blast design) — implementación propia sobre
`core.malla_perforacion` y `core.geometry`, no un cálculo físico de
propagación de onda de detonación.
"""

from __future__ import annotations

import numpy as np
from scipy.interpolate import griddata

from core.geometry import perfil_seccion, punto_en_poligono
from core.malla_perforacion import PosicionTaladro

RESOLUCION_GRILLA_DEFAULT = 60


def malla_isotiempos(
    taladros: list[PosicionTaladro],
    forma_seccion: str | None,
    ancho: float,
    alto: float,
    resolucion: int = RESOLUCION_GRILLA_DEFAULT,
) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """Devuelve (Y, Z, T) — grilla 2D del retardo interpolado (ms) dentro
    del contorno de la sección. `None` si hay menos de 3 taladros cargados
    con retardo asignado (no alcanza para interpolar)."""
    con_retardo = [t for t in taladros if t.retardo_ms is not None]
    if len(con_retardo) < 3:
        return None

    puntos = np.array([[t.y, t.z] for t in con_retardo])
    valores = np.array([t.retardo_ms for t in con_retardo])

    perfil = perfil_seccion(forma_seccion, ancho, alto)
    y_min, y_max = float(perfil[:, 0].min()), float(perfil[:, 0].max())
    z_min, z_max = 0.0, float(perfil[:, 1].max())

    ys = np.linspace(y_min, y_max, resolucion)
    zs = np.linspace(z_min, z_max, resolucion)
    Y, Z = np.meshgrid(ys, zs)

    # "linear" deja NaN fuera del casco convexo de los taladros, aunque esa
    # zona siga dentro del contorno (p. ej. las esquinas cerca de corona o
    # piso, más allá del taladro más externo) — se rellenan esos huecos con
    # el valor del taladro más cercano ("nearest"), para que el mapa cubra
    # toda la sección real, no solo el área entre taladros.
    T = griddata(puntos, valores, (Y, Z), method="linear")
    T_nearest = griddata(puntos, valores, (Y, Z), method="nearest")
    T = np.where(np.isnan(T), T_nearest, T)

    mascara = np.zeros(T.shape, dtype=bool)
    for i in range(T.shape[0]):
        for j in range(T.shape[1]):
            mascara[i, j] = punto_en_poligono(Y[i, j], Z[i, j], perfil)
    T = np.where(mascara, T, np.nan)

    return Y, Z, T
