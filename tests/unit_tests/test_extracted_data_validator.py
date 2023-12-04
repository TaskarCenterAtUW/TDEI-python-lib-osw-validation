import unittest
import os
import tempfile
import shutil
from src.python_osw_validation.extracted_data_validator import ExtractedDataValidator


class TestExtractedDataValidator(unittest.TestCase):

    def setUp(self):
        self.valid_dir = tempfile.mkdtemp()
        self.invalid_empty_dir = tempfile.mkdtemp()
        self.invalid_missing_files_dir = tempfile.mkdtemp()
        self.invalid_missing_required_files_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.valid_dir)
        shutil.rmtree(self.invalid_empty_dir)
        shutil.rmtree(self.invalid_missing_files_dir)
        shutil.rmtree(self.invalid_missing_required_files_dir)

    def create_valid_directory_structure(self):
        # Create a valid directory structure with 3 geojson files
        valid_files = ['edges.geojson', 'nodes.geojson', 'points.geojson']
        for file in valid_files:
            open(os.path.join(self.valid_dir, file), 'w').close()

    def create_invalid_empty_directory(self):
        # Create an empty directory
        pass

    def create_invalid_missing_files_directory(self):
        # Create a directory with only one geojson file
        open(os.path.join(self.invalid_missing_files_dir, 'edges.geojson'), 'w').close()

    def create_invalid_missing_required_files_directory(self):
        # Create a directory with three geojson files, but not all required ones
        invalid_files = ['edges.geojson', 'invalid.geojson', 'points.geojson']
        for file in invalid_files:
            open(os.path.join(self.invalid_missing_required_files_dir, file), 'w').close()

    def test_valid_directory_structure(self):
        self.create_valid_directory_structure()
        validator = ExtractedDataValidator(self.valid_dir)
        self.assertTrue(validator.is_valid())
        self.assertEqual(len(validator.files), 3)

    def test_invalid_empty_directory(self):
        self.create_invalid_empty_directory()
        validator = ExtractedDataValidator(self.invalid_empty_dir)
        self.assertFalse(validator.is_valid())
        self.assertEqual(validator.error, 'Folder is empty or does not exist.')

    def test_invalid_missing_files_directory(self):
        self.create_invalid_missing_files_directory()
        validator = ExtractedDataValidator(self.invalid_missing_files_dir)
        self.assertFalse(validator.is_valid())
        self.assertEqual(validator.error, 'There are not enough .geojson files in the folder.')

    def test_invalid_missing_required_files_directory(self):
        self.create_invalid_missing_required_files_directory()
        validator = ExtractedDataValidator(self.invalid_missing_required_files_dir)
        self.assertFalse(validator.is_valid())
        self.assertEqual(validator.error, 'Missing one or more required .geojson files.')


if __name__ == '__main__':
    unittest.main()
