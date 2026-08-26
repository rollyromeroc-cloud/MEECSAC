"""Vistas tipo tablero (dashboard) de los módulos de Voladura y Polvorín.

Mismo criterio que el resto de `viz/`: aquí solo se calculan los KPI y se
arman las figuras — la disposición en pantalla (columnas, `st.metric`) la
hace cada página, para que este módulo siga siendo testeable sin
Streamlit.

No introduce ningún cálculo nuevo: todos los números salen de
`core.voladura.calcular_programa` y `core.polvorin` (EMR y distancias),
solo se agregan y se grafican.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from core.constants import ORDEN_ETAPAS
from core.models import LaborMinera, Polvorin, PuntoRiesgo, ResultadoDistancia, ResultadoVoladura
from core.polvorin import emr_kg_polvorin

# Paleta de marca MEECSAC (muestreada del logo) + acentos de estado.
MEECSAC_DARK = "#33454E"
MEECSAC_CYAN = "#00A7E3"
COLOR_OK = "#2A9D8F"
COLOR_ALERTA = "#E63946"
COLOR_NEUTRO = "#9AA5AB"
# Serie categórica fija (no se cicla): explosivo tipo 1 / tipo 2.
COLOR_TIPO1 = "#88CCEE"
COLOR_TIPO2 = "#CC6677"

_PLANTILLA = "plotly_white"


@dataclass
class Kpi:
    """Una tarjeta del tablero. `ayuda` es opcional y explica de dónde sale
    la cifra, para que el número nunca quede sin trazabilidad."""
    etiqueta: str
    valor: str
    icono: str
    ayuda: str | None = None


def _fig_vacia(mensaje: str) -> go.Figure:
    """Figura con un mensaje centrado — para cuando no hay datos que
    graficar todavía (evita un gráfico vacío sin explicación)."""
    fig = go.Figure()
    fig.add_annotation(
        text=mensaje, xref="paper", yref="paper", x=0.5, y=0.5,
        showarrow=False, font=dict(color=COLOR_NEUTRO, size=13),
    )
    fig.update_layout(
        template=_PLANTILLA, xaxis=dict(visible=False), yaxis=dict(visible=False),
        margin=dict(l=10, r=10, t=40, b=10), height=280,
    )
    return fig


# --------------------------------------------------------------------------
# Voladura
# --------------------------------------------------------------------------


def kpis_voladura(
    labores: list[LaborMinera], resultados: list[ResultadoVoladura]
) -> list[Kpi]:
    """Tarjetas del tablero de Voladura, agregando todo el programa."""
    avance = sum(l.avance_proyectado_m for l in labores)
    disparos = sum(r.n_disparos for r in resultados)
    explosivo = sum(r.explosivo_total_kg for r in resultados)
    tonelaje = sum(r.tonelaje_total_tm for r in resultados)
    # factor de potencia del programa = explosivo total / tonelaje total —
    # NO el promedio de los factores por labor, que daría un valor distinto
    # (media de cocientes ≠ cociente de sumas) y sin significado físico.
    factor = explosivo / tonelaje if tonelaje > 0 else 0.0
    return [
        Kpi("Labores", f"{len(labores):,}", ":material/account_tree:"),
        Kpi("Avance programado", f"{avance:,.2f} m", ":material/straighten:"),
        Kpi("Disparos", f"{disparos:,}", ":material/bolt:"),
        Kpi("Explosivo total", f"{explosivo:,.2f} kg", ":material/explosion:"),
        Kpi("Tonelaje total", f"{tonelaje:,.2f} TM", ":material/scale:"),
        Kpi(
            "Factor de potencia", f"{factor:,.3f} kg/TM", ":material/speed:",
            ayuda="Explosivo total ÷ tonelaje total del programa (no el promedio de los factores por labor).",
        ),
    ]


def _df_voladura(
    labores: list[LaborMinera], resultados: list[ResultadoVoladura]
) -> pd.DataFrame:
    df = pd.DataFrame(
        [
            {
                "Labor": l.nombre,
                "Tipo": l.tipo,
                "Etapa": l.etapa,
                "Destino": l.destino_material,
                "Avance (m)": l.avance_proyectado_m,
                "Disparos": r.n_disparos,
                "Tonelaje (TM)": r.tonelaje_total_tm,
                "Explosivo (kg)": r.explosivo_total_kg,
                "Explosivo tipo 1 (kg)": r.explosivo_tipo1_kg,
                "Explosivo tipo 2 (kg)": r.explosivo_tipo2_kg,
                "Factor de potencia (kg/TM)": r.factor_potencia_kg_tm,
            }
            for l, r in zip(labores, resultados)
        ]
    )
    if not df.empty:
        df["Etapa"] = pd.Categorical(df["Etapa"], categories=ORDEN_ETAPAS, ordered=True)
        df = df.sort_values(["Etapa", "Labor"])
    return df


def fig_avance_tonelaje_por_labor(
    labores: list[LaborMinera], resultados: list[ResultadoVoladura]
) -> go.Figure:
    """Avance (barras) y tonelaje (línea, eje secundario) por labor — las
    dos magnitudes del programa que se leen juntas, en distinta unidad."""
    df = _df_voladura(labores, resultados)
    if df.empty:
        return _fig_vacia("Sin labores registradas")
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df["Labor"], y=df["Avance (m)"], name="Avance (m)",
            marker_color=MEECSAC_CYAN,
            hovertemplate="%{x}<br>Avance: %{y:,.2f} m<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["Labor"], y=df["Tonelaje (TM)"], name="Tonelaje (TM)",
            mode="lines+markers", yaxis="y2",
            line=dict(color=MEECSAC_DARK, width=2),
            hovertemplate="%{x}<br>Tonelaje: %{y:,.2f} TM<extra></extra>",
        )
    )
    fig.update_layout(
        template=_PLANTILLA, title="Avance y tonelaje por labor",
        yaxis=dict(title="Avance (m)"),
        yaxis2=dict(title="Tonelaje (TM)", overlaying="y", side="right", showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        margin=dict(l=10, r=10, t=60, b=10), height=340,
    )
    return fig


def fig_tonelaje_por_etapa(
    labores: list[LaborMinera], resultados: list[ResultadoVoladura]
) -> go.Figure:
    """Tonelaje por etapa, separado por destino del material (mineral vs
    desmonte) — la lectura que interesa para producción."""
    df = _df_voladura(labores, resultados)
    if df.empty:
        return _fig_vacia("Sin labores registradas")
    agrupado = df.groupby(["Etapa", "Destino"], observed=True)["Tonelaje (TM)"].sum().reset_index()
    fig = px.bar(
        agrupado, x="Etapa", y="Tonelaje (TM)", color="Destino",
        title="Tonelaje por etapa y destino del material",
        color_discrete_map={"Mineral": MEECSAC_CYAN, "Desmonte": COLOR_NEUTRO},
    )
    fig.update_layout(
        template=_PLANTILLA, margin=dict(l=10, r=10, t=60, b=10), height=340,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    return fig


def fig_explosivo_por_tipo(
    labores: list[LaborMinera], resultados: list[ResultadoVoladura]
) -> go.Figure:
    """Reparto del explosivo entre los dos tipos declarados, por labor."""
    df = _df_voladura(labores, resultados)
    if df.empty:
        return _fig_vacia("Sin labores registradas")
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df["Labor"], y=df["Explosivo tipo 1 (kg)"], name="Explosivo tipo 1",
            marker_color=COLOR_TIPO1,
            hovertemplate="%{x}<br>Tipo 1: %{y:,.2f} kg<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            x=df["Labor"], y=df["Explosivo tipo 2 (kg)"], name="Explosivo tipo 2",
            marker_color=COLOR_TIPO2,
            hovertemplate="%{x}<br>Tipo 2: %{y:,.2f} kg<extra></extra>",
        )
    )
    fig.update_layout(
        template=_PLANTILLA, barmode="stack", title="Explosivo por tipo y labor",
        yaxis=dict(title="Explosivo (kg)"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        margin=dict(l=10, r=10, t=60, b=10), height=340,
    )
    return fig


def fig_factor_potencia(
    labores: list[LaborMinera], resultados: list[ResultadoVoladura]
) -> go.Figure:
    """Factor de potencia por labor, con la referencia del programa — para
    ver de un vistazo qué labor se sale del promedio."""
    df = _df_voladura(labores, resultados)
    if df.empty:
        return _fig_vacia("Sin labores registradas")
    explosivo = sum(r.explosivo_total_kg for r in resultados)
    tonelaje = sum(r.tonelaje_total_tm for r in resultados)
    referencia = explosivo / tonelaje if tonelaje > 0 else 0.0
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df["Labor"], y=df["Factor de potencia (kg/TM)"], name="Factor de potencia",
            marker_color=MEECSAC_DARK,
            hovertemplate="%{x}<br>%{y:,.3f} kg/TM<extra></extra>",
        )
    )
    if referencia > 0:
        fig.add_hline(
            y=referencia, line_dash="dash", line_color=COLOR_ALERTA,
            annotation_text=f"Programa: {referencia:,.3f} kg/TM",
            annotation_position="top left",
        )
    fig.update_layout(
        template=_PLANTILLA, title="Factor de potencia por labor",
        yaxis=dict(title="kg/TM"), showlegend=False,
        margin=dict(l=10, r=10, t=60, b=10), height=340,
    )
    return fig


# --------------------------------------------------------------------------
# Polvorín
# --------------------------------------------------------------------------


def kpis_polvorin(
    polvorines: list[Polvorin],
    puntos: list[PuntoRiesgo],
    resultados_por_polvorin: dict[str, list[ResultadoDistancia]],
) -> list[Kpi]:
    """Tarjetas del tablero de Polvorín. El EMR total solo suma los
    polvorines que tienen composición registrada (ver
    `core.polvorin.emr_kg_polvorin`); los que no, no se asumen en 0 kg de
    producto sino que se cuentan aparte."""
    emrs = [emr_kg_polvorin(p) for p in polvorines]
    con_emr = [e for e in emrs if e is not None]
    todos = [r for lista in resultados_por_polvorin.values() for r in lista]
    cumplen = sum(1 for r in todos if r.cumple)
    pct = (cumplen / len(todos) * 100.0) if todos else 0.0
    return [
        Kpi("Polvorines", f"{len(polvorines):,}", ":material/warehouse:"),
        Kpi("Puntos de riesgo", f"{len(puntos):,}", ":material/warning:"),
        Kpi(
            "EMR total", f"{sum(con_emr):,.2f} kg", ":material/scale:",
            ayuda=(
                f"Equivalente en kg de dinamita 60%, sumando los {len(con_emr)} de "
                f"{len(polvorines)} polvorines con composición registrada."
            ),
        ),
        Kpi("Verificaciones", f"{len(todos):,}", ":material/rule:"),
        Kpi("Cumplen", f"{cumplen:,}", ":material/check_circle:"),
        Kpi(
            "Cumplimiento", f"{pct:,.1f} %", ":material/verified:",
            ayuda="Contra la distancia mínima que confirmaste en cada punto de riesgo, no contra la sugerencia de la Tabla K.",
        ),
    ]


def fig_distancias_vs_minima(
    resultados_por_polvorin: dict[str, list[ResultadoDistancia]],
) -> go.Figure:
    """Distancia real vs. la mínima requerida, por par polvorín–punto. La
    barra se colorea por cumplimiento y la mínima va como marcador, para
    que la brecha se lea directamente."""
    filas = [
        {
            "Par": f"{nombre} → {r.punto_nombre}",
            "Real (m)": r.distancia_real_m,
            "Mínima (m)": r.distancia_minima_m,
            "Estado": "Cumple" if r.cumple else "No cumple",
        }
        for nombre, lista in resultados_por_polvorin.items()
        for r in lista
    ]
    if not filas:
        return _fig_vacia("Sin puntos de riesgo registrados")
    df = pd.DataFrame(filas).sort_values("Real (m)")
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df["Real (m)"], y=df["Par"], orientation="h", name="Distancia real",
            marker_color=[COLOR_OK if e == "Cumple" else COLOR_ALERTA for e in df["Estado"]],
            hovertemplate="%{y}<br>Real: %{x:,.2f} m<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["Mínima (m)"], y=df["Par"], mode="markers", name="Mínima requerida",
            marker=dict(symbol="line-ns", size=16, line=dict(color=MEECSAC_DARK, width=3)),
            hovertemplate="%{y}<br>Mínima: %{x:,.2f} m<extra></extra>",
        )
    )
    fig.update_layout(
        template=_PLANTILLA, title="Distancia real vs. mínima requerida",
        xaxis=dict(title="Distancia (m)"), yaxis=dict(title=""),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        margin=dict(l=10, r=10, t=60, b=10),
        height=max(320, 40 * len(df) + 120),
    )
    return fig


def fig_holgura_por_punto(
    resultados_por_polvorin: dict[str, list[ResultadoDistancia]],
) -> go.Figure:
    """Holgura (distancia real − mínima) por par: negativa = incumplimiento
    y cuánto falta, positiva = margen disponible."""
    filas = [
        {
            "Par": f"{nombre} → {r.punto_nombre}",
            "Holgura (m)": r.distancia_real_m - r.distancia_minima_m,
        }
        for nombre, lista in resultados_por_polvorin.items()
        for r in lista
    ]
    if not filas:
        return _fig_vacia("Sin puntos de riesgo registrados")
    df = pd.DataFrame(filas).sort_values("Holgura (m)")
    fig = go.Figure(
        go.Bar(
            x=df["Holgura (m)"], y=df["Par"], orientation="h",
            marker_color=[COLOR_OK if v >= 0 else COLOR_ALERTA for v in df["Holgura (m)"]],
            hovertemplate="%{y}<br>Holgura: %{x:,.2f} m<extra></extra>",
        )
    )
    fig.add_vline(x=0, line_color=MEECSAC_DARK, line_width=1)
    fig.update_layout(
        template=_PLANTILLA, title="Holgura sobre la distancia mínima",
        xaxis=dict(title="Metros (negativo = incumple)"), yaxis=dict(title=""),
        showlegend=False, margin=dict(l=10, r=10, t=60, b=10),
        height=max(320, 40 * len(df) + 120),
    )
    return fig


def fig_emr_por_polvorin(polvorines: list[Polvorin]) -> go.Figure:
    """EMR (kg equivalente dinamita 60%) de cada polvorín con composición
    registrada — los que no la tienen se omiten, no se dibujan en 0."""
    filas = [
        {"Polvorín": p.nombre, "EMR (kg)": emr, "Tipo": p.tipo}
        for p, emr in ((p, emr_kg_polvorin(p)) for p in polvorines)
        if emr is not None
    ]
    if not filas:
        return _fig_vacia("Ningún polvorín tiene composición registrada todavía")
    df = pd.DataFrame(filas).sort_values("EMR (kg)", ascending=False)
    fig = px.bar(
        df, x="Polvorín", y="EMR (kg)", color="Tipo",
        title="EMR por polvorín (kg equiv. dinamita 60%)",
        color_discrete_map={"Explosivos": COLOR_ALERTA, "Accesorios": MEECSAC_CYAN},
    )
    fig.update_layout(
        template=_PLANTILLA, margin=dict(l=10, r=10, t=60, b=10), height=340,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    return fig


def fig_estado_cumplimiento(
    resultados_por_polvorin: dict[str, list[ResultadoDistancia]],
) -> go.Figure:
    """Reparto cumple / no cumple sobre el total de verificaciones."""
    todos = [r for lista in resultados_por_polvorin.values() for r in lista]
    if not todos:
        return _fig_vacia("Sin puntos de riesgo registrados")
    cumplen = sum(1 for r in todos if r.cumple)
    fig = go.Figure(
        go.Pie(
            labels=["Cumple", "No cumple"],
            values=[cumplen, len(todos) - cumplen],
            hole=0.55,
            marker=dict(colors=[COLOR_OK, COLOR_ALERTA]),
            sort=False,
        )
    )
    fig.update_layout(
        template=_PLANTILLA, title="Estado de cumplimiento",
        margin=dict(l=10, r=10, t=60, b=10), height=340,
    )
    return fig
