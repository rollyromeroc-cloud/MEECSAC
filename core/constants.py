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
    "Subnivel",
    "Ventana",
    "Rampa",
    "Inclinado",
    "Pique",
    "Chimenea",
    "Tajeo",
]

# Labores de orientación vertical/subvertical (afecta cómo se interpreta
# "longitud existente"/"avance": altura en vez de longitud horizontal).
LABORES_VERTICALES = {"Pique", "Chimenea"}

# Forma de la sección transversal (solo labores horizontales — Pique/Chimenea
# siempre usan sección circular vertical, ver core.geometry.malla_solida_pique).
FORMAS_SECCION = [
    "Baúl (hastiales rectos)",
    "Herradura (sin hastiales rectos)",
    "Trapezoidal",
    "Circular",
]

TIPOS_ROCA = ["Suave", "Media", "Dura"]

# Diseño de malla de perforación por tipo de roca — N.° T = (P / dt) + (C × S),
# donde P = perímetro de la sección (m), S = área de la sección (m²), dt =
# distancia entre taladros (m) y C = coeficiente de roca. Rango de dt en
# metros (se usa el punto medio como valor por defecto editable).
DISTANCIA_TALADROS_RANGO_M = {
    "Dura": (0.35, 0.40),
    "Media": (0.45, 0.50),
    "Suave": (0.55, 0.60),
}
COEFICIENTE_ROCA = {
    "Dura": 2.0,
    "Media": 1.5,
    "Suave": 1.0,
}

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

# Descripciones genéricas por tipo de labor, para la memoria descriptiva
# (introducción, programa de actividades, especificaciones técnicas) del
# reporte Word — inspiradas en la redacción típica de un informe técnico de
# perforación y voladura, parametrizadas para cualquier conjunto de labores.
DESCRIPCION_TIPO_LABOR = {
    "Galería": (
        "Son labores mineras de desarrollo de carácter horizontal, destinadas "
        "al acceso, reconocimiento y seguimiento del cuerpo mineralizado, así "
        "como a facilitar el transporte de mineral, desmonte, personal, "
        "materiales y equipos."
    ),
    "Cortada": (
        "Son labores mineras horizontales ejecutadas para interceptar el "
        "cuerpo mineralizado, permitiendo el acceso directo a las zonas de "
        "explotación y el avance de los frentes de producción."
    ),
    "Estocada": (
        "Son labores mineras horizontales de preparación, ejecutadas "
        "lateralmente desde una labor principal, que permiten ampliar los "
        "frentes de trabajo y el acceso a la estructura mineralizada."
    ),
    "Subnivel": (
        "Son labores mineras horizontales de preparación, ejecutadas entre "
        "niveles principales con una separación vertical reducida, destinadas "
        "a delimitar y preparar el cuerpo mineralizado como base para la "
        "perforación y voladura en los métodos de explotación por subniveles."
    ),
    "Ventana": (
        "Son labores mineras horizontales de corta longitud, ejecutadas para "
        "conectar dos labores existentes, facilitando la ventilación, el "
        "acceso de personal y la evacuación de material entre ellas."
    ),
    "Rampa": (
        "Son labores mineras de desarrollo con pendiente controlada, "
        "destinadas a comunicar niveles y permitir el tránsito de equipos, "
        "personal y material entre ellos."
    ),
    "Inclinado": (
        "Son labores mineras desarrolladas con una inclinación pronunciada y "
        "constante siguiendo la estructura mineralizada, destinadas a "
        "comunicar niveles y facilitar el transporte de mineral, desmonte, "
        "personal y materiales mediante sistemas de izaje o rieles."
    ),
    "Pique": (
        "Son labores mineras de desarrollo vertical o subvertical destinadas "
        "a comunicar diferentes niveles de trabajo, facilitar el tránsito del "
        "personal, mejorar la ventilación y permitir el transporte de "
        "materiales y mineral."
    ),
    "Chimenea": (
        "Son labores mineras de desarrollo vertical o subvertical destinadas "
        "a mejorar la ventilación, la comunicación entre niveles y la "
        "seguridad operacional de la unidad minera."
    ),
    "Tajeo": (
        "Es la labor minera de explotación subterránea mediante la cual se "
        "extrae el mineral económicamente explotable siguiendo la geometría "
        "del cuerpo mineralizado, según el método de explotación adoptado."
    ),
}

# Frase corta de propósito, usada en "Se ha programado el desarrollo de
# LABOR, con sección A × B, [propósito]" y en el listado del Programa de
# Actividades por etapa.
PROPOSITO_TIPO_LABOR = {
    "Galería": (
        "permitiendo la continuidad de las labores de preparación y "
        "explotación, así como la comunicación entre los diferentes frentes "
        "de trabajo"
    ),
    "Cortada": (
        "permitiendo la continuidad de las labores de explotación y la "
        "recuperación del mineral económicamente explotable"
    ),
    "Estocada": "permitiendo ampliar los frentes de trabajo y el acceso a la estructura mineralizada",
    "Subnivel": "permitiendo delimitar y preparar el cuerpo mineralizado para su posterior explotación por subniveles",
    "Ventana": "facilitando la ventilación, el acceso de personal y la evacuación de material entre las labores conectadas",
    "Rampa": "permitiendo el tránsito de equipos y personal entre niveles",
    "Inclinado": "permitiendo la comunicación entre niveles y el transporte de mineral, desmonte, personal y materiales siguiendo la estructura mineralizada",
    "Pique": "contribuyendo a mejorar la comunicación entre niveles y la operatividad de la mina",
    "Chimenea": "destinada a mejorar la ventilación, la comunicación y la seguridad operacional",
    "Tajeo": "permitiendo la extracción del mineral económicamente explotable según el método de explotación adoptado",
}

ACTIVIDADES_CICLICAS = [
    "Perforación y Voladura",
    "Carguío y extracción",
    "Sostenimiento y Limpieza",
    "Desquinche y Relleno",
    "Transporte",
]

ORDEN_ETAPAS = ["Desarrollo", "Preparación", "Explotación"]

# Capacidad maxima por guia de remision segun SUCAMEC, por tipo generico de
# explosivo/accesorio (no por marca comercial). Valores de referencia; ante
# cualquier discrepancia con la guia/permiso vigente, prevalece el documento
# oficial. Mas adelante se ampliara con variantes comerciales (p.ej. FAMESA).
TIPOS_SUCAMEC_GUIAS = [
    {"categoria": "Explosivos", "producto": "Dinamita", "capacidad_por_guia": 575, "unidad": "KG"},
    {"categoria": "Explosivos", "producto": "Emulsión o hidrogel encartuchada", "capacidad_por_guia": 575, "unidad": "KG"},
    {"categoria": "Explosivos", "producto": "ANFO", "capacidad_por_guia": 600, "unidad": "KG"},
    {"categoria": "Accesorios", "producto": "Cordón detonante", "capacidad_por_guia": 30000, "unidad": "M"},
    {"categoria": "Accesorios", "producto": "Detonador de mecha o fulminante común", "capacidad_por_guia": 500000, "unidad": "PZAS"},
    {"categoria": "Accesorios", "producto": "Cordón de ignición", "capacidad_por_guia": 30000, "unidad": "M"},
    {"categoria": "Accesorios", "producto": "Conector para cordón de ignición", "capacidad_por_guia": 80000, "unidad": "PZAS"},
    {"categoria": "Accesorios", "producto": "Detonador no eléctrico", "capacidad_por_guia": 15000, "unidad": "PZAS"},
    {"categoria": "Accesorios", "producto": "Mecha de seguridad", "capacidad_por_guia": 100000, "unidad": "M"},
    {"categoria": "Accesorios", "producto": "Detonador ensamblado", "capacidad_por_guia": 60000, "unidad": "PZAS"},
]

# Texto de unidad tal como aparece en la celda "UNIDADES DE MEDIDA" del
# Formato N.° 23 SUCAMEC (distinto de la abreviatura usada arriba).
UNIDAD_SUCAMEC_TEXTO = {"KG": "KILOGRAMOS", "M": "METROS", "PZAS": "UNIDADES"}

# Plantillas oficiales (modelo ya llenado por el usuario) del Formato N.° 23:
# tipo 1 = FAMESA -> Polvorin (una por categoria, con el origen FAMESA ya
# correcto en cada una); tipo 2 = Polvorin -> Unidad minera. Se usan tal cual
# vienen, solo se reemplazan producto/cantidad/unidades y, en tipo 2, los
# datos del polvorin (origen) y de la concesion (destino).
PLANTILLA_GUIA_TIPO1 = {
    "Explosivos": "Formato gts TIPO 1 FAMESA LIMA EXPLOSIVOS.xlsx",
    "Accesorios": "Formato gts TIPO 1 FAMESA LIMA ACCESORIOS.xlsx",
}
PLANTILLA_GUIA_TIPO2 = "Formato gts TIPO 2.xlsx"
