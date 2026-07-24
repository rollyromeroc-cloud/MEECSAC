"""Esquema 3D de una labor minera (túnel tipo herradura) con cotas.

Usa Plotly (ya es dependencia de la app para los demás gráficos). La
geometría pura vive en `core.geometry` — este módulo solo arma la figura:
trazos del wireframe o el sólido + líneas y textos de cota (ancho, alto,
longitud existente, avance proyectado).

El túnel se dibuja en dos tramos con colores distintos: lo ya excavado
("longitud existente", gris neutro — un hecho, no una serie de datos) y lo
que se proyecta avanzar ("avance proyectado", color de identidad).
"""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from core.geometry import malla_solida_tunel, malla_tunel, relacion_aspecto
from core.models import LaborMinera, ResultadoVoladura

# Paleta fija (no se cicla): gris neutro para lo ya construido (un hecho,
# no una serie categórica), color de identidad para lo proyectado/nuevo, y
# tinta neutra para las cotas (anotaciones, no datos).
COLOR_EXISTENTE = "#999999"
COLOR_PROYECTADO = "#88CCEE"
COLOR_FRONTERA = "#CC6677"
COLOR_COTA = "#444444"


def _agregar_cota(
    lineas: list[np.ndarray],
    p1: tuple[float, float, float],
    p2: tuple[float, float, float],
    tick_dir: tuple[float, float, float],
    tick_len: float,
) -> None:
    """Agrega una línea de cota tipo CAD: el segmento principal más una
    pequeña marca perpendicular (línea de referencia) en cada extremo."""
    a, b = np.array(p1, dtype=float), np.array(p2, dtype=float)
    lineas.append(np.array([a, b]))
    d = np.array(tick_dir, dtype=float) * (tick_len / 2.0)
    lineas.append(np.array([a - d, a + d]))
    lineas.append(np.array([b - d, b + d]))


def _linea_con_separadores(lineas: list[np.ndarray]) -> tuple[list, list, list]:
    """Concatena varias polilíneas en un solo trazo Scatter3d, separadas por
    `None` (técnica estándar de Plotly para dibujar múltiples segmentos en
    una sola traza, evitando decenas de trazas y de entradas de leyenda)."""
    xs, ys, zs = [], [], []
    for linea in lineas:
        xs.extend(linea[:, 0].tolist() + [None])
        ys.extend(linea[:, 1].tolist() + [None])
        zs.extend(linea[:, 2].tolist() + [None])
    return xs, ys, zs


def _agregar_tramo_wireframe(
    fig: go.Figure, ancho: float, alto: float, longitud: float, x_inicio: float,
    color: str, nombre_leyenda: str, n_anillos: int,
) -> None:
    if longitud <= 0:
        return
    malla = malla_tunel(ancho, alto, longitud, n_anillos=max(n_anillos, 2), x_inicio=x_inicio)
    xs, ys, zs = _linea_con_separadores(malla["anillos"])
    fig.add_trace(
        go.Scatter3d(
            x=xs, y=ys, z=zs, mode="lines",
            line=dict(color=color, width=2), name=nombre_leyenda, hoverinfo="skip",
        )
    )
    xs, ys, zs = _linea_con_separadores(malla["longitudinales"])
    fig.add_trace(
        go.Scatter3d(
            x=xs, y=ys, z=zs, mode="lines",
            line=dict(color=color, width=4), name=nombre_leyenda,
            showlegend=False, hoverinfo="skip",
        )
    )


def _cotas_comunes(
    labor: LaborMinera, longitud_total: float
) -> tuple[list[np.ndarray], list[float], list[float], list[float], list[str]]:
    """Cotas de ancho, alto, longitud existente y avance proyectado."""
    radio = labor.ancho_m / 2.0
    alto = labor.alto_m
    longitud_existente = max(labor.longitud_existente_m, 0.0)
    avance_proyectado = labor.avance_proyectado_m

    offset_frontal = max(0.5, 0.08 * longitud_total)
    offset_lateral = max(0.3, 0.15 * radio)
    offset_vertical = max(0.3, 0.15 * alto)
    tick = max(offset_vertical, offset_lateral) * 0.4
    x0 = -offset_frontal

    lineas: list[np.ndarray] = []
    tx, ty, tz, textos = [], [], [], []

    _agregar_cota(lineas, (x0, -radio, 0.0), (x0, radio, 0.0), (0, 0, 1), tick)
    tx.append(x0); ty.append(0.0); tz.append(-offset_vertical * 0.6)
    textos.append(f"Ancho: {labor.ancho_m:.2f} m")

    y_alto = -radio - offset_lateral * 1.8
    _agregar_cota(lineas, (x0, y_alto, 0.0), (x0, y_alto, alto), (0, 1, 0), tick)
    tx.append(x0); ty.append(y_alto - offset_lateral * 0.8); tz.append(alto / 2.0)
    textos.append(f"Alto: {labor.alto_m:.2f} m")

    if longitud_existente > 0:
        z_exist = -offset_vertical
        _agregar_cota(lineas, (0.0, 0.0, z_exist), (longitud_existente, 0.0, z_exist), (0, 0, 1), tick)
        tx.append(longitud_existente / 2.0); ty.append(0.0); tz.append(z_exist - offset_vertical * 0.4)
        textos.append(f"Longitud existente: {longitud_existente:.2f} m")

    z_avance = alto + offset_vertical
    _agregar_cota(
        lineas, (longitud_existente, 0.0, z_avance), (longitud_total, 0.0, z_avance), (0, 0, 1), tick
    )
    tx.append(longitud_existente + avance_proyectado / 2.0); ty.append(0.0)
    tz.append(z_avance + offset_vertical * 0.4)
    textos.append(f"Avance proyectado: {avance_proyectado:.2f} m")

    return lineas, tx, ty, tz, textos


def _layout_comun(fig: go.Figure, labor: LaborMinera, longitud_total: float) -> None:
    ratio_x, ratio_y, ratio_z = relacion_aspecto(labor.ancho_m, labor.alto_m, longitud_total)
    fig.update_layout(
        title=f"Esquema — {labor.tipo}: {labor.nombre}",
        scene=dict(
            xaxis=dict(title="Avance (m)", showbackground=False),
            yaxis=dict(title="", showbackground=False, visible=False),
            zaxis=dict(title="", showbackground=False, visible=False),
            aspectmode="manual",
            aspectratio=dict(x=ratio_x, y=ratio_y, z=ratio_z),
            camera=dict(eye=dict(x=0.75, y=0.75, z=0.45)),
        ),
        legend=dict(orientation="h", yanchor="bottom", y=0.01, x=0.01),
        margin=dict(l=0, r=0, t=40, b=30),
        annotations=[
            dict(
                text=(
                    f"Sección {labor.ancho_m:.2f} × {labor.alto_m:.2f} m — "
                    f"esquema referencial, proporciones no a escala"
                ),
                xref="paper", yref="paper", x=0.5, y=-0.02,
                showarrow=False, font=dict(color=COLOR_COTA, size=10),
            )
        ],
    )


def build_tunnel_figure(
    labor: LaborMinera,
    resultado: ResultadoVoladura,
    n_anillos: int = 16,
) -> go.Figure:
    """Wireframe 3D de la labor: tramo existente (gris) + tramo proyectado
    (color de identidad), con sus cotas."""
    longitud_existente = max(labor.longitud_existente_m, 0.0)
    avance_proyectado = max(labor.avance_proyectado_m, 0.01)
    longitud_total = longitud_existente + avance_proyectado

    fig = go.Figure()

    n_anillos_existente = (
        max(3, round(n_anillos * longitud_existente / longitud_total)) if longitud_existente > 0 else 0
    )
    n_anillos_proyectado = max(3, n_anillos - n_anillos_existente)

    _agregar_tramo_wireframe(
        fig, labor.ancho_m, labor.alto_m, longitud_existente, 0.0,
        COLOR_EXISTENTE, "Tramo existente", n_anillos_existente,
    )
    _agregar_tramo_wireframe(
        fig, labor.ancho_m, labor.alto_m, avance_proyectado, longitud_existente,
        COLOR_PROYECTADO, "Tramo proyectado", n_anillos_proyectado,
    )

    if longitud_existente > 0:
        radio = labor.ancho_m / 2.0
        fig.add_trace(
            go.Scatter3d(
                x=[longitud_existente, longitud_existente],
                y=[0.0, 0.0],
                z=[0.0, labor.alto_m],
                mode="lines",
                line=dict(color=COLOR_FRONTERA, width=3, dash="dash"),
                name="Frente actual",
                hoverinfo="skip",
            )
        )

    cota_lineas, tx, ty, tz, textos = _cotas_comunes(labor, longitud_total)
    xs, ys, zs = _linea_con_separadores(cota_lineas)
    fig.add_trace(
        go.Scatter3d(
            x=xs, y=ys, z=zs, mode="lines",
            line=dict(color=COLOR_COTA, width=2), name="Cotas", hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter3d(
            x=tx, y=ty, z=tz, mode="text", text=textos,
            textposition="middle center", textfont=dict(color=COLOR_COTA, size=12),
            name="", showlegend=False, hoverinfo="skip",
        )
    )

    _layout_comun(fig, labor, longitud_total)
    return fig


def build_tunnel_figure_solido(
    labor: LaborMinera,
    resultado: ResultadoVoladura,
    n_anillos: int = 16,
) -> go.Figure:
    """Versión sólida (superficie rellena) del mismo esquema, con el mismo
    esquema de colores existente/proyectado."""
    longitud_existente = max(labor.longitud_existente_m, 0.0)
    avance_proyectado = max(labor.avance_proyectado_m, 0.01)
    longitud_total = longitud_existente + avance_proyectado

    n_anillos_existente = (
        max(3, round(n_anillos * longitud_existente / longitud_total)) if longitud_existente > 0 else 0
    )
    n_anillos_proyectado = max(3, n_anillos - n_anillos_existente)

    malla = malla_solida_tunel(
        labor.ancho_m, labor.alto_m, longitud_existente, avance_proyectado,
        n_anillos_existente=max(n_anillos_existente, 2) if longitud_existente > 0 else 0,
        n_anillos_proyectado=n_anillos_proyectado,
    )
    vertices = malla["vertices"]
    triangulos = malla["triangulos"]
    color_por_triangulo = [
        COLOR_EXISTENTE if t == "existente" else COLOR_PROYECTADO
        for t in malla["tramo_por_triangulo"]
    ]

    fig = go.Figure()
    fig.add_trace(
        go.Mesh3d(
            x=vertices[:, 0], y=vertices[:, 1], z=vertices[:, 2],
            i=triangulos[:, 0], j=triangulos[:, 1], k=triangulos[:, 2],
            facecolor=color_por_triangulo,
            flatshading=True,
            opacity=1.0,
            hoverinfo="skip",
            showlegend=False,
        )
    )
    # trazas invisibles solo para que la leyenda muestre el significado de
    # cada color del sólido (Mesh3d con facecolor no genera leyenda propia)
    for color, nombre, activo in (
        (COLOR_EXISTENTE, "Tramo existente", longitud_existente > 0),
        (COLOR_PROYECTADO, "Tramo proyectado", True),
    ):
        if activo:
            fig.add_trace(
                go.Scatter3d(
                    x=[None], y=[None], z=[None], mode="markers",
                    marker=dict(size=8, color=color), name=nombre,
                )
            )

    if longitud_existente > 0:
        fig.add_trace(
            go.Scatter3d(
                x=[longitud_existente, longitud_existente],
                y=[0.0, 0.0],
                z=[0.0, labor.alto_m],
                mode="lines",
                line=dict(color=COLOR_FRONTERA, width=4, dash="dash"),
                name="Frente actual",
                hoverinfo="skip",
            )
        )

    cota_lineas, tx, ty, tz, textos = _cotas_comunes(labor, longitud_total)
    xs, ys, zs = _linea_con_separadores(cota_lineas)
    fig.add_trace(
        go.Scatter3d(
            x=xs, y=ys, z=zs, mode="lines",
            line=dict(color=COLOR_COTA, width=2), name="Cotas", hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter3d(
            x=tx, y=ty, z=tz, mode="text", text=textos,
            textposition="middle center", textfont=dict(color=COLOR_COTA, size=12),
            name="", showlegend=False, hoverinfo="skip",
        )
    )

    _layout_comun(fig, labor, longitud_total)
    return fig
