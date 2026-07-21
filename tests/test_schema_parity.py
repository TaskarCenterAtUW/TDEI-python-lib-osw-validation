import json
from pathlib import Path

import jsonschema_rs

SCHEMA_DIR = Path(__file__).parent.parent / "src" / "python_osw_validation" / "schema"
FIXTURES_DIR = Path(__file__).parent / "schema" / "fixtures"

SCHEMAS = {
    dataset: f"opensidewalks.{dataset}.schema-0.3.json"
    for dataset in ("nodes", "edges", "zones", "points", "lines", "polygons")
}


def load(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def validator(schema_name: str):
    schema = load(SCHEMA_DIR / SCHEMAS[schema_name])
    return jsonschema_rs.Draft7Validator(schema)


def run_fixture(schema_name: str, fixture_name: str):
    data = load(FIXTURES_DIR / schema_name / fixture_name)
    return data


def test_all_supported_dataset_schemas_are_packaged_and_loadable():
    for dataset in SCHEMAS:
        assert validator(dataset)


# --- Nodes ---

def test_nodes_accept_custom_node_fields():
    data = run_fixture("nodes", "valid_custom_node.json")
    assert validator("nodes").is_valid(data)


# --- Edges ---

def test_edges_accept_custom_edge_fields():
    data = run_fixture("edges", "valid_custom_edge.json")
    assert validator("edges").is_valid(data)


def test_edges_accept_custom_edge_without_highway():
    data = run_fixture("edges", "valid_custom_edge_no_highway.json")
    assert validator("edges").is_valid(data)


def test_edges_schema_02_guard_leaves_extension_properties_to_schema_validation():
    data = run_fixture("edges", "invalid_custom_edge_schema02.json")
    # The compatibility guard only handles custom tokens and tree coverage.
    from src.python_osw_validation import OSWValidation
    guard = OSWValidation(zipfile_path="dummy.zip")
    reasons = guard._contains_disallowed_features_for_02(data)
    assert reasons == set()


def test_nodes_schema_02_allows_ext_fields():
    data = run_fixture("nodes", "valid_node_ext_schema02.json")
    from src.python_osw_validation import OSWValidation
    guard = OSWValidation(zipfile_path="dummy.zip")
    reasons = guard._contains_disallowed_features_for_02(data)
    assert reasons == set()


def test_custom_point_schema03_accepts():
    data = run_fixture("points", "valid_custom_point.json")
    assert validator("points").is_valid(data)


def test_custom_point_schema02_rejects_custom_flag():
    data = run_fixture("points", "invalid_custom_point_schema02.json")
    from src.python_osw_validation import OSWValidation
    guard = OSWValidation(zipfile_path="dummy.zip")
    reasons = guard._contains_disallowed_features_for_02(data)
    assert reasons == {"custom_token"}


def test_custom_line_schema03_accepts():
    data = run_fixture("lines", "valid_custom_line.json")
    assert validator("lines").is_valid(data)


def test_custom_line_schema02_guard_leaves_ext_to_schema_validation():
    data = run_fixture("lines", "invalid_custom_line_schema02.json")
    from src.python_osw_validation import OSWValidation
    guard = OSWValidation(zipfile_path="dummy.zip")
    reasons = guard._contains_disallowed_features_for_02(data)
    assert reasons == set()


def test_custom_polygon_schema03_accepts():
    data = run_fixture("polygons", "valid_custom_polygon.json")
    assert validator("polygons").is_valid(data)


def test_custom_polygon_schema02_guard_leaves_ext_to_schema_validation():
    data = run_fixture("polygons", "invalid_custom_polygon_schema02.json")
    from src.python_osw_validation import OSWValidation
    guard = OSWValidation(zipfile_path="dummy.zip")
    reasons = guard._contains_disallowed_features_for_02(data)
    assert reasons == set()


def test_custom_zone_schema02_guard_leaves_ext_to_schema_validation():
    data = run_fixture("zones", "invalid_custom_zone_schema02.json")
    from src.python_osw_validation import OSWValidation
    guard = OSWValidation(zipfile_path="dummy.zip")
    reasons = guard._contains_disallowed_features_for_02(data)
    assert reasons == set()


# --- Zones ---

def test_zones_accept_custom_zone_fields():
    data = run_fixture("zones", "valid_custom_zone.json")
    assert validator("zones").is_valid(data)


def test_zones_accept_custom_zone_without_highway():
    data = run_fixture("zones", "valid_custom_zone_no_highway.json")
    assert validator("zones").is_valid(data)
