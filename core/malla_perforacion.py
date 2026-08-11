"""Malla de perforación 2D (posiciones de cada taladro en la cara del
frente), para visualizar y exportar el patrón de un corte quemado en
cuadrado/rombo expandido alrededor de los alivios centrales.

Es una PLANTILLA PARAMÉTRICA — un patrón clásico de corte quemado (burn
cut) escalado y rotado según la sección real de la labor (ancho, alto,
forma_seccion) — no un diseño optimizado a medida (no considera carga
específica por taladro, tiempos de encendido ni condiciones de roca más
allá del criterio general que ya existe en `core.voladura.
taladros_desde_roca`). El objetivo es una malla dimensionalmente coherente
y reconocible por un perforista — imitando software de diseño de mallas
tipo JKSimBlast/XSiteBlast en la FORMA de calcular distancias — no un
cálculo certificado ni el criterio de campo real de ninguna OTS en
particular (ver `core.models.LaborMinera.tipo_roca` para el mismo
disclaimer aplicado a N.° de taladros).

El burden del primer anillo de arranque se calcula con la regla empírica
de Holmberg (Holmberg, 1982; ver también Persson, Holmberg & Lee, "Rock
Blasting and Explosives Engineering"): para un corte con taladros de
alivio de diámetro Ø agrupados, el diámetro equivalente del vacío es
De = Ø × √n_alivio, y el burden máximo práctico del primer anillo es
B1 = 1.5 × De. Los anillos siguientes (cuadrado → rombo → cuadrado...)
crecen en progresión B(i) = B1 × √2^(i-1) — la progresión estándar de un
corte en espiral cuadrado, donde cada anillo mantiene la misma proporción
burden/lado que el anterior, solo rotado 45°.

Categorías de taladro:
  - "alivio": taladros sin carga, agrupados en el centro — dan espacio
    libre para que rompa el corte.
  - "arranque": anillos concéntricos de taladros cargados alrededor de los
    alivios, alternando cuadrado → rombo (rotado 45°) → cuadrado → ...
  - "contorno": el resto de taladros cargados, distribuidos a lo largo del
    perfil real de la sección (ver `core.geometry.perfil_seccion`), con un
    pequeño margen hacia adentro desde la pared.

No se modela la zapatera (piso) como categoría aparte — sus taladros
quedan incluidos en "contorno".
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from core.geometry import perfil_seccion

MARGEN_CONTORNO_DEFAULT_M = 0.10
FACTOR_BURDEN_HOLMBERG = 1.5  # B1 = FACTOR_BURDEN_HOLMBERG × diámetro equivalente del vacío
FACTOR_EXPANSION_ANILLO = math.sqrt(2.0)  # progresión clásica cuadrado→rombo


@dataclass
class PosicionTaladro:
    y: float
    z: float
    categoria: str  # "alivio" | "arranque" | "contorno"
    anillo: int = 0  # 0 = alivio; 1, 2, 3... = anillo de arranque (0 si es contorno)


@dataclass
class AnilloInfo:
    """Distancias de un anillo de arranque — análogo a las cotas que
    muestra un software de diseño de malla tipo JKSimBlast/XSiteBlast."""
    anillo: int
    forma: str  # "Cuadrado" | "Rombo"
    n_taladros: int
    burden_mm: float  # distancia del centro del corte a cada taladro del anillo
    lado_mm: float  # distancia entre dos taladros adyacentes del mismo anillo


def burden_inicial_m(
    diametro_alivio_mm: float, n_alivio: int, factor: float = FACTOR_BURDEN_HOLMBERG,
) -> float:
    """Burden (m) del primer anillo de arranque, por la regla empírica de
    Holmberg: B1 = factor × (Ø_alivio × √n_alivio). Si no hay taladros de
    alivio (n_alivio <= 0), no hay vacío que abra el corte — se devuelve
    directamente `diametro_alivio_mm` convertido a metros como aproximación
    mínima razonable, para que la malla siga siendo dibujable."""
    if n_alivio <= 0 or diametro_alivio_mm <= 0:
        return max(diametro_alivio_mm, 1.0) / 1000.0
    diametro_equivalente_mm = diametro_alivio_mm * math.sqrt(n_alivio)
    return (factor * diametro_equivalente_mm) / 1000.0


def _cluster_alivio(n: int, centro: tuple[float, float], espaciado: float) -> list[PosicionTaladro]:
    """Agrupa los `n` taladros de alivio en un clúster pequeño y compacto
    alrededor de `centro` — sin carga, solo dan espacio libre al corte."""
    cy, cz = centro
    if n <= 0:
        return []
    if n == 1:
        offsets = [(0.0, 0.0)]
    elif n == 2:
        offsets = [(-espaciado / 2, 0.0), (espaciado / 2, 0.0)]
    elif n == 3:
        offsets = [(0.0, espaciado / 2), (-espaciado / 2, -espaciado / 2), (espaciado / 2, -espaciado / 2)]
    else:
        # cuadrado para los primeros 4; cualquier excedente se apila al centro
        # (caso raro — un diseño real no pondría más de 4 alivios juntos).
        offsets = [
            (-espaciado / 2, -espaciado / 2), (espaciado / 2, -espaciado / 2),
            (espaciado / 2, espaciado / 2), (-espaciado / 2, espaciado / 2),
        ]
        offsets += [(0.0, 0.0)] * (n - 4)
    return [PosicionTaladro(cy + dy, cz + dz, "alivio", anillo=0) for dy, dz in offsets[:n]]


def _anillo_cuadrado(centro: tuple[float, float], radio: float, rotacion_deg: float) -> list[tuple[float, float]]:
    """4 puntos de un cuadrado (o rombo, si `rotacion_deg`=45) de
    semidiagonal `radio` alrededor de `centro`."""
    cy, cz = centro
    puntos = []
    for k in range(4):
        ang = math.radians(rotacion_deg + 90 * k)
        puntos.append((cy + radio * math.cos(ang), cz + radio * math.sin(ang)))
    return puntos


def _anillos_arranque(
    n_taladros: int, centro: tuple[float, float], radio_inicial: float,
) -> tuple[list[PosicionTaladro], list[AnilloInfo]]:
    """Distribuye `n_taladros` en anillos de 4 (cuadrado, rombo, cuadrado...)
    con burden creciente en progresión √2 (ver docstring del módulo) — el
    excedente que no completa un anillo de 4 se reparte en un anillo final
    con ese mismo radio. Devuelve las posiciones y, por separado, las
    distancias de cada anillo (burden y lado) en milímetros."""
    posiciones: list[PosicionTaladro] = []
    anillos_info: list[AnilloInfo] = []
    restantes = n_taladros
    anillo = 1
    radio = radio_inicial
    while restantes > 0:
        es_rombo = anillo % 2 == 0
        rotacion = 45.0 if es_rombo else 0.0
        n_en_anillo = min(4, restantes)
        puntos = _anillo_cuadrado(centro, radio, rotacion)[:n_en_anillo]
        posiciones.extend(
            PosicionTaladro(y, z, "arranque", anillo=anillo) for y, z in puntos
        )
        anillos_info.append(AnilloInfo(
            anillo=anillo,
            forma="Rombo" if es_rombo else "Cuadrado",
            n_taladros=n_en_anillo,
            burden_mm=radio * 1000.0,
            lado_mm=radio * math.sqrt(2.0) * 1000.0,
        ))
        restantes -= n_en_anillo
        radio *= FACTOR_EXPANSION_ANILLO
        anillo += 1
    return posiciones, anillos_info


def _puntos_contorno(
    forma: str | None, ancho: float, alto: float, n_puntos: int, margen: float,
) -> list[tuple[float, float]]:
    """`n_puntos` equiespaciados a lo largo del perfil real de la sección,
    desplazados `margen` metros hacia el centro (aproximación: escala el
    perfil respecto a su propio centro geométrico, no un offset geométrico
    exacto de curva paralela — suficiente para un margen pequeño)."""
    if n_puntos <= 0:
        return []
    perfil = perfil_seccion(forma, ancho, alto, n_arco=max(24, n_puntos))
    centro_y = float(np.mean(perfil[:, 0]))
    centro_z = float(np.mean(perfil[:, 1]))
    radio_medio = float(np.mean(np.hypot(perfil[:, 0] - centro_y, perfil[:, 1] - centro_z)))
    factor = max(0.0, (radio_medio - margen) / radio_medio) if radio_medio > 0 else 1.0

    n_perfil = len(perfil)
    indices = np.linspace(0, n_perfil, n_puntos, endpoint=False).astype(int) % n_perfil
    puntos = []
    for idx in indices:
        y, z = perfil[idx]
        puntos.append((
            centro_y + (y - centro_y) * factor,
            centro_z + (z - centro_z) * factor,
        ))
    return puntos


def generar_malla_perforacion(
    ancho: float,
    alto: float,
    taladros_cargados: int,
    taladros_alivio: int,
    diametro_barreno_mm: float,
    diametro_alivio_mm: float | None = None,
    forma_seccion: str | None = None,
    margen_contorno_m: float = MARGEN_CONTORNO_DEFAULT_M,
) -> tuple[list[PosicionTaladro], list[AnilloInfo]]:
    """Genera la malla completa: alivios al centro, anillos de arranque
    (cuadrado→rombo expandido, burden real vía `burden_inicial_m`) y el
    resto de taladros cargados repartidos en el contorno real de la
    sección. `diametro_alivio_mm` por defecto usa el mismo diámetro que
    `diametro_barreno_mm` — en perforación manual (Jack Leg) sin broca de
    rimado especial, los taladros de alivio suelen perforarse con la misma
    broca, solo se dejan sin cargar; si se usa una broca de mayor diámetro
    para el alivio, indícalo aquí.

    Devuelve (posiciones, anillos_info) — `anillos_info` trae el burden y
    el lado de cada anillo de arranque en milímetros, para mostrarlos como
    cotas (igual que un software de diseño de malla)."""
    if diametro_alivio_mm is None:
        diametro_alivio_mm = diametro_barreno_mm

    centro = (0.0, alto / 2.0)
    radio_inicial = burden_inicial_m(diametro_alivio_mm, taladros_alivio)
    espaciado_alivio = (diametro_alivio_mm * 2.5) / 1000.0

    posiciones = _cluster_alivio(taladros_alivio, centro, espaciado_alivio)

    n_arranque = min(taladros_cargados, 8)
    n_contorno = taladros_cargados - n_arranque
    posiciones_arranque, anillos_info = _anillos_arranque(n_arranque, centro, radio_inicial)
    posiciones += posiciones_arranque
    posiciones += [
        PosicionTaladro(y, z, "contorno", anillo=0)
        for y, z in _puntos_contorno(forma_seccion, ancho, alto, n_contorno, margen_contorno_m)
    ]
    return posiciones, anillos_info
