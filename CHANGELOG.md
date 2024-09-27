# Change log

### 0.2.6
- Add garbage collection to free up memory after validation


### 0.2.5
- Updated geopandas package


### 0.2.3
- Performance improvement if there are any errors


### 0.2.2
- Added functionality to get the specific number of errors
  ```
  validator = OSWValidation(zipfile_path=<ZIP_FILE_PATH>)
  result = validator.validate() // will return only first 20 errors by default
  result = validator.validate(max_errors=10) // will return only first 10 errors
  ```

### 0.2.1
- Updated zipfile_handler
- Fixed "No .geojson files found in the specified directory or its subdirectories." issue

### 0.2.0
- Updated schema file to OSW 0.2
- Added create_zip method to ZipFileHandler
- Made all OSW files optional
- Added additional validation steps based on the OSW network properties
- Add external extensions to ExtractedDataValidator
- Validate external extensions against basic Open Geospatial Consortium (OGC) standards
- Aggregate schema errors and data integrity errors separately before returning errors to user

### 0.0.5
- Support for multi-level geojson file
- Now handles the following two folder structures when unzipped abc.zip
  1. abc\{nodes, edges, points}.geojson
  2. {nodes, edges, points}.geojson
  
### 0.0.4
- Points are not required for a valid OSW dataset

### 0.0.3
- Added schema file to package

### 0.0.2
- Updated package Unit test cases.
- Updated README file

### 0.0.1
- Initial version of python_osw_validation package.
