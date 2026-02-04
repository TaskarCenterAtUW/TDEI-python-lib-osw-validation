import json
import os
import unittest

import jsonschema_rs


SCHEMA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "src",
    "python_osw_validation",
    "schema",
)
SCHEMA_URI = "https://sidewalks.washington.edu/opensidewalks/0.3/schema.json"


def _load_schema(filename: str):
    path = os.path.join(SCHEMA_DIR, filename)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _validate(filename: str, data: dict) -> bool:
    schema = _load_schema(filename)
    return jsonschema_rs.Draft7Validator(schema).is_valid(data)


def _feature_collection(feature):
    return {"$schema": SCHEMA_URI, "type": "FeatureCollection", "features": [feature]}


def _point_tree(leaf_cycle: str):
    return _feature_collection(
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [0, 0]},
            "properties": {"_id": "p1", "natural": "tree", "leaf_cycle": leaf_cycle},
        }
    )


def _line_tree_row(leaf_cycle: str):
    return _feature_collection(
        {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
            "properties": {"_id": "l1", "natural": "tree_row", "leaf_cycle": leaf_cycle},
        }
    )


def _polygon_wood(leaf_cycle: str):
    return _feature_collection(
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
            },
            "properties": {"_id": "g1", "natural": "wood", "leaf_cycle": leaf_cycle},
        }
    )


class TestLeafCycleValidation(unittest.TestCase):
    def test_points_leaf_cycle_accepts_deciduous(self):
        data = _point_tree("deciduous")
        self.assertTrue(_validate("opensidewalks.points.schema-0.3.json", data))

    def test_points_leaf_cycle_rejects_mixed(self):
        data = _point_tree("mixed")
        self.assertFalse(_validate("opensidewalks.points.schema-0.3.json", data))

    def test_lines_leaf_cycle_accepts_mixed(self):
        data = _line_tree_row("mixed")
        self.assertTrue(_validate("opensidewalks.lines.schema-0.3.json", data))

    def test_lines_leaf_cycle_rejects_semi_deciduous(self):
        data = _line_tree_row("semi_deciduous")
        self.assertFalse(_validate("opensidewalks.lines.schema-0.3.json", data))

    def test_polygons_leaf_cycle_accepts_mixed(self):
        data = _polygon_wood("mixed")
        self.assertTrue(_validate("opensidewalks.polygons.schema-0.3.json", data))

    def test_polygons_leaf_cycle_rejects_semi_evergreen(self):
        data = _polygon_wood("semi_evergreen")
        self.assertFalse(_validate("opensidewalks.polygons.schema-0.3.json", data))


if __name__ == "__main__":
    unittest.main()
