import os
import json
import jsonschema
from typing import Dict, Any
from .zipfile_handler import ZipFileHandler
from .extracted_data_validator import ExtractedDataValidator

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), 'schema')


class OSWValidation:
    schema_dir = os.path.join(SCHEMA_PATH, 'opensidewalks.schema.json')

    def __init__(self, zipfile_path: str, schema_file_path=None):
        self.zipfile_path = zipfile_path
        self.extracted_dir = None
        if schema_file_path is None:
            self.schema = self.load_osw_schema(OSWValidation.schema_dir)
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



    def validate(self) -> bool:
        self.error = None

        # Extract the zipfile
        zip_handler = ZipFileHandler(self.zipfile_path)
        self.extracted_dir = zip_handler.extract_zip()

        if not self.extracted_dir:
            self.error = zip_handler.error
            return False

        # Validate the folder structure
        validator = ExtractedDataValidator(self.extracted_dir)
        if not validator.is_valid():
            self.error = validator.error
            return False

        try:
            for file in validator.files:
                file_path = os.path.join(file)
                filename = os.path.basename(file_path)
                is_valid = self.validate_osw_errors(self.load_osw_file(file_path))
                # print(f'{filename} validation result: {is_valid}')

                if not is_valid:
                    zip_handler.remove_extracted_files()
                    return False
            zip_handler.remove_extracted_files()
            return True
        except Exception as e:
            zip_handler.remove_extracted_files()
            self.error = f'Unable to validate: {e}'
            return False



    def load_osw_file(self, graph_geojson_path: str) -> Dict[str, Any]:
        '''Load OSW Data'''

        with open(graph_geojson_path, 'r') as file:
            data = json.load(file)
        return data

    def validate_osw_errors(self, geojson_data: Dict[str, Any]) -> bool:
        '''Validate OSW Data against the schema and process all errors'''
        validator = jsonschema.Draft7Validator(self.schema)
        errors = validator.iter_errors(geojson_data)

        error_count = 0
        for error in errors:
            error_count += 1
            self.error = error

        return error_count == 0
