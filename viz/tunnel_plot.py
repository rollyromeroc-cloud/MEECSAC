"""Esquema 3D de una labor minera (túnel tipo herradura) con cotas.

Usa Plotly (ya es dependencia de la app para los demás gráficos). La
geometría pura vive en `core.geometry` — este módulo solo arma la figura:
trazos del wireframe + líneas y textos de cota (ancho, alto, avance).
"""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from core.geometry import malla_tunel, relacion_aspecto
from core.models import LaborMinera, ResultadoVoladura

# Paleta fija (no se cicla): color de identidad para la sección del túnel,
# color distinto para el eje longitudinal, y tinta neutra para las cotas
# (las cotas son anotaciones, no series de datos).
COLOR_SECCION = "#88CCEE"
COLOR_EJE = "#CC6677"
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


def build_tunnel_figure(
    labor: LaborMinera,
    resultado: ResultadoVoladura,
    n_anillos: int = 16,
) -> go.Figure:
    """Construye el wireframe 3D de la labor con sus cotas principales."""
    longitud = max(labor.avance_proyectado_m, 0.01)
    malla = malla_tunel(labor.ancho_m, labor.alto_m, longitud, n_anillos=n_anillos)

    radio = labor.ancho_m / 2.0
    alto = labor.alto_m

    fig = go.Figure()

    # Anillos (secciones transversales a lo largo del avance)
    xs, ys, zs = _linea_con_separadores(malla["anillos"])
    fig.add_trace(
        go.Scatter3d(
            x=xs, y=ys, z=zs,
            mode="lines",
            line=dict(color=COLOR_SECCION, width=2),
            name="Sección",
            hoverinfo="skip",
        )
    )

    # Líneas longitudinales (eje del avance en piso y corona)
    xs, ys, zs = _linea_con_separadores(malla["longitudinales"])
    fig.add_trace(
        go.Scatter3d(
            x=xs, y=ys, z=zs,
            mode="lines",
            line=dict(color=COLOR_EJE, width=4),
            name="Eje del avance",
            hoverinfo="skip",
        )
    )

    # --- Cotas ---
    offset_frontal = max(0.5, 0.08 * longitud)
    offset_lateral = max(0.3, 0.15 * radio)
    offset_vertical = max(0.3, 0.15 * alto)
    x0 = -offset_frontal

    cota_lineas = []
    cota_textos_x, cota_textos_y, cota_textos_z, cota_textos = [], [], [], []
    tick = max(offset_vertical, offset_lateral) * 0.4

    # Cota de ancho: barra horizontal a la entrada, a nivel de piso
    # (marcas de referencia verticales, perpendiculares a la barra)
    _agregar_cota(cota_lineas, (x0, -radio, 0.0), (x0, radio, 0.0), (0, 0, 1), tick)
    cota_textos_x.append(x0)
    cota_textos_y.append(0.0)
    cota_textos_z.append(-offset_vertical * 0.6)
    cota_textos.append(f"Ancho: {labor.ancho_m:.2f} m")

    # Cota de alto: barra vertical a la entrada, al costado izquierdo
    # (marcas de referencia horizontales)
    y_alto = -radio - offset_lateral * 1.8
    _agregar_cota(cota_lineas, (x0, y_alto, 0.0), (x0, y_alto, alto), (0, 1, 0), tick)
    cota_textos_x.append(x0)
    cota_textos_y.append(y_alto - offset_lateral * 0.8)
    cota_textos_z.append(alto / 2.0)
    cota_textos.append(f"Alto: {labor.alto_m:.2f} m")

    # Cota de avance: barra longitudinal por encima de la corona
    # (marcas de referencia verticales en cada extremo)
    z_avance = alto + offset_vertical
    _agregar_cota(cota_lineas, (0.0, 0.0, z_avance), (longitud, 0.0, z_avance), (0, 0, 1), tick)
    cota_textos_x.append(longitud / 2.0)
    cota_textos_y.append(0.0)
    cota_textos_z.append(z_avance + offset_vertical * 0.4)
    cota_textos.append(f"Avance proyectado: {labor.avance_proyectado_m:.2f} m")

    xs, ys, zs = _linea_con_separadores(cota_lineas)
    fig.add_trace(
        go.Scatter3d(
            x=xs, y=ys, z=zs,
            mode="lines",
            line=dict(color=COLOR_COTA, width=2),
            name="Cotas",
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter3d(
            x=cota_textos_x, y=cota_textos_y, z=cota_textos_z,
            mode="text",
            text=cota_textos,
            textposition="middle center",
            textfont=dict(color=COLOR_COTA, size=12),
            name="",
            showlegend=False,
            hoverinfo="skip",
        )
    )

    ratio_x, ratio_y, ratio_z = relacion_aspecto(labor.ancho_m, labor.alto_m, longitud)
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
                xref="paper", yref="paper",
                x=0.5, y=-0.02,
                showarrow=False,
                font=dict(color=COLOR_COTA, size=10),
            )
        ],
    )
    return fig
