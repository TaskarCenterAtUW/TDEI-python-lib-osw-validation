import os
import shutil
import tempfile
from typing import Optional
import zipfile36 as zipfile


class ZipFileHandler:
    def __init__(self, zip_file_path: str):
        self.zip_file_path = zip_file_path
        self.extracted_dir = None
        self.error = None

    def create_temp_dir(self) -> str:
        # Create a temporary directory for extracting files
        self.extracted_dir = tempfile.mkdtemp()
        return os.path.abspath(self.extracted_dir)

    def extract_zip(self) -> Optional[str]:
        try:
            if not self.extracted_dir:
                self.create_temp_dir()

            with zipfile.ZipFile(self.zip_file_path, "r") as zip_ref:
                zip_ref.extractall(self.extracted_dir)

            first_item = zip_ref.namelist()[0]

            return f'{self.extracted_dir}/{first_item}'
        except Exception as e:
            self.error = f'Error extracting ZIP file: {e}'

    def remove_extracted_files(self) -> None:
        if self.extracted_dir and os.path.exists(self.extracted_dir):
            shutil.rmtree(self.extracted_dir)
            self.extracted_dir = None
