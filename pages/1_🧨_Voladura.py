from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import streamlit as st

from auth import require_login

LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "logo_meecsac.jpg"
from core.constants import (
    COEFICIENTE_ROCA,
    DESTINO_PREDOMINANTE_POR_ETAPA,
    DESTINOS_MATERIAL,
    DISTANCIA_TALADROS_RANGO_M,
    EQUIPOS_PERFORACION,
    FORMAS_SECCION,
    LABORES_VERTICALES,
    METODO_TALADROS_MANUAL,
    METODO_TALADROS_ROCA,
    METODO_TALADROS_SECCION,
    ORDEN_ETAPAS,
    TIPOS_CORTE,
    TIPOS_EXPLOSIVO_DEFAULT,
    TIPOS_LABOR,
    TIPOS_ROCA,
)
from core.geometry import malla_solida_pique, malla_solida_tunel, perimetro_seccion
from core.georef import (
    calcular_rumbo_pendiente,
    matriz_rotacion,
    matriz_rotacion_vertical,
    transformar_vertices,
)
from core.malla_perforacion import (
    generar_malla_perforacion,
    secuencia_disparo,
    validar_traslapes,
)
from core.memoria import memoria_calculo
from core.models import DatosGenerales, LaborMinera
from core.voladura import (
    avance_desde_n_disparos,
    avance_desde_produccion_objetivo,
    calcular_programa,
    taladros_desde_roca,
    taladros_por_disparo_seccion,
)
from reports.docx_builder import build_voladura_report
from reports.dxf_export import construir_dxf_labor
from reports.malla_pdf import build_malla_pdf
from viz.dashboard import kpis_voladura
from viz.resumen import con_fila_total, tabla_resultados
from viz.malla_plot import build_isotiempos_figure, build_malla_perforacion_figure
from viz.tunnel_plot import build_tunnel_figure, build_tunnel_figure_solido

st.set_page_config(page_title="Voladura", page_icon=str(LOGO_PATH), layout="wide")
require_login()
st.logo(str(LOGO_PATH), size="large")
st.session_state.setdefault("labores", [])

st.title(":material/explosion: Cálculo de perforación y voladura")
st.write(
    "Registra cada labor minera con su sección y malla de perforación. "
    "El cálculo de taladros, explosivos, accesorios, avance y tonelaje se "
    "actualiza automáticamente."
)

with st.expander("Agregar labor minera", icon=":material/add_circle:", expanded=len(st.session_state["labores"]) == 0):
    st.caption(
        "Solo se piden las variables del programa (labor, sección, longitud, "
        "avance por disparo, taladros por disparo). El diseño de perforación, "
        "los explosivos y las densidades ya usan el criterio estándar de la "
        "OTS — ajústalos en 'Parámetros avanzados' solo si un caso puntual lo requiere."
    )
    modo_programa = st.selectbox(
        "Dato de programa que ya tienes",
        [
            "Longitud programada (m)", "N.° de disparos programado",
            "Producción objetivo (TM)", "Avance mensual (6 meses)",
        ],
        key="modo_programa_nueva_labor",
        help=(
            "Elige el dato que ya conoces del plan; el resto (longitud "
            "programada, N.° de disparos o producción, según corresponda) se "
            "calcula automáticamente con el mismo criterio de la OTS. Con "
            "'Avance mensual' se ingresa directamente lo programado mes a mes."
        ),
    )

    st.markdown("**Propiedades de la roca y N.° de taladros**")
    c_roca1, c_roca2 = st.columns([1, 2])
    with c_roca1:
        tipo_roca = st.selectbox("Tipo de roca", TIPOS_ROCA, index=1, key="tipo_roca_nueva_labor")
    with c_roca2:
        metodo_taladros = st.selectbox(
            "¿Cómo se calcula el N.° de taladros por disparo?",
            [METODO_TALADROS_MANUAL, METODO_TALADROS_SECCION, METODO_TALADROS_ROCA],
            key="metodo_taladros_nueva_labor",
            help=(
                "Las dos fórmulas son las que proporciona la OTS.\n\n"
                "• Manual: usas el número que escribes abajo.\n\n"
                "• Por sección: N.° T = 10 × √(A × H) — solo depende del "
                "tamaño de la sección (cuadro de parámetros operativos).\n\n"
                "• Por tipo de roca: N.° T = (Perímetro / dt) + (Coef. roca × "
                "Área) — además pide el espaciamiento entre taladros (dt), "
                "con el rango y el coeficiente de la tabla por tipo de roca."
            ),
        )
    alterar_por_roca = metodo_taladros == METODO_TALADROS_ROCA
    distancia_taladros = None
    if alterar_por_roca:
        rango_dt = DISTANCIA_TALADROS_RANGO_M.get(tipo_roca, (0.0, 0.0))
        distancia_taladros = st.number_input(
            "Distancia entre taladros — dt (m)",
            min_value=0.01, value=round(sum(rango_dt) / 2.0, 3), step=0.005, format="%.3f",
            key=f"dt_nueva_labor_{tipo_roca}",
            help=f"Rango típico para roca {tipo_roca.lower()}: {rango_dt[0]}–{rango_dt[1]} m. Editable.",
        )

    with st.form("form_labor", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            nombre = st.text_input("Nombre de la labor", placeholder="Ej. Galería Nivel 2")
            tipo = st.selectbox("Tipo de labor", TIPOS_LABOR)
            etapa = st.selectbox("Etapa", ORDEN_ETAPAS)
        with c2:
            ancho = st.number_input("Ancho de sección (m)", min_value=0.0, value=1.77, step=0.01)
            alto = st.number_input("Alto de sección (m)", min_value=0.0, value=1.10, step=0.01)
            forma_seccion = st.selectbox(
                "Forma de la sección", FORMAS_SECCION,
                help="Solo aplica a labores horizontales — Pique y Chimenea siempre usan sección circular vertical.",
            )
        with c3:
            destino = st.selectbox(
                "Destino del material", DESTINOS_MATERIAL,
                help=(
                    "Material predominante según la etapa (guía referencial, la "
                    "elección sigue siendo manual): "
                    + " · ".join(f"{e}: {d}" for e, d in DESTINO_PREDOMINANTE_POR_ETAPA.items())
                ),
            )
            longitud_existente = st.number_input("Longitud/altura existente (m)", value=0.0)

        es_avance_mensual = modo_programa == "Avance mensual (6 meses)"
        st.markdown("**Programa de avance**")
        c4, c5 = st.columns(2)
        with c4:
            avance_por_disparo = st.number_input(
                "Avance x disparo (m)", value=None if es_avance_mensual else 1.10,
                placeholder="Opcional si no se conoce" if es_avance_mensual else None,
            )
        with c5:
            taladros_label = "N.° taladros x disparo"
            if metodo_taladros == METODO_TALADROS_ROCA:
                taladros_label += " (se recalcula según la roca)"
            elif metodo_taladros == METODO_TALADROS_SECCION:
                taladros_label += " (se recalcula según la sección)"
            taladros_cargados = st.number_input(
                taladros_label, min_value=0, value=None if es_avance_mensual else 23, step=1,
                placeholder="Opcional si no se conoce" if es_avance_mensual else None,
            )

        avance_proyectado_input = n_disparos_input = produccion_objetivo_input = None
        avance_mensual_input: list[float] | None = None
        if modo_programa == "Longitud programada (m)":
            avance_proyectado_input = st.number_input("Longitud programada (m)", value=66.0)
        elif modo_programa == "N.° de disparos programado":
            n_disparos_input = st.number_input("N.° de disparos programado", min_value=0, value=60, step=1)
        elif modo_programa == "Producción objetivo (TM)":
            produccion_objetivo_input = st.number_input("Producción objetivo (TM)", min_value=0.0, value=346.96)
        else:
            st.caption("Avance programado por mes (m) — se suman para la longitud total.")
            cols_meses = st.columns(6)
            avance_mensual_input = [
                cols_meses[i].number_input(f"Mes {i + 1}", min_value=0.0, value=0.0, step=0.1, key=f"mes_{i + 1}")
                for i in range(6)
            ]

        with st.expander("Parámetros avanzados (criterio OTS)", icon=":material/tune:"):
            st.markdown("**Diseño de perforación**")
            c7, c8, c9 = st.columns(3)
            with c7:
                diametro_barreno = st.number_input("Diámetro de barreno (mm)", value=36.0)
                longitud_barreno = st.number_input("Longitud de barreno (pies)", value=4.0)
            with c8:
                equipo = st.selectbox("Equipo de perforación", EQUIPOS_PERFORACION)
                tipo_corte = st.selectbox("Tipo de corte", TIPOS_CORTE)
            with c9:
                taladros_alivio = st.number_input("Taladros de alivio", min_value=0, value=2, step=1)
                diametro_alivio = st.number_input(
                    "Diámetro de alivio (mm)", min_value=0.0, value=None,
                    placeholder="= diámetro de barreno",
                    help=(
                        "Diámetro de los taladros de alivio, si se perforan con una "
                        "broca distinta a la de los taladros cargados — usado para "
                        "calcular el burden del corte en la malla de perforación "
                        "(ver más abajo). Vacío = usar el mismo diámetro de barreno."
                    ),
                )

            st.markdown("**Explosivos y accesorios**")
            c10, c11, c12 = st.columns(3)
            with c10:
                cartuchos_por_taladro = st.number_input("Cartuchos por taladro", min_value=0, value=4, step=1)
                peso_cartucho = st.number_input("Peso por cartucho (kg)", value=0.08, format="%.3f")
            with c11:
                tipo_explosivo_1 = st.text_input("Explosivo tipo 1", value=TIPOS_EXPLOSIVO_DEFAULT[0])
                pct_1 = st.number_input("% explosivo tipo 1", min_value=0.0, max_value=100.0, value=40.0)
            with c12:
                tipo_explosivo_2 = st.text_input("Explosivo tipo 2", value=TIPOS_EXPLOSIVO_DEFAULT[1])
                pct_2 = st.number_input("% explosivo tipo 2", min_value=0.0, max_value=100.0, value=60.0)

            st.markdown("**Densidades**")
            c13, c14 = st.columns(2)
            with c13:
                densidad_desmonte = st.number_input("Peso específico desmonte (TM/m³)", value=2.70)
            with c14:
                densidad_mineral = st.number_input("Peso específico mineral (TM/m³)", value=3.00)

        observaciones = st.text_area("Observaciones", value="")

        enviado = st.form_submit_button("Agregar labor", icon=":material/add:", type="primary")
        if enviado:
            densidad_usada = densidad_mineral if destino == "Mineral" else densidad_desmonte
            if not nombre:
                st.error("Ingresa un nombre para la labor.")
            elif abs(pct_1 + pct_2 - 100.0) > 0.01:
                st.error("Los porcentajes de explosivo deben sumar 100%.")
            elif modo_programa == "N.° de disparos programado" and (avance_por_disparo or 0) <= 0:
                st.error("El avance x disparo debe ser mayor a 0 para calcular la longitud a partir del N.° de disparos.")
            elif modo_programa == "Producción objetivo (TM)" and (ancho * alto <= 0 or densidad_usada <= 0):
                st.error("La sección (ancho × alto) y la densidad deben ser mayores a 0 para calcular la longitud a partir de la producción objetivo.")
            elif alterar_por_roca and (not distancia_taladros or distancia_taladros <= 0):
                st.error("La distancia entre taladros (dt) debe ser mayor a 0 para calcular el N.° de taladros según la roca.")
            else:
                avance_mensual_final = None
                if modo_programa == "Longitud programada (m)":
                    avance_proyectado = avance_proyectado_input
                elif modo_programa == "N.° de disparos programado":
                    avance_proyectado = avance_desde_n_disparos(int(n_disparos_input), avance_por_disparo)
                elif modo_programa == "Producción objetivo (TM)":
                    avance_proyectado = avance_desde_produccion_objetivo(
                        produccion_objetivo_input, ancho, alto, densidad_usada
                    )
                else:
                    avance_mensual_final = list(avance_mensual_input)
                    avance_proyectado = sum(avance_mensual_final)

                avance_por_disparo_final = avance_por_disparo if avance_por_disparo is not None else 0.0
                taladros_final = int(taladros_cargados) if taladros_cargados is not None else 0
                if metodo_taladros == METODO_TALADROS_ROCA:
                    perimetro = perimetro_seccion(forma_seccion, ancho, alto)
                    coeficiente = COEFICIENTE_ROCA.get(tipo_roca, 0.0)
                    taladros_final = taladros_desde_roca(perimetro, ancho * alto, distancia_taladros, coeficiente)
                elif metodo_taladros == METODO_TALADROS_SECCION:
                    taladros_final = taladros_por_disparo_seccion(ancho, alto)

                labor = LaborMinera(
                    nombre=nombre,
                    tipo=tipo,
                    etapa=etapa,
                    ancho_m=ancho,
                    alto_m=alto,
                    forma_seccion=forma_seccion,
                    longitud_existente_m=longitud_existente,
                    avance_proyectado_m=avance_proyectado,
                    avance_por_disparo_m=avance_por_disparo_final,
                    avance_mensual_m=avance_mensual_final,
                    diametro_barreno_mm=diametro_barreno,
                    longitud_barreno_pies=longitud_barreno,
                    tipo_corte=tipo_corte,
                    equipo_perforacion=equipo,
                    taladros_cargados=taladros_final,
                    taladros_alivio=int(taladros_alivio),
                    diametro_alivio_mm=diametro_alivio,
                    cartuchos_por_taladro=int(cartuchos_por_taladro),
                    peso_cartucho_kg=peso_cartucho,
                    tipo_explosivo_1=tipo_explosivo_1,
                    tipo_explosivo_2=tipo_explosivo_2,
                    pct_explosivo_1=pct_1,
                    pct_explosivo_2=pct_2,
                    tipo_roca=tipo_roca,
                    alterar_por_roca=alterar_por_roca,
                    distancia_taladros_m=distancia_taladros if alterar_por_roca else None,
                    metodo_taladros=metodo_taladros,
                    destino_material=destino,
                    densidad_desmonte_tm_m3=densidad_desmonte,
                    densidad_mineral_tm_m3=densidad_mineral,
                    observaciones=observaciones,
                )
                st.session_state["labores"].append(labor)
                st.success(f"Labor '{nombre}' agregada.")

labores: list[LaborMinera] = st.session_state["labores"]

if not labores:
    st.info("Aún no hay labores registradas. Agrega la primera con el formulario de arriba.")
    st.stop()

resultados = calcular_programa(labores)
dg_esquema = st.session_state.setdefault("datos_generales", DatosGenerales())


def _forma_malla(labor: LaborMinera) -> str | None:
    """Forma de sección con la que se dibuja la malla: un Pique/Chimenea se
    perfora sobre una sección circular, no sobre la herradura de la labor."""
    return "Circular" if labor.tipo in LABORES_VERTICALES else labor.forma_seccion


def _alto_malla(labor: LaborMinera) -> float:
    """En labores verticales la "sección" es el círculo de diámetro
    `ancho_m`, así que el alto de la malla es ese mismo diámetro."""
    return labor.ancho_m if labor.tipo in LABORES_VERTICALES else labor.alto_m


vista = st.segmented_control(
    "Vista", ["Detalle", "Dashboard"], default="Detalle", key="vista_voladura",
    label_visibility="collapsed",
)
if vista == "Dashboard":
    st.header(":material/dashboard: Tablero del programa de voladura", divider="gray")
    kpis = kpis_voladura(labores, resultados)
    for fila in (kpis[:3], kpis[3:]):
        for columna, kpi in zip(st.columns(len(fila)), fila):
            columna.metric(
                f"{kpi.icono} {kpi.etiqueta}", kpi.valor, border=True, help=kpi.ayuda,
            )

    st.subheader(":material/table_view: Resumen de cálculos por labor", divider="gray")
    st.dataframe(
        con_fila_total(tabla_resultados(labores, resultados), resultados),
        use_container_width=True, hide_index=True,
    )

    st.subheader(":material/view_in_ar: Esquema 3D y malla de perforación por labor", divider="gray")
    nombres_dash = [labor.nombre for labor in labores]
    labores_ver = st.multiselect(
        "Labores a mostrar", nombres_dash, default=nombres_dash[:3],
        help="Cada labor dibuja su sólido 3D y su malla; mostrar muchas a la vez hace más lento el tablero.",
    )
    if not labores_ver:
        st.info("Selecciona al menos una labor para ver sus esquemas.")
    for nombre_labor in labores_ver:
        i = nombres_dash.index(nombre_labor)
        labor_d, resultado_d = labores[i], resultados[i]
        st.markdown(f"**{labor_d.tipo}: {labor_d.nombre}** — {labor_d.etapa}")
        col_3d, col_malla = st.columns(2)
        col_3d.plotly_chart(
            build_tunnel_figure_solido(labor_d, resultado_d, n_meses=dg_esquema.periodo_meses),
            use_container_width=True, key=f"dash_3d_{i}",
        )
        fig_malla_d, _ = build_malla_perforacion_figure(
            labor_d.ancho_m, _alto_malla(labor_d), labor_d.taladros_cargados, labor_d.taladros_alivio,
            diametro_barreno_mm=labor_d.diametro_barreno_mm,
            diametro_alivio_mm=labor_d.diametro_alivio_mm,
            forma_seccion=_forma_malla(labor_d), nombre_labor=labor_d.nombre,
        )
        col_malla.plotly_chart(fig_malla_d, use_container_width=True, key=f"dash_malla_{i}")

    st.caption(
        "Mismos esquemas que la vista Detalle, agrupados para comparar labores — "
        "cambia a Detalle para las cotas, la secuencia de disparo y los reportes."
    )
    st.stop()

st.header(":material/table_view: Resultados por labor", divider="gray")

tabla = tabla_resultados(labores, resultados)
st.dataframe(tabla, use_container_width=True, hide_index=True)

nombres = [labor.nombre for labor in labores]
a_eliminar = st.selectbox("Eliminar labor", ["(ninguna)"] + nombres)
if a_eliminar != "(ninguna)" and st.button("Eliminar seleccionada", icon=":material/delete:"):
    idx = nombres.index(a_eliminar)
    st.session_state["labores"].pop(idx)
    st.rerun()

st.header(":material/view_in_ar: Esquema de la labor", divider="gray")
c_lab, c_estilo = st.columns([2, 1])
with c_lab:
    labor_a_graficar = st.selectbox("Labor a esquematizar", nombres, key="labor_esquema")
with c_estilo:
    estilo_esquema = st.radio(
        "Estilo", ["Wireframe", "Sólido"], key="estilo_esquema", horizontal=True
    )
idx_esquema = nombres.index(labor_a_graficar)
if estilo_esquema == "Sólido":
    modo_anillos = st.radio(
        "Anillos de avance", ["Mensual", "Por disparo"], key="modo_anillos_esquema", horizontal=True,
    )
    fig_tunel = build_tunnel_figure_solido(
        labores[idx_esquema], resultados[idx_esquema], n_meses=dg_esquema.periodo_meses,
        modo_anillos="disparo" if modo_anillos == "Por disparo" else "mensual",
    )
else:
    fig_tunel = build_tunnel_figure(labores[idx_esquema], resultados[idx_esquema])
st.plotly_chart(fig_tunel, use_container_width=True)
leyenda_esquema = (
    "🩶 Gris = tramo ya existente · 🔵 Azul = avance proyectado · "
    "línea punteada roja = frente actual"
)
if estilo_esquema == "Sólido" and modo_anillos == "Mensual":
    leyenda_esquema += (
        " · línea punteada ámbar = avance mensual programado (asumiendo avance "
        f"uniforme en {dg_esquema.periodo_meses} meses — ajustable en "
        "'Datos generales del informe' más abajo)."
    )
elif estilo_esquema == "Sólido":
    leyenda_esquema += " · línea punteada ámbar = un anillo por cada disparo."
else:
    leyenda_esquema += "."
st.caption(leyenda_esquema)

st.header(":material/grid_on: Malla de perforación", divider="gray")
st.caption(
    "Plantilla paramétrica de un round completo (alivios al centro, zonas "
    "en anillo arranque→ayuda→subayuda, contorno y arrastre sobre la "
    "sección real) — es una referencia visual de dónde cae cada taladro, no "
    "el trazo de malla real de campo; el N.° de taladros sí sale de las "
    "fórmulas de la OTS. El corte sigue el método de Holmberg: B₁ = 1.5 × "
    "Ø_alivio × √N.° alivios para el arranque, y cada sección siguiente abre "
    "contra el vacío en diagonal de la anterior (B(n) = 1.5 × √2 × B(n-1)). "
    "Contorno y arrastre ya no son parte del corte, así que se escalan desde "
    "B₁ con los factores de seguridad de Ojeda (2003) — contorno 3, arrastre 2."
)
labor_malla = labores[idx_esquema]
forma_malla = _forma_malla(labor_malla)
alto_malla = _alto_malla(labor_malla)
fig_malla, zonas_malla = build_malla_perforacion_figure(
    labor_malla.ancho_m, alto_malla, labor_malla.taladros_cargados, labor_malla.taladros_alivio,
    diametro_barreno_mm=labor_malla.diametro_barreno_mm, diametro_alivio_mm=labor_malla.diametro_alivio_mm,
    forma_seccion=forma_malla, nombre_labor=labor_malla.nombre,
)
st.plotly_chart(fig_malla, use_container_width=True)
if zonas_malla:
    st.caption("Distancias por zona (burden y, en zonas de arranque/ayuda/subayuda, lado del anillo):")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Zona": z.zona, "Forma": z.forma or "—", "N.° taladros": z.n_taladros,
                    "Burden (mm)": round(z.burden_mm, 1),
                    "Lado (mm)": round(z.lado_mm, 1) if z.lado_mm is not None else None,
                }
                for z in zonas_malla
            ]
        ),
        use_container_width=True, hide_index=True,
    )

malla_taladros, _ = generar_malla_perforacion(
    labor_malla.ancho_m, alto_malla, labor_malla.taladros_cargados, labor_malla.taladros_alivio,
    diametro_barreno_mm=labor_malla.diametro_barreno_mm, diametro_alivio_mm=labor_malla.diametro_alivio_mm,
    forma_seccion=forma_malla,
)
conflictos_malla = validar_traslapes(malla_taladros, diametro_barreno_mm=labor_malla.diametro_barreno_mm)
if conflictos_malla:
    st.warning(
        f"{len(conflictos_malla)} par(es) de taladros quedaron más cerca entre sí que la "
        "distancia mínima segura para el diámetro de barreno indicado — revisa la sección, "
        "el N.° de alivios/taladros o el diámetro de alivio."
    )
    st.dataframe(
        pd.DataFrame([
            {
                "Categoría A": c.categoria_a, "Categoría B": c.categoria_b,
                "Distancia (mm)": round(c.distancia_m * 1000, 0),
                "Mínimo requerido (mm)": round(c.minimo_requerido_m * 1000, 0),
            }
            for c in conflictos_malla
        ]),
        use_container_width=True, hide_index=True,
    )

with st.expander(":material/schedule: Secuencia de disparo (retardos)"):
    st.caption(
        "Orden de disparo por zona (arranque primero, arrastre al final) — retardos de "
        "referencia (ver core.malla_perforacion.RETARDO_MS_POR_ZONA), no un diseño de "
        "timing certificado; ajusta según el sistema de iniciación real que uses."
    )
    pasos_disparo = secuencia_disparo(malla_taladros)
    st.dataframe(
        pd.DataFrame([
            {"Orden": p.orden, "Categoría": p.categoria, "Anillo": p.anillo or None, "Retardo (ms)": p.retardo_ms}
            for p in pasos_disparo
        ]),
        use_container_width=True, hide_index=True,
    )

with st.expander(":material/thermostat: Isotiempos de detonación"):
    st.caption(
        "Mapa de calor del retardo interpolado dentro del contorno real de la sección — "
        "interpolación numérica (sin extrapolar fuera de la sección), no una simulación "
        "física de propagación de onda."
    )
    fig_isotiempos = build_isotiempos_figure(
        malla_taladros, labor_malla.ancho_m, alto_malla, forma_seccion=forma_malla,
        nombre_labor=labor_malla.nombre,
    )
    if fig_isotiempos is None:
        st.info("Se requieren al menos 3 taladros cargados para interpolar los isotiempos.")
    else:
        st.plotly_chart(fig_isotiempos, use_container_width=True)

st.markdown("**Ficha de malla en PDF**")
pdf_malla_bytes = build_malla_pdf(
    labor_malla, resultados[idx_esquema], st.session_state.get("datos_generales"),
    zonas=zonas_malla,
)
st.download_button(
    "Descargar ficha de malla (PDF A3)",
    data=pdf_malla_bytes,
    file_name=f"malla_{labor_malla.nombre}.pdf",
    mime="application/pdf",
    icon=":material/download:",
    key=f"descargar_malla_pdf_{labor_malla.nombre}",
)

st.subheader(":material/place: Georreferenciación y exportación DXF")
st.caption(
    "Ubica el punto de inicio real (UTM + cota) de esta labor para exportar "
    "el sólido a DXF y colocarlo en su posición exacta dentro de un modelo "
    "de AutoCAD que ya esté georreferenciado en UTM."
)
labor_actual = labores[idx_esquema]
es_vertical = labor_actual.tipo in LABORES_VERTICALES
clave_labor = labor_actual.nombre

c_este, c_norte, c_cota = st.columns(3)
with c_este:
    labor_actual.este_utm_inicio = st.number_input(
        "Este UTM — punto de inicio", value=labor_actual.este_utm_inicio,
        format="%.2f", key=f"geo_este_inicio_{clave_labor}",
    )
with c_norte:
    labor_actual.norte_utm_inicio = st.number_input(
        "Norte UTM — punto de inicio", value=labor_actual.norte_utm_inicio,
        format="%.2f", key=f"geo_norte_inicio_{clave_labor}",
    )
with c_cota:
    labor_actual.cota_inicio_m = st.number_input(
        "Cota — punto de inicio (m)", value=labor_actual.cota_inicio_m,
        format="%.2f", key=f"geo_cota_inicio_{clave_labor}",
    )

tiene_punto_final = st.checkbox(
    "La labor ya está en operación (tengo el punto final real)",
    value=labor_actual.este_utm_final is not None,
    key=f"geo_tiene_final_{clave_labor}",
)

if tiene_punto_final:
    c_este_f, c_norte_f, c_cota_f = st.columns(3)
    with c_este_f:
        labor_actual.este_utm_final = st.number_input(
            "Este UTM — punto final", value=labor_actual.este_utm_final,
            format="%.2f", key=f"geo_este_final_{clave_labor}",
        )
    with c_norte_f:
        labor_actual.norte_utm_final = st.number_input(
            "Norte UTM — punto final", value=labor_actual.norte_utm_final,
            format="%.2f", key=f"geo_norte_final_{clave_labor}",
        )
    with c_cota_f:
        labor_actual.cota_final_m = st.number_input(
            "Cota — punto final (m)", value=labor_actual.cota_final_m,
            format="%.2f", key=f"geo_cota_final_{clave_labor}",
        )
elif es_vertical:
    labor_actual.este_utm_final = labor_actual.norte_utm_final = labor_actual.cota_final_m = None
    labor_actual.sentido_vertical = st.radio(
        "Sentido", ["Abajo", "Arriba"], horizontal=True, key=f"geo_sentido_{clave_labor}",
        index=0 if labor_actual.sentido_vertical == "Abajo" else 1,
    )
else:
    labor_actual.este_utm_final = labor_actual.norte_utm_final = labor_actual.cota_final_m = None
    c_rumbo, c_pendiente = st.columns(2)
    with c_rumbo:
        labor_actual.rumbo_manual_deg = st.number_input(
            "Rumbo manual (° desde el Norte)", value=labor_actual.rumbo_manual_deg,
            min_value=0.0, max_value=360.0, format="%.1f", key=f"geo_rumbo_{clave_labor}",
        )
    with c_pendiente:
        labor_actual.pendiente_manual_pct = st.number_input(
            "Pendiente manual (%, opcional — positivo = bajando)",
            value=labor_actual.pendiente_manual_pct, format="%.1f", key=f"geo_pendiente_{clave_labor}",
        )

punto_inicio_completo = None not in (
    labor_actual.este_utm_inicio, labor_actual.norte_utm_inicio, labor_actual.cota_inicio_m,
)
punto_final_completo = None not in (
    labor_actual.este_utm_final, labor_actual.norte_utm_final, labor_actual.cota_final_m,
)

st.markdown("**Exportar a AutoCAD (DXF)**")
if not punto_inicio_completo:
    st.info("Completa el punto de inicio (Este, Norte, Cota) para poder exportar el sólido a DXF.")
else:
    origen = (labor_actual.este_utm_inicio, labor_actual.norte_utm_inicio, labor_actual.cota_inicio_m)
    longitud_existente_dxf = max(labor_actual.longitud_existente_m, 0.0)
    avance_proyectado_dxf = max(labor_actual.avance_proyectado_m, 0.01)
    rotacion = None

    if es_vertical:
        if punto_final_completo:
            sentido = "abajo" if labor_actual.cota_final_m < labor_actual.cota_inicio_m else "arriba"
        else:
            sentido = "abajo" if labor_actual.sentido_vertical == "Abajo" else "arriba"
        rotacion = matriz_rotacion_vertical(sentido)
        malla_dxf = malla_solida_pique(labor_actual.ancho_m, longitud_existente_dxf, avance_proyectado_dxf)
        st.caption(f"Orientación: labor vertical, sentido \"{sentido}\".")
    else:
        rumbo = pendiente_deg = None
        if punto_final_completo:
            rumbo, pendiente_deg, distancia_horizontal = calcular_rumbo_pendiente(
                labor_actual.este_utm_inicio, labor_actual.norte_utm_inicio, labor_actual.cota_inicio_m,
                labor_actual.este_utm_final, labor_actual.norte_utm_final, labor_actual.cota_final_m,
            )
            if longitud_existente_dxf > 0:
                diferencia = abs(distancia_horizontal - longitud_existente_dxf)
                if diferencia > max(1.0, 0.05 * longitud_existente_dxf):
                    st.warning(
                        f"La distancia real entre los dos puntos ({distancia_horizontal:.1f} m) difiere "
                        f"de la longitud existente declarada ({longitud_existente_dxf:.1f} m); se usa esta "
                        "última para el tamaño del sólido exportado."
                    )
        elif labor_actual.rumbo_manual_deg is not None:
            rumbo = labor_actual.rumbo_manual_deg
            pendiente_deg = math.degrees(math.atan((labor_actual.pendiente_manual_pct or 0.0) / 100.0))

        if rumbo is None:
            st.info("Ingresa el rumbo manual o el punto final para orientar la exportación.")
        else:
            rotacion = matriz_rotacion(rumbo, pendiente_deg)
            st.caption(f"Rumbo: {rumbo:.1f}° · Pendiente: {pendiente_deg:.1f}°")
        malla_dxf = malla_solida_tunel(
            labor_actual.ancho_m, labor_actual.alto_m, longitud_existente_dxf, avance_proyectado_dxf,
            forma=labor_actual.forma_seccion,
        )

    if rotacion is not None:
        dg_geo = st.session_state.setdefault("datos_generales", DatosGenerales())
        vertices_mundo = transformar_vertices(malla_dxf["vertices"], origen, rotacion)
        dxf_bytes = construir_dxf_labor(
            vertices_mundo, malla_dxf["triangulos"], malla_dxf["tramo_por_triangulo"],
            origen, labor_actual.nombre, labor_actual.tipo,
            zona_hemisferio=f"{dg_geo.zona_utm}{dg_geo.hemisferio}",
        )
        st.download_button(
            "Descargar sólido en DXF (AutoCAD)",
            data=dxf_bytes,
            file_name=f"{labor_actual.nombre}.dxf",
            mime="application/dxf",
            icon=":material/download:",
            key=f"descargar_dxf_{clave_labor}",
        )

st.header(":material/calculate: Memoria de cálculo", divider="gray")
st.caption(
    "Desglose paso a paso (fórmula → sustitución → resultado) de cada cifra "
    "de la tabla de resultados — para auditar o sustentar el cálculo."
)
labor_a_detallar = st.selectbox("Labor a detallar", nombres, key="labor_memoria")
idx_memoria = nombres.index(labor_a_detallar)
pasos = memoria_calculo(labores[idx_memoria], resultados[idx_memoria])
tabla_memoria = pd.DataFrame(
    [
        {"Concepto": p.concepto, "Fórmula": p.formula, "Sustitución": p.sustitucion, "Resultado": p.resultado}
        for p in pasos
    ]
)
st.dataframe(tabla_memoria, use_container_width=True, hide_index=True)

st.header(":material/description: Reporte", divider="gray")
titulo_proyecto = st.text_input("Título del proyecto para el reporte", value="Programa de perforación y voladura")

with st.expander("Datos generales del informe (opcional)", icon=":material/badge:"):
    st.caption(
        "Se usan para armar el encabezado y la introducción del reporte Word "
        "(estilo informe técnico). Deja en blanco lo que no aplique — nunca "
        "se inventa un dato."
    )
    dg = st.session_state.setdefault("datos_generales", DatosGenerales())
    c1, c2 = st.columns(2)
    with c1:
        dg.nombre_concesion = st.text_input(
            "Nombre de la concesión / proyecto", value=dg.nombre_concesion,
            placeholder='Ej. Concesión Minera "Virgen de la Puerta I"',
        )
        dg.codigo_concesion = st.text_input("Código de concesión", value=dg.codigo_concesion)
        dg.empresa = st.text_input("Empresa / razón social", value=dg.empresa)
        dg.ruc = st.text_input("RUC", value=dg.ruc)
    with c2:
        dg.departamento = st.text_input("Departamento", value=dg.departamento)
        dg.provincia = st.text_input("Provincia", value=dg.provincia)
        dg.distrito = st.text_input("Distrito", value=dg.distrito)
        dg.periodo_meses = st.number_input("Periodo del programa (meses)", min_value=1, value=dg.periodo_meses, step=1)
    st.caption("Zona UTM del proyecto — se usa como referencia en la exportación a DXF.")
    c3, c4 = st.columns(2)
    with c3:
        dg.zona_utm = st.number_input("Zona UTM", min_value=1, max_value=60, value=dg.zona_utm)
    with c4:
        dg.hemisferio = st.selectbox("Hemisferio", ["S", "N"], index=0 if dg.hemisferio == "S" else 1)

    st.caption("Cajetín del reporte — datos de control del documento.")
    c5, c6 = st.columns(2)
    with c5:
        dg.elaborado_por = st.text_input("Elaborado por", value=dg.elaborado_por)
        dg.cargo_elaborado_por = st.text_input("Cargo / área", value=dg.cargo_elaborado_por)
        dg.revisado_por = st.text_input("Revisado por", value=dg.revisado_por)
        dg.aprobado_por = st.text_input("Aprobado por", value=dg.aprobado_por)
    with c6:
        dg.numero_plano = st.text_input("N.° de plano", value=dg.numero_plano)
        dg.revision = st.text_input("Revisión", value=dg.revision, placeholder="0")
        dg.cliente = st.text_input("Cliente", value=dg.cliente)

estilo_reporte = "solido" if estilo_esquema == "Sólido" else "wireframe"
buffer = build_voladura_report(
    labores, resultados, titulo_proyecto, st.session_state["datos_generales"], estilo_reporte
)
st.download_button(
    "Descargar reporte Word",
    data=buffer,
    file_name="reporte_voladura.docx",
    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    icon=":material/download:",
    type="primary",
)
