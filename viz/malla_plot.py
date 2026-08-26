"""Esquema 2D de la malla de perforación (cara del frente) de una labor
minera — alivios, zonas en anillo (arranque→ayuda→subayuda, con cotas de
burden en mm) y contorno/arrastre, sobre el perfil real de la sección. Ver
`core.malla_perforacion` para la geometría y las distancias.
"""

from __future__ import annotations

import plotly.graph_objects as go

from core.geometry import perfil_seccion
from core.isotimes import malla_isotiempos
from core.malla_perforacion import PosicionTaladro, ZonaInfo, ZONAS_ANILLO, generar_malla_perforacion

COLOR_CONTORNO_PERFIL = "#444444"
# Paleta de alto contraste (círculos llenos de color vivo, alivio en blanco
# con borde oscuro) — estilo de referencia de una malla real de campo, en
# vez de la paleta pastel anterior: solo cambia la presentación visual, las
# 5 zonas y su lógica de cálculo (`core.malla_perforacion`) no cambian.
COLOR_ALIVIO = "#FFFFFF"
COLOR_ARRANQUE = "#E63946"
COLOR_AYUDA = "#F4A100"
COLOR_SUBAYUDA = "#4CC9F0"
COLOR_CONTORNO_TALADRO = "#1D3557"
COLOR_ARRASTRE = "#2A9D8F"
COLOR_COTA_ANILLO = "#AA4499"
COLOR_BORDE_TALADRO = "#22242A"
COLOR_TRAZO_ANILLO = "#6B7280"

NOMBRE_CATEGORIA = {
    "alivio": "Alivio (sin carga)",
    "arranque": "Arranque",
    "ayuda": "Ayuda",
    "subayuda": "Subayuda",
    "contorno": "Contorno",
    "arrastre": "Arrastre (zapatera)",
}
COLOR_CATEGORIA = {
    "alivio": COLOR_ALIVIO,
    "arranque": COLOR_ARRANQUE,
    "ayuda": COLOR_AYUDA,
    "subayuda": COLOR_SUBAYUDA,
    "contorno": COLOR_CONTORNO_TALADRO,
    "arrastre": COLOR_ARRASTRE,
}
ORDEN_CATEGORIAS = ("alivio", "arranque", "ayuda", "subayuda", "contorno", "arrastre")


def build_malla_perforacion_figure(
    ancho: float,
    alto: float,
    taladros_cargados: int,
    taladros_alivio: int,
    diametro_barreno_mm: float,
    diametro_alivio_mm: float | None = None,
    forma_seccion: str | None = None,
    nombre_labor: str = "",
) -> tuple[go.Figure, list[ZonaInfo]]:
    """Figura 2D (contorno de la sección + posiciones de taladro por
    categoría, con la cota de burden de cada zona en anillo) lista para
    `st.plotly_chart`, junto con las distancias de cada zona (para
    mostrarlas también en una tabla)."""
    malla: list[PosicionTaladro]
    zonas_info: list[ZonaInfo]
    malla, zonas_info = generar_malla_perforacion(
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

    # trazos de cuadrado/rombo que unen los taladros de cada anillo del
    # corte — la "forma" que `ZonaInfo` ya calcula y que en una malla
    # dibujada a mano se traza siempre, para que se lea de un vistazo cómo
    # abre cada sección contra la anterior. Se dibujan antes que los
    # marcadores para que las líneas queden por debajo de los taladros.
    for zona in ZONAS_ANILLO:
        anillo = [t for t in malla if t.categoria == zona]
        if len(anillo) < 3:
            continue  # con menos de 3 taladros no hay polígono que trazar
        ys = [t.y for t in anillo] + [anillo[0].y]
        zs = [t.z for t in anillo] + [anillo[0].z]
        fig.add_trace(
            go.Scatter(
                x=ys, y=zs, mode="lines",
                line=dict(color=COLOR_TRAZO_ANILLO, width=1.2),
                showlegend=False, hoverinfo="skip",
            )
        )

    for categoria in ORDEN_CATEGORIAS:
        puntos = [t for t in malla if t.categoria == categoria]
        if not puntos:
            continue
        fig.add_trace(
            go.Scatter(
                x=[t.y for t in puntos],
                y=[t.z for t in puntos],
                mode="markers",
                marker=dict(
                    size=15, color=COLOR_CATEGORIA[categoria], symbol="circle",
                    line=dict(width=1.5, color=COLOR_BORDE_TALADRO),
                ),
                name=f"{NOMBRE_CATEGORIA[categoria]} ({len(puntos)})",
                hovertext=[NOMBRE_CATEGORIA[categoria] for _ in puntos],
                hoverinfo="text",
            )
        )

    centro_y, centro_z = 0.0, alto / 2.0
    zonas_anillo_usadas = [z for z in zonas_info if z.zona.lower() in ZONAS_ANILLO]
    for i, info in enumerate(zonas_anillo_usadas):
        # las etiquetas se sacan fuera del corte (a la derecha del anillo
        # más externo) con una flecha hacia su propio anillo: puestas sobre
        # el anillo mismo tapaban los taladros del corte, que es justo la
        # zona más densa de la malla.
        radio_m = info.burden_mm / 1000.0
        fig.add_annotation(
            x=centro_y + radio_m, y=centro_z,
            ax=40, ay=-30 - 18 * (len(zonas_anillo_usadas) - 1 - i),
            axref="pixel", ayref="pixel",
            text=f"{info.zona}: {info.burden_mm:.0f} mm",
            showarrow=True, arrowhead=2, arrowsize=0.8, arrowwidth=1,
            arrowcolor=COLOR_COTA_ANILLO, xanchor="left",
            font=dict(color=COLOR_COTA_ANILLO, size=10),
        )

    titulo = f"Malla de perforación — {nombre_labor}" if nombre_labor else "Malla de perforación"
    fig.update_layout(
        title=titulo,
        xaxis=dict(title="", showgrid=False, zeroline=False, scaleanchor="y", scaleratio=1),
        yaxis=dict(title="", showgrid=False, zeroline=False),
        # leyenda en caja (como una ficha de campo), no solo texto flotante
        legend=dict(
            orientation="h", yanchor="bottom", y=-0.3, x=0.0,
            bgcolor="white", bordercolor=COLOR_BORDE_TALADRO, borderwidth=1,
        ),
        plot_bgcolor="white",
        margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig, zonas_info


def build_isotiempos_figure(
    malla: list[PosicionTaladro],
    ancho: float,
    alto: float,
    forma_seccion: str | None = None,
    nombre_labor: str = "",
) -> go.Figure | None:
    """Mapa de calor de isotiempos de detonación (ms), interpolado y
    enmascarado al contorno real de la sección — ver `core.isotimes`.
    Devuelve `None` si no hay suficientes taladros cargados para
    interpolar (el llamador debe mostrar un aviso en ese caso)."""
    resultado = malla_isotiempos(malla, forma_seccion, ancho, alto)
    if resultado is None:
        return None
    Y, Z, T = resultado
    perfil = perfil_seccion(forma_seccion, ancho, alto)

    fig = go.Figure()
    fig.add_trace(
        go.Heatmap(
            x=Y[0, :], y=Z[:, 0], z=T,
            colorscale="YlOrRd", colorbar=dict(title="ms"),
            hovertemplate="Retardo: %{z:.0f} ms<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=list(perfil[:, 0]) + [perfil[0, 0]],
            y=list(perfil[:, 1]) + [perfil[0, 1]],
            mode="lines", line=dict(color=COLOR_CONTORNO_PERFIL, width=2),
            name="Contorno de la sección", hoverinfo="skip",
        )
    )
    con_retardo = [t for t in malla if t.retardo_ms is not None]
    fig.add_trace(
        go.Scatter(
            x=[t.y for t in con_retardo], y=[t.z for t in con_retardo],
            mode="markers", marker=dict(size=6, color="black"),
            name="Taladros cargados", hoverinfo="skip",
        )
    )

    titulo = f"Isotiempos de detonación — {nombre_labor}" if nombre_labor else "Isotiempos de detonación"
    fig.update_layout(
        title=titulo,
        xaxis=dict(title="", showgrid=False, zeroline=False, scaleanchor="y", scaleratio=1),
        yaxis=dict(title="", showgrid=False, zeroline=False),
        margin=dict(l=10, r=10, t=40, b=10),
        showlegend=False,
    )
    return fig
