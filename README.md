# TDEI python lib OSW validation package

This package validates OSW GeoJSON datasets packaged as a ZIP file.

## System requirements

| Software | Version |
|----------|---------|
| Python   | >= 3.10 |

## What this package does?

- Extracts the provided ZIP file
- Finds supported OSW dataset files inside the extracted directory
- Validates each file (`edges`, `lines`, `nodes`, `points`, `polygons`, and `zones`) against the matching schema
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
print(result.issues)  # per-file or per-feature issues

result = validator.validate(max_errors=10)
print(result.is_valid)
print(result.errors)  # returns up to the first 10 high-level errors
```

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

The validator accepts dataset files whose names end with one of these exact suffixes:

- `.edges.geojson`
- `.lines.geojson`
- `.nodes.geojson`
- `.points.geojson`
- `.polygons.geojson`
- `.zones.geojson`

It also accepts the legacy form:

- `.edges.OSW.geojson`
- `.lines.OSW.geojson`
- `.nodes.OSW.geojson`
- `.points.OSW.geojson`
- `.polygons.OSW.geojson`
- `.zones.OSW.geojson`

Examples:

- `gs_metaline_falls_uga.nodes.geojson` is valid
- `gs_yarrow_point.edges.geojson` is valid
- `roadEdges.geojson` is invalid

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
