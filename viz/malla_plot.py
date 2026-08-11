"""Esquema 2D de la malla de perforación (cara del frente) de una labor
minera — alivios, anillos de arranque (cuadrado→rombo, con cotas de burden
en mm) y contorno, sobre el perfil real de la sección. Ver
`core.malla_perforacion` para la geometría y las distancias.
"""

from __future__ import annotations

import plotly.graph_objects as go

from core.geometry import perfil_seccion
from core.malla_perforacion import AnilloInfo, PosicionTaladro, generar_malla_perforacion

COLOR_CONTORNO_PERFIL = "#444444"
COLOR_ALIVIO = "#882255"
COLOR_ARRANQUE = "#44AA99"
COLOR_CONTORNO_TALADRO = "#117733"
COLOR_COTA_ANILLO = "#AA4499"

_NOMBRE_CATEGORIA = {"alivio": "Alivio (sin carga)", "arranque": "Arranque/ayuda", "contorno": "Contorno"}
_COLOR_CATEGORIA = {"alivio": COLOR_ALIVIO, "arranque": COLOR_ARRANQUE, "contorno": COLOR_CONTORNO_TALADRO}
_SIMBOLO_CATEGORIA = {"alivio": "circle-open", "arranque": "circle", "contorno": "circle"}


def build_malla_perforacion_figure(
    ancho: float,
    alto: float,
    taladros_cargados: int,
    taladros_alivio: int,
    diametro_barreno_mm: float,
    diametro_alivio_mm: float | None = None,
    forma_seccion: str | None = None,
    nombre_labor: str = "",
) -> tuple[go.Figure, list[AnilloInfo]]:
    """Figura 2D (contorno de la sección + posiciones de taladro por
    categoría, con la cota de burden de cada anillo de arranque) lista para
    `st.plotly_chart`, junto con las distancias de cada anillo (para
    mostrarlas también en una tabla)."""
    malla: list[PosicionTaladro]
    anillos_info: list[AnilloInfo]
    malla, anillos_info = generar_malla_perforacion(
        ancho, alto, taladros_cargados, taladros_alivio,
        diametro_barreno_mm=diametro_barreno_mm, diametro_alivio_mm=diametro_alivio_mm,
        forma_seccion=forma_seccion,
    )
    perfil = perfil_seccion(forma_seccion, ancho, alto)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=list(perfil[:, 0]) + [perfil[0, 0]],
            y=list(perfil[:, 1]) + [perfil[0, 1]],
            mode="lines",
            line=dict(color=COLOR_CONTORNO_PERFIL, width=2),
            name="Contorno de la sección",
            hoverinfo="skip",
        )
    )

    for categoria in ("alivio", "arranque", "contorno"):
        puntos = [t for t in malla if t.categoria == categoria]
        if not puntos:
            continue
        fig.add_trace(
            go.Scatter(
                x=[t.y for t in puntos],
                y=[t.z for t in puntos],
                mode="markers",
                marker=dict(
                    size=14, color=_COLOR_CATEGORIA[categoria], symbol=_SIMBOLO_CATEGORIA[categoria],
                    line=dict(width=2, color=_COLOR_CATEGORIA[categoria]),
                ),
                name=f"{_NOMBRE_CATEGORIA[categoria]} ({len(puntos)})",
                hovertext=[
                    f"{_NOMBRE_CATEGORIA[categoria]} — anillo {t.anillo}" if t.anillo else _NOMBRE_CATEGORIA[categoria]
                    for t in puntos
                ],
                hoverinfo="text",
            )
        )

    centro_y, centro_z = 0.0, alto / 2.0
    for info in anillos_info:
        # etiqueta de cota (burden en mm) sobre el eje +y del anillo, como
        # las cotas numéricas de un software de diseño de malla
        radio_m = info.burden_mm / 1000.0
        fig.add_annotation(
            x=centro_y + radio_m, y=centro_z,
            text=f"B{info.anillo}: {info.burden_mm:.0f} mm",
            showarrow=False, yshift=12,
            font=dict(color=COLOR_COTA_ANILLO, size=10),
        )

    titulo = f"Malla de perforación — {nombre_labor}" if nombre_labor else "Malla de perforación"
    fig.update_layout(
        title=titulo,
        xaxis=dict(title="", showgrid=False, zeroline=False, scaleanchor="y", scaleratio=1),
        yaxis=dict(title="", showgrid=False, zeroline=False),
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, x=0.0),
        margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig, anillos_info
