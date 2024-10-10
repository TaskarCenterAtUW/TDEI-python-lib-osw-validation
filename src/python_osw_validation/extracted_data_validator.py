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

        # Use a generator for geojson files to avoid storing all paths in memory
        geojson_files = glob.iglob(os.path.join(self.extracted_dir, '**', '*.geojson'), recursive=True)

        required_files = {key for key, value in OSW_DATASET_FILES.items() if value['required']}
        optional_files = {key for key, value in OSW_DATASET_FILES.items() if not value['required']}
        missing_files = set()
        duplicate_files = set()
        found_files = {key: [] for key in OSW_DATASET_FILES}

        for filename in geojson_files:
            base_name = os.path.basename(filename)
            for file_type in OSW_DATASET_FILES:
                if file_type in base_name:
                    found_files[file_type].append(filename)
                    break

        # Process required and optional files
        for file_type, files in found_files.items():
            file_count = len(files)
            if file_type in required_files:
                if file_count == 0:
                    missing_files.add(file_type)
                elif file_count == 1:
                    self.files.append(files[0])
                else:
                    duplicate_files.add(file_type)
            elif file_type in optional_files and file_count == 1:
                self.files.append(files[0])
            elif file_count > 1:
                duplicate_files.add(file_type)

        # Release memory after processing files
        gc.collect()

        # Check for missing or duplicate files
        if missing_files:
            self.error = f'Missing required .geojson files: {", ".join(missing_files)}.'
            return False

        if duplicate_files:
            self.error = f'Multiple .geojson files of the same type found: {", ".join(duplicate_files)}.'
            return False

        # Add OSW external extensions, GeoJSON files we know nothing about
        self.externalExtensions.extend(
            filename for file_list in found_files.values() for filename in file_list if filename not in self.files
        )

        # Release memory after collecting external extensions
        gc.collect()

        return True
