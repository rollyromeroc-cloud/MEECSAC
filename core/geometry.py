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
    x_inicio: float = 0.0,
) -> dict:
    """Anillos (secciones transversales) y líneas longitudinales de un tramo
    de túnel extruido a lo largo del eje X (de `x_inicio` a
    `x_inicio + longitud`), listos para dibujarse como wireframe 3D.

    `x_inicio` permite encadenar dos tramos (p. ej. longitud existente y
    avance proyectado) sin recalcular el perfil.

    Devuelve un dict con:
      - "anillos": lista de arrays (n_perfil, 3) con columnas (x, y, z)
      - "longitudinales": lista de arrays (n_anillos, 3) en puntos clave del
        perfil (piso izquierdo, corona, piso derecho)
      - "perfil": el contorno 2D usado (y, z)
    """
    perfil = perfil_herradura(ancho, alto, n_arco=n_arco)
    xs = np.linspace(x_inicio, x_inicio + longitud, n_anillos)

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


def _anillos_de_tramo(perfil: np.ndarray, xs: np.ndarray) -> list[np.ndarray]:
    return [
        np.column_stack([np.full(len(perfil), x), perfil[:, 0], perfil[:, 1]])
        for x in xs
    ]


def malla_solida_tunel(
    ancho: float,
    alto: float,
    longitud_existente: float,
    avance_proyectado: float,
    n_anillos_existente: int = 8,
    n_anillos_proyectado: int = 14,
    n_arco: int = 24,
) -> dict:
    """Vértices y triángulos de una superficie sólida (tubo abierto tipo
    herradura) para el tramo existente y el proyectado, con una etiqueta de
    tramo por triángulo para poder colorearlos distinto.

    Devuelve un dict con:
      - "vertices": array (N, 3) de todos los vértices (x, y, z)
      - "triangulos": array (M, 3) de índices de vértice por triángulo
      - "tramo_por_triangulo": lista de "existente"/"proyectado" (largo M)
      - "x_frontera": x donde termina lo existente y empieza lo proyectado
    """
    perfil = perfil_herradura(ancho, alto, n_arco=n_arco)
    n_perfil = len(perfil)

    tramos_xs = []
    if longitud_existente > 0:
        tramos_xs.append(("existente", np.linspace(0.0, longitud_existente, max(n_anillos_existente, 2))))
    xs_proy = np.linspace(
        longitud_existente, longitud_existente + avance_proyectado, max(n_anillos_proyectado, 2)
    )
    if tramos_xs:
        xs_proy = xs_proy[1:]  # evita duplicar el anillo de empalme
    tramos_xs.append(("proyectado", xs_proy))

    vertices: list[tuple[float, float, float]] = []
    anillos_idx: list[list[int]] = []
    anillo_tramo: list[str] = []
    for nombre_tramo, xs in tramos_xs:
        for x in xs:
            idx_inicio = len(vertices)
            vertices.extend((x, y, z) for y, z in perfil)
            anillos_idx.append(list(range(idx_inicio, idx_inicio + n_perfil)))
            anillo_tramo.append(nombre_tramo)

    triangulos: list[tuple[int, int, int]] = []
    tramo_por_triangulo: list[str] = []
    for r in range(len(anillos_idx) - 1):
        ring_a, ring_b = anillos_idx[r], anillos_idx[r + 1]
        # el tramo del segmento es el del anillo de llegada (evita marcar el
        # anillo de empalme, que pertenece a "existente", como "proyectado")
        tramo = anillo_tramo[r + 1]
        for j in range(n_perfil - 1):
            a0, a1 = ring_a[j], ring_a[j + 1]
            b0, b1 = ring_b[j], ring_b[j + 1]
            triangulos.append((a0, a1, b0))
            triangulos.append((a1, b1, b0))
            tramo_por_triangulo.extend([tramo, tramo])

    return {
        "vertices": np.array(vertices),
        "triangulos": np.array(triangulos),
        "tramo_por_triangulo": tramo_por_triangulo,
        "x_frontera": longitud_existente,
    }


def relacion_aspecto(ancho: float, alto: float, longitud: float) -> tuple[float, float, float]:
    """Proporciones (x, y, z), normalizadas para el `aspectratio` de la
    escena 3D (el eje más largo siempre vale 1.0).

    Ancho y alto se mantienen a escala real entre sí (para que, por ejemplo,
    una labor de 2.75×2.75 se vea más "cuadrada" que una de 1.77×1.10). El
    avance (eje x) se comprime logarítmicamente respecto al tamaño de la
    sección: crece con la longitud real (dos labores con distinto avance se
    ven visiblemente distintas), pero sin volverse una línea inmanejable
    para avances de decenas de metros con secciones de ~1-3 m.

    Se normaliza por el componente máximo para que la cámara (eye fijo) dé
    un encuadre consistente sin importar las dimensiones absolutas de la
    labor — solo importan las proporciones relativas entre ancho/alto/avance.
    """
    escala_seccion = max(ancho, alto, 1e-6)
    ratio_x = escala_seccion * (1.0 + np.log1p(longitud / escala_seccion))
    ratio_y, ratio_z = ancho, alto
    maximo = max(ratio_x, ratio_y, ratio_z, 1e-6)
    return ratio_x / maximo, ratio_y / maximo, ratio_z / maximo
