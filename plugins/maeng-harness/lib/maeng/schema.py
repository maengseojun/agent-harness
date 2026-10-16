"""Tiny JSON-schema subset validator (type, enum, required, properties, items, $ref to #/$defs)."""
from pathlib import Path

from .common import read_json

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "verdict.schema.json"
_TYPES = {"object": dict, "array": list, "string": str, "integer": int, "null": type(None), "boolean": bool}


def load_schema():
    return read_json(SCHEMA_PATH)


def validate(value, schema, root=None, path="$"):
    """Return a list of error strings (empty when valid)."""
    root = root or schema
    if "$ref" in schema:
        node = root
        for part in schema["$ref"].lstrip("#/").split("/"):
            node = node[part]
        return validate(value, node, root, path)
    errors = []
    if "enum" in schema and value not in schema["enum"]:
        return [f"{path}: {value!r} not in {schema['enum']}"]
    types = schema.get("type")
    if types:
        types = types if isinstance(types, list) else [types]
        if not any(isinstance(value, _TYPES[t]) and not (t == "integer" and isinstance(value, bool)) for t in types):
            return [f"{path}: expected {types}"]
    if isinstance(value, dict):
        for k in schema.get("required", []):
            if k not in value:
                errors.append(f"{path}.{k}: missing")
        props = schema.get("properties", {})
        for k, v in value.items():
            if k in props:
                errors += validate(v, props[k], root, f"{path}.{k}")
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}.{k}: unexpected")
    if isinstance(value, list) and "items" in schema:
        for i, v in enumerate(value):
            errors += validate(v, schema["items"], root, f"{path}[{i}]")
    return errors
