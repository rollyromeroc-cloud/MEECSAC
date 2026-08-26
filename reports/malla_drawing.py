"""Dibujo vectorial de la malla de perforación para el PDF, con reportlab.

Sustituye al `fig.to_image()` de Plotly que usaba la ficha: ese camino
depende de kaleido y, según la versión, de un Chrome instalado — ya tumbó
la app en producción una vez, y en Python 3.14 (la versión que corre hoy
Streamlit Cloud) `to_image()` se CUELGA en vez de lanzar, así que ni
siquiera un `try/except` lo salva. Dibujar aquí no añade dependencias
(reportlab ya arma la ficha) y además sale en vector, que es lo que
corresponde en un plano.

Reutiliza los colores y la geometría de `viz.malla_plot` /
`core.malla_perforacion`, para que la malla del PDF y la de pantalla sean
la misma figura y no dos diseños que se desincronizan.
"""

from __future__ import annotations

from reportlab.graphics.shapes import Circle, Drawing, Line, PolyLine, String
from reportlab.lib import colors

from core.geometry import perfil_seccion
from core.malla_perforacion import PosicionTaladro, ZonaInfo, ZONAS_ANILLO
from viz.malla_plot import (
    COLOR_BORDE_TALADRO,
    COLOR_CATEGORIA,
    COLOR_CONTORNO_PERFIL,
    COLOR_COTA_ANILLO,
    COLOR_TRAZO_ANILLO,
    NOMBRE_CATEGORIA,
    ORDEN_CATEGORIAS,
)

RADIO_TALADRO_PT = 3.4
ANCHO_LEYENDA_PT = 132.0
MARGEN_PT = 10.0


def _perfil_cerrado(forma_seccion: str | None, ancho: float, alto: float) -> list[tuple[float, float]]:
    perfil = perfil_seccion(forma_seccion, ancho, alto)
    puntos = [(float(y), float(z)) for y, z in perfil]
    return puntos + [puntos[0]]


def build_malla_drawing(
    taladros: list[PosicionTaladro],
    zonas: list[ZonaInfo],
    ancho: float,
    alto: float,
    forma_seccion: str | None,
    ancho_pt: float,
    alto_pt: float,
) -> Drawing:
    """`Drawing` (Flowable de Platypus) con el contorno de la sección, los
    trazos de anillo del corte, los taladros por categoría y una leyenda
    con los conteos y el burden de cada zona en anillo.

    La malla se dibuja a escala uniforme en los dos ejes: deformarla para
    llenar el marco falsearía las distancias, que es justamente lo que la
    ficha documenta.
    """
    dibujo = Drawing(ancho_pt, alto_pt)
    perfil = _perfil_cerrado(forma_seccion, ancho, alto)

    ys = [p[0] for p in perfil] + [t.y for t in taladros]
    zs = [p[1] for p in perfil] + [t.z for t in taladros]
    if not ys:
        return dibujo
    y_min, y_max = min(ys), max(ys)
    z_min, z_max = min(zs), max(zs)

    area_ancho = max(ancho_pt - ANCHO_LEYENDA_PT - 2 * MARGEN_PT, 1.0)
    area_alto = max(alto_pt - 2 * MARGEN_PT, 1.0)
    escala = min(
        area_ancho / max(y_max - y_min, 1e-6),
        area_alto / max(z_max - z_min, 1e-6),
    )
    # centrado dentro del área de dibujo, con la misma escala en Y y Z
    offset_x = MARGEN_PT + (area_ancho - (y_max - y_min) * escala) / 2.0
    offset_y = MARGEN_PT + (area_alto - (z_max - z_min) * escala) / 2.0

    def a_papel(y: float, z: float) -> tuple[float, float]:
        return offset_x + (y - y_min) * escala, offset_y + (z - z_min) * escala

    color_perfil = colors.HexColor(COLOR_CONTORNO_PERFIL)
    color_trazo = colors.HexColor(COLOR_TRAZO_ANILLO)
    color_borde = colors.HexColor(COLOR_BORDE_TALADRO)

    puntos_perfil: list[float] = []
    for y, z in perfil:
        px, py = a_papel(y, z)
        puntos_perfil.extend([px, py])
    dibujo.add(PolyLine(puntos_perfil, strokeColor=color_perfil, strokeWidth=1.4))

    # trazos de cuadrado/rombo de cada anillo del corte, por debajo de los
    # taladros (mismo criterio que la figura de pantalla)
    for zona in ZONAS_ANILLO:
        anillo = [t for t in taladros if t.categoria == zona]
        if len(anillo) < 3:
            continue  # con menos de 3 taladros no hay polígono que trazar
        coords: list[float] = []
        for t in list(anillo) + [anillo[0]]:
            px, py = a_papel(t.y, t.z)
            coords.extend([px, py])
        dibujo.add(PolyLine(coords, strokeColor=color_trazo, strokeWidth=0.8))

    for categoria in ORDEN_CATEGORIAS:
        color = colors.HexColor(COLOR_CATEGORIA[categoria])
        for t in (t for t in taladros if t.categoria == categoria):
            px, py = a_papel(t.y, t.z)
            dibujo.add(
                Circle(
                    px, py, RADIO_TALADRO_PT,
                    fillColor=color, strokeColor=color_borde, strokeWidth=0.7,
                )
            )

    _agregar_leyenda(dibujo, taladros, zonas, ancho_pt, alto_pt)
    return dibujo


def _agregar_leyenda(
    dibujo: Drawing, taladros: list[PosicionTaladro], zonas: list[ZonaInfo],
    ancho_pt: float, alto_pt: float,
) -> None:
    """Leyenda a la derecha: un punto por categoría con su conteo, y debajo
    el burden de las zonas en anillo (las cotas van aquí y no sobre el
    corte, donde taparían los taladros más densos)."""
    x = ancho_pt - ANCHO_LEYENDA_PT
    y = alto_pt - MARGEN_PT - 8.0
    color_borde = colors.HexColor(COLOR_BORDE_TALADRO)

    dibujo.add(String(x, y, "LEYENDA", fontName="Helvetica-Bold", fontSize=7.5,
                      fillColor=colors.HexColor(COLOR_CONTORNO_PERFIL)))
    y -= 13.0
    for categoria in ORDEN_CATEGORIAS:
        n = sum(1 for t in taladros if t.categoria == categoria)
        if not n:
            continue
        dibujo.add(
            Circle(
                x + 4, y + 2, RADIO_TALADRO_PT,
                fillColor=colors.HexColor(COLOR_CATEGORIA[categoria]),
                strokeColor=color_borde, strokeWidth=0.7,
            )
        )
        dibujo.add(
            String(
                x + 13, y, f"{NOMBRE_CATEGORIA[categoria]} ({n})",
                fontName="Helvetica", fontSize=6.5, fillColor=colors.black,
            )
        )
        y -= 11.0

    anillos = [z for z in zonas if z.zona.lower() in ZONAS_ANILLO]
    if not anillos:
        return
    y -= 5.0
    dibujo.add(Line(x, y + 4, x + ANCHO_LEYENDA_PT - MARGEN_PT, y + 4,
                    strokeColor=colors.HexColor("#B8C2C6"), strokeWidth=0.5))
    y -= 8.0
    dibujo.add(String(x, y, "BURDEN POR ZONA", fontName="Helvetica-Bold", fontSize=7,
                      fillColor=colors.HexColor(COLOR_COTA_ANILLO)))
    y -= 11.0
    for info in anillos:
        dibujo.add(
            String(
                x, y, f"{info.zona}: {info.burden_mm:.0f} mm",
                fontName="Helvetica", fontSize=6.5,
                fillColor=colors.HexColor(COLOR_COTA_ANILLO),
            )
        )
        y -= 10.0
