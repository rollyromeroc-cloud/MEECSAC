from core.models import DatosGenerales, LaborMinera
from core.voladura import calcular_programa
from reports.narrativa import parrafos_introduccion, programa_actividades, secuencia_operativa


def _labores_ejemplo():
    return [
        LaborMinera(
            nombre="Galería Nivel 2", tipo="Galería", etapa="Desarrollo",
            ancho_m=1.77, alto_m=1.10, avance_proyectado_m=66.0,
        ),
        LaborMinera(
            nombre="Estocada Derecha", tipo="Estocada", etapa="Preparación",
            ancho_m=2.10, alto_m=1.40, avance_proyectado_m=66.0,
        ),
        LaborMinera(
            nombre="Cortada Frente", tipo="Cortada", etapa="Explotación",
            ancho_m=2.20, alto_m=1.55, avance_proyectado_m=66.0, destino_material="Mineral",
        ),
    ]


def test_parrafos_introduccion_no_vacio_y_menciona_labores():
    labores = _labores_ejemplo()
    resultados = calcular_programa(labores)
    datos = DatosGenerales(nombre_concesion='la concesión "Prueba"', periodo_meses=6)
    parrafos = parrafos_introduccion(labores, resultados, datos)
    assert len(parrafos) == 5
    texto = " ".join(parrafos)
    assert "Prueba" in texto
    assert "Galería" in texto
    assert "6 meses" in texto


def test_programa_actividades_agrupa_por_etapa_en_orden():
    labores = _labores_ejemplo()
    resultados = calcular_programa(labores)
    secciones = programa_actividades(labores, resultados)
    etapas = [s[0] for s in secciones]
    assert etapas == ["Desarrollo", "Preparación", "Explotación"]
    # cada sección tiene exactamente una labor de ejemplo
    for etapa, _intro, bullets in secciones:
        assert len(bullets) == 1


def test_programa_actividades_incluye_exploracion_primero():
    labores = _labores_ejemplo() + [
        LaborMinera(
            nombre="Chimenea Exploratoria", tipo="Chimenea", etapa="Exploración",
            ancho_m=1.20, alto_m=1.20, avance_proyectado_m=20.0,
        ),
    ]
    resultados = calcular_programa(labores)
    secciones = programa_actividades(labores, resultados)
    etapas = [s[0] for s in secciones]
    assert etapas == ["Exploración", "Desarrollo", "Preparación", "Explotación"]
    intro_exploracion = next(intro for etapa, intro, _ in secciones if etapa == "Exploración")
    assert intro_exploracion  # tiene texto introductorio propio, no queda vacío


def test_secuencia_operativa_incluye_totales():
    labores = _labores_ejemplo()
    resultados = calcular_programa(labores)
    datos = DatosGenerales(periodo_meses=6)
    lineas = secuencia_operativa(labores, resultados, datos)
    assert any("Desarrollo:" in l for l in lineas)
    assert any("198.00 m" in l for l in lineas)  # 66*3 avance total
