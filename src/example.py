import os
from python_lib_osw_validation import OSWValidation


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_DIR = os.path.join(CURRENT_DIR, 'schema')


if __name__ == '__main__':
    validator = OSWValidation(schema_dir=SCHEMA_DIR)
    is_valid = validator.validate()
    if is_valid is False:
        print(validator.errors)