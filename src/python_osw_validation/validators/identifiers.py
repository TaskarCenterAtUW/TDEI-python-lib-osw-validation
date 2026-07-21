from typing import Callable, Dict, List, Optional, Set, Tuple

import geopandas as gpd

from .models import ValidationFinding


def column_values(
    gdf: Optional[gpd.GeoDataFrame],
    column: str,
    dataset_name: str,
) -> Tuple[Set, List[ValidationFinding]]:
    if gdf is None:
        return set(), []
    if column not in gdf.columns:
        return set(), [ValidationFinding(
            f"Missing required column '{column}' in {dataset_name}.",
            dataset_name,
            code="MISSING_REQUIRED_COLUMN",
        )]
    try:
        return set(gdf[column].dropna()), []
    except Exception:
        try:
            return set(map(str, gdf[column].dropna())), []
        except Exception:
            return set(), [ValidationFinding(
                f"Could not create set for column '{column}' in {dataset_name}.",
                dataset_name,
                code="COLUMN_VALUE_ERROR",
            )]


def duplicate_identifier_findings(
    datasets: Dict[str, Optional[gpd.GeoDataFrame]],
    display_limit: int,
    duplicate_checker: Optional[Callable] = None,
) -> List[ValidationFinding]:
    findings: List[ValidationFinding] = []
    for dataset_name, gdf in datasets.items():
        if gdf is None:
            continue
        if duplicate_checker:
            is_valid, duplicates = duplicate_checker(gdf)
            if is_valid:
                continue
        else:
            duplicates = list(gdf[gdf.duplicated('_id', keep=False)]['_id'].unique())
        if not duplicates:
            continue
        displayed = ', '.join(map(str, duplicates[:display_limit]))
        if len(duplicates) > display_limit:
            message = (
                f"Duplicate _id's found in {dataset_name}: showing first {display_limit} "
                f"of {len(duplicates)} duplicates: {displayed}"
            )
        else:
            message = f"Duplicate _id's found in {dataset_name}: {displayed}"
        findings.append(ValidationFinding(message, dataset_name, code="DUPLICATE_IDENTIFIER"))
    return findings


def _reference_values(gdf: Optional[gpd.GeoDataFrame], column: str) -> Set:
    if gdf is None or column not in gdf.columns:
        return set()
    values = gdf[column].dropna().tolist()
    return {
        item
        for value in values
        for item in (value if isinstance(value, (list, tuple)) else [value])
    }


def _unmatched_finding(
    node_ids: Set,
    references: Set,
    field: str,
    source_dataset: str,
    display_limit: int,
) -> Optional[ValidationFinding]:
    if not node_ids or not references:
        return None
    unmatched = list(references - node_ids)
    if not unmatched:
        return None
    displayed = ', '.join(map(str, unmatched[:display_limit]))
    shown = display_limit if len(unmatched) > display_limit else 'all'
    return ValidationFinding(
        message=(
            f"All {field}'s in {source_dataset} should be part of _id's mentioned in nodes. "
            f"Showing {shown} out of {len(unmatched)} unmatched {field}'s: {displayed}"
        ),
        filename='All',
        code="UNMATCHED_REFERENCE",
    )


def identifier_integrity_findings(
    datasets: Dict[str, Optional[gpd.GeoDataFrame]],
    display_limit: int,
    duplicate_checker: Optional[Callable] = None,
) -> List[ValidationFinding]:
    """Validate duplicate IDs, required reference columns, and cross-file references."""
    findings = duplicate_identifier_findings(datasets, display_limit, duplicate_checker)
    nodes = datasets.get('nodes')
    edges = datasets.get('edges')
    zones = datasets.get('zones')

    node_ids, node_findings = column_values(nodes, '_id', 'nodes') if nodes is not None else (set(), [])
    u_ids, u_findings = column_values(edges, '_u_id', 'edges') if edges is not None else (set(), [])
    v_ids, v_findings = column_values(edges, '_v_id', 'edges') if edges is not None else (set(), [])
    findings.extend(node_findings + u_findings + v_findings)

    if zones is not None and '_w_id' not in zones.columns:
        findings.append(ValidationFinding(
            "Missing required column '_w_id' in zones.",
            'zones',
            code="MISSING_REQUIRED_COLUMN",
        ))
        w_ids = set()
    else:
        w_ids = _reference_values(zones, '_w_id')

    for references, field, dataset_name in (
        (u_ids, '_u_id', 'edges'),
        (v_ids, '_v_id', 'edges'),
        (w_ids, '_w_id', 'zones'),
    ):
        finding = _unmatched_finding(node_ids, references, field, dataset_name, display_limit)
        if finding:
            findings.append(finding)
    return findings
