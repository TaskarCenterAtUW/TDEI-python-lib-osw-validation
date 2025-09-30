import json
import os
import tempfile
import unittest
import zipfile

from src.python_osw_validation import OSWValidation

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
MINIMAL_ZIP = os.path.join(ASSETS_DIR, "minimal.zip")
UW_ZONES_VALID_ZIP = os.path.join(ASSETS_DIR, "UW.zones.valid.zip")


class TestSchemaRequirementDuringValidation(unittest.TestCase):
    """Ensure that GeoJSON files without $schema fail validation."""

    def _validate_missing_schema(self, source_zip: str, relative_paths):
        with tempfile.TemporaryDirectory() as tmpdir:
            extracted_dir = os.path.join(tmpdir, "extracted")
            os.makedirs(extracted_dir, exist_ok=True)

            with zipfile.ZipFile(source_zip) as src_zip:
                src_zip.extractall(extracted_dir)

            for rel_path in relative_paths:
                geojson_path = os.path.join(extracted_dir, rel_path)
                with open(geojson_path, encoding="utf-8") as geojson_file:
                    data = json.load(geojson_file)
                data.pop("$schema", None)
                with open(geojson_path, "w", encoding="utf-8") as geojson_file:
                    json.dump(data, geojson_file)

            modified_zip = os.path.join(tmpdir, "modified.zip")
            with zipfile.ZipFile(modified_zip, "w", zipfile.ZIP_DEFLATED) as dst_zip:
                for root, _, files in os.walk(extracted_dir):
                    for filename in files:
                        file_path = os.path.join(root, filename)
                        arcname = os.path.relpath(file_path, extracted_dir)
                        dst_zip.write(file_path, arcname)

            validation = OSWValidation(zipfile_path=modified_zip)
            return validation.validate(max_errors=5)

    def _assert_missing_schema_failure(self, result):
        self.assertFalse(result.is_valid)
        self.assertIsNotNone(result.errors)
        self.assertTrue(
            any("\"$schema\" is a required property" in error for error in result.errors),
            f"Expected missing $schema error, got: {result.errors}",
        )
        self.assertIsNotNone(result.issues)
        self.assertTrue(
            any(
                "\"$schema\" is a required property" in message
                for issue in result.issues
                for message in (
                    issue.get("error_message")
                    if isinstance(issue.get("error_message"), list)
                    else [issue.get("error_message")]
                )
                if message
            ),
            f"Expected missing $schema issue, got: {result.issues}",
        )

    def test_point_geojson_requires_schema(self):
        result = self._validate_missing_schema(
            MINIMAL_ZIP,
            ["minimal/wa.microsoft.graph.nodes.OSW.geojson"],
        )
        self._assert_missing_schema_failure(result)

    def test_linestring_geojson_requires_schema(self):
        result = self._validate_missing_schema(
            MINIMAL_ZIP,
            ["minimal/wa.microsoft.graph.edges.OSW.geojson"],
        )
        self._assert_missing_schema_failure(result)

    def test_polygon_geojson_requires_schema(self):
        result = self._validate_missing_schema(
            UW_ZONES_VALID_ZIP,
            ["UW.zones.valid/UW.zones.geojson"],
        )
        self._assert_missing_schema_failure(result)