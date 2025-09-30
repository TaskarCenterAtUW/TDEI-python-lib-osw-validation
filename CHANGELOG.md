# Change log

### 0.2.15
- Update the base schema to make the $schema key is required
- Added unit test cases for that


### 0.2.14
- Improved GeoJSON parse error reporting with detailed file, line, and column context.
- Added unit tests covering JSON parsing and file read failure scenarios.
- Capped duplicate `_id` validation messages default it to first 20 values while reporting the total duplicate count to avoid excessively large issue payloads.
- Added a new unit test that verifies duplicate ID logging trims the displayed IDs to 20 while reporting the total number of duplicates.

### 0.2.13
- Updated Schema

### 0.2.12

#### Added
- Per-geometry schema support: auto-picks Point/LineString/Polygon schemas with sensible defaults.
- Structured per-feature **issues** output (former “fixme”): one best, human-friendly message per feature.
- Friendly error formatter:
  - Compacts `Enum` errors.
  - Summarizes `anyOf` by unioning required keys → “must include one of: …”.
- `_feature_index_from_error()` to reliably extract `feature_index` from `jsonschema_rs` error paths.
- `_get_colset()` utility for safe set extraction with diagnostics for missing columns.
- Unit tests covering helpers, schema selection, and issues aggregation.

#### Changed
- `validate()` now **streams** `jsonschema_rs` errors; legacy `errors` list remains but is capped by `max_errors`.
- `ValidationResult` now includes `issues`.
- Schema selection prefers geometry from the first feature; falls back to filename heuristics (`nodes/points`, `edges/lines`, `zones/polygons`).

#### Fixed
- Robust GeoJSON/extension handling:
  - Safe fallback to index when `_id` is missing.
  - Non-serializable property detection in extensions (with clear messages).
- Safer flattening of `_w_id` (list-like) for zone validations.

#### Migration Notes
- Prefer consuming `ValidationResult.issues` for per-feature UX and tooling.

### 0.2.11

- Fixed [BUG-2065](https://dev.azure.com/TDEI-UW/TDEI/_workitems/edit/2065/)
- Added functionality to catch serialization errors
- Added unit test cases for that
- Added test file `test_serialization_error.zip` to test the serialization error

### 0.2.10

- Added limit the message error when u_id and v_id are missing
- Added Unit test cases for missing u_id and v_id

### 0.2.8

- Fixed geopands version to `0.14.4`.
- Latest geopands version `0.10.0` is not compatible and failing to parse the zones.
- Added unit test cases for valid and invalid zone files

### 0.2.7

- Switch to `jsonschema_rs` for performance enhancement, instead of `jsonschema` package
- Refactor code for improve memory utilization
- Added garbage collector

### 0.2.6

- Add garbage collection to free up memory after validation

### 0.2.5

- Updated geopandas package

### 0.2.3

- Performance improvement if there are any errors

### 0.2.2

- Added functionality to get the specific number of errors
  ```
  validator = OSWValidation(zipfile_path=<ZIP_FILE_PATH>)
  result = validator.validate() // will return only first 20 errors by default
  result = validator.validate(max_errors=10) // will return only first 10 errors
  ```

### 0.2.1

- Updated zipfile_handler
- Fixed "No .geojson files found in the specified directory or its subdirectories." issue

### 0.2.0

- Updated schema file to OSW 0.2
- Added create_zip method to ZipFileHandler
- Made all OSW files optional
- Added additional validation steps based on the OSW network properties
- Add external extensions to ExtractedDataValidator
- Validate external extensions against basic Open Geospatial Consortium (OGC) standards
- Aggregate schema errors and data integrity errors separately before returning errors to user

### 0.0.5

- Support for multi-level geojson file
- Now handles the following two folder structures when unzipped abc.zip
    1. abc\{nodes, edges, points}.geojson
    2. {nodes, edges, points}.geojson

### 0.0.4

- Points are not required for a valid OSW dataset

### 0.0.3

- Added schema file to package

### 0.0.2

- Updated package Unit test cases.
- Updated README file

### 0.0.1

- Initial version of python_osw_validation package.
