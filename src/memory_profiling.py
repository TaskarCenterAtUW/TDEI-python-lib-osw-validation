import os
import time
import psutil
from memory_profiler import profile
from python_osw_validation import OSWValidation

PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_DIR = os.path.join(PARENT_DIR, 'src/python_osw_validation/schema')
SCHEMA_FILE_PATH = os.path.join(SCHEMA_DIR, 'opensidewalks.schema.json')
INPUT_FOLDER = os.path.join(PARENT_DIR, 'src/assets')
INPUT_FILE = os.path.join(INPUT_FOLDER, 'graph-250.zip')
JOBS = [
    # 'external_extension',
    # 'missing_identifier',
    # 'nodes_invalid',
    # 'points_invalid',
    # '_id_missing',
    # 'no_entity',
    # 'wrong_datatype',
    # 'multiple_entries',
    # 'graph-1',
    # 'graph-2',
    # 'graph-3',
    # 'graph-4',
    # 'graph-5',
    # 'graph-100',
    # 'graph-200',
    # 'graph-250',
    'valid'
]


def print_memory_usage_psutil(label=""):
    process = psutil.Process(os.getpid())
    memory_mb = process.memory_info().rss / (1024 ** 2)  # RSS in MB
    print(f'  \x1b[34m {label} Memory usage (psutil): {memory_mb:.2f} MB \x1b[0m')
    return memory_mb


def run():
    for job in JOBS:
        start_time = time.time()
        input_file = os.path.join(INPUT_FOLDER, f'{job}.zip')
        print(f'\x1b[32m Processing File: {input_file} at {start_time}... \x1b[0m')
        print_memory_usage_psutil('Initial')

        validator = OSWValidation(zipfile_path=input_file, schema_file_path=SCHEMA_FILE_PATH)
        result = validator.validate()
        print(f'  \x1b[3{"5" if result.is_valid else "1"}m Request Status: {result.is_valid} \x1b[0m')
        print(result.errors)
        print_memory_usage_psutil('Final')
        end_time = time.time()
        time_taken = end_time - start_time

        print(f'\x1b[33m Time taken: {time_taken} Seconds \x1b[0m \n')

    print_memory_usage_psutil('Initial')
    # Uncomment below line to clean up the generated files
    # f.cleanup()


if __name__ == '__main__':
    # run()
    run()
