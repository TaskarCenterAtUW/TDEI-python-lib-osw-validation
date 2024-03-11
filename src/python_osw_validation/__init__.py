import os
import json
import jsonschema
from typing import Dict, Any, Optional, List
import geopandas as gpd
from .zipfile_handler import ZipFileHandler
from .extracted_data_validator import ExtractedDataValidator

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), 'schema')

OSW_dataset_files = {"edges": {
                                "required": False,
                                "geometry": "LineString"
                              },
                     "nodes": {
                                "required": False,
                                "geometry": "Point"
                              },
                     "points": {
                                "required": False,
                                "geometry": "Point"
                              },
                     "lines": {
                                "required": False,
                                "geometry": "LineString"
                              },
                     "zones": {
                                "required": False,
                                "geometry": "Polygon"
                              },
                     "polygons": {
                                "required": False,
                                "geometry": "Polygon"
                              }
                    }


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
        
    def unique_id(self, gdf):
        """Check for duplicate values in the _id field"""
        duplicates = gdf[gdf.duplicated('_id', keep=False)]['_id'].unique()
        
        is_valid = len(duplicates) == 0
        
        return is_valid, list(duplicates)

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

            # Validate data integrity
            OSW_dataset = {}
            for file in validator.files:
                file_path = os.path.join(file)
                osw_file = file_path.split('.')[-2]
                OSW_dataset[osw_file] = gpd.read_file(file_path)

            # Are all id's unique in each file? No need to check uniqueness across files yet since we do not have a global OSW ID format yet
            for osw_file in OSW_dataset:
                is_valid, duplicates = self.unique_id(OSW_dataset[osw_file])
                if not is_valid:
                    zip_handler.remove_extracted_files()
                    self.errors.append(f"Duplicate _id's found in {osw_file} : {duplicates}")
                    return ValidationResult(False, self.errors)

            # Create sets of node id's and foreign keys to be used in validation
            if "nodes" in OSW_dataset:
                node_ids = set(OSW_dataset['nodes']['_id'])
            else:
                node_ids = set()

            if "edges" in OSW_dataset:
                node_ids_edges_u = set(OSW_dataset['edges']['_u_id'])
                node_ids_edges_v = set(OSW_dataset['edges']['_v_id'])
            else:
                node_ids_edges_u = set()
                node_ids_edges_v = set()

            if "zones" in OSW_dataset:
                node_ids_zones_w = set([item for sublist in OSW_dataset['zones']['_w_id'] for item in sublist])
            else:
                node_ids_zones_w = set()

            # Do all node references in _u_id exist in nodes?
            unmatched = node_ids_edges_u - node_ids
            is_valid = len(unmatched) == 0
            if not is_valid:
                zip_handler.remove_extracted_files()
                self.errors.append(f"Foreign key constraints for edge start nodes failed, _u_id's of unmatched nodes: {unmatched}")
                return ValidationResult(False, self.errors)

            # Do all node references in _v_id exist in nodes?
            unmatched = node_ids_edges_v - node_ids
            is_valid = len(unmatched) == 0
            if not is_valid:
                zip_handler.remove_extracted_files()
                self.errors.append(f"Foreign key constraints for edge end nodes failed, _v_id's of unmatched nodes: {unmatched}")
                return ValidationResult(False, self.errors)

            # Do all node references in _w_id exist in nodes?
            unmatched = node_ids_zones_w - node_ids
            is_valid = len(unmatched) == 0
            if not is_valid:
                zip_handler.remove_extracted_files()
                self.errors.append(f"Foreign key constraints for zone nodes failed, _w_id's of unmatched nodes: {unmatched}")
                return ValidationResult(False, self.errors)
            
            # Geometry validation: check geometry type in each file and test if coordinates make a shape that is reasonable geometric shape according to the Simple Feature Access standard
            for osw_file in OSW_dataset:
                invalid_geojson = OSW_dataset[osw_file][(OSW_dataset[osw_file].geometry.type != OSW_dataset_files[osw_file]['geometry']) | (OSW_dataset[osw_file].is_valid==False)]
                is_valid = len(invalid_geojson) == 0
                if not is_valid:
                    zip_handler.remove_extracted_files()
                    self.errors.append(f"Invalid {osw_file} geometries found, id's of invalid geometries: {set(invalid_geojson['_id'])}")
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
