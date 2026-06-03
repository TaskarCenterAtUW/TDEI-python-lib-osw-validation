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
SCHEMA_PATH = os.path.join(
    SCHEMA_DIR,
    "opensidewalks.schema-0.3.json",
)


class TestSchemaDefinitionsExist(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            cls.schema = json.load(f)

    def test_definitions_present_with_required_fields(self):
        feature_requirements = {
            "Tree": ["geometry", "properties", "type"],
            "TreeFields": ["_id", "natural"],
            "TreeRow": ["geometry", "properties", "type"],
            "TreeRowFields": ["_id", "natural"],
            "CustomPoint": ["geometry", "properties", "type"],
            "CustomPointFields": ["_id"],
            "CustomLine": ["geometry", "properties", "type"],
            "CustomLineFields": ["_id"],
            "CustomPolygon": ["geometry", "properties", "type"],
            "CustomPolygonFields": ["_id"],
            "Wood": ["geometry", "properties", "type"],
            "WoodFields": ["_id", "natural"],
        }

        definitions = self.schema.get("definitions", {})
        for name, required_fields in feature_requirements.items():
            with self.subTest(definition=name):
                self.assertIn(name, definitions, f"{name} definition missing from schema")
                required = definitions[name].get("required", [])
                for field in required_fields:
                    self.assertIn(field, required, f"{name} should require '{field}'")


class TestLengthSchemaDefinitions(unittest.TestCase):
    def _validator(self, schema_filename):
        schema_path = os.path.join(SCHEMA_DIR, schema_filename)
        with open(schema_path, encoding="utf-8") as f:
            return jsonschema_rs.Draft7Validator(json.load(f))

    def _feature_collection(self, properties):
        return {
            "$schema": "https://sidewalks.washington.edu/opensidewalks/0.3/schema.json",
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[0, 0], [1, 1]],
                    },
                    "properties": properties,
                }
            ],
        }

    def test_edges_length_allows_values_over_5000_meters(self):
        validator = self._validator("opensidewalks.edges.schema-0.3.json")
        data = self._feature_collection({
            "_id": "edge-1",
            "_u_id": "node-a",
            "_v_id": "node-b",
            "footway": "sidewalk",
            "highway": "footway",
            "length": 6629.35,
        })

        self.assertTrue(validator.is_valid(data))

    def test_lines_length_allows_values_over_5000_meters(self):
        validator = self._validator("opensidewalks.lines.schema-0.3.json")
        data = self._feature_collection({
            "_id": "line-1",
            "barrier": "fence",
            "length": 6629.35,
        })

        self.assertTrue(validator.is_valid(data))

    def test_length_allows_zero(self):
        validator = self._validator("opensidewalks.edges.schema-0.3.json")
        data = self._feature_collection({
            "_id": "edge-1",
            "_u_id": "node-a",
            "_v_id": "node-b",
            "footway": "sidewalk",
            "highway": "footway",
            "length": 0,
        })

        self.assertTrue(validator.is_valid(data))

    def test_length_rejects_minus_one(self):
        validator = self._validator("opensidewalks.edges.schema-0.3.json")
        data = self._feature_collection({
            "_id": "edge-1",
            "_u_id": "node-a",
            "_v_id": "node-b",
            "footway": "sidewalk",
            "highway": "footway",
            "length": -1,
        })

        self.assertFalse(validator.is_valid(data))


if __name__ == "__main__":
    unittest.main()
