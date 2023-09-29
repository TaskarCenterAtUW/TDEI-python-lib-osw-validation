import os
from python_lib_osw_validation import OSWValidation

PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(PARENT_DIR, 'tests/assets')
VALID_ZIP_FILE = os.path.join(ASSETS_DIR, 'valid.zip')

if __name__ == '__main__':
    validator = OSWValidation(zipfile_path=VALID_ZIP_FILE)
    is_valid = validator.validate()
    if not is_valid:
        print(validator.error)