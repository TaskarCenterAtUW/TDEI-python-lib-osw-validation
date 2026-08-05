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
print(result.issues)  # detailed per-feature issues, capped to first 20 by default

result = validator.validate(max_errors=10)
print(result.is_valid)
print(result.errors)  # returns up to the first 10 high-level errors
print(result.issues)  # capped by the same max_errors limit
```

### Validation configuration

Use `ValidationConfig` to override validation behavior for one validator instance.
When no configuration is supplied, the documented defaults are used.

```python
from python_osw_validation import OSWValidation, ValidationConfig

config = ValidationConfig(
    max_geometry_vertices=3000,
    coordinate_precision=8,
    allow_zero_length_lines=False,
)

validator = OSWValidation(
    zipfile_path="dataset.zip",
    config=config,
)
result = validator.validate()
```

| Setting | Default | Meaning |
|---------|---------|---------|
| `max_geometry_vertices` | `2000` | Maximum allowed vertices for edges, lines, polygons, and zones. Must be an integer greater than zero. |
| `coordinate_precision` | `7` | Maximum coordinate decimal places allowed. Features exceeding it fail validation. Must be a non-negative integer. |
| `allow_zero_length_lines` | `True` | Allows collapsed `LineString` geometries in edges, lines, and external line data. Set to `False` to reject them. |

Allowing zero-length lines does not bypass `_u_id`/`_v_id` existence or exact
node-coordinate checks. Zero-area polygons and zones, collapsed `MultiLineString`
geometries, and line geometries in point datasets remain invalid.

## Error behavior

- `errors`: high-level validation messages, capped by `max_errors` (default `20`).
- `issues`: detailed per-feature validation issues, also capped by `max_errors`.
- Coordinates carrying more than `coordinate_precision` decimal places fail validation before schema checks, one error per offending feature, and the message names the fix:
  - `Feature 12 in 'osw.edges.geojson' contains coordinates with more than 7 decimal places. Reduce them to at most 7 decimal places; you can use the OSW data wizard tool to clean this up.`
- `issues[].filename` is always the GeoJSON file the problem was found in, never an internal dataset key.
- If actual null or numeric NaN values are found in `ext:*` extension properties, validation fails early before schema checks with actionable messages such as:
  - `Invalid value at 'ext:metadata.score': nan. Null/NaN placeholders are not allowed; provide a valid value or remove this property. You can use the OSW data wizard tool to clean this up.`
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
