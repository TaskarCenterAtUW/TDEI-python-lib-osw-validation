import unittest
import os
import tempfile
import shutil
from unittest.mock import patch
from src.python_osw_validation.extracted_data_validator import ExtractedDataValidator
from src.python_osw_validation.extracted_data_validator import ALLOWED_OSW_03_FILENAMES


class TestExtractedDataValidator(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for testing
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        # Remove the temporary directory and its contents
        shutil.rmtree(self.test_dir)

    def create_files(self, files):
        for file in files:
            full_path = os.path.join(self.test_dir, file)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w') as f:
                f.write('Test content')

    def test_valid_data_at_root(self):
        # Test when required files are at the root level
        validator = ExtractedDataValidator(self.test_dir)
        self.create_files(['opensidewalks.nodes.geojson', 'opensidewalks.edges.geojson', 'opensidewalks.points.geojson'])
        self.assertTrue(validator.is_valid())

    def test_valid_data_inside_folder(self):
        # Test when required files are inside a folder
        validator = ExtractedDataValidator(self.test_dir)
        os.makedirs(os.path.join(self.test_dir, 'abc'))
        self.create_files(['abc/opensidewalks.nodes.geojson', 'abc/opensidewalks.edges.geojson'])
        self.assertTrue(validator.is_valid())

    def test_duplicate_files(self):
        # Test when there are duplicate files
        validator = ExtractedDataValidator(self.test_dir)
        self.create_files(['abc/opensidewalks.nodes.geojson', 'opensidewalks.nodes.geojson'])
        self.assertFalse(validator.is_valid())
        self.assertEqual(validator.error, 'Multiple .geojson files of the same type found: nodes.')

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

    def test_valid_subset_of_allowed_files(self):
        # Dataset may contain any subset of the 6 allowed files
        validator = ExtractedDataValidator(self.test_dir)
        self.create_files(['opensidewalks.nodes.geojson'])
        self.assertTrue(validator.is_valid())
        self.assertEqual(len(validator.files), 1)

    def test_non_standard_filenames_raise_error(self):
        validator = ExtractedDataValidator(self.test_dir)
        self.create_files(['custom.nodes.geojson', 'opensidewalks.nodes.geojson'])
        self.assertFalse(validator.is_valid())
        allowed_fmt = ", ".join(ALLOWED_OSW_03_FILENAMES)
        self.assertEqual(validator.error, f'Dataset contains non-standard file names. The only allowed file names are {{{allowed_fmt}}}')

    def test_missing_required_files_detected(self):
        required = {
            "nodes": {"required": True, "geometry": "Point"},
            "edges": {"required": True, "geometry": "LineString"},
        }
        with patch('src.python_osw_validation.extracted_data_validator.OSW_DATASET_FILES', required):
            validator = ExtractedDataValidator(self.test_dir)
            # only edges present → nodes missing
            self.create_files(['city.edges.geojson'])
            self.assertFalse(validator.is_valid())
            self.assertEqual(validator.error, 'Missing required .geojson files: nodes.')

    def test_duplicate_required_files_detected(self):
        required = {
            "nodes": {"required": True, "geometry": "Point"},
            "edges": {"required": True, "geometry": "LineString"},
        }
        with patch('src.python_osw_validation.extracted_data_validator.OSW_DATASET_FILES', required):
            validator = ExtractedDataValidator(self.test_dir)
            self.create_files(['a.nodes.geojson', 'b.nodes.geojson', 'city.edges.geojson'])
            self.assertFalse(validator.is_valid())
            self.assertEqual(validator.error, 'Multiple .geojson files of the same type found: nodes.')

    def test_unsupported_files_are_rejected(self):
        validator = ExtractedDataValidator(self.test_dir)
        self.create_files(['a.nodes.geojson', 'something_else.geojson'])
        self.assertFalse(validator.is_valid())
        self.assertEqual(
            validator.error,
            'Unsupported .geojson files present: something_else.geojson. '
            'Allowed file types are {edges, nodes, points, lines, zones, polygons}'
        )


if __name__ == '__main__':
    unittest.main()
