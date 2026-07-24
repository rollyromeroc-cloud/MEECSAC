"""Geometría pura para el esquema 3D de una labor minera (túnel tipo herradura).

Sin dependencias de graficación; solo numpy. Genera el contorno de la sección
transversal (ancho × alto) y su extrusión a lo largo del avance, para que la
capa de visualización (Plotly) solo tenga que dibujar los puntos ya
calculados.
"""

from __future__ import annotations

import numpy as np


def perfil_herradura(ancho: float, alto: float, n_arco: int = 24) -> np.ndarray:
    """Contorno 2D (y, z) de una sección tipo herradura/bóveda.

    Muros verticales rectos hasta donde empieza el arco, y arco semi-elíptico
    hasta la corona. Si el ancho es grande respecto al alto, el arco ocupa
    toda la altura (sin muros rectos) — heurística razonable para un
    esquema visual, no un diseño geomecánico.

    Devuelve un array (N, 2) recorriendo el contorno: piso-izquierda →
    muro izquierdo → arco (izquierda a derecha) → piso-derecha.
    """
    radio = ancho / 2.0
    flecha = min(radio, alto)
    alto_muro = alto - flecha

    puntos = [(-radio, 0.0), (-radio, alto_muro)]

    angulos = np.linspace(np.pi, 0.0, n_arco)
    for ang in angulos:
        y = radio * np.cos(ang)
        z = alto_muro + flecha * np.sin(ang)
        puntos.append((y, z))

    puntos.append((radio, 0.0))
    return np.array(puntos)


def malla_tunel(
    ancho: float,
    alto: float,
    longitud: float,
    n_anillos: int = 14,
    n_arco: int = 24,
) -> dict:
    """Anillos (secciones transversales) y líneas longitudinales de un túnel
    extruido a lo largo del eje X, listos para dibujarse como wireframe 3D.

    Devuelve un dict con:
      - "anillos": lista de arrays (n_perfil, 3) con columnas (x, y, z)
      - "longitudinales": lista de arrays (n_anillos, 3) en puntos clave del
        perfil (piso izquierdo, corona, piso derecho)
      - "perfil": el contorno 2D usado (y, z)
    """
    perfil = perfil_herradura(ancho, alto, n_arco=n_arco)
    xs = np.linspace(0.0, longitud, n_anillos)

    anillos = [
        np.column_stack([np.full(len(perfil), x), perfil[:, 0], perfil[:, 1]])
        for x in xs
    ]

    indices_clave = [0, len(perfil) // 2, len(perfil) - 1]
    longitudinales = [
        np.column_stack([xs, np.full(len(xs), perfil[idx, 0]), np.full(len(xs), perfil[idx, 1])])
        for idx in indices_clave
    ]

    return {"anillos": anillos, "longitudinales": longitudinales, "perfil": perfil}
