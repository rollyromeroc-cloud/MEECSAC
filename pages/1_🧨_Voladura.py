import pandas as pd
import plotly.express as px
import streamlit as st

from auth import require_login
from core.constants import (
    DESTINOS_MATERIAL,
    EQUIPOS_PERFORACION,
    TIPOS_CORTE,
    TIPOS_EXPLOSIVO_DEFAULT,
    TIPOS_LABOR,
    TIPOS_ROCA,
)
from core.memoria import memoria_calculo
from core.models import DatosGenerales, LaborMinera
from core.voladura import calcular_programa
from reports.docx_builder import build_voladura_report
from viz.tunnel_plot import build_tunnel_figure, build_tunnel_figure_solido

st.set_page_config(page_title="Voladura", page_icon="🧨", layout="wide")
require_login()
st.session_state.setdefault("labores", [])

# Paleta categórica fija (2 series: explosivo tipo 1 / tipo 2) — colorblind-safe
# (Plotly "Safe", basada en Okabe-Ito). No se cicla ni se reordena.
COLOR_TIPO1 = "#88CCEE"
COLOR_TIPO2 = "#CC6677"

st.title("🧨 Cálculo de perforación y voladura")
st.write(
    "Registra cada labor minera con su sección y malla de perforación. "
    "El cálculo de taladros, explosivos, accesorios, avance y tonelaje se "
    "actualiza automáticamente."
)

with st.expander("➕ Agregar labor minera", expanded=len(st.session_state["labores"]) == 0):
    with st.form("form_labor", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            nombre = st.text_input("Nombre de la labor", placeholder="Ej. Galería Nivel 2")
            tipo = st.selectbox("Tipo de labor", TIPOS_LABOR)
            etapa = st.selectbox("Etapa", ["Desarrollo", "Preparación", "Explotación"])
        with c2:
            ancho = st.number_input("Ancho de sección (m)", min_value=0.0, value=1.77, step=0.01)
            alto = st.number_input("Alto de sección (m)", min_value=0.0, value=1.10, step=0.01)
            tipo_roca = st.selectbox("Tipo de roca", TIPOS_ROCA, index=1)
        with c3:
            destino = st.selectbox("Destino del material", DESTINOS_MATERIAL)
            densidad_desmonte = st.number_input("Peso específico desmonte (TM/m³)", value=2.70)
            densidad_mineral = st.number_input("Peso específico mineral (TM/m³)", value=3.00)

        st.markdown("**Avance**")
        c4, c5, c6 = st.columns(3)
        with c4:
            longitud_existente = st.number_input("Longitud/altura existente (m)", value=0.0)
        with c5:
            avance_proyectado = st.number_input("Avance proyectado (m)", value=66.0)
        with c6:
            avance_por_disparo = st.number_input("Avance promedio por disparo (m)", value=1.10)

        st.markdown("**Diseño de perforación**")
        c7, c8, c9 = st.columns(3)
        with c7:
            diametro_barreno = st.number_input("Diámetro de barreno (mm)", value=36.0)
            longitud_barreno = st.number_input("Longitud de barreno (pies)", value=4.0)
        with c8:
            equipo = st.selectbox("Equipo de perforación", EQUIPOS_PERFORACION)
            tipo_corte = st.selectbox("Tipo de corte", TIPOS_CORTE)
        with c9:
            taladros_cargados = st.number_input("Taladros cargados por disparo", min_value=0, value=23, step=1)
            taladros_alivio = st.number_input("Taladros de alivio", min_value=0, value=2, step=1)

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

        observaciones = st.text_area("Observaciones", value="")

        enviado = st.form_submit_button("Agregar labor")
        if enviado:
            if not nombre:
                st.error("Ingresa un nombre para la labor.")
            elif abs(pct_1 + pct_2 - 100.0) > 0.01:
                st.error("Los porcentajes de explosivo deben sumar 100%.")
            else:
                labor = LaborMinera(
                    nombre=nombre,
                    tipo=tipo,
                    etapa=etapa,
                    ancho_m=ancho,
                    alto_m=alto,
                    longitud_existente_m=longitud_existente,
                    avance_proyectado_m=avance_proyectado,
                    avance_por_disparo_m=avance_por_disparo,
                    diametro_barreno_mm=diametro_barreno,
                    longitud_barreno_pies=longitud_barreno,
                    tipo_corte=tipo_corte,
                    equipo_perforacion=equipo,
                    taladros_cargados=int(taladros_cargados),
                    taladros_alivio=int(taladros_alivio),
                    cartuchos_por_taladro=int(cartuchos_por_taladro),
                    peso_cartucho_kg=peso_cartucho,
                    tipo_explosivo_1=tipo_explosivo_1,
                    tipo_explosivo_2=tipo_explosivo_2,
                    pct_explosivo_1=pct_1,
                    pct_explosivo_2=pct_2,
                    tipo_roca=tipo_roca,
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

st.header("Resultados por labor")

tabla = pd.DataFrame(
    [
        {
            "Labor": labor.nombre,
            "Tipo": labor.tipo,
            "Etapa": labor.etapa,
            "Sección (m)": f"{labor.ancho_m} × {labor.alto_m}",
            "Área (m²)": round(r.area_m2, 3),
            "Avance (m)": labor.avance_proyectado_m,
            "N.° disparos": r.n_disparos,
            "Explosivo total (kg)": round(r.explosivo_total_kg, 2),
            "Volumen total (m³)": round(r.volumen_total_m3, 2),
            "Tonelaje total (TM)": round(r.tonelaje_total_tm, 2),
            "Factor de potencia (kg/TM)": round(r.factor_potencia_kg_tm, 2),
            "Fulminantes": r.fulminantes_total,
            "Mecha total (m)": round(r.mecha_total_m, 2),
        }
        for labor, r in zip(labores, resultados)
    ]
)
st.dataframe(tabla, use_container_width=True, hide_index=True)

nombres = [labor.nombre for labor in labores]
a_eliminar = st.selectbox("Eliminar labor", ["(ninguna)"] + nombres)
if a_eliminar != "(ninguna)" and st.button("Eliminar seleccionada"):
    idx = nombres.index(a_eliminar)
    st.session_state["labores"].pop(idx)
    st.rerun()

st.header("Esquema de la labor")
c_lab, c_estilo = st.columns([2, 1])
with c_lab:
    labor_a_graficar = st.selectbox("Labor a esquematizar", nombres, key="labor_esquema")
with c_estilo:
    estilo_esquema = st.radio(
        "Estilo", ["Wireframe", "Sólido"], key="estilo_esquema", horizontal=True
    )
idx_esquema = nombres.index(labor_a_graficar)
constructor_figura = build_tunnel_figure_solido if estilo_esquema == "Sólido" else build_tunnel_figure
fig_tunel = constructor_figura(labores[idx_esquema], resultados[idx_esquema])
st.plotly_chart(fig_tunel, use_container_width=True)
st.caption(
    "🩶 Gris = tramo ya existente · 🔵 Azul = avance proyectado · "
    "línea punteada = frente actual."
)

st.header("📐 Memoria de cálculo")
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

st.header("Gráficos")

col_a, col_b = st.columns(2)

with col_a:
    fig_avance = px.bar(
        tabla,
        x="Labor",
        y="Avance (m)",
        color="Etapa",
        title="Avance proyectado por labor",
    )
    fig_avance.update_layout(yaxis_title="Avance (m)", xaxis_title=None)
    st.plotly_chart(fig_avance, use_container_width=True)

with col_b:
    explosivos_df = pd.DataFrame(
        {
            "Labor": [labor.nombre for labor in labores] * 2,
            "Tipo": [labor.tipo_explosivo_1 for labor in labores]
            + [labor.tipo_explosivo_2 for labor in labores],
            "Explosivo (kg)": [r.explosivo_tipo1_kg for r in resultados]
            + [r.explosivo_tipo2_kg for r in resultados],
        }
    )
    fig_exp = px.bar(
        explosivos_df,
        x="Labor",
        y="Explosivo (kg)",
        color="Tipo",
        title="Consumo de explosivo por labor",
        color_discrete_sequence=[COLOR_TIPO1, COLOR_TIPO2],
    )
    fig_exp.update_layout(yaxis_title="Explosivo (kg)", xaxis_title=None)
    st.plotly_chart(fig_exp, use_container_width=True)

fig_tonelaje = px.bar(
    tabla,
    x="Labor",
    y="Tonelaje total (TM)",
    color="Etapa",
    title="Tonelaje total por labor",
)
fig_tonelaje.update_layout(yaxis_title="Tonelaje (TM)", xaxis_title=None)
st.plotly_chart(fig_tonelaje, use_container_width=True)

st.header("Reporte")
titulo_proyecto = st.text_input("Título del proyecto para el reporte", value="Programa de perforación y voladura")

with st.expander("Datos generales del informe (opcional)"):
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

estilo_reporte = "solido" if estilo_esquema == "Sólido" else "wireframe"
buffer = build_voladura_report(
    labores, resultados, titulo_proyecto, st.session_state["datos_generales"], estilo_reporte
)
st.download_button(
    "⬇️ Descargar reporte Word",
    data=buffer,
    file_name="reporte_voladura.docx",
    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
)
