import os
import gc
import glob

OSW_DATASET_FILES = {
    "edges": {
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


class ExtractedDataValidator:
    def __init__(self, extracted_dir: str):
        self.extracted_dir = extracted_dir
        self.files = []
        self.externalExtensions = []
        self.error = None

    def is_valid(self) -> bool:
        # Check if the directory exists
        if not os.path.exists(self.extracted_dir):
            self.error = 'Directory does not exist.'
            return False

        # Look for required files at the root level
        geojson_files = glob.glob(os.path.join(self.extracted_dir, '*.geojson'))

        # If not found at the root, check inside folders
        if not geojson_files:
            geojson_files = glob.glob(os.path.join(self.extracted_dir, '*', '*.geojson'))

        if not geojson_files:
            self.error = 'No .geojson files found in the specified directory or its subdirectories.'
            return False

        required_files = [key for key, value in OSW_DATASET_FILES.items() if value['required']]
        optional_files = [key for key, value in OSW_DATASET_FILES.items() if not value['required']]
        missing_files = []
        duplicate_files = []
        save_filename = None  # Initialize this variable

        try:
            # Process required files
            for required_file in required_files:
                file_count = 0
                for filename in geojson_files:
                    base_name = os.path.basename(filename)
                    if required_file in base_name and base_name.endswith('.geojson'):
                        file_count += 1
                        save_filename = filename
                if file_count == 0:
                    # Missing required file
                    missing_files.append(required_file)
                elif file_count == 1:
                    self.files.append(save_filename)
                else:
                    # Duplicate file
                    duplicate_files.append(required_file)

            # Process optional files
            for optional_file in optional_files:
                file_count = 0
                for filename in geojson_files:
                    base_name = os.path.basename(filename)
                    if optional_file in base_name and base_name.endswith('.geojson'):
                        file_count += 1
                        save_filename = filename
                if file_count == 1:
                    self.files.append(save_filename)
                elif file_count > 1:
                    # Duplicate file
                    duplicate_files.append(optional_file)

            # Check for missing or duplicate files
            if missing_files:
                self.error = f'Missing required .geojson files: {", ".join(missing_files)}.'
                return False

            if duplicate_files:
                self.error = f'Multiple .geojson files of the same type found: {", ".join(duplicate_files)}.'
                return False

            # Add OSW external extensions, GeoJSON files we know nothing about
            self.externalExtensions.extend([item for item in geojson_files if item not in self.files])

        finally:
            # Cleanup large lists and call garbage collector
            del geojson_files, required_files, optional_files, missing_files, duplicate_files
            gc.collect()

        return True
