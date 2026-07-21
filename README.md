# TDEI python lib OSW validation package

[![python-osw-validation](https://img.shields.io/pypi/v/python-osw-validation?label=python-osw-validation&cacheSeconds=60&t=1)](https://pypi.org/project/python-osw-validation/)
[![Unit Tests](https://github.com/TaskarCenterAtUW/TDEI-python-lib-osw-validation/actions/workflows/unit_tests.yml/badge.svg)](https://github.com/TaskarCenterAtUW/TDEI-python-lib-osw-validation/actions/workflows/unit_tests.yml)
![Coverage](https://raw.githubusercontent.com/TaskarCenterAtUW/TDEI-python-lib-osw-validation/badges/coverage.svg)

This package validates OSW GeoJSON datasets packaged as a ZIP file.

## System requirements

| Software | Version |
|----------|---------|
| Python   | >= 3.10 |

## What this package does?

- Extracts the provided ZIP file
- Finds supported OSW dataset files inside the extracted directory
- Validates each file (`edges`, `lines`, `nodes`, `points`, `polygons`, and `zones`) against the matching schema
- Performs an upfront data-quality check for actual null and numeric NaN values in `ext:*` extension properties (for example JSON `null` or numeric `NaN`; string values like `"null"` and `"nan"` are not rejected by this precheck)
- Runs cross-file integrity checks such as duplicate `_id` detection and edge or zone references back to nodes
- Returns a `ValidationResult` object with `is_valid`, `errors`, and `issues`

Any subset of the six supported dataset files may be present. By default, no individual dataset file is required.

## Starting a new project with template

- Add `python-osw-validation` package as dependency in your `requirements.txt`
- or `pip install python-osw-validation`
- Start using the packages in your code.

## Initialize and Configuration

```python
from python_osw_validation import OSWValidation

validator = OSWValidation(zipfile_path='<Zip file path>')
result = validator.validate()
print(result.is_valid)
print(result.errors)  # returns up to the first 20 high-level errors by default
print(result.error_details)  # structured high-level error code, severity, and message
print(result.issues)  # detailed per-feature issues, capped to first 20 by default
print(result.issue_details)  # issues plus stable code and severity fields
print(result.warnings)  # non-blocking coordinate precision warning, or an empty string
print(result.warning_details)  # structured warning code, severity, and message
print(result.summary)  # counts grouped by severity, code, and file

result = validator.validate(max_errors=10)
print(result.is_valid)
print(result.errors)  # returns up to the first 10 high-level errors
print(result.issues)  # capped by the same max_errors limit
```

### Validation configuration

`ValidationConfig` provides per-validator threshold overrides. Existing behavior is
preserved when no configuration is supplied.

```python
from python_osw_validation import OSWValidation, ValidationConfig

config = ValidationConfig(
    max_geometry_vertices=3000,
    coordinate_precision=8,
    allow_zero_length_lines=True,
)

validator = OSWValidation(
    zipfile_path="dataset.zip",
    config=config,
)
result = validator.validate()
```

| Setting | Default | Meaning |
|---------|---------|---------|
| `max_geometry_vertices` | `2000` | Maximum allowed vertices for edges, lines, polygons, and zones. The value must be an integer greater than zero. |
| `coordinate_precision` | `7` | Maximum decimal places before a non-blocking `COORDINATE_PRECISION` warning is reported. The value must be a non-negative integer. |
| `allow_zero_length_lines` | `False` | When `True`, allows line and edge geometries whose coordinates all represent the same location. The value must be a boolean. |

`VERTEX_LIMIT_DATASETS` remains an internal OSW policy and is not configurable.
Changing these thresholds can make results differ from the default TDEI validation
policy. When zero-length lines are allowed, endpoint references and exact node-coordinate
matching are still enforced. Zero-area polygons and zones remain invalid. Exact edge/node
and zone/node coordinate matching is not configurable.

## Error behavior

- `errors`: high-level validation messages, capped by `max_errors` (default `20`).
- `error_details`: structured equivalents of `errors` with stable `code`, `severity`,
  and `message` fields.
- `issues`: detailed per-feature validation issues, also capped by `max_errors`.
- `issue_details`: mirrors `issues` and adds stable `code` and `severity` fields.
  The legacy `issues` payload and message formats remain unchanged.
- `warning_details`: structured warnings; `warnings` remains the legacy aggregate string.
- `summary`: aggregate `error_count`, `warning_count`, `issue_count`, `by_severity`,
  `by_code`, and `by_file` values.
- If actual null or numeric NaN values are found in `ext:*` extension properties, validation fails early before schema checks with actionable messages such as:
  - `Invalid value at 'ext:metadata.score': nan. Null/NaN placeholders are not allowed; provide a valid value or remove this property.`
- For enum validation, long allowed-value lists are summarized as:
  - first 5 values joined by `|`
  - followed by `| and N more` when applicable.

You can also override schemas:

```python
from python_osw_validation import OSWValidation

validator = OSWValidation(
    zipfile_path='<Zip file path>',
    schema_paths={
        'nodes': 'path/to/opensidewalks.nodes.schema-0.3.json',
        'edges': 'path/to/opensidewalks.edges.schema-0.3.json',
    },
)
```

Example structured `issue_details` item:

```python
{
    "filename": "edges",
    "feature_index": 12,
    "error_message": "Feature 'e-12' has zero-length geometry ...",
    "code": "COLLAPSED_GEOMETRY",
    "severity": "error",
}
```

### Error and warning codes

Codes are stable, machine-readable identifiers in upper snake case. Use codes for
application logic and use `message` or `error_message` for display. Do not parse the
human-readable message to determine the failure type.

- `error_details` represents the high-level legacy `errors` list and uses the generic
  `VALIDATION_ERROR` code.
- `issue_details` provides the specific error code for each detailed validation issue.
- `warning_details` provides non-blocking warning codes.
- Error severity is `error`; warning severity is `warning`.

#### General and schema error codes

| Code | Meaning |
|------|---------|
| `VALIDATION_ERROR` | A high-level validation failure, or a detailed issue for which no more specific code is available. |
| `SCHEMA_VALIDATION` | A JSON Schema failure whose schema keyword could not be identified. |
| `SCHEMA_REQUIRED` | A property required by the selected schema is missing. |
| `SCHEMA_TYPE` | A value has a different datatype from the datatype required by the schema. |
| `SCHEMA_ENUM` | A value is not one of the values allowed by the schema. |
| `SCHEMA_ANY_OF` | A value does not satisfy any schema branch in an `anyOf` rule. |
| `SCHEMA_ADDITIONAL_PROPERTIES` | A property is not allowed by the selected schema. |
| `NULLISH_EXTENSION_VALUE` | An `ext:*` property contains an actual null or numeric NaN value. |
| `UNSUPPORTED_OSW_02_CONTENT` | An OSW 0.2 dataset contains custom tokens or tree content that the compatibility rules do not support. |

Other JSON Schema keywords follow the same convention: `SCHEMA_` plus the keyword
converted to upper snake case. For example, `minItems` becomes `SCHEMA_MIN_ITEMS`.

#### Identifier and mapping error codes

| Code | Meaning |
|------|---------|
| `MISSING_REQUIRED_COLUMN` | A dataset is missing a column required for cross-file validation, such as `_id`, `_u_id`, `_v_id`, or `_w_id`. |
| `COLUMN_VALUE_ERROR` | Values from a required column could not be read into a comparable set. |
| `DUPLICATE_IDENTIFIER` | A dataset contains more than one feature with the same `_id`. |
| `UNMATCHED_REFERENCE` | An edge or zone references a node ID that is not present in the nodes dataset. |
| `EDGE_NODE_COORDINATE_MISMATCH` | An edge start or end coordinate does not exactly match its referenced `_u_id` or `_v_id` node coordinate. |
| `ZONE_NODE_COORDINATE_MISMATCH` | A node referenced by a zone `_w_id` is not an exact vertex of the zone exterior ring. |

#### Geometry error codes

| Code | Meaning |
|------|---------|
| `INVALID_GEOMETRY` | A feature has the wrong geometry type or fails geometry validity checks. |
| `COLLAPSED_GEOMETRY` | A line has zero length or a polygon has zero area because all of its coordinates are identical. |
| `GEOMETRY_VERTEX_LIMIT` | An edge, line, polygon, or zone contains more than 2,000 geometry vertices. |
| `GEOMETRY_ID_EXTRACTION_ERROR` | Invalid extension geometries were found, but their feature IDs could not be extracted for reporting. |

#### Warning codes

| Code | Meaning | Effect on `is_valid` |
|------|---------|----------------------|
| `COORDINATE_PRECISION` | At least one input coordinate has more than seven decimal places. | None; this warning is non-blocking. |

## Troubleshooting

- Check `result.is_valid` first; warnings never make a valid dataset invalid.
- Use `result.summary["by_file"]` to locate the files with the most reported issues.
- Use issue `feature_index` and `filename` to locate a feature, then use `code` for
  stable application logic and `error_message` for display.
- Increase `max_errors` when the default cap of 20 hides later failures.
- Coordinate mismatch checks use exact longitude/latitude equality; preserve source
  precision when generating referenced nodes, edges, and zones.

## Supported filenames

The validator accepts four filename formats for each dataset type:

- `<dataset>.geojson`
- `*.<dataset>.geojson`
- `<dataset>.OSW.geojson`
- `*.<dataset>.OSW.geojson`

Where `<dataset>` is one of:

- `edges`
- `lines`
- `nodes`
- `points`
- `polygons`
- `zones`

Examples:

- `nodes.geojson` is valid
- `gs_metaline_falls_uga.nodes.geojson` is valid
- `nodes.OSW.geojson` is valid
- `gs_yarrow_point.edges.geojson` is valid
- `wa.microsoft.graph.edges.OSW.geojson` is valid
- `roadEdges.geojson` is invalid
- `roadedges.geojson` is invalid
- `River._edges_.geojson` is invalid

If a dataset uses canonical OSW 0.3 names that start with `opensidewalks.`, then only these exact names are allowed:

- `opensidewalks.edges.geojson`
- `opensidewalks.lines.geojson`
- `opensidewalks.nodes.geojson`
- `opensidewalks.points.geojson`
- `opensidewalks.polygons.geojson`
- `opensidewalks.zones.geojson`

### Testing

All unit tests are under `tests/unit_tests`.

- To execute the tests:

  `pip install -r requirements.txt`

  `python -m unittest discover -v tests/unit_tests`

- To execute code coverage:

  `coverage run --source=src/python_osw_validation -m unittest discover -v tests/unit_tests`

  `coverage html`

  `coverage report`

After running coverage, open `htmlcov/index.html` to inspect the report in a browser.

### Validation architecture

`OSWValidation` is the public entry point and remains responsible for ZIP extraction,
file loading, schema streaming, compatibility output, and cleanup. Reusable validation
logic lives under `src/python_osw_validation/validators/`:

- `geometry.py`: collapsed geometries, geometry types, SFA validity, and vertex limits.
- `mapping.py`: edge/node and zone/node coordinate mapping.
- `identifiers.py`: duplicate IDs, required reference columns, and unmatched references.
- `precision.py`: non-blocking coordinate precision detection.
- `schema.py`: schema selection, nullish extension values, and OSW 0.2 compatibility helpers.

Validator modules return immutable `ValidationFinding` values instead of mutating the
public validator. `OSWValidation` converts those findings into the existing `errors` and
`issues` response, preserving backward compatibility.

## Use locally
To use the library locally, use the [example.py](./src/example.py) code

## Deployment

- The library can be pushed to [TestPyPI](https://test.pypi.org/project/python-osw-validation/) or [PyPI](https://pypi.org/project/python-osw-validation/)

### Deploy to TestPyPI

- On every push to `dev` branch, a workflow is triggered which publishes the updated version to TestPyPI

### Deploy to PyPI

- This happens whenever a tag or release is created with `*.*.*` notation, for example `0.0.8`
- To change the version, update [version.py](./src/python_osw_validation/version.py)
- To release a new version:
  - Go to the GitHub repository
  - Under [releases](https://github.com/TaskarCenterAtUW/TDEI-python-lib-osw-validation/releases), click on `Draft a new release`
  - Under `choose a new tag`, add a new tag `v*.*.*`, then generate release notes
  - Choose `main` branch for release
  - Publish the release.
- This release triggers a workflow to generate the new package version.
- The new package will be available at https://pypi.org/project/python-osw-validation/
