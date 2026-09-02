"""Paridad con el notebook original, acotada al despacho horario.

Hasta la replicacion fiel del paper, este test comparaba el modelo completo
contra el notebook. Ya no puede: el modelo cambio a proposito en seis puntos
(altura de buje, DC/AC, perdidas de conversion, valor residual, almacenamiento
de H2, redondeo de bateria y unidades de GHI), y todos esos cambios acercan la
replicacion a las cifras publicadas. Ver CHANGELOG.md.

Lo que si debe seguir siendo identico es la **logica de despacho**: la regla de
carga minima, el orden de prioridades y la contabilidad del estado de carga no
se tocaron. Eso es lo que se verifica aqui, con eficiencias neutras para aislar
el despacho de las perdidas nuevas.

La validacion del modelo completo vive ahora en ``test_paper_validation.py``,
contra las cifras del paper en vez de contra el notebook.
"""

import numpy as np
import pytest

from h2_hres.simulation.dispatch import MinLoadPolicy, dispatch_hourly

import notebook_reference as reference


ETA = 0.9 ** 0.5


def _notebook_dispatch(generation, electrolyzer_mw, min_load_ratio, battery_mw,
                       battery_mwh, eta_ch, eta_dis):
    """Bucle de despacho de la celda 15, copiado literalmente.

    Se reproduce aqui en vez de llamar a ``simulate_wpeb`` para poder comparar
    solo el despacho, sin arrastrar el modelo de generacion ni el economico.
    """
    soc = 0.0
    soc_max = battery_mwh
    p_batt_max = battery_mw
    min_elz = min_load_ratio * electrolyzer_mw

    grid_sales = []
    electrolyzer_load = []

    for gen in generation:
        p_elz = min(gen, electrolyzer_mw)

        if 0 < p_elz < min_elz:
            deficit = min_elz - p_elz
            p_can_discharge = min(p_batt_max, soc * eta_dis)
            p_dis = min(deficit, p_can_discharge)
            p_elz += p_dis
            soc -= p_dis / eta_dis
            if p_elz < min_elz:
                soc += p_dis / eta_dis
                p_elz = 0.0

        remaining = gen - p_elz

        if remaining > 0 and soc < soc_max:
            p_charge_room = min(p_batt_max, (soc_max - soc) / eta_ch)
            p_ch = min(remaining, p_charge_room)
            soc += p_ch * eta_ch
            remaining -= p_ch

        grid_sales.append(max(remaining, 0.0))
        electrolyzer_load.append(p_elz)

    return np.array(electrolyzer_load), np.array(grid_sales)


@pytest.mark.parametrize("seed", [0, 1, 2])
@pytest.mark.parametrize(
    "electrolyzer_mw,battery_mw,battery_mwh",
    [(95.0, 28.5, 28.5), (50.0, 15.0, 30.0), (80.0, 0.0, 0.0)],
)
def test_dispatch_matches_the_notebook(seed, electrolyzer_mw, battery_mw, battery_mwh):
    """El despacho TOP_UP debe seguir siendo el de la celda 15, hora por hora."""
    generation = np.random.default_rng(seed).uniform(0.0, 200.0, 3000)

    expected_load, expected_grid = _notebook_dispatch(
        generation, electrolyzer_mw, 0.30, battery_mw, battery_mwh, ETA, ETA
    )
    result = dispatch_hourly(
        generation,
        electrolyzer_mw,
        0.30,
        battery_mw,
        battery_mwh,
        ETA,
        ETA,
        policy=MinLoadPolicy.TOP_UP,
    )

    np.testing.assert_allclose(result.electrolyzer_load, expected_load, rtol=0, atol=1e-12)
    np.testing.assert_allclose(result.grid_sales, expected_grid, rtol=0, atol=1e-12)


def test_notebook_costs_still_match_the_paper_table():
    """Los costos del notebook son los de la Tabla 4 y no deben haber cambiado."""
    assert reference.COSTS["wind_capex_cny_per_kw"] == 5917.0
    assert reference.COSTS["pv_capex_cny_per_kw"] == 4633.0
    assert reference.COSTS["electrolyzer_capex_cny_per_kw"] == 6964.0
    assert reference.COSTS["battery_capex_cny_per_kw"] == 2549.0
    assert reference.COSTS["hydrogen_storage_capex_cny_per_kg"] == 6611.77


def test_the_notebook_extension_was_genuinely_broken():
    """Documenta el bug de origen: la clave que la celda 34 leia no existia."""
    assert "electrolyzer_specific_consumption_kwh_per_kg" not in reference.CONFIG
    assert "electrolyzer_specific_consumption_kwh_per_kg" not in reference.COSTS


def test_notebook_ignored_hub_height_and_ghi_units():
    """Las dos brechas que mas movieron la replicacion, fijadas como regresion.

    El notebook no traia altura de buje -- usaba WS50M directo -- y trataba la
    GHI como kWh/m2 cuando NASA la entrega en W/m2. Lo segundo anulaba la
    produccion fotovoltaica por completo via la correccion termica.
    """
    assert "wind_hub_height_m" not in reference.CONFIG
    assert reference.CONFIG["pv_noct_c"] == 47.0

    # Con GHI en W/m2, la temperatura de celda del notebook se dispara y el
    # factor termico se vuelve negativo: el campo PV entrega cero.
    ghi_w_m2 = 500.0
    t_cell = 20.0 + (reference.CONFIG["pv_noct_c"] - 20.0) / 0.8 * ghi_w_m2
    temp_factor = 1.0 + reference.CONFIG["pv_temp_coeff_pct_per_c"] / 100.0 * (t_cell - 25.0)
    assert t_cell > 10_000
    assert temp_factor < 0
