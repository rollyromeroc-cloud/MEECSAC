import dataclasses
import json

import pandas as pd
import plotly.express as px
import streamlit as st

from auth import require_login
from core.models import LaborMinera, Polvorin, PuntoRiesgo
from core.voladura import calcular_programa

st.set_page_config(page_title="Programa General", page_icon="📊", layout="wide")
require_login()
st.session_state.setdefault("labores", [])
st.session_state.setdefault("polvorines", [])
st.session_state.setdefault("puntos_riesgo", [])

st.title("📊 Programa general")
st.write(
    "Vista consolidada de todas las labores del programa, y exportar/importar "
    "el proyecto completo (labores + polvorines + puntos de riesgo) como JSON "
    "para compartirlo entre las computadoras del equipo."
)

labores: list[LaborMinera] = st.session_state["labores"]

if labores:
    resultados = calcular_programa(labores)

    total_avance = sum(l.avance_proyectado_m for l in labores)
    total_disparos = sum(r.n_disparos for r in resultados)
    total_explosivo = sum(r.explosivo_total_kg for r in resultados)
    total_tonelaje = sum(r.tonelaje_total_tm for r in resultados)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Avance total programado", f"{total_avance:,.2f} m")
    c2.metric("Disparos totales", f"{total_disparos:,}")
    c3.metric("Explosivo total", f"{total_explosivo:,.2f} kg")
    c4.metric("Tonelaje total", f"{total_tonelaje:,.2f} TM")

    df = pd.DataFrame(
        [
            {
                "Labor": l.nombre,
                "Etapa": l.etapa,
                "Avance (m)": l.avance_proyectado_m,
                "Tonelaje (TM)": r.tonelaje_total_tm,
                "Explosivo (kg)": r.explosivo_total_kg,
            }
            for l, r in zip(labores, resultados)
        ]
    )

    orden_etapas = ["Desarrollo", "Preparación", "Explotación"]
    df["Etapa"] = pd.Categorical(df["Etapa"], categories=orden_etapas, ordered=True)
    df = df.sort_values(["Etapa", "Labor"])
    df["Avance acumulado (m)"] = df["Avance (m)"].cumsum()
    df["Tonelaje acumulado (TM)"] = df["Tonelaje (TM)"].cumsum()

    st.subheader("Avance y tonelaje acumulado del programa")
    fig = px.line(
        df,
        x="Labor",
        y="Avance acumulado (m)",
        markers=True,
        title="Avance acumulado por labor (ordenado por etapa)",
    )
    fig.update_layout(xaxis_title=None)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Distribución de tonelaje por etapa")
    fig2 = px.bar(
        df,
        x="Etapa",
        y="Tonelaje (TM)",
        color="Etapa",
        title="Tonelaje total por etapa del programa",
    )
    st.plotly_chart(fig2, use_container_width=True)
else:
    st.info("Aún no hay labores registradas. Ve a la sección '🧨 Voladura' para agregar la primera.")

st.header("Exportar / importar proyecto")

st.write(
    "Exporta todo el proyecto (labores, polvorines, puntos de riesgo) a un "
    "archivo JSON para compartirlo por correo o mensajería, y cárgalo en otra "
    "computadora con el mismo formulario."
)


def _proyecto_a_dict() -> dict:
    return {
        "labores": [dataclasses.asdict(l) for l in st.session_state["labores"]],
        "polvorines": [dataclasses.asdict(p) for p in st.session_state["polvorines"]],
        "puntos_riesgo": [dataclasses.asdict(p) for p in st.session_state["puntos_riesgo"]],
    }


col_exp, col_imp = st.columns(2)

with col_exp:
    st.subheader("Exportar")
    json_bytes = json.dumps(_proyecto_a_dict(), indent=2, ensure_ascii=False).encode("utf-8")
    st.download_button(
        "⬇️ Descargar proyecto (JSON)",
        data=json_bytes,
        file_name="proyecto_voladura_polvorin.json",
        mime="application/json",
    )

with col_imp:
    st.subheader("Importar")
    archivo = st.file_uploader("Cargar proyecto (JSON)", type="json")
    modo = st.radio("Al importar:", ["Reemplazar todo", "Agregar a lo existente"], horizontal=True)
    if archivo is not None and st.button("Importar ahora"):
        try:
            datos = json.loads(archivo.read().decode("utf-8"))
            nuevas_labores = [LaborMinera(**d) for d in datos.get("labores", [])]
            nuevos_polvorines = [Polvorin(**d) for d in datos.get("polvorines", [])]
            nuevos_puntos = [PuntoRiesgo(**d) for d in datos.get("puntos_riesgo", [])]

            if modo == "Reemplazar todo":
                st.session_state["labores"] = nuevas_labores
                st.session_state["polvorines"] = nuevos_polvorines
                st.session_state["puntos_riesgo"] = nuevos_puntos
            else:
                st.session_state["labores"].extend(nuevas_labores)
                st.session_state["polvorines"].extend(nuevos_polvorines)
                st.session_state["puntos_riesgo"].extend(nuevos_puntos)

            st.success(
                f"Importado: {len(nuevas_labores)} labores, "
                f"{len(nuevos_polvorines)} polvorines, {len(nuevos_puntos)} puntos de riesgo."
            )
            st.rerun()
        except Exception as e:
            st.error(f"No se pudo importar el archivo: {e}")
