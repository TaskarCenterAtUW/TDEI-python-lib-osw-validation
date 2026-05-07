"""Geometry mapping consistency validation for OSW datasets.

This module validates that cross-file references between OSW dataset
components correspond to real geometries:

* ``edges._u_id`` / ``edges._v_id`` must reference an existing node in
  ``nodes.geojson`` AND the node's coordinates must equal the corresponding
  endpoint of the edge ``LineString`` (start coord for ``_u_id``, end coord
  for ``_v_id``).
* ``zones._w_id`` is a list of node ids whose coordinates must match the
  zone polygon's outer ring vertices, in order.

The validator emits structured issues with ``filename``, ``feature_index``,
``feature_id`` (when available) and a clear, actionable error message.

Coordinate matching is performed by exact equality on the (lon, lat) pair.
Altitude / extra coordinate dimensions are ignored.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
import math


# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------

Coord = Tuple[float, float]


def _coord_key(coord: Sequence[Any]) -> Optional[Coord]:
    """Return (lon, lat) tuple for a coordinate, or None when malformed."""
    if not isinstance(coord, (list, tuple)) or len(coord) < 2:
        return None
    try:
        lon = float(coord[0])
        lat = float(coord[1])
    except (TypeError, ValueError):
        return None
    if math.isnan(lon) or math.isnan(lat):
        return None
    return (lon, lat)


def _format_coord(coord: Optional[Sequence[Any]]) -> str:
    key = _coord_key(coord) if coord is not None else None
    if key is None:
        return "<missing>"
    return f"({key[0]}, {key[1]})"


# ---------------------------------------------------------------------------
# Index builders
# ---------------------------------------------------------------------------


def build_node_coord_index(nodes_geojson: Optional[Dict[str, Any]]) -> Dict[str, Coord]:
    """Map each node ``_id`` to its (lon, lat) coordinate.

    Nodes without a usable ``_id`` or geometry are skipped silently;
    higher level validation already reports those issues.
    """
    index: Dict[str, Coord] = {}
    if not isinstance(nodes_geojson, dict):
        return index
    features = nodes_geojson.get("features") or []
    if not isinstance(features, list):
        return index
    for feature in features:
        if not isinstance(feature, dict):
            continue
        props = feature.get("properties") or {}
        node_id = props.get("_id") if isinstance(props, dict) else None
        if not isinstance(node_id, str) or not node_id:
            continue
        geom = feature.get("geometry") or {}
        if not isinstance(geom, dict) or geom.get("type") != "Point":
            continue
        coord = _coord_key(geom.get("coordinates"))
        if coord is None:
            continue
        # First write wins - duplicate id detection is reported elsewhere.
        index.setdefault(node_id, coord)
    return index


# ---------------------------------------------------------------------------
# Edge validation
# ---------------------------------------------------------------------------


def validate_edge_node_mapping(
        edges_geojson: Optional[Dict[str, Any]],
        node_coords: Dict[str, Coord],
        edges_filename: str = "edges",
        nodes_present: bool = True,
) -> List[Dict[str, Any]]:
    """Validate ``_u_id`` and ``_v_id`` references on edges.

    Reports issues for:
      * Missing reference values
      * References whose target node id does not exist in nodes
      * References whose target node coordinate does not match the matching
        endpoint of the edge ``LineString``

    When ``nodes_present`` is False (no nodes file in dataset) coordinate
    matching is skipped because the targets are unknown.
    """
    issues: List[Dict[str, Any]] = []
    if not isinstance(edges_geojson, dict):
        return issues
    features = edges_geojson.get("features") or []
    if not isinstance(features, list):
        return issues

    for idx, feature in enumerate(features):
        if not isinstance(feature, dict):
            continue
        props = feature.get("properties") or {}
        if not isinstance(props, dict):
            props = {}
        feature_id = props.get("_id") if isinstance(props.get("_id"), str) else None
        geom = feature.get("geometry") or {}
        coords = geom.get("coordinates") if isinstance(geom, dict) else None
        is_linestring = (
                isinstance(geom, dict)
                and geom.get("type") == "LineString"
                and isinstance(coords, list)
                and len(coords) >= 2
        )
        u_endpoint = _coord_key(coords[0]) if is_linestring else None
        v_endpoint = _coord_key(coords[-1]) if is_linestring else None

        for ref_field, endpoint, endpoint_label in (
                ("_u_id", u_endpoint, "start"),
                ("_v_id", v_endpoint, "end"),
        ):
            ref_val = props.get(ref_field)
            if ref_val is None or (isinstance(ref_val, str) and not ref_val.strip()):
                issues.append(_make_issue(
                    edges_filename, idx, feature_id,
                    f"Edge is missing required '{ref_field}' reference.",
                ))
                continue
            if not isinstance(ref_val, str):
                # Schema validation already complains about non-string ids; skip
                # cross-file checks for these.
                continue

            if not nodes_present:
                # Only the existence check is meaningful, and we have no node set.
                continue

            target = node_coords.get(ref_val)
            if target is None:
                issues.append(_make_issue(
                    edges_filename, idx, feature_id,
                    f"Edge {ref_field}='{ref_val}' does not reference any node in nodes.geojson.",
                ))
                continue

            if endpoint is None:
                # Geometry was malformed; schema validation reports that. Skip
                # coordinate mismatch reporting to avoid noise.
                continue

            if target != endpoint:
                issues.append(_make_issue(
                    edges_filename, idx, feature_id,
                    (f"Edge {ref_field}='{ref_val}' coordinate mismatch: "
                     f"node is at {_format_coord(target)} but edge {endpoint_label} "
                     f"point is at {_format_coord(endpoint)}."),
                ))
    return issues


# ---------------------------------------------------------------------------
# Zone validation
# ---------------------------------------------------------------------------


def _polygon_outer_ring(geom: Any) -> Optional[List[Sequence[Any]]]:
    """Return the outer ring coordinate list for a Polygon, else None."""
    if not isinstance(geom, dict):
        return None
    if geom.get("type") != "Polygon":
        return None
    coords = geom.get("coordinates")
    if not isinstance(coords, list) or not coords:
        return None
    ring = coords[0]
    if not isinstance(ring, list) or len(ring) < 3:
        return None
    return ring


def validate_zone_node_mapping(
        zones_geojson: Optional[Dict[str, Any]],
        node_coords: Dict[str, Coord],
        zones_filename: str = "zones",
        nodes_present: bool = True,
) -> List[Dict[str, Any]]:
    """Validate ``_w_id`` references on zones.

    Each zone feature must have a ``_w_id`` array whose entries:
      1. Reference real node ids
      2. Map to coordinates that match the polygon's outer-ring vertices
         in the same order. The ring may include a closing vertex
         (last == first); when present the closing vertex is ignored
         when comparing lengths.
    """
    issues: List[Dict[str, Any]] = []
    if not isinstance(zones_geojson, dict):
        return issues
    features = zones_geojson.get("features") or []
    if not isinstance(features, list):
        return issues

    for idx, feature in enumerate(features):
        if not isinstance(feature, dict):
            continue
        props = feature.get("properties") or {}
        if not isinstance(props, dict):
            props = {}
        feature_id = props.get("_id") if isinstance(props.get("_id"), str) else None
        w_ids = props.get("_w_id")
        if w_ids is None:
            issues.append(_make_issue(
                zones_filename, idx, feature_id,
                "Zone is missing required '_w_id' reference list.",
            ))
            continue
        if not isinstance(w_ids, (list, tuple)):
            issues.append(_make_issue(
                zones_filename, idx, feature_id,
                "Zone '_w_id' must be an array of node identifiers.",
            ))
            continue
        if not w_ids:
            issues.append(_make_issue(
                zones_filename, idx, feature_id,
                "Zone '_w_id' array is empty; expected node references for the polygon ring.",
            ))
            continue

        # Existence check
        missing_refs = [w for w in w_ids if not (isinstance(w, str) and w in node_coords)]
        if nodes_present and missing_refs:
            preview = ", ".join(map(str, missing_refs[:5]))
            more = f" (+{len(missing_refs) - 5} more)" if len(missing_refs) > 5 else ""
            issues.append(_make_issue(
                zones_filename, idx, feature_id,
                f"Zone '_w_id' references unknown node id(s): {preview}{more}.",
            ))
            # We continue to coordinate check on a best-effort basis below
            # only if all references resolve; otherwise it's noisy.
            continue

        ring = _polygon_outer_ring(feature.get("geometry"))
        if ring is None:
            # Schema/geometry validation already reports malformed polygons.
            continue
        if not nodes_present:
            continue

        ring_coords = [_coord_key(c) for c in ring]
        is_closed = (
                len(ring_coords) >= 2
                and ring_coords[0] is not None
                and ring_coords[0] == ring_coords[-1]
        )
        # Two conventions are accepted for closed rings:
        #   * `_w_id` contains an entry for every ring vertex, *including* the
        #     trailing duplicate that closes the polygon.
        #   * `_w_id` contains an entry only for each unique ring vertex (no
        #     trailing duplicate).
        # For open rings only the first convention is valid.
        if is_closed and len(w_ids) == len(ring_coords) - 1:
            comparable_ring = ring_coords[:-1]
        else:
            comparable_ring = ring_coords

        if len(comparable_ring) != len(w_ids):
            issues.append(_make_issue(
                zones_filename, idx, feature_id,
                (f"Zone '_w_id' has {len(w_ids)} entries but polygon ring has "
                 f"{len(comparable_ring)} vertices; they must align."),
            ))
            continue

        mismatches: List[str] = []
        for pos, (wid, ring_pt) in enumerate(zip(w_ids, comparable_ring)):
            if not isinstance(wid, str):
                mismatches.append(
                    f"position {pos}: '_w_id' entry is not a string"
                )
                continue
            node_pt = node_coords.get(wid)
            if node_pt is None or ring_pt is None or node_pt != ring_pt:
                mismatches.append(
                    f"position {pos}: '_w_id'='{wid}' at node {_format_coord(node_pt)} "
                    f"vs ring vertex {_format_coord(ring_pt)}"
                )
        if mismatches:
            preview = "; ".join(mismatches[:3])
            more = f"; and {len(mismatches) - 3} more" if len(mismatches) > 3 else ""
            issues.append(_make_issue(
                zones_filename, idx, feature_id,
                f"Zone polygon ring does not match '_w_id' node coordinates: {preview}{more}.",
            ))
    return issues


# ---------------------------------------------------------------------------
# Issue construction
# ---------------------------------------------------------------------------


def _make_issue(
        filename: str,
        feature_index: Optional[int],
        feature_id: Optional[str],
        message: str,
) -> Dict[str, Any]:
    return {
        "filename": filename,
        "feature_index": feature_index,
        "feature_id": feature_id,
        "error_message": [message],
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_geometry_mapping_validation(
        nodes_geojson: Optional[Dict[str, Any]],
        edges_geojson: Optional[Dict[str, Any]],
        zones_geojson: Optional[Dict[str, Any]],
        filenames: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Run all geometry mapping validations and return aggregated issues.

    ``filenames`` maps the dataset key (``edges``, ``zones``, ``nodes``)
    to the filename used in error messages so that downstream tooling sees
    the actual file rather than a generic dataset key.
    """
    fn = filenames or {}
    edges_name = fn.get("edges", "edges")
    zones_name = fn.get("zones", "zones")

    nodes_present = isinstance(nodes_geojson, dict) and bool(nodes_geojson.get("features"))
    node_coords = build_node_coord_index(nodes_geojson) if nodes_present else {}

    issues: List[Dict[str, Any]] = []
    issues.extend(validate_edge_node_mapping(
        edges_geojson, node_coords, edges_name, nodes_present
    ))
    issues.extend(validate_zone_node_mapping(
        zones_geojson, node_coords, zones_name, nodes_present
    ))
    return issues


__all__ = [
    "build_node_coord_index",
    "run_geometry_mapping_validation",
    "validate_edge_node_mapping",
    "validate_zone_node_mapping",
]
