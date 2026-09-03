"""Configuracion tipada del sistema WPEB.

Reemplaza los diccionarios ``CONFIG``, ``COSTS`` y ``EXT_CONFIG`` del notebook
original por una jerarquia de dataclasses congeladas con validacion.

El motivo del cambio no es estetico: el notebook leia
``config["electrolyzer_specific_consumption_kwh_per_kg"]``, una clave que nunca
existio, y el error solo aparecia dentro del bucle de optimizacion. Aqui una
clave inexistente falla al construir el escenario, y el consumo especifico es
una propiedad derivada que no se puede desincronizar de la eficiencia.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass, replace
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "SiteConfig",
    "WindConfig",
    "PVConfig",
    "BatteryConfig",
    "ElectrolyzerConfig",
    "EconomicsConfig",
    "ConstraintsConfig",
    "SearchConfig",
    "PSOConfig",
    "GAConfig",
    "MetaheuristicConfig",
    "ComponentCost",
    "CostConfig",
    "ScenarioConfig",
    "ConfigError",
]


class ConfigError(ValueError):
    """Error de configuracion: clave desconocida, tipo o rango invalido."""


@dataclass(frozen=True)
class SiteConfig:
    """Emplazamiento y ventana temporal de los datos meteorologicos.

    Por defecto, Damao Banner (Baotou, Mongolia Interior), el sitio del paper.
    """

    lat: float = 41.70
    lon: float = 110.43
    start_year: int = 2001
    end_year: int = 2021
    analysis_year: Optional[int] = None

    # NASA POWER entrega los datos en UTC, pero la complementariedad viento-solar
    # se mide por dia solar local. En Damao Banner (UTC+8) el periodo diurno cruza
    # la medianoche UTC, de modo que agrupar por fecha UTC parte cada dia solar en
    # dos. Ver CHANGELOG.md, correccion 6.
    utc_offset_hours: float = 8.0

    def __post_init__(self) -> None:
        if not -90.0 <= self.lat <= 90.0:
            raise ConfigError("lat fuera de rango [-90, 90]: " + str(self.lat))
        if not -14.0 <= self.utc_offset_hours <= 14.0:
            raise ConfigError(
                "utc_offset_hours debe estar en [-14, 14]: "
                + str(self.utc_offset_hours)
            )
        if not -180.0 <= self.lon <= 180.0:
            raise ConfigError("lon fuera de rango [-180, 180]: " + str(self.lon))
        if self.start_year > self.end_year:
            raise ConfigError(
                "start_year ({}) > end_year ({})".format(self.start_year, self.end_year)
            )
        if self.analysis_year is not None and not (
            self.start_year <= self.analysis_year <= self.end_year
        ):
            raise ConfigError(
                "analysis_year ({}) fuera de [{}, {}]".format(
                    self.analysis_year, self.start_year, self.end_year
                )
            )

    @property
    def years(self) -> List[int]:
        return list(range(self.start_year, self.end_year + 1))


@dataclass(frozen=True)
class WindConfig:
    """Turbina y recurso eolico a la altura de buje.

    La curva de potencia es cubica simplificada entre cut-in y velocidad nominal.
    La velocidad se evalua a ``hub_height_m``, no a los 50 m de la medicion: NASA
    POWER entrega esa correccion en la columna ``wsc_ms`` usando el exponente de
    cizalladura de ``wind_surface``.
    """

    turbine_rated_mw: float = 5.0
    cut_in_ms: float = 2.5
    rated_ms: float = 10.5
    cut_out_ms: float = 25.0

    # Tabla 3 del paper: buje a 105 m. La superficie determina el exponente de
    # cizalladura que aplica NASA; ver WIND_SURFACE_ALPHA en data/nasa_power.py.
    hub_height_m: float = 105.0
    wind_surface: str = "vegtype_9"

    # Que serie alimenta la curva de potencia:
    #   "measured_50m" -> WS50M tal como la mide NASA
    #   "hub_height"   -> WSC, corregida a hub_height_m
    #
    # El default es "measured_50m" por evidencia, no por comodidad: reproduce el
    # CF eolico de 40% que reporta el paper (§3.1) con desvio de 1%, mientras que
    # corregir a 105 m lo lleva a 56%. El paper declara buje a 105 m, de modo que
    # su modelo debe incluir perdidas de estela, curva real de turbina u otros
    # descuentos que no publica. Se conservan ambas rutas para poder medir el
    # efecto por separado; ver CHANGELOG.md, correccion 1.
    wind_speed_source: str = "measured_50m"

    def __post_init__(self) -> None:
        if self.turbine_rated_mw <= 0:
            raise ConfigError("turbine_rated_mw debe ser > 0")
        if not self.cut_in_ms < self.rated_ms < self.cut_out_ms:
            raise ConfigError(
                "la curva de potencia exige cut_in < rated < cut_out, se recibio "
                "{} / {} / {}".format(self.cut_in_ms, self.rated_ms, self.cut_out_ms)
            )
        if self.cut_in_ms < 0:
            raise ConfigError("cut_in_ms debe ser >= 0")
        if not 10.0 <= self.hub_height_m <= 300.0:
            raise ConfigError(
                "hub_height_m debe estar entre 10 y 300 m (limite de NASA POWER): "
                "{}".format(self.hub_height_m)
            )
        valid_sources = ("measured_50m", "hub_height")
        if self.wind_speed_source not in valid_sources:
            raise ConfigError(
                "wind_speed_source debe ser uno de {}: {}".format(
                    valid_sources, self.wind_speed_source
                )
            )


@dataclass(frozen=True)
class PVConfig:
    """Modelo fotovoltaico horario: GHI, derating y correccion termica tipo NOCT."""

    dc_ac_ratio: float = 1.2
    temp_coeff_pct_per_c: float = -0.5
    noct_c: float = 47.0
    stc_efficiency_pct: float = 13.0
    derating_factor: float = 0.90

    def __post_init__(self) -> None:
        if self.dc_ac_ratio <= 0:
            raise ConfigError("dc_ac_ratio debe ser > 0")
        if self.temp_coeff_pct_per_c > 0:
            raise ConfigError(
                "temp_coeff_pct_per_c debe ser <= 0 "
                "(la eficiencia cae con la temperatura)"
            )
        if not 0.0 < self.derating_factor <= 1.0:
            raise ConfigError("derating_factor debe estar en (0, 1]")
        if not 0.0 < self.stc_efficiency_pct <= 100.0:
            raise ConfigError("stc_efficiency_pct debe estar en (0, 100]")


@dataclass(frozen=True)
class BatteryConfig:
    """Bateria: eficiencia, dimensionamiento base y malla discreta de la extension."""

    roundtrip_efficiency: float = 0.90

    # Modelo base: la potencia es un porcentaje fijo de la del electrolizador,
    # redondeado hacia arriba al tamano de pack disponible. Los casos publicados
    # lo confirman: 0.30*95=28.5 -> B30, 0.30*80=24 -> B25, 0.30*85=25.5 -> B27.5.
    power_ratio_to_electrolyzer: float = 0.30
    power_rounding_step_mw: float = 2.5
    duration_h: float = 1.0

    # Extension discreta: potencia y duracion son variables de decision.
    power_step_mw: float = 5.0
    power_min_mw: float = 0.0
    power_max_mw: float = 50.0
    duration_candidates_h: Tuple[float, ...] = (1.0, 2.0, 4.0)

    def __post_init__(self) -> None:
        if not 0.0 < self.roundtrip_efficiency <= 1.0:
            raise ConfigError("roundtrip_efficiency debe estar en (0, 1]")
        if self.power_ratio_to_electrolyzer < 0:
            raise ConfigError("power_ratio_to_electrolyzer debe ser >= 0")
        if self.power_rounding_step_mw <= 0:
            raise ConfigError("power_rounding_step_mw debe ser > 0")
        if self.duration_h <= 0:
            raise ConfigError("duration_h debe ser > 0")
        if self.power_step_mw <= 0:
            raise ConfigError("power_step_mw debe ser > 0")
        if self.power_min_mw < 0:
            raise ConfigError("power_min_mw debe ser >= 0")
        if self.power_min_mw > self.power_max_mw:
            raise ConfigError("power_min_mw > power_max_mw")
        if not self.duration_candidates_h:
            raise ConfigError("duration_candidates_h no puede estar vacio")
        if any(d <= 0 for d in self.duration_candidates_h):
            raise ConfigError("duration_candidates_h debe contener valores > 0")
        # Tuple para que la dataclass congelada siga siendo hasheable.
        object.__setattr__(
            self,
            "duration_candidates_h",
            tuple(float(d) for d in self.duration_candidates_h),
        )

    @property
    def eta_charge(self) -> float:
        """Eficiencia de carga, repartiendo el roundtrip simetricamente."""
        return self.roundtrip_efficiency ** 0.5

    @property
    def eta_discharge(self) -> float:
        """Eficiencia de descarga, repartiendo el roundtrip simetricamente."""
        return self.roundtrip_efficiency ** 0.5


@dataclass(frozen=True)
class ElectrolyzerConfig:
    """Electrolizador: eficiencia, carga minima y modularidad discreta."""

    efficiency: float = 0.75
    h2_hhv_kwh_per_kg: float = 39.4
    min_load_ratio: float = 0.30

    # Extension discreta: el electrolizador se compra en unidades enteras.
    unit_mw: float = 5.0
    min_units: int = 10  # 50 MW
    max_units: int = 20  # 100 MW

    # Tanque de hidrogeno (Tabla 3 del paper: 1e4 kg). Entra al NPC cotizado por
    # kg; el paper no lo dimensiona dentro del barrido W/P/E/B, asi que es fijo.
    hydrogen_storage_kg: float = 10_000.0

    def __post_init__(self) -> None:
        if not 0.0 < self.efficiency <= 1.0:
            raise ConfigError("efficiency debe estar en (0, 1]")
        if self.h2_hhv_kwh_per_kg <= 0:
            raise ConfigError("h2_hhv_kwh_per_kg debe ser > 0")
        if not 0.0 <= self.min_load_ratio <= 1.0:
            raise ConfigError("min_load_ratio debe estar en [0, 1]")
        if self.unit_mw <= 0:
            raise ConfigError("unit_mw debe ser > 0")
        if self.min_units < 1:
            raise ConfigError("min_units debe ser >= 1")
        if self.min_units > self.max_units:
            raise ConfigError(
                "min_units ({}) > max_units ({})".format(self.min_units, self.max_units)
            )
        if self.hydrogen_storage_kg < 0:
            raise ConfigError("hydrogen_storage_kg debe ser >= 0")

    @property
    def specific_consumption_kwh_per_kg(self) -> float:
        """Consumo especifico de electricidad por kg de H2.

        Derivado, no configurable: con los valores del paper resulta
        ``39.4 / 0.75 = 52.53`` kWh/kg. El notebook original calculaba el H2 de
        dos formas distintas -- el modelo base via HHV/eficiencia y el extendido
        via una clave ``electrolyzer_specific_consumption_kwh_per_kg`` que nunca
        existio, por lo que la extension fallaba con KeyError. Esta propiedad
        garantiza que ambos simuladores usen exactamente la misma conversion.
        """
        return self.h2_hhv_kwh_per_kg / self.efficiency

    @property
    def min_capacity_mw(self) -> float:
        return self.min_units * self.unit_mw

    @property
    def max_capacity_mw(self) -> float:
        return self.max_units * self.unit_mw


@dataclass(frozen=True)
class ConverterConfig:
    """Eficiencias de conversion y consumo parasito de la planta.

    El balance de potencia del paper (Eq. 6) contabiliza ``P_inverter_loss``,
    ``P_rectifier_loss``, ``P_battery_loss`` y ``P_plant_load``. La Tabla 3 fija
    el convertidor de sistema y el bidireccional en 95%.

    ``plant_load_ratio`` queda en 0.0 porque el paper no publica su valor: es un
    supuesto explicito, no un dato.
    """

    inverter_efficiency: float = 0.95       # PV DC -> AC
    rectifier_efficiency: float = 0.95      # AC -> DC del electrolizador
    bidirectional_efficiency: float = 0.95  # bateria AC <-> DC
    plant_load_ratio: float = 0.0           # consumo parasito sobre generacion bruta

    def __post_init__(self) -> None:
        for name in (
            "inverter_efficiency",
            "rectifier_efficiency",
            "bidirectional_efficiency",
        ):
            value = getattr(self, name)
            if not 0.0 < value <= 1.0:
                raise ConfigError(name + " debe estar en (0, 1]")
        if not 0.0 <= self.plant_load_ratio < 1.0:
            raise ConfigError("plant_load_ratio debe estar en [0, 1)")


@dataclass(frozen=True)
class EconomicsConfig:
    """Horizonte, descuento y criterio de energia util para el LCOE."""

    project_lifetime_years: int = 25
    real_discount_rate: float = 0.0435

    # Denominador del LCOE. El notebook usaba "electrolyzer_plus_grid" en el
    # modelo base y "electrolyzer_only" en el extendido, sin justificarlo; ver
    # CHANGELOG.md, correccion 2.
    lcoe_energy_basis: str = "electrolyzer_plus_grid"

    def __post_init__(self) -> None:
        if self.project_lifetime_years < 1:
            raise ConfigError("project_lifetime_years debe ser >= 1")
        if self.real_discount_rate <= -1.0:
            raise ConfigError("real_discount_rate debe ser > -1")
        valid = ("electrolyzer_plus_grid", "electrolyzer_only")
        if self.lcoe_energy_basis not in valid:
            raise ConfigError(
                "lcoe_energy_basis debe ser uno de {}: {}".format(
                    valid, self.lcoe_energy_basis
                )
            )


@dataclass(frozen=True)
class ConstraintsConfig:
    """Restricciones de diseno del paper."""

    total_generation_capacity_mw: float = 200.0  # Wind + PV, fijo
    agsr_max: float = 0.20  # ventas a red / generacion renovable
    electrolyzer_ratio_max: float = 0.50  # E <= 50% de (Wind + PV)

    # None -> exportacion ilimitada y curtailment identicamente 0, que es el
    # comportamiento del notebook original.
    grid_export_limit_mw: Optional[float] = None

    def __post_init__(self) -> None:
        if self.total_generation_capacity_mw <= 0:
            raise ConfigError("total_generation_capacity_mw debe ser > 0")
        if not 0.0 <= self.agsr_max <= 1.0:
            raise ConfigError("agsr_max debe estar en [0, 1]")
        if not 0.0 < self.electrolyzer_ratio_max <= 1.0:
            raise ConfigError("electrolyzer_ratio_max debe estar en (0, 1]")
        if self.grid_export_limit_mw is not None and self.grid_export_limit_mw < 0:
            raise ConfigError("grid_export_limit_mw debe ser >= 0 o None")

    @property
    def electrolyzer_max_mw(self) -> float:
        return self.electrolyzer_ratio_max * self.total_generation_capacity_mw


@dataclass(frozen=True)
class SearchConfig:
    """Resolucion del barrido exhaustivo (celdas 17 y 18 del notebook)."""

    wind_step_mw: float = 10.0
    electrolyzer_step_mw: float = 5.0

    def __post_init__(self) -> None:
        if self.wind_step_mw <= 0:
            raise ConfigError("wind_step_mw debe ser > 0")
        if self.electrolyzer_step_mw <= 0:
            raise ConfigError("electrolyzer_step_mw debe ser > 0")


@dataclass(frozen=True)
class PSOConfig:
    """Hiperparametros del enjambre de particulas (PSO).

    Los defaults son los coeficientes de constriccion de Clerc-Kennedy, el
    valor canonico de la literatura, no un ajuste fino a este problema: la
    comparativa de metaheuristicas no debe leerse como un torneo con un
    favorito afinado.
    """

    inertia: float = 0.729
    cognitive: float = 1.49445
    social: float = 1.49445
    velocity_clamp_ratio: float = 0.20

    def __post_init__(self) -> None:
        if self.inertia < 0:
            raise ConfigError("inertia debe ser >= 0")
        if self.cognitive < 0:
            raise ConfigError("cognitive debe ser >= 0")
        if self.social < 0:
            raise ConfigError("social debe ser >= 0")
        if not 0.0 < self.velocity_clamp_ratio <= 1.0:
            raise ConfigError("velocity_clamp_ratio debe estar en (0, 1]")


@dataclass(frozen=True)
class GAConfig:
    """Hiperparametros del algoritmo genetico de codificacion real."""

    crossover_rate: float = 0.90
    mutation_rate: float = 0.10
    mutation_sigma_ratio: float = 0.10
    tournament_size: int = 3
    elite_count: int = 2

    def __post_init__(self) -> None:
        if not 0.0 <= self.crossover_rate <= 1.0:
            raise ConfigError("crossover_rate debe estar en [0, 1]")
        if not 0.0 <= self.mutation_rate <= 1.0:
            raise ConfigError("mutation_rate debe estar en [0, 1]")
        if self.mutation_sigma_ratio <= 0:
            raise ConfigError("mutation_sigma_ratio debe ser > 0")
        if self.tournament_size < 2:
            raise ConfigError("tournament_size debe ser >= 2")
        if self.elite_count < 0:
            raise ConfigError("elite_count debe ser >= 0")


@dataclass(frozen=True)
class MetaheuristicConfig:
    """Presupuesto y reproducibilidad de los optimizadores poblacionales."""

    population: int = 20
    iterations: int = 30
    seed: int = 42
    penalty_infeasible: float = 1e6
    penalty_agsr_weight: float = 1e3
    pso: PSOConfig = field(default_factory=PSOConfig)
    ga: GAConfig = field(default_factory=GAConfig)

    def __post_init__(self) -> None:
        if self.population < 1:
            raise ConfigError("population debe ser >= 1")
        if self.iterations < 1:
            raise ConfigError("iterations debe ser >= 1")
        if self.penalty_infeasible < 0:
            raise ConfigError("penalty_infeasible debe ser >= 0")
        if self.penalty_agsr_weight < 0:
            raise ConfigError("penalty_agsr_weight debe ser >= 0")
        if self.ga.elite_count > self.population:
            raise ConfigError(
                "ga.elite_count ({}) no puede superar population ({})".format(
                    self.ga.elite_count, self.population
                )
            )
        if self.ga.tournament_size > self.population:
            raise ConfigError(
                "ga.tournament_size ({}) no puede superar population ({})".format(
                    self.ga.tournament_size, self.population
                )
            )

    @property
    def evaluation_budget(self) -> int:
        """Evaluaciones del objetivo; permite comparar algoritmos con equidad."""
        return self.population * self.iterations


@dataclass(frozen=True)
class ComponentCost:
    """Costos de un componente, con base de potencia (kW) y de energia (kWh).

    La base de energia existe sobre todo para la bateria: en el notebook original
    la duracion era variable de decision pero no tenia costo asociado, de modo
    que el optimizador podia elegir 4 h gratis. Los defaults en 0.0 preservan
    exactamente el NPC del notebook.
    """

    capex_cny_per_kw: float = 0.0
    replacement_cny_per_kw: float = 0.0
    om_cny_per_kw_year: float = 0.0
    capex_cny_per_kwh: float = 0.0
    replacement_cny_per_kwh: float = 0.0
    om_cny_per_kwh_year: float = 0.0
    life_years: int = 25

    def __post_init__(self) -> None:
        for name in (
            "capex_cny_per_kw",
            "replacement_cny_per_kw",
            "om_cny_per_kw_year",
            "capex_cny_per_kwh",
            "replacement_cny_per_kwh",
            "om_cny_per_kwh_year",
        ):
            if getattr(self, name) < 0:
                raise ConfigError(name + " debe ser >= 0")
        if self.life_years < 1:
            raise ConfigError("life_years debe ser >= 1")

    @property
    def has_energy_cost(self) -> bool:
        return (
            self.capex_cny_per_kwh > 0
            or self.replacement_cny_per_kwh > 0
            or self.om_cny_per_kwh_year > 0
        )


@dataclass(frozen=True)
class CostConfig:
    """Costos del paper, en CNY."""

    wind: ComponentCost = field(
        default_factory=lambda: ComponentCost(
            capex_cny_per_kw=5917.0,
            replacement_cny_per_kw=0.0,
            om_cny_per_kw_year=40.2,
            life_years=25,
        )
    )
    pv: ComponentCost = field(
        default_factory=lambda: ComponentCost(
            capex_cny_per_kw=4633.0,
            replacement_cny_per_kw=0.0,
            om_cny_per_kw_year=17.6,
            life_years=25,
        )
    )
    electrolyzer: ComponentCost = field(
        default_factory=lambda: ComponentCost(
            capex_cny_per_kw=6964.0,
            replacement_cny_per_kw=5969.14,
            om_cny_per_kw_year=208.92,
            life_years=15,
        )
    )
    battery: ComponentCost = field(
        default_factory=lambda: ComponentCost(
            capex_cny_per_kw=2549.0,
            replacement_cny_per_kw=500.0,
            om_cny_per_kw_year=10.0,
            life_years=10,
        )
    )

    # El paper cotiza el almacenamiento de H2 por kg, pero no explicita su
    # dimensionamiento dentro del barrido W/P/E/B, asi que queda fuera del NPC
    # de la linea base. Se conserva para extensiones futuras.
    hydrogen_storage_capex_cny_per_kg: float = 6611.77
    hydrogen_storage_om_cny_per_kg_year: float = 141.68
    hydrogen_storage_life_years: int = 25

    def __post_init__(self) -> None:
        if self.hydrogen_storage_capex_cny_per_kg < 0:
            raise ConfigError("hydrogen_storage_capex_cny_per_kg debe ser >= 0")
        if self.hydrogen_storage_om_cny_per_kg_year < 0:
            raise ConfigError("hydrogen_storage_om_cny_per_kg_year debe ser >= 0")
        if self.hydrogen_storage_life_years < 1:
            raise ConfigError("hydrogen_storage_life_years debe ser >= 1")


@dataclass(frozen=True)
class ScenarioConfig:
    """Escenario completo: todo lo necesario para reproducir una corrida."""

    name: str = "paper_li2024"
    description: str = ""
    site: SiteConfig = field(default_factory=SiteConfig)
    wind: WindConfig = field(default_factory=WindConfig)
    pv: PVConfig = field(default_factory=PVConfig)
    battery: BatteryConfig = field(default_factory=BatteryConfig)
    electrolyzer: ElectrolyzerConfig = field(default_factory=ElectrolyzerConfig)
    converter: ConverterConfig = field(default_factory=ConverterConfig)
    economics: EconomicsConfig = field(default_factory=EconomicsConfig)
    constraints: ConstraintsConfig = field(default_factory=ConstraintsConfig)
    search: SearchConfig = field(default_factory=SearchConfig)
    metaheuristic: MetaheuristicConfig = field(default_factory=MetaheuristicConfig)
    costs: CostConfig = field(default_factory=CostConfig)

    def __post_init__(self) -> None:
        # Coherencia entre bloques: la malla discreta del electrolizador no puede
        # violar la restriccion E <= ratio_max * (Wind + PV).
        max_discrete = self.electrolyzer.max_capacity_mw
        allowed = self.constraints.electrolyzer_max_mw
        if max_discrete > allowed + 1e-9:
            raise ConfigError(
                "la malla discreta permite hasta {:.1f} MW de electrolizador, "
                "pero la restriccion admite como maximo {:.1f} MW "
                "(electrolyzer_ratio_max={})".format(
                    max_discrete, allowed, self.constraints.electrolyzer_ratio_max
                )
            )

    def to_dict(self) -> Dict[str, Any]:
        return _to_plain(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScenarioConfig":
        return _from_plain(cls, data or {}, path="")

    def replace(self, **changes: Any) -> "ScenarioConfig":
        """Copia con cambios, revalidando. Util para barridos de sensibilidad."""
        return replace(self, **changes)


def _to_plain(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _to_plain(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, (tuple, list)):
        return [_to_plain(v) for v in obj]
    return obj


def _from_plain(cls: type, data: Any, path: str) -> Any:
    """Construye una dataclass desde un dict, rechazando claves desconocidas.

    El rechazo explicito es deliberado: un typo en el YAML debe fallar al cargar
    el escenario, no producir silenciosamente un valor por defecto distinto del
    que el investigador cree estar usando.
    """
    if not isinstance(data, dict):
        raise ConfigError(
            "{}: se esperaba un mapeo, se recibio {}".format(
                path or "raiz", type(data).__name__
            )
        )

    field_map = {f.name: f for f in fields(cls)}
    unknown = set(data) - set(field_map)
    if unknown:
        raise ConfigError(
            "{}: clave(s) desconocida(s) {}. Claves validas: {}".format(
                path or "raiz", sorted(unknown), ", ".join(sorted(field_map))
            )
        )

    kwargs: Dict[str, Any] = {}
    for name, value in data.items():
        f = field_map[name]
        nested = _nested_type(f.type)
        child_path = path + "." + name if path else name
        if nested is not None and value is not None:
            kwargs[name] = _from_plain(nested, value, child_path)
        elif name == "duration_candidates_h" and value is not None:
            kwargs[name] = tuple(_coerce(v, "float", child_path) for v in value)
        else:
            kwargs[name] = _coerce(value, f.type, child_path)
    return cls(**kwargs)


def _coerce(value: Any, annotation: Any, path: str) -> Any:
    """Ajusta el tipo de un valor escalar al declarado en la dataclass.

    Existe por una trampa concreta de YAML 1.1: ``1.0e6`` se carga como el
    string ``"1.0e6"`` -- hace falta ``1.0e+6`` para que sea un float -- y sin
    esta conversion el error aparece recien al comparar rangos, con un mensaje
    que no menciona el YAML.
    """
    if value is None or isinstance(value, bool):
        return value

    name = annotation if isinstance(annotation, str) else getattr(annotation, "__name__", "")

    if "float" in name and not isinstance(value, float):
        try:
            return float(value)
        except (TypeError, ValueError):
            raise ConfigError(
                "{}: se esperaba un numero, se recibio {!r}".format(path, value)
            ) from None

    if "int" in name and "float" not in name and not isinstance(value, int):
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ConfigError(
                "{}: se esperaba un entero, se recibio {!r}".format(path, value)
            ) from None
        if number != int(number):
            raise ConfigError(
                "{}: se esperaba un entero, se recibio {!r}".format(path, value)
            )
        return int(number)

    return value


_NESTED_TYPES = {
    "SiteConfig": SiteConfig,
    "WindConfig": WindConfig,
    "PVConfig": PVConfig,
    "BatteryConfig": BatteryConfig,
    "ElectrolyzerConfig": ElectrolyzerConfig,
    "EconomicsConfig": EconomicsConfig,
    "ConstraintsConfig": ConstraintsConfig,
    "ConverterConfig": ConverterConfig,
    "SearchConfig": SearchConfig,
    "PSOConfig": PSOConfig,
    "GAConfig": GAConfig,
    "MetaheuristicConfig": MetaheuristicConfig,
    "ComponentCost": ComponentCost,
    "CostConfig": CostConfig,
}


def _nested_type(annotation: Any) -> Optional[type]:
    """Resuelve el tipo anidado por nombre.

    Se resuelve por nombre y no por identidad porque
    ``from __future__ import annotations`` deja las anotaciones como strings.
    """
    name = (
        annotation
        if isinstance(annotation, str)
        else getattr(annotation, "__name__", "")
    )
    return _NESTED_TYPES.get(name)
