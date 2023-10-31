import os
import json
import jsonschema
from typing import Dict, Any, Optional, List
from .zipfile_handler import ZipFileHandler
from .extracted_data_validator import ExtractedDataValidator

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), 'schema')


class ValidationResult:
    def __init__(self, is_valid: bool, errors: Optional[List[str]] = None):
        self.is_valid = is_valid
        self.errors = errors


class OSWValidation:
    default_schema_file_path = os.path.join(SCHEMA_PATH, 'opensidewalks.schema.json')

    def __init__(self, zipfile_path: str, schema_file_path=None):
        self.zipfile_path = zipfile_path
        self.extracted_dir = None
        self.errors = []
        if schema_file_path is None:
            self.schema_file_path = OSWValidation.default_schema_file_path
        else:
            self.schema_file_path = schema_file_path

    def load_osw_schema(self, schema_path: str) -> Dict[str, Any]:
        '''Load OSW Schema'''
        try:
            with open(schema_path, 'r') as file:
                return json.load(file)
        except Exception as e:
            self.errors.append(f'Invalid or missing schema file: {e}')
            raise Exception(f'Invalid or missing schema file: {e}')

    def validate(self) -> ValidationResult:
        try:
            # Extract the zipfile
            zip_handler = ZipFileHandler(self.zipfile_path)
            self.extracted_dir = zip_handler.extract_zip()

            if not self.extracted_dir:
                self.errors.append(zip_handler.error)
                return ValidationResult(False, self.errors)

            # Validate the folder structure
            validator = ExtractedDataValidator(self.extracted_dir)
            if not validator.is_valid():
                self.errors.append(validator.error)
                return ValidationResult(False, self.errors)

            for file in validator.files:
                file_path = os.path.join(file)
                is_valid = self.validate_osw_errors(self.load_osw_file(file_path))
                if not is_valid:
                    zip_handler.remove_extracted_files()
                    return ValidationResult(False, self.errors)

            return ValidationResult(True)
        except Exception as e:
            self.errors.append(f'Unable to validate: {e}')
            return ValidationResult(False, self.errors)

    def load_osw_file(self, graph_geojson_path: str) -> Dict[str, Any]:
        '''Load OSW Data'''
        with open(graph_geojson_path, 'r') as file:
            return json.load(file)

    def validate_osw_errors(self, geojson_data: Dict[str, Any]) -> bool:
        '''Validate OSW Data against the schema and process all errors'''
        validator = jsonschema.Draft7Validator(self.load_osw_schema(self.schema_file_path))
        errors = list(validator.iter_errors(geojson_data))

        if errors:
            for error in errors:
                self.errors.append(f'Validation error: {error.message}')
            return False
        return True
