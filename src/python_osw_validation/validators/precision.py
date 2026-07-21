import json
from typing import Callable, Iterable

from ..helpers import _geojson_file_has_excess_coordinate_precision


def has_excess_coordinate_precision(
    file_paths: Iterable[str],
    checker: Callable = _geojson_file_has_excess_coordinate_precision,
) -> bool:
    """Return True when any readable input contains coordinates over seven decimals."""
    for file_path in file_paths:
        try:
            if checker(str(file_path)):
                return True
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            # Parsing and schema validation own functional input errors.
            continue
    return False
