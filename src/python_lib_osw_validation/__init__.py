import os
import json
import jsonschema
from typing import Dict, Any, Optional
from .zipfile_handler import ZipFileHandler
from .extracted_data_validator import ExtractedDataValidator

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), 'schema')


class ValidationResult:
    def __init__(self, is_valid: bool, error: Optional[str] = None):
        self.is_valid = is_valid
        self.error = error


class OSWValidation:
    default_schema_file_path = os.path.join(SCHEMA_PATH, 'opensidewalks.schema.json')

    def __init__(self, zipfile_path: str, schema_file_path=None):
        self.zipfile_path = zipfile_path
        self.extracted_dir = None
        if schema_file_path is None:
            self.schema = self.load_osw_schema(OSWValidation.default_schema_file_path)
        else:
            self.schema = self.load_osw_schema(schema_file_path)

        self.error = None

    def load_osw_schema(self, schema_path: str) -> Dict[str, Any]:
        '''Load OSW Schema'''
        try:
            with open(schema_path, 'r') as file:
                schema = json.load(file)
            return schema
        except Exception as e:
            self.error = e
            raise Exception(f'Invalid or missing schema file: {e}')

    def validate(self) -> ValidationResult:
        try:
            # Extract the zipfile
            zip_handler = ZipFileHandler(self.zipfile_path)
            self.extracted_dir = zip_handler.extract_zip()

            if not self.extracted_dir:
                self.error = zip_handler.error
                return ValidationResult(False, self.error)

            # Validate the folder structure
            validator = ExtractedDataValidator(self.extracted_dir)
            if not validator.is_valid():
                self.error = validator.error
                return ValidationResult(False, self.error)

            for file in validator.files:
                file_path = os.path.join(file)
                is_valid = self.validate_osw_errors(self.load_osw_file(file_path))
                if not is_valid:
                    zip_handler.remove_extracted_files()
                    return ValidationResult(False, self.error)

            return ValidationResult(True, None)
        except Exception as e:
            self.error = f'Unable to validate: {e}'
            return ValidationResult(False, self.error)

    def load_osw_file(self, graph_geojson_path: str) -> Dict[str, Any]:
        '''Load OSW Data'''

        with open(graph_geojson_path, 'r') as file:
            data = json.load(file)
        return data

    def validate_osw_errors(self, geojson_data: Dict[str, Any]) -> bool:
        '''Validate OSW Data against the schema and process all errors'''
        validator = jsonschema.Draft7Validator(self.schema)
        errors = list(validator.iter_errors(geojson_data))

        if errors:
            self.error = errors[0]
            return False
        return True
