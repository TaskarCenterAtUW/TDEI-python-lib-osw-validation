import unittest
import os
import tempfile
import shutil
from src.python_osw_validation.extracted_data_validator import ExtractedDataValidator


class TestExtractedDataValidator(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for testing
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        # Remove the temporary directory and its contents
        shutil.rmtree(self.test_dir)

    def create_files(self, files):
        for file in files:
            with open(os.path.join(self.test_dir, file), 'w') as f:
                f.write('Test content')

    def test_valid_data_at_root(self):
        # Test when required files are at the root level
        validator = ExtractedDataValidator(self.test_dir)
        self.create_files(['a.nodes.geojson', 'a.edges.geojson', 'a.points.geojson'])
        self.assertTrue(validator.is_valid())

    def test_valid_data_inside_folder(self):
        # Test when required files are inside a folder
        validator = ExtractedDataValidator(self.test_dir)
        os.makedirs(os.path.join(self.test_dir, 'abc'))
        self.create_files(['abc/a.nodes.geojson', 'abc/a.edges.geojson', 'abc/a.points.geojson'])
        self.assertTrue(validator.is_valid())

    def test_duplicate_files(self):
        # Test when there are duplicate files
        validator = ExtractedDataValidator(self.test_dir)
        self.create_files(['a.1.nodes.geojson', 'a.2.nodes.geojson'])
        self.assertFalse(validator.is_valid())
        self.assertEqual(validator.error, 'Multiple .geojson files of the same type found: nodes.')

    def test_missing_optional_file(self):
        # Test when optional file is missing
        validator = ExtractedDataValidator(self.test_dir)
        self.create_files(['a.nodes.geojson', 'a.edges.geojson'])
        self.assertTrue(validator.is_valid())

    def test_no_geojson_files(self):
        # Test when no .geojson files are present
        validator = ExtractedDataValidator(self.test_dir)
        self.create_files(['some.txt', 'another.txt'])
        self.assertFalse(validator.is_valid())
        self.assertEqual(validator.error, 'No .geojson files found in the specified directory or its subdirectories.')

    def test_invalid_directory(self):
        # Test when the specified directory does not exist
        validator = ExtractedDataValidator('nonexistent_directory')
        self.assertFalse(validator.is_valid())
        self.assertEqual(validator.error, 'Directory does not exist.')

    def test_empty_directory(self):
        # Test when the specified directory is empty
        validator = ExtractedDataValidator(self.test_dir)
        self.assertFalse(validator.is_valid())
        self.assertEqual(validator.error, 'No .geojson files found in the specified directory or its subdirectories.')


if __name__ == '__main__':
    unittest.main()
