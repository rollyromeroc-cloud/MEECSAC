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

from core.constants import LABORES_VERTICALES
from core.geometry import (
    anillos_de_avance_mensual,
    anillos_de_avance_mensual_pique,
    malla_solida_pique,
    malla_solida_tunel,
    malla_tunel,
    malla_tunel_pique,
    relacion_aspecto,
)
from core.models import LaborMinera, ResultadoVoladura

# Paleta fija (no se cicla): gris neutro para lo ya construido (un hecho,
# no una serie categórica), color de identidad para lo proyectado/nuevo, y
# tinta neutra para las cotas (anotaciones, no datos).
COLOR_EXISTENTE = "#999999"
COLOR_PROYECTADO = "#88CCEE"
COLOR_FRONTERA = "#CC6677"
COLOR_COTA = "#444444"
COLOR_ANILLO_MES = "#DDCC77"


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
    color: str, nombre_leyenda: str, n_anillos: int, forma: str | None = None,
) -> None:
    if longitud <= 0:
        return
    malla = malla_tunel(ancho, alto, longitud, n_anillos=max(n_anillos, 2), x_inicio=x_inicio, forma=forma)
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


def _agregar_tramo_wireframe_pique(
    fig: go.Figure, diametro: float, longitud: float, z_inicio: float,
    color: str, nombre_leyenda: str, n_anillos: int,
) -> None:
    if longitud <= 0:
        return
    malla = malla_tunel_pique(diametro, longitud, n_anillos=max(n_anillos, 2), z_inicio=z_inicio)
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


def _agregar_anillos_avance_mensual(
    fig: go.Figure, anillos: list[np.ndarray], vertical: bool, offset_etiqueta: float,
) -> None:
    """Dibuja los anillos de avance mensual (`core.geometry.anillos_de_avance_mensual*`)
    sobre la figura, con una etiqueta "Mes k" por anillo — para identificar
    de un vistazo cuánto avance corresponde a cada mes de la programación."""
    if not anillos:
        return
    xs, ys, zs = _linea_con_separadores(anillos)
    fig.add_trace(
        go.Scatter3d(
            x=xs, y=ys, z=zs, mode="lines",
            line=dict(color=COLOR_ANILLO_MES, width=4, dash="dot"),
            name="Avance mensual programado", hoverinfo="skip",
        )
    )
    tx, ty, tz, textos = [], [], [], []
    for mes, anillo in enumerate(anillos, start=1):
        if vertical:
            tx.append(offset_etiqueta); ty.append(0.0); tz.append(anillo[0, 2])
        else:
            tx.append(anillo[0, 0]); ty.append(0.0); tz.append(offset_etiqueta)
        textos.append(f"Mes {mes}")
    fig.add_trace(
        go.Scatter3d(
            x=tx, y=ty, z=tz, mode="text", text=textos,
            textposition="middle center", textfont=dict(color=COLOR_ANILLO_MES, size=11),
            name="", showlegend=False, hoverinfo="skip",
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


def _cotas_verticales(
    labor: LaborMinera, longitud_total: float
) -> tuple[list[np.ndarray], list[float], list[float], list[float], list[str]]:
    """Cotas de diámetro, profundidad/altura existente y avance proyectado
    para Pique/Chimenea (extrusión local a lo largo de Z)."""
    radio = labor.ancho_m / 2.0
    longitud_existente = max(labor.longitud_existente_m, 0.0)
    avance_proyectado = labor.avance_proyectado_m

    offset_vertical = max(0.5, 0.08 * longitud_total)
    offset_lateral = max(0.3, 0.3 * radio)
    tick = max(offset_vertical, offset_lateral) * 0.4
    z0 = -offset_vertical

    lineas: list[np.ndarray] = []
    tx, ty, tz, textos = [], [], [], []

    _agregar_cota(lineas, (-radio, 0.0, z0), (radio, 0.0, z0), (0, 1, 0), tick)
    tx.append(0.0); ty.append(0.0); tz.append(z0 - offset_vertical * 0.5)
    textos.append(f"Diámetro: {labor.ancho_m:.2f} m")

    if longitud_existente > 0:
        x_prof = radio + offset_lateral * 1.8
        _agregar_cota(lineas, (x_prof, 0.0, 0.0), (x_prof, 0.0, longitud_existente), (1, 0, 0), tick)
        tx.append(x_prof + offset_lateral * 0.8); ty.append(0.0); tz.append(longitud_existente / 2.0)
        textos.append(f"Profundidad/altura existente: {longitud_existente:.2f} m")

    x_avance = -(radio + offset_lateral * 1.8)
    _agregar_cota(
        lineas, (x_avance, 0.0, longitud_existente), (x_avance, 0.0, longitud_total), (1, 0, 0), tick
    )
    tx.append(x_avance - offset_lateral * 0.8); ty.append(0.0)
    tz.append(longitud_existente + avance_proyectado / 2.0)
    textos.append(f"Avance proyectado: {avance_proyectado:.2f} m")

    return lineas, tx, ty, tz, textos


def _layout_vertical(fig: go.Figure, labor: LaborMinera, longitud_total: float) -> None:
    ratio_largo, ratio_diametro, _ = relacion_aspecto(labor.ancho_m, labor.ancho_m, longitud_total)
    fig.update_layout(
        title=f"Esquema — {labor.tipo}: {labor.nombre}",
        scene=dict(
            xaxis=dict(title="", showbackground=False, visible=False),
            yaxis=dict(title="", showbackground=False, visible=False),
            zaxis=dict(title="Profundidad / altura (m)", showbackground=False),
            aspectmode="manual",
            aspectratio=dict(x=ratio_diametro, y=ratio_diametro, z=ratio_largo),
            camera=dict(eye=dict(x=0.9, y=0.9, z=0.35)),
        ),
        legend=dict(orientation="h", yanchor="bottom", y=0.01, x=0.01),
        margin=dict(l=0, r=0, t=40, b=30),
        annotations=[
            dict(
                text=(
                    f"Diámetro {labor.ancho_m:.2f} m — "
                    f"esquema referencial, proporciones no a escala"
                ),
                xref="paper", yref="paper", x=0.5, y=-0.02,
                showarrow=False, font=dict(color=COLOR_COTA, size=10),
            )
        ],
    )


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
    (color de identidad), con sus cotas. Pique/Chimenea se dibujan como
    cilindro vertical (extrusión local en Z); el resto, como herradura
    horizontal (extrusión local en X)."""
    vertical = labor.tipo in LABORES_VERTICALES
    longitud_existente = max(labor.longitud_existente_m, 0.0)
    avance_proyectado = max(labor.avance_proyectado_m, 0.01)
    longitud_total = longitud_existente + avance_proyectado

    fig = go.Figure()

    n_anillos_existente = (
        max(3, round(n_anillos * longitud_existente / longitud_total)) if longitud_existente > 0 else 0
    )
    n_anillos_proyectado = max(3, n_anillos - n_anillos_existente)

    if vertical:
        _agregar_tramo_wireframe_pique(
            fig, labor.ancho_m, longitud_existente, 0.0,
            COLOR_EXISTENTE, "Tramo existente", n_anillos_existente,
        )
        _agregar_tramo_wireframe_pique(
            fig, labor.ancho_m, avance_proyectado, longitud_existente,
            COLOR_PROYECTADO, "Tramo proyectado", n_anillos_proyectado,
        )
    else:
        _agregar_tramo_wireframe(
            fig, labor.ancho_m, labor.alto_m, longitud_existente, 0.0,
            COLOR_EXISTENTE, "Tramo existente", n_anillos_existente, forma=labor.forma_seccion,
        )
        _agregar_tramo_wireframe(
            fig, labor.ancho_m, labor.alto_m, avance_proyectado, longitud_existente,
            COLOR_PROYECTADO, "Tramo proyectado", n_anillos_proyectado, forma=labor.forma_seccion,
        )

    if longitud_existente > 0:
        radio = labor.ancho_m / 2.0
        if vertical:
            frente = dict(
                x=[-radio, radio], y=[0.0, 0.0], z=[longitud_existente, longitud_existente],
            )
        else:
            frente = dict(
                x=[longitud_existente, longitud_existente], y=[0.0, 0.0], z=[0.0, labor.alto_m],
            )
        fig.add_trace(
            go.Scatter3d(
                **frente,
                mode="lines",
                line=dict(color=COLOR_FRONTERA, width=3, dash="dash"),
                name="Frente actual",
                hoverinfo="skip",
            )
        )

    cotas = _cotas_verticales if vertical else _cotas_comunes
    cota_lineas, tx, ty, tz, textos = cotas(labor, longitud_total)
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

    (_layout_vertical if vertical else _layout_comun)(fig, labor, longitud_total)
    return fig


def build_tunnel_figure_solido(
    labor: LaborMinera,
    resultado: ResultadoVoladura,
    n_anillos: int = 16,
    n_meses: int | None = None,
) -> go.Figure:
    """Versión sólida y cerrada (piso/muros/arco + tapas, o cilindro para
    Pique/Chimenea) del mismo esquema, con el mismo esquema de colores
    existente/proyectado. Si se indica `n_meses` (periodo del programa),
    superpone un anillo punteado por cada mes de avance proyectado
    (asumiendo avance uniforme), con su etiqueta "Mes k", para identificar
    la programación mensual directamente sobre el sólido."""
    vertical = labor.tipo in LABORES_VERTICALES
    longitud_existente = max(labor.longitud_existente_m, 0.0)
    avance_proyectado = max(labor.avance_proyectado_m, 0.01)
    longitud_total = longitud_existente + avance_proyectado

    n_anillos_existente = (
        max(3, round(n_anillos * longitud_existente / longitud_total)) if longitud_existente > 0 else 0
    )
    n_anillos_proyectado = max(3, n_anillos - n_anillos_existente)

    if vertical:
        malla = malla_solida_pique(
            labor.ancho_m, longitud_existente, avance_proyectado,
            n_anillos_existente=max(n_anillos_existente, 2) if longitud_existente > 0 else 0,
            n_anillos_proyectado=n_anillos_proyectado,
        )
    else:
        malla = malla_solida_tunel(
            labor.ancho_m, labor.alto_m, longitud_existente, avance_proyectado,
            n_anillos_existente=max(n_anillos_existente, 2) if longitud_existente > 0 else 0,
            n_anillos_proyectado=n_anillos_proyectado,
            forma=labor.forma_seccion,
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
            # iluminación 100% ambiental: el piso (normal hacia abajo) se ve
            # con el mismo color que muros/arco/tapas sin importar el ángulo
            # de cámara — de lo contrario, con el sombreado por defecto de
            # Plotly, las caras que miran hacia abajo se ven oscuras/ocultas.
            lighting=dict(ambient=1.0, diffuse=0.0, specular=0.0),
            # contorno oscuro sobre cada arista triangulada: sin esto, el
            # sólido se ve como un bloque uniforme sin definición de bordes.
            contour=dict(show=True, color="#2B2B2B", width=3),
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

    if n_meses:
        radio = labor.ancho_m / 2.0
        if vertical:
            anillos_mes = anillos_de_avance_mensual_pique(
                labor.ancho_m, longitud_existente, avance_proyectado, n_meses,
            )
            offset_etiqueta = radio * 1.35
        else:
            anillos_mes = anillos_de_avance_mensual(
                labor.ancho_m, labor.alto_m, longitud_existente, avance_proyectado, n_meses,
                forma=labor.forma_seccion,
            )
            offset_etiqueta = labor.alto_m + max(0.5, 0.08 * longitud_total) * 0.6
        _agregar_anillos_avance_mensual(fig, anillos_mes, vertical, offset_etiqueta)

    if longitud_existente > 0:
        radio = labor.ancho_m / 2.0
        if vertical:
            frente = dict(
                x=[-radio, radio], y=[0.0, 0.0], z=[longitud_existente, longitud_existente],
            )
        else:
            frente = dict(
                x=[longitud_existente, longitud_existente], y=[0.0, 0.0], z=[0.0, labor.alto_m],
            )
        fig.add_trace(
            go.Scatter3d(
                **frente,
                mode="lines",
                line=dict(color=COLOR_FRONTERA, width=4, dash="dash"),
                name="Frente actual",
                hoverinfo="skip",
            )
        )

    cotas = _cotas_verticales if vertical else _cotas_comunes
    cota_lineas, tx, ty, tz, textos = cotas(labor, longitud_total)
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

    (_layout_vertical if vertical else _layout_comun)(fig, labor, longitud_total)
    return fig
