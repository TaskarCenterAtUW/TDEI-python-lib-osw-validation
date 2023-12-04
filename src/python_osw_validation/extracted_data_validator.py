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
        if len(geojson_files) < 2:
            self.error = 'There are not enough .geojson files in the folder.'
            return False

        edges_present = False
        nodes_present = False
        for filename in geojson_files:
            base_name = os.path.basename(filename)
            if 'edges' in base_name and base_name.endswith('.geojson'):
                self.files.append(filename)
                edges_present = True
            elif 'nodes' in base_name and base_name.endswith('.geojson'):
                self.files.append(filename)
                nodes_present = True
            elif 'points' in base_name and base_name.endswith('.geojson'):
                self.files.append(filename)

        if not edges_present or not nodes_present:
            self.error = 'Missing one or more required .geojson files.'
            return False

        return True
