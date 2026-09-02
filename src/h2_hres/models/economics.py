"""Modelo economico: valor presente, NPC, LCOE y LCOH (celda 15 del notebook).

Respecto del notebook, cada componente admite ademas una base de costo por
energia (CNY/kWh) que por defecto vale 0.0. Con los costos del paper -- que solo
tienen base de potencia -- el NPC resultante es identico al del notebook.
"""

from __future__ import annotations

from typing import List

from ..config.schema import ComponentCost, CostConfig, EconomicsConfig

__all__ = [
    "crf",
    "replacement_years",
    "present_value_of_replacements",
    "present_value_of_om",
    "component_npc",
    "salvage_value",
    "hydrogen_storage_npc",
    "npc_from_capacities",
    "levelized_cost",
]


def crf(discount_rate: float, years: int) -> float:
    """Factor de recuperacion de capital.

    Con tasa cero el factor degenera en 1/n, que es el limite analitico de la
    formula y evita una division por cero.
    """
    if years < 1:
        raise ValueError("years debe ser >= 1")
    if discount_rate == 0.0:
        return 1.0 / years
    growth = (1.0 + discount_rate) ** years
    return (discount_rate * growth) / (growth - 1.0)


def replacement_years(life_years: int, project_years: int) -> List[int]:
    """Anos en que toca reemplazar el componente dentro del horizonte.

    Un componente de vida 15 anos en un proyecto de 25 se reemplaza solo en el
    ano 15: el reemplazo del ano 30 cae fuera del horizonte.
    """
    if life_years < 1:
        raise ValueError("life_years debe ser >= 1")
    return list(range(life_years, project_years, life_years))


def present_value_of_replacements(
    quantity: float, cost_per_unit: float, life_years: int,
    project_years: int, discount_rate: float,
) -> float:
    """Valor presente de los reemplazos periodicos."""
    if quantity <= 0 or cost_per_unit <= 0:
        return 0.0
    return sum(
        (quantity * cost_per_unit) / ((1.0 + discount_rate) ** year)
        for year in replacement_years(life_years, project_years)
    )


def present_value_of_om(
    quantity: float, om_per_unit_year: float, project_years: int, discount_rate: float
) -> float:
    """Valor presente de la operacion y mantenimiento anual."""
    if quantity <= 0 or om_per_unit_year <= 0:
        return 0.0
    return sum(
        (quantity * om_per_unit_year) / ((1.0 + discount_rate) ** year)
        for year in range(1, project_years + 1)
    )


def salvage_value(
    quantity: float,
    replacement_cost_per_unit: float,
    life_years: int,
    project_years: int,
    discount_rate: float,
) -> float:
    """Valor residual al final del horizonte, metodo lineal de HOMER.

    Si el ultimo reemplazo ocurre antes del fin del proyecto, al componente le
    queda vida util sin usar. Ese remanente se valora en proporcion a la vida
    restante y se descuenta desde el fin del horizonte:

        S = C_rep * (vida_restante / vida_componente) / (1 + i) ** N

    Con los datos del paper, el electrolizador (vida 15, reemplazo en el ano 15)
    llega al ano 25 con 5 de 15 anos sin usar. Un componente cuya vida coincide
    con el horizonte -- eolica y PV, 25 anos -- no tiene residual.
    """
    if quantity <= 0 or replacement_cost_per_unit <= 0:
        return 0.0

    replacements = replacement_years(life_years, project_years)
    if not replacements:
        return 0.0

    last_replacement = replacements[-1]
    remaining_life = life_years - (project_years - last_replacement)
    if remaining_life <= 0:
        return 0.0

    value = quantity * replacement_cost_per_unit * (remaining_life / life_years)
    return value / ((1.0 + discount_rate) ** project_years)


def component_npc(
    capacity_kw: float,
    capacity_kwh: float,
    cost: ComponentCost,
    economics: EconomicsConfig,
) -> float:
    """Costo presente neto de un componente: capex + reemplazos + O&M - residual.

    Suma las bases de potencia y de energia. Para todos los componentes del
    paper la base de energia es 0.0, asi que solo contribuye la de potencia.
    """
    rate = economics.real_discount_rate
    horizon = economics.project_lifetime_years

    total = 0.0
    for quantity, capex, replacement, om in (
        (
            capacity_kw,
            cost.capex_cny_per_kw,
            cost.replacement_cny_per_kw,
            cost.om_cny_per_kw_year,
        ),
        (
            capacity_kwh,
            cost.capex_cny_per_kwh,
            cost.replacement_cny_per_kwh,
            cost.om_cny_per_kwh_year,
        ),
    ):
        if quantity <= 0:
            continue
        total += quantity * capex
        total += present_value_of_replacements(
            quantity, replacement, cost.life_years, horizon, rate
        )
        total += present_value_of_om(quantity, om, horizon, rate)
        total -= salvage_value(
            quantity, replacement, cost.life_years, horizon, rate
        )
    return total


def hydrogen_storage_npc(
    capacity_kg: float, costs: CostConfig, economics: EconomicsConfig
) -> float:
    """Costo presente neto del almacenamiento de H2, cotizado por kg.

    El paper lo incluye en el NPC (Tabla 4 y Fig. 16f) con una capacidad de
    1e4 kg (Tabla 3). Su vida util coincide con el horizonte, de modo que no
    tiene reemplazos ni valor residual.
    """
    if capacity_kg <= 0:
        return 0.0

    return capacity_kg * costs.hydrogen_storage_capex_cny_per_kg + present_value_of_om(
        capacity_kg,
        costs.hydrogen_storage_om_cny_per_kg_year,
        economics.project_lifetime_years,
        economics.real_discount_rate,
    )


def npc_from_capacities(
    wind_mw: float,
    pv_mw: float,
    electrolyzer_mw: float,
    battery_mw: float,
    battery_mwh: float,
    costs: CostConfig,
    economics: EconomicsConfig,
    hydrogen_storage_kg: float = 0.0,
) -> float:
    """Costo presente neto del sistema WPEB completo."""
    mw_to_kw = 1000.0
    mwh_to_kwh = 1000.0

    return (
        component_npc(wind_mw * mw_to_kw, 0.0, costs.wind, economics)
        + component_npc(pv_mw * mw_to_kw, 0.0, costs.pv, economics)
        + component_npc(electrolyzer_mw * mw_to_kw, 0.0, costs.electrolyzer, economics)
        + component_npc(
            battery_mw * mw_to_kw, battery_mwh * mwh_to_kwh, costs.battery, economics
        )
        + hydrogen_storage_npc(hydrogen_storage_kg, costs, economics)
    )


def levelized_cost(annualized_cost_cny: float, annual_output: float) -> float:
    """Costo nivelado: costo anualizado por unidad de producto anual.

    Devuelve infinito si no hay produccion, para que las configuraciones
    esteriles nunca ganen una comparacion por minimo.
    """
    if annual_output <= 0:
        return float("inf")
    return annualized_cost_cny / annual_output
