import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import jsonschema_rs

from ..helpers import (
    _add_additional_properties_hint,
    _err_kind,
    _feature_index_from_error,
    _pretty_message,
)
from .common import is_nullish


def schema_error_code(error_kind: str) -> str:
    """Convert a JSON Schema error kind to a stable upper-snake-case code."""
    if not error_kind:
        return "SCHEMA_VALIDATION"
    normalized = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", error_kind)
    return f"SCHEMA_{normalized.upper()}"


def _schema_error_kind(error: Any) -> str:
    error_kind = _err_kind(error)
    if error_kind:
        return error_kind
    schema_path = list(getattr(error, "schema_path", []) or [])
    return schema_path[-1] if schema_path and isinstance(schema_path[-1], str) else ""


@dataclass(frozen=True)
class SchemaValidationOutcome:
    errors: List[str]
    issues: List[Dict[str, Any]]
    continue_validation: bool


def schema_key_from_text(text: Optional[str], dataset_keys: Iterable[str]) -> Optional[str]:
    if not text:
        return None

    basename = os.path.basename(text).lower()
    for key in dataset_keys:
        if (
            basename == f"{key}.geojson"
            or basename == f"{key}.osw.geojson"
            or basename.endswith(f".{key}.geojson")
            or basename.endswith(f".{key}.osw.geojson")
        ):
            return key
    return None


def schema_key_from_url(schema_url: Any, dataset_keys: Iterable[str]) -> Optional[str]:
    if not isinstance(schema_url, str):
        return None

    lower_url = schema_url.lower()
    for key in dataset_keys:
        if lower_url.endswith(f"/{key}.schema.json"):
            return key
    return None


def collect_nullish_property_paths(obj: Any, prefix: str = "") -> List[Tuple[str, Any]]:
    paths: List[Tuple[str, Any]] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            paths.extend(collect_nullish_property_paths(value, next_prefix))
        return paths
    if isinstance(obj, list):
        for index, value in enumerate(obj):
            next_prefix = f"{prefix}[{index}]" if prefix else f"[{index}]"
            paths.extend(collect_nullish_property_paths(value, next_prefix))
        return paths
    if is_nullish(obj):
        paths.append((prefix or "value", obj))
    return paths


def collect_nullish_extension_property_paths(props: Dict[str, Any]) -> List[Tuple[str, Any]]:
    paths: List[Tuple[str, Any]] = []
    for key, value in props.items():
        if isinstance(key, str) and key.startswith("ext:"):
            paths.extend(collect_nullish_property_paths(value, key))
    return paths


def disallowed_legacy_02_features(geojson_data: Dict[str, Any]) -> set:
    """Return unsupported tree/custom content categories found in OSW 0.2 data."""
    reasons = set()
    for feature in geojson_data.get("features", []):
        props = feature.get("properties") or {}
        natural = props.get("natural")
        if isinstance(natural, str) and natural.strip().lower() in {"tree", "wood"}:
            reasons.add("tree")
        if any(key in props for key in ("leaf_cycle", "leaf_type")):
            reasons.add("tree")
        for key, value in props.items():
            target = value.lower() if isinstance(value, str) else key.lower() if isinstance(key, str) else ""
            if any(token in target for token in (
                "custom point", "custom_point", "custompoint",
                "custom line", "custom_line", "customline",
                "custom polygon", "custom_polygon", "custompolygon",
            )):
                reasons.add("custom_token")
    return reasons


def prevalidate_geojson(
    geojson_data: Dict[str, Any],
    filename: str,
    dataset_key: str,
    max_errors: int,
) -> Optional[SchemaValidationOutcome]:
    """Run extension-null and OSW 0.2 compatibility checks before JSON Schema."""
    errors: List[str] = []
    issues: List[Dict[str, Any]] = []
    features = geojson_data.get("features", []) if isinstance(geojson_data, dict) else []
    for index, feature in enumerate(features):
        if not isinstance(feature, dict):
            continue
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            continue
        for path, bad_value in collect_nullish_extension_property_paths(properties):
            if len(errors) >= max_errors:
                return SchemaValidationOutcome(errors, issues, False)
            rendered = f'"{bad_value}"' if isinstance(bad_value, str) else str(bad_value)
            message = (
                f"Invalid value at '{path}': {rendered}. "
                "Null/NaN placeholders are not allowed; provide a valid value or remove this property."
            )
            errors.append(f"Validation error: {message}")
            issues.append({
                "filename": filename,
                "feature_index": index,
                "error_message": [message],
                "code": "NULLISH_EXTENSION_VALUE",
                "severity": "error",
            })
    if errors:
        return SchemaValidationOutcome(errors, issues, False)

    schema_url = geojson_data.get('$schema')
    if isinstance(schema_url, str) and '0.2/schema.json' in schema_url:
        reasons = disallowed_legacy_02_features(geojson_data)
        if reasons:
            labels = {
                "edges": "Custom Edge",
                "lines": "Custom Line",
                "polygons": "Custom Polygon",
                "zones": "Custom Polygon/Zone",
                "points": "Custom Point",
                "nodes": "Custom Node",
            }
            parts = []
            if "tree" in reasons:
                parts.append("Tree coverage")
            if "custom_ext" in reasons or "custom_token" in reasons:
                parts.append(labels.get(dataset_key, "Custom content"))
            message = "0.2 schema does not support " + " and ".join(parts)
            return SchemaValidationOutcome(
                [message],
                [{
                    "filename": filename,
                    "feature_index": None,
                    "error_message": message,
                    "code": "UNSUPPORTED_OSW_02_CONTENT",
                    "severity": "error",
                }],
                False,
            )
    return None


def validate_against_schema(
    geojson_data: Dict[str, Any],
    filename: str,
    schema: Dict[str, Any],
    max_errors: int,
) -> SchemaValidationOutcome:
    """Stream JSON Schema failures into backward-compatible errors and issues."""
    errors: List[str] = []
    collected_issues: List[Dict[str, Any]] = []
    validator = jsonschema_rs.Draft7Validator(schema)

    for error in validator.iter_errors(geojson_data):
        if len(errors) >= max_errors:
            break
        raw_message = _add_additional_properties_hint(getattr(error, "message", "") or "")
        error_kind = _schema_error_kind(error)
        errors.append(f"Validation error: {raw_message}")
        feature_index = _feature_index_from_error(error)
        collected_issues.append({
            "filename": filename,
            "feature_index": feature_index if feature_index is not None else -1,
            "error_message": [_pretty_message(error, schema)],
            "code": schema_error_code(error_kind),
            "severity": "error",
            "_kind": error_kind,
        })

    has_specific_by_feature = {
        issue["feature_index"]
        for issue in collected_issues
        if issue.get("_kind") != "AnyOf"
    }
    issues = []
    for issue in collected_issues:
        if issue.get("_kind") == "AnyOf" and issue["feature_index"] in has_specific_by_feature:
            continue
        issue.pop("_kind", None)
        issues.append(issue)

    return SchemaValidationOutcome(errors, issues, len(errors) < max_errors)
