import json
import os
import unittest


SCHEMA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "src",
    "python_osw_validation",
    "schema",
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


if __name__ == "__main__":
    unittest.main()
