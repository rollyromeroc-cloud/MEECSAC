from __future__ import annotations

from pathlib import Path

import streamlit as st

from auth import require_login

LOGO_PATH = Path(__file__).resolve().parent / "assets" / "logo_meecsac.jpg"

st.set_page_config(
    page_title="Voladura & Polvorín",
    page_icon=str(LOGO_PATH),
    layout="wide",
)

require_login()
st.logo(str(LOGO_PATH), size="large")

# Estado compartido entre páginas (dura mientras la pestaña del navegador
# esté abierta; no se persiste entre sesiones — usar exportar/importar JSON
# en "Programa General" para guardar o compartir el trabajo).
st.session_state.setdefault("labores", [])
st.session_state.setdefault("polvorines", [])
st.session_state.setdefault("puntos_riesgo", [])

st.title(":material/explosion: Voladura & Polvorín")
st.caption("MEECSAC · Más que Explosivos")
st.write(
    "Automatiza el cálculo de perforación y voladura por labor minera "
    "(explosivos, accesorios, avance, tonelaje) y la verificación de "
    "distancias de seguridad de polvorines."
)

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(":material/construction: Labores cargadas", len(st.session_state["labores"]), border=True)
with col2:
    st.metric(":material/warehouse: Polvorines cargados", len(st.session_state["polvorines"]), border=True)
with col3:
    st.metric(":material/warning: Puntos de riesgo cargados", len(st.session_state["puntos_riesgo"]), border=True)

st.markdown(
    """
### ¿Cómo usar la app?

1. **🧨 Voladura** — registra cada labor minera (sección, malla de perforación,
   explosivos) y obtén de inmediato taladros, explosivo total, accesorios,
   avance, volumen, tonelaje y factor de potencia. Descarga el reporte Word.
2. **🏭 Polvorín** — registra el polvorín y los puntos de riesgo cercanos
   (poblados, vías, líneas férreas, etc.), visualízalos en el mapa y verifica
   las distancias reales contra las distancias mínimas que definas.
3. **📊 Programa General** — vista consolidada de todas las labores, gráficos
   del programa completo, y exportar/importar el proyecto como JSON para
   compartirlo entre los 3 equipos.

Usa el menú de la izquierda para navegar entre secciones.
"""
)

st.caption(
    "Nota: los datos viven en tu sesión del navegador. Para compartirlos con "
    "otra computadora, exporta el proyecto a JSON en 'Programa General' y "
    "cárgalo ahí."
)
