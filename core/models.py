"""Modelos de dominio — Python puro, sin Streamlit ni dependencias de UI."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional

from core.constants import (
    DENSIDAD_DESMONTE_DEFAULT,
    DENSIDAD_MINERAL_DEFAULT,
    DIAMETRO_BARRENO_DEFAULT_MM,
    DISTRIBUCION_EXPLOSIVO_DEFAULT,
    HEMISFERIO_DEFAULT,
    LONGITUD_BARRENO_DEFAULT_PIES,
    PESO_CARTUCHO_DEFAULT_KG,
    TIPOS_EXPLOSIVO_DEFAULT,
    TRAMO_ENCENDIDO_MECHA_PIES,
    ZONA_UTM_DEFAULT,
)


@dataclass
class LaborMinera:
    """Datos de entrada de una labor minera (galería, cortada, pique, etc.)."""

    nombre: str
    tipo: str = "Galería"
    etapa: str = "Desarrollo"

    # Sección del túnel/labor
    ancho_m: float = 0.0
    alto_m: float = 0.0

    # Avance
    longitud_existente_m: float = 0.0
    avance_proyectado_m: float = 0.0
    avance_por_disparo_m: float = 1.10

    # Diseño de perforación
    diametro_barreno_mm: float = DIAMETRO_BARRENO_DEFAULT_MM
    longitud_barreno_pies: float = LONGITUD_BARRENO_DEFAULT_PIES
    tipo_corte: str = "Corte en V"
    equipo_perforacion: str = "Jack Leg"
    taladros_cargados: int = 23
    taladros_alivio: int = 2

    # Explosivos
    cartuchos_por_taladro: int = 4
    peso_cartucho_kg: float = PESO_CARTUCHO_DEFAULT_KG
    tipo_explosivo_1: str = TIPOS_EXPLOSIVO_DEFAULT[0]
    tipo_explosivo_2: str = TIPOS_EXPLOSIVO_DEFAULT[1]
    pct_explosivo_1: float = DISTRIBUCION_EXPLOSIVO_DEFAULT[0]
    pct_explosivo_2: float = DISTRIBUCION_EXPLOSIVO_DEFAULT[1]

    # Aspectos técnicos / material
    tipo_roca: str = "Intermedia"
    destino_material: str = "Desmonte"  # "Desmonte" o "Mineral"
    densidad_desmonte_tm_m3: float = DENSIDAD_DESMONTE_DEFAULT
    densidad_mineral_tm_m3: float = DENSIDAD_MINERAL_DEFAULT

    # Accesorios
    tipo_fulminante: str = "Fulminante común N.° 08"
    tramo_encendido_pies: float = TRAMO_ENCENDIDO_MECHA_PIES

    # Georreferenciación opcional (para exportar el sólido a DXF/AutoCAD en
    # su posición real). Punto de inicio; punto final solo si la labor ya
    # está en operación (se usa para calcular rumbo/pendiente reales en vez
    # de los manuales). Ver core.georef.
    este_utm_inicio: Optional[float] = None
    norte_utm_inicio: Optional[float] = None
    cota_inicio_m: Optional[float] = None
    este_utm_final: Optional[float] = None
    norte_utm_final: Optional[float] = None
    cota_final_m: Optional[float] = None
    rumbo_manual_deg: Optional[float] = None
    pendiente_manual_pct: Optional[float] = None
    sentido_vertical: str = "Abajo"  # solo Pique/Chimenea sin punto final: "Abajo" o "Arriba"

    observaciones: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ResultadoVoladura:
    """Salida calculada a partir de una LaborMinera."""

    labor_nombre: str
    area_m2: float
    longitud_final_m: float
    n_disparos: int

    cartuchos_por_disparo: int
    explosivo_por_disparo_kg: float
    explosivo_total_kg: float
    explosivo_tipo1_kg: float
    explosivo_tipo2_kg: float

    volumen_por_disparo_m3: float
    volumen_total_m3: float
    densidad_usada_tm_m3: float
    tonelaje_por_disparo_tm: float
    tonelaje_total_tm: float

    factor_potencia_kg_tm: float
    consumo_especifico_kg_m3: float

    fulminantes_total: int
    mecha_por_taladro_m: float
    mecha_por_disparo_m: float
    mecha_total_m: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Polvorin:
    """Un polvorín (explosivos o accesorios) con su cerco perimétrico."""

    nombre: str
    tipo: str = "Explosivos"  # "Explosivos" o "Accesorios"
    este_utm: float = 0.0
    norte_utm: float = 0.0
    vertices_cerco: list[tuple[float, float]] = field(default_factory=list)
    cantidad_almacenada_kg: Optional[float] = None
    radio_influencia_m: Optional[float] = None


@dataclass
class PuntoRiesgo:
    """Punto externo contra el que se mide la distancia de seguridad."""

    nombre: str
    tipo: str
    este_utm: float
    norte_utm: float
    distancia_minima_requerida_m: float = 0.0


@dataclass
class ResultadoDistancia:
    punto_nombre: str
    punto_tipo: str
    distancia_real_m: float
    distancia_minima_m: float
    cumple: bool


@dataclass
class DatosGenerales:
    """Encabezado del informe técnico: identifica el proyecto/concesión.

    Todos los campos son opcionales — si se dejan vacíos, el reporte Word
    simplemente omite esa línea del encabezado en vez de mostrar un dato
    inventado.
    """

    nombre_concesion: str = ""
    codigo_concesion: str = ""
    empresa: str = ""
    ruc: str = ""
    departamento: str = ""
    provincia: str = ""
    distrito: str = ""
    periodo_meses: int = 6

    # Zona UTM del proyecto — metadato para la etiqueta del marcador DXF
    # (la exportación en sí usa Este/Norte/Cota crudos, sin reproyectar).
    zona_utm: int = ZONA_UTM_DEFAULT
    hemisferio: str = HEMISFERIO_DEFAULT


@dataclass
class PolvorinGuiaSucamec:
    """Datos de un polvorin para completar las guias SUCAMEC (Formato N.° 23,
    tipo 1 FAMESA-Polvorin y tipo 2 Polvorin-Unidad minera).

    La resolucion, direccion y demas datos del polvorin (origen en tipo 2,
    destino en tipo 1) NO se sobreescriben: se mantienen tal cual estan en el
    Excel base/modelo de ese polvorin (por defecto el bundled con la app; si
    hay mas de un polvorin con datos distintos, cada uno sube su propio par
    de plantillas ya llenadas). Solo se completa automaticamente la
    concesion/unidad minera de destino (tipo 2) y el producto/cantidad/
    unidades de cada guia.
    """

    nombre: str
    plantilla_tipo1_explosivos: bytes | None = None  # None = usar la plantilla por defecto
    plantilla_tipo1_accesorios: bytes | None = None
    plantilla_tipo2: bytes | None = None
    concesion_nombre: str = ""
    concesion_codigo: str = ""
    concesion_distrito: str = ""
    concesion_provincia: str = ""
    concesion_departamento: str = ""
