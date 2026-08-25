"""Malla de perforación 2D (posiciones de cada taladro en la cara del
frente), para visualizar y exportar el patrón de un corte quemado con las
5 zonas estándar de un round de voladura: arranque, ayuda, subayuda,
contorno (hastiales/corona) y arrastre (zapatera).

Es una PLANTILLA PARAMÉTRICA — un patrón clásico de corte quemado (burn
cut) escalado y rotado según la sección real de la labor (ancho, alto,
forma_seccion) — no un diseño optimizado a medida (no considera carga
específica por taladro, tiempos de encendido ni condiciones de roca más
allá del criterio general que ya existe en `core.voladura.
taladros_desde_roca`). El objetivo es una malla dimensionalmente coherente
y reconocible por un perforista — imitando software de diseño de mallas
tipo JKSimBlast/XSiteBlast/DIMAP en la FORMA de calcular y mostrar
distancias — no un cálculo certificado ni el criterio de campo real de
ninguna OTS en particular (ver `core.models.LaborMinera.tipo_roca` para el
mismo disclaimer aplicado a N.° de taladros).

Burden de las zonas en anillo del corte quemado (arranque/ayuda/subayuda)
— método de Holmberg (Holmberg, 1982; ver también Persson, Holmberg & Lee,
"Rock Blasting and Explosives Engineering", y la tabla numérica del "cuele
de cuatro secciones" reproducida en Jimeno, "Manual de Perforación y
Voladura de Rocas", IGME) para un corte de barrenos paralelos:
  - Sección 1 (arranque): con taladros de alivio de diámetro Ø agrupados,
    el diámetro equivalente del vacío es De = Ø × √n_alivio, y el burden
    del primer anillo es B1 = 1.5 × De.
  - Secciones siguientes (ayuda, subayuda, ...): cada anillo abre contra
    el "vacío" que deja el cuadrado/rombo de la sección anterior, cuyo
    lado es a(n-1) = B(n-1) × √2 — por eso B(n) = 1.5 × a(n-1) =
    1.5×√2 × B(n-1) ≈ 2.12 × B(n-1). Verificado contra la tabla numérica
    de referencia (en múltiplos de Ø): B1=1.50Ø, lado1=2.12Ø, B2=3.18Ø,
    lado2=4.50Ø, B3=6.75Ø, lado3=9.54Ø, B4=14.31Ø — cada valor es 1.5× o
    √2× el anterior, tal como esta fórmula predice.

Burden de contorno y arrastre — estas dos zonas ya no son parte del corte
(no abren contra un vacío previo, sino que definen el perfil final y el
piso de la labor), así que la progresión geométrica de Holmberg no aplica
ahí. Se escalan en cambio con los factores de seguridad (Fs) de Ojeda
(2003), "Nueva teoría del burden" (IV CONEINGEMMET 2003) — la fórmula
completa de Ojeda (B = Ø×(PoD/(Fs×σr×RQD)+1)) requiere datos que esta app
no pide todavía (presión de detonación del explosivo, resistencia a
compresión de la roca, RQD) y su reconstrucción a partir de fuentes
secundarias no pasó una verificación dimensional de confianza — por eso NO
se implementa esa fórmula absoluta. Lo que sí se reutiliza, porque es
verificable y consistente, es la tabla de Fs por zona que esa misma fuente
reporta — más Fs = burden más ajustado (más cerca del vacío), menos Fs =
burden más amplio (zona de producción): arranque=6, ayuda=5, subayuda=4,
contorno=3, arrastre=2. El burden de contorno/arrastre se escala desde B1
(arranque) proporcionalmente al cociente de factores:
B_zona = B1 × (Fs_arranque / Fs_zona).

Categorías de taladro:
  - "alivio": taladros sin carga, agrupados en el centro.
  - "arranque" / "ayuda" / "subayuda": anillos concéntricos de taladros
    cargados alrededor de los alivios, alternando cuadrado → rombo
    (rotado 45°) → cuadrado, con burden creciente según la progresión de
    Holmberg (B(n) = 1.5×√2 × B(n-1)).
  - "contorno": taladros a lo largo de hastiales y corona (perfil real de
    la sección), con un margen hacia adentro = burden de esa zona.
  - "arrastre": taladros a lo largo del piso (zapatera) — repartidos por
    longitud de arco a lo largo del contorno CERRADO (incluye el tramo del
    piso, que de otro modo casi no tiene vértices propios en el perfil) y
    clasificados por debajo de un umbral de altura.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from core.geometry import perfil_seccion

FACTOR_BURDEN_HOLMBERG = 1.5  # B1 = FACTOR_BURDEN_HOLMBERG × diámetro equivalente del vacío

# Factores de seguridad (Fs) por zona — Ojeda (2003), "Nueva teoría del
# burden" (IV CONEINGEMMET). El burden de cada zona es proporcional al
# inverso de su Fs respecto al de arranque (ver docstring del módulo).
FACTOR_SEGURIDAD_ZONA = {
    "arranque": 6.0,
    "ayuda": 5.0,
    "subayuda": 4.0,
    "contorno": 3.0,
    "arrastre": 2.0,
}
ZONAS_ANILLO = ("arranque", "ayuda", "subayuda")  # zonas en anillos concéntricos, en orden
UMBRAL_ARRASTRE_FRACCION_ALTO = 0.2  # puntos del perfil con z < este × alto → arrastre (zapatera)

# Retardo de iniciación por zona (ms) — secuencia corta creciente desde el
# arranque hacia el contorno/arrastre, siguiendo el orden estándar de
# disparo de un round (el arranque rompe primero, hacia el vacío central;
# el contorno y el arrastre salen al final). Son valores de referencia
# (equivalentes a una numeración de periodos de detonador no eléctrico
# tipo Nonel/Exel), no un diseño de timing certificado — el usuario debe
# ajustar según el sistema de iniciación real que use. None = no detona
# (taladro de alivio, sin carga).
RETARDO_MS_POR_ZONA: dict[str, float | None] = {
    "alivio": None,
    "arranque": 0.0,
    "ayuda": 25.0,
    "subayuda": 50.0,
    "contorno": 75.0,
    "arrastre": 100.0,
}


@dataclass
class PosicionTaladro:
    y: float
    z: float
    categoria: str  # "alivio" | "arranque" | "ayuda" | "subayuda" | "contorno" | "arrastre"
    anillo: int = 0  # 1, 2, 3 para las zonas en anillo (arranque/ayuda/subayuda); 0 en las demás
    retardo_ms: float | None = None  # None = no detona (alivio); ver RETARDO_MS_POR_ZONA


@dataclass
class ZonaInfo:
    """Distancias de una zona de la malla — análogo a las cotas y tablas
    que muestra un software de diseño de malla tipo JKSimBlast/DIMAP."""
    zona: str
    n_taladros: int
    burden_mm: float
    lado_mm: float | None = None  # solo aplica a zonas en anillo (cuadrado/rombo)
    forma: str | None = None  # "Cuadrado" | "Rombo" | None


def burden_inicial_m(
    diametro_alivio_mm: float, n_alivio: int, factor: float = FACTOR_BURDEN_HOLMBERG,
) -> float:
    """Burden (m) del anillo de arranque, por la regla empírica de
    Holmberg: B1 = factor × (Ø_alivio × √n_alivio). Si no hay taladros de
    alivio (n_alivio <= 0), no hay vacío que abra el corte — se devuelve
    directamente `diametro_alivio_mm` convertido a metros como aproximación
    mínima razonable, para que la malla siga siendo dibujable."""
    if n_alivio <= 0 or diametro_alivio_mm <= 0:
        return max(diametro_alivio_mm, 1.0) / 1000.0
    diametro_equivalente_mm = diametro_alivio_mm * math.sqrt(n_alivio)
    return (factor * diametro_equivalente_mm) / 1000.0


def burden_zona_m(burden_arranque_m: float, zona: str) -> float:
    """Burden (m) de `zona`, escalado desde el burden de arranque según
    los factores de seguridad de Ojeda (2003) — ver docstring del módulo.
    Solo aplica a "contorno"/"arrastre"; las zonas en anillo del corte usan
    `burden_siguiente_seccion_m` (progresión de Holmberg)."""
    fs_zona = FACTOR_SEGURIDAD_ZONA[zona]
    fs_arranque = FACTOR_SEGURIDAD_ZONA["arranque"]
    return burden_arranque_m * (fs_arranque / fs_zona)


def burden_siguiente_seccion_m(
    burden_anterior_m: float, factor: float = FACTOR_BURDEN_HOLMBERG,
) -> float:
    """Burden (m) de la siguiente sección del corte quemado, por el método
    de Holmberg: la sección anterior deja un vacío cuadrado de lado
    a = burden_anterior × √2 (diagonal del cuadrado/rombo de taladros), y
    la nueva sección se calcula igual que la primera pero contra ese vacío:
    B(n) = factor × a = factor × √2 × burden_anterior — ver docstring del
    módulo para la verificación numérica contra la tabla de referencia."""
    lado_anterior_m = burden_anterior_m * math.sqrt(2.0)
    return factor * lado_anterior_m


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


def _zonas_en_anillo(
    taladros_cargados: int, centro: tuple[float, float], burden_arranque_m: float,
) -> tuple[list[PosicionTaladro], list[ZonaInfo], int]:
    """Reparte hasta 4 taladros en cada una de las zonas en anillo
    (arranque → ayuda → subayuda, alternando cuadrado/rombo), con burden
    creciente según la progresión de Holmberg (`burden_siguiente_seccion_m`
    — cada sección abre contra el vacío que deja la anterior). Devuelve las
    posiciones, la info de cada zona usada y el N.° de taladros restantes
    (para contorno/arrastre)."""
    posiciones: list[PosicionTaladro] = []
    zonas_info: list[ZonaInfo] = []
    restantes = taladros_cargados
    burden = burden_arranque_m
    for i, zona in enumerate(ZONAS_ANILLO):
        if i > 0:
            burden = burden_siguiente_seccion_m(burden)
        n_zona = min(4, restantes)
        if n_zona <= 0:
            break
        es_rombo = i % 2 == 1
        puntos = _anillo_cuadrado(centro, burden, 45.0 if es_rombo else 0.0)[:n_zona]
        posiciones.extend(
            PosicionTaladro(y, z, zona, anillo=i + 1) for y, z in puntos
        )
        zonas_info.append(ZonaInfo(
            zona=zona.capitalize(),
            n_taladros=n_zona,
            burden_mm=burden * 1000.0,
            lado_mm=burden * math.sqrt(2.0) * 1000.0,
            forma="Rombo" if es_rombo else "Cuadrado",
        ))
        restantes -= n_zona
    return posiciones, zonas_info, restantes


def _puntos_contorno(
    forma: str | None, ancho: float, alto: float, n_puntos: int, margen: float,
) -> list[tuple[float, float]]:
    """`n_puntos` equiespaciados por LONGITUD DE ARCO a lo largo del
    contorno real y CERRADO de la sección (incluye el tramo del piso, entre
    el último y el primer vértice del perfil — `perfil_seccion` no trae
    vértices propios ahí, así que un reparto por índice de vértice casi
    nunca cae en el piso y deja la zona de arrastre sin taladros;
    repartir por longitud de arco sí le da al piso su parte proporcional
    del perímetro). Cada punto se desplaza `margen` metros hacia el centro
    a lo largo de su propia dirección radial — un offset POR PUNTO, no un
    factor de escala global: con un factor global el desplazamiento real
    depende de qué tan lejos del centroide esté cada punto, y los del piso
    (los más alejados en secciones altas) se movían mucho más que `margen`,
    subiendo por encima del umbral de arrastre y dejando la zapatera sin
    taladros. No es el offset exacto de una curva paralela, pero sí respeta
    la distancia pedida en cada punto."""
    if n_puntos <= 0:
        return []
    perfil = perfil_seccion(forma, ancho, alto, n_arco=max(24, n_puntos * 2))
    centro_y = float(np.mean(perfil[:, 0]))
    centro_z = float(np.mean(perfil[:, 1]))

    cerrado = np.vstack([perfil, perfil[:1]])  # incluye el tramo de piso (último → primero)
    segmentos = np.diff(cerrado, axis=0)
    longitudes = np.hypot(segmentos[:, 0], segmentos[:, 1])
    perimetro = float(longitudes.sum())
    if perimetro <= 0:
        return []
    acumulado = np.concatenate([[0.0], np.cumsum(longitudes)])

    puntos = []
    for k in range(n_puntos):
        s = (perimetro * k) / n_puntos
        idx = min(int(np.searchsorted(acumulado, s, side="right") - 1), len(cerrado) - 2)
        s0, s1 = acumulado[idx], acumulado[idx + 1]
        t = (s - s0) / (s1 - s0) if s1 > s0 else 0.0
        y = cerrado[idx, 0] + t * (cerrado[idx + 1, 0] - cerrado[idx, 0])
        z = cerrado[idx, 1] + t * (cerrado[idx + 1, 1] - cerrado[idx, 1])
        dy, dz = y - centro_y, z - centro_z
        distancia = math.hypot(dy, dz)
        factor = max(0.0, (distancia - margen) / distancia) if distancia > 0 else 0.0
        puntos.append((centro_y + dy * factor, centro_z + dz * factor))
    return puntos


def generar_malla_perforacion(
    ancho: float,
    alto: float,
    taladros_cargados: int,
    taladros_alivio: int,
    diametro_barreno_mm: float,
    diametro_alivio_mm: float | None = None,
    forma_seccion: str | None = None,
) -> tuple[list[PosicionTaladro], list[ZonaInfo]]:
    """Genera la malla completa: alivios al centro, zonas en anillo
    (arranque→ayuda→subayuda) y el resto de taladros cargados repartidos
    entre contorno (hastiales/corona) y arrastre (zapatera) sobre el
    perfil real de la sección. `diametro_alivio_mm` por defecto usa el
    mismo diámetro que `diametro_barreno_mm` — en perforación manual
    (Jack Leg) sin broca de rimado especial, los taladros de alivio suelen
    perforarse con la misma broca, solo se dejan sin cargar; si se usa una
    broca de mayor diámetro para el alivio, indícalo aquí.

    Devuelve (posiciones, zonas_info) — `zonas_info` trae el burden (y el
    lado, para las zonas en anillo) de cada zona en milímetros, para
    mostrarlas como cotas y tabla (igual que un software de diseño de malla)."""
    if diametro_alivio_mm is None:
        diametro_alivio_mm = diametro_barreno_mm

    centro = (0.0, alto / 2.0)
    burden_arranque = burden_inicial_m(diametro_alivio_mm, taladros_alivio)
    # el clúster de alivios nunca debe extenderse más allá de la mitad del
    # burden de arranque — si no, los alivios de los extremos del clúster
    # quedarían más cerca de los taladros de arranque que lo que el propio
    # burden calculado asume, y podrían llegar a traslaparse físicamente
    # con ellos (ver test_validar_traslapes_*).
    espaciado_alivio = min((diametro_alivio_mm * 2.5) / 1000.0, burden_arranque * 0.5)

    posiciones = _cluster_alivio(taladros_alivio, centro, espaciado_alivio)

    posiciones_anillo, zonas_info, restantes = _zonas_en_anillo(taladros_cargados, centro, burden_arranque)
    posiciones += posiciones_anillo

    margen_contorno_m = burden_zona_m(burden_arranque, "contorno")
    umbral_z = UMBRAL_ARRASTRE_FRACCION_ALTO * alto
    n_contorno = n_arrastre = 0
    for y, z in _puntos_contorno(forma_seccion, ancho, alto, restantes, margen_contorno_m):
        if z < umbral_z:
            posiciones.append(PosicionTaladro(y, z, "arrastre", anillo=0))
            n_arrastre += 1
        else:
            posiciones.append(PosicionTaladro(y, z, "contorno", anillo=0))
            n_contorno += 1
    if n_contorno:
        zonas_info.append(ZonaInfo(zona="Contorno", n_taladros=n_contorno, burden_mm=margen_contorno_m * 1000.0))
    if n_arrastre:
        burden_arrastre = burden_zona_m(burden_arranque, "arrastre")
        zonas_info.append(ZonaInfo(zona="Arrastre", n_taladros=n_arrastre, burden_mm=burden_arrastre * 1000.0))

    for taladro in posiciones:
        taladro.retardo_ms = RETARDO_MS_POR_ZONA[taladro.categoria]

    return posiciones, zonas_info


@dataclass
class PasoDisparo:
    orden: int
    categoria: str
    anillo: int
    retardo_ms: float


def secuencia_disparo(taladros: list[PosicionTaladro]) -> list[PasoDisparo]:
    """Orden de disparo de los taladros CARGADOS (excluye alivio, que no
    detona), ordenados por retardo ascendente — igual criterio que
    `RETARDO_MS_POR_ZONA` (ver docstring del módulo)."""
    cargados = [t for t in taladros if t.retardo_ms is not None]
    cargados.sort(key=lambda t: t.retardo_ms)
    return [
        PasoDisparo(orden=i + 1, categoria=t.categoria, anillo=t.anillo, retardo_ms=t.retardo_ms)
        for i, t in enumerate(cargados)
    ]


@dataclass
class ConflictoTaladro:
    """Dos taladros perforados demasiado cerca uno del otro — nunca se
    corrige en silencio, solo se detecta y reporta (igual criterio que
    cualquier validación de traslapes: la decisión de ajustar el diseño
    queda del lado del usuario)."""
    indice_a: int
    indice_b: int
    categoria_a: str
    categoria_b: str
    distancia_m: float
    minimo_requerido_m: float


def validar_traslapes(
    taladros: list[PosicionTaladro], diametro_barreno_mm: float, margen_m: float = 0.01,
) -> list[ConflictoTaladro]:
    """Detecta pares de taladros perforados más cerca entre sí que
    `2×radio_barreno + margen_m` — un traslape físico entre barrenos, o un
    espaciamiento tan ajustado que no cabría el explosivo/taco con
    seguridad. `margen_m` por defecto es deliberadamente pequeño (1 cm):
    en un corte quemado los anillos consecutivos de arranque/ayuda/
    subayuda están, por diseño, muy cerca entre sí (eso es justamente lo
    que mide el burden) — un margen grande generaría falsos positivos
    permanentes en cualquier malla bien diseñada. No modifica la malla;
    el diseño se ajusta manualmente (cambiando N.° de taladros, sección o
    parámetros de burden) si hay conflictos."""
    radio_m = (diametro_barreno_mm / 1000.0) / 2.0
    minimo_requerido_m = 2 * radio_m + margen_m
    conflictos: list[ConflictoTaladro] = []
    for i in range(len(taladros)):
        for j in range(i + 1, len(taladros)):
            a, b = taladros[i], taladros[j]
            distancia_m = math.hypot(a.y - b.y, a.z - b.z)
            if distancia_m < minimo_requerido_m:
                conflictos.append(ConflictoTaladro(
                    indice_a=i, indice_b=j, categoria_a=a.categoria, categoria_b=b.categoria,
                    distancia_m=distancia_m, minimo_requerido_m=minimo_requerido_m,
                ))
    return conflictos
