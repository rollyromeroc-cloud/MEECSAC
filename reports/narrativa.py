"""Generación de texto narrativo del informe (introducción, programa de
actividades, secuencia operativa) — parametrizado a partir de las labores
que el usuario haya cargado, siguiendo la redacción típica de un informe
técnico de perforación y voladura.

Python puro (sin Streamlit ni python-docx), para poder testearse aislado.
"""

from __future__ import annotations

from collections import Counter

from core.constants import ORDEN_ETAPAS, PROPOSITO_TIPO_LABOR
from core.models import DatosGenerales, LaborMinera, ResultadoVoladura


def _moda(valores: list) -> object | None:
    """Valor más frecuente de una lista (para "el equipo/diámetro típico")."""
    valores = [v for v in valores if v not in (None, "", 0)]
    if not valores:
        return None
    return Counter(valores).most_common(1)[0][0]


def _lista_en_espanol(items: list[str]) -> str:
    items = [i for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " y " + items[-1]


def parrafos_introduccion(
    labores: list[LaborMinera],
    resultados: list[ResultadoVoladura],
    datos: DatosGenerales,
) -> list[str]:
    """Párrafos de la sección INTRODUCCIÓN."""
    if not labores:
        return []

    nombre = datos.nombre_concesion or "la concesión minera"
    tipos_presentes = _lista_en_espanol(sorted({l.tipo for l in labores}))

    p1 = (
        f"Las labores mineras se ejecutarán en el área de {nombre}, dentro del "
        f"área autorizada para el desarrollo de actividades mineras "
        f"subterráneas. El programa contempla labores de "
        f"{_lista_en_espanol(sorted({l.etapa.lower() for l in labores}))}, "
        f"mediante la ejecución de {tipos_presentes}, conforme al programa de "
        f"avance proyectado."
    )

    equipo_tipico = _moda([l.equipo_perforacion for l in labores])
    diametro_tipico = _moda([l.diametro_barreno_mm for l in labores])
    longitud_tipica = _moda([l.longitud_barreno_pies for l in labores])
    secciones = "; ".join(
        f"{l.nombre} presenta una sección de {l.ancho_m:.2f} m × {l.alto_m:.2f} m"
        for l in labores
    )
    p2 = (
        f"Las labores se ejecutarán mediante perforación y voladura "
        f"convencional, empleando equipos tipo {equipo_tipico or 'Jackleg'}, "
        f"barrenos de {diametro_tipico or 36:.0f} mm de diámetro y "
        f"{longitud_tipica or 4:.0f} pies de longitud, de acuerdo con las "
        f"características geomecánicas del macizo rocoso. {secciones}."
    )

    avance_total = sum(l.avance_proyectado_m for l in labores)
    tonelaje_total = sum(r.tonelaje_total_tm for r in resultados)
    p3 = (
        f"El programa de minado considera el avance progresivo de las "
        f"labores subterráneas, manteniendo coherencia entre el volumen de "
        f"material removido, el consumo de explosivos y el programa de "
        f"explotación proyectado, alcanzando un avance total de "
        f"{avance_total:,.2f} m y un tonelaje programado de "
        f"{tonelaje_total:,.2f} TM para el periodo de {datos.periodo_meses} "
        f"meses."
    )

    explosivos = _lista_en_espanol(
        sorted({l.tipo_explosivo_1 for l in labores} | {l.tipo_explosivo_2 for l in labores})
    )
    fulminantes = _lista_en_espanol(sorted({l.tipo_fulminante for l in labores}))
    p4 = (
        f"Para las operaciones de perforación y voladura se emplearán "
        f"{explosivos}. Como accesorios de voladura se utilizarán "
        f"{fulminantes} y mecha de seguridad, conforme al diseño de "
        f"perforación establecido para cada labor minera."
    )

    p5 = (
        "En materia de Seguridad y Salud Ocupacional, el operador minero "
        "dará cumplimiento a las disposiciones establecidas en el "
        "Reglamento de Seguridad y Salud Ocupacional en Minería, aprobado "
        "mediante Decreto Supremo N.° 024-2016-EM y sus modificatorias, "
        "especialmente en lo referente a perforación, voladura, "
        "manipulación, transporte y almacenamiento de explosivos y "
        "accesorios de voladura, con la finalidad de salvaguardar la "
        "integridad de los trabajadores y garantizar el desarrollo seguro "
        "de las operaciones mineras subterráneas."
    )

    return [p1, p2, p3, p4, p5]


_INTRO_ETAPA = {
    "Desarrollo": (
        "En esta etapa se ejecutan las labores de desarrollo, las cuales "
        "permiten el acceso al cuerpo mineralizado, la comunicación entre "
        "niveles y la apertura de nuevos frentes de trabajo."
    ),
    "Preparación": (
        "En esta etapa se ejecutan las labores de preparación, orientadas a "
        "acondicionar el yacimiento para su explotación."
    ),
    "Explotación": (
        "En esta etapa se ejecuta la explotación del mineral económicamente "
        "explotable."
    ),
}


def programa_actividades(
    labores: list[LaborMinera], resultados: list[ResultadoVoladura]
) -> list[tuple[str, str, list[str]]]:
    """Devuelve, por etapa presente (en orden Desarrollo→Preparación→
    Explotación), una tupla (etapa, párrafo introductorio, lista de
    oraciones por labor)."""
    por_etapa: dict[str, list[tuple[LaborMinera, ResultadoVoladura]]] = {}
    for labor, resultado in zip(labores, resultados):
        por_etapa.setdefault(labor.etapa, []).append((labor, resultado))

    secciones = []
    for etapa in ORDEN_ETAPAS:
        pares = por_etapa.get(etapa)
        if not pares:
            continue
        bullets = []
        for labor, resultado in pares:
            proposito = PROPOSITO_TIPO_LABOR.get(labor.tipo, "de acuerdo con el diseño de perforación adoptado")
            bullets.append(
                f"{labor.nombre}: Se proyecta un avance de {labor.avance_proyectado_m:,.2f} m, "
                f"con sección de {labor.ancho_m:.2f} m × {labor.alto_m:.2f} m "
                f"({resultado.area_m2:.2f} m²), {proposito}."
            )
        intro = _INTRO_ETAPA.get(etapa, "")
        secciones.append((etapa, intro, bullets))

    # etapas fuera del orden estándar (por si el usuario usó un texto libre)
    for etapa, pares in por_etapa.items():
        if etapa in ORDEN_ETAPAS:
            continue
        bullets = [
            f"{labor.nombre}: Se proyecta un avance de {labor.avance_proyectado_m:,.2f} m, "
            f"con sección de {labor.ancho_m:.2f} m × {labor.alto_m:.2f} m ({resultado.area_m2:.2f} m²)."
            for labor, resultado in pares
        ]
        secciones.append((etapa, "", bullets))

    return secciones


def secuencia_operativa(
    labores: list[LaborMinera], resultados: list[ResultadoVoladura], datos: DatosGenerales
) -> list[str]:
    """Líneas de la sección 'Secuencia Operativa': una por etapa + cierre."""
    por_etapa: dict[str, list[str]] = {}
    for labor in labores:
        por_etapa.setdefault(labor.etapa, []).append(labor.nombre)

    lineas = []
    for etapa in ORDEN_ETAPAS:
        nombres = por_etapa.get(etapa)
        if nombres:
            lineas.append(f"{etapa}: {_lista_en_espanol(nombres)}.")
    for etapa, nombres in por_etapa.items():
        if etapa not in ORDEN_ETAPAS:
            lineas.append(f"{etapa}: {_lista_en_espanol(nombres)}.")

    avance_total = sum(l.avance_proyectado_m for l in labores)
    tonelaje_total = sum(r.tonelaje_total_tm for r in resultados)
    lineas.append(
        f"El programa ha sido elaborado manteniendo coherencia entre el "
        f"avance de las labores, el volumen de material removido y el "
        f"consumo de explosivos, considerando un avance total proyectado de "
        f"{avance_total:,.2f} m y un tonelaje total programado de "
        f"{tonelaje_total:,.2f} TM para el periodo de {datos.periodo_meses} meses."
    )
    return lineas
