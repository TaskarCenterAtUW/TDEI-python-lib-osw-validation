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
print(result.errors)

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
test_invalid_empty_directory (test_extracted_data_validator.TestExtractedDataValidator) ... ok
test_invalid_missing_files_directory (test_extracted_data_validator.TestExtractedDataValidator) ... ok
test_invalid_missing_required_files_directory (test_extracted_data_validator.TestExtractedDataValidator) ... ok
test_valid_directory_structure (test_extracted_data_validator.TestExtractedDataValidator) ... ok
test_edges_invalid_zipfile (test_osw_validation.TestOSWValidation) ... ok
test_edges_invalid_zipfile_with_invalid_schema (test_osw_validation.TestOSWValidation) ... ok
test_edges_invalid_zipfile_with_schema (test_osw_validation.TestOSWValidation) ... ok
test_extra_field_zipfile (test_osw_validation.TestOSWValidation) ... ok
test_id_missing_zipfile (test_osw_validation.TestOSWValidation) ... ok
test_invalid_geometry_zipfile (test_osw_validation.TestOSWValidation) ... ok
test_invalid_zipfile (test_osw_validation.TestOSWValidation) ... ok
test_invalid_zipfile_with_invalid_schema (test_osw_validation.TestOSWValidation) ... ok
test_invalid_zipfile_with_schema (test_osw_validation.TestOSWValidation) ... ok
test_minimal_zipfile (test_osw_validation.TestOSWValidation) ... ok
test_minimal_zipfile_with_invalid_schema (test_osw_validation.TestOSWValidation) ... ok
test_minimal_zipfile_with_schema (test_osw_validation.TestOSWValidation) ... ok
test_missing_files_inside_zipfile (test_osw_validation.TestOSWValidation) ... ok
test_missing_files_inside_zipfile_with_invalid_schema (test_osw_validation.TestOSWValidation) ... ok
test_missing_files_inside_zipfile_with_schema (test_osw_validation.TestOSWValidation) ... ok
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
Ran 34 tests in 121.220s

OK
```