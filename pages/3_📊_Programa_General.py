from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from auth import require_login
from core.constants import ORDEN_ETAPAS
from core.models import LaborMinera, Polvorin, PuntoRiesgo
from core.voladura import calcular_programa

LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "logo_meecsac.jpg"

st.set_page_config(page_title="Programa General", page_icon=str(LOGO_PATH), layout="wide")
require_login()
st.logo(str(LOGO_PATH), size="large")
st.session_state.setdefault("labores", [])
st.session_state.setdefault("polvorines", [])
st.session_state.setdefault("puntos_riesgo", [])

st.title(":material/dashboard: Programa general")
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
    c1.metric(":material/straighten: Avance total programado", f"{total_avance:,.2f} m", border=True)
    c2.metric(":material/bolt: Disparos totales", f"{total_disparos:,}", border=True)
    c3.metric(":material/explosion: Explosivo total", f"{total_explosivo:,.2f} kg", border=True)
    c4.metric(":material/scale: Tonelaje total", f"{total_tonelaje:,.2f} TM", border=True)

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

    df["Etapa"] = pd.Categorical(df["Etapa"], categories=ORDEN_ETAPAS, ordered=True)
    df = df.sort_values(["Etapa", "Labor"])
    df["Avance acumulado (m)"] = df["Avance (m)"].cumsum()
    df["Tonelaje acumulado (TM)"] = df["Tonelaje (TM)"].cumsum()

    st.subheader(":material/table_view: Programa consolidado por labor")
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("Aún no hay labores registradas. Ve a la sección '🧨 Voladura' para agregar la primera.")

st.header(":material/swap_horiz: Exportar / importar proyecto", divider="gray")

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
    st.subheader(":material/upload_file: Exportar")
    json_bytes = json.dumps(_proyecto_a_dict(), indent=2, ensure_ascii=False).encode("utf-8")
    st.download_button(
        "Descargar proyecto (JSON)",
        data=json_bytes,
        file_name="proyecto_voladura_polvorin.json",
        mime="application/json",
        icon=":material/download:",
        type="primary",
    )

with col_imp:
    st.subheader(":material/file_open: Importar")
    archivo = st.file_uploader("Cargar proyecto (JSON)", type="json")
    modo = st.radio("Al importar:", ["Reemplazar todo", "Agregar a lo existente"], horizontal=True)
    if archivo is not None and st.button("Importar ahora", icon=":material/publish:", type="primary"):
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
