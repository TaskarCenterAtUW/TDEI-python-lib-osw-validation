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
    def test_enum_compacts_message(self):
        KindEnum = type("Kind_Enum", (), {})
        e = FakeErr(kind=KindEnum(),
                    message="not in allowed set or 3 other candidates\nignore this")
        self.assertEqual(helpers._pretty_message(e, schema={}), "not in allowed set")

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

        self.assertLess(helpers._rank_for(e_enum), helpers._rank_for(e_req))
        self.assertLess(helpers._rank_for(e_req), helpers._rank_for(e_pat))
        self.assertLess(helpers._rank_for(e_pat), helpers._rank_for(e_other))

    def test_tiebreaker_shorter_message_is_better(self):
        KType = type("Kind_Type", (), {})
        e_short = FakeErr(kind=KType(), message="short")
        e_long = FakeErr(kind=KType(), message="a much longer message to increase length")
        self.assertLess(helpers._rank_for(e_short), helpers._rank_for(e_long))


if __name__ == "__main__":
    unittest.main()
