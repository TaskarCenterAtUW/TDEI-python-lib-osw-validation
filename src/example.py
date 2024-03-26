import os
from python_osw_validation import OSWValidation

PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(PARENT_DIR, 'tests/assets')
VALID_ZIP_FILE = os.path.join(ASSETS_DIR, 'valid.zip')
INVALID_ZIP_FILE = os.path.join(ASSETS_DIR, 'invalid.zip')
TEST_ZIP_FILE = os.path.join(ASSETS_DIR,'Archive.zip')
SCHEMA_DIR = os.path.join(PARENT_DIR, 'src/python_osw_validation/schema')
SCHEMA_FILE_PATH = os.path.join(SCHEMA_DIR, 'opensidewalks.schema.json')


def valid_test_with_provided_schema():
    validator = OSWValidation(zipfile_path=VALID_ZIP_FILE, schema_file_path=SCHEMA_FILE_PATH)
    result = validator.validate()
    print(f'Valid Test With Provided Schema: {"Passed" if result.is_valid else "Failed"}')


def valid_test_without_provided_schema():
    validator = OSWValidation(zipfile_path=VALID_ZIP_FILE)
    result = validator.validate()
    print(f'Valid Test Without Schema: {"Passed" if result.is_valid else "Failed"}')


def invalid_test_with_provided_schema():
    validator = OSWValidation(zipfile_path=INVALID_ZIP_FILE, schema_file_path=SCHEMA_FILE_PATH)
    result = validator.validate()
    if not result.is_valid:
        for error in result.errors:
            print(error)
    print(f'Invalid Test With Provided Schema: {"Failed" if result.is_valid else "Passed"}')


def invalid_test_without_provided_schema():
    validator = OSWValidation(zipfile_path=INVALID_ZIP_FILE)
    result = validator.validate()
    print(f'Invalid Test Without Schema: {"Failed" if result.is_valid else "Passed"}')

def test_with_archive_file():
    validator = OSWValidation(zipfile_path=TEST_ZIP_FILE)
    result = validator.validate()
    print(result.errors)
    print(result.is_valid)


if __name__ == '__main__':
    # valid_test_with_provided_schema()
    # valid_test_without_provided_schema()
    # invalid_test_with_provided_schema()
    # invalid_test_without_provided_schema()
    test_with_archive_file()
