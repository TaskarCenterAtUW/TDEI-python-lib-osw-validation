import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import geopandas as gpd
from shapely.geometry import Point, LineString, Polygon

import src.python_osw_validation as osw_mod
from src.python_osw_validation import OSWValidation

# Build a robust patch prefix from the module actually imported
_PATCH_PREFIX = osw_mod.__name__
_PATCH_UNIQUE = f"{_PATCH_PREFIX}.OSWValidation.are_ids_unique"
_PATCH_ZIP = f"{_PATCH_PREFIX}.ZipFileHandler"
_PATCH_EV = f"{_PATCH_PREFIX}.ExtractedDataValidator"
_PATCH_READ_FILE = f"{_PATCH_PREFIX}.gpd.read_file"
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

    def test_missing_u_id_logged_and_no_keyerror(self):
        """Edges missing `_u_id` should log a friendly error instead of raising KeyError."""
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

    def test_load_osw_file_logs_json_decode_error(self):
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

    def test_load_osw_file_logs_os_error(self):
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

    def test_pick_schema_by_geometry_and_by_filename(self):
        """Point/LineString/Polygon ⇒ proper schema; filename fallback when features empty."""
        v = OSWValidation(zipfile_path="dummy.zip")

        self.assertEqual(
            v.pick_schema_for_file("/any/path.json", {"features": [{"geometry": {"type": "Point"}}]}),
            v.point_schema_path,
        )
        self.assertEqual(
            v.pick_schema_for_file("/any/path.json", {"features": [{"geometry": {"type": "LineString"}}]}),
            v.line_schema_path,
        )
        self.assertEqual(
            v.pick_schema_for_file("/any/path.json", {"features": [{"geometry": {"type": "Polygon"}}]}),
            v.polygon_schema_path,
        )
        self.assertEqual(
            v.pick_schema_for_file("/tmp/my.nodes.geojson", {"features": []}),
            v.point_schema_path,
        )
        self.assertEqual(
            v.pick_schema_for_file("/tmp/my.edges.geojson", {"features": []}),
            v.line_schema_path,
        )
        self.assertEqual(
            v.pick_schema_for_file("/tmp/my.zones.geojson", {"features": []}),
            v.polygon_schema_path,
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

    # ---------- _get_colset ----------
    def test_get_colset_returns_set_when_column_present(self):
        v = OSWValidation(zipfile_path="dummy.zip")
        gdf = self._gdf({"_id": [1, 2, 2, None, 3]}, geom="Point")
        s = v._get_colset(gdf, "_id", "nodes")
        self.assertEqual(s, {1, 2, 3})

    def test_get_colset_logs_and_returns_empty_when_missing(self):
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

    # ---------- pick_schema_for_file ----------
    def test_pick_schema_by_geometry(self):
        v = OSWValidation(zipfile_path="dummy.zip")
        self.assertEqual(
            v.pick_schema_for_file("/x/y.json", {"features": [{"geometry": {"type": "Point"}}]}),
            v.point_schema_path,
        )
        self.assertEqual(
            v.pick_schema_for_file("/x/y.json", {"features": [{"geometry": {"type": "LineString"}}]}),
            v.line_schema_path,
        )
        self.assertEqual(
            v.pick_schema_for_file("/x/y.json", {"features": [{"geometry": {"type": "Polygon"}}]}),
            v.polygon_schema_path,
        )

    def test_pick_schema_filename_fallback(self):
        v = OSWValidation(zipfile_path="dummy.zip")
        self.assertEqual(v.pick_schema_for_file("/tmp/my.nodes.geojson", {"features": []}), v.point_schema_path)
        self.assertEqual(v.pick_schema_for_file("/tmp/my.edges.geojson", {"features": []}), v.line_schema_path)
        self.assertEqual(v.pick_schema_for_file("/tmp/my.zones.geojson", {"features": []}), v.polygon_schema_path)

    def test_pick_schema_force_single_schema_override(self):
        force = "/forced/opensidewalks.schema.json"
        v = OSWValidation(zipfile_path="dummy.zip", schema_file_path=force)
        # should always return forced schema when provided
        self.assertEqual(v.pick_schema_for_file("/tmp/my.edges.geojson", {"features": []}), force)
        self.assertEqual(v.pick_schema_for_file("/any/path.json", {"features": [{"geometry": {"type": "Point"}}]}), force)


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


if __name__ == "__main__":
    unittest.main()
