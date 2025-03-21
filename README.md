# TDEI python lib OSW validation package

This package validates the OSW geojson file. Package requires a OSW zip file path

## System requirements

| Software | Version |
|----------|---------|
| Python   | 3.10.x  |

## What this package does?

- It unzip the provided zip files
- Check for the required nodes and edges geojson files inside the unzipped folder
- Validate each file (nodes, edges and points) against schema, schema can be found here
- Return true or false according to validation
- you can check the error if it returned false.

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
print(result.errors) # will return first 20 errors by default if there are errors

result = validator.validate(max_errors=10)  
print(result.is_valid)
print(result.errors) # will return first 10 errors depending on the max_errors parameter

```

### Testing

The project is configured with `python` to figure out the coverage of the unit tests. All the tests are in `tests`
folder.

- To execute the tests, please follow the commands:

  `pip install -r requirements.txt`

  `python -m unittest discover -v tests/unit_tests`

- To execute the code coverage, please follow the commands:

  `coverage run --source=src/python_osw_validation -m unittest discover -v tests/unit_tests`

  `coverage html` // Can be run after 1st command

  `coverage report` // Can be run after 1st command

- After the commands are run, you can check the coverage report in `htmlcov/index.html`. Open the file in any browser,
  and it shows complete coverage details
- The terminal will show the output of coverage like this

```shell

>  coverage run --source=src/python_osw_validation -m unittest discover -v tests/unit_tests
test_duplicate_files (test_extracted_data_validator.TestExtractedDataValidator) ... ok
test_empty_directory (test_extracted_data_validator.TestExtractedDataValidator) ... ok
test_invalid_directory (test_extracted_data_validator.TestExtractedDataValidator) ... ok
test_missing_optional_file (test_extracted_data_validator.TestExtractedDataValidator) ... ok
test_no_geojson_files (test_extracted_data_validator.TestExtractedDataValidator) ... ok
test_valid_data_at_root (test_extracted_data_validator.TestExtractedDataValidator) ... ok
test_valid_data_inside_folder (test_extracted_data_validator.TestExtractedDataValidator) ... ok
test_edges_invalid_zipfile (test_osw_validation.TestOSWValidation) ... ok
test_edges_invalid_zipfile_with_invalid_schema (test_osw_validation.TestOSWValidation) ... ok
test_edges_invalid_zipfile_with_schema (test_osw_validation.TestOSWValidation) ... ok
test_external_extension_file_inside_zipfile (test_osw_validation.TestOSWValidation) ... ok
test_external_extension_file_inside_zipfile_with_invalid_schema (test_osw_validation.TestOSWValidation) ... ok
test_external_extension_file_inside_zipfile_with_schema (test_osw_validation.TestOSWValidation) ... ok
test_extra_field_zipfile (test_osw_validation.TestOSWValidation) ... ok
test_id_missing_zipfile (test_osw_validation.TestOSWValidation) ... ok
test_invalid_geometry_zipfile (test_osw_validation.TestOSWValidation) ... ok
test_invalid_zipfile (test_osw_validation.TestOSWValidation) ... ok
test_invalid_zipfile_with_invalid_schema (test_osw_validation.TestOSWValidation) ... ok
test_invalid_zipfile_with_schema (test_osw_validation.TestOSWValidation) ... ok
test_minimal_zipfile (test_osw_validation.TestOSWValidation) ... ok
test_minimal_zipfile_with_invalid_schema (test_osw_validation.TestOSWValidation) ... ok
test_minimal_zipfile_with_schema (test_osw_validation.TestOSWValidation) ... ok
test_missing_identifier_zipfile (test_osw_validation.TestOSWValidation) ... ok
test_no_entity_zipfile (test_osw_validation.TestOSWValidation) ... ok
test_nodes_invalid_zipfile (test_osw_validation.TestOSWValidation) ... ok
test_nodes_invalid_zipfile_with_invalid_schema (test_osw_validation.TestOSWValidation) ... ok
test_nodes_invalid_zipfile_with_schema (test_osw_validation.TestOSWValidation) ... ok
test_points_invalid_zipfile (test_osw_validation.TestOSWValidation) ... ok
test_points_invalid_zipfile_with_invalid_schema (test_osw_validation.TestOSWValidation) ... ok
test_points_invalid_zipfile_with_schema (test_osw_validation.TestOSWValidation) ... ok
test_valid_zipfile (test_osw_validation.TestOSWValidation) ... ok
test_valid_zipfile_with_invalid_schema (test_osw_validation.TestOSWValidation) ... ok
test_valid_zipfile_with_schema (test_osw_validation.TestOSWValidation) ... ok
test_wrong_datatypes_zipfile (test_osw_validation.TestOSWValidation) ... ok
test_extract_invalid_zip (test_zipfile_handler.TestZipFileHandler) ... ok
test_extract_valid_zip (test_zipfile_handler.TestZipFileHandler) ... ok
test_remove_extracted_files (test_zipfile_handler.TestZipFileHandler) ... ok

----------------------------------------------------------------------
Ran 37 tests in 1284.068s

OK
```

## Use locally:
To use the library locally, use the [example.py](./src/example.py) code

## Deployment:

- The library can be pushed to [TestPy](https://test.pypi.org/project/python-osw-validation/) or [PYPI](https://pypi.org/project/python-osw-validation/)
### Deploy to TestPy
- On every push to `dev` branch, a workflow is triggered which publishes the updated version to TestPy

### Deploy to PyPI
- This happens whenever a tag/release is created with `*.*.*` notation (eg. 0.0.8)
- To change the version, change the version at [version.py](./src/python_osw_validation/version.py)
- To release a new version:
  - Go to Github link of this repository
  - Under [releases](https://github.com/TaskarCenterAtUW/TDEI-python-lib-osw-validation/releases), click on `Draft a new release`
  - Under `choose a new tag`, add a new tag `v*.*.*` , Generate Release notes
  - Choose `main` branch for release
  - Publish the release.
- This release triggers a workflow to generate the new version of the Package.
- The new package will be available at https://pypi.org/project/python-osw-validation/