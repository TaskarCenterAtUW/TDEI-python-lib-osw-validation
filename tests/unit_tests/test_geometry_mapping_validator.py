"""Unit tests for python_osw_validation.geometry_mapping_validator."""
from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from typing import Any, Dict, List

# Make `src` importable for local development checkouts.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

# Import the geometry_mapping_validator module directly so this test file
# does not require the heavy optional dependencies (geopandas, jsonschema_rs)
# of the parent package's __init__.py. The module itself is pure Python.
_MOD_PATH = os.path.join(
    SRC, "python_osw_validation", "geometry_mapping_validator.py"
)
_spec = importlib.util.spec_from_file_location(
    "_geometry_mapping_validator", _MOD_PATH
)
_geometry_mapping_validator = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_geometry_mapping_validator)

build_node_coord_index = _geometry_mapping_validator.build_node_coord_index
run_geometry_mapping_validation = _geometry_mapping_validator.run_geometry_mapping_validation
validate_edge_node_mapping = _geometry_mapping_validator.validate_edge_node_mapping
validate_zone_node_mapping = _geometry_mapping_validator.validate_zone_node_mapping


def _node(node_id: str, lon: float, lat: float) -> Dict[str, Any]:
    return {
        "type": "Feature",
        "properties": {"_id": node_id},
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
    }


def _nodes(*pairs) -> Dict[str, Any]:
    return {"type": "FeatureCollection", "features": [_node(*p) for p in pairs]}


def _edge(edge_id: str, u_id: str, v_id: str, coords: List[List[float]]) -> Dict[str, Any]:
    return {
        "type": "Feature",
        "properties": {"_id": edge_id, "_u_id": u_id, "_v_id": v_id},
        "geometry": {"type": "LineString", "coordinates": coords},
    }


def _edges(*features) -> Dict[str, Any]:
    return {"type": "FeatureCollection", "features": list(features)}


def _zone(zone_id: str, w_ids: List[str], ring: List[List[float]]) -> Dict[str, Any]:
    return {
        "type": "Feature",
        "properties": {"_id": zone_id, "_w_id": w_ids},
        "geometry": {"type": "Polygon", "coordinates": [ring]},
    }


def _zones(*features) -> Dict[str, Any]:
    return {"type": "FeatureCollection", "features": list(features)}


def _messages(issues: List[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    for it in issues:
        msgs = it.get("error_message") or []
        if msgs:
            out.append(msgs[0])
    return out


class BuildNodeCoordIndexTests(unittest.TestCase):
    def test_returns_empty_for_invalid_inputs(self):
        self.assertEqual(build_node_coord_index(None), {})
        self.assertEqual(build_node_coord_index({}), {})
        self.assertEqual(build_node_coord_index({"features": "not a list"}), {})

    def test_indexes_valid_nodes_only(self):
        nodes = _nodes(("n1", 1.0, 2.0), ("n2", 3.0, 4.0))
        # Add a malformed feature that should be skipped
        nodes["features"].append({"type": "Feature", "properties": {"_id": "bad"}})
        nodes["features"].append({"type": "Feature", "properties": {},
                                  "geometry": {"type": "Point", "coordinates": [9, 9]}})
        idx = build_node_coord_index(nodes)
        self.assertEqual(idx, {"n1": (1.0, 2.0), "n2": (3.0, 4.0)})

    def test_first_id_wins_when_duplicates(self):
        nodes = _nodes(("n1", 1.0, 2.0), ("n1", 9.0, 9.0))
        idx = build_node_coord_index(nodes)
        self.assertEqual(idx["n1"], (1.0, 2.0))


class EdgeMappingTests(unittest.TestCase):
    def setUp(self):
        self.nodes = _nodes(("n1", 0.0, 0.0), ("n2", 1.0, 1.0))
        self.node_idx = build_node_coord_index(self.nodes)

    def test_valid_edge_passes(self):
        edges = _edges(_edge("e1", "n1", "n2", [[0.0, 0.0], [0.5, 0.5], [1.0, 1.0]]))
        issues = validate_edge_node_mapping(edges, self.node_idx)
        self.assertEqual(issues, [])

    def test_missing_u_id_reports_per_feature(self):
        edges = _edges({
            "type": "Feature",
            "properties": {"_id": "e1", "_v_id": "n2"},
            "geometry": {"type": "LineString", "coordinates": [[0.0, 0.0], [1.0, 1.0]]},
        })
        issues = validate_edge_node_mapping(edges, self.node_idx)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["feature_index"], 0)
        self.assertEqual(issues[0]["feature_id"], "e1")
        self.assertIn("_u_id", issues[0]["error_message"][0])

    def test_unknown_reference_reports(self):
        edges = _edges(_edge("e1", "ghost", "n2", [[0.0, 0.0], [1.0, 1.0]]))
        msgs = _messages(validate_edge_node_mapping(edges, self.node_idx))
        self.assertTrue(any("does not reference any node" in m for m in msgs))
        self.assertTrue(any("'ghost'" in m for m in msgs))

    def test_coordinate_mismatch_reports(self):
        # _u_id correct id but the line does not start at n1's coordinate.
        edges = _edges(_edge("e1", "n1", "n2", [[5.0, 5.0], [1.0, 1.0]]))
        msgs = _messages(validate_edge_node_mapping(edges, self.node_idx))
        self.assertTrue(any("coordinate mismatch" in m for m in msgs))
        self.assertTrue(any("(5.0, 5.0)" in m for m in msgs))
        self.assertTrue(any("(0.0, 0.0)" in m for m in msgs))

    def test_filename_propagates_into_issue(self):
        edges = _edges(_edge("e1", "ghost", "n2", [[0.0, 0.0], [1.0, 1.0]]))
        issues = validate_edge_node_mapping(edges, self.node_idx, edges_filename="awesome.edges.geojson")
        self.assertEqual(issues[0]["filename"], "awesome.edges.geojson")

    def test_skips_coordinate_check_when_no_nodes(self):
        edges = _edges(_edge("e1", "n1", "n2", [[5.0, 5.0], [9.0, 9.0]]))
        issues = validate_edge_node_mapping(edges, {}, nodes_present=False)
        self.assertEqual(issues, [])


class ZoneMappingTests(unittest.TestCase):
    def setUp(self):
        # A square: (0,0)-(1,0)-(1,1)-(0,1)
        self.nodes = _nodes(("a", 0.0, 0.0), ("b", 1.0, 0.0),
                            ("c", 1.0, 1.0), ("d", 0.0, 1.0))
        self.node_idx = build_node_coord_index(self.nodes)
        self.ring_closed = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]
        self.w_ids = ["a", "b", "c", "d"]

    def test_valid_zone_passes(self):
        zones = _zones(_zone("z1", self.w_ids, self.ring_closed))
        self.assertEqual(validate_zone_node_mapping(zones, self.node_idx), [])

    def test_open_ring_also_valid(self):
        ring_open = self.ring_closed[:-1]
        zones = _zones(_zone("z1", self.w_ids, ring_open))
        self.assertEqual(validate_zone_node_mapping(zones, self.node_idx), [])

    def test_missing_w_id_reports(self):
        zone = {"type": "Feature", "properties": {"_id": "z1"},
                "geometry": {"type": "Polygon", "coordinates": [self.ring_closed]}}
        msgs = _messages(validate_zone_node_mapping(_zones(zone), self.node_idx))
        self.assertTrue(any("missing required '_w_id'" in m for m in msgs))

    def test_w_id_not_array_reports(self):
        zone = {"type": "Feature", "properties": {"_id": "z1", "_w_id": "not-a-list"},
                "geometry": {"type": "Polygon", "coordinates": [self.ring_closed]}}
        msgs = _messages(validate_zone_node_mapping(_zones(zone), self.node_idx))
        self.assertTrue(any("must be an array" in m for m in msgs))

    def test_unknown_w_id_reports(self):
        zones = _zones(_zone("z1", ["a", "b", "ghost", "d"], self.ring_closed))
        msgs = _messages(validate_zone_node_mapping(zones, self.node_idx))
        self.assertTrue(any("unknown node id" in m for m in msgs))
        self.assertTrue(any("ghost" in m for m in msgs))

    def test_length_mismatch_reports(self):
        zones = _zones(_zone("z1", ["a", "b", "c"], self.ring_closed))  # 3 ids vs 4 vertices
        msgs = _messages(validate_zone_node_mapping(zones, self.node_idx))
        self.assertTrue(any("must align" in m for m in msgs))

    def test_ring_coordinate_mismatch_reports(self):
        # All ids resolve but order is wrong → coordinates don't line up.
        zones = _zones(_zone("z1", ["a", "c", "b", "d"], self.ring_closed))
        msgs = _messages(validate_zone_node_mapping(zones, self.node_idx))
        self.assertTrue(any("does not match" in m for m in msgs))


class IntegrationTests(unittest.TestCase):
    def test_runs_all_validators_and_aggregates(self):
        nodes = _nodes(("n1", 0.0, 0.0), ("n2", 1.0, 1.0),
                       ("a", 0.0, 0.0), ("b", 1.0, 0.0),
                       ("c", 1.0, 1.0), ("d", 0.0, 1.0))
        edges = _edges(_edge("e_bad", "n1", "ghost", [[0.0, 0.0], [9.0, 9.0]]))
        zones = _zones(_zone("z_bad", ["a", "c", "b", "d"],
                             [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]))
        issues = run_geometry_mapping_validation(
            nodes_geojson=nodes,
            edges_geojson=edges,
            zones_geojson=zones,
            filenames={"edges": "edges.geojson", "zones": "zones.geojson"},
        )
        # We expect:
        #   - one for edge unknown _v_id
        #   - one for edge _u_id coordinate mismatch (n1=(0,0) vs (0,0)) actually ok, so just unknown ref
        #   - zone ring mismatch
        self.assertGreaterEqual(len(issues), 2)
        self.assertTrue(any(i["filename"] == "edges.geojson" for i in issues))
        self.assertTrue(any(i["filename"] == "zones.geojson" for i in issues))
        # Each issue carries feature_index and feature_id
        for it in issues:
            self.assertIn("feature_index", it)
            self.assertIn("feature_id", it)

    def test_no_issues_when_dataset_is_consistent(self):
        nodes = _nodes(("n1", 0.0, 0.0), ("n2", 1.0, 1.0))
        edges = _edges(_edge("e1", "n1", "n2", [[0.0, 0.0], [1.0, 1.0]]))
        issues = run_geometry_mapping_validation(
            nodes_geojson=nodes,
            edges_geojson=edges,
            zones_geojson=None,
        )
        self.assertEqual(issues, [])

    def test_handles_missing_nodes_file_gracefully(self):
        # No nodes available → existence and coordinate checks become no-ops
        # but missing _u_id still flagged.
        edges = _edges({
            "type": "Feature",
            "properties": {"_id": "e1", "_v_id": "n2"},
            "geometry": {"type": "LineString", "coordinates": [[0.0, 0.0], [1.0, 1.0]]},
        })
        issues = run_geometry_mapping_validation(
            nodes_geojson=None,
            edges_geojson=edges,
            zones_geojson=None,
        )
        msgs = _messages(issues)
        self.assertTrue(any("_u_id" in m for m in msgs))


if __name__ == "__main__":
    unittest.main()
