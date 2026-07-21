import os
import gc
import json
from typing import Dict, Any, Optional, List, Tuple
import geopandas as gpd
import jsonschema_rs  # Re-exported for backward-compatible test and patch seams.

from .zipfile_handler import ZipFileHandler
from .config import DEFAULT_COORDINATE_PRECISION, ValidationConfig
from .extracted_data_validator import ExtractedDataValidator, OSW_DATASET_FILES, dataset_key_for_filename
from .version import __version__
from .helpers import (
    _read_geojson_without_ext,
    _geojson_file_has_excess_coordinate_precision,
)
from .validators.geometry import (
    MAX_GEOMETRY_VERTICES,
    VERTEX_LIMIT_DATASETS,
    collapsed_geometry_findings,
    generic_invalid_geometry_finding,
    geometry_vertex_count,
    vertex_limit_findings,
)
from .validators.identifiers import column_values, identifier_integrity_findings
from .validators.mapping import build_node_coord_map, edge_mapping_findings, zone_mapping_findings
from .validators.models import ValidationFinding
from .validators.precision import has_excess_coordinate_precision
from .validators.schema import (
    collect_nullish_extension_property_paths,
    disallowed_legacy_02_features,
    prevalidate_geojson,
    schema_key_from_text,
    schema_key_from_url,
    validate_against_schema,
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

COORDINATE_PRECISION_WARNING = (
    "Input dataset contains coordinates with more than "
    f"{DEFAULT_COORDINATE_PRECISION} decimal places."
)


class ValidationResult:
    """Container for validation outcome.

    * `errors`: high-level, human-readable strings (legacy behavior).
    * `error_details`: structured high-level errors.
    * `issues`: per-feature schema problems (former `fixme`), each item:
        { 'filename': str, 'feature_index': Optional[int], 'error_message': List[str] }
    * `issue_details`: issues with additive stable `code` and `severity` metadata.
    * `warnings`: non-blocking validation warning string.
    * `warning_details`: structured warning metadata.
    * `summary`: aggregate counts by severity, code, and file.
    """

    def __init__(self, is_valid: bool, errors: Optional[List[str]] = None,
                 issues: Optional[List[Dict[str, Any]]] = None, warnings: str = ""):
        self.is_valid = is_valid
        if len(errors) == 0:
            self.errors = None
        else:
            self.errors = errors
        self.error_details = [{
            "code": "VALIDATION_ERROR",
            "severity": "error",
            "message": message,
        } for message in (self.errors or [])]
        self.issue_details = self._normalize_issues(issues)
        self.issues = self._legacy_issues(issues)
        self.warnings = warnings
        self.warning_details = ([{
            "code": "COORDINATE_PRECISION",
            "severity": "warning",
            "message": warnings,
        }] if warnings else [])
        self.summary = self._build_summary()

    @staticmethod
    def _normalize_issues(issues: Optional[List[Dict[str, Any]]]):
        if issues is None:
            return None
        normalized = []
        for issue in issues:
            item = dict(issue)
            item.setdefault("code", "VALIDATION_ERROR")
            item.setdefault("severity", "error")
            normalized.append(item)
        return normalized

    @staticmethod
    def _legacy_issues(issues: Optional[List[Dict[str, Any]]]):
        if issues is None:
            return None
        return [
            {key: value for key, value in issue.items() if key not in {"code", "severity"}}
            for issue in issues
        ]

    def _build_summary(self) -> Dict[str, Any]:
        issues = self.issue_details or []
        by_code: Dict[str, int] = {}
        by_file: Dict[str, int] = {}
        for issue in issues:
            code = issue["code"]
            filename = issue.get("filename") or "unknown"
            by_code[code] = by_code.get(code, 0) + 1
            by_file[filename] = by_file.get(filename, 0) + 1
        for warning in self.warning_details:
            code = warning["code"]
            by_code[code] = by_code.get(code, 0) + 1
        return {
            "error_count": len(self.errors or []),
            "warning_count": len(self.warning_details),
            "issue_count": len(issues),
            "by_severity": {
                "error": len(self.error_details),
                "warning": len(self.warning_details),
            },
            "by_code": by_code,
            "by_file": by_file,
        }


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
            config: Optional[ValidationConfig] = None,
    ):
        self.zipfile_path = zipfile_path
        self.extracted_dir: Optional[str] = None
        self.errors: List[str] = []
        # per-feature schema issues (formerly `fixme`)
        self.issues: List[Dict[str, Any]] = []
        self.warnings = ""
        if config is not None and not isinstance(config, ValidationConfig):
            raise TypeError("config must be a ValidationConfig instance.")
        self.config = config or ValidationConfig()

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
    def log_errors(
        self,
        message: str,
        filename: Optional[str] = None,
        feature_index: Optional[int] = None,
        code: str = "VALIDATION_ERROR",
    ):
        """Helper to log errors in a consistent format."""
        self.errors.append(message)
        self.issues.append({
            'filename': filename,
            'feature_index': feature_index,
            'error_message': message,
            'code': code,
            'severity': 'error',
        })

    def _record_findings(
        self,
        findings: List[ValidationFinding],
        max_errors: Optional[int] = None,
    ) -> None:
        for finding in findings:
            if max_errors is not None and len(self.errors) >= max_errors:
                break
            self.log_errors(
                finding.message,
                finding.filename,
                finding.feature_index,
                finding.code,
            )

    def _check_coordinate_precision(self, file_paths) -> None:
        """Set one aggregate warning without affecting validation state."""
        if has_excess_coordinate_precision(
            file_paths,
            checker=lambda path: _geojson_file_has_excess_coordinate_precision(
                path,
                self.config.coordinate_precision,
            ),
        ):
            self.warnings = (
                "Input dataset contains coordinates with more than "
                f"{self.config.coordinate_precision} decimal places."
            )

    # add this small helper inside OSWValidation (near other helpers)
    def _get_colset(self, gdf: Optional[gpd.GeoDataFrame], col: str, filekey: str) -> set:
        """Return set of a column if present; else log and return empty set."""
        values, findings = column_values(gdf, col, filekey)
        self._record_findings(findings)
        return values

    # ----------------------------
    # Geometry mapping helpers
    # ----------------------------

    def _build_node_coord_map(self, nodes_df: gpd.GeoDataFrame) -> Dict[Any, tuple]:
        """Return {node_id: (lon, lat)} from a nodes GeoDataFrame."""
        return build_node_coord_map(nodes_df)

    def _validate_edge_geometry_mapping(
        self,
        edges_df: Optional[gpd.GeoDataFrame],
        node_coord_map: Dict[Any, tuple],
        max_errors: int,
    ) -> None:
        """Verify edge start/end coordinates match their _u_id/_v_id node geometries."""
        self._record_findings(edge_mapping_findings(edges_df, node_coord_map), max_errors)

    def _validate_zone_geometry_mapping(
        self,
        zones_df: Optional[gpd.GeoDataFrame],
        node_coord_map: Dict[Any, tuple],
        max_errors: int,
    ) -> None:
        """Verify each _w_id node coordinate is a vertex of the zone's polygon exterior ring."""
        self._record_findings(zone_mapping_findings(zones_df, node_coord_map), max_errors)

    def _geometry_vertex_count(self, geom) -> int:
        """Count line and polygon vertices, excluding polygon ring closure coordinates."""
        return geometry_vertex_count(geom)

    def _validate_geometry_vertex_limit(
        self,
        gdf: Optional[gpd.GeoDataFrame],
        dataset_name: str,
        max_errors: int,
    ) -> None:
        """Report line or polygon features containing more than 2,000 vertices."""
        self._record_findings(
            vertex_limit_findings(
                gdf,
                dataset_name,
                self.config.max_geometry_vertices,
            ),
            max_errors,
        )

    def _validate_collapsed_geometries(
        self,
        gdf: Optional[gpd.GeoDataFrame],
        dataset_name: str,
        max_errors: int,
    ) -> set:
        """Report line or polygon features whose coordinates all share one location."""
        result = collapsed_geometry_findings(
            gdf,
            dataset_name,
            self.config.allow_zero_length_lines and dataset_name in {"edges", "lines"},
        )
        self._record_findings(result.findings, max_errors)
        return result.collapsed_indexes

    def _schema_key_from_text(self, text: Optional[str]) -> Optional[str]:
        """Return dataset key from exact filename suffixes only."""
        return schema_key_from_text(text, self.dataset_schema_paths)

    def _schema_key_from_schema_url(self, schema_url: Any) -> Optional[str]:
        return schema_key_from_url(schema_url, self.dataset_schema_paths)

    def _collect_nullish_extension_property_paths(self, props: Dict[str, Any]) -> List[Tuple[str, Any]]:
        return collect_nullish_extension_property_paths(props)

    def _contains_disallowed_features_for_02(self, geojson_data: Dict[str, Any]) -> set:
        """Detect Tree coverage or Custom content in legacy 0.2 datasets.

        Returns a set of reason tags, e.g. {"tree", "custom_ext", "custom_token"}.
        Empty set means no 0.2-only violations detected.
        """
        return disallowed_legacy_02_features(geojson_data)

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

        schema_key = self._schema_key_from_schema_url(geojson_data.get('$schema'))
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
            return ValidationResult(is_valid, final_errors, final_issues, self.warnings)

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

            self._check_coordinate_precision(
                list(getattr(validator, 'files', []) or [])
                + list(getattr(validator, 'externalExtensions', []) or [])
            )

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
                osw_file = dataset_key_for_filename(os.path.basename(file_path))
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

            self._record_findings(
                identifier_integrity_findings(
                    OSW_DATASET,
                    max_errors,
                    duplicate_checker=self.are_ids_unique,
                ),
                max_errors,
            )

            nodes_df = OSW_DATASET.get('nodes')
            edges_df = OSW_DATASET.get('edges')
            zones_df = OSW_DATASET.get('zones')

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
                collapsed = collapsed_geometry_findings(
                    gdf,
                    osw_file,
                    self.config.allow_zero_length_lines and osw_file in {"edges", "lines"},
                )
                self._record_findings(collapsed.findings, max_errors)
                if osw_file in VERTEX_LIMIT_DATASETS and len(self.errors) < max_errors:
                    self._validate_geometry_vertex_limit(gdf, osw_file, max_errors)
                expected_geom = OSW_DATASET_FILES.get(osw_file, {}).get('geometry')
                generic = generic_invalid_geometry_finding(
                    gdf,
                    osw_file,
                    expected_geom,
                    collapsed.collapsed_indexes,
                    max_errors,
                )
                if generic:
                    self._record_findings([generic], max_errors)

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

                collapsed = collapsed_geometry_findings(
                    extensionFile,
                    file_name,
                    self.config.allow_zero_length_lines,
                )
                self._record_findings(collapsed.findings, max_errors)
                if len(self.errors) < max_errors:
                    self._validate_geometry_vertex_limit(extensionFile, file_name, max_errors)
                generic = generic_invalid_geometry_finding(
                    extensionFile,
                    file_name,
                    None,
                    collapsed.collapsed_indexes,
                    max_errors,
                    True,
                )
                if generic:
                    self._record_findings([generic], max_errors)

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
        remaining_errors = max_errors - len(self.errors)
        if remaining_errors <= 0:
            return False

        prevalidation = prevalidate_geojson(
            geojson_data,
            filename,
            self._schema_key_from_text(file_path) or "data",
            remaining_errors,
        )
        if prevalidation:
            self.errors.extend(prevalidation.errors)
            self.issues.extend(prevalidation.issues)
            return prevalidation.continue_validation

        schema_path = self.pick_schema_for_file(file_path, geojson_data)
        schema = self.load_osw_schema(schema_path)
        outcome = validate_against_schema(
            geojson_data,
            filename,
            schema,
            remaining_errors,
        )
        self.errors.extend(outcome.errors)
        self.issues.extend(outcome.issues)
        return outcome.continue_validation
