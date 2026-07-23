"""Gate de contraseña simple para mantener la app privada.

La contraseña se define en `st.secrets["APP_PASSWORD"]` (panel de Secrets de
Streamlit Community Cloud, o `.streamlit/secrets.toml` local — nunca se
commitea). Si no hay contraseña configurada (ej. desarrollo local sin
secrets.toml), se deja pasar con una advertencia, para no bloquear el
desarrollo.
"""

from __future__ import annotations

import streamlit as st


def require_login() -> None:
    try:
        password = st.secrets.get("APP_PASSWORD")
    except Exception:
        password = None

    if not password:
        st.sidebar.warning(
            "⚠️ APP_PASSWORD no configurado — la app está sin protección "
            "de contraseña (solo debería pasar esto en desarrollo local)."
        )
        return

    if st.session_state.get("autenticado"):
        return

    st.title("🔒 Acceso privado")
    st.write("Ingresa la contraseña del equipo para continuar.")
    intento = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if intento == password:
            st.session_state["autenticado"] = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta.")

    st.stop()
