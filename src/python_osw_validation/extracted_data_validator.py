import os
import glob


class ExtractedDataValidator:
    def __init__(self, extracted_dir: str):
        self.extracted_dir = extracted_dir
        self.files = []
        self.error = None

    def is_valid(self) -> bool:
        if not os.path.exists(self.extracted_dir) or not os.listdir(self.extracted_dir):
            self.error = 'Folder is empty or does not exist.'
            return False

        geojson_files = glob.glob(os.path.join(self.extracted_dir, '*.geojson'))
        if len(geojson_files) < 3:
            self.error = 'There are not enough .geojson files in the folder.'
            return False

        for filename in geojson_files:
            base_name = os.path.basename(filename)
            if 'edges' in base_name and base_name.endswith('.geojson'):
                self.files.append(filename)
            elif 'nodes' in base_name and base_name.endswith('.geojson'):
                self.files.append(filename)
            elif 'points' in base_name and base_name.endswith('.geojson'):
                self.files.append(filename)

        if len(self.files) != 3:
            self.error = 'Missing one or more required .geojson files.'
            return False

        return True
