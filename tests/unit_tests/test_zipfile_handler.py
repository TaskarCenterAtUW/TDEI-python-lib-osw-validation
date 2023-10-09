import unittest
import os
from src.python_osw_validation.zipfile_handler import ZipFileHandler

PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_PATH = os.path.join(PARENT_DIR, 'assets')


class TestZipFileHandler(unittest.TestCase):

    def setUp(self):
        self.valid_zip_path = os.path.join(ASSETS_PATH, 'valid.zip')
        self.invalid_zip_path = os.path.join(ASSETS_PATH, 'invalid_path.zip')
        self.temp_dir = None

    def tearDown(self):
        if self.temp_dir and os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)

    def test_extract_valid_zip(self):
        zip_handler = ZipFileHandler(self.valid_zip_path)
        extracted_dir = zip_handler.extract_zip()
        self.assertIsNotNone(extracted_dir)
        self.assertTrue(os.path.exists(extracted_dir))
        zip_handler.remove_extracted_files()

    def test_extract_invalid_zip(self):
        zip_handler = ZipFileHandler(self.invalid_zip_path)
        extracted_dir = zip_handler.extract_zip()
        self.assertIsNone(extracted_dir)
        self.assertIsNotNone(zip_handler.error)

    def test_remove_extracted_files(self):
        zip_handler = ZipFileHandler(self.valid_zip_path)
        extracted_dir = zip_handler.extract_zip()
        self.assertIsNotNone(extracted_dir)
        self.assertTrue(os.path.exists(extracted_dir))
        zip_handler.remove_extracted_files()
        self.assertFalse(os.path.exists(extracted_dir))
        self.assertIsNone(zip_handler.extracted_dir)


if __name__ == '__main__':
    unittest.main()
