"""Vistas tipo tablero (dashboard) de los módulos de Voladura y Polvorín.

Mismo criterio que el resto de `viz/`: aquí solo se calculan los KPI y se
arman las figuras — la disposición en pantalla (columnas, `st.metric`) la
hace cada página, para que este módulo siga siendo testeable sin
Streamlit.

No introduce ningún cálculo nuevo: todos los números salen de
`core.voladura.calcular_programa` y `core.polvorin` (EMR y distancias),
solo se agregan y se grafican.

La plataforma no usa gráficos de barras: no forman parte de un informe OTS.
En Voladura el tablero son los KPI más los esquemas 2D y 3D de cada labor
(`viz.tunnel_plot` y `viz.malla_plot`); en Polvorín, los KPI más el reparto
de cumplimiento, y el detalle de distancias va en su tabla.
"""

from __future__ import annotations

from dataclasses import dataclass

import plotly.graph_objects as go

from core.models import LaborMinera, Polvorin, PuntoRiesgo, ResultadoDistancia, ResultadoVoladura
from core.polvorin import emr_kg_polvorin

# Paleta de marca MEECSAC (muestreada del logo) + acentos de estado.
MEECSAC_DARK = "#33454E"
MEECSAC_CYAN = "#00A7E3"
COLOR_OK = "#2A9D8F"
COLOR_ALERTA = "#E63946"
COLOR_NEUTRO = "#9AA5AB"

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
