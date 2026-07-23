"""Valores por defecto y catálogos usados en los formularios.

Estos son puntos de partida editables por el usuario en cada labor/polvorín,
no verdades regulatorias fijas. En particular, las distancias mínimas de
seguridad del módulo de polvorín NO se hardcodean aquí: deben verificarse
contra el reglamento vigente (D.S. N.° 024-2016-EM y modificatorias) y
capturarse a mano en la UI.
"""

from __future__ import annotations

PIE_A_METROS = 0.3048

TIPOS_LABOR = [
    "Galería",
    "Cortada",
    "Estocada",
    "Rampa",
    "Pique",
    "Chimenea",
    "Tajo",
]

# Labores de orientación vertical/subvertical (afecta cómo se interpreta
# "longitud existente"/"avance": altura en vez de longitud horizontal).
LABORES_VERTICALES = {"Pique", "Chimenea"}

TIPOS_ROCA = ["Suave", "Intermedia", "Dura", "Muy dura"]

# Peso específico típico (TM/m³) — referencial, editable por labor.
DENSIDAD_DESMONTE_DEFAULT = 2.70
DENSIDAD_MINERAL_DEFAULT = 3.00

DESTINOS_MATERIAL = ["Desmonte", "Mineral"]

# Explosivos de referencia (cartucho 7/8" x 7", ~0.08 kg c/u) — el peso por
# cartucho es editable porque depende del explosivo y el proveedor.
TIPOS_EXPLOSIVO_DEFAULT = ["Dinamita semigelatina", "Emulsión encartuchada grado 5000"]
PESO_CARTUCHO_DEFAULT_KG = 0.08
DISTRIBUCION_EXPLOSIVO_DEFAULT = (40, 60)  # % tipo 1, % tipo 2

DIAMETRO_BARRENO_DEFAULT_MM = 36
LONGITUD_BARRENO_DEFAULT_PIES = 4

TIPOS_FULMINANTE = ["Fulminante común N.° 08", "Fulminante eléctrico", "Detonador no eléctrico (NONEL)"]

# Mecha de seguridad por taladro = longitud de barreno + tramo de encendido.
TRAMO_ENCENDIDO_MECHA_PIES = 1

TIPOS_CORTE = ["Corte en V", "Corte quemado (burn cut)", "Corte en cuña", "Corte cilíndrico"]

EQUIPOS_PERFORACION = ["Jack Leg", "Jumbo", "Stoper", "Manual"]

# Tipos de punto de riesgo para el módulo de polvorín (referencia de los
# planos de ubicación revisados: distancias teóricas vs. reales).
TIPOS_PUNTO_RIESGO = [
    "Local de riesgo / poblado",
    "Instalación administrativa",
    "Tránsito público (vía)",
    "Líneas férreas",
    "Edificio habitado",
    "Agentes externos de riesgo",
]

ZONA_UTM_DEFAULT = 18
HEMISFERIO_DEFAULT = "S"
