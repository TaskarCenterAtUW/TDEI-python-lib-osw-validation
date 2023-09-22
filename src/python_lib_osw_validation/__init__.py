import os
import json
import jsonschema
from pathlib import Path
from typing import Dict, Any


class OSWValidation:
    def __init__(self, schema_dir: str):
        self.schema_dir = schema_dir
        self.schema = self.load_osw_schema(Path(self.schema_dir, 'opensidewalks.schema.json'))
        self.region_id = 'wa.microsoft'

    def load_osw_schema(self, schema_path: str) -> Dict[str, Any]:
        """Load OSW Schema"""
        with open(schema_path, 'r') as file:
            schema = json.load(file)
        return schema

    def load_osw_file(self, graph_geojson_path: str) -> Dict[str, Any]:
        """Load OSW Data"""
        with open(graph_geojson_path, 'r') as file:
            data = json.load(file)
        return data

    def validate_osw_errors(self, geojson_data: Dict[str, Any]) -> bool:
        """Validate OSW Data against the schema and process all errors"""
        validator = jsonschema.Draft7Validator(self.schema)
        errors = validator.iter_errors(geojson_data)

        error_count = 0
        for error in errors:
            error_count += 1
            # Format and store in file for further review
            print(error)

        return error_count == 0

    def validate(self) -> None:
        # Validate edges
        is_valid = self.validate_osw_errors(
            self.load_osw_file(Path(self.schema_dir, f"{self.region_id}.graph.edges.OSW.geojson")))
        print(f"Edges validation result: {is_valid}")

        # Validate nodes
        is_valid = self.validate_osw_errors(
            self.load_osw_file(Path(self.schema_dir, f"{self.region_id}.graph.nodes.OSW.geojson")))
        print(f"Nodes validation result: {is_valid}")

        # Validate points
        is_valid = self.validate_osw_errors(
            self.load_osw_file(Path(self.schema_dir, f"{self.region_id}.graph.points.OSW.geojson")))
        print(f"Points validation result: {is_valid}")
