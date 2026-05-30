import json
import os
import tempfile
import unittest
import math
from unittest.mock import patch, MagicMock
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString, Polygon

import src.python_osw_validation as osw_mod
from src.python_osw_validation import OSWValidation

# Build a robust patch prefix from the module actually imported
_PATCH_PREFIX = osw_mod.__name__
_PATCH_UNIQUE = f"{_PATCH_PREFIX}.OSWValidation.are_ids_unique"
_PATCH_ZIP = f"{_PATCH_PREFIX}.ZipFileHandler"
_PATCH_EV = f"{_PATCH_PREFIX}.ExtractedDataValidator"
_PATCH_READ_FILE = f"{_PATCH_PREFIX}._read_geojson_without_ext"
_PATCH_VALIDATE = f"{_PATCH_PREFIX}.OSWValidation.validate_osw_errors"
_PATCH_DATASET_FILES = f"{_PATCH_PREFIX}.OSW_DATASET_FILES"

# A tiny canonical mapping that matches our mocked basenames
_CANON_DATASET_FILES = {
    "nodes": {"geometry": "Point"},
    "edges": {"geometry": "LineString"},
    "zones": {"geometry": "Polygon"},
}


class TestOSWValidationExtras(unittest.TestCase):
    """Additional tests covering edge-cases introduced by the new validator."""

    # ---------- helpers to build small GeoDataFrames ----------
    def _gdf_nodes(self, ids):
        return gpd.GeoDataFrame(
            {"_id": ids, "geometry": [Point(0, i) for i in range(len(ids))]},
            geometry="geometry",
            crs="EPSG:4326",
        )

    def _gdf_edges(self, u_ids=None, v_ids=None, n=1, ids=None):
        """Edges with a default _id column to avoid KeyError in duplicated('_id')."""
        if ids is None:
            ids = list(range(1, n + 1))
        data = {
            "_id": ids,
            "geometry": [LineString([(0, 0), (1, 1)]) for _ in range(n)],
        }
        if u_ids is not None:
            data["_u_id"] = u_ids
        if v_ids is not None:
            data["_v_id"] = v_ids
        return gpd.GeoDataFrame(data, geometry="geometry", crs="EPSG:4326")

    def _gdf_zones(self, w_ids_lists, n=None, ids=None):
        """Zones with a default _id column to avoid KeyError in duplicated('_id')."""
        if n is None:
            n = len(w_ids_lists)
        if ids is None:
            ids = list(range(1, n + 1))
        polys = [Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]) for _ in range(n)]
        return gpd.GeoDataFrame({"_id": ids, "_w_id": w_ids_lists, "geometry": polys},
                                geometry="geometry", crs="EPSG:4326")

    # ---------- shared fakes for Zip + ExtractedDataValidator ----------
    def _fake_validator(self, files, external_exts=None, valid=True, error="folder invalid"):
        val = MagicMock()
        val.files = files
        val.externalExtensions = external_exts or []
        val.is_valid.return_value = valid
        val.error = error
        return val

    # ---------------- tests ----------------

    def test_structure_error_uses_uploaded_filename(self):
        """Validator errors should reference the uploaded ZIP, not the temp extraction dir."""
        with patch(_PATCH_ZIP) as PZip, patch(_PATCH_EV) as PVal:
            z = MagicMock()
            z.extract_zip.return_value = "/tmp/tmp123"
            z.remove_extracted_files.return_value = None
            PZip.return_value = z

            PVal.return_value = self._fake_validator(files=[], valid=False, error="bad structure")

            upload_path = "/uploads/user_dataset.zip"
            res = OSWValidation(zipfile_path=upload_path).validate()

        self.assertFalse(res.is_valid)
        issue = res.issues[0]
        self.assertEqual(issue["filename"], os.path.basename(upload_path))
        self.assertIn("bad structure", issue["error_message"])

    def test_nullish_values_fail_before_schema_validation(self):
        validator = OSWValidation(zipfile_path="dummy.zip")
        geojson_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "step_count": None,
                        "width": math.nan,
                        "string_null": "null",
                        "string_nan": "nan",
                        "string_nan_mixed_case": " NaN ",
                        "ext:missing": None,
                        "ext:metadata": {
                            "score": math.nan,
                        },
                    },
                    "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
                }
            ],
        }

        with patch.object(validator, "load_osw_file", return_value=geojson_data), \
             patch.object(validator, "pick_schema_for_file") as pick_schema_mock:
            ok = validator.validate_osw_errors("/tmp/FIFA_sidewalks.edges.geojson", max_errors=20)

        self.assertFalse(ok)
        pick_schema_mock.assert_not_called()
        self.assertEqual(len(validator.issues), 2)
        self.assertEqual(
            validator.issues[0]["error_message"],
            ["Invalid value at 'ext:missing': None. Null/NaN placeholders are not allowed; provide a valid value or remove this property."],
        )
        self.assertEqual(
            validator.issues[1]["error_message"],
            ["Invalid value at 'ext:metadata.score': nan. Null/NaN placeholders are not allowed; provide a valid value or remove this property."],
        )

    def test_non_extension_nullish_values_are_not_upfront_nullish_values(self):
        validator = OSWValidation(zipfile_path="dummy.zip")

        self.assertEqual(
            validator._collect_nullish_extension_property_paths({
                "step_count": None,
                "width": math.nan,
                "string_null": "null",
                "string_nan": "nan",
                "string_nan_mixed_case": " NaN ",
                "nested": [None, math.nan],
                "ext:string_null": "null",
                "ext:string_nan": "nan",
                "ext:string_nan_mixed_case": " NaN ",
                "ext:nested_strings": ["null", "nan"],
            }),
            [],
        )

    def test_missing_u_id_reports_error_without_keyerror(self):
        """Edges missing `_u_id` should report a friendly error instead of raising KeyError."""
        fake_files = ["/tmp/nodes.geojson", "/tmp/edges.geojson"]
        nodes = self._gdf_nodes([1, 2])
        # edges WITHOUT _u_id; include _id to bypass duplicated('_id') KeyError
        edges = self._gdf_edges(u_ids=None, v_ids=[1, 2], n=2, ids=[101, 102])

        with patch(_PATCH_ZIP) as PZip, \
             patch(_PATCH_EV) as PVal, \
             patch(_PATCH_VALIDATE, return_value=True), \
             patch(_PATCH_READ_FILE) as PRead, \
             patch(_PATCH_DATASET_FILES, _CANON_DATASET_FILES):

            z = MagicMock()
            z.extract_zip.return_value = "/tmp/extracted"
            z.remove_extracted_files.return_value = None
            z.error = "extraction failed"
            PZip.return_value = z

            PVal.return_value = self._fake_validator(fake_files)

            def _rf(path):
                b = os.path.basename(path)
                if "nodes" in b:
                    return nodes
                if "edges" in b:
                    return edges
                return gpd.GeoDataFrame()
            PRead.side_effect = _rf

            res = OSWValidation(zipfile_path="dummy.zip").validate()
            self.assertFalse(res.is_valid, f"Expected invalid; errors={res.errors}")
            self.assertTrue(any("_u_id" in e and "Missing required column" in e for e in (res.errors or [])),
                            f"Errors were: {res.errors}")

    def test_unmatched_u_id_is_limited_to_20(self):
        """When there are many unmatched _u_id values, only 20 are listed."""
        fake_files = ["/tmp/nodes.geojson", "/tmp/edges.geojson"]
        nodes = self._gdf_nodes([1, 2])
        # edges have 25 u_ids (23 unmatched vs nodes {1,2}); include _id to bypass KeyError
        edges = self._gdf_edges(u_ids=list(range(1, 26)), v_ids=list(range(1, 26)), n=25, ids=list(range(100, 125)))

        with patch(_PATCH_ZIP) as PZip, \
             patch(_PATCH_EV) as PVal, \
             patch(_PATCH_VALIDATE, return_value=True), \
             patch(_PATCH_READ_FILE) as PRead, \
             patch(_PATCH_DATASET_FILES, _CANON_DATASET_FILES):

            z = MagicMock()
            z.extract_zip.return_value = "/tmp/extracted"
            z.remove_extracted_files.return_value = None
            PZip.return_value = z
            PVal.return_value = self._fake_validator(fake_files)

            def _rf(path):
                b = os.path.basename(path)
                return nodes if "nodes" in b else edges
            PRead.side_effect = _rf

            res = OSWValidation(zipfile_path="dummy.zip").validate()
            self.assertFalse(res.is_valid, f"Expected invalid; errors={res.errors}")
            msg = next((e for e in (res.errors or []) if "_u_id" in e and "unmatched" in e), None)
            self.assertIsNotNone(msg, f"Expected unmatched _u_id error not found. Errors: {res.errors}")
            self.assertIn("Showing 20 out of", msg)
            displayed = msg.split(":")[-1].strip()
            if displayed:
                shown_ids = [x.strip() for x in displayed.split(",")]
                self.assertLessEqual(len(shown_ids), 20)

    def test_unmatched_w_id_is_limited_to_20(self):
        fake_files = ["/tmp/nodes.geojson", "/tmp/zones.geojson"]
        nodes = self._gdf_nodes([1, 2, 3])
        # zones have many _w_id that do not exist in nodes; include _id to bypass KeyError
        w_lists = [[i, i + 100] for i in range(1, 26)]  # each row has 2 ids (50 candidates)
        zones = self._gdf_zones(w_lists, ids=list(range(1000, 1000 + len(w_lists))))

        with patch(_PATCH_ZIP) as PZip, \
             patch(_PATCH_EV) as PVal, \
             patch(_PATCH_VALIDATE, return_value=True), \
             patch(_PATCH_READ_FILE) as PRead, \
             patch(_PATCH_DATASET_FILES, _CANON_DATASET_FILES):

            z = MagicMock()
            z.extract_zip.return_value = "/tmp/extracted"
            PZip.return_value = z
            PVal.return_value = self._fake_validator(fake_files)

            def _rf(path):
                b = os.path.basename(path)
                return nodes if "nodes" in b else zones
            PRead.side_effect = _rf

            res = OSWValidation(zipfile_path="dummy.zip").validate()
            self.assertFalse(res.is_valid, f"Expected invalid; errors={res.errors}")
            msg = next((e for e in (res.errors or []) if "_w_id" in e and "unmatched" in e), None)
            self.assertIsNotNone(msg, f"Expected unmatched _w_id error not found. Errors: {res.errors}")
            self.assertIn("Showing 20 out of", msg)
            displayed = msg.split(":")[-1].strip()
            if displayed:
                shown_ids = [x.strip() for x in displayed.split(",")]
                self.assertLessEqual(len(shown_ids), 20)

    def test_load_osw_file_reports_json_decode_error(self):
        """Invalid JSON should surface a detailed message with location context."""
        validator = OSWValidation(zipfile_path="dummy.zip")
        with tempfile.NamedTemporaryFile("w", suffix=".geojson", delete=False) as tmp:
            tmp.write('{"features": [1, }')
            bad_path = tmp.name
        try:
            with self.assertRaises(json.JSONDecodeError):
                validator.load_osw_file(bad_path)
        finally:
            os.unlink(bad_path)

        self.assertTrue(any("Failed to parse" in e for e in (validator.errors or [])),
                        f"Errors were: {validator.errors}")
        message = validator.errors[-1]
        basename = os.path.basename(bad_path)
        self.assertIn(basename, message)
        self.assertIn("line", message)
        self.assertIn("column", message)

        issue = validator.issues[-1]
        self.assertEqual(issue["filename"], basename)
        self.assertIsNone(issue["feature_index"])
        self.assertEqual(issue["error_message"], message)

    def test_load_osw_file_reports_os_error(self):
        """Missing files should log a readable OS error message."""
        validator = OSWValidation(zipfile_path="dummy.zip")
        missing_path = os.path.join(tempfile.gettempdir(), "nonexistent_osw_file.geojson")
        if os.path.exists(missing_path):
            os.unlink(missing_path)

        with self.assertRaises(OSError):
            validator.load_osw_file(missing_path)

        self.assertTrue(any("Unable to read file" in e for e in (validator.errors or [])),
                        f"Errors were: {validator.errors}")
        message = validator.errors[-1]
        basename = os.path.basename(missing_path)
        self.assertIn(basename, message)
        self.assertIn("Unable to read file", message)

        issue = validator.issues[-1]
        self.assertEqual(issue["filename"], basename)
        self.assertIsNone(issue["feature_index"])
        self.assertEqual(issue["error_message"], message)

    def test_validate_reports_json_decode_error(self):
        """Full validation flow should surface parse errors before schema checks."""
        with tempfile.NamedTemporaryFile("w", suffix=".geojson", delete=False) as tmp:
            tmp.write('{"type": "FeatureCollection", "features": [1, }')
            bad_path = tmp.name

        try:
            with patch(_PATCH_ZIP) as PZip, patch(_PATCH_EV) as PVal:
                z = MagicMock()
                z.extract_zip.return_value = "/tmp/extracted"
                z.remove_extracted_files.return_value = None
                PZip.return_value = z

                PVal.return_value = self._fake_validator([bad_path])

                result = OSWValidation(zipfile_path="dummy.zip").validate()

            self.assertFalse(result.is_valid)
            message = next((e for e in (result.errors or []) if "Failed to parse" in e), None)
            self.assertIsNotNone(message, f"Expected parse error message. Errors: {result.errors}")
            basename = os.path.basename(bad_path)
            self.assertIn(basename, message)
            self.assertIn("line", message)

            issue = next((i for i in (result.issues or []) if i["filename"] == basename), None)
            self.assertIsNotNone(issue, f"Issues were: {result.issues}")
            self.assertEqual(issue["error_message"], message)
        finally:
            os.unlink(bad_path)

    def test_validate_reports_read_file_exception(self):
        """GeoDataFrame read failures are logged and do not crash."""
        fake_files = ["/tmp/edges.geojson"]

        with patch(_PATCH_ZIP) as PZip, \
             patch(_PATCH_EV) as PVal, \
             patch(_PATCH_VALIDATE, return_value=True), \
             patch(_PATCH_READ_FILE, side_effect=Exception("boom")), \
             patch(_PATCH_DATASET_FILES, _CANON_DATASET_FILES):

            z = MagicMock()
            z.extract_zip.return_value = "/tmp/extracted"
            z.remove_extracted_files.return_value = None
            PZip.return_value = z
            PVal.return_value = self._fake_validator(fake_files)

            res = OSWValidation(zipfile_path="dummy.zip").validate()

        self.assertFalse(res.is_valid)
        self.assertTrue(any("Failed to read 'edges.geojson' as GeoJSON: boom" in e for e in (res.errors or [])),
                        f"Errors were: {res.errors}")

    def test_missing_w_id_reports_error(self):
        """Zones missing _w_id should report a clear message."""
        fake_files = ["/tmp/nodes.geojson", "/tmp/zones.geojson"]
        nodes = self._gdf_nodes([1, 2])
        # zones without _w_id column
        polygons = [Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])]
        zones = gpd.GeoDataFrame({"_id": [10]}, geometry=polygons, crs="EPSG:4326")

        with patch(_PATCH_ZIP) as PZip, \
             patch(_PATCH_EV) as PVal, \
             patch(_PATCH_VALIDATE, return_value=True), \
             patch(_PATCH_READ_FILE) as PRead, \
             patch(_PATCH_DATASET_FILES, _CANON_DATASET_FILES):

            z = MagicMock()
            z.extract_zip.return_value = "/tmp/extracted"
            z.remove_extracted_files.return_value = None
            PZip.return_value = z
            PVal.return_value = self._fake_validator(fake_files)

            def _rf(path):
                b = os.path.basename(path)
                if "nodes" in b:
                    return nodes
                if "zones" in b:
                    return zones
                return gpd.GeoDataFrame()

            PRead.side_effect = _rf

            res = OSWValidation(zipfile_path="dummy.zip").validate()

        self.assertFalse(res.is_valid)
        self.assertTrue(any("Missing required column '_w_id' in zones." in e for e in (res.errors or [])),
                        f"Errors were: {res.errors}")

    def test_extension_read_failure_reports_error(self):
        """Failure reading an extension file should be reported and skipped."""
        fake_files = ["/tmp/nodes.geojson"]
        nodes = self._gdf_nodes([1])
        ext_path = "/tmp/custom.geojson"

        with patch(_PATCH_ZIP) as PZip, \
             patch(_PATCH_EV) as PVal, \
             patch(_PATCH_VALIDATE, return_value=True), \
             patch(_PATCH_READ_FILE) as PRead, \
             patch(_PATCH_DATASET_FILES, _CANON_DATASET_FILES):

            z = MagicMock()
            z.extract_zip.return_value = "/tmp/extracted"
            z.remove_extracted_files.return_value = None
            PZip.return_value = z

            val = self._fake_validator(fake_files, external_exts=[ext_path])
            PVal.return_value = val

            def _rf(path):
                b = os.path.basename(path)
                if "nodes" in b:
                    return nodes
                if os.path.basename(path) == os.path.basename(ext_path):
                    raise Exception("boom")
                return gpd.GeoDataFrame()

            PRead.side_effect = _rf

            res = OSWValidation(zipfile_path="dummy.zip").validate()

        self.assertFalse(res.is_valid)
        self.assertTrue(any("Failed to read extension 'custom.geojson' as GeoJSON: boom" in e for e in (res.errors or [])),
                        f"Errors were: {res.errors}")

    def test_extension_invalid_ids_reports_extraction_failure(self):
        """If invalid extension features exist but id extraction fails, we report gracefully."""
        ext_path = "/tmp/custom.geojson"
        fake_files = ["/tmp/nodes.geojson"]
        nodes = self._gdf_nodes([1])

        invalid_geojson = MagicMock()
        invalid_geojson.__len__.return_value = 1
        invalid_geojson.get.side_effect = Exception("explode")

        extension_file = MagicMock()
        extension_file.__getitem__.return_value = invalid_geojson  # handles extensionFile[extensionFile.is_valid == False]
        extension_file.is_valid = [False]
        extension_file.drop.return_value = pd.DataFrame()

        with patch(_PATCH_ZIP) as PZip, \
             patch(_PATCH_EV) as PVal, \
             patch(_PATCH_VALIDATE, return_value=True), \
             patch(_PATCH_READ_FILE) as PRead, \
             patch(_PATCH_DATASET_FILES, _CANON_DATASET_FILES):

            z = MagicMock()
            z.extract_zip.return_value = "/tmp/extracted"
            z.remove_extracted_files.return_value = None
            PZip.return_value = z

            val = self._fake_validator(fake_files, external_exts=[ext_path])
            PVal.return_value = val

            def _rf(path):
                b = os.path.basename(path)
                if "nodes" in b:
                    return nodes
                if os.path.basename(path) == os.path.basename(ext_path):
                    return extension_file
                return gpd.GeoDataFrame()

            PRead.side_effect = _rf

            res = OSWValidation(zipfile_path="dummy.zip").validate()

        self.assertFalse(res.is_valid)
        self.assertTrue(any("Invalid features found in `custom.geojson`, but failed to extract IDs: explode" in e
                            for e in (res.errors or [])),
                        f"Errors were: {res.errors}")

    def test_extension_invalid_geometries_reported(self):
        """Invalid geometries inside an extension file should surface a clear error."""
        ext_path = "/tmp/custom.geojson"
        fake_files = ["/tmp/nodes.geojson"]
        nodes = self._gdf_nodes([1])

        invalid_geojson = MagicMock()
        invalid_geojson.__len__.return_value = 2
        invalid_geojson.get.return_value = ["a", "b"]

        extension_file = MagicMock()
        extension_file.is_valid = [False, False]
        extension_file.__getitem__.return_value = invalid_geojson
        extension_file.drop.return_value = pd.DataFrame()

        with patch(_PATCH_ZIP) as PZip, \
             patch(_PATCH_EV) as PVal, \
             patch(_PATCH_VALIDATE, return_value=True), \
             patch(_PATCH_READ_FILE) as PRead, \
             patch(_PATCH_DATASET_FILES, _CANON_DATASET_FILES):

            z = MagicMock()
            z.extract_zip.return_value = "/tmp/extracted"
            z.remove_extracted_files.return_value = None
            PZip.return_value = z

            val = self._fake_validator(fake_files, external_exts=[ext_path])
            PVal.return_value = val

            def _rf(path):
                b = os.path.basename(path)
                if "nodes" in b:
                    return nodes
                if os.path.basename(path) == os.path.basename(ext_path):
                    return extension_file
                return gpd.GeoDataFrame()

            PRead.side_effect = _rf

            res = OSWValidation(zipfile_path="dummy.zip").validate()

        self.assertFalse(res.is_valid)
        self.assertTrue(any("Invalid geometries found in extension file `custom.geojson`" in e
                            for e in (res.errors or [])),
                        f"Errors were: {res.errors}")

    def test_extension_serialization_failure_reported(self):
        """Non-serializable extension properties should be reported."""
        ext_path = "/tmp/custom.geojson"
        fake_files = ["/tmp/nodes.geojson"]
        nodes = self._gdf_nodes([1])

        extension_file = MagicMock()
        extension_file.is_valid = [True]
        extension_file.__getitem__.return_value = gpd.GeoDataFrame()  # no invalid geometries
        extension_file.drop.side_effect = Exception("serialize boom")

        with patch(_PATCH_ZIP) as PZip, \
             patch(_PATCH_EV) as PVal, \
             patch(_PATCH_VALIDATE, return_value=True), \
             patch(_PATCH_READ_FILE) as PRead, \
             patch(_PATCH_DATASET_FILES, _CANON_DATASET_FILES):

            z = MagicMock()
            z.extract_zip.return_value = "/tmp/extracted"
            z.remove_extracted_files.return_value = None
            PZip.return_value = z

            val = self._fake_validator(fake_files, external_exts=[ext_path])
            PVal.return_value = val

            def _rf(path):
                b = os.path.basename(path)
                if "nodes" in b:
                    return nodes
                if os.path.basename(path) == os.path.basename(ext_path):
                    return extension_file
                return gpd.GeoDataFrame()

            PRead.side_effect = _rf

            res = OSWValidation(zipfile_path="dummy.zip").validate()

        self.assertFalse(res.is_valid)
        self.assertTrue(any("Extension file `custom.geojson` has non-serializable properties: serialize boom" in e
                            for e in (res.errors or [])),
                        f"Errors were: {res.errors}")

    def test_duplicate_ids_detection(self):
        """Duplicates inside a single file are reported."""
        fake_files = ["/tmp/nodes.geojson"]
        nodes = self._gdf_nodes([1, 2, 2, 3])  # duplicate "2"

        with patch(_PATCH_ZIP) as PZip, \
             patch(_PATCH_EV) as PVal, \
             patch(_PATCH_VALIDATE, return_value=True), \
             patch(_PATCH_READ_FILE, return_value=nodes), \
             patch(_PATCH_DATASET_FILES, _CANON_DATASET_FILES):

            z = MagicMock()
            z.extract_zip.return_value = "/tmp/extracted"
            PZip.return_value = z
            PVal.return_value = self._fake_validator(fake_files)

            res = OSWValidation(zipfile_path="dummy.zip").validate()
            self.assertFalse(res.is_valid)
            msg = next((e for e in (res.errors or []) if "Duplicate _id's found in nodes" in e), None)
            self.assertEqual(msg, "Duplicate _id's found in nodes: 2")

    def test_duplicate_ids_detection_is_limited_to_20(self):
        """Duplicate messages cap the number of displayed IDs."""
        fake_files = ["/tmp/nodes.geojson"]
        duplicate_ids = [f"id{i}" for i in range(25) for _ in (0, 1)]  # 25 unique duplicates
        nodes = self._gdf_nodes(duplicate_ids)

        with patch(_PATCH_ZIP) as PZip, \
                patch(_PATCH_EV) as PVal, \
                patch(_PATCH_VALIDATE, return_value=True), \
                patch(_PATCH_READ_FILE, return_value=nodes), \
                patch(_PATCH_DATASET_FILES, _CANON_DATASET_FILES):
            z = MagicMock()
            z.extract_zip.return_value = "/tmp/extracted"
            PZip.return_value = z
            PVal.return_value = self._fake_validator(fake_files)

            res = OSWValidation(zipfile_path="dummy.zip").validate()
            self.assertFalse(res.is_valid)
            msg = next((e for e in (res.errors or []) if "Duplicate _id's found in nodes" in e), None)
            self.assertIsNotNone(msg, "Expected duplicate-id error not found")
            self.assertIn("showing first 20 of 25 duplicates", msg)
            displayed = msg.split("duplicates:")[-1].strip()
            shown_ids = [part.strip() for part in displayed.split(",") if part.strip()]
            self.assertLessEqual(len(shown_ids), 20)
            expected_ids = [f"id{i}" for i in range(20)]
            self.assertEqual(shown_ids, expected_ids)

    def test_pick_schema_by_filename_only(self):
        """Filename drives selection; geometry-only inputs fall back to line schema."""
        v = OSWValidation(zipfile_path="dummy.zip")
        # filename mapping
        self.assertEqual(v.pick_schema_for_file("/tmp/my.nodes.geojson", {"features": []}), v.dataset_schema_paths["nodes"])
        self.assertEqual(v.pick_schema_for_file("/tmp/my.edges.geojson", {"features": []}), v.dataset_schema_paths["edges"])
        self.assertEqual(v.pick_schema_for_file("/tmp/my.points.geojson", {"features": []}), v.dataset_schema_paths["points"])
        self.assertEqual(v.pick_schema_for_file("/tmp/my.lines.geojson", {"features": []}), v.dataset_schema_paths["lines"])
        self.assertEqual(v.pick_schema_for_file("/tmp/my.polygons.geojson", {"features": []}), v.dataset_schema_paths["polygons"])
        self.assertEqual(v.pick_schema_for_file("/tmp/my.zones.geojson", {"features": []}), v.dataset_schema_paths["zones"])
        # geometry-only (no filename hint) falls back to line schema
        self.assertEqual(
            v.pick_schema_for_file("/tmp/unknown.geojson", {"features": [{"geometry": {"type": "Point"}}]}),
            v.line_schema_path,
        )

    def test_zip_extract_failure_bubbles_as_error(self):
        """If zip extraction fails, we get a clean error and False result."""
        with patch(_PATCH_ZIP) as PZip:
            z = MagicMock()
            z.extract_zip.return_value = None
            z.error = "Failed to extract zip"
            PZip.return_value = z

            res = OSWValidation(zipfile_path="bad.zip").validate()
            self.assertFalse(res.is_valid)
            self.assertTrue(any("Failed to extract zip" in e for e in (res.errors or [])))

    def test_extracted_data_validator_invalid(self):
        """If folder structure is invalid, its error is surfaced."""
        with patch(_PATCH_ZIP) as PZip, patch(_PATCH_EV) as PVal:
            z = MagicMock()
            z.extract_zip.return_value = "/tmp/extracted"
            PZip.return_value = z

            PVal.return_value = self._fake_validator(files=[], valid=False, error="bad structure")

            res = OSWValidation(zipfile_path="dummy.zip").validate()
            self.assertFalse(res.is_valid)
            self.assertTrue(any("bad structure" in e for e in (res.errors or [])))

    def test_issues_populated_for_invalid_zip(self):
        """Ensure `issues` contains per-feature messages when validation fails."""
        assets = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
        invalid_zip = os.path.join(assets, "invalid.zip")
        if os.path.exists(invalid_zip):
            res = OSWValidation(zipfile_path=invalid_zip).validate()
            self.assertFalse(res.is_valid)
            self.assertIsInstance(res.issues, list)
            self.assertGreater(len(res.issues), 0)
            ex = res.issues[0]
            self.assertIn("filename", ex)
            self.assertIn("feature_index", ex)
            self.assertIn("error_message", ex)
        else:
            # Mock a minimal run that forces one schema error → issues populated
            fake_files = ["/tmp/nodes.geojson"]
            nodes = self._gdf_nodes([1])

            with patch(_PATCH_ZIP) as PZip, \
                 patch(_PATCH_EV) as PVal, \
                 patch(_PATCH_VALIDATE) as PSchema, \
                 patch(_PATCH_READ_FILE, return_value=nodes), \
                 patch(_PATCH_DATASET_FILES, _CANON_DATASET_FILES):

                z = MagicMock()
                z.extract_zip.return_value = "/tmp/extracted"
                PZip.return_value = z
                PVal.return_value = self._fake_validator(fake_files)

                def _schema_side_effect(self_obj, *args, **kwargs):
                    # simulate legacy error and per-feature issue
                    self_obj.errors.append("Validation error: dummy schema error")
                    self_obj.issues.append({
                        "filename": "nodes.geojson",
                        "feature_index": 0,
                        "error_message": ["dummy message"],
                    })
                    return True

                PSchema.side_effect = _schema_side_effect

                res = OSWValidation(zipfile_path="dummy.zip").validate()
                self.assertFalse(res.is_valid)
                self.assertGreater(len(res.issues), 0)
                self.assertIn("dummy message", res.issues[0]["error_message"])

class TestOSWValidationInternals(unittest.TestCase):
    """Covers `_get_colset` and `pick_schema_for_file` internals."""

    # ---------- helpers ----------
    def _gdf(self, data, geom="Point"):
        if geom == "Point":
            g = [Point(0, i) for i in range(len(next(iter(data.values()))))]
        elif geom == "LineString":
            g = [LineString([(0, 0), (1, 1)]) for _ in range(len(next(iter(data.values()))))]
        else:
            g = [Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]) for _ in range(len(next(iter(data.values()))))]
        data = {**data, "geometry": g}
        return gpd.GeoDataFrame(data, geometry="geometry", crs="EPSG:4326")

    def _write_geojson(self, data):
        tmp = tempfile.NamedTemporaryFile("w", suffix=".geojson", delete=False)
        json.dump(data, tmp)
        tmp.close()
        return tmp.name

    # ---------- _get_colset ----------
    def test_get_colset_returns_set_when_column_present(self):
        v = OSWValidation(zipfile_path="dummy.zip")
        gdf = self._gdf({"_id": [1, 2, 2, None, 3]}, geom="Point")
        s = v._get_colset(gdf, "_id", "nodes")
        self.assertEqual(s, {1, 2, 3})

    def test_get_colset_reports_missing_column(self):
        v = OSWValidation(zipfile_path="dummy.zip")
        gdf = self._gdf({"foo": [1, 2]}, geom="Point")
        s = v._get_colset(gdf, "_id", "nodes")
        self.assertEqual(s, set())
        self.assertTrue(any("Missing required column '_id' in nodes." in e for e in v.errors))

    def test_get_colset_handles_unhashable_by_stringifying(self):
        v = OSWValidation(zipfile_path="dummy.zip")
        # dicts are unhashable; method should stringify
        gdf = self._gdf({"meta": [{"a": 1}, {"b": 2}, None]}, geom="Point")
        s = v._get_colset(gdf, "meta", "nodes")
        self.assertEqual(s, {str({"a": 1}), str({"b": 2})})
        # and should not log an error for existing column
        self.assertFalse(any("meta" in e and "Could not create set" in e for e in (v.errors or [])))

    def test_get_colset_with_none_gdf(self):
        v = OSWValidation(zipfile_path="dummy.zip")
        s = v._get_colset(None, "_id", "nodes")
        self.assertEqual(s, set())

    def test_get_colset_reports_stringify_failure(self):
        class BadObj:
            def __hash__(self):
                raise TypeError("no hash")

            def __str__(self):
                raise ValueError("no str")

        v = OSWValidation(zipfile_path="dummy.zip")
        gdf = self._gdf({"meta": [BadObj()]}, geom="Point")
        s = v._get_colset(gdf, "meta", "nodes")
        self.assertEqual(s, set())
        self.assertTrue(any("Could not create set for column 'meta' in nodes." in e for e in (v.errors or [])),
                        f"Errors were: {v.errors}")

    def test_load_osw_schema_reports_missing_file(self):
        v = OSWValidation(zipfile_path="dummy.zip")
        missing_schema = os.path.join(tempfile.gettempdir(), "missing_schema.json")
        if os.path.exists(missing_schema):
            os.unlink(missing_schema)
        with self.assertRaises(Exception):
            v.load_osw_schema(missing_schema)
        self.assertTrue(any("Invalid or missing schema file" in e for e in (v.errors or [])),
                        f"Errors were: {v.errors}")

    def test_schema_02_rejects_tree_and_custom(self):
        base = {
            "$schema": "https://sidewalks.washington.edu/opensidewalks/0.2/schema.json",
            "type": "FeatureCollection",
        }

        def _feature(props):
            return {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [0, 0]},
                "properties": props,
            }

        path_tree = self._write_geojson({**base, "features": [_feature({"natural": "tree"})]})
        v = OSWValidation(zipfile_path="dummy.zip")
        try:
            res = v.validate_osw_errors(path_tree, max_errors=5)
        finally:
            os.unlink(path_tree)
        self.assertFalse(res)
        self.assertTrue(any("0.2 schema does not support Tree coverage" in e for e in (v.errors or [])),
                        f"Errors were: {v.errors}")

        path_custom = self._write_geojson({**base, "features": [_feature({"type": "Custom Point"})]})
        v2 = OSWValidation(zipfile_path="dummy.zip")
        try:
            res2 = v2.validate_osw_errors(path_custom, max_errors=5)
        finally:
            os.unlink(path_custom)
        self.assertFalse(res2)
        self.assertTrue(any("0.2 schema does not support" in e for e in (v2.errors or [])),
                        f"Errors were: {v2.errors}")

        path_wood = self._write_geojson({**base, "features": [_feature({"natural": "wood", "leaf_cycle": "mixed"})]})
        v3 = OSWValidation(zipfile_path="dummy.zip")
        try:
            res3 = v3.validate_osw_errors(path_wood, max_errors=5)
        finally:
            os.unlink(path_wood)
        self.assertFalse(res3)
        self.assertTrue(any("0.2 schema does not support Tree coverage" in e for e in (v3.errors or [])),
                        f"Errors were: {v3.errors}")

    def test_schema_03_with_tree_tags_is_allowed(self):
        base = {
            "$schema": "https://sidewalks.washington.edu/opensidewalks/0.3/schema.json",
            "type": "FeatureCollection",
        }

        feat = {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
            "properties": {"natural": "wood", "leaf_cycle": "mixed", "_id": "p1"},
        }
        path = self._write_geojson({**base, "features": [feat]})

        class DummyValidator:
            def __init__(self, *_):
                pass

            def iter_errors(self, *_):
                return []

        v = OSWValidation(zipfile_path="dummy.zip")
        try:
            with patch("src.python_osw_validation.jsonschema_rs.Draft7Validator", DummyValidator), \
                 patch.object(OSWValidation, "_contains_disallowed_features_for_02", side_effect=Exception("should_not_call")):
                res = v.validate_osw_errors(path, max_errors=5)
        finally:
            os.unlink(path)

        self.assertTrue(res)
        self.assertFalse(v.errors)

    def test_cleanup_handles_locals_membership_error(self):
        """Finalizer should swallow errors when checking locals membership."""

        class BadPath:
            def __str__(self):
                return "/tmp/nodes.geojson"

            def __fspath__(self):
                return "/tmp/nodes.geojson"

            def __hash__(self):
                raise TypeError("boom")

        fake_files = [BadPath()]
        nodes = self._gdf({"_id": [1]}, geom="Point")

        class DummyValidator:
            def __init__(self, files):
                self.files = files
                self.externalExtensions = []
                self.error = "ok"

            def is_valid(self):
                return True

        with patch(_PATCH_ZIP) as PZip, \
             patch(_PATCH_EV) as PVal, \
             patch(_PATCH_VALIDATE, return_value=True), \
             patch(_PATCH_READ_FILE, return_value=nodes), \
             patch(_PATCH_DATASET_FILES, _CANON_DATASET_FILES):

            z = MagicMock()
            z.extract_zip.return_value = "/tmp/extracted"
            z.remove_extracted_files.return_value = None
            PZip.return_value = z

            PVal.return_value = DummyValidator(fake_files)

            res = OSWValidation(zipfile_path="dummy.zip").validate()

        self.assertTrue(res.is_valid)
        self.assertIsNone(res.errors)

    # ---------- pick_schema_for_file ----------
    def test_pick_schema_by_geometry(self):
        v = OSWValidation(zipfile_path="dummy.zip")
        self.assertEqual(
            v.pick_schema_for_file("/x/y.json", {"features": [{"geometry": {"type": "Point"}}]}),
            v.line_schema_path,
        )
        self.assertEqual(
            v.pick_schema_for_file("/x/y.json", {"features": [{"geometry": {"type": "LineString"}}]}),
            v.line_schema_path,
        )
        self.assertEqual(
            v.pick_schema_for_file("/x/y.json", {"features": [{"geometry": {"type": "Polygon"}}]}),
            v.line_schema_path,
        )

    def test_pick_schema_by_schema_url(self):
        v = OSWValidation(zipfile_path="dummy.zip")
        self.assertEqual(
            v.pick_schema_for_file("/x/nodes.json", {"$schema": "https://sidewalks.washington.edu/opensidewalks/0.3/nodes.schema.json"}),
            v.dataset_schema_paths["nodes"],
        )
        self.assertEqual(
            v.pick_schema_for_file("/x/general.json", {"$schema": "https://sidewalks.washington.edu/opensidewalks/0.3/schema.json"}),
            v.line_schema_path,
        )
        self.assertEqual(
            v.pick_schema_for_file("/x/general.json", {"$schema": "https://sidewalks.washington.edu/opensidewalks/0.2/schema.json"}),
            v.line_schema_path,
        )

    def test_pick_schema_filename_fallback(self):
        v = OSWValidation(zipfile_path="dummy.zip")
        self.assertEqual(v.pick_schema_for_file("/tmp/my.nodes.geojson", {"features": []}), v.dataset_schema_paths["nodes"])
        self.assertEqual(v.pick_schema_for_file("/tmp/my.points.geojson", {"features": []}), v.dataset_schema_paths["points"])
        self.assertEqual(v.pick_schema_for_file("/tmp/my.edges.geojson", {"features": []}), v.dataset_schema_paths["edges"])
        self.assertEqual(v.pick_schema_for_file("/tmp/my.lines.geojson", {"features": []}), v.dataset_schema_paths["lines"])
        self.assertEqual(v.pick_schema_for_file("/tmp/my.zones.geojson", {"features": []}), v.dataset_schema_paths["zones"])
        self.assertEqual(v.pick_schema_for_file("/tmp/my.polygons.geojson", {"features": []}), v.dataset_schema_paths["polygons"])
        self.assertEqual(
            v.pick_schema_for_file("/tmp/geometry_only.geojson", {"features": [{"geometry": {"type": "Point"}}]}),
            v.line_schema_path,
        )

    def test_pick_schema_ignores_prefix_substrings(self):
        v = OSWValidation(zipfile_path="dummy.zip")
        self.assertEqual(
            v.pick_schema_for_file("/tmp/gs_metaline_falls_uga.nodes.geojson", {"features": []}),
            v.dataset_schema_paths["nodes"],
        )
        self.assertEqual(
            v.pick_schema_for_file("/tmp/gs_yarrow_point.edges.geojson", {"features": []}),
            v.dataset_schema_paths["edges"],
        )
        self.assertEqual(
            v.pick_schema_for_file("/tmp/wa.microsoft.graph.nodes.OSW.geojson", {"features": []}),
            v.dataset_schema_paths["nodes"],
        )
        self.assertEqual(
            v.pick_schema_for_file("/tmp/baseline.nodes.geojson", {"features": []}),
            v.dataset_schema_paths["nodes"],
        )
        self.assertEqual(
            v.pick_schema_for_file("/tmp/roadEdges.geojson", {"features": []}),
            v.line_schema_path,
        )

    def test_pick_schema_force_single_schema_override(self):
        force = "/forced/opensidewalks.schema-0.3.json"
        v = OSWValidation(zipfile_path="dummy.zip", schema_file_path=force)
        # should always return forced schema when provided
        self.assertEqual(v.pick_schema_for_file("/tmp/my.edges.geojson", {"features": []}), force)
        self.assertEqual(v.pick_schema_for_file("/any/path.json", {"features": [{"geometry": {"type": "Point"}}]}), force)

    def test_unexpected_exception_surfaces_unable_to_validate(self):
        """Any unexpected exception should be surfaced via 'Unable to validate'."""
        fake_files = ["/tmp/nodes.geojson"]
        with patch(_PATCH_ZIP) as PZip, \
             patch(_PATCH_EV) as PVal, \
             patch(_PATCH_VALIDATE, side_effect=RuntimeError("boom")), \
             patch(_PATCH_DATASET_FILES, _CANON_DATASET_FILES):

            z = MagicMock()
            z.extract_zip.return_value = "/tmp/extracted"
            z.remove_extracted_files.return_value = None
            PZip.return_value = z

            val = MagicMock()
            val.files = fake_files
            val.externalExtensions = []
            val.is_valid.return_value = True
            val.error = None
            PVal.return_value = val

            res = OSWValidation(zipfile_path="dummy.zip").validate()

        self.assertFalse(res.is_valid)
        self.assertTrue(any("Unable to validate: boom" in e for e in (res.errors or [])),
                        f"Errors were: {res.errors}")


class TestOSWValidationInvalidGeometryLogging(unittest.TestCase):
    """Covers the 'invalid geometries' logging branch, including _id-present and _id-missing fallback."""

    def _gdf_edges_wrong_geom(self, n, with_id=True):
        # Expected geometry (from patched OSW_DATASET_FILES) is LineString,
        # so we intentionally use Points to trigger invalids via type mismatch.
        data = {}
        if with_id:
            data["_id"] = list(range(100, 100 + n))
        # build Point geoms
        pts = [Point(i, i) for i in range(n)]
        data["geometry"] = pts
        return gpd.GeoDataFrame(data, geometry="geometry", crs="EPSG:4326")

    def _gdf_nodes(self, ids):
        return gpd.GeoDataFrame(
            {"_id": ids, "geometry": [Point(0, i) for i in range(len(ids))]},
            geometry="geometry",
            crs="EPSG:4326",
        )

    def _fake_validator(self, files, valid=True, error="folder invalid"):
        m = MagicMock()
        m.files = files
        m.externalExtensions = []
        m.is_valid.return_value = valid
        m.error = error
        return m

    def test_invalid_geometry_logs_ids_when__id_present(self):
        """When _id exists, the message should list some _id values and total count."""
        fake_files = ["/tmp/edges.geojson"]
        edges = self._gdf_edges_wrong_geom(n=3, with_id=True)

        with patch(_PATCH_ZIP) as PZip, \
             patch(_PATCH_EV) as PVal, \
             patch(_PATCH_VALIDATE, return_value=True), \
             patch(_PATCH_READ_FILE, return_value=edges), \
             patch(_PATCH_DATASET_FILES, _CANON_DATASET_FILES):
            z = MagicMock()
            z.extract_zip.return_value = "/tmp/extracted"
            z.remove_extracted_files.return_value = None
            PZip.return_value = z
            PVal.return_value = self._fake_validator(fake_files)

            res = OSWValidation(zipfile_path="dummy.zip").validate()
            self.assertFalse(res.is_valid)
            # Expect the invalid geometry message for 'edges'
            msg = next((e for e in (res.errors or []) if "invalid edges geometries" in e), None)
            self.assertIsNotNone(msg, f"No invalid-geometry message found. Errors: {res.errors}")
            self.assertIn("Showing all out of 3", msg)

    def test_invalid_geometry_logs_index_when__id_missing_and_caps_20(self):
        """When _id is missing, it falls back to index and caps display at 20 of N."""
        fake_files = ["/tmp/edges.geojson"]
        edges = self._gdf_edges_wrong_geom(n=25, with_id=False)  # 25 invalid features, no _id column

        with patch(_PATCH_ZIP) as PZip, \
                patch(_PATCH_EV) as PVal, \
                patch(_PATCH_VALIDATE, return_value=True), \
                patch(_PATCH_READ_FILE, return_value=edges), \
                patch(_PATCH_DATASET_FILES, _CANON_DATASET_FILES), \
                patch(_PATCH_UNIQUE, return_value=(True, [])):  # <-- bypass duplicates check entirely

            z = MagicMock()
            z.extract_zip.return_value = "/tmp/extracted"
            z.remove_extracted_files.return_value = None
            PZip.return_value = z
            PVal.return_value = self._fake_validator(fake_files)

            res = OSWValidation(zipfile_path="dummy.zip").validate()
            self.assertFalse(res.is_valid, f"Expected invalid; errors={res.errors}")
            msg = next((e for e in (res.errors or []) if "invalid edges geometries" in e), None)
            self.assertIsNotNone(msg, f"No invalid-geometry message found. Errors: {res.errors}")
            self.assertIn("Showing 20 out of 25", msg)


class TestGeometryMappingViaValidate(unittest.TestCase):
    """Unit tests for _u_id/_v_id/_w_id coordinate mapping through validate()."""

    # ---- GeoDataFrame helpers ----

    def _nodes_gdf(self, id_coord_pairs):
        """[(id, x, y), ...] → GeoDataFrame of Point nodes."""
        return gpd.GeoDataFrame(
            {
                "_id": [p[0] for p in id_coord_pairs],
                "geometry": [Point(p[1], p[2]) for p in id_coord_pairs],
            },
            geometry="geometry", crs="EPSG:4326",
        )

    def _edges_gdf(self, rows):
        """[(_id, _u_id, _v_id, coords), ...] → GeoDataFrame of LineString edges."""
        return gpd.GeoDataFrame(
            {
                "_id": [r[0] for r in rows],
                "_u_id": [r[1] for r in rows],
                "_v_id": [r[2] for r in rows],
                "geometry": [LineString(r[3]) for r in rows],
            },
            geometry="geometry", crs="EPSG:4326",
        )

    def _zones_gdf(self, rows):
        """[(_id, w_ids, ring), ...] → GeoDataFrame of Polygon zones."""
        return gpd.GeoDataFrame(
            {
                "_id": [r[0] for r in rows],
                "_w_id": [r[1] for r in rows],
                "geometry": [Polygon(r[2]) for r in rows],
            },
            geometry="geometry", crs="EPSG:4326",
        )

    def _patch_env(self, fake_files, read_side_effect):
        """Return a context manager tuple for patching zip+validator+read_file."""
        z = MagicMock()
        z.extract_zip.return_value = "/tmp/extracted"
        z.remove_extracted_files.return_value = None

        val = MagicMock()
        val.files = fake_files
        val.externalExtensions = []
        val.is_valid.return_value = True

        return z, val, read_side_effect

    # ---- helper to run validate() with mocks ----

    def _run(self, fake_files, read_fn):
        with patch(_PATCH_ZIP) as PZip, \
             patch(_PATCH_EV) as PVal, \
             patch(_PATCH_VALIDATE, return_value=True), \
             patch(_PATCH_READ_FILE) as PRead, \
             patch(_PATCH_DATASET_FILES, _CANON_DATASET_FILES):
            z, val, rf = self._patch_env(fake_files, read_fn)
            PZip.return_value = z
            PVal.return_value = val
            PRead.side_effect = rf
            return OSWValidation(zipfile_path="dummy.zip").validate()

    # ---- tests ----

    def test_valid_edge_mapping_passes(self):
        nodes = self._nodes_gdf([("n1", 0.0, 0.0), ("n2", 1.0, 1.0)])
        edges = self._edges_gdf([("e1", "n1", "n2", [(0.0, 0.0), (0.5, 0.5), (1.0, 1.0)])])

        def rf(path):
            b = os.path.basename(path)
            return nodes if "nodes" in b else edges if "edges" in b else gpd.GeoDataFrame()

        res = self._run(["/tmp/nodes.geojson", "/tmp/edges.geojson"], rf)
        self.assertTrue(res.is_valid, f"Expected valid; errors={res.errors}")

    def test_u_id_coord_mismatch_fails(self):
        nodes = self._nodes_gdf([("n1", 0.0, 0.0), ("n2", 1.0, 1.0)])
        # Edge starts at (9,9) but _u_id=n1 is at (0,0)
        edges = self._edges_gdf([("e1", "n1", "n2", [(9.0, 9.0), (1.0, 1.0)])])

        def rf(path):
            b = os.path.basename(path)
            return nodes if "nodes" in b else edges if "edges" in b else gpd.GeoDataFrame()

        res = self._run(["/tmp/nodes.geojson", "/tmp/edges.geojson"], rf)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("_u_id mismatch" in e for e in (res.errors or [])))

    def test_v_id_coord_mismatch_fails(self):
        nodes = self._nodes_gdf([("n1", 0.0, 0.0), ("n2", 1.0, 1.0)])
        # Edge ends at (8,8) but _v_id=n2 is at (1,1)
        edges = self._edges_gdf([("e1", "n1", "n2", [(0.0, 0.0), (8.0, 8.0)])])

        def rf(path):
            b = os.path.basename(path)
            return nodes if "nodes" in b else edges if "edges" in b else gpd.GeoDataFrame()

        res = self._run(["/tmp/nodes.geojson", "/tmp/edges.geojson"], rf)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("_v_id mismatch" in e for e in (res.errors or [])))

    def test_mismatch_error_includes_feature_index_and_id(self):
        nodes = self._nodes_gdf([("n1", 0.0, 0.0), ("n2", 1.0, 1.0)])
        edges = self._edges_gdf([("edge-xyz", "n1", "n2", [(9.0, 9.0), (1.0, 1.0)])])

        def rf(path):
            b = os.path.basename(path)
            return nodes if "nodes" in b else edges if "edges" in b else gpd.GeoDataFrame()

        res = self._run(["/tmp/nodes.geojson", "/tmp/edges.geojson"], rf)
        issue = next((i for i in (res.issues or []) if "_u_id mismatch" in i.get("error_message", "")), None)
        self.assertIsNotNone(issue)
        self.assertEqual(issue["filename"], "edges")
        self.assertIsNotNone(issue["feature_index"])
        self.assertIn("edge-xyz", issue["error_message"])

    def test_u_id_not_in_node_map_does_not_double_report(self):
        """Unknown _u_id is caught by the existence check; no coord error for it."""
        nodes = self._nodes_gdf([("n1", 0.0, 0.0)])
        edges = self._edges_gdf([("e1", "ghost", "n1", [(5.0, 5.0), (0.0, 0.0)])])

        def rf(path):
            b = os.path.basename(path)
            return nodes if "nodes" in b else edges if "edges" in b else gpd.GeoDataFrame()

        res = self._run(["/tmp/nodes.geojson", "/tmp/edges.geojson"], rf)
        # existence check fires, but no coordinate mismatch error
        coord_errs = [e for e in (res.errors or []) if "mismatch" in e]
        self.assertEqual(coord_errs, [])

    def test_no_nodes_file_skips_mapping(self):
        """When there are no nodes, coordinate checks are silently skipped."""
        edges = self._edges_gdf([("e1", "n1", "n2", [(0.0, 0.0), (1.0, 1.0)])])

        def rf(path):
            return edges if "edges" in os.path.basename(path) else gpd.GeoDataFrame()

        res = self._run(["/tmp/edges.geojson"], rf)
        self.assertTrue(res.is_valid, f"Expected valid; errors={res.errors}")

    def test_w_id_coord_mismatch_fails(self):
        ring = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        nodes = self._nodes_gdf([
            ("w1", 0.0, 0.0), ("w2", 1.0, 0.0), ("w3", 1.0, 1.0),
            ("w4", 9.0, 9.0),  # not in ring
        ])
        zones = self._zones_gdf([("z1", ["w1", "w2", "w3", "w4"], ring)])

        def rf(path):
            b = os.path.basename(path)
            return nodes if "nodes" in b else zones if "zones" in b else gpd.GeoDataFrame()

        res = self._run(["/tmp/nodes.geojson", "/tmp/zones.geojson"], rf)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("_w_id coordinate mismatch" in e for e in (res.errors or [])))
        self.assertTrue(any("w4" in e for e in (res.errors or [])))

    def test_valid_zone_mapping_passes(self):
        ring = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        nodes = self._nodes_gdf([
            ("w1", 0.0, 0.0), ("w2", 1.0, 0.0), ("w3", 1.0, 1.0), ("w4", 0.0, 1.0),
        ])
        zones = self._zones_gdf([("z1", ["w1", "w2", "w3", "w4"], ring)])

        def rf(path):
            b = os.path.basename(path)
            return nodes if "nodes" in b else zones if "zones" in b else gpd.GeoDataFrame()

        res = self._run(["/tmp/nodes.geojson", "/tmp/zones.geojson"], rf)
        self.assertTrue(res.is_valid, f"Expected valid; errors={res.errors}")

    def test_max_errors_caps_geometry_mapping_errors(self):
        nodes = self._nodes_gdf([("n1", 0.0, 0.0), ("n2", 1.0, 1.0)])
        # 10 edges all with wrong start coordinate
        edges = gpd.GeoDataFrame(
            {
                "_id": [f"e{i}" for i in range(10)],
                "_u_id": ["n1"] * 10,
                "_v_id": ["n2"] * 10,
                "geometry": [LineString([(9.0, 9.0), (1.0, 1.0)])] * 10,
            },
            geometry="geometry", crs="EPSG:4326",
        )

        def rf(path):
            b = os.path.basename(path)
            return nodes if "nodes" in b else edges if "edges" in b else gpd.GeoDataFrame()

        with patch(_PATCH_ZIP) as PZip, \
             patch(_PATCH_EV) as PVal, \
             patch(_PATCH_VALIDATE, return_value=True), \
             patch(_PATCH_READ_FILE) as PRead, \
             patch(_PATCH_DATASET_FILES, _CANON_DATASET_FILES):
            z = MagicMock()
            z.extract_zip.return_value = "/tmp/extracted"
            z.remove_extracted_files.return_value = None
            PZip.return_value = z
            val = MagicMock()
            val.files = ["/tmp/nodes.geojson", "/tmp/edges.geojson"]
            val.externalExtensions = []
            val.is_valid.return_value = True
            PVal.return_value = val
            PRead.side_effect = rf
            res = OSWValidation(zipfile_path="dummy.zip").validate(max_errors=3)

        self.assertFalse(res.is_valid)
        self.assertLessEqual(len(res.errors), 3)

    def test_coord_within_tolerance_no_error(self):
        """Coordinates within 1e-7 degrees are accepted as matching."""
        nodes = self._nodes_gdf([("n1", 0.0, 0.0), ("n2", 1.0, 1.0)])
        # Start is 5e-8 off (within tolerance)
        edges = self._edges_gdf([("e1", "n1", "n2", [(5e-8, 0.0), (1.0, 1.0)])])

        def rf(path):
            b = os.path.basename(path)
            return nodes if "nodes" in b else edges if "edges" in b else gpd.GeoDataFrame()

        res = self._run(["/tmp/nodes.geojson", "/tmp/edges.geojson"], rf)
        self.assertTrue(res.is_valid, f"Expected valid; errors={res.errors}")


if __name__ == "__main__":
    unittest.main()
