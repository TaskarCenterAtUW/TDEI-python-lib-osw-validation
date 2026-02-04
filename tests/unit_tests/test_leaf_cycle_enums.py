import json
import os
import unittest


SCHEMA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "src",
    "python_osw_validation",
    "schema",
)

SCHEMA_FILES = {
    "lines": "opensidewalks.lines.schema-0.3.json",
    "points": "opensidewalks.points.schema-0.3.json",
    "polygons": "opensidewalks.polygons.schema-0.3.json",
}


def _load_schema(schema_name: str):
    path = os.path.join(SCHEMA_DIR, SCHEMA_FILES[schema_name])
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _collect_leaf_cycle_enums(schema):
    enums = []

    def walk(node):
        if isinstance(node, dict):
            leaf = node.get("leaf_cycle")
            if isinstance(leaf, dict) and "enum" in leaf:
                enums.append(leaf["enum"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(schema)
    return enums


class TestLeafCycleEnums(unittest.TestCase):
    def _assert_leaf_cycle_values(self, schema_name, expected):
        schema = _load_schema(schema_name)
        enums = _collect_leaf_cycle_enums(schema)
        self.assertTrue(enums, f"{schema_name} schema missing leaf_cycle enums")
        for enum in enums:
            self.assertEqual(
                set(enum),
                expected,
                f"{schema_name} leaf_cycle enum mismatch: {enum}",
            )

    def test_lines_leaf_cycle_enum(self):
        self._assert_leaf_cycle_values("lines", {"deciduous", "evergreen", "mixed"})

    def test_points_leaf_cycle_enum(self):
        self._assert_leaf_cycle_values("points", {"deciduous", "evergreen"})

    def test_polygons_leaf_cycle_enum(self):
        self._assert_leaf_cycle_values("polygons", {"deciduous", "evergreen", "mixed"})


if __name__ == "__main__":
    unittest.main()
