"""Carga y volcado de escenarios en YAML.

Un escenario YAML solo necesita declarar lo que difiere de los defaults del
paper; el resto se completa desde ``ScenarioConfig``. Al terminar cada corrida
se vuelca la configuracion *resuelta* junto a los resultados, de modo que el
directorio de salida contenga todo lo necesario para reproducirla.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Union

import yaml

from .schema import ConfigError, ScenarioConfig

__all__ = ["load_scenario", "dump_scenario", "default_scenario"]

PathLike = Union[str, Path]


def default_scenario() -> ScenarioConfig:
    """Escenario de replicacion del paper, sin ningun override."""
    return ScenarioConfig()


def load_scenario(path: PathLike) -> ScenarioConfig:
    """Carga un escenario desde YAML, validando claves y rangos."""
    p = Path(path)
    if not p.is_file():
        raise ConfigError("no existe el archivo de escenario: " + str(p))

    with p.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ConfigError(
            "el escenario debe ser un mapeo YAML, se recibio "
            + type(raw).__name__
        )

    try:
        return ScenarioConfig.from_dict(raw)
    except ConfigError as exc:
        raise ConfigError("en " + str(p) + ": " + str(exc)) from exc


def dump_scenario(config: ScenarioConfig, path: PathLike) -> Path:
    """Vuelca la configuracion resuelta a YAML y devuelve la ruta escrita."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data: Dict[str, Any] = config.to_dict()
    with p.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return p
