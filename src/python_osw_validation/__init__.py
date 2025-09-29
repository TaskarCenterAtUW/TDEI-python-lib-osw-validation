import os
import gc
import json
import traceback
from typing import Dict, Any, Optional, List, Tuple
import geopandas as gpd
import jsonschema_rs

from .zipfile_handler import ZipFileHandler
from .extracted_data_validator import ExtractedDataValidator, OSW_DATASET_FILES
from .version import __version__
from .helpers import _feature_index_from_error, _pretty_message, _rank_for

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), 'schema')


class ValidationResult:
    """Container for validation outcome.

    * `errors`: high-level, human-readable strings (legacy behavior).
    * `issues`: per-feature schema problems (former `fixme`), each item:
        { 'filename': str, 'feature_index': Optional[int], 'error_message': List[str] }
    """

    def __init__(self, is_valid: bool, errors: Optional[List[str]] = None,
                 issues: Optional[List[Dict[str, Any]]] = None):
        self.is_valid = is_valid
        if len(errors) == 0:
            self.errors = None
        else:
            self.errors = errors
        self.issues = issues


class OSWValidation:
    default_schema_file_path = os.path.join(SCHEMA_PATH, 'opensidewalks.schema.json')

    # per-geometry defaults
    default_point_schema = os.path.join(SCHEMA_PATH, 'Point_schema.json')
    default_line_schema = os.path.join(SCHEMA_PATH, 'Linestring_schema.json')
    default_polygon_schema = os.path.join(SCHEMA_PATH, 'Polygon_schema.json')

    def __init__(
            self,
            zipfile_path: str,
            schema_file_path=None,
            point_schema_path: Optional[str] = None,
            line_schema_path: Optional[str] = None,
            polygon_schema_path: Optional[str] = None,
    ):
        self.zipfile_path = zipfile_path
        self.extracted_dir: Optional[str] = None
        self.errors: List[str] = []
        # per-feature schema issues (formerly `fixme`)
        self.issues: List[Dict[str, Any]] = []

        # Legacy single schema (if set, used for all)
        self.schema_file_path = schema_file_path  # may be None

        # Per-geometry schemas (with defaults)
        self.point_schema_path = point_schema_path or self.default_point_schema
        self.line_schema_path = line_schema_path or self.default_line_schema
        self.polygon_schema_path = polygon_schema_path or self.default_polygon_schema

    # ----------------------------
    # Utilities & helpers
    # ----------------------------
    def log_errors(self, message: str, filename: Optional[str] = None, feature_index: Optional[int] = None):
        """Helper to log errors in a consistent format."""
        self.errors.append(message)
        self.issues.append({
            'filename': filename,
            'feature_index': feature_index,
            'error_message': message,
        })

    # add this small helper inside OSWValidation (near other helpers)
    def _get_colset(self, gdf: Optional[gpd.GeoDataFrame], col: str, filekey: str) -> set:
        """Return set of a column if present; else log and return empty set."""
        if gdf is None:
            return set()
        if col not in gdf.columns:
            self.log_errors(f"Missing required column '{col}' in {filekey}.", filekey, None)
            return set()
        try:
            return set(gdf[col].dropna())
        except Exception:
            # If non-hashable entries sneak in, coerce to str to keep moving
            try:
                return set(map(str, gdf[col].dropna()))
            except Exception:
                self.log_errors(f"Could not create set for column '{col}' in {filekey}.", filekey, None)
                return set()

    # ----------------------------
    # Schema selection
    # ----------------------------

    def load_osw_schema(self, schema_path: str) -> Dict[str, Any]:
        """Load OSW Schema"""
        try:
            with open(schema_path, 'r') as file:
                return json.load(file)
        except Exception as e:
            self.log_errors(
                message=f'Invalid or missing schema file: {e}',
                filename=schema_path,
                feature_index=None
            )
            raise Exception(f'Invalid or missing schema file: {e}')

    def are_ids_unique(self, gdf):
        """Check for duplicate values in the _id field"""
        duplicates = gdf[gdf.duplicated('_id', keep=False)]['_id'].unique()
        is_valid = len(duplicates) == 0
        return is_valid, list(duplicates)

    def pick_schema_for_file(self, file_path: str, geojson_data: Dict[str, Any]) -> str:
        if self.schema_file_path:
            return self.schema_file_path
        try:
            features = geojson_data.get('features', [])
            if features:
                gtype = (features[0].get('geometry') or {}).get('type')
                if gtype == 'Point':
                    return self.point_schema_path
                if gtype == 'LineString':
                    return self.line_schema_path
                if gtype == 'Polygon':
                    return self.polygon_schema_path
        except Exception:
            pass
        lower = os.path.basename(file_path).lower()
        if 'node' in lower or 'point' in lower:
            return self.point_schema_path
        if 'edge' in lower or 'line' in lower:
            return self.line_schema_path
        if 'zone' in lower or 'polygon' in lower or 'area' in lower:
            return self.polygon_schema_path
        return self.line_schema_path

    # ----------------------------
    # Core validation entrypoint
    # ----------------------------
    def validate(self, max_errors=20) -> ValidationResult:
        zip_handler = None
        OSW_DATASET: Dict[str, Optional[gpd.GeoDataFrame]] = {}
        validator = None
        try:
            # Extract the zipfile
            zip_handler = ZipFileHandler(self.zipfile_path)
            self.extracted_dir = zip_handler.extract_zip()

            if not self.extracted_dir:
                self.log_errors(
                    message=zip_handler.error,
                    filename=self.zipfile_path,
                    feature_index=None
                )
                return ValidationResult(False, self.errors, self.issues)

            # Validate the folder structure
            validator = ExtractedDataValidator(self.extracted_dir)
            if not validator.is_valid():
                self.log_errors(
                    message=validator.error,
                    filename=self.extracted_dir,
                    feature_index=None
                )
                return ValidationResult(False, self.errors, self.issues)

            # Per-file schema validation → populate self.issues (fixme-like)
            for file in validator.files:
                file_path = os.path.join(file)
                if not self.validate_osw_errors(file_path=str(file_path), max_errors=max_errors):
                    # mirror legacy behavior: stop early when we hit the cap
                    break

            if self.errors:
                return ValidationResult(False, self.errors, self.issues)

            # Load GeoDataFrames for integrity checks
            for file in validator.files:
                file_path = os.path.join(file)
                osw_file = next((osw_key for osw_key in OSW_DATASET_FILES.keys()
                                 if osw_key in os.path.basename(file_path)), '')
                try:
                    gdf = gpd.read_file(file_path)
                except Exception as e:
                    self.log_errors(
                        message=f"Failed to read '{os.path.basename(file_path)}' as GeoJSON: {e}",
                        filename=os.path.basename(file_path),
                        feature_index=None
                    )
                    gdf = None
                if osw_file:
                    OSW_DATASET[osw_file] = gdf

            # Are all id's unique in each file?
            for osw_file, gdf in OSW_DATASET.items():
                if gdf is None:
                    continue
                is_valid, duplicates = self.are_ids_unique(gdf)
                if not is_valid:
                    total_duplicates = len(duplicates)
                    displayed = ', '.join(map(str, duplicates[:max_errors]))
                    if total_duplicates > max_errors:
                        message = (f"Duplicate _id's found in {osw_file}: showing first {max_errors} "
                                   f"of {total_duplicates} duplicates: {displayed}")
                    else:
                        message = f"Duplicate _id's found in {osw_file}: {displayed}"
                    self.log_errors(
                        message=message,
                        filename=osw_file,
                        feature_index=None
                    )

            # Create sets of node id's and foreign keys to be used in validation
            nodes_df = OSW_DATASET.get('nodes')
            edges_df = OSW_DATASET.get('edges')
            zones_df = OSW_DATASET.get('zones')

            node_ids = self._get_colset(nodes_df, '_id', 'nodes') if nodes_df is not None else set()
            node_ids_edges_u = self._get_colset(edges_df, '_u_id', 'edges') if edges_df is not None else set()
            node_ids_edges_v = self._get_colset(edges_df, '_v_id', 'edges') if edges_df is not None else set()

            # zones: _w_id is list-like per feature → flatten safely
            if zones_df is not None:
                if '_w_id' in zones_df.columns:
                    vals = zones_df['_w_id'].dropna().tolist()
                    node_ids_zones_w = set(
                        item
                        for sub in vals
                        for item in (sub if isinstance(sub, (list, tuple)) else [sub])
                    )
                else:
                    self.log_errors("Missing required column '_w_id' in zones.", 'zones', None)
                    node_ids_zones_w = set()
            else:
                node_ids_zones_w = set()

            # Cross-file integrity checks (only when we have the prerequisite sets)
            if node_ids and node_ids_edges_u:
                unmatched = node_ids_edges_u - node_ids
                if unmatched:
                    unmatched_list = list(unmatched)
                    num_unmatched = len(unmatched_list)
                    limit = min(num_unmatched, max_errors)
                    displayed_unmatched = ', '.join(map(str, unmatched_list[:limit]))
                    self.log_errors(
                        message=(f"All _u_id's in edges should be part of _id's mentioned in nodes. "
                                 f"Showing {max_errors if num_unmatched > max_errors else 'all'} out of {num_unmatched} "
                                 f"unmatched _u_id's: {displayed_unmatched}"),
                        filename='All',
                        feature_index=None
                    )

            if node_ids and node_ids_edges_v:
                unmatched = node_ids_edges_v - node_ids
                if unmatched:
                    unmatched_list = list(unmatched)
                    num_unmatched = len(unmatched_list)
                    limit = min(num_unmatched, max_errors)
                    displayed_unmatched = ', '.join(map(str, unmatched_list[:limit]))
                    self.log_errors(
                        message=(f"All _v_id's in edges should be part of _id's mentioned in nodes. "
                                 f"Showing {max_errors if num_unmatched > max_errors else 'all'} out of {num_unmatched} "
                                 f"unmatched _v_id's: {displayed_unmatched}"),
                        filename='All',
                        feature_index=None
                    )

            if node_ids and node_ids_zones_w:
                unmatched = node_ids_zones_w - node_ids
                if unmatched:
                    unmatched_list = list(unmatched)
                    num_unmatched = len(unmatched_list)
                    limit = min(num_unmatched, max_errors)
                    displayed_unmatched = ', '.join(map(str, unmatched_list[:limit]))
                    self.log_errors(
                        message=(f"All _w_id's in zones should be part of _id's mentioned in nodes. "
                                 f"Showing {max_errors if num_unmatched > max_errors else 'all'} out of {num_unmatched} "
                                 f"unmatched _w_id's: {displayed_unmatched}"),
                        filename='All',
                        feature_index=None
                    )

            # Geometry validation: check geometry type and SFA validity
            for osw_file, gdf in OSW_DATASET.items():
                if gdf is None:
                    continue
                expected_geom = OSW_DATASET_FILES.get(osw_file, {}).get('geometry')
                if expected_geom:
                    invalid_geojson = gdf[
                        (gdf.geometry.type != expected_geom) | (gdf.is_valid == False)
                        ]
                else:
                    invalid_geojson = gdf[gdf.is_valid == False]

                if len(invalid_geojson) > 0:
                    # Extract IDs if present, else fallback to index
                    ids_series = invalid_geojson['_id'] if '_id' in invalid_geojson.columns else invalid_geojson.index
                    invalid_ids = list(set(ids_series))
                    num_invalid = len(invalid_ids)
                    limit = min(num_invalid, max_errors)
                    displayed_invalid = ', '.join(map(str, invalid_ids[:limit]))
                    self.log_errors(
                        message=(f"Showing {max_errors if num_invalid > max_errors else 'all'} out of {num_invalid} "
                                 f"invalid {osw_file} geometries, id's of invalid geometries: {displayed_invalid}"),
                        filename='All',
                        feature_index=None
                    )

            # Validate OSW external extensions
            for file in validator.externalExtensions:
                file_path = os.path.join(file)
                file_name = os.path.basename(file)
                try:
                    extensionFile = gpd.read_file(file_path)
                except Exception as e:
                    self.log_errors(
                        message=f"Failed to read extension '{file_name}' as GeoJSON: {e}",
                        filename=file_name,
                        feature_index=None
                    )
                    continue

                invalid_geojson = extensionFile[extensionFile.is_valid == False]
                if len(invalid_geojson) > 0:
                    try:
                        invalid_ids = list(set(invalid_geojson.get('_id', invalid_geojson.index)))
                        num_invalid = len(invalid_ids)
                        limit = min(num_invalid, max_errors)
                        displayed_invalid = ', '.join(map(str, invalid_ids[:limit]))
                        self.log_errors(
                            message=(f"Invalid geometries found in extension file `{file_name}`. "
                                     f"Showing {max_errors if num_invalid > max_errors else 'all'} of {num_invalid} "
                                     f"invalid geometry IDs: {displayed_invalid}"),
                            filename=file_name,
                            feature_index=None
                        )
                    except Exception as e:
                        self.log_errors(
                            message=f"Invalid features found in `{file_name}`, but failed to extract IDs: {e}",
                            filename=file_name,
                            feature_index=None
                        )

                # Optional: Test serializability of extension file
                try:
                    for _, row in extensionFile.drop(columns='geometry').iterrows():
                        json.dumps(row.to_dict())
                except Exception as e:
                    self.log_errors(
                        message=f"Extension file `{file_name}` has non-serializable properties: {e}",
                        filename=file_name,
                        feature_index=None
                    )
                    break

            if self.errors:
                return ValidationResult(False, self.errors, self.issues)
            else:
                return ValidationResult(True, [], self.issues)

        except Exception as e:
            self.log_errors(
                message=f'Unable to validate: {e}',
                filename=None,
                feature_index=None
            )
            traceback.print_exc()
            return ValidationResult(False, self.errors, self.issues)
        finally:
            # Cleanup extracted files
            try:
                del OSW_DATASET
            except Exception:
                pass
            if zip_handler:
                zip_handler.remove_extracted_files()

            # Force garbage collection to free memory
            gc.collect()

            # Additional memory cleanup for geopandas dataframes
            if validator:
                try:
                    for osw_file in getattr(validator, 'files', []):
                        if osw_file in locals():
                            del osw_file
                except Exception:
                    pass
                del validator
            gc.collect()

    def load_osw_file(self, graph_geojson_path: str) -> Dict[str, Any]:
        try:
            with open(graph_geojson_path, 'r') as file:
                return json.load(file)
        except json.JSONDecodeError as e:
            filename = os.path.basename(graph_geojson_path)
            self.log_errors(
                message=(
                    f"Failed to parse '{filename}' as valid JSON. "
                    f"{e.msg} (line {e.lineno}, column {e.colno}, char {e.pos})."
                ),
                filename=filename,
                feature_index=None,
            )
            raise
        except OSError as e:
            filename = os.path.basename(graph_geojson_path)
            self.log_errors(
                message=f"Unable to read file '{filename}': {e.strerror or e}",
                filename=filename,
                feature_index=None,
            )
            raise

    def validate_osw_errors(self, file_path: str, max_errors: int) -> bool:
        """Validate one OSW GeoJSON against the appropriate schema (streaming).

        - Keeps legacy `self.errors` capped by `max_errors` (original behavior).
        - While streaming, tracks the *best* error per feature (ranked) and,
          before returning, pushes a single human-friendly message per feature
          into `self.issues` (like your sample: "must include one of: ...").
        """
        try:
            geojson_data = self.load_osw_file(file_path)
        except json.JSONDecodeError:
            return False
        except OSError:
            return False
        schema_path = self.pick_schema_for_file(file_path, geojson_data)
        schema = self.load_osw_schema(schema_path)
        validator = jsonschema_rs.Draft7Validator(schema)

        filename = os.path.basename(file_path)

        # Per-feature best error accumulator (streaming)
        #   feature_idx -> (rank_tuple, error_obj)
        best_by_feature: Dict[Optional[int], Tuple[tuple, Any]] = {}
        feature_order: List[Optional[int]] = []  # preserve first-seen order

        # Legacy cap
        legacy_count = 0

        # --- STREAM over errors; STOP as soon as legacy hits the cap ---
        for err in validator.iter_errors(geojson_data):
            # legacy list (for backward compatibility)
            if legacy_count < max_errors:
                self.errors.append(f'Validation error: {getattr(err, "message", "")}')
                legacy_count += 1
            else:
                # We've reached the legacy cap; stop work to match original performance
                break

            # Track the best error per feature
            fidx = _feature_index_from_error(err)
            r = _rank_for(err)
            prev = best_by_feature.get(fidx)
            if prev is None:
                best_by_feature[fidx] = (r, err)
                feature_order.append(fidx)
            else:
                if r < prev[0]:
                    best_by_feature[fidx] = (r, err)

        # Build per-feature issues (one concise message per feature) in first-seen order
        for fidx in feature_order:
            _, best_err = best_by_feature[fidx]
            pretty = _pretty_message(best_err, schema)
            self.issues.append({
                "filename": filename,
                "feature_index": fidx if fidx is not None else -1,
                "error_message": [pretty],
            })

        # Mirror original boolean behavior: False when we exactly hit the cap
        return len(self.errors) < max_errors
