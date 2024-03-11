import os
import glob


class ExtractedDataValidator:
    def __init__(self, extracted_dir: str):
        self.extracted_dir = extracted_dir
        self.files = []
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

        required_files = {}
        optional_files = {'nodes', 'edges', 'points', 'lines', 'zones', 'polygons'}
        for filename in geojson_files:
            base_name = os.path.basename(filename)
            for required_file in required_files:
                if required_file in base_name and base_name.endswith('.geojson'):
                    self.files.append(filename)
                    required_files.remove(required_file)
                    break
            for optional_file in optional_files:
                if optional_file in base_name and base_name.endswith('.geojson'):
                    self.files.append(filename)
                    optional_files.remove(optional_file)
                    break

        if required_files:
            self.error = f'Missing required .geojson files: {", ".join(required_files)}.'
            return False

        return True
