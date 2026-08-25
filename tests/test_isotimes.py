import numpy as np

from core.isotimes import malla_isotiempos
from core.malla_perforacion import generar_malla_perforacion


def test_malla_isotiempos_devuelve_grilla_enmascarada():
    malla, _ = generar_malla_perforacion(
        ancho=1.77, alto=1.10, taladros_cargados=23, taladros_alivio=2,
        diametro_barreno_mm=36.0, forma_seccion="Baúl (hastiales rectos)",
    )
    resultado = malla_isotiempos(malla, "Baúl (hastiales rectos)", 1.77, 1.10, resolucion=30)
    assert resultado is not None
    Y, Z, T = resultado
    assert Y.shape == Z.shape == T.shape == (30, 30)
    # hay celdas dentro del contorno (no-NaN) y celdas fuera (NaN)
    assert np.any(~np.isnan(T))
    assert np.any(np.isnan(T))
    # el rango de tiempos interpolados no debe exceder el de los retardos reales
    retardos_reales = [t.retardo_ms for t in malla if t.retardo_ms is not None]
    validos = T[~np.isnan(T)]
    assert validos.min() >= min(retardos_reales) - 1e-6
    assert validos.max() <= max(retardos_reales) + 1e-6


def test_malla_isotiempos_none_con_pocos_taladros():
    from core.malla_perforacion import PosicionTaladro

    taladros = [
        PosicionTaladro(y=0.0, z=0.5, categoria="arranque", anillo=1, retardo_ms=0.0),
        PosicionTaladro(y=0.1, z=0.5, categoria="arranque", anillo=1, retardo_ms=0.0),
    ]
    assert malla_isotiempos(taladros, "Baúl (hastiales rectos)", 1.77, 1.10) is None
