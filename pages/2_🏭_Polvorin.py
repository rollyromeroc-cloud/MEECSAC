from pathlib import Path

import folium
import pandas as pd
import streamlit as st
from pyproj import Transformer
from streamlit_folium import st_folium

from auth import require_login

LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "logo_meecsac.jpg"
from core.constants import HEMISFERIO_DEFAULT, TIPOS_PUNTO_RIESGO, ZONA_UTM_DEFAULT
from core.models import Polvorin, PuntoRiesgo
from core.polvorin import area_shoelace, evaluar_distancias, perimetro
from reports.docx_builder import build_polvorin_report

st.set_page_config(page_title="Polvorín", page_icon=str(LOGO_PATH), layout="wide")
require_login()
st.logo(str(LOGO_PATH), size="large")
st.session_state.setdefault("polvorines", [])
st.session_state.setdefault("puntos_riesgo", [])

st.title(":material/warehouse: Seguridad de polvorín")
st.write(
    "Registra el/los polvorín(es) y los puntos de riesgo cercanos para "
    "verificar distancias reales contra las distancias mínimas que definas. "
    "Las distancias mínimas **no vienen precargadas**: ingrésalas según el "
    "reglamento vigente (D.S. N.° 024-2016-EM y modificatorias) — la app no "
    "reemplaza esa verificación."
)

with st.expander("Zona UTM del proyecto", icon=":material/public:"):
    c1, c2 = st.columns(2)
    with c1:
        zona_utm = st.number_input("Zona UTM", min_value=1, max_value=60, value=ZONA_UTM_DEFAULT)
    with c2:
        hemisferio = st.selectbox("Hemisferio", ["S", "N"], index=0 if HEMISFERIO_DEFAULT == "S" else 1)

epsg_code = f"327{int(zona_utm):02d}" if hemisferio == "S" else f"326{int(zona_utm):02d}"
transformer = Transformer.from_crs(f"EPSG:{epsg_code}", "EPSG:4326", always_xy=True)


def utm_a_lonlat(este: float, norte: float):
    lon, lat = transformer.transform(este, norte)
    return lat, lon


with st.expander("Agregar polvorín", icon=":material/add_circle:", expanded=len(st.session_state["polvorines"]) == 0):
    with st.form("form_polvorin", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            nombre_p = st.text_input("Nombre", placeholder="Ej. Polvorín de Explosivos 1")
            tipo_p = st.selectbox("Tipo", ["Explosivos", "Accesorios"])
        with c2:
            este_p = st.number_input("Este UTM", value=500000.0, format="%.2f")
            norte_p = st.number_input("Norte UTM", value=8390000.0, format="%.2f")
        with c3:
            cantidad_kg = st.number_input("Cantidad almacenada (kg, opcional)", value=0.0)
            radio_influencia = st.number_input(
                "Radio de influencia (m, opcional)",
                value=0.0,
                help="Radio de seguridad alrededor del polvorín, se dibuja como círculo en el mapa (como en tus planos de referencia).",
            )

        st.caption("Vértices del cerco perimétrico (opcional, para calcular área/perímetro):")
        vertices_df = st.data_editor(
            pd.DataFrame({"Este": [], "Norte": []}),
            num_rows="dynamic",
            key="vertices_editor",
        )

        enviado_p = st.form_submit_button("Agregar polvorín", icon=":material/add:", type="primary")
        if enviado_p:
            if not nombre_p:
                st.error("Ingresa un nombre para el polvorín.")
            else:
                vertices = [
                    (row["Este"], row["Norte"])
                    for _, row in vertices_df.iterrows()
                    if pd.notna(row["Este"]) and pd.notna(row["Norte"])
                ]
                polvorin = Polvorin(
                    nombre=nombre_p,
                    tipo=tipo_p,
                    este_utm=este_p,
                    norte_utm=norte_p,
                    vertices_cerco=vertices,
                    cantidad_almacenada_kg=cantidad_kg or None,
                    radio_influencia_m=radio_influencia or None,
                )
                st.session_state["polvorines"].append(polvorin)
                st.success(f"Polvorín '{nombre_p}' agregado.")

with st.expander("Agregar punto de riesgo", icon=":material/add_location_alt:", expanded=False):
    with st.form("form_punto_riesgo", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            nombre_r = st.text_input("Nombre del punto", placeholder="Ej. Centro poblado San Juan")
            tipo_r = st.selectbox("Tipo de punto", TIPOS_PUNTO_RIESGO)
        with c2:
            este_r = st.number_input("Este UTM ", value=500000.0, format="%.2f", key="este_r")
            norte_r = st.number_input("Norte UTM ", value=8390000.0, format="%.2f", key="norte_r")
        with c3:
            distancia_minima = st.number_input("Distancia mínima requerida (m)", value=0.0)

        enviado_r = st.form_submit_button("Agregar punto de riesgo", icon=":material/add:", type="primary")
        if enviado_r:
            if not nombre_r:
                st.error("Ingresa un nombre para el punto de riesgo.")
            else:
                punto = PuntoRiesgo(
                    nombre=nombre_r,
                    tipo=tipo_r,
                    este_utm=este_r,
                    norte_utm=norte_r,
                    distancia_minima_requerida_m=distancia_minima,
                )
                st.session_state["puntos_riesgo"].append(punto)
                st.success(f"Punto de riesgo '{nombre_r}' agregado.")

polvorines: list[Polvorin] = st.session_state["polvorines"]
puntos: list[PuntoRiesgo] = st.session_state["puntos_riesgo"]

if not polvorines:
    st.info("Aún no hay polvorines registrados. Agrega el primero con el formulario de arriba.")
    st.stop()

resultados_por_polvorin = {p.nombre: evaluar_distancias(p, puntos) for p in polvorines}

st.header(":material/warehouse: Polvorines registrados", divider="gray")
for polvorin in polvorines:
    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        with c1:
            st.subheader(f"{polvorin.tipo}: {polvorin.nombre}")
            st.write(f"Coordenadas: Este {polvorin.este_utm}, Norte {polvorin.norte_utm}")
            if polvorin.vertices_cerco:
                st.write(
                    f"Área del cerco: {area_shoelace(polvorin.vertices_cerco):,.2f} m² · "
                    f"Perímetro: {perimetro(polvorin.vertices_cerco):,.2f} m"
                )
        with c2:
            if st.button("Eliminar", key=f"del_{polvorin.nombre}", icon=":material/delete:"):
                st.session_state["polvorines"].remove(polvorin)
                st.rerun()

        resultados = resultados_por_polvorin[polvorin.nombre]
        if resultados:
            df = pd.DataFrame(
                [
                    {
                        "Punto de riesgo": r.punto_nombre,
                        "Tipo": r.punto_tipo,
                        "Distancia real (m)": round(r.distancia_real_m, 2),
                        "Distancia mínima (m)": r.distancia_minima_m,
                        "¿Cumple?": "✅ Sí" if r.cumple else "❌ No",
                    }
                    for r in resultados
                ]
            )
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.caption("Sin puntos de riesgo registrados todavía.")

if puntos:
    st.header(":material/warning: Puntos de riesgo registrados", divider="gray")
    nombres_puntos = [p.nombre for p in puntos]
    a_eliminar = st.selectbox("Eliminar punto de riesgo", ["(ninguno)"] + nombres_puntos)
    if a_eliminar != "(ninguno)" and st.button("Eliminar punto seleccionado", icon=":material/delete:"):
        idx = nombres_puntos.index(a_eliminar)
        st.session_state["puntos_riesgo"].pop(idx)
        st.rerun()

st.header(":material/map: Mapa", divider="gray")
lat0, lon0 = utm_a_lonlat(polvorines[0].este_utm, polvorines[0].norte_utm)
mapa = folium.Map(location=[lat0, lon0], zoom_start=14)

for polvorin in polvorines:
    lat, lon = utm_a_lonlat(polvorin.este_utm, polvorin.norte_utm)
    folium.Marker(
        [lat, lon],
        tooltip=f"{polvorin.tipo}: {polvorin.nombre}",
        icon=folium.Icon(color="red", icon="warning-sign"),
    ).add_to(mapa)
    if polvorin.vertices_cerco:
        cerco_latlon = [utm_a_lonlat(e, n) for e, n in polvorin.vertices_cerco]
        folium.Polygon(cerco_latlon, color="red", weight=2, fill=True, fill_opacity=0.1).add_to(mapa)
    if polvorin.radio_influencia_m:
        folium.Circle(
            [lat, lon],
            radius=polvorin.radio_influencia_m,
            color="#2CA02C",
            weight=2,
            dash_array="6",
            fill=False,
            tooltip=f"Radio de influencia: {polvorin.radio_influencia_m:,.2f} m",
        ).add_to(mapa)

for punto in puntos:
    lat, lon = utm_a_lonlat(punto.este_utm, punto.norte_utm)
    folium.Marker(
        [lat, lon],
        tooltip=f"{punto.tipo}: {punto.nombre}",
        icon=folium.Icon(color="blue", icon="info-sign"),
    ).add_to(mapa)
    for polvorin in polvorines:
        lat_p, lon_p = utm_a_lonlat(polvorin.este_utm, polvorin.norte_utm)
        distancia = next(
            (
                r.distancia_real_m
                for r in resultados_por_polvorin[polvorin.nombre]
                if r.punto_nombre == punto.nombre
            ),
            None,
        )
        if distancia is not None:
            folium.PolyLine(
                [[lat_p, lon_p], [lat, lon]],
                color="gray",
                weight=1,
                dash_array="4",
                tooltip=f"{distancia:,.0f} m",
            ).add_to(mapa)

polvorines_con_radio = [p for p in polvorines if p.radio_influencia_m]
if polvorines_con_radio:
    st.caption("Leyenda de radios de influencia (círculos discontinuos verdes en el mapa):")
    st.dataframe(
        pd.DataFrame(
            [
                {"Polvorín": p.nombre, "Tipo": p.tipo, "Radio de influencia (m)": p.radio_influencia_m}
                for p in polvorines_con_radio
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

st_folium(mapa, use_container_width=True, height=500)

st.header(":material/description: Reporte", divider="gray")
titulo_proyecto_p = st.text_input(
    "Título del proyecto para el reporte", value="Verificación de seguridad de polvorín"
)
buffer = build_polvorin_report(polvorines, resultados_por_polvorin, titulo_proyecto_p)
st.download_button(
    "Descargar reporte Word",
    data=buffer,
    file_name="reporte_polvorin.docx",
    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    icon=":material/download:",
    type="primary",
)
