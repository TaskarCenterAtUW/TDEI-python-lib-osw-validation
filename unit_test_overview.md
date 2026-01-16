# Unit Test Scenario Counts

Below is a breakdown of all test scenarios (functions named `test_`) across the suite, plus a short description of the main areas they cover.

- **Total scenarios:** 120
- **Unit test subset (tests/unit_tests) scenarios:** 106 (matches `coverage run --source=src/python_osw_validation -m unittest discover -v tests/unit_tests`)

| Test module | Scenarios | Focus |
| --- | ---: | --- |
| tests/test_schema_parity.py | 14 | Schema parity and customized-field handling |
| tests/unit_tests/test_extracted_data_validator.py | 11 | Folder/filename validation, duplicates/missing files, unsupported files |
| tests/unit_tests/test_helpers.py | 17 | Helper utilities (pretty messages, rankings, feature index extraction, additional-properties hint) |
| tests/unit_tests/test_osw_validation.py | 34 | End-to-end ZIP validation across assets (valid/invalid, schemas, serialization, unmatched IDs) |
| tests/unit_tests/test_osw_validation_extras.py | 35 | Edge cases: foreign-key checks, duplicate IDs, invalid geometries, extension file failures, JSON/OS errors, 0.2 disallowed content, unexpected exceptions, structure error messaging |
| tests/unit_tests/test_schema_definitions.py | 1 | Schema definition smoke check |
| tests/unit_tests/test_schema_metadata.py | 3 | Metadata/heuristic schema selection |
| tests/unit_tests/test_zipfile_handler.py | 5 | Zip extraction/creation lifecycle |

Method used: counted functions matching `def test_` within `tests/` (full suite) and separately validated the `tests/unit_tests` subset via the coverage command above.

## Detail for heavy-hitter suites

### tests/unit_tests/test_osw_validation.py (34 scenarios)
- Zip validation success/failure paths: `test_valid_zipfile`, `test_valid_zipfile_with_schema`, `test_valid_zipfile_with_invalid_schema`, `test_minimal_zipfile*`, `test_invalid_zipfile*` (with/without schemas, error cap checks).
- Dataset-specific invalid archives: `test_nodes_invalid_zipfile*`, `test_edges_invalid_zipfile*`, `test_points_invalid_zipfile*`.
- External extensions: `test_external_extension_file_inside_zipfile*` (default/override/invalid schema).
- Schema-level failures: missing `_id` (`test_id_missing_zipfile`), extra fields, invalid geometry, missing identifiers, no entities, wrong datatypes.
- Zones coverage: `test_valid_zones_file`, `test_invalid_zones_file`.
- Serialization error surfaced: `test_invalid_serialization_file`.
- Foreign-key cap: `test_unmatched_ids_limited_to_20`.

### tests/unit_tests/test_osw_validation_extras.py (35 scenarios)
- Foreign-key checks: `test_missing_u_id_reports_error_without_keyerror`, `test_unmatched_u_id_is_limited_to_20`, `test_unmatched_w_id_is_limited_to_20`.
- JSON/IO parsing: `test_load_osw_file_reports_json_decode_error`, `test_load_osw_file_reports_os_error`, `test_validate_reports_json_decode_error`.
- GeoDataFrame read failures: `test_validate_reports_read_file_exception`.
- Zones column presence: `test_missing_w_id_reports_error`.
- Extension handling: read failure, invalid IDs, invalid geometries, serialization failure (`test_extension_*` group).
- Duplicate IDs: `test_duplicate_ids_detection`, `test_duplicate_ids_detection_is_limited_to_20`.
- Invalid geometries: `_id` present vs missing with cap (`test_invalid_geometry_logs_*`).
- Helpers and selection: `test_pick_schema_*`, `_get_colset*`, `test_load_osw_schema_reports_missing_file`.
- 0.2 disallowed content vs 0.3 allowed: `test_schema_02_rejects_tree_and_custom`, `test_schema_03_with_tree_tags_is_allowed`.
- Robustness: cleanup handling, zip extract failure, invalid folder structure, unexpected exception path (`test_cleanup_handles_locals_membership_error`, `test_zip_extract_failure_bubbles_as_error`, `test_extracted_data_validator_invalid`, `test_unexpected_exception_surfaces_unable_to_validate`, `test_issues_populated_for_invalid_zip`).
- Uploaded-name fidelity: structure errors report the uploaded filename instead of temp extraction dirs (`test_structure_error_uses_uploaded_filename`).

### tests/unit_tests/test_extracted_data_validator.py (11 scenarios)
- Valid layouts at root or nested, empty/invalid directories, and no-geojson detection.
- Duplicate detection and missing required files (patched OSW_DATASET_FILES).
- Non-standard filenames rejected; valid subsets of canonical OSW files accepted.
- Unsupported GeoJSON types (non OSW keys) are rejected.

### tests/test_schema_parity.py (14 scenarios)
- Custom feature acceptance/rejection across nodes/edges/points/lines/polygons/zones.
- 0.2 vs 0.3 parity: custom tags rejected on 0.2 where appropriate; accepted on 0.3.
- Extension fields allowed/blocked per schema version.

### tests/unit_tests/test_helpers.py (17 scenarios)
- Feature index extraction robustness across error shapes.
- Pretty-message compaction (enum, anyOf, ordering, trimming noise, additional-properties hint appended).
- Error ranking/tie-breaking and message selection helpers.

### tests/unit_tests/test_schema_definitions.py (1 scenario)
- Ensures schema definitions include required fields (smoke check).

### tests/unit_tests/test_schema_metadata.py (3 scenarios)
- Enforces schema requirement by geometry type (Point/LineString/Polygon) when schema URL missing.

### tests/unit_tests/test_zipfile_handler.py (5 scenarios)
- Zip extraction success/failure, cleanup of extracted files.
- Zip creation happy path and failure path.

## Coverage snapshot

Name | Stmts | Miss | Cover
--- | ---: | ---: | ---:
src/python_osw_validation/__init__.py | 300 | 8 | 97%
src/python_osw_validation/extracted_data_validator.py | 90 | 1 | 99%
src/python_osw_validation/helpers.py | 54 | 2 | 96%
src/python_osw_validation/version.py | 1 | 0 | 100%
src/python_osw_validation/zipfile_handler.py | 48 | 1 | 98%
**TOTAL** | 493 | 12 | 98%
