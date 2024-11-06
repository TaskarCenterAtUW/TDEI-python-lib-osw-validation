import unittest
import os
from unittest.mock import patch, MagicMock
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

    @patch('src.python_osw_validation.zipfile_handler.glob.glob')
    @patch('src.python_osw_validation.zipfile_handler.zipfile.ZipFile')
    def test_create_zip_success(self, mock_zipfile, mock_glob):
        zip_handler = ZipFileHandler(self.valid_zip_path)

        # Mock the glob function to return a list of files that match the pattern
        mock_glob.return_value = ['file1.txt', 'file2.txt']

        # Mock the ZipFile object
        mock_zip = MagicMock()
        mock_zipfile.return_value.__enter__.return_value = mock_zip

        # Call the create_zip function with a file pattern
        zip_path = zip_handler.create_zip(file_pattern='*.txt')

        # Check if the zip file path is returned correctly
        self.assertEqual(zip_path, os.path.abspath(self.valid_zip_path))
        self.assertIsNone(zip_handler.error)

        # Verify the correct calls with any path formatting adjustments
        mock_zip.write.assert_any_call(mock_glob.return_value[0], arcname='../../file1.txt')
        mock_zip.write.assert_any_call(mock_glob.return_value[1], arcname='../../file2.txt')

    @patch('src.python_osw_validation.zipfile_handler.zipfile.ZipFile')
    def test_create_zip_failure(self, mock_zipfile):
        zip_handler = ZipFileHandler(self.valid_zip_path)

        # Simulate an exception when creating the zip file
        mock_zipfile.side_effect = Exception('Mocked error during zip creation')

        # Call the create_zip function, expecting it to fail
        zip_path = zip_handler.create_zip(file_pattern='*.txt')

        # Verify the return value and error handling
        self.assertIsNone(zip_path)
        self.assertIn('Error creating ZIP file: Mocked error during zip creation', zip_handler.error)


if __name__ == '__main__':
    unittest.main()
