import os
import gc
import json
import jsonschema_rs
import geopandas as gpd
from typing import Dict, Any, Optional, List
from .zipfile_handler import ZipFileHandler
from .extracted_data_validator import ExtractedDataValidator, OSW_DATASET_FILES
from .version import __version__

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
        """Load OSW Schema"""
        try:
            with open(schema_path, 'r') as file:
                return json.load(file)
        except Exception as e:
            self.errors.append(f'Invalid or missing schema file: {e}')
            raise Exception(f'Invalid or missing schema file: {e}')

    def are_ids_unique(self, gdf):
        """Check for duplicate values in the _id field"""
        duplicates = gdf[gdf.duplicated('_id', keep=False)]['_id'].unique()
        is_valid = len(duplicates) == 0
        return is_valid, list(duplicates)

    def validate(self, max_errors=20) -> ValidationResult:
        zip_handler = None
        OSW_DATASET = {}
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

            # Validate schema for each file
            for file in validator.files:
                file_path = os.path.join(file)
                if not self.validate_osw_errors(file_path=str(file_path), max_errors=max_errors):
                    break

            if self.errors:
                return ValidationResult(False, self.errors)

            # Validate data integrity, freeing up memory after processing each file
            for file in validator.files:
                file_path = os.path.join(file)
                osw_file = next(
                    (osw_file_any for osw_file_any in OSW_DATASET_FILES.keys() if osw_file_any in file_path), ''
                )
                OSW_DATASET[osw_file] = gpd.read_file(file_path)

                # Validate uniqueness of _id fields in each file
                is_valid, duplicates = self.are_ids_unique(OSW_DATASET[osw_file])
                if not is_valid:
                    self.errors.append(f"Duplicate _id's found in {osw_file} : {duplicates}")

                # Geometry validation
                invalid_geojson = OSW_DATASET[osw_file][
                    (OSW_DATASET[osw_file].geometry.type != OSW_DATASET_FILES[osw_file]['geometry']) |
                    (~OSW_DATASET[osw_file].is_valid)
                    ]
                if len(invalid_geojson) > 0:
                    self.errors.append(f"Invalid {osw_file} geometries: {invalid_geojson['_id'].tolist()}")
                del invalid_geojson  # Release memory after validation of each file

                # Delete the GeoDataFrame for this file after processing
                del OSW_DATASET[osw_file]
                gc.collect()  # Ensure memory is freed

            # Validate OSW external extensions and free memory
            for file in validator.externalExtensions:
                file_path = os.path.join(file)
                extension_file = gpd.read_file(file_path)
                invalid_geojson = extension_file[~extension_file.is_valid]
                if len(invalid_geojson) > 0:
                    self.errors.append(f"Invalid geometries in {file}: {invalid_geojson['_id'].tolist()}")
                del extension_file, invalid_geojson  # Free memory after processing each extension
                gc.collect()

            if self.errors:
                return ValidationResult(False, self.errors)
            else:
                return ValidationResult(True)

        except Exception as e:
            self.errors.append(f'Unable to validate: {e}')
            return ValidationResult(False, self.errors)

        finally:
            del OSW_DATASET  # Release memory from the OSW_DATASET GeoDataFrames
            if zip_handler:
                zip_handler.remove_extracted_files()
            gc.collect()  # Ensure all unused memory is released

    def load_osw_file(self, graph_geojson_path: str) -> Dict[str, Any]:
        """Load OSW Data"""
        with open(graph_geojson_path, 'r') as file:
            return json.load(file)

    def validate_osw_errors(self, file_path: str, max_errors: int) -> bool:
        """Validate OSW Data against the schema and process all errors"""
        geojson_data = self.load_osw_file(file_path)
        validator = jsonschema_rs.Draft7Validator(self.load_osw_schema(self.schema_file_path))

        error_count = 0
        for error in validator.iter_errors(geojson_data):
            if error_count < max_errors:
                self.errors.append(f'Validation error: {error.message}')
                error_count += 1
            else:
                break

        # If we've hit the max_errors, release memory associated with errors
        if len(self.errors) >= max_errors:
            del self.errors[:]  # Clear the error list to free up memory
            gc.collect()

        return len(self.errors) < max_errors
