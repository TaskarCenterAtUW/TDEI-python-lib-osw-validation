import unittest
from unittest.mock import patch

import geopandas as gpd
from shapely.geometry import LineString, Polygon

from src.python_osw_validation import OSWValidation, ValidationConfig


class TestValidationConfig(unittest.TestCase):
    @staticmethod
    def _gdf(geometry, feature_id="feature-1"):
        return gpd.GeoDataFrame(
            {"_id": [feature_id], "geometry": [geometry]},
            geometry="geometry",
            crs="EPSG:4326",
        )

    def test_defaults_match_public_configuration_contract(self):
        config = ValidationConfig()

        self.assertEqual(config.max_geometry_vertices, 2000)
        self.assertEqual(config.coordinate_precision, 7)
        self.assertFalse(config.allow_zero_length_lines)

    def test_invalid_configuration_values_are_rejected(self):
        cases = (
            ({"max_geometry_vertices": 0}, ValueError),
            ({"max_geometry_vertices": True}, TypeError),
            ({"coordinate_precision": -1}, ValueError),
            ({"coordinate_precision": 1.5}, TypeError),
            ({"allow_zero_length_lines": "yes"}, TypeError),
        )
        for kwargs, expected_error in cases:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(expected_error):
                    ValidationConfig(**kwargs)

    def test_custom_max_geometry_vertices_is_enforced(self):
        validator = OSWValidation(
            zipfile_path="dummy.zip",
            config=ValidationConfig(max_geometry_vertices=3),
        )
        line = LineString([(0, 0), (1, 0), (2, 0), (3, 0)])

        validator._validate_geometry_vertex_limit(
            self._gdf(line, "line-four"),
            "lines",
            max_errors=20,
        )

        self.assertEqual(len(validator.errors), 1)
        self.assertIn("Maximum allowed is 3", validator.errors[0])

    def test_custom_coordinate_precision_is_forwarded_to_checker(self):
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

    def test_zero_length_line_is_rejected_by_default_and_can_be_allowed(self):
        line = self._gdf(LineString([(1, 1), (1, 1)]), "line-zero")
        default_validator = OSWValidation(zipfile_path="dummy.zip")
        permissive_validator = OSWValidation(
            zipfile_path="dummy.zip",
            config=ValidationConfig(allow_zero_length_lines=True),
        )

        default_indexes = default_validator._validate_collapsed_geometries(
            line,
            "lines",
            max_errors=20,
        )
        permissive_indexes = permissive_validator._validate_collapsed_geometries(
            line,
            "lines",
            max_errors=20,
        )

        self.assertEqual(default_indexes, {0})
        self.assertEqual(len(default_validator.errors), 1)
        self.assertIn("zero-length geometry", default_validator.errors[0])
        self.assertEqual(permissive_indexes, {0})
        self.assertEqual(permissive_validator.errors, [])

    def test_zero_area_polygon_remains_invalid(self):
        polygon = self._gdf(
            Polygon([(1, 1), (1, 1), (1, 1), (1, 1)]),
            "polygon-zero",
        )
        validator = OSWValidation(zipfile_path="dummy.zip")

        indexes = validator._validate_collapsed_geometries(
            polygon,
            "polygons",
            max_errors=20,
        )

        self.assertEqual(indexes, {0})
        self.assertEqual(len(validator.errors), 1)
        self.assertIn("zero-area geometry", validator.errors[0])

    def test_validator_rejects_non_config_object(self):
        with self.assertRaisesRegex(TypeError, "ValidationConfig"):
            OSWValidation(zipfile_path="dummy.zip", config={})


if __name__ == "__main__":
    unittest.main()
