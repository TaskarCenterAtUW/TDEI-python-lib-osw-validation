import json
import os
import tempfile
import unittest

import src.python_osw_validation.helpers as helpers


class FakeErr:
    """Tiny stand-in for jsonschema_rs errors."""
    def __init__(self, instance_path=None, kind=None, validator=None, message="", schema_path=None):
        self.instance_path = instance_path if instance_path is not None else []
        self.kind = kind
        self.validator = validator
        self.message = message
        self.schema_path = schema_path if schema_path is not None else []


# ----- tests for _add_additional_properties_hint ------------------------------
class TestAddAdditionalPropertiesHint(unittest.TestCase):
    def test_appends_ext_hint_for_unexpected_tag(self):
        msg = "Additional properties are not allowed ('foo' was unexpected)"
        expected = "Additional properties are not allowed ('foo' was unexpected). If you want to carry this tag, change it to ext:foo"
        self.assertEqual(helpers._add_additional_properties_hint(msg), expected)

    def test_leaves_other_messages_unchanged(self):
        msg = "value must be one of [a, b, c]"
        self.assertEqual(helpers._add_additional_properties_hint(msg), msg)


# ----- tests for _feature_index_from_error ------------------------------------
class TestFeatureIndexFromError(unittest.TestCase):
    def test_feature_index_present(self):
        e = FakeErr(instance_path=["features", 5, "properties", "x"])
        self.assertEqual(helpers._feature_index_from_error(e), 5)

    def test_feature_index_absent(self):
        e = FakeErr(instance_path=["foo", "bar", 3])  # not "features/<n>"
        self.assertIsNone(helpers._feature_index_from_error(e))

    def test_feature_index_next_not_int(self):
        e = FakeErr(instance_path=["features", "not-an-int", "properties"])
        self.assertIsNone(helpers._feature_index_from_error(e))


# ----- tests for _err_kind -----------------------------------------------------
class TestErrKind(unittest.TestCase):
    def test_prefers_kind_object(self):
        # class name "Kind_Required" -> "Required"
        KindRequired = type("Kind_Required", (), {})
        e = FakeErr(kind=KindRequired())
        self.assertEqual(helpers._err_kind(e), "Required")

    def test_fallback_to_validator(self):
        e = FakeErr(kind=None, validator="anyOf")
        self.assertEqual(helpers._err_kind(e), "AnyOf")

    def test_fallback_to_message(self):
        e = FakeErr(kind=None, validator=None, message="... failed anyOf constraint ...")
        self.assertEqual(helpers._err_kind(e), "AnyOf")

    def test_empty_when_unknown(self):
        e = FakeErr(kind=None, validator=None, message="totally unrelated")
        self.assertEqual(helpers._err_kind(e), "")


# ----- tests for _clean_enum_message ------------------------------------------
class TestCleanEnumMessage(unittest.TestCase):
    def test_strips_other_candidates_and_trims(self):
        e = FakeErr(message="value 'x' not permitted or 2 other candidates\nextra details here")
        self.assertEqual(helpers._clean_enum_message(e), "value 'x' not permitted")

    def test_no_noise_no_change(self):
        e = FakeErr(message="must be one of [A,B,C]")
        self.assertEqual(helpers._clean_enum_message(e), "must be one of [A,B,C]")


# ----- tests for _pretty_message ----------------------------------------------
class TestPrettyMessage(unittest.TestCase):
    def test_enum_formats_human_readable_field_message(self):
        KindEnum = type("Kind_Enum", (), {})
        e = FakeErr(kind=KindEnum(),
                    instance_path=["features", 0, "properties", "climb"],
                    message='"null" is not one of "down" or "up" or 3 other candidates\nignore this')
        self.assertEqual(
            helpers._pretty_message(e, schema={}),
            "Invalid value at 'climb': 'null'. Acceptable values can be one of down|up, provide a valid value and retry again.",
        )

    def test_anyof_unions_required_fields(self):
        # Build a schema reachable via schema_path with anyOf/allOf nesting
        schema = {
            "properties": {
                "features": {
                    "items": {
                        "anyOf": [
                            {"required": ["a", "b"]},
                            {"allOf": [
                                {"required": ["c"]},
                                {"anyOf": [{"required": ["d"]}]}
                            ]},
                        ]
                    }
                }
            }
        }
        KindAnyOf = type("Kind_AnyOf", (), {})
        e = FakeErr(
            kind=KindAnyOf(),
            schema_path=["properties", "features", "items", "anyOf"],
            message="",
        )
        msg = helpers._pretty_message(e, schema)
        # Union should be a,b,c,d — order is sorted in helper
        self.assertEqual(msg, "must include one of: a, b, c, d")

    def test_default_first_line_from_message(self):
        e = FakeErr(kind=None, validator=None, message="first line only\nsecond line ignored")
        self.assertEqual(helpers._pretty_message(e, schema={}), "first line only")

    def test_type_with_enum_parent_uses_enum_style_message(self):
        KindType = type("Kind_Type", (), {})
        schema = {
            "properties": {
                "climb": {
                    "enum": ["down", "up"],
                    "type": "string",
                }
            }
        }
        e = FakeErr(
            kind=KindType(),
            instance_path=["features", 0, "properties", "climb"],
            schema_path=["properties", "climb", "type"],
            message='"null" is not of type "string"',
        )
        self.assertEqual(
            helpers._pretty_message(e, schema=schema),
            "Invalid value at 'climb': 'null'. Acceptable values can be one of down|up, provide a valid value and retry again.",
        )

    def test_type_formats_requires_value_message(self):
        KindType = type("Kind_Type", (), {})
        e = FakeErr(
            kind=KindType(),
            instance_path=["features", 0, "properties", "step_count"],
            schema_path=["properties", "step_count", "type"],
            message='"null" is not of type "integer"',
        )
        self.assertEqual(
            helpers._pretty_message(e, schema={"properties": {"step_count": {"type": "integer"}}}),
            "Invalid value at 'step_count': 'null' . Acceptable datatype is integer ; provide a valid value and retry",
        )

    def test_additional_properties_hint_is_applied(self):
        msg = "Additional properties are not allowed ('bar' was unexpected)"
        e = FakeErr(kind=None, validator=None, message=msg)
        expected = "Additional properties are not allowed ('bar' was unexpected). If you want to carry this tag, change it to ext:bar"
        self.assertEqual(helpers._pretty_message(e, schema={}), expected)


# ----- tests for _rank_for -----------------------------------------------------
class TestRankFor(unittest.TestCase):
    def test_ordering_by_kind(self):
        KEnum = type("Kind_Enum", (), {})
        KReq = type("Kind_Required", (), {})
        KPat = type("Kind_Pattern", (), {})
        KOther = type("Kind_SomethingElse", (), {})

        e_enum = FakeErr(kind=KEnum(), message="m1")
        e_req = FakeErr(kind=KReq(), message="m2")
        e_pat = FakeErr(kind=KPat(), message="m3")
        e_other = FakeErr(kind=KOther(), message="m4")

        self.assertLess(helpers._rank_for(e_req), helpers._rank_for(e_enum))
        self.assertLess(helpers._rank_for(e_enum), helpers._rank_for(e_pat))
        self.assertLess(helpers._rank_for(e_pat), helpers._rank_for(e_other))

    def test_tiebreaker_shorter_message_is_better(self):
        KType = type("Kind_Type", (), {})
        e_short = FakeErr(kind=KType(), message="short")
        e_long = FakeErr(kind=KType(), message="a much longer message to increase length")
        self.assertLess(helpers._rank_for(e_short), helpers._rank_for(e_long))


class TestReadGeojsonWithoutExt(unittest.TestCase):
    def _write_geojson(self, payload):
        fd, path = tempfile.mkstemp(suffix=".geojson")
        os.close(fd)
        with open(path, "w") as f:
            json.dump(payload, f)
        self.addCleanup(os.remove, path)
        return path

    def test_drops_ext_properties_with_mixed_types(self):
        """The bug we're fixing: ext:* values mixing numeric and string across
        features causes pyogrio dtype inference to fail. After stripping, the
        load should succeed and the ext:* column should not be present."""
        payload = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"_id": "a", "ext:TextRotation": 310.0, "name": "n1"},
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                },
                {
                    "type": "Feature",
                    "properties": {"_id": "b", "ext:TextRotation": "not_appl", "name": "n2"},
                    "geometry": {"type": "Point", "coordinates": [1, 1]},
                },
            ],
        }
        path = self._write_geojson(payload)
        gdf = helpers._read_geojson_without_ext(path)

        self.assertEqual(len(gdf), 2)
        self.assertNotIn("ext:TextRotation", gdf.columns)
        # Non-ext columns must be preserved for downstream integrity checks.
        self.assertIn("_id", gdf.columns)
        self.assertIn("name", gdf.columns)
        self.assertEqual(sorted(gdf["_id"].tolist()), ["a", "b"])

    def test_preserves_non_ext_properties(self):
        payload = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"_id": "x", "highway": "footway", "ext:foo": 1},
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                }
            ],
        }
        gdf = helpers._read_geojson_without_ext(self._write_geojson(payload))
        self.assertIn("highway", gdf.columns)
        self.assertNotIn("ext:foo", gdf.columns)
        self.assertEqual(gdf["highway"].iloc[0], "footway")

    def test_no_ext_properties_is_noop(self):
        payload = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"_id": "x", "highway": "footway"},
                    "geometry": {"type": "Point", "coordinates": [2, 3]},
                }
            ],
        }
        gdf = helpers._read_geojson_without_ext(self._write_geojson(payload))
        self.assertEqual(len(gdf), 1)
        self.assertEqual(gdf["highway"].iloc[0], "footway")
        self.assertEqual(gdf.geometry.iloc[0].x, 2)
        self.assertEqual(gdf.geometry.iloc[0].y, 3)

    def test_empty_feature_collection(self):
        payload = {"type": "FeatureCollection", "features": []}
        gdf = helpers._read_geojson_without_ext(self._write_geojson(payload))
        self.assertEqual(len(gdf), 0)

    def test_crs_is_propagated_when_present(self):
        payload = {
            "type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
            "features": [
                {
                    "type": "Feature",
                    "properties": {"_id": "x"},
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                }
            ],
        }
        gdf = helpers._read_geojson_without_ext(self._write_geojson(payload))
        self.assertIsNotNone(gdf.crs)


if __name__ == "__main__":
    unittest.main()
