from version import version
from setuptools import setup, find_packages

with open('README.md', 'r') as fh:
    long_description = fh.read()

setup(
    name='python_osw_validation',
    version=version,
    author='Sujata Misra',
    author_email='sujatam@gaussiansolutions.com',
    description='Python library for OSW validation',
    long_description=long_description,
    project_urls={
        'Documentation': 'https://github.com/TaskarCenterAtUW/TDEI-python-lib-osw-validation/blob/main/README.md',
        'GitHub': 'https://github.com/TaskarCenterAtUW/TDEI-python-lib-osw-validation',
        'Changelog': 'https://github.com/TaskarCenterAtUW/TDEI-python-lib-osw-validation/blob/main/CHANGELOG.md'
    },
    long_description_content_type='text/markdown',
    url='https://github.com/TaskarCenterAtUW/TDEI-python-lib-osw-validation',
    install_requires=[
        'jsonschema_rs==0.26.1',
        'zipfile36==0.1.3',
        'geopandas==0.14.4'
    ],
    packages=find_packages(where='src'),
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.10',
    package_dir={'': 'src'},
    package_data={
        'python_osw_validation': ['schema/*'],
    },
)
