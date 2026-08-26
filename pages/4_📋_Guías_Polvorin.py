from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from auth import require_login
from core.constants import TIPOS_SUCAMEC_GUIAS
from core.guias_sucamec import ProductoGuia, generar_zip_guias
from core.models import PolvorinGuiaSucamec
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

# --- Solicitudes: el polvorín NO se pide — su dirección y resolución de
# subdirección (FAMESA-Huaral) ya están correctas en la plantilla por
# defecto. Por cada solicitud solo se completa la concesión de destino y la
# resolución de gerencia relacionada con esa solicitud.
st.divider()
st.markdown("### Solicitudes")
st.caption(
    "La plantilla por defecto ya trae la dirección y la resolución de subdirección de "
    "FAMESA (Huaral). Por cada solicitud completa la concesión de destino y la resolución "
    "de gerencia, que encabeza los dos tipos de guía. Si tu planta de origen no es la de "
    "la plantilla, puedes sobreescribir su dirección abajo; sube tus propias plantillas "
    "solo si necesitas cambiar algo más del formato."
)

n_polvorines = st.number_input(
    "N.° de solicitudes", min_value=0, max_value=8, value=st.session_state.get("n_polvorines", 0),
    key="n_polvorines",
)

polvorines: dict[str, PolvorinGuiaSucamec] = {}
for i in range(int(n_polvorines)):
    with st.expander(f"Solicitud N.° {i + 1}", expanded=(i == 0)):
        nombre_polvorin = st.text_input(
            "Nombre de la solicitud/guía", value=f"Solicitud N.° {i + 1}", key=f"polv_nombre_{i}",
        )

        st.markdown("**N.° de resolución de gerencia relacionada con la solicitud**")
        st.caption(
            "Encabeza las dos guías (sección I del formato) y además llena el bloque de "
            "autorización excepcional del destino en el tipo 2."
        )
        rg1, rg2 = st.columns(2)
        resolucion_gerencia_numero = rg1.text_input(
            "N.° de resolución", key=f"polv_res_ger_num_{i}",
            placeholder="Ej. 01463-2026-SUCAMEC/DEPP-SDAEPP",
        )
        resolucion_gerencia_fecha = rg2.text_input(
            "Fecha de emisión (DD/MM/AAAA)", key=f"polv_res_ger_fecha_{i}",
            placeholder="Ej. 12/05/2026",
        )

        st.markdown("**Planta de origen del tipo 1 (FAMESA por defecto)**")
        st.caption("Déjalo vacío para conservar la dirección que ya trae la plantilla.")
        origen_direccion = st.text_input(
            "Dirección de origen", key=f"polv_origen_dir_{i}",
            placeholder="Ej. KM 57 DE LA PANAMERICANA NORTE INCAPAMPA",
        )
        od1, od2, od3 = st.columns(3)
        origen_distrito = od1.text_input("Distrito de origen", key=f"polv_origen_distrito_{i}")
        origen_provincia = od2.text_input("Provincia de origen", key=f"polv_origen_provincia_{i}")
        origen_departamento = od3.text_input("Región/Depto. de origen", key=f"polv_origen_departamento_{i}")

        st.markdown("**Concesión / unidad minera de destino**")
        cm1, cm2 = st.columns(2)
        concesion_nombre = cm1.text_input("Nombre de la concesión", key=f"polv_conc_nombre_{i}")
        concesion_codigo = cm2.text_input("Código único", key=f"polv_conc_codigo_{i}")
        cd1, cd2, cd3 = st.columns(3)
        concesion_distrito = cd1.text_input("Distrito", key=f"polv_conc_distrito_{i}")
        concesion_provincia = cd2.text_input("Provincia", key=f"polv_conc_provincia_{i}")
        concesion_departamento = cd3.text_input("Región/Departamento", key=f"polv_conc_departamento_{i}")

        with st.expander("¿Polvorín distinto a FAMESA (Huaral)? Sube tus propias plantillas", expanded=False):
            st.caption("Si no subes nada aquí, se usa la plantilla FAMESA (Huaral) por defecto de la app.")
            pt1, pt2, pt3 = st.columns(3)
            archivo_tipo1_explosivos = pt1.file_uploader(
                "Base TIPO 1 — Explosivos", type=["xlsx"], key=f"polv_plantilla_t1e_{i}",
            )
            archivo_tipo1_accesorios = pt2.file_uploader(
                "Base TIPO 1 — Accesorios", type=["xlsx"], key=f"polv_plantilla_t1a_{i}",
            )
            archivo_tipo2 = pt3.file_uploader(
                "Base TIPO 2", type=["xlsx"], key=f"polv_plantilla_t2_{i}",
            )

        polvorin = PolvorinGuiaSucamec(
            nombre=nombre_polvorin or f"Solicitud N.° {i + 1}",
            plantilla_tipo1_explosivos=archivo_tipo1_explosivos.getvalue() if archivo_tipo1_explosivos else None,
            plantilla_tipo1_accesorios=archivo_tipo1_accesorios.getvalue() if archivo_tipo1_accesorios else None,
            plantilla_tipo2=archivo_tipo2.getvalue() if archivo_tipo2 else None,
            concesion_nombre=concesion_nombre,
            concesion_codigo=concesion_codigo,
            concesion_distrito=concesion_distrito,
            concesion_provincia=concesion_provincia,
            concesion_departamento=concesion_departamento,
            resolucion_gerencia_numero=resolucion_gerencia_numero,
            resolucion_gerencia_fecha=resolucion_gerencia_fecha,
            origen_direccion=origen_direccion,
            origen_distrito=origen_distrito,
            origen_provincia=origen_provincia,
            origen_departamento=origen_departamento,
        )
        polvorines[polvorin.nombre] = polvorin

nombres_polvorines = list(polvorines.keys())

st.divider()
st.markdown("### Productos")

filas_resultado = []
productos_guia: list[ProductoGuia] = []

for tipo in TIPOS_SUCAMEC_GUIAS:
    producto = tipo["producto"]
    capacidad = tipo["capacidad_por_guia"]
    unidad = tipo["unidad"]
    categoria = tipo["categoria"]
    key_base = producto.replace(" ", "_").replace("é", "e").replace("ó", "o")

    with st.container(border=True):
        col_nombre, col_variantes = st.columns([3, 1])
        col_nombre.markdown(f"**{producto}** — {categoria} · {capacidad:,} {unidad} por guía")
        n_variantes = col_variantes.number_input(
            "N.° de variantes",
            min_value=0,
            max_value=6,
            value=0,
            key=f"n_var_{key_base}",
            help="0 = no se solicita este tipo ahora.",
        )
        for i in range(int(n_variantes)):
            if nombres_polvorines:
                c1, c2, c3 = st.columns([2, 1, 2])
            else:
                c1, c2 = st.columns([2, 1])
                c3 = None
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
            polvorin_asignado = None
            if c3 is not None:
                seleccion = c3.selectbox(
                    "Solicitud asignada", nombres_polvorines, key=f"polvorin_sel_{key_base}_{i}",
                )
                polvorin_asignado = polvorines.get(seleccion)
            if cantidad > 0:
                resultado = calcular_guias(cantidad, capacidad)
                filas_resultado.append({
                    "Categoría": categoria,
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
                    "Solicitud": polvorin_asignado.nombre if polvorin_asignado else "(sin asignar)",
                })
                if polvorin_asignado is not None:
                    productos_guia.append(ProductoGuia(
                        nombre_variante=nombre_variante or producto,
                        categoria=categoria,
                        producto_sucamec=producto,
                        cantidad_solicitada=cantidad,
                        capacidad_por_guia=capacidad,
                        unidad_abrev=unidad,
                        polvorin=polvorin_asignado,
                    ))

st.divider()
st.markdown("### Resultado")
if not filas_resultado:
    st.info("Indica al menos una cantidad solicitada arriba para ver el cálculo.")
else:
    df = pd.DataFrame(filas_resultado)
    st.dataframe(df, width="stretch", hide_index=True)
    total_guias = int(df["Guías totales"].sum())
    st.metric(":material/receipt_long: Guías totales (todas las variantes)", total_guias, border=True)

    buffer_excel = BytesIO()
    with pd.ExcelWriter(buffer_excel, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Guías de polvorín")
    st.download_button(
        "Descargar tabla (Excel)",
        buffer_excel.getvalue(),
        "guias_polvorin.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        icon=":material/download:",
    )

    st.divider()
    st.markdown("### Excel SUCAMEC (tipo 1 y tipo 2) por guía")
    if not nombres_polvorines:
        st.warning("Define al menos una solicitud arriba y asígnala a cada producto para poder generar los Excel.")
    elif not productos_guia:
        st.warning("Asigna una solicitud a cada producto/variante con cantidad solicitada para generar los Excel.")
    else:
        st.caption(
            "Se genera un Excel TIPO 1 (FAMESA→Polvorín) y un Excel TIPO 2 (Polvorín→Unidad "
            "minera) por cada guía individual — si un producto requiere 9 guías, se generan "
            "9 pares de Excel para ese producto, cada uno con la cantidad exacta de esa guía "
            "(las completas con la capacidad máxima, la última con el restante)."
        )
        archivo_firma = st.file_uploader(
            "Firma (imagen, opcional)",
            type=["png", "jpg", "jpeg"],
            key="guias_firma",
            help="Se inserta en la misma posición (sobre 'FIRMA O HUELLA DIGITAL DEL "
            "REPRESENTANTE LEGAL') en todos los Excel generados.",
        )
        if st.button("Generar Excel SUCAMEC (.zip)", icon=":material/table_view:"):
            firma_bytes = archivo_firma.getvalue() if archivo_firma else None
            zip_buffer, resumen = generar_zip_guias(productos_guia, firma_bytes)
            st.session_state.guias_zip = zip_buffer.getvalue()
            st.session_state.guias_resumen = resumen

        resumen_guardado = st.session_state.get("guias_resumen")
        if resumen_guardado:
            st.dataframe(pd.DataFrame(resumen_guardado), width="stretch", hide_index=True)
            st.download_button(
                "Descargar Excel SUCAMEC (.zip)",
                st.session_state.guias_zip,
                "guias_sucamec.zip",
                "application/zip",
                icon=":material/download:",
            )
