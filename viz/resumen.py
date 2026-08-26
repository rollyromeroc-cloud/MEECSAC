"""Tabla resumen del programa de voladura (una fila por labor, más una
fila de totales).

La usan la vista Detalle y el tablero de `pages/1_Voladura`. Vive aquí y no
dentro de la página para poder testearse sin Streamlit — encierra dos
detalles que ya han fallado antes en este proyecto:

  - mezclar un texto (p. ej. "—") con números en una columna numérica rompe
    la serialización Arrow de `st.dataframe`, así que las celdas sin valor
    van como `None`;
  - el factor de potencia del programa es explosivo total ÷ tonelaje total,
    no el promedio de los factores por labor (media de cocientes ≠ cociente
    de sumas).

No calcula nada nuevo: todo sale de `core.voladura.calcular_programa`.
"""

from __future__ import annotations

import pandas as pd

from core.models import LaborMinera, ResultadoVoladura

# Columnas que tiene sentido sumar en la fila TOTAL. Sumar el avance por
# disparo, los taladros por disparo o el área daría una cifra sin
# significado, así que esas se dejan vacías.
COLUMNAS_ADITIVAS = (
    "Longitud programa (m)",
    "Producción mineral (TM)",
    "Producción desmonte (TM)",
    "N.° disparos",
    "Total de taladros",
    "Explosivo total (kg)",
    "Volumen total (m³)",
    "Tonelaje total (TM)",
    "Fulminantes",
    "Mecha total (m)",
)
COLUMNAS_TEXTO = ("Sección (m)", "Tipo", "Etapa")


def tabla_resultados(
    labores: list[LaborMinera], resultados: list[ResultadoVoladura]
) -> pd.DataFrame:
    """Una fila por labor con todo lo calculado."""
    return pd.DataFrame(
        [
            {
                "Labor": labor.nombre,
                "Sección (m)": f"{labor.ancho_m} × {labor.alto_m}",
                "Longitud programa (m)": labor.avance_proyectado_m,
                "Producción mineral (TM)": (
                    round(r.tonelaje_total_tm, 2) if labor.destino_material == "Mineral" else 0.0
                ),
                "Producción desmonte (TM)": (
                    round(r.tonelaje_total_tm, 2) if labor.destino_material == "Desmonte" else 0.0
                ),
                "Avance x disparo (m)": labor.avance_por_disparo_m,
                "N.° taladros x disparo": labor.taladros_cargados,
                "N.° disparos": r.n_disparos,
                "Total de taladros": r.total_taladros,
                "Tipo": labor.tipo,
                "Etapa": labor.etapa,
                "Área (m²)": round(r.area_m2, 3),
                "Explosivo total (kg)": round(r.explosivo_total_kg, 2),
                "Volumen total (m³)": round(r.volumen_total_m3, 2),
                "Tonelaje total (TM)": round(r.tonelaje_total_tm, 2),
                "Factor de potencia (kg/TM)": round(r.factor_potencia_kg_tm, 2),
                "Fulminantes": r.fulminantes_total,
                "Mecha total (m)": round(r.mecha_total_m, 2),
            }
            for labor, r in zip(labores, resultados)
        ]
    )


def con_fila_total(
    tabla: pd.DataFrame, resultados: list[ResultadoVoladura]
) -> pd.DataFrame:
    """Devuelve `tabla` con una fila TOTAL al final (ver docstring del
    módulo para las dos reglas que aplica)."""
    if tabla.empty:
        return tabla
    explosivo = sum(r.explosivo_total_kg for r in resultados)
    tonelaje = sum(r.tonelaje_total_tm for r in resultados)

    total: dict = {columna: None for columna in tabla.columns}
    total.update({columna: tabla[columna].sum() for columna in COLUMNAS_ADITIVAS})
    for columna in COLUMNAS_TEXTO:
        total[columna] = ""
    total["Labor"] = "TOTAL"
    total["Factor de potencia (kg/TM)"] = (
        round(explosivo / tonelaje, 2) if tonelaje > 0 else 0.0
    )
    return pd.concat([tabla, pd.DataFrame([total])], ignore_index=True)
