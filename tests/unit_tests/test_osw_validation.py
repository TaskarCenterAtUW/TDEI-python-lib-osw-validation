import os
import unittest
from src.python_osw_validation import OSWValidation

PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSETS_PATH = os.path.join(PARENT_DIR, 'assets')
SCHEMA_DIR = os.path.join(SRC_DIR, 'src/python_osw_validation/schema')
SCHEMA_FILE_PATH = os.path.join(SCHEMA_DIR, 'opensidewalks.schema.json')
INVALID_SCHEMA_FILE_PATH = os.path.join(SCHEMA_DIR, 'opensidewalk.schema.json')


class TestOSWValidation(unittest.TestCase):

    def setUp(self):
        self.valid_zipfile = os.path.join(ASSETS_PATH, 'valid.zip')
        self.minimal_zipfile = os.path.join(ASSETS_PATH, 'minimal.zip')
        self.invalid_zipfile = os.path.join(ASSETS_PATH, 'invalid.zip')
        self.nodes_invalid_zipfile = os.path.join(ASSETS_PATH, 'nodes_invalid.zip')
        self.edges_invalid_zipfile = os.path.join(ASSETS_PATH, 'edges_invalid.zip')
        self.points_invalid_zipfile = os.path.join(ASSETS_PATH, 'points_invalid.zip')
        self.external_extension_file_zipfile = os.path.join(ASSETS_PATH, 'external_extension.zip')
        self.id_missing_zipfile = os.path.join(ASSETS_PATH, '_id_missing.zip')
        self.extra_field_zipfile = os.path.join(ASSETS_PATH, 'extra_field.zip')
        self.invalid_geometry_zipfile = os.path.join(ASSETS_PATH, 'invalid_geometry.zip')
        self.missing_identifier_zipfile = os.path.join(ASSETS_PATH, 'missing_identifier.zip')
        self.no_entity_zipfile = os.path.join(ASSETS_PATH, 'no_entity.zip')
        self.wrong_datatypes_zipfile = os.path.join(ASSETS_PATH, 'wrong_datatype.zip')
        self.valid_zones_file = os.path.join(ASSETS_PATH, 'UW.zones.valid.zip')
        self.invalid_zones_file = os.path.join(ASSETS_PATH, 'UW.zones.invalid.zip')
        self.valid_osw_file = os.path.join(ASSETS_PATH, 'wa.bellevue.zip')
        self.invalid_v_id_file = os.path.join(ASSETS_PATH, '4151.zip')
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

    def test_minimal_zipfile(self):
        validation = OSWValidation(zipfile_path=self.minimal_zipfile)
        result = validation.validate()
        self.assertTrue(result.is_valid)
        self.assertIsNone(result.errors)

    def test_minimal_zipfile_with_schema(self):
        validation = OSWValidation(zipfile_path=self.minimal_zipfile, schema_file_path=self.schema_file_path)
        result = validation.validate()
        self.assertTrue(result.is_valid)
        self.assertIsNone(result.errors)

    def test_minimal_zipfile_with_invalid_schema(self):
        validation = OSWValidation(zipfile_path=self.minimal_zipfile, schema_file_path=self.invalid_schema_file_path)
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

    def test_invalid_zipfile_default_error_count(self):
        validation = OSWValidation(zipfile_path=self.invalid_zipfile)
        result = validation.validate()
        self.assertFalse(result.is_valid)
        self.assertIsNotNone(result.errors)
        self.assertLessEqual(len(result.errors), 20)

    def test_invalid_zipfile_should_specific_errors_counts(self):
        validation = OSWValidation(zipfile_path=self.invalid_zipfile)
        result = validation.validate(max_errors=10)
        self.assertFalse(result.is_valid)
        self.assertIsNotNone(result.errors)
        self.assertLessEqual(len(result.errors), 10)

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

    def test_external_extension_file_inside_zipfile(self):
        validation = OSWValidation(zipfile_path=self.external_extension_file_zipfile)
        result = validation.validate()
        self.assertTrue(result.is_valid)
        self.assertIsNone(result.errors)

    def test_external_extension_file_inside_zipfile_with_schema(self):
        validation = OSWValidation(zipfile_path=self.external_extension_file_zipfile,
                                   schema_file_path=self.schema_file_path)
        result = validation.validate()
        self.assertTrue(result.is_valid)
        self.assertIsNone(result.errors)

    def test_external_extension_file_inside_zipfile_with_invalid_schema(self):
        validation = OSWValidation(zipfile_path=self.external_extension_file_zipfile,
                                   schema_file_path=self.invalid_schema_file_path)
        result = validation.validate()
        self.assertTrue(result.is_valid)
        self.assertIsNone(result.errors)

    def test_id_missing_zipfile(self):
        validation = OSWValidation(zipfile_path=self.id_missing_zipfile)
        result = validation.validate()
        self.assertFalse(result.is_valid)
        self.assertIsNotNone(result.errors)

    def test_extra_field_zipfile(self):
        validation = OSWValidation(zipfile_path=self.extra_field_zipfile)
        result = validation.validate()
        self.assertFalse(result.is_valid)
        self.assertIsNotNone(result.errors)

    def test_invalid_geometry_zipfile(self):
        validation = OSWValidation(zipfile_path=self.invalid_geometry_zipfile)
        result = validation.validate()
        self.assertFalse(result.is_valid)
        self.assertIsNotNone(result.errors)

    def test_missing_identifier_zipfile(self):
        validation = OSWValidation(zipfile_path=self.missing_identifier_zipfile)
        result = validation.validate()
        self.assertFalse(result.is_valid)
        self.assertIsNotNone(result.errors)

    def test_no_entity_zipfile(self):
        validation = OSWValidation(zipfile_path=self.no_entity_zipfile)
        result = validation.validate()
        self.assertFalse(result.is_valid)
        self.assertIsNotNone(result.errors)

    def test_wrong_datatypes_zipfile(self):
        validation = OSWValidation(zipfile_path=self.wrong_datatypes_zipfile)
        result = validation.validate()
        self.assertFalse(result.is_valid)
        self.assertIsNotNone(result.errors)

    def test_valid_osw_file(self):
        validation = OSWValidation(zipfile_path=self.valid_osw_file)
        result = validation.validate()
        self.assertTrue(result.is_valid)
        self.assertIsNone(result.errors)

    def test_valid_zones_file(self):
        validation = OSWValidation(zipfile_path=self.valid_zones_file)
        result = validation.validate()
        self.assertTrue(result.is_valid)
        self.assertIsNone(result.errors)

    def test_invalid_zones_file(self):
        validation = OSWValidation(zipfile_path=self.invalid_zones_file)
        result = validation.validate()
        self.assertFalse(result.is_valid)
        self.assertIsNotNone(result.errors)

    def test_unmatched_ids_limited_to_20(self):
        validation = OSWValidation(zipfile_path=self.invalid_v_id_file)
        result = validation.validate()

        # Ensure validation fails
        self.assertFalse(result.is_valid, 'Validation should fail, but it passed.')
        self.assertTrue(result.errors, 'Validation should produce errors, but it returned none.')

        # Try to find the unmatched ID error message
        error_message = next((err for err in result.errors if 'unmatched' in err.lower()), None)

        # Ensure the error message exists
        self.assertIsNotNone(error_message, 'Expected error message for unmatched IDs not found.')

        # Extract the displayed IDs from the message
        extracted_ids = error_message.split(':')[-1].strip().split(', ')

        # Ensure only 20 IDs are displayed
        self.assertLessEqual(len(extracted_ids), 20, 'More than 20 unmatched IDs displayed in the error message.')

        # Ensure the total count is mentioned
        self.assertIn('Showing 20 out of', error_message)


if __name__ == '__main__':
    unittest.main()
