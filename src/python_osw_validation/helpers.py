from typing import Optional
import re

_ADDITIONAL_PROPERTIES_RE = re.compile(
    r"Additional properties are not allowed \('(?P<tag>[^']+)' was unexpected\)"
)
_ENUM_RE = re.compile(r'^(?P<got>.+?) is not one of (?P<allowed>.+)$')
_TYPE_RE = re.compile(r'^(?P<got>.+?) is not of type (?P<type>.+)$')


def _add_additional_properties_hint(msg: str) -> str:
    match = _ADDITIONAL_PROPERTIES_RE.search(msg)
    if not match:
        return msg
    tag = match.group("tag")
    return f"{msg}. If you want to carry this tag, change it to ext:{tag}"

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

def _friendly_enum_message(err, schema=None) -> str:
    raw = _clean_enum_message(err)
    match = _ENUM_RE.match(raw)
    if not match:
        return raw

    path = list(getattr(err, "instance_path", []) or [])
    field = path[-1] if path and isinstance(path[-1], str) else "value"
    got = match.group("got").strip('"')
    allowed = match.group("allowed")
    values = []
    if schema is not None:
        try:
            node = schema
            for seg in list(getattr(err, "schema_path", []) or []):
                node = node[seg]
            if isinstance(node, list):
                values = [str(v) for v in node]
            elif isinstance(node, dict) and isinstance(node.get("enum"), list):
                values = [str(v) for v in node["enum"]]
        except Exception:
            values = []
    if not values:
        values = re.findall(r'"([^"]+)"', allowed)
    if values:
        shown = values[:5]
        allowed_text = "|".join(shown)
        if len(values) > 5:
            allowed_text = f"{allowed_text}| and {len(values) - 5} more"
    else:
        allowed_text = allowed
    return (
        f"Invalid value at '{field}': '{got}'. "
        f"Acceptable values can be one of {allowed_text}, provide a valid value and retry again."
    )

def _friendly_type_message(err, schema) -> Optional[str]:
    raw = (getattr(err, "message", "") or "").split("\n")[0]
    if not _TYPE_RE.match(raw):
        return None

    path = list(getattr(err, "instance_path", []) or [])
    field = path[-1] if path and isinstance(path[-1], str) else "value"
    type_match = _TYPE_RE.match(raw)
    got = type_match.group("got")
    expected_type = type_match.group("type").strip('"')

    try:
        node = schema
        for seg in list(getattr(err, "schema_path", []) or []):
            node = node[seg]

        parent = None
        schema_path = list(getattr(err, "schema_path", []) or [])
        if schema_path:
            parent = schema
            for seg in schema_path[:-1]:
                parent = parent[seg]

        if isinstance(parent, dict) and isinstance(parent.get("enum"), list):
            enum_values = list(parent["enum"])
            shown = enum_values[:5]
            allowed = "|".join(str(v) for v in shown)
            if len(enum_values) > 5:
                allowed = f"{allowed}| and {len(enum_values) - 5} more"
            cleaned_got = got.strip('"')
            return (
                f"Invalid value at '{field}': '{cleaned_got}'. "
                f"Acceptable values can be one of {allowed}, provide a valid value and retry again."
            )
    except Exception:
        pass

    cleaned_got = got.strip('"')
    return (
        f"Invalid value at '{field}': '{cleaned_got}' . "
        f"Acceptable datatype is {expected_type} ; provide a valid value and retry"
    )

def _has_enum_context(err, schema) -> bool:
    """True when this error is an enum mismatch or type mismatch on an enum-constrained field."""
    if _err_kind(err) == "Enum":
        return True
    if _err_kind(err) != "Type":
        return False
    return _friendly_type_message(err, schema) is not None


def _instance_path_str(err) -> str:
    """Render jsonschema instance path as a readable JSON path."""
    path = list(getattr(err, "instance_path", []) or [])
    if not path:
        return ""

    parts = []
    for seg in path:
        if isinstance(seg, int):
            if parts:
                parts[-1] = f"{parts[-1]}[{seg}]"
            else:
                parts.append(f"[{seg}]")
        else:
            parts.append(str(seg))
    return ".".join(parts)


def _with_path(err, msg: str) -> str:
    path = _instance_path_str(err)
    if not path:
        return msg
    return f"{msg} (at: {path})"


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
        return _add_additional_properties_hint(_friendly_enum_message(err, schema))

    if kind == "Type":
        friendly_type = _friendly_type_message(err, schema)
        if friendly_type:
            return _add_additional_properties_hint(friendly_type)

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
                return _with_path(err, _add_additional_properties_hint(f"must include one of: {props}"))
        except Exception:
            pass

    # Default: first line from library message
    friendly_enum = _friendly_enum_message(err, schema)
    if friendly_enum != _clean_enum_message(err):
        return _add_additional_properties_hint(friendly_enum)

    friendly_type = _friendly_type_message(err, schema)
    if friendly_type:
        return _add_additional_properties_hint(friendly_type)

    default_msg = (getattr(err, "message", "") or "").split("\n")[0]
    return _with_path(err, _add_additional_properties_hint(default_msg))


def _rank_for(err) -> tuple:
    """
    Ranking for 'best' error per feature.
    Prefer Type/Required/Const > Enum > (Pattern/Minimum/Maximum) > others.
    """
    kind = _err_kind(err)
    order = (
        0 if kind in {"Type", "Required", "Const"} else
        1 if kind == "Enum" else
        2 if kind in {"Pattern", "Minimum", "Maximum"} else
        3
    )
    length = len(getattr(err, "message", "") or "")
    return (order, length)
