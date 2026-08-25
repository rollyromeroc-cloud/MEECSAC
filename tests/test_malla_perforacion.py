import math

import pytest

from core.malla_perforacion import (
    FACTOR_BURDEN_HOLMBERG,
    FACTOR_SEGURIDAD_ZONA,
    RETARDO_MS_POR_ZONA,
    PosicionTaladro,
    burden_inicial_m,
    burden_siguiente_seccion_m,
    burden_zona_m,
    generar_malla_perforacion,
    secuencia_disparo,
    validar_traslapes,
)


def test_burden_inicial_regla_de_holmberg():
    # De = 36mm * sqrt(2) = 50.91mm ; B1 = 1.5 * 50.91mm = 76.37mm = 0.07637m
    b1 = burden_inicial_m(diametro_alivio_mm=36.0, n_alivio=2)
    assert b1 == pytest.approx(1.5 * 36.0 * math.sqrt(2) / 1000.0, abs=1e-6)


def test_burden_inicial_sin_alivio_no_falla():
    assert burden_inicial_m(diametro_alivio_mm=36.0, n_alivio=0) > 0


def test_burden_siguiente_seccion_sigue_la_tabla_de_referencia_de_holmberg():
    # Tabla del "cuele de cuatro secciones" (Jimeno, Manual de Perforación y
    # Voladura de Rocas), en múltiplos del diámetro de alivio D:
    # B1=1.50D, B2=3.18D, B3=6.75D, B4=14.31D.
    d = 1.0
    b1 = burden_inicial_m(diametro_alivio_mm=d * 1000.0, n_alivio=1)  # De=D -> B1=1.5D
    b2 = burden_siguiente_seccion_m(b1)
    b3 = burden_siguiente_seccion_m(b2)
    b4 = burden_siguiente_seccion_m(b3)
    assert b1 == pytest.approx(1.50 * d, abs=1e-2)
    assert b2 == pytest.approx(3.18 * d, abs=1e-2)
    assert b3 == pytest.approx(6.75 * d, abs=1e-2)
    assert b4 == pytest.approx(14.31 * d, abs=2e-2)
    # cada sección es 1.5×√2 ≈ 2.12 veces la anterior
    assert b2 / b1 == pytest.approx(1.5 * math.sqrt(2.0))


def test_burden_zona_escala_por_factor_de_seguridad_ojeda():
    b1 = 0.076
    assert burden_zona_m(b1, "arranque") == pytest.approx(b1)
    assert burden_zona_m(b1, "ayuda") == pytest.approx(b1 * 6.0 / 5.0)
    assert burden_zona_m(b1, "subayuda") == pytest.approx(b1 * 6.0 / 4.0)
    assert burden_zona_m(b1, "contorno") == pytest.approx(b1 * 6.0 / 3.0)
    assert burden_zona_m(b1, "arrastre") == pytest.approx(b1 * 6.0 / 2.0)
    # burden creciente a medida que se aleja del arranque (menos Fs = más burden)
    burdens = [burden_zona_m(b1, z) for z in ("arranque", "ayuda", "subayuda", "contorno", "arrastre")]
    assert burdens == sorted(burdens)


def test_genera_el_total_correcto_de_taladros():
    malla, _ = generar_malla_perforacion(
        ancho=1.77, alto=1.10, taladros_cargados=23, taladros_alivio=2,
        diametro_barreno_mm=36.0, forma_seccion="Baúl (hastiales rectos)",
    )
    assert len(malla) == 23 + 2
    n_alivio = sum(1 for t in malla if t.categoria == "alivio")
    n_resto = sum(1 for t in malla if t.categoria != "alivio")
    assert n_alivio == 2
    assert n_resto == 23


def test_asigna_hasta_4_taladros_por_zona_en_anillo_antes_de_contorno():
    malla, zonas = generar_malla_perforacion(
        ancho=2.00, alto=2.00, taladros_cargados=20, taladros_alivio=2,
        diametro_barreno_mm=36.0, forma_seccion="Baúl (hastiales rectos)",
    )
    n_arranque = sum(1 for t in malla if t.categoria == "arranque")
    n_ayuda = sum(1 for t in malla if t.categoria == "ayuda")
    n_subayuda = sum(1 for t in malla if t.categoria == "subayuda")
    n_contorno_arrastre = sum(1 for t in malla if t.categoria in ("contorno", "arrastre"))
    assert n_arranque == 4
    assert n_ayuda == 4
    assert n_subayuda == 4
    assert n_contorno_arrastre == 8  # 20 - 12
    zonas_por_nombre = {z.zona: z for z in zonas}
    assert set(zonas_por_nombre) == {"Arranque", "Ayuda", "Subayuda", "Contorno", "Arrastre"}


def test_pocos_taladros_cargados_solo_arranque():
    malla, zonas = generar_malla_perforacion(
        ancho=1.20, alto=1.20, taladros_cargados=3, taladros_alivio=1,
        diametro_barreno_mm=36.0, forma_seccion="Baúl (hastiales rectos)",
    )
    n_arranque = sum(1 for t in malla if t.categoria == "arranque")
    assert n_arranque == 3
    assert len(zonas) == 1
    assert zonas[0].zona == "Arranque"
    assert zonas[0].n_taladros == 3


def test_alivio_unico_queda_en_el_centro():
    malla, _ = generar_malla_perforacion(
        ancho=1.77, alto=1.10, taladros_cargados=0, taladros_alivio=1,
        diametro_barreno_mm=36.0, forma_seccion="Baúl (hastiales rectos)",
    )
    alivio = next(t for t in malla if t.categoria == "alivio")
    assert alivio.y == pytest.approx(0.0)
    assert alivio.z == pytest.approx(0.55)  # alto / 2


def test_zonas_en_anillo_alternan_cuadrado_y_rombo_con_burden_creciente():
    diametro_barreno = 36.0
    n_alivio = 2
    malla, zonas = generar_malla_perforacion(
        ancho=2.00, alto=2.00, taladros_cargados=12, taladros_alivio=n_alivio,
        diametro_barreno_mm=diametro_barreno, forma_seccion="Baúl (hastiales rectos)",
    )
    assert [z.zona for z in zonas[:3]] == ["Arranque", "Ayuda", "Subayuda"]
    assert [z.forma for z in zonas[:3]] == ["Cuadrado", "Rombo", "Cuadrado"]
    assert [z.n_taladros for z in zonas[:3]] == [4, 4, 4]

    b1_esperado_m = burden_inicial_m(diametro_barreno, n_alivio)
    b2_esperado_m = burden_siguiente_seccion_m(b1_esperado_m)
    b3_esperado_m = burden_siguiente_seccion_m(b2_esperado_m)
    assert zonas[0].burden_mm == pytest.approx(b1_esperado_m * 1000.0)
    # progresión de Holmberg: cada sección abre contra el vacío en diagonal
    # (√2) de la anterior, con el mismo factor 1.5 → B(n) ≈ 2.12 × B(n-1)
    assert zonas[1].burden_mm == pytest.approx(b2_esperado_m * 1000.0)
    assert zonas[1].burden_mm == pytest.approx(zonas[0].burden_mm * 1.5 * math.sqrt(2.0))
    assert zonas[2].burden_mm == pytest.approx(b3_esperado_m * 1000.0)
    assert zonas[0].lado_mm == pytest.approx(zonas[0].burden_mm * math.sqrt(2.0))

    anillo_1 = [t for t in malla if t.categoria == "arranque"]
    anillo_2 = [t for t in malla if t.categoria == "ayuda"]
    centro_z = 1.0
    # anillo 1 (cuadrado, rotación 0°): un punto debe caer sobre el eje y
    # (z == centro) — a diferencia del anillo 2 (rombo, rotado 45°).
    assert any(abs(t.z - centro_z) < 1e-6 for t in anillo_1)
    assert not any(abs(t.z - centro_z) < 1e-6 for t in anillo_2)


def test_diametro_alivio_por_defecto_usa_el_del_barreno():
    _, zonas_a = generar_malla_perforacion(
        ancho=2.00, alto=2.00, taladros_cargados=4, taladros_alivio=2,
        diametro_barreno_mm=36.0, forma_seccion="Baúl (hastiales rectos)",
    )
    _, zonas_b = generar_malla_perforacion(
        ancho=2.00, alto=2.00, taladros_cargados=4, taladros_alivio=2,
        diametro_barreno_mm=36.0, diametro_alivio_mm=36.0, forma_seccion="Baúl (hastiales rectos)",
    )
    assert zonas_a[0].burden_mm == pytest.approx(zonas_b[0].burden_mm)


def test_arrastre_queda_cerca_del_piso_y_contorno_por_encima_del_umbral():
    ancho, alto = 2.20, 1.55
    forma = "Baúl (hastiales rectos)"
    malla, _ = generar_malla_perforacion(
        ancho=ancho, alto=alto, taladros_cargados=24, taladros_alivio=2,
        diametro_barreno_mm=36.0, forma_seccion=forma,
    )
    umbral = 0.2 * alto
    arrastre = [t for t in malla if t.categoria == "arrastre"]
    contorno = [t for t in malla if t.categoria == "contorno"]
    assert arrastre  # con 24 taladros cargados, sobran suficientes para llegar al piso
    assert all(t.z < umbral for t in arrastre)
    assert all(t.z >= umbral for t in contorno)


def test_arrastre_recibe_varios_taladros_no_solo_las_esquinas_del_piso():
    # el piso (zapatera) no tiene vértices propios en `perfil_seccion` (solo
    # sus 2 esquinas) — el reparto por longitud de arco debe darle su parte
    # proporcional del contorno de todos modos, no solo 1-2 taladros fijos.
    malla, _ = generar_malla_perforacion(
        ancho=2.20, alto=1.55, taladros_cargados=24, taladros_alivio=2,
        diametro_barreno_mm=36.0, forma_seccion="Baúl (hastiales rectos)",
    )
    n_arrastre = sum(1 for t in malla if t.categoria == "arrastre")
    assert n_arrastre >= 3


def test_puntos_de_contorno_quedan_dentro_del_perfil_real():
    from core.geometry import perfil_seccion

    ancho, alto = 2.20, 1.55
    forma = "Baúl (hastiales rectos)"
    malla, _ = generar_malla_perforacion(
        ancho=ancho, alto=alto, taladros_cargados=24, taladros_alivio=2,
        diametro_barreno_mm=36.0, forma_seccion=forma,
    )
    perimetro_holes = [t for t in malla if t.categoria in ("contorno", "arrastre")]
    assert perimetro_holes

    perfil = perfil_seccion(forma, ancho, alto)
    centro_y = perfil[:, 0].mean()
    centro_z = perfil[:, 1].mean()
    radio_perfil_max = max(math.hypot(y - centro_y, z - centro_z) for y, z in perfil)

    for t in perimetro_holes:
        radio_taladro = math.hypot(t.y - centro_y, t.z - centro_z)
        assert radio_taladro < radio_perfil_max  # con margen hacia adentro


def test_factor_burden_holmberg_y_tabla_de_seguridad_son_positivos():
    assert FACTOR_BURDEN_HOLMBERG > 0
    assert all(v > 0 for v in FACTOR_SEGURIDAD_ZONA.values())
    # a menor Fs, mayor burden relativo — la tabla debe ser monótona en el
    # orden esperado del round (arranque -> ayuda -> subayuda -> contorno -> arrastre)
    orden = ["arranque", "ayuda", "subayuda", "contorno", "arrastre"]
    valores = [FACTOR_SEGURIDAD_ZONA[z] for z in orden]
    assert valores == sorted(valores, reverse=True)


def test_retardo_asignado_por_zona_alivio_nunca_detona():
    malla, _ = generar_malla_perforacion(
        ancho=1.77, alto=1.10, taladros_cargados=23, taladros_alivio=2,
        diametro_barreno_mm=36.0, forma_seccion="Baúl (hastiales rectos)",
    )
    for t in malla:
        assert t.retardo_ms == RETARDO_MS_POR_ZONA[t.categoria]
    alivios = [t for t in malla if t.categoria == "alivio"]
    assert all(t.retardo_ms is None for t in alivios)
    cargados = [t for t in malla if t.categoria != "alivio"]
    assert all(t.retardo_ms is not None for t in cargados)


def test_secuencia_disparo_ordenada_por_retardo_ascendente_y_excluye_alivio():
    malla, _ = generar_malla_perforacion(
        ancho=1.77, alto=1.10, taladros_cargados=23, taladros_alivio=2,
        diametro_barreno_mm=36.0, forma_seccion="Baúl (hastiales rectos)",
    )
    pasos = secuencia_disparo(malla)
    assert len(pasos) == 23  # excluye los 2 alivios
    assert [p.orden for p in pasos] == list(range(1, 24))
    retardos = [p.retardo_ms for p in pasos]
    assert retardos == sorted(retardos)
    assert pasos[0].categoria == "arranque"  # el arranque siempre dispara primero


def test_validar_traslapes_sin_conflictos_con_alivio_rimado_de_diametro_adecuado():
    # un solo taladro de alivio "rimado" (broca de mayor diámetro, como en
    # la práctica real) da un burden inicial holgado — malla sin conflictos
    malla, _ = generar_malla_perforacion(
        ancho=2.00, alto=2.00, taladros_cargados=23, taladros_alivio=1,
        diametro_barreno_mm=36.0, diametro_alivio_mm=89.0, forma_seccion="Baúl (hastiales rectos)",
    )
    conflictos = validar_traslapes(malla, diametro_barreno_mm=36.0)
    assert conflictos == []


def test_validar_traslapes_detecta_anillos_de_arranque_demasiado_juntos():
    # con 2 alivios SIN rimar (mismo diámetro que el barreno, 36mm) el
    # burden inicial es más ajustado y el propio patrón cuadrado→rombo
    # concéntrico puede acercar demasiado dos anillos consecutivos — la
    # validación debe surfacear esto, no ocultarlo silenciosamente.
    malla, _ = generar_malla_perforacion(
        ancho=2.00, alto=2.00, taladros_cargados=23, taladros_alivio=2,
        diametro_barreno_mm=36.0, forma_seccion="Baúl (hastiales rectos)",
    )
    conflictos = validar_traslapes(malla, diametro_barreno_mm=36.0)
    assert len(conflictos) > 0
    assert all(c.distancia_m < c.minimo_requerido_m for c in conflictos)


def test_validar_traslapes_detecta_taladros_demasiado_juntos():
    taladros = [
        PosicionTaladro(y=0.0, z=0.5, categoria="arranque", anillo=1),
        PosicionTaladro(y=0.01, z=0.5, categoria="arranque", anillo=1),  # a 1cm — imposible con broca de 36mm
    ]
    conflictos = validar_traslapes(taladros, diametro_barreno_mm=36.0)
    assert len(conflictos) == 1
    assert conflictos[0].distancia_m == pytest.approx(0.01)
    assert conflictos[0].minimo_requerido_m == pytest.approx(0.036 + 0.01)
