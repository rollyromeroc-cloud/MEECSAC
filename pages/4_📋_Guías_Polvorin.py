from pathlib import Path

import pandas as pd
import streamlit as st

from auth import require_login
from core.constants import TIPOS_SUCAMEC_GUIAS
from core.polvorin import calcular_guias

LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "logo_meecsac.jpg"

st.set_page_config(page_title="Guías de Polvorín", page_icon=str(LOGO_PATH), layout="wide")
require_login()
st.logo(str(LOGO_PATH), size="large")

st.title(":material/receipt_long: Guías de polvorín")
st.write(
    "Calcula cuántas guías de remisión se necesitan por tipo de explosivo o "
    "accesorio, según la cantidad solicitada y la capacidad máxima por guía "
    "(SUCAMEC). Si vas a solicitar más de una variante comercial de un mismo "
    "tipo (por ejemplo, dos productos de emulsión distintos), indica cuántas "
    "variantes con el número de al lado — aparecerá un campo de cantidad por "
    "cada una, y cada variante se calcula por separado sin combinarse con las "
    "demás."
)
st.caption(
    "Por ahora la capacidad por guía es la genérica de SUCAMEC según el tipo "
    "de producto; todavía no distingue entre marcas comerciales "
    "(ej. FAMESA) — eso se agregará en una siguiente etapa."
)

filas_resultado = []

for tipo in TIPOS_SUCAMEC_GUIAS:
    producto = tipo["producto"]
    capacidad = tipo["capacidad_por_guia"]
    unidad = tipo["unidad"]
    key_base = producto.replace(" ", "_").replace("é", "e").replace("ó", "o")

    with st.container(border=True):
        col_nombre, col_variantes = st.columns([3, 1])
        col_nombre.markdown(f"**{producto}** — {tipo['categoria']} · {capacidad:,} {unidad} por guía")
        n_variantes = col_variantes.number_input(
            "N.° de variantes",
            min_value=0,
            max_value=6,
            value=0,
            key=f"n_var_{key_base}",
            help="0 = no se solicita este tipo ahora.",
        )
        for i in range(int(n_variantes)):
            c1, c2 = st.columns([2, 1])
            nombre_variante = c1.text_input(
                "Nombre/marca (opcional)",
                value=producto if n_variantes == 1 else f"{producto} {i + 1}",
                key=f"nombre_{key_base}_{i}",
            )
            cantidad = c2.number_input(
                f"Cantidad solicitada ({unidad})",
                min_value=0.0,
                step=1.0,
                key=f"cantidad_{key_base}_{i}",
            )
            if cantidad > 0:
                resultado = calcular_guias(cantidad, capacidad)
                filas_resultado.append({
                    "Categoría": tipo["categoria"],
                    "Tipo (SUCAMEC)": producto,
                    "Producto/variante": nombre_variante or producto,
                    "Cantidad solicitada": cantidad,
                    "Unidad": unidad,
                    "Capacidad por guía": capacidad,
                    "Guías completas": resultado["guias_completas"],
                    "Cantidad en guías completas": resultado["cantidad_guias_completas"],
                    "Guía restante": resultado["guia_restante"],
                    "Cantidad restante": resultado["cantidad_restante"],
                    "Guías totales": resultado["guias_totales"],
                })

st.divider()
st.markdown("### Resultado")
if not filas_resultado:
    st.info("Indica al menos una cantidad solicitada arriba para ver el cálculo.")
else:
    df = pd.DataFrame(filas_resultado)
    st.dataframe(df, width="stretch", hide_index=True)
    total_guias = int(df["Guías totales"].sum())
    st.metric(":material/receipt_long: Guías totales (todas las variantes)", total_guias, border=True)

    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "Descargar tabla (CSV)",
        csv,
        "guias_polvorin.csv",
        "text/csv",
        icon=":material/download:",
    )
