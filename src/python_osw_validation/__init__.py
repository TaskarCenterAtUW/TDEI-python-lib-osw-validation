import os
import gc
import json
import jsonschema_rs
import geopandas as gpd
from .zipfile_handler import ZipFileHandler
from typing import Dict, Any, Optional, List
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
        validator = None
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
                if not self.validate_osw_errors(file_path=str(file_path), max_errors=max_errors):
                    break

            if self.errors:
                return ValidationResult(False, self.errors)

            # Validate data integrity
            for file in validator.files:
                file_path = os.path.join(file)
                osw_file = next(
                    (osw_file_any for osw_file_any in OSW_DATASET_FILES.keys() if osw_file_any in file_path), '')
                OSW_DATASET[osw_file] = gpd.read_file(file_path)

            # Are all id's unique in each file? No need to check uniqueness across files yet since we do not have a global OSW ID format yet
            for osw_file in OSW_DATASET:
                is_valid, duplicates = self.are_ids_unique(OSW_DATASET[osw_file])
                if not is_valid:
                    self.errors.append(f"Duplicate _id's found in {osw_file} : {duplicates}")

            # Create sets of node id's and foreign keys to be used in validation
            if 'nodes' in OSW_DATASET:
                node_ids = set(OSW_DATASET['nodes']['_id'])
            else:
                node_ids = set()

            if 'edges' in OSW_DATASET:
                node_ids_edges_u = set(OSW_DATASET['edges']['_u_id'])
                node_ids_edges_v = set(OSW_DATASET['edges']['_v_id'])
            else:
                node_ids_edges_u = set()
                node_ids_edges_v = set()

            if 'zones' in OSW_DATASET:
                node_ids_zones_w = set([item for sublist in OSW_DATASET['zones']['_w_id'] for item in sublist])
            else:
                node_ids_zones_w = set()

            # Do all node references in _u_id exist in nodes?
            unmatched = node_ids_edges_u - node_ids
            is_valid = len(unmatched) == 0
            if not is_valid:
                self.errors.append(
                    f"All _u_id's in edges should be part of _id's mentioned in nodes, _u_id's not in nodes are: {unmatched}")

            # Do all node references in _v_id exist in nodes?
            unmatched = node_ids_edges_v - node_ids
            is_valid = len(unmatched) == 0
            if not is_valid:
                self.errors.append(
                    f"All _v_id's in edges should be part of _id's mentioned in nodes, _v_id's not in nodes are: {unmatched}")

            # Do all node references in _w_id exist in nodes?
            unmatched = node_ids_zones_w - node_ids
            is_valid = len(unmatched) == 0
            if not is_valid:
                self.errors.append(
                    f"All _w_id's in zones should be part of _id's mentioned in nodes, _w_id's not in nodes are: {unmatched}")

            # Geometry validation: check geometry type in each file and test if coordinates make a shape that is reasonable geometric shape according to the Simple Feature Access standard
            for osw_file in OSW_DATASET:
                invalid_geojson = OSW_DATASET[osw_file][
                    (OSW_DATASET[osw_file].geometry.type != OSW_DATASET_FILES[osw_file]['geometry']) | (
                                OSW_DATASET[osw_file].is_valid == False)]
                is_valid = len(invalid_geojson) == 0
                if not is_valid:
                    self.errors.append(
                        f"Invalid {osw_file} geometries found, id's of invalid geometries: {set(invalid_geojson['_id'])}")

            # Validate OSW external extensions
            for file in validator.externalExtensions:
                file_path = os.path.join(file)
                extensionFile = gpd.read_file(file_path)
                invalid_geojson = extensionFile[extensionFile.is_valid == False]
                is_valid = len(invalid_geojson) == 0
                if not is_valid:
                    self.errors.append(
                        f"Invalid geometries found in extension file {file}, list of invalid geometries: {invalid_geojson.to_json()}")

            if self.errors:
                return ValidationResult(False, self.errors)
            else:
                return ValidationResult(True)
        except Exception as e:
            self.errors.append(f'Unable to validate: {e}')
            return ValidationResult(False, self.errors)
        finally:
            del OSW_DATASET
            if zip_handler:
                zip_handler.remove_extracted_files()

            # Force garbage collection to free memory
            gc.collect()

            # Additional memory cleanup for geopandas dataframes
            if validator:
                for osw_file in validator.files:
                    if osw_file in locals():
                        del osw_file
                del validator
            gc.collect()

    def load_osw_file(self, graph_geojson_path: str) -> Dict[str, Any]:
        """Load OSW Data"""
        with open(graph_geojson_path, 'r') as file:
            return json.load(file)

    def validate_osw_errors(self, file_path: str, max_errors: int) -> bool:
        """Validate OSW Data against the schema and process all errors"""
        geojson_data = self.load_osw_file(file_path)
        validator = jsonschema_rs.Draft7Validator(self.load_osw_schema(self.schema_file_path))

        for error in validator.iter_errors(geojson_data):
            self.errors.append(f'Validation error: {error.message}')
            if len(self.errors) >= max_errors:
                return False

        return len(self.errors) < max_errors
