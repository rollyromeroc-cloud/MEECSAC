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
    return _perfil_arco_con_muro(radio, alto_muro, flecha, n_arco)


def perfil_baul(ancho: float, alto: float, n_arco: int = 24) -> np.ndarray:
    """Contorno 2D (y, z) de una sección tipo baúl: muros verticales rectos
    (hastiales rectos) garantizados hasta al menos la mitad de la altura, y
    arco semi-elíptico hasta la corona en la mitad superior — a diferencia
    de `perfil_herradura`, el arco nunca ocupa más de la mitad de la altura
    (nunca "come" todo el muro), sea cual sea la relación ancho/alto."""
    radio = ancho / 2.0
    flecha = min(radio, alto * 0.5)
    alto_muro = alto - flecha
    return _perfil_arco_con_muro(radio, alto_muro, flecha, n_arco)


def perfil_herradura_pura(ancho: float, alto: float, n_arco: int = 24) -> np.ndarray:
    """Contorno 2D (y, z) de una sección tipo herradura SIN hastiales
    rectos: el arco semi-elíptico ocupa toda la altura desde el piso, sin
    tramo de muro vertical (a diferencia de `perfil_baul`)."""
    radio = ancho / 2.0
    return _perfil_arco_con_muro(radio, 0.0, alto, n_arco)


def _perfil_arco_con_muro(radio: float, alto_muro: float, flecha: float, n_arco: int) -> np.ndarray:
    puntos = [(-radio, 0.0), (-radio, alto_muro)]
    angulos = np.linspace(np.pi, 0.0, n_arco)
    for ang in angulos:
        y = radio * np.cos(ang)
        z = alto_muro + flecha * np.sin(ang)
        puntos.append((y, z))
    puntos.append((radio, 0.0))
    return np.array(puntos)


def perfil_trapezoidal(ancho: float, alto: float, factor_techo: float = 0.6) -> np.ndarray:
    """Contorno 2D (y, z) de una sección trapezoidal: piso de ancho `ancho`,
    techo plano centrado más angosto (`ancho * factor_techo`) y hastiales
    rectos inclinados — típico de labores pequeñas sin sostenimiento en
    arco. Sin discretizar (4 vértices, aristas rectas)."""
    radio_piso = ancho / 2.0
    radio_techo = (ancho * factor_techo) / 2.0
    return np.array([
        (-radio_piso, 0.0),
        (-radio_techo, alto),
        (radio_techo, alto),
        (radio_piso, 0.0),
    ])


def _perfil_por_forma(forma: str | None, ancho: float, alto: float, n_arco: int) -> np.ndarray:
    """Despacha el contorno 2D según `forma` (uno de FORMAS_SECCION). Si
    `forma` no coincide con ninguna opción explícita (p. ej. None, para
    compatibilidad con llamadas que no la especifican), usa la heurística
    original de `perfil_herradura`."""
    if forma == "Circular":
        return perfil_circular(ancho, n_arco=n_arco)
    if forma == "Trapezoidal":
        return perfil_trapezoidal(ancho, alto)
    if forma == "Herradura (sin hastiales rectos)":
        return perfil_herradura_pura(ancho, alto, n_arco=n_arco)
    if forma == "Baúl (hastiales rectos)":
        return perfil_baul(ancho, alto, n_arco=n_arco)
    return perfil_herradura(ancho, alto, n_arco=n_arco)


def perimetro_seccion(forma: str | None, ancho: float, alto: float, n_arco: int = 24) -> float:
    """Perímetro (m) del contorno de la sección transversal — usado en el
    diseño de malla de perforación, N.° T = (Perímetro / dt) + (Coef. roca ×
    Área), ver `core.voladura.taladros_desde_roca`."""
    perfil_cerrado = _cerrar_anillo(_perfil_por_forma(forma, ancho, alto, n_arco))
    segmentos = np.diff(perfil_cerrado, axis=0)
    return float(np.sum(np.hypot(segmentos[:, 0], segmentos[:, 1])))


def _cerrar_anillo(anillo: np.ndarray) -> np.ndarray:
    """Repite el primer punto al final para que, al dibujarse como línea,
    el anillo quede cerrado (incluye el piso — la arista que conecta
    piso-derecha con piso-izquierda) en vez de terminar abierto en el
    último punto del perfil."""
    return np.vstack([anillo, anillo[0]])


def malla_tunel(
    ancho: float,
    alto: float,
    longitud: float,
    n_anillos: int = 14,
    n_arco: int = 24,
    x_inicio: float = 0.0,
    forma: str | None = None,
) -> dict:
    """Anillos (secciones transversales) y líneas longitudinales de un tramo
    de túnel extruido a lo largo del eje X (de `x_inicio` a
    `x_inicio + longitud`), listos para dibujarse como wireframe 3D.

    `x_inicio` permite encadenar dos tramos (p. ej. longitud existente y
    avance proyectado) sin recalcular el perfil. `forma` selecciona la
    sección transversal (ver `FORMAS_SECCION`); si se omite, se usa la
    heurística de `perfil_herradura`.

    Devuelve un dict con:
      - "anillos": lista de arrays (n_perfil, 3) con columnas (x, y, z)
      - "longitudinales": lista de arrays (n_anillos, 3) en puntos clave del
        perfil (piso izquierdo, corona, piso derecho)
      - "perfil": el contorno 2D usado (y, z)
    """
    perfil = _perfil_por_forma(forma, ancho, alto, n_arco)
    xs = np.linspace(x_inicio, x_inicio + longitud, n_anillos)

    anillos = [
        _cerrar_anillo(np.column_stack([np.full(len(perfil), x), perfil[:, 0], perfil[:, 1]]))
        for x in xs
    ]

    indices_clave = [0, len(perfil) // 2, len(perfil) - 1]
    longitudinales = [
        np.column_stack([xs, np.full(len(xs), perfil[idx, 0]), np.full(len(xs), perfil[idx, 1])])
        for idx in indices_clave
    ]

    return {"anillos": anillos, "longitudinales": longitudinales, "perfil": perfil}


def malla_tunel_pique(
    diametro: float,
    longitud: float,
    n_anillos: int = 14,
    n_arco: int = 24,
    z_inicio: float = 0.0,
) -> dict:
    """Análogo de `malla_tunel` para Pique/Chimenea: anillos circulares
    extruidos a lo largo del eje LOCAL Z (de `z_inicio` a
    `z_inicio + longitud`), listos para dibujarse como wireframe 3D.
    Mismo formato de retorno que `malla_tunel` (columnas x, y, z)."""
    perfil = perfil_circular(diametro, n_arco=n_arco)
    zs = np.linspace(z_inicio, z_inicio + longitud, n_anillos)

    anillos = [
        _cerrar_anillo(np.column_stack([perfil[:, 0], perfil[:, 1], np.full(len(perfil), z)]))
        for z in zs
    ]

    indices_clave = [0, len(perfil) // 4, len(perfil) // 2]
    longitudinales = [
        np.column_stack([np.full(len(zs), perfil[idx, 0]), np.full(len(zs), perfil[idx, 1]), zs])
        for idx in indices_clave
    ]

    return {"anillos": anillos, "longitudinales": longitudinales, "perfil": perfil}


def _posiciones_mensuales(
    longitud_existente: float, avance_proyectado: float, n_meses: int,
    avance_mensual: list[float] | None,
) -> np.ndarray:
    """Posiciones acumuladas (a lo largo del eje de extrusión) de cada
    anillo mensual. Si se pasa `avance_mensual` (una cifra de avance real
    por mes, no necesariamente uniforme — p. ej. un programa [0.3, 0.3,
    0.5, 0.5, 1.0, 1.0]), se usan esas cifras tal cual; si no, se asume
    avance uniforme (avance_proyectado / n_meses por mes)."""
    if avance_mensual:
        return longitud_existente + np.cumsum(avance_mensual)
    if n_meses <= 0 or avance_proyectado <= 0:
        return np.array([])
    avance_mes = avance_proyectado / n_meses
    return longitud_existente + np.arange(1, n_meses + 1) * avance_mes


def anillos_de_avance_mensual(
    ancho: float, alto: float, longitud_existente: float, avance_proyectado: float,
    n_meses: int, forma: str | None = None, n_arco: int = 24,
    avance_mensual: list[float] | None = None,
) -> list[np.ndarray]:
    """Un anillo cerrado (ver `_cerrar_anillo`) por cada mes de programa —
    para marcar la programación mensual sobre el esquema. Por defecto
    asume avance uniforme (avance_proyectado / n_meses por mes); si se pasa
    `avance_mensual` (una cifra de avance real por cada mes, no
    necesariamente uniforme), se usan esas posiciones acumuladas reales en
    su lugar. Los anillos quedan en x = longitud_existente + avance
    acumulado (el último coincide con el final del avance proyectado).
    Devuelve lista vacía si no hay avance ni meses que marcar."""
    posiciones = _posiciones_mensuales(longitud_existente, avance_proyectado, n_meses, avance_mensual)
    if len(posiciones) == 0:
        return []
    perfil = _perfil_por_forma(forma, ancho, alto, n_arco)
    return [
        _cerrar_anillo(np.column_stack([np.full(len(perfil), x), perfil[:, 0], perfil[:, 1]]))
        for x in posiciones
    ]


def anillos_de_avance_mensual_pique(
    diametro: float, longitud_existente: float, avance_proyectado: float,
    n_meses: int, n_arco: int = 24, avance_mensual: list[float] | None = None,
) -> list[np.ndarray]:
    """Análogo de `anillos_de_avance_mensual` para Pique/Chimenea (eje
    local Z en vez de X)."""
    posiciones = _posiciones_mensuales(longitud_existente, avance_proyectado, n_meses, avance_mensual)
    if len(posiciones) == 0:
        return []
    perfil = perfil_circular(diametro, n_arco=n_arco)
    return [
        _cerrar_anillo(np.column_stack([
            perfil[:, 0], perfil[:, 1], np.full(len(perfil), z),
        ]))
        for z in posiciones
    ]


def _franja_triangulos(idx_a: list[int], idx_b: list[int], n_perfil: int) -> list[tuple[int, int, int]]:
    """Triangula la franja entre dos anillos consecutivos de un perfil
    CERRADO por wraparound de índices (la arista `n_perfil-1 -> 0` cierra
    el contorno, generando el piso en la misma pasada que muros/arco, sin
    duplicar ningún vértice). Orden de vértices elegido para que las
    normales queden salientes."""
    triangulos = []
    for j in range(n_perfil):
        jp1 = (j + 1) % n_perfil
        a0, a1 = idx_a[j], idx_a[jp1]
        b0, b1 = idx_b[j], idx_b[jp1]
        triangulos.append((a0, b0, a1))
        triangulos.append((a1, b0, b1))
    return triangulos


def _tapa_abanico(
    anillo_idx: list[int], vertices: list[tuple[float, float, float]], normal_saliente: np.ndarray,
) -> list[tuple[int, int, int]]:
    """Triangulación en abanico de una tapa (anillo de un perfil convexo,
    sin índice duplicado) — válida sin dependencias extra porque tanto el
    contorno herradura cerrado con piso plano como el círculo son convexos.
    Corrige el sentido de cada triángulo contra `normal_saliente`."""
    v0 = anillo_idx[0]
    p0 = np.array(vertices[v0])
    triangulos = []
    for i in range(1, len(anillo_idx) - 1):
        v1, v2 = anillo_idx[i], anillo_idx[i + 1]
        p1, p2 = np.array(vertices[v1]), np.array(vertices[v2])
        normal = np.cross(p1 - p0, p2 - p0)
        if np.dot(normal, normal_saliente) < 0:
            v1, v2 = v2, v1
        triangulos.append((v0, v1, v2))
    return triangulos


def _malla_solida_generica(
    perfil: np.ndarray,
    longitud_existente: float,
    avance_proyectado: float,
    n_anillos_existente: int,
    n_anillos_proyectado: int,
    colocar_3d,
) -> dict:
    """Vértices y triángulos de un sólido CERRADO (piso + muros/arco + 2
    tapas en los extremos) para el tramo existente y el proyectado, con una
    etiqueta de tramo por triángulo para poder colorearlos distinto.

    `colocar_3d(perfil_punto, coord_extrusion) -> (x, y, z)` ubica un punto
    2D del perfil en el eje de extrusión que corresponda (X para galerías,
    Z para piques/chimeneas), permitiendo compartir toda esta lógica entre
    ambas orientaciones.

    Devuelve un dict con:
      - "vertices": array (N, 3) de todos los vértices
      - "triangulos": array (M, 3) de índices de vértice por triángulo
      - "tramo_por_triangulo": lista de "existente"/"proyectado" (largo M)
      - "frontera_local": coordenada de extrusión donde termina lo
        existente y empieza lo proyectado
    """
    n_perfil = len(perfil)

    tramos_coord = []
    if longitud_existente > 0:
        tramos_coord.append(("existente", np.linspace(0.0, longitud_existente, max(n_anillos_existente, 2))))
    coord_proy = np.linspace(
        longitud_existente, longitud_existente + avance_proyectado, max(n_anillos_proyectado, 2)
    )
    if tramos_coord:
        coord_proy = coord_proy[1:]  # evita duplicar el anillo de empalme
    tramos_coord.append(("proyectado", coord_proy))

    vertices: list[tuple[float, float, float]] = []
    anillos_idx: list[list[int]] = []
    anillo_tramo: list[str] = []
    for nombre_tramo, coords in tramos_coord:
        for coord in coords:
            idx_inicio = len(vertices)
            vertices.extend(colocar_3d(punto, coord) for punto in perfil)
            anillos_idx.append(list(range(idx_inicio, idx_inicio + n_perfil)))
            anillo_tramo.append(nombre_tramo)

    triangulos: list[tuple[int, int, int]] = []
    tramo_por_triangulo: list[str] = []
    for r in range(len(anillos_idx) - 1):
        ring_a, ring_b = anillos_idx[r], anillos_idx[r + 1]
        # el tramo del segmento es el del anillo de llegada (evita marcar el
        # anillo de empalme, que pertenece a "existente", como "proyectado")
        tramo = anillo_tramo[r + 1]
        franja = _franja_triangulos(ring_a, ring_b, n_perfil)
        triangulos.extend(franja)
        tramo_por_triangulo.extend([tramo] * len(franja))

    normal_inicio = np.array(colocar_3d((0.0, 0.0), -1.0)) - np.array(colocar_3d((0.0, 0.0), 0.0))
    triangulos_tapa_inicio = _tapa_abanico(anillos_idx[0], vertices, normal_inicio)
    triangulos.extend(triangulos_tapa_inicio)
    tramo_por_triangulo.extend([anillo_tramo[0]] * len(triangulos_tapa_inicio))

    normal_fin = -normal_inicio
    triangulos_tapa_fin = _tapa_abanico(anillos_idx[-1], vertices, normal_fin)
    triangulos.extend(triangulos_tapa_fin)
    tramo_por_triangulo.extend([anillo_tramo[-1]] * len(triangulos_tapa_fin))

    return {
        "vertices": np.array(vertices),
        "triangulos": np.array(triangulos),
        "tramo_por_triangulo": tramo_por_triangulo,
        "frontera_local": longitud_existente,
    }


def malla_solida_tunel(
    ancho: float,
    alto: float,
    longitud_existente: float,
    avance_proyectado: float,
    n_anillos_existente: int = 8,
    n_anillos_proyectado: int = 14,
    n_arco: int = 24,
    forma: str | None = None,
) -> dict:
    """Vértices y triángulos de un sólido cerrado (piso + muros/arco + tapas
    en el portal y en la punta del avance proyectado) para el tramo
    existente y el proyectado. `forma` selecciona la sección transversal
    (ver `FORMAS_SECCION`); si se omite, se usa la heurística de
    `perfil_herradura`. Ver `_malla_solida_generica` para el formato de
    retorno."""
    perfil = _perfil_por_forma(forma, ancho, alto, n_arco)

    def colocar_3d(punto: tuple[float, float], x: float) -> tuple[float, float, float]:
        y, z = punto
        return (x, y, z)

    return _malla_solida_generica(
        perfil, longitud_existente, avance_proyectado,
        n_anillos_existente, n_anillos_proyectado, colocar_3d,
    )


def perfil_circular(diametro: float, n_arco: int = 24) -> np.ndarray:
    """Contorno 2D (x, y) de una sección circular, `n_arco` puntos
    equiespaciados sin punto de cierre duplicado (misma convención que
    `perfil_herradura`: cerrar el anillo es responsabilidad de la malla)."""
    radio = diametro / 2.0
    angulos = np.linspace(0.0, 2 * np.pi, n_arco, endpoint=False)
    return np.column_stack([radio * np.cos(angulos), radio * np.sin(angulos)])


def malla_solida_pique(
    diametro: float,
    longitud_existente: float,
    avance_proyectado: float,
    n_anillos_existente: int = 4,
    n_anillos_proyectado: int = 6,
    n_arco: int = 24,
) -> dict:
    """Análogo cilíndrico de `malla_solida_tunel` para Pique/Chimenea:
    sección circular (`perfil_circular`) extruida a lo largo del eje LOCAL
    +Z (no +X) — un pique/chimenea es una labor vertical/subvertical.
    `diametro` reutiliza `labor.ancho_m`; `alto_m` no se usa para estos
    tipos. Mismo formato de retorno que `malla_solida_tunel` (incluye
    "frontera_local", aquí la coordenada Z donde termina lo existente)."""
    perfil = perfil_circular(diametro, n_arco=n_arco)

    def colocar_3d(punto: tuple[float, float], z: float) -> tuple[float, float, float]:
        x, y = punto
        return (x, y, z)

    return _malla_solida_generica(
        perfil, longitud_existente, avance_proyectado,
        n_anillos_existente, n_anillos_proyectado, colocar_3d,
    )


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
