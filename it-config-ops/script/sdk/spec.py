"""Load OpenAPI 3 operations from specs/<system>/*.yaml.

The generator and find() both use this parser so the call surface and the
search index cannot drift. External $ref and missing operationId are skipped,
not guessed.
"""

from __future__ import annotations

import keyword
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

METHODS = ("get", "post", "put", "patch", "delete")
PAGINATION_NAMES = {"page", "pagenum", "pagesize", "cursor", "limit", "offset"}
QUERY_TOKENS = {"get", "list", "query", "search", "find", "page"}
SECRET_HEADER_NAMES = {"cookie", "authorization", "proxy-authorization"}


class SpecError(ValueError):
    pass


@dataclass(frozen=True)
class Param:
    name: str
    location: str  # path, query, header, body, form, file
    py_type: str
    required: bool
    pagination: bool


@dataclass(frozen=True)
class Operation:
    system: str
    module: str
    operation_id: str
    method: str
    path: str
    summary: str
    description: str
    tags: tuple[str, ...]
    params: tuple[Param, ...]
    mutation: bool
    fields_unknown: bool
    return_type: str
    response_fields: tuple[tuple[str, str], ...]
    source: str


@dataclass(frozen=True)
class Skip:
    system: str
    source: str
    method: str
    path: str
    reason: str


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _snake(name: str) -> str:
    chars: list[str] = []
    for index, char in enumerate(name):
        if char.isupper() and index and (
            name[index - 1].islower() or (index + 1 < len(name) and name[index + 1].islower())
        ):
            chars.append("_")
        chars.append(char.lower() if char.isalnum() else "_")
    text = "".join(chars).strip("_")
    while "__" in text:
        text = text.replace("__", "_")
    if not text or text[0].isdigit() or keyword.iskeyword(text):
        text = f"api_{text}"
    return text


def module_name(path: str) -> str:
    segment = next((part for part in path.split("/") if part and "{" not in part), "api")
    return _snake(segment)


def _ident(name: str) -> bool:
    return name.isidentifier() and not keyword.iskeyword(name)


def _unquote(part: str) -> str:
    return part.replace("~1", "/").replace("~0", "~")


def _resolve(doc: dict[str, Any], node: Any, seen: tuple[str, ...] = ()) -> Any:
    if not isinstance(node, dict) or "$ref" not in node:
        return node
    ref = node["$ref"]
    if not isinstance(ref, str) or not ref.startswith("#/"):
        raise SpecError(f"external $ref is not resolved: {ref}")
    if ref in seen:
        raise SpecError(f"cyclic $ref: {ref}")
    target: Any = doc
    for raw in ref[2:].split("/"):
        part = _unquote(raw)
        if not isinstance(target, dict) or part not in target:
            raise SpecError(f"unresolved $ref: {ref}")
        target = target[part]
    return _resolve(doc, target, seen + (ref,))


def _merge_object(doc: dict[str, Any], schema: Any) -> dict[str, Any]:
    schema = _resolve(doc, schema)
    if not isinstance(schema, dict):
        raise SpecError("schema is not an object")
    if "allOf" in schema:
        merged: dict[str, Any] = {"type": "object", "properties": {}, "required": []}
        for part in schema["allOf"]:
            piece = _merge_object(doc, part)
            merged["properties"].update(piece.get("properties") or {})
            merged["required"].extend(piece.get("required") or [])
        return merged
    if "oneOf" in schema or "anyOf" in schema:
        raise SpecError("ambiguous oneOf/anyOf schema")
    return schema


def _py_type(schema: Any) -> str:
    if not isinstance(schema, dict):
        return "Any"
    kind = schema.get("type")
    if isinstance(kind, list):
        return "Any"
    if schema.get("format") == "binary":
        return "str"
    return {
        "string": "str",
        "integer": "int",
        "number": "float",
        "boolean": "bool",
        "array": "list",
        "object": "dict",
    }.get(kind, "Any")


def _first_token(operation_id: str) -> str:
    match = re.split(r"(?=[A-Z])|[_\-]", operation_id, maxsplit=1)
    return (match[0] if match else operation_id).lower()


def is_mutation(method: str, operation_id: str, path: str) -> bool:
    method = method.lower()
    if method == "get":
        return False
    if method in {"put", "patch", "delete"}:
        return True
    if method != "post":
        return False
    tail = path.rstrip("/").split("/")[-1].lower()
    return _first_token(operation_id) not in QUERY_TOKENS and tail not in QUERY_TOKENS


def _response(doc: dict[str, Any], operation: dict[str, Any]) -> tuple[str, bool, tuple[tuple[str, str], ...]]:
    responses = operation.get("responses") or {}
    payload = responses.get("200") or responses.get(200) or responses.get("201") or responses.get(201) or {}
    content = (payload.get("content") or {}).get("application/json") or {}
    if "schema" not in content:
        return "dict", True, ()
    try:
        schema = _merge_object(doc, content["schema"])
    except SpecError:
        return "Any", True, ()
    kind = schema.get("type")
    if kind == "array":
        items = schema.get("items") or {}
        try:
            items = _merge_object(doc, items) if items else {}
        except SpecError:
            items = {}
        fields = _properties(items) if items.get("type") == "object" else ()
        unknown = items.get("type") == "object" and not fields
        return "list", unknown, fields
    if kind == "object":
        fields = _properties(schema)
        return "dict", not fields, fields
    return _py_type(schema), False, ()


def _properties(schema: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    props = schema.get("properties") or {}
    if not isinstance(props, dict) or not props:
        return ()
    return tuple((name, _py_type(value if isinstance(value, dict) else {})) for name, value in props.items())


def _parameter(doc: dict[str, Any], raw: Any) -> Param | None:
    try:
        item = _resolve(doc, raw)
    except SpecError as err:
        raise SpecError(str(err)) from err
    if not isinstance(item, dict):
        raise SpecError("parameter is not an object")
    name = item.get("name")
    location = item.get("in")
    if not isinstance(name, str) or not isinstance(location, str):
        raise SpecError("parameter missing name or in")
    if location == "header" and name.lower() in SECRET_HEADER_NAMES:
        return None
    if not _ident(name):
        raise SpecError(f"parameter name is not a Python identifier: {name}")
    schema = item.get("schema") or {}
    try:
        schema = _resolve(doc, schema)
    except SpecError as err:
        raise SpecError(str(err)) from err
    required = bool(item.get("required")) or location == "path"
    py_type = _py_type(schema if isinstance(schema, dict) else {})
    if location == "header":
        where = "header"
    elif location in {"path", "query"}:
        where = location
    else:
        raise SpecError(f"unsupported parameter location: {location}")
    return Param(name, where, py_type, required, name.lower() in PAGINATION_NAMES)


def _body_params(doc: dict[str, Any], operation: dict[str, Any]) -> list[Param]:
    body = operation.get("requestBody")
    if not body:
        return []
    body = _resolve(doc, body)
    if not isinstance(body, dict):
        raise SpecError("requestBody is not an object")
    content = body.get("content") or {}
    if not isinstance(content, dict):
        raise SpecError("requestBody content is not an object")
    kinds = [key for key in ("multipart/form-data", "application/json") if key in content]
    if len(kinds) != 1:
        if not kinds:
            raise SpecError("requestBody has no json or multipart schema")
        raise SpecError("requestBody has both json and multipart schemas")
    media = content[kinds[0]] or {}
    schema = _merge_object(doc, media.get("schema") or {"type": "object"})
    required_body = bool(body.get("required"))
    props = schema.get("properties") or {}
    required_names = set(schema.get("required") or [])
    if not props:
        if kinds[0] == "multipart/form-data":
            raise SpecError("multipart body has no properties")
        return [Param("body", "body", "dict", required_body, False)]
    params: list[Param] = []
    for name, raw in props.items():
        if not _ident(name):
            raise SpecError(f"body field is not a Python identifier: {name}")
        field = _resolve(doc, raw)
        if not isinstance(field, dict):
            field = {}
        binary = field.get("format") == "binary" or (
            kinds[0] == "multipart/form-data" and field.get("type") == "string" and field.get("format") == "binary"
        )
        if kinds[0] == "multipart/form-data" and (binary or field.get("format") == "binary"):
            location = "file"
            py_type = "str"
        elif kinds[0] == "multipart/form-data":
            location = "form"
            py_type = _py_type(field)
        else:
            location = "body"
            py_type = _py_type(field)
        params.append(Param(name, location, py_type, name in required_names or required_body and name in required_names, False))
    # A required requestBody does not make every property required. Only schema.required does.
    # Recompute: required iff listed in schema.required. If the list is empty and the body is
    # required with a single file (the upload sample has no required array), treat every
    # property as required when requestBody.required is true and schema.required is absent.
    if "required" not in schema and required_body:
        params = [Param(p.name, p.location, p.py_type, True, p.pagination) for p in params]
    else:
        params = [
            Param(p.name, p.location, p.py_type, p.name in required_names, p.pagination) for p in params
        ]
    return params


def _collect_parameters(doc: dict[str, Any], path_item: dict[str, Any], operation: dict[str, Any]) -> list[Param]:
    merged: dict[tuple[str, str], Param] = {}
    for source in (path_item.get("parameters") or [], operation.get("parameters") or []):
        for raw in source:
            param = _parameter(doc, raw)
            if param is None:
                continue
            merged[(param.location, param.name)] = param
    params = list(merged.values())
    params.extend(_body_params(doc, operation))
    return params


def _ordered(path: str, params: list[Param]) -> tuple[Param, ...]:
    path_names = re.findall(r"\{([^{}]+)\}", path)

    def rank(param: Param) -> tuple[int, int, str]:
        if param.location == "path":
            index = path_names.index(param.name) if param.name in path_names else len(path_names)
            return (0 if param.required else 1, index, param.name)
        location_order = {"query": 1, "header": 2, "body": 3, "form": 4, "file": 5}
        return (0 if param.required else 1, location_order.get(param.location, 9), param.name)

    return tuple(sorted(params, key=rank))


def load_documents(root: Path | None = None) -> tuple[list[Operation], list[Skip]]:
    root = root or repo_root()
    specs = root / "specs"
    operations: list[Operation] = []
    skipped: list[Skip] = []
    if not specs.is_dir():
        return [], [Skip("", "", "", "", f"missing specs directory: {specs}")]
    for system_dir in sorted(path for path in specs.iterdir() if path.is_dir()):
        system = system_dir.name
        for spec_path in sorted(system_dir.glob("*.yaml")):
            with spec_path.open(encoding="utf-8") as handle:
                document = yaml.safe_load(handle)
            if not isinstance(document, dict):
                skipped.append(Skip(system, spec_path.name, "", "", "document is not a mapping"))
                continue
            paths = document.get("paths") or {}
            if not isinstance(paths, dict):
                skipped.append(Skip(system, spec_path.name, "", "", "paths is not a mapping"))
                continue
            for path, path_item in paths.items():
                if not isinstance(path_item, dict):
                    skipped.append(Skip(system, spec_path.name, "", str(path), "path item is not a mapping"))
                    continue
                for method in METHODS:
                    if method not in path_item:
                        continue
                    operation = path_item[method]
                    if not isinstance(operation, dict):
                        skipped.append(Skip(system, spec_path.name, method, str(path), "operation is not a mapping"))
                        continue
                    operation_id = operation.get("operationId")
                    if not isinstance(operation_id, str) or not operation_id:
                        skipped.append(Skip(system, spec_path.name, method, str(path), "missing operationId"))
                        continue
                    if not _ident(operation_id):
                        skipped.append(Skip(system, spec_path.name, method, str(path), "operationId is not a Python identifier"))
                        continue
                    try:
                        params = _ordered(str(path), _collect_parameters(document, path_item, operation))
                        return_type, unknown, fields = _response(document, operation)
                    except SpecError as err:
                        skipped.append(Skip(system, spec_path.name, method, str(path), str(err)))
                        continue
                    tags = tuple(tag for tag in (operation.get("tags") or []) if isinstance(tag, str))
                    operations.append(Operation(
                        system=system,
                        module=module_name(str(path)),
                        operation_id=operation_id,
                        method=method.upper(),
                        path=str(path),
                        summary=str(operation.get("summary") or ""),
                        description=str(operation.get("description") or ""),
                        tags=tags,
                        params=params,
                        mutation=is_mutation(method, operation_id, str(path)),
                        fields_unknown=unknown,
                        return_type=return_type,
                        response_fields=fields,
                        source=spec_path.name,
                    ))
    seen: set[tuple[str, str]] = set()
    unique: list[Operation] = []
    for operation in operations:
        key = (operation.system, operation.operation_id)
        if key in seen:
            skipped.append(Skip(
                operation.system, operation.source, operation.method, operation.path,
                f"duplicate operationId {operation.operation_id}",
            ))
            continue
        seen.add(key)
        unique.append(operation)
    unique.sort(key=lambda item: (item.system, item.module, item.operation_id))
    skipped.sort(key=lambda item: (item.system, item.source, item.path, item.method, item.reason))
    return unique, skipped
