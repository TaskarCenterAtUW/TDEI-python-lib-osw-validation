from typing import Optional
import re

def _feature_index_from_error(err) -> Optional[int]:
    """
    Return the index after 'features' in the instance path, else None.
    Works with jsonschema_rs errors.
    """
    path = list(getattr(err, "instance_path", []))
    for i, seg in enumerate(path):
        if seg == "features" and i + 1 < len(path) and isinstance(path[i + 1], int):
            return path[i + 1]
    return None

def _err_kind(err) -> str:
    """
    Best-effort classification of error kind.
    Prefers jsonschema_rs 'kind', falls back to 'validator', then message.
    """
    kobj = getattr(err, "kind", None)
    if kobj is not None:
        return type(kobj).__name__.split("_")[-1]  # e.g. 'AnyOf', 'Enum', 'Required'
    v = getattr(err, "validator", None)
    if isinstance(v, str):
        return v[0].upper() + v[1:]  # 'anyOf' -> 'AnyOf'
    msg = getattr(err, "message", "") or ""
    return "AnyOf" if "anyOf" in msg else ""


def _clean_enum_message(err) -> str:
    """Compact enum error (strip ‘…or N other candidates’)."""
    msg = getattr(err, "message", "") or ""
    msg = re.sub(r"\s*or\s+\d+\s+other candidates", "", msg)
    return msg.split("\n")[0]


def _pretty_message(err, schema) -> str:
    """
    Convert a jsonschema_rs error to a concise, user-friendly string.

    Special handling:
      - Enum  → compact message
      - AnyOf → summarize the union of 'required' fields across branches:
                "must include one of: <fields>"
    """
    kind = _err_kind(err)

    if kind == "Enum":
        return _clean_enum_message(err)

    if kind == "AnyOf":
        # Follow schema_path to the anyOf node; union of 'required' keys in branches.
        sub = schema
        try:
            for seg in getattr(err, "schema_path", []):
                sub = sub[seg]

            required = set()

            def crawl(node):
                if isinstance(node, dict):
                    if isinstance(node.get("required"), list):
                        required.update(node["required"])
                    for key in ("allOf", "anyOf", "oneOf"):
                        if isinstance(node.get(key), list):
                            for child in node[key]:
                                crawl(child)
                elif isinstance(node, list):
                    for child in node:
                        crawl(child)

            crawl(sub)

            if required:
                props = ", ".join(sorted(required))
                return f"must include one of: {props}"
        except Exception:
            pass

    # Default: first line from library message
    return (getattr(err, "message", "") or "").split("\n")[0]


def _rank_for(err) -> tuple:
    """
    Ranking for 'best' error per feature.
    Prefer Enum > (Type/Required/Const) > (Pattern/Minimum/Maximum) > others.
    """
    kind = _err_kind(err)
    order = (
        0 if kind == "Enum" else
        1 if kind in {"Type", "Required", "Const"} else
        2 if kind in {"Pattern", "Minimum", "Maximum"} else
        3
    )
    length = len(getattr(err, "message", "") or "")
    return (order, length)
