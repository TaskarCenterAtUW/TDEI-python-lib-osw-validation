import os
import unittest
from src.python_lib_osw_validation import OSWValidation

PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSETS_PATH = os.path.join(PARENT_DIR, 'assets')
SCHEMA_DIR = os.path.join(SRC_DIR, 'src/python_lib_osw_validation/schema')
SCHEMA_FILE_PATH = os.path.join(SCHEMA_DIR, 'opensidewalks.schema.json')
INVALID_SCHEMA_FILE_PATH = os.path.join(SCHEMA_DIR, 'opensidewalk.schema.json')


class TestOSWValidation(unittest.TestCase):

    def setUp(self):
        self.valid_zipfile = os.path.join(ASSETS_PATH, 'valid.zip')
        self.invalid_zipfile = os.path.join(ASSETS_PATH, 'invalid.zip')
        self.nodes_invalid_zipfile = os.path.join(ASSETS_PATH, 'nodes_invalid.zip')
        self.edges_invalid_zipfile = os.path.join(ASSETS_PATH, 'edges_invalid.zip')
        self.points_invalid_zipfile = os.path.join(ASSETS_PATH, 'points_invalid.zip')
        self.missing_files_zipfile = os.path.join(ASSETS_PATH, 'invalid_files.zip')
        self.schema_file_path = SCHEMA_FILE_PATH
        self.invalid_schema_file_path = INVALID_SCHEMA_FILE_PATH

    def test_valid_zipfile(self):
        validation = OSWValidation(zipfile_path=self.valid_zipfile)
        result = validation.validate()
        self.assertTrue(result.is_valid)
        self.assertIsNone(result.errors)

    def test_valid_zipfile_with_schema(self):
        validation = OSWValidation(zipfile_path=self.valid_zipfile, schema_file_path=self.schema_file_path)
        result = validation.validate()
        self.assertTrue(result.is_valid)
        self.assertIsNone(result.errors)

    def test_valid_zipfile_with_invalid_schema(self):

        validation = OSWValidation(zipfile_path=self.valid_zipfile, schema_file_path=self.invalid_schema_file_path)
        result = validation.validate()
        self.assertTrue(len(result.errors) > 0)

    def test_invalid_zipfile(self):
        validation = OSWValidation(zipfile_path=self.invalid_zipfile)
        result = validation.validate()
        self.assertFalse(result.is_valid)
        self.assertIsNotNone(result.errors)

    def test_invalid_zipfile_with_schema(self):
        validation = OSWValidation(zipfile_path=self.invalid_zipfile, schema_file_path=self.schema_file_path)
        result = validation.validate()
        self.assertFalse(result.is_valid)
        self.assertIsNotNone(result.errors)

    def test_invalid_zipfile_with_invalid_schema(self):
        validation = OSWValidation(zipfile_path=self.invalid_zipfile,
                                       schema_file_path=self.invalid_schema_file_path)
        result = validation.validate()
        self.assertTrue(len(result.errors) > 0)

    def test_nodes_invalid_zipfile(self):
        validation = OSWValidation(zipfile_path=self.nodes_invalid_zipfile)
        result = validation.validate()
        self.assertFalse(result.is_valid)
        self.assertIsNotNone(result.errors)

    def test_nodes_invalid_zipfile_with_schema(self):
        validation = OSWValidation(zipfile_path=self.nodes_invalid_zipfile, schema_file_path=self.schema_file_path)
        result = validation.validate()
        self.assertFalse(result.is_valid)
        self.assertIsNotNone(result.errors)

    def test_nodes_invalid_zipfile_with_invalid_schema(self):
        validation = OSWValidation(zipfile_path=self.nodes_invalid_zipfile,
                                   schema_file_path=self.invalid_schema_file_path)
        result = validation.validate()
        self.assertTrue(len(result.errors) > 0)

    def test_edges_invalid_zipfile(self):
        validation = OSWValidation(zipfile_path=self.edges_invalid_zipfile)
        result = validation.validate()
        self.assertFalse(result.is_valid)
        self.assertIsNotNone(result.errors)

    def test_edges_invalid_zipfile_with_schema(self):
        validation = OSWValidation(zipfile_path=self.edges_invalid_zipfile, schema_file_path=self.schema_file_path)
        result = validation.validate()
        self.assertFalse(result.is_valid)
        self.assertIsNotNone(result.errors)

    def test_edges_invalid_zipfile_with_invalid_schema(self):
        validation = OSWValidation(zipfile_path=self.edges_invalid_zipfile,
                                   schema_file_path=self.invalid_schema_file_path)
        result = validation.validate()
        self.assertTrue(len(result.errors) > 0)

    def test_points_invalid_zipfile(self):
        validation = OSWValidation(zipfile_path=self.points_invalid_zipfile)
        result = validation.validate()
        self.assertFalse(result.is_valid)
        self.assertIsNotNone(result.errors)

    def test_points_invalid_zipfile_with_schema(self):
        validation = OSWValidation(zipfile_path=self.points_invalid_zipfile, schema_file_path=self.schema_file_path)
        result = validation.validate()
        self.assertFalse(result.is_valid)
        self.assertIsNotNone(result.errors)

    def test_points_invalid_zipfile_with_invalid_schema(self):
        validation = OSWValidation(zipfile_path=self.points_invalid_zipfile,
                                   schema_file_path=self.invalid_schema_file_path)
        result = validation.validate()
        self.assertTrue(len(result.errors) > 0)

    def test_missing_files_inside_zipfile(self):
        validation = OSWValidation(zipfile_path=self.missing_files_zipfile)
        result = validation.validate()
        self.assertFalse(result.is_valid)
        self.assertIsNotNone(result.errors)

    def test_missing_files_inside_zipfile_with_schema(self):
        validation = OSWValidation(zipfile_path=self.missing_files_zipfile, schema_file_path=self.schema_file_path)
        result = validation.validate()
        self.assertFalse(result.is_valid)
        self.assertIsNotNone(result.errors)

    def test_missing_files_inside_zipfile_with_invalid_schema(self):
        validation = OSWValidation(zipfile_path=self.missing_files_zipfile,
                                   schema_file_path=self.invalid_schema_file_path)
        result = validation.validate()
        self.assertTrue(len(result.errors) > 0)


if __name__ == '__main__':
    unittest.main()
