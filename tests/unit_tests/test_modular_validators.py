import unittest
from unittest.mock import patch

import geopandas as gpd
from shapely.geometry import LineString, MultiLineString, Point, Polygon

from src.python_osw_validation import OSWValidation, ValidationConfig, ValidationResult
from src.python_osw_validation.validators.geometry import (
    geometry_vertex_count,
    validate_dataset_geometries,
)
from src.python_osw_validation.validators.identifiers import identifier_integrity_findings
from src.python_osw_validation.validators.mapping import (
    build_node_coord_map,
    edge_mapping_findings,
    zone_mapping_findings,
)
from src.python_osw_validation.validators.models import ValidationFinding
from src.python_osw_validation.validators.precision import has_excess_coordinate_precision
from src.python_osw_validation.validators.schema import (
    collect_nullish_extension_property_paths,
    prevalidate_geojson,
    schema_error_code,
    schema_key_from_text,
    validate_against_schema,
)


class TestGeometryValidatorModule(unittest.TestCase):
    def test_pipeline_reports_collapsed_line_without_generic_duplicate(self):
        gdf = gpd.GeoDataFrame(
            {"_id": ["line-zero"], "geometry": [LineString([(1, 1), (1, 1)])]},
            geometry="geometry",
            crs="EPSG:4326",
        )

        result = validate_dataset_geometries(
            gdf,
            "lines",
            expected_geometry="LineString",
            display_limit=20,
            include_vertex_limit=True,
        )

        self.assertEqual(len(result.findings), 1)
        self.assertIn("zero-length geometry", result.findings[0].message)
        self.assertEqual(result.findings[0].code, "COLLAPSED_GEOMETRY")
        self.assertEqual(result.collapsed_indexes, {0})

    def test_pipeline_reports_vertex_limit_and_generic_type_error(self):
        long_line = LineString((float(index), float(index % 2)) for index in range(2001))
        gdf = gpd.GeoDataFrame(
            {
                "_id": ["line-long", "wrong-type"],
                "geometry": [long_line, Point(0, 0)],
            },
            geometry="geometry",
            crs="EPSG:4326",
        )

        result = validate_dataset_geometries(
            gdf,
            "lines",
            expected_geometry="LineString",
            display_limit=20,
            include_vertex_limit=True,
        )

        self.assertEqual(len(result.findings), 2)
        self.assertIn("2001 geometry vertices", result.findings[0].message)
        self.assertIn("invalid lines geometries", result.findings[1].message)

    def test_pipeline_allows_zero_length_line_when_configured(self):
        gdf = gpd.GeoDataFrame(
            {"_id": ["line-zero"], "geometry": [LineString([(1, 1), (1, 1)])]},
            geometry="geometry",
        )

        result = validate_dataset_geometries(
            gdf,
            "lines",
            expected_geometry="LineString",
            display_limit=20,
            include_vertex_limit=True,
            allow_zero_length_lines=True,
        )

        self.assertEqual(result.findings, [])
        self.assertEqual(result.collapsed_indexes, {0})

    def test_zero_area_polygon_remains_invalid_when_zero_length_lines_are_allowed(self):
        polygon = Polygon([(1, 1), (1, 1), (1, 1), (1, 1)])
        gdf = gpd.GeoDataFrame(
            {"_id": ["polygon-zero"], "geometry": [polygon]},
            geometry="geometry",
        )

        result = validate_dataset_geometries(
            gdf,
            "polygons",
            expected_geometry="Polygon",
            display_limit=20,
            include_vertex_limit=True,
            allow_zero_length_lines=True,
        )

        self.assertEqual(len(result.findings), 1)
        self.assertEqual(result.findings[0].code, "COLLAPSED_GEOMETRY")
        self.assertIn("zero-area geometry", result.findings[0].message)

    def test_collapsed_multiline_remains_invalid_when_zero_length_lines_are_allowed(self):
        gdf = gpd.GeoDataFrame(
            {
                "_id": ["multiline-zero"],
                "geometry": [MultiLineString([[(1, 1), (1, 1)]])],
            },
            geometry="geometry",
        )

        result = validate_dataset_geometries(
            gdf,
            "custom.geojson",
            expected_geometry=None,
            display_limit=20,
            include_vertex_limit=True,
            is_extension=True,
            allow_zero_length_lines=True,
        )

        self.assertEqual(len(result.findings), 1)
        self.assertEqual(result.findings[0].code, "COLLAPSED_GEOMETRY")

    def test_collapsed_line_in_point_dataset_remains_invalid_when_lines_are_allowed(self):
        gdf = gpd.GeoDataFrame(
            {"_id": ["wrong-node"], "geometry": [LineString([(1, 1), (1, 1)])]},
            geometry="geometry",
        )

        result = validate_dataset_geometries(
            gdf,
            "nodes",
            expected_geometry="Point",
            display_limit=20,
            include_vertex_limit=False,
            allow_zero_length_lines=True,
        )

        self.assertEqual(len(result.findings), 1)
        self.assertEqual(result.findings[0].code, "COLLAPSED_GEOMETRY")

    def test_polygon_ring_closure_is_not_counted_as_an_extra_vertex(self):
        polygon = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
        self.assertEqual(geometry_vertex_count(polygon), 4)


class TestIdentifierValidatorModule(unittest.TestCase):
    def test_duplicate_and_unmatched_references_return_findings(self):
        nodes = gpd.GeoDataFrame(
            {"_id": ["n1", "n1"], "geometry": [Point(0, 0), Point(0, 0)]},
            geometry="geometry",
        )
        edges = gpd.GeoDataFrame(
            {
                "_id": ["e1"],
                "_u_id": ["n1"],
                "_v_id": ["missing"],
                "geometry": [LineString([(0, 0), (1, 1)])],
            },
            geometry="geometry",
        )

        findings = identifier_integrity_findings(
            {"nodes": nodes, "edges": edges},
            display_limit=20,
        )

        self.assertEqual(len(findings), 2)
        self.assertIn("Duplicate _id's found in nodes", findings[0].message)
        self.assertIn("unmatched _v_id's", findings[1].message)


class TestMappingValidatorModule(unittest.TestCase):
    def test_mapping_modules_return_feature_level_findings(self):
        nodes = gpd.GeoDataFrame(
            {"_id": ["n1", "w1"], "geometry": [Point(0, 0), Point(5, 5)]},
            geometry="geometry",
        )
        edges = gpd.GeoDataFrame(
            {
                "_id": ["e1"],
                "_u_id": ["n1"],
                "geometry": [LineString([(1, 0), (2, 0)])],
            },
            geometry="geometry",
            index=[3],
        )
        zones = gpd.GeoDataFrame(
            {
                "_id": ["z1"],
                "_w_id": [["w1"]],
                "geometry": [Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
            },
            geometry="geometry",
            index=[4],
        )
        node_coordinates = build_node_coord_map(nodes)

        edge_findings = edge_mapping_findings(edges, node_coordinates)
        zone_findings = zone_mapping_findings(zones, node_coordinates)

        self.assertEqual(edge_findings[0].feature_index, 3)
        self.assertEqual(edge_findings[0].code, "EDGE_NODE_COORDINATE_MISMATCH")
        self.assertIn("_u_id mismatch", edge_findings[0].message)
        self.assertEqual(zone_findings[0].feature_index, 4)
        self.assertIn("_w_id coordinate mismatch", zone_findings[0].message)


class TestSupportValidatorModules(unittest.TestCase):
    def test_validation_config_preserves_existing_defaults(self):
        config = ValidationConfig()

        self.assertEqual(config.max_geometry_vertices, 2000)
        self.assertEqual(config.coordinate_precision, 7)
        self.assertFalse(config.allow_zero_length_lines)

    def test_validation_config_rejects_invalid_values(self):
        invalid_configs = (
            ({"max_geometry_vertices": 0}, ValueError),
            ({"max_geometry_vertices": True}, TypeError),
            ({"coordinate_precision": -1}, ValueError),
            ({"coordinate_precision": 1.5}, TypeError),
            ({"allow_zero_length_lines": "yes"}, TypeError),
        )
        for kwargs, expected_error in invalid_configs:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(expected_error):
                    ValidationConfig(**kwargs)

    def test_custom_vertex_limit_is_used_by_validator(self):
        line = LineString([(0, 0), (1, 0), (2, 0), (3, 0)])
        gdf = gpd.GeoDataFrame(
            {"_id": ["line-four"], "geometry": [line]},
            geometry="geometry",
        )
        validator = OSWValidation(
            zipfile_path="dummy.zip",
            config=ValidationConfig(max_geometry_vertices=3),
        )

        validator._validate_geometry_vertex_limit(gdf, "lines", max_errors=20)

        self.assertEqual(len(validator.errors), 1)
        self.assertIn("Maximum allowed is 3", validator.errors[0])

    def test_custom_coordinate_precision_is_used_by_validator(self):
        validator = OSWValidation(
            zipfile_path="dummy.zip",
            config=ValidationConfig(coordinate_precision=5),
        )
        with patch(
            "src.python_osw_validation._geojson_file_has_excess_coordinate_precision",
            return_value=True,
        ) as checker:
            validator._check_coordinate_precision(["nodes.geojson"])

        checker.assert_called_once_with("nodes.geojson", 5)
        self.assertEqual(
            validator.warnings,
            "Input dataset contains coordinates with more than 5 decimal places.",
        )

    def test_validator_rejects_non_config_object(self):
        with self.assertRaisesRegex(TypeError, "ValidationConfig"):
            OSWValidation(zipfile_path="dummy.zip", config={})

    def test_precision_checker_is_injectable(self):
        checked = []

        def checker(path):
            checked.append(path)
            return path.endswith("warning.geojson")

        self.assertTrue(has_excess_coordinate_precision(["ok.geojson", "warning.geojson"], checker))
        self.assertEqual(checked, ["ok.geojson", "warning.geojson"])

    def test_schema_helpers_are_reusable(self):
        self.assertEqual(
            schema_key_from_text("city.edges.OSW.geojson", ["nodes", "edges"]),
            "edges",
        )
        self.assertEqual(
            collect_nullish_extension_property_paths({"ext:value": None, "name": None}),
            [("ext:value", None)],
        )
        self.assertEqual(
            schema_error_code("AdditionalProperties"),
            "SCHEMA_ADDITIONAL_PROPERTIES",
        )
        self.assertEqual(schema_error_code(""), "SCHEMA_VALIDATION")

    def test_schema_prevalidation_returns_structured_null_issue(self):
        data = {
            "features": [{
                "properties": {"ext:value": None},
            }],
        }

        outcome = prevalidate_geojson(data, "points.geojson", "points", max_errors=20)

        self.assertFalse(outcome.continue_validation)
        self.assertEqual(outcome.issues[0]["filename"], "points.geojson")
        self.assertEqual(outcome.issues[0]["feature_index"], 0)
        self.assertIn("Null/NaN placeholders", outcome.errors[0])

    def test_schema_validation_streams_backward_compatible_errors(self):
        schema = {
            "type": "object",
            "required": ["type"],
            "properties": {"type": {"const": "FeatureCollection"}},
        }

        outcome = validate_against_schema({}, "nodes.geojson", schema, max_errors=20)

        self.assertTrue(outcome.continue_validation)
        self.assertEqual(len(outcome.errors), 1)
        self.assertTrue(outcome.errors[0].startswith("Validation error:"))
        self.assertEqual(outcome.issues[0]["filename"], "nodes.geojson")

    def test_additional_properties_schema_error_uses_snake_case_code(self):
        schema = {
            "type": "object",
            "properties": {"type": {"const": "FeatureCollection"}},
            "additionalProperties": False,
        }

        outcome = validate_against_schema(
            {"type": "FeatureCollection", "unexpected": True},
            "nodes.geojson",
            schema,
            max_errors=20,
        )

        self.assertEqual(
            outcome.issues[0]["code"],
            "SCHEMA_ADDITIONAL_PROPERTIES",
        )

    def test_validation_finding_is_immutable(self):
        finding = ValidationFinding("message", "edges", 1)
        with self.assertRaises(AttributeError):
            finding.message = "changed"

    def test_validation_result_adds_structured_metadata_and_summary(self):
        result = ValidationResult(
            False,
            ["bad geometry"],
            [{
                "filename": "edges",
                "feature_index": 4,
                "error_message": "bad geometry",
                "code": "INVALID_GEOMETRY",
                "severity": "error",
            }],
            "coordinate warning",
        )

        self.assertNotIn("code", result.issues[0])
        self.assertEqual(result.error_details[0]["code"], "VALIDATION_ERROR")
        self.assertEqual(result.issue_details[0]["code"], "INVALID_GEOMETRY")
        self.assertEqual(result.warning_details[0]["code"], "COORDINATE_PRECISION")
        self.assertEqual(result.summary["error_count"], 1)
        self.assertEqual(result.summary["warning_count"], 1)
        self.assertEqual(result.summary["by_file"], {"edges": 1})
        self.assertEqual(result.summary["by_severity"], {"error": 1, "warning": 1})
        self.assertEqual(
            result.summary["by_code"],
            {"INVALID_GEOMETRY": 1, "COORDINATE_PRECISION": 1},
        )

    def test_validation_result_preserves_legacy_issue_shape_additively(self):
        result = ValidationResult(
            False,
            ["legacy"],
            [{"filename": "All", "feature_index": None, "error_message": "legacy"}],
        )

        self.assertEqual(result.issues[0]["error_message"], "legacy")
        self.assertNotIn("code", result.issues[0])
        self.assertEqual(result.issue_details[0]["code"], "VALIDATION_ERROR")
        self.assertEqual(result.issue_details[0]["severity"], "error")


if __name__ == "__main__":
    unittest.main()
