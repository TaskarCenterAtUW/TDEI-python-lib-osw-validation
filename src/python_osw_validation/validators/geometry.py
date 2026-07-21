from dataclasses import dataclass
from typing import List, Optional, Set

import geopandas as gpd

from ..config import DEFAULT_MAX_GEOMETRY_VERTICES
from .common import feature_identifier
from .models import ValidationFinding


MAX_GEOMETRY_VERTICES = DEFAULT_MAX_GEOMETRY_VERTICES
VERTEX_LIMIT_DATASETS = frozenset({"edges", "lines", "polygons", "zones"})


@dataclass(frozen=True)
class GeometryValidationResult:
    findings: List[ValidationFinding]
    collapsed_indexes: Set


def ring_vertex_count(ring) -> int:
    coordinates = list(ring.coords)
    if len(coordinates) > 1 and coordinates[0] == coordinates[-1]:
        return len(coordinates) - 1
    return len(coordinates)


def geometry_vertex_count(geometry) -> int:
    """Count line and polygon vertices, excluding polygon ring closure coordinates."""
    if geometry is None:
        return 0
    if geometry.geom_type == 'LineString':
        return len(geometry.coords)
    if geometry.geom_type == 'Polygon':
        return ring_vertex_count(geometry.exterior) + sum(
            ring_vertex_count(ring) for ring in geometry.interiors
        )
    if geometry.geom_type in {'MultiLineString', 'MultiPolygon', 'GeometryCollection'}:
        return sum(geometry_vertex_count(part) for part in geometry.geoms)
    return 0


def geometry_coordinate_pairs(geometry) -> List[tuple]:
    """Return two-dimensional coordinate pairs from line and polygon geometries."""
    if geometry is None or geometry.is_empty:
        return []
    if geometry.geom_type in {'LineString', 'LinearRing'}:
        return [(coordinate[0], coordinate[1]) for coordinate in geometry.coords]
    if geometry.geom_type == 'Polygon':
        coordinates = geometry_coordinate_pairs(geometry.exterior)
        for ring in geometry.interiors:
            coordinates.extend(geometry_coordinate_pairs(ring))
        return coordinates
    if geometry.geom_type in {'MultiLineString', 'MultiPolygon', 'GeometryCollection'}:
        return [
            coordinate
            for part in geometry.geoms
            for coordinate in geometry_coordinate_pairs(part)
        ]
    return []


def collapsed_geometry_findings(
    gdf: Optional[gpd.GeoDataFrame],
    dataset_name: str,
    allow_zero_length_lines: bool = False,
) -> GeometryValidationResult:
    """Find line or polygon features whose coordinates all share one location."""
    findings: List[ValidationFinding] = []
    collapsed_indexes = set()
    if gdf is None:
        return GeometryValidationResult(findings, collapsed_indexes)

    for feature_index, row in gdf.iterrows():
        geometry = row.geometry
        coordinates = geometry_coordinate_pairs(geometry)
        if len(coordinates) < 2 or len(set(coordinates)) != 1:
            continue

        if geometry.geom_type in {'LineString', 'MultiLineString'}:
            geometry_problem = 'zero-length'
        elif geometry.geom_type in {'Polygon', 'MultiPolygon'}:
            geometry_problem = 'zero-area'
        else:
            continue

        collapsed_indexes.add(feature_index)
        if geometry.geom_type == 'LineString' and allow_zero_length_lines:
            continue
        feature_id = feature_identifier(row, feature_index)
        findings.append(ValidationFinding(
            message=(
                f"Feature '{feature_id}' in '{dataset_name}' has {geometry_problem} geometry "
                "because all coordinates are identical."
            ),
            filename=dataset_name,
            feature_index=feature_index,
            code="COLLAPSED_GEOMETRY",
        ))

    return GeometryValidationResult(findings, collapsed_indexes)


def vertex_limit_findings(
    gdf: Optional[gpd.GeoDataFrame],
    dataset_name: str,
    max_vertices: int = MAX_GEOMETRY_VERTICES,
) -> List[ValidationFinding]:
    """Find line or polygon features containing more than the configured limit."""
    findings: List[ValidationFinding] = []
    if gdf is None:
        return findings

    for feature_index, row in gdf.iterrows():
        vertex_count = geometry_vertex_count(row.geometry)
        if vertex_count <= max_vertices:
            continue

        feature_id = feature_identifier(row, feature_index)
        findings.append(ValidationFinding(
            message=(
                f"Feature '{feature_id}' in '{dataset_name}' contains {vertex_count} geometry vertices. "
                f"Maximum allowed is {max_vertices}."
            ),
            filename=dataset_name,
            feature_index=feature_index,
            code="GEOMETRY_VERTEX_LIMIT",
        ))
    return findings


def generic_invalid_geometry_finding(
    gdf: gpd.GeoDataFrame,
    dataset_name: str,
    expected_geometry: Optional[str],
    excluded_indexes: Set,
    display_limit: int,
    is_extension: bool = False,
) -> Optional[ValidationFinding]:
    if expected_geometry:
        invalid = gdf[(gdf.geometry.type != expected_geometry) | (gdf.is_valid == False)]
    else:
        invalid = gdf[gdf.is_valid == False]
    if excluded_indexes:
        invalid = invalid.drop(index=excluded_indexes, errors='ignore')
    if len(invalid) == 0:
        return None

    if is_extension:
        try:
            invalid_ids = list(set(invalid.get('_id', invalid.index)))
        except Exception as error:
            return ValidationFinding(
                message=(
                    f"Invalid features found in `{dataset_name}`, but failed to extract IDs: {error}"
                ),
                filename=dataset_name,
                code="GEOMETRY_ID_EXTRACTION_ERROR",
            )
    else:
        ids = invalid['_id'] if '_id' in invalid.columns else invalid.index
        invalid_ids = list(set(ids))
    count = len(invalid_ids)
    displayed = ', '.join(map(str, invalid_ids[:display_limit]))
    shown = display_limit if count > display_limit else 'all'
    if is_extension:
        message = (
            f"Invalid geometries found in extension file `{dataset_name}`. "
            f"Showing {shown} of {count} invalid geometry IDs: {displayed}"
        )
        filename = dataset_name
    else:
        message = (
            f"Showing {shown} out of {count} invalid {dataset_name} geometries, "
            f"id's of invalid geometries: {displayed}"
        )
        filename = 'All'
    return ValidationFinding(message=message, filename=filename, code="INVALID_GEOMETRY")


def validate_dataset_geometries(
    gdf: Optional[gpd.GeoDataFrame],
    dataset_name: str,
    expected_geometry: Optional[str],
    display_limit: int,
    include_vertex_limit: bool,
    is_extension: bool = False,
    max_vertices: int = MAX_GEOMETRY_VERTICES,
    allow_zero_length_lines: bool = False,
) -> GeometryValidationResult:
    if gdf is None:
        return GeometryValidationResult([], set())

    allow_collapsed_line = allow_zero_length_lines and (
        expected_geometry == 'LineString' or is_extension
    )
    collapsed = collapsed_geometry_findings(
        gdf,
        dataset_name,
        allow_collapsed_line,
    )
    findings = list(collapsed.findings)
    if include_vertex_limit:
        findings.extend(vertex_limit_findings(gdf, dataset_name, max_vertices))
    generic = generic_invalid_geometry_finding(
        gdf,
        dataset_name,
        expected_geometry,
        collapsed.collapsed_indexes,
        display_limit,
        is_extension,
    )
    if generic:
        findings.append(generic)
    return GeometryValidationResult(findings, collapsed.collapsed_indexes)
