from typing import Any, Dict, List, Optional

import geopandas as gpd

from .common import feature_identifier
from .models import ValidationFinding


def build_node_coord_map(nodes_df: gpd.GeoDataFrame) -> Dict[Any, tuple]:
    coordinates: Dict[Any, tuple] = {}
    for _, row in nodes_df.iterrows():
        node_id = row.get('_id')
        geometry = row.geometry
        if node_id is not None and geometry is not None and geometry.geom_type == 'Point':
            coordinates[node_id] = (geometry.x, geometry.y)
    return coordinates


def edge_mapping_findings(
    edges_df: Optional[gpd.GeoDataFrame],
    node_coordinates: Dict[Any, tuple],
) -> List[ValidationFinding]:
    findings: List[ValidationFinding] = []
    if edges_df is None or not node_coordinates:
        return findings

    has_u_id = '_u_id' in edges_df.columns
    has_v_id = '_v_id' in edges_df.columns
    if not (has_u_id or has_v_id):
        return findings

    for feature_index, row in edges_df.iterrows():
        geometry = row.geometry
        if geometry is None or geometry.geom_type != 'LineString':
            continue
        coordinates = list(geometry.coords)
        if not coordinates:
            continue

        edge_id = feature_identifier(row, feature_index)
        for field, coordinate, endpoint in (
            ('_u_id', coordinates[0], 'start'),
            ('_v_id', coordinates[-1], 'end'),
        ):
            if field not in edges_df.columns:
                continue
            node_id = row.get(field)
            if node_id is None or node_id not in node_coordinates:
                continue
            node_coordinate = node_coordinates[node_id]
            edge_coordinate = (coordinate[0], coordinate[1])
            if edge_coordinate == node_coordinate:
                continue
            findings.append(ValidationFinding(
                message=(
                    f"edges id '{edge_id}' : {endpoint} coordinate {edge_coordinate} does not match "
                    f"node id '{node_id}' coordinate {node_coordinate} ({field} mismatch)."
                ),
                filename='edges',
                feature_index=feature_index,
                code="EDGE_NODE_COORDINATE_MISMATCH",
            ))
    return findings


def zone_mapping_findings(
    zones_df: Optional[gpd.GeoDataFrame],
    node_coordinates: Dict[Any, tuple],
) -> List[ValidationFinding]:
    findings: List[ValidationFinding] = []
    if zones_df is None or not node_coordinates or '_w_id' not in zones_df.columns:
        return findings

    for feature_index, row in zones_df.iterrows():
        geometry = row.geometry
        if geometry is None or geometry.geom_type != 'Polygon':
            continue
        zone_id = feature_identifier(row, feature_index)
        ring_coordinates = {(coordinate[0], coordinate[1]) for coordinate in geometry.exterior.coords}
        node_ids = row.get('_w_id')
        if node_ids is None:
            continue
        if not isinstance(node_ids, (list, tuple)):
            node_ids = [node_ids]

        for node_id in node_ids:
            if node_id is None or node_id not in node_coordinates:
                continue
            node_coordinate = node_coordinates[node_id]
            if node_coordinate in ring_coordinates:
                continue
            findings.append(ValidationFinding(
                message=(
                    f"zones id '{zone_id}' : node id '{node_id}' coordinate {node_coordinate} "
                    "is not a vertex of the zone polygon geometry (_w_id coordinate mismatch)."
                ),
                filename='zones',
                feature_index=feature_index,
                code="ZONE_NODE_COORDINATE_MISMATCH",
            ))
    return findings
