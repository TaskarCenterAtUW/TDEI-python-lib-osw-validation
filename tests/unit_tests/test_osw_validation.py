import os
import unittest
from src.python_lib_osw_validation import OSWValidation

PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_PATH = os.path.join(PARENT_DIR, 'assets')


class TestOSWValidation(unittest.TestCase):

    def setUp(self):
        self.valid_zipfile = os.path.join(ASSETS_PATH, 'valid.zip')
        self.invalid_zipfile = os.path.join(ASSETS_PATH, 'invalid.zip')
        self.nodes_invalid_zipfile = os.path.join(ASSETS_PATH, 'nodes_invalid.zip')
        self.edges_invalid_zipfile = os.path.join(ASSETS_PATH, 'edges_invalid.zip')
        self.points_invalid_zipfile = os.path.join(ASSETS_PATH, 'points_invalid.zip')
        self.missing_files_zipfile = os.path.join(ASSETS_PATH, 'invalid_files.zip')

    def test_valid_zipfile(self):
        validation = OSWValidation(self.valid_zipfile)
        result = validation.validate()
        self.assertTrue(result)
        self.assertIsNone(validation.error)

    def test_invalid_zipfile(self):
        validation = OSWValidation(self.invalid_zipfile)
        result = validation.validate()
        self.assertFalse(result)
        self.assertIsNotNone(validation.error)

    def test_nodes_invalid_zipfile(self):
        validation = OSWValidation(self.nodes_invalid_zipfile)
        result = validation.validate()
        self.assertFalse(result)
        self.assertIsNotNone(validation.error)

    def test_edges_invalid_zipfile(self):
        validation = OSWValidation(self.edges_invalid_zipfile)
        result = validation.validate()
        self.assertFalse(result)
        self.assertIsNotNone(validation.error)

    def test_points_invalid_zipfile(self):
        validation = OSWValidation(self.points_invalid_zipfile)
        result = validation.validate()
        self.assertFalse(result)
        self.assertIsNotNone(validation.error)

    def test_missing_files_inside_zipfile(self):
        validation = OSWValidation(self.missing_files_zipfile)
        result = validation.validate()
        self.assertFalse(result)
        self.assertIsNotNone(validation.error)


if __name__ == '__main__':
    unittest.main()
