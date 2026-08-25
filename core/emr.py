"""EMR (Equivalente en Masa de Referencia — dinamita al 60%) y distancias
mínimas de seguridad por la tabla de valores de K, para la sección de
seguridad de polvorín.

Factores de equivalencia DIN 60% y tabla de K reproducidos de la plantilla
de cálculo de EMR de referencia del usuario (misma tabla que usa la
industria de explosivos en el Perú) — es una PLANTILLA PARAMÉTRICA para
apoyar el cálculo, no un dictamen certificado: el usuario debe verificarla
contra el reglamento vigente (D.S. N.° 024-2016-EM y modificatorias) antes
de tomar una decisión operativa (mismo criterio de disclaimer que
`core.polvorin`).

Dos tipos de factor de equivalencia:
  - "indirecto": kg equivalente por kg de producto → Resultado = cantidad × factor
    (explosivos, medidos en kg).
  - "directo": unidades (pza/m) equivalentes a 1 kg de referencia →
    Resultado = cantidad / factor (accesorios, medidos en pza o m).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FactorDIN60:
    tipo: str  # "indirecto" | "directo"
    factor: float
    unidad: str  # "kg" | "pza" | "m"


# Curado desde la tabla completa de referencia (85 ítems, incluye explosivos
# primarios/secundarios de uso no minero) a los productos relevantes para
# voladura subterránea/superficial de mina — mismo alcance de productos que
# ya usa `pages.1_Voladura` (tipo_explosivo_1/2, cartuchos) y
# `core.polvorin` (polvorines de Explosivos/Accesorios).
FACTORES_DIN60: dict[str, FactorDIN60] = {
    # Explosivos (factor "indirecto", kg equivalente por kg de producto)
    "Dinamita gelatina 80%": FactorDIN60("indirecto", 0.787, "kg"),
    "Dinamita gelatina 60%": FactorDIN60("indirecto", 0.755, "kg"),
    "Dinamita gelatina 40%": FactorDIN60("indirecto", 0.574, "kg"),
    "ANFO": FactorDIN60("indirecto", 0.608, "kg"),
    "ANFO pesado (ANFO:Emulsión 60:40)": FactorDIN60("indirecto", 0.559, "kg"),
    "ANFO pesado aluminizado (ANFO:Emulsión:Al 51:35:15)": FactorDIN60("indirecto", 0.986, "kg"),
    "Nitrato de amonio / sales o fertilizantes explosivos": FactorDIN60("indirecto", 0.608, "kg"),
    "Emulsión o hidrogel encartuchada": FactorDIN60("indirecto", 0.713, "kg"),
    "Emulsión o hidrogel a granel sensibilizada": FactorDIN60("indirecto", 0.520, "kg"),
    "Emulsión o hidrogel a granel no sensibilizada": FactorDIN60("indirecto", 0.479, "kg"),
    "Pentolita / booster (PETN:TNT 50:50)": FactorDIN60("indirecto", 0.841, "kg"),
    "Explosivo permisible o de seguridad": FactorDIN60("indirecto", 0.621, "kg"),
    # Accesorios (factor "directo", unidades o metros por kg equivalente)
    "Fulminante común N.° 6": FactorDIN60("directo", 1978, "pza"),
    "Fulminante común N.° 8": FactorDIN60("directo", 1416, "pza"),
    "Fulminante común N.° 10": FactorDIN60("directo", 1295, "pza"),
    "Fulminante común N.° 12": FactorDIN60("directo", 997, "pza"),
    "Detonador eléctrico instantáneo N.° 2": FactorDIN60("directo", 5231, "pza"),
    "Detonador eléctrico instantáneo N.° 4": FactorDIN60("directo", 2902, "pza"),
    "Mecha de seguridad": FactorDIN60("directo", 587, "m"),
    "Cordón de ignición / mecha rápida": FactorDIN60("directo", 251, "m"),
    "Conector para cordón de ignición": FactorDIN60("directo", 1978, "pza"),
    "Cordón detonante (5 g PETN/m)": FactorDIN60("directo", 196, "m"),
    "Cordón detonante (15 g PETN/m)": FactorDIN60("directo", 65, "m"),
}


def equivalente_din60_kg(nombre_item: str, cantidad: float) -> float:
    """kg equivalente de dinamita al 60% de `cantidad` unidades de
    `nombre_item` — multiplica o divide según el tipo de factor (ver
    docstring del módulo). 0.0 si `nombre_item` no está en la tabla."""
    factor = FACTORES_DIN60.get(nombre_item)
    if factor is None or cantidad <= 0:
        return 0.0
    if factor.tipo == "indirecto":
        return cantidad * factor.factor
    return cantidad / factor.factor if factor.factor > 0 else 0.0


def emr_total_kg(items: list[tuple[str, float]]) -> float:
    """EMR total (kg equivalente dinamita 60%) de una lista de
    (nombre_item, cantidad) — el "W" de la fórmula de distancia de
    seguridad (D = K × ∛W)."""
    return sum(equivalente_din60_kg(nombre, cantidad) for nombre, cantidad in items)


def raiz_cubica_emr(emr_kg: float) -> float:
    return emr_kg ** (1.0 / 3.0) if emr_kg > 0 else 0.0


# Tabla N.° 2 - Valores de K, por tipo de instalación — las claves coinciden
# con `core.constants.TIPOS_PUNTO_RIESGO`, salvo "Polvorín [barricado] a
# otro polvorín" (comparación polvorín-a-polvorín, fuera de alcance: la app
# compara cada polvorín contra puntos de riesgo, no polvorines entre sí).
TABLA_K_SUPERFICIAL: dict[str, float] = {
    "Local de riesgo / poblado": 1.25,
    "Instalación administrativa": 3.0,
    "Tránsito público (vía)": 6.0,
    "Líneas férreas": 12.0,
    "Edificio habitado": 15.0,
    "Agentes externos de riesgo": 16.0,
}
TABLA_K_SUBTERRANEO: dict[str, float] = {
    "Local de riesgo / poblado": 1.25,
    "Instalación administrativa": 3.0,
    "Tránsito público (vía)": 4.0,
    "Líneas férreas": 6.0,
    "Edificio habitado": 8.0,
    # "Agentes externos de riesgo" no está definido en la tabla de
    # referencia para polvorín subterráneo — sin sugerencia automática ahí.
}


def distancia_seguridad_m(emr_kg: float, k: float) -> tuple[float, float]:
    """(D barricado, D libre) = (K × ∛EMR, 2 × D_barricado) — fórmula de
    distancia mínima de seguridad por cantidad-distancia."""
    d_barricado = k * raiz_cubica_emr(emr_kg)
    return d_barricado, d_barricado * 2.0
