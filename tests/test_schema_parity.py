import json
from pathlib import Path

import jsonschema_rs

SCHEMA_DIR = Path(__file__).parent.parent / "src" / "python_osw_validation" / "schema"
FIXTURES_DIR = Path(__file__).parent / "schema" / "fixtures"

SOURCE_SCHEMA = "opensidewalks.schema-0.3.json"
SHORT_SCHEMAS = {
    "nodes": "opensidewalks.nodes.schema-0.3.json",
    "edges": "opensidewalks.edges.schema-0.3.json",
    "points": "opensidewalks.points.schema-0.3.json",
    "lines": "opensidewalks.lines.schema-0.3.json",
    "polygons": "opensidewalks.polygons.schema-0.3.json",
    "zones": "opensidewalks.zones.schema-0.3.json",
}


def load(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def validator(schema_name: str, customized: bool):
    fname = SHORT_SCHEMAS[schema_name] if customized else SOURCE_SCHEMA
    schema = load(SCHEMA_DIR / fname)
    return jsonschema_rs.Draft7Validator(schema)


def run_fixture(schema_name: str, fixture_name: str):
    data = load(FIXTURES_DIR / schema_name / fixture_name)
    return data


# --- Nodes ---

def test_nodes_accept_custom_node_fields():
    data = run_fixture("nodes", "valid_custom_node.json")
    orig = validator("nodes", customized=False)
    ours = validator("nodes", customized=True)
    assert orig.is_valid(data)
    assert ours.is_valid(data)


# --- Edges ---

def test_edges_accept_custom_edge_fields():
    data = run_fixture("edges", "valid_custom_edge.json")
    orig = validator("edges", customized=False)
    ours = validator("edges", customized=True)
    assert orig.is_valid(data)
    assert ours.is_valid(data)


def test_edges_accept_custom_edge_without_highway():
    data = run_fixture("edges", "valid_custom_edge_no_highway.json")
    orig = validator("edges", customized=False)
    ours = validator("edges", customized=True)
    assert orig.is_valid(data)
    assert ours.is_valid(data)


def test_edges_schema_02_allows_ext_fields_without_custom_tokens():
    data = run_fixture("edges", "invalid_custom_edge_schema02.json")
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
    orig = validator("points", customized=False)
    ours = validator("points", customized=True)
    assert orig.is_valid(data)
    assert ours.is_valid(data)


def test_custom_point_schema02_rejects_custom_flag():
    data = run_fixture("points", "invalid_custom_point_schema02.json")
    from src.python_osw_validation import OSWValidation
    guard = OSWValidation(zipfile_path="dummy.zip")
    reasons = guard._contains_disallowed_features_for_02(data)
    assert reasons == {"custom_token"}


def test_custom_line_schema03_accepts():
    data = run_fixture("lines", "valid_custom_line.json")
    orig = validator("lines", customized=False)
    ours = validator("lines", customized=True)
    assert orig.is_valid(data)
    assert ours.is_valid(data)


def test_line_schema02_allows_ext_fields_without_custom_tokens():
    data = run_fixture("lines", "invalid_custom_line_schema02.json")
    from src.python_osw_validation import OSWValidation
    guard = OSWValidation(zipfile_path="dummy.zip")
    reasons = guard._contains_disallowed_features_for_02(data)
    assert reasons == set()


def test_custom_polygon_schema03_accepts():
    data = run_fixture("polygons", "valid_custom_polygon.json")
    orig = validator("polygons", customized=False)
    ours = validator("polygons", customized=True)
    assert orig.is_valid(data)
    assert ours.is_valid(data)


def test_polygon_schema02_allows_ext_fields_without_custom_tokens():
    data = run_fixture("polygons", "invalid_custom_polygon_schema02.json")
    from src.python_osw_validation import OSWValidation
    guard = OSWValidation(zipfile_path="dummy.zip")
    reasons = guard._contains_disallowed_features_for_02(data)
    assert reasons == set()


def test_zone_schema02_allows_ext_fields_without_custom_tokens():
    data = run_fixture("zones", "invalid_custom_zone_schema02.json")
    from src.python_osw_validation import OSWValidation
    guard = OSWValidation(zipfile_path="dummy.zip")
    reasons = guard._contains_disallowed_features_for_02(data)
    assert reasons == set()


# --- Zones ---

def test_zones_accept_custom_zone_fields():
    data = run_fixture("zones", "valid_custom_zone.json")
    orig = validator("zones", customized=False)
    ours = validator("zones", customized=True)
    assert orig.is_valid(data)
    assert ours.is_valid(data)


def test_zones_accept_custom_zone_without_highway():
    data = run_fixture("zones", "valid_custom_zone_no_highway.json")
    orig = validator("zones", customized=False)
    ours = validator("zones", customized=True)
    assert orig.is_valid(data)
    assert ours.is_valid(data)
