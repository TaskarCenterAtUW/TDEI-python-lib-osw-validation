import os
import gc
import json
import math
import numbers
from typing import Dict, Any, Optional, List, Tuple
import geopandas as gpd
import jsonschema_rs

from .zipfile_handler import ZipFileHandler
from .extracted_data_validator import ExtractedDataValidator, OSW_DATASET_FILES
from .version import __version__
from .helpers import (
    _add_additional_properties_hint,
    _err_kind,
    _feature_index_from_error,
    _pretty_message,
    _read_geojson_without_ext,
)

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), 'schema')
DEFAULT_DATASET_SCHEMAS = {
    "edges": os.path.join(SCHEMA_PATH, 'opensidewalks.edges.schema-0.3.json'),
    "lines": os.path.join(SCHEMA_PATH, 'opensidewalks.lines.schema-0.3.json'),
    "nodes": os.path.join(SCHEMA_PATH, 'opensidewalks.nodes.schema-0.3.json'),
    "points": os.path.join(SCHEMA_PATH, 'opensidewalks.points.schema-0.3.json'),
    "polygons": os.path.join(SCHEMA_PATH, 'opensidewalks.polygons.schema-0.3.json'),
    "zones": os.path.join(SCHEMA_PATH, 'opensidewalks.zones.schema-0.3.json'),
}


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
    default_schema_file_path_03 = os.path.join(SCHEMA_PATH, 'opensidewalks.schema-0.3.json')

    # per-geometry defaults
    default_point_schema = DEFAULT_DATASET_SCHEMAS['points']
    default_line_schema = DEFAULT_DATASET_SCHEMAS['edges']
    default_polygon_schema = DEFAULT_DATASET_SCHEMAS['zones']

    def __init__(
            self,
            zipfile_path: str,
            schema_file_path=None,
            schema_paths: Optional[Dict[str, str]] = None,
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

        # Dataset-specific schemas (override via schema_paths)
        self.dataset_schema_paths = {**DEFAULT_DATASET_SCHEMAS}
        if schema_paths:
            self.dataset_schema_paths.update({k: v for k, v in schema_paths.items() if v})

        # Per-geometry schemas (with defaults)
        self.point_schema_path = point_schema_path or self.dataset_schema_paths['points']
        self.line_schema_path = line_schema_path or self.dataset_schema_paths['edges']
        self.polygon_schema_path = polygon_schema_path or self.dataset_schema_paths['zones']

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
    # Geometry mapping helpers
    # ----------------------------

    _COORD_TOLERANCE = 1e-7  # ~1 cm at equator

    def _coords_match(self, c1: tuple, c2: tuple) -> bool:
        return abs(c1[0] - c2[0]) <= self._COORD_TOLERANCE and abs(c1[1] - c2[1]) <= self._COORD_TOLERANCE

    def _build_node_coord_map(self, nodes_df: gpd.GeoDataFrame) -> Dict[Any, tuple]:
        """Return {node_id: (lon, lat)} from a nodes GeoDataFrame."""
        coord_map: Dict[Any, tuple] = {}
        for _, row in nodes_df.iterrows():
            try:
                nid = row['_id']
            except KeyError:
                continue
            geom = row.geometry
            if nid is not None and geom is not None and geom.geom_type == 'Point':
                coord_map[nid] = (geom.x, geom.y)
        return coord_map

    def _validate_edge_geometry_mapping(
        self,
        edges_df: Optional[gpd.GeoDataFrame],
        node_coord_map: Dict[Any, tuple],
        max_errors: int,
    ) -> None:
        """Verify edge start/end coordinates match their _u_id/_v_id node geometries."""
        if edges_df is None or not node_coord_map:
            return

        has_u_id = '_u_id' in edges_df.columns
        has_v_id = '_v_id' in edges_df.columns
        if not (has_u_id or has_v_id):
            return

        for feat_idx, row in edges_df.iterrows():
            if len(self.errors) >= max_errors:
                break

            geom = row.geometry
            if geom is None or geom.geom_type != 'LineString':
                continue

            coords = list(geom.coords)
            if not coords:
                continue

            try:
                edge_id = row['_id']
            except KeyError:
                edge_id = feat_idx

            if has_u_id:
                try:
                    u_id = row['_u_id']
                except KeyError:
                    u_id = None
                if u_id is not None and u_id in node_coord_map:
                    node_coord = node_coord_map[u_id]
                    edge_start = (coords[0][0], coords[0][1])
                    if not self._coords_match(edge_start, node_coord):
                        self.log_errors(
                            message=(
                                f"edges id '{edge_id}' : "
                                f"start coordinate {edge_start} does not match "
                                f"node id '{u_id}' coordinate {node_coord} (_u_id mismatch)."
                            ),
                            filename='edges',
                            feature_index=feat_idx,
                        )

            if len(self.errors) >= max_errors:
                break

            if has_v_id:
                try:
                    v_id = row['_v_id']
                except KeyError:
                    v_id = None
                if v_id is not None and v_id in node_coord_map:
                    node_coord = node_coord_map[v_id]
                    edge_end = (coords[-1][0], coords[-1][1])
                    if not self._coords_match(edge_end, node_coord):
                        self.log_errors(
                            message=(
                                f"edges id '{edge_id}' : "
                                f"end coordinate {edge_end} does not match "
                                f"node id '{v_id}' coordinate {node_coord} (_v_id mismatch)."
                            ),
                            filename='edges',
                            feature_index=feat_idx,
                        )

    def _validate_zone_geometry_mapping(
        self,
        zones_df: Optional[gpd.GeoDataFrame],
        node_coord_map: Dict[Any, tuple],
        max_errors: int,
    ) -> None:
        """Verify each _w_id node coordinate is a vertex of the zone's polygon exterior ring."""
        if zones_df is None or not node_coord_map:
            return

        if '_w_id' not in zones_df.columns:
            return

        for feat_idx, row in zones_df.iterrows():
            if len(self.errors) >= max_errors:
                break

            geom = row.geometry
            if geom is None or geom.geom_type != 'Polygon':
                continue

            try:
                zone_id = row['_id']
            except KeyError:
                zone_id = feat_idx

            ring_coords = {(c[0], c[1]) for c in geom.exterior.coords}

            try:
                w_ids = row['_w_id']
            except KeyError:
                continue

            if w_ids is None:
                continue
            if not isinstance(w_ids, (list, tuple)):
                w_ids = [w_ids]

            for w_id in w_ids:
                if len(self.errors) >= max_errors:
                    break
                if w_id is None or w_id not in node_coord_map:
                    continue
                node_coord = node_coord_map[w_id]
                if not any(self._coords_match(node_coord, rc) for rc in ring_coords):
                    self.log_errors(
                        message=(
                            f"zones id '{zone_id}' : "
                            f"node id '{w_id}' coordinate {node_coord} is not a vertex "
                            f"of the zone polygon geometry (_w_id coordinate mismatch)."
                        ),
                        filename='zones',
                        feature_index=feat_idx,
                    )

    def _schema_key_from_text(self, text: Optional[str]) -> Optional[str]:
        """Return dataset key from exact filename suffixes only."""
        if not text:
            return None

        basename = os.path.basename(text).lower()
        stem, _ = os.path.splitext(basename)
        for key in self.dataset_schema_paths:
            if (
                    stem == key
                    or stem == f"{key}.osw"
                    or stem.endswith(f".{key}")
                    or stem.endswith(f".{key}.osw")
            ):
                return key

        return None

    def _is_nullish_value(self, value: Any) -> bool:
        if value is None:
            return True
        return isinstance(value, numbers.Real) and math.isnan(value)

    def _collect_nullish_property_paths(self, obj: Any, prefix: str = "") -> List[Tuple[str, Any]]:
        paths: List[Tuple[str, Any]] = []
        if isinstance(obj, dict):
            for key, value in obj.items():
                next_prefix = f"{prefix}.{key}" if prefix else str(key)
                paths.extend(self._collect_nullish_property_paths(value, next_prefix))
            return paths
        if isinstance(obj, list):
            for idx, value in enumerate(obj):
                next_prefix = f"{prefix}[{idx}]" if prefix else f"[{idx}]"
                paths.extend(self._collect_nullish_property_paths(value, next_prefix))
            return paths
        if self._is_nullish_value(obj):
            paths.append((prefix or "value", obj))
        return paths

    def _collect_nullish_extension_property_paths(self, props: Dict[str, Any]) -> List[Tuple[str, Any]]:
        paths: List[Tuple[str, Any]] = []
        for key, value in props.items():
            if isinstance(key, str) and key.startswith("ext:"):
                paths.extend(self._collect_nullish_property_paths(value, key))
        return paths

    def _contains_disallowed_features_for_02(self, geojson_data: Dict[str, Any]) -> set:
        """Detect Tree coverage or Custom content in legacy 0.2 datasets.

        Returns a set of reason tags, e.g. {"tree", "custom_ext", "custom_token"}.
        Empty set means no 0.2-only violations detected.
        """
        reasons = set()
        for feat in geojson_data.get("features", []):
            props = feat.get("properties") or {}
            geom = feat.get("geometry") or {}
            geom_type = geom.get("type") if isinstance(geom, dict) else None
            is_point = isinstance(geom_type, str) and geom_type.lower() == "point"

            val = props.get("natural")
            if isinstance(val, str) and val.strip().lower() in {"tree", "wood"}:
                reasons.add("tree")
            if any(k in props for k in ("leaf_cycle", "leaf_type")):
                reasons.add("tree")
            for k, v in props.items():
                target = ""
                if isinstance(v, str):
                    target = v.lower()
                elif isinstance(k, str):
                    target = k.lower()
                if any(tok in target for tok in ["custom point", "custom_point", "custompoint",
                                                 "custom line", "custom_line", "customline",
                                                 "custom polygon", "custom_polygon", "custompolygon"]):
                    reasons.add("custom_token")
        return reasons

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

        basename = os.path.basename(file_path)
        schema_key = self._schema_key_from_text(basename)
        if schema_key and schema_key in self.dataset_schema_paths:
            return self.dataset_schema_paths[schema_key]

        return self.line_schema_path

    # ----------------------------
    # Core validation entrypoint
    # ----------------------------
    def validate(self, max_errors=20) -> ValidationResult:
        def _finalize(is_valid: bool, errors: Optional[List[str]] = None) -> ValidationResult:
            final_errors = self.errors if errors is None else errors
            final_errors = (final_errors or [])[:max_errors]
            final_issues = (self.issues or [])[:max_errors]
            return ValidationResult(is_valid, final_errors, final_issues)

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
                return _finalize(False)

            # Validate the folder structure
            validator = ExtractedDataValidator(self.extracted_dir)
            if not validator.is_valid():
                upload_name = os.path.basename(self.zipfile_path) if self.zipfile_path else self.extracted_dir
                self.log_errors(
                    message=validator.error,
                    filename=upload_name,
                    feature_index=None
                )
                return _finalize(False)

            # Per-file schema validation → populate self.issues (fixme-like)
            for file in validator.files:
                file_path = os.path.join(file)
                if not self.validate_osw_errors(file_path=str(file_path), max_errors=max_errors):
                    # mirror legacy behavior: stop early when we hit the cap
                    break

            if self.errors:
                return _finalize(False)

            # Load GeoDataFrames for integrity checks
            for file in validator.files:
                file_path = os.path.join(file)
                osw_file = next((osw_key for osw_key in OSW_DATASET_FILES.keys()
                                 if osw_key in os.path.basename(file_path)), '')
                try:
                    gdf = _read_geojson_without_ext(file_path)
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

            # Geometry mapping: coordinate consistency using already-loaded GeoDataFrames
            if nodes_df is not None and len(self.errors) < max_errors:
                node_coord_map = self._build_node_coord_map(nodes_df)
                if node_coord_map:
                    self._validate_edge_geometry_mapping(edges_df, node_coord_map, max_errors)
                    self._validate_zone_geometry_mapping(zones_df, node_coord_map, max_errors)

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
                    extensionFile = _read_geojson_without_ext(file_path)
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
                return _finalize(False)
            else:
                return _finalize(True, [])

        except Exception as e:
            self.log_errors(
                message=f'Unable to validate: {e}',
                filename=None,
                feature_index=None
            )
            return _finalize(False)
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

        filename = os.path.basename(file_path)

        # Upfront guard: reject null/NaN values in free-form extension properties.
        # Schema-owned properties are left to schema validation.
        features = geojson_data.get("features", []) if isinstance(geojson_data, dict) else []
        found_nullish = False
        for idx, feature in enumerate(features):
            if not isinstance(feature, dict):
                continue
            props = feature.get("properties")
            if not isinstance(props, dict):
                continue
            bad_paths = self._collect_nullish_extension_property_paths(props)
            for path, bad_value in bad_paths:
                if len(self.errors) >= max_errors:
                    return False
                found_nullish = True
                rendered = f'"{bad_value}"' if isinstance(bad_value, str) else str(bad_value)
                msg = (
                    f"Invalid value at '{path}': {rendered}. "
                    f"Null/NaN placeholders are not allowed; provide a valid value or remove this property."
                )
                self.errors.append(f"Validation error: {msg}")
                self.issues.append({
                    "filename": filename,
                    "feature_index": idx,
                    "error_message": [msg],
                })
        if found_nullish:
            return False

        schema_url = geojson_data.get('$schema')
        if isinstance(schema_url, str) and '0.2/schema.json' in schema_url:
            reasons = self._contains_disallowed_features_for_02(geojson_data)
            if reasons:
                dataset_key = self._schema_key_from_text(file_path) or "data"
                custom_label_map = {
                    "edges": "Custom Edge",
                    "lines": "Custom Line",
                    "polygons": "Custom Polygon",
                    "zones": "Custom Polygon/Zone",
                    "points": "Custom Point",
                    "nodes": "Custom Node",
                }
                parts = []
                if "tree" in reasons:
                    parts.append("Tree coverage")
                if "custom_ext" in reasons or "custom_token" in reasons:
                    parts.append(custom_label_map.get(dataset_key, "Custom content"))
                msg = f"0.2 schema does not support " + " and ".join(parts)
                self.log_errors(
                    message=msg,
                    filename=os.path.basename(file_path),
                    feature_index=None,
                )
                return False

        schema_path = self.pick_schema_for_file(file_path, geojson_data)
        schema = self.load_osw_schema(schema_path)
        validator = jsonschema_rs.Draft7Validator(schema)

        # Legacy cap
        legacy_count = 0
        collected_issues: List[Dict[str, Any]] = []

        # --- STREAM over errors; STOP as soon as legacy hits the cap ---
        for err in validator.iter_errors(geojson_data):
            # legacy list (for backward compatibility)
            if legacy_count < max_errors:
                raw_msg = _add_additional_properties_hint(getattr(err, "message", "") or "")
                self.errors.append(f"Validation error: {raw_msg}")
                legacy_count += 1
            else:
                # We've reached the legacy cap; stop work to match original performance
                break

            # Keep every issue (no per-feature collapsing)
            fidx = _feature_index_from_error(err)
            collected_issues.append({
                "filename": filename,
                "feature_index": fidx if fidx is not None else -1,
                "error_message": [_pretty_message(err, schema)],
                "_kind": _err_kind(err),
            })

        # Drop noisy AnyOf summaries when specific field-level errors exist
        # for the same feature.
        has_specific_by_feature: Dict[int, bool] = {}
        for issue in collected_issues:
            fidx = issue["feature_index"]
            if issue.get("_kind") != "AnyOf":
                has_specific_by_feature[fidx] = True

        for issue in collected_issues:
            if issue.get("_kind") == "AnyOf" and has_specific_by_feature.get(issue["feature_index"], False):
                continue
            issue.pop("_kind", None)
            self.issues.append(issue)

        # Mirror original boolean behavior: False when we exactly hit the cap
        return len(self.errors) < max_errors
