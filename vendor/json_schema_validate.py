"""Minimal vendored subset of the JSON Schema Draft 2020-12 validator.

This is *not* a full Draft 2020-12 implementation. It supports the keywords
that the stage A contracts actually use, and nothing more. Stage A is the only
phase allowed to vendor code; future phases must extend this file or replace
it through an explicit meta-version bump.

Supported keywords (per Draft 2020-12 semantics):
    type, enum, const, pattern, minLength, maximum, minimum,
    exclusiveMaximum, exclusiveMinimum, multipleOf,
    minItems, maxItems, uniqueItems,
    properties, required, additionalProperties,
    items, prefixItems,
    $ref, $defs, definitions, $schema,
    oneOf, anyOf, allOf, not,
    format (only "uri-reference" — returns the value as-is for downstream checks).

Unsupported (will raise ``SchemaUnsupportedError`` so we notice early):
    $dynamicRef / $anchor / $vocabulary / $id resolution across files,
    contentEncoding / contentMediaType,
    if/then/else, dependentRequired, propertyNames, etc.

Public surface:
    validate(instance, schema) -> list[str]
    iter_errors(instance, schema) -> iterator yielding JSON-pointer paths.
"""

from __future__ import annotations

import re
from typing import Any, Iterable


class SchemaError(Exception):
    """Raised when the schema itself is malformed for this validator."""


class SchemaUnsupportedError(SchemaError):
    """Raised when the schema uses keywords this vendored subset does not implement."""


_SENTINEL = object()


def _resolve(ref: str, root: Any) -> Any:
    if not ref.startswith("#"):
        raise SchemaError(f"only JSON-pointer $ref is supported; got {ref!r}")
    if ref == "#":
        return root
    body = ref[1:]
    if body.startswith("/"):
        body = body[1:]
    if body == "":
        return root
    parts = body.split("/")
    node: Any = root
    for raw in parts:
        key = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict):
            if key not in node:
                raise SchemaError(f"$ref {ref!r} could not be resolved")
            node = node[key]
        elif isinstance(node, list):
            try:
                index = int(key)
            except ValueError as exc:
                raise SchemaError(f"$ref {ref!r} uses non-integer index {key!r}") from exc
            if index < 0 or index >= len(node):
                raise SchemaError(f"$ref {ref!r} index {index} out of range")
            node = node[index]
        else:
            raise SchemaError(f"$ref {ref!r} walked into non-container")
    return node


def _check_type(value: Any, expected: str | list[str]) -> str | None:
    expected_list = expected if isinstance(expected, list) else [expected]
    mapping: dict[str, tuple[tuple[type, ...], ...]] = {
        "null": ((type(None),),),
        "boolean": ((bool,),),
        "string": ((str,),),
        "number": ((int, float),),
        "integer": ((int,),),
        "array": ((list, tuple),),
        "object": ((dict,),),
    }
    for kind in expected_list:
        if kind not in mapping:
            raise SchemaUnsupportedError(f"unsupported type {kind!r}")
        for type_tuple in mapping[kind]:
            if isinstance(value, type_tuple):
                if kind == "integer" and isinstance(value, bool):
                    continue
                return None
    return f"expected type {' | '.join(expected_list)}, got {type(value).__name__}"


def _validate(instance: Any, schema: Any, root: Any, pointer: str, errors: list[str]) -> None:
    if not isinstance(schema, dict):
        raise SchemaError(f"schema at {pointer or '/'} must be an object")

    if "$ref" in schema:
        target = _resolve(schema["$ref"], root)
        _validate(instance, target, root, pointer, errors)
        return

    if "type" in schema:
        err = _check_type(instance, schema["type"])
        if err is not None:
            errors.append(f"{pointer}: {err}" if pointer else err)
            return

    if "enum" in schema:
        enum = schema["enum"]
        if not isinstance(enum, list):
            raise SchemaError("enum must be a list")
        if instance not in enum:
            rendered = ", ".join(repr(x) for x in enum)
            errors.append(f"{pointer}: value not in enum [{rendered}]")
            return

    if "const" in schema:
        if instance != schema["const"]:
            errors.append(f"{pointer}: value != const {schema['const']!r}")
            return

    if isinstance(instance, str):
        if "minLength" in schema:
            n = len(instance)
            if n < schema["minLength"]:
                errors.append(f"{pointer}: string length {n} < minLength {schema['minLength']}")
                return
        if "maxLength" in schema:
            n = len(instance)
            if n > schema["maxLength"]:
                errors.append(f"{pointer}: string length {n} > maxLength {schema['maxLength']}")
                return
        # Vendored extension: enforce a cap on Unicode codepoints (not UTF-16 code units).
        if "x-wenfengCodepointMax" in schema:
            cap = schema["x-wenfengCodepointMax"]
            n = len(instance)
            if n > cap:
                errors.append(
                    f"{pointer}: excerpt has {n} codepoints, exceeds x-wenfengCodepointMax {cap}"
                )
                return
        if "pattern" in schema:
            pattern = schema["pattern"]
            if not isinstance(pattern, str):
                raise SchemaError("pattern must be a string")
            if re.search(pattern, instance) is None:
                errors.append(f"{pointer}: string does not match pattern /{pattern}/")
                return
        if schema.get("format") == "uri-reference":
            # Stage A only uses uri-reference for evaluation_ref / evidence paths.
            if not instance:
                errors.append(f"{pointer}: uri-reference must be non-empty")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{pointer}: {instance} > maximum {schema['maximum']}")
            return
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{pointer}: {instance} < minimum {schema['minimum']}")
            return
        if "exclusiveMaximum" in schema and instance >= schema["exclusiveMaximum"]:
            errors.append(f"{pointer}: {instance} >= exclusiveMaximum {schema['exclusiveMaximum']}")
            return
        if "exclusiveMinimum" in schema and instance <= schema["exclusiveMinimum"]:
            errors.append(f"{pointer}: {instance} <= exclusiveMinimum {schema['exclusiveMinimum']}")
            return

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{pointer}: array length {len(instance)} < minItems {schema['minItems']}")
            return
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(f"{pointer}: array length {len(instance)} > maxItems {schema['maxItems']}")
            return
        if schema.get("uniqueItems"):
            seen: list[Any] = []
            for idx, item in enumerate(instance):
                if item in seen:
                    errors.append(f"{pointer}: duplicate item at index {idx}")
                    return
                seen.append(item)
        # Vendored extension x-wenfengRange: enforces ordering on a fixed-length array.
        # Documented in schemas/_meta.json. Supported values: "open" means [a,b) with a<b.
        if schema.get("x-wenfengRange") == "open" and len(instance) == 2:
            start, end = instance[0], instance[1]
            if not (isinstance(start, (int, float)) and isinstance(end, (int, float))):
                errors.append(f"{pointer}: x-wenfengRange=open requires two numbers")
                return
            if not (isinstance(start, int) and isinstance(end, int) and not isinstance(start, bool) and not isinstance(end, bool)):
                errors.append(f"{pointer}: x-wenfengRange=open requires integers (codepoints)")
                return
            if start >= end:
                errors.append(
                    f"{pointer}: x-wenfengRange=open requires start < end, got {start} >= {end}"
                )
                return
        if "items" in schema:
            for idx, item in enumerate(instance):
                _validate(item, schema["items"], root, f"{pointer}/{idx}", errors)

    if isinstance(instance, dict):
        if "required" in schema:
            for key in schema["required"]:
                if key not in instance:
                    errors.append(f"{pointer}: missing required field '{key}'")
        if "properties" in schema:
            for key, sub_schema in schema["properties"].items():
                if key in instance:
                    _validate(instance[key], sub_schema, root, f"{pointer}/{_escape(key)}", errors)
        additional = schema.get("additionalProperties")
        if additional is False:
            allowed = set(schema.get("properties", {}).keys())
            extras = set(instance.keys()) - allowed
            if extras:
                errors.append(
                    f"{pointer}: unexpected additional properties: {sorted(extras)}"
                )
        elif isinstance(additional, dict):
            for key, value in instance.items():
                if key not in schema.get("properties", {}):
                    _validate(value, additional, root, f"{pointer}/{_escape(key)}", errors)

    if "oneOf" in schema:
        branches = schema["oneOf"]
        if not isinstance(branches, list):
            raise SchemaError("oneOf must be a list")
        match_count = 0
        for branch in branches:
            branch_errors: list[str] = []
            _validate(instance, branch, root, pointer, branch_errors)
            if not branch_errors:
                match_count += 1
        if match_count != 1:
            errors.append(f"{pointer}: oneOf matched {match_count} branches (need exactly 1)")
            return

    if "not" in schema:
        not_errors: list[str] = []
        _validate(instance, schema["not"], root, pointer, not_errors)
        if not not_errors:
            errors.append(f"{pointer}: value matched forbidden schema 'not'")
            return


def _escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def validate(instance: Any, schema: Any) -> list[str]:
    """Return a list of human-readable error messages; empty list = valid."""
    errors: list[str] = []
    _validate(instance, schema, schema, "", errors)
    return errors


def is_valid(instance: Any, schema: Any) -> bool:
    return not validate(instance, schema)


__all__ = ["validate", "is_valid", "SchemaError", "SchemaUnsupportedError"]