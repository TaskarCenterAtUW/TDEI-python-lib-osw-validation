import math
import numbers
from typing import Any


def is_nullish(value: Any) -> bool:
    if value is None:
        return True
    return isinstance(value, numbers.Real) and math.isnan(value)


def feature_identifier(row, feature_index: Any) -> Any:
    feature_id = row.get('_id', feature_index)
    return feature_index if is_nullish(feature_id) else feature_id
