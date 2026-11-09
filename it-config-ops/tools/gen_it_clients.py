#!/usr/bin/env python3
"""Deterministically generate Python clients from it-config-ops YAML.

Does not call an LLM. $ref is resolved to named types (cross-file and in-file).
"""

from __future__ import annotations

import argparse
import keyword
import pprint
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"
SCRIPT_DIR = ROOT / "script"
COMMON_FILE = "common.yaml"

HEADER = '''\
"""GENERATED from schemas/*.yaml — do not edit. Re-run tools/gen_it_clients.py."""
from __future__ import annotations

'''


class SpecError(ValueError):
    pass


def load_docs() -> dict[str, Any]:
    docs: dict[str, Any] = {}
    for path in sorted(SCHEMA_DIR.glob("*.yaml")):
        with path.open(encoding="utf-8") as handle:
            docs[path.name] = yaml.safe_load(handle)
    if COMMON_FILE not in docs:
        raise SpecError(f"missing {COMMON_FILE}")
    return docs


def split_ref(ref: str) -> tuple[str | None, list[str]]:
    if not ref:
        raise SpecError("empty $ref")
    if "#" not in ref:
        return ref, []
    file_part, pointer = ref.split("#", 1)
    parts = [part for part in pointer.split("/") if part]
    return (file_part or None), parts


def lookup(doc: Any, parts: list[str]) -> Any:
    node = doc
    for part in parts:
        if not isinstance(node, dict) or part not in node:
            raise SpecError(f"unresolved pointer /{'/'.join(parts)}")
        node = node[part]
    return node


def resolve_ref(
    docs: dict[str, Any], current_file: str, ref: str, stack: tuple[str, ...] = ()
) -> tuple[str, list[str], Any]:
    file_part, parts = split_ref(ref)
    target_file = current_file if not file_part else file_part
    if target_file not in docs:
        raise SpecError(f"$ref file not loaded: {ref}")
    key = f"{target_file}#/{'/'.join(parts)}"
    if key in stack:
        raise SpecError(f"cyclic $ref: {' -> '.join(stack + (key,))}")
    node = lookup(docs[target_file], parts)
    if isinstance(node, dict) and "$ref" in node:
        return resolve_ref(docs, target_file, node["$ref"], stack + (key,))
    return target_file, parts, node


def ident(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in name)
    if not cleaned or cleaned[0].isdigit() or keyword.iskeyword(cleaned):
        cleaned = f"f_{cleaned}"
    return cleaned


def schema_type_name(file_name: str, parts: list[str]) -> str:
    if not parts:
        raise SpecError(f"anonymous $ref target in {file_name}")
    return ident(parts[-1])


def py_type(
    docs: dict[str, Any],
    current_file: str,
    schema: Any | None,
    imports: set[tuple[str, str]],
) -> str:
    if schema is None:
        return "Any"
    if not isinstance(schema, dict):
        return "Any"
    if "$ref" in schema:
        target_file, parts, _ = resolve_ref(docs, current_file, schema["$ref"])
        name = schema_type_name(target_file, parts)
        if target_file == COMMON_FILE and current_file != COMMON_FILE:
            imports.add((name, "_gen_common"))
        return name
    if "allOf" in schema:
        # Named allOf schemas are merged in emit_typed_dict. Inline allOf is not guessed.
        return "Any"
    if "enum" in schema and schema.get("type", "string") == "string":
        values = ", ".join(repr(value) for value in schema["enum"])
        return f"Literal[{values}]"
    type_name = schema.get("type")
    if type_name == "string":
        return "str"
    if type_name == "integer":
        return "int"
    if type_name == "number":
        return "float"
    if type_name == "boolean":
        return "bool"
    if type_name == "array":
        return f"list[{py_type(docs, current_file, schema.get('items'), imports)}]"
    if type_name == "object" or "properties" in schema:
        return "dict[str, Any]"
    return "Any"


def merge_all_of(
    docs: dict[str, Any], current_file: str, schema: dict[str, Any]
) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    required: list[str] = []
    description = schema.get("description")
    for member in schema["allOf"]:
        node = member
        member_file = current_file
        if isinstance(member, dict) and "$ref" in member:
            member_file, _, node = resolve_ref(docs, current_file, member["$ref"])
        if not isinstance(node, dict):
            continue
        if node.get("allOf"):
            node = merge_all_of(docs, member_file, node)
        properties.update(node.get("properties") or {})
        for name in node.get("required") or []:
            if name not in required:
                required.append(name)
        description = description or node.get("description")
    extras = {key: value for key, value in schema.items() if key != "allOf"}
    merged = {
        "type": "object",
        "properties": properties,
        "required": required,
        **extras,
    }
    if description:
        merged["description"] = description
    return merged


def named_schemas(file_name: str, doc: Any) -> dict[str, tuple[str, list[str], dict[str, Any]]]:
    found: dict[str, tuple[str, list[str], dict[str, Any]]] = {}
    if file_name == COMMON_FILE:
        schemas = (doc or {}).get("schemas") or {}
        prefix = ["schemas"]
    else:
        schemas = ((doc or {}).get("components") or {}).get("schemas") or {}
        prefix = ["components", "schemas"]
    for name, schema in schemas.items():
        if not isinstance(schema, dict):
            raise SpecError(f"{file_name} schema {name} must be a mapping")
        found[name] = (file_name, prefix + [name], schema)
    return found


def emit_typed_dict(
    docs: dict[str, Any],
    file_name: str,
    name: str,
    schema: dict[str, Any],
    imports: set[tuple[str, str]],
) -> str:
    if "allOf" in schema:
        schema = merge_all_of(docs, file_name, schema)
    if schema.get("type") == "string" or "enum" in schema:
        alias = py_type(docs, file_name, schema, imports)
        return f"{name} = {alias}\n"
    properties = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    lines = []
    description = schema.get("description")
    if description:
        lines.append(f"class {name}(TypedDict):")
        lines.append(f'    """{description}"""')
    else:
        lines.append(f"class {name}(TypedDict):")
    if not properties:
        lines.append("    pass")
        return "\n".join(lines) + "\n"
    for field, field_schema in properties.items():
        field_name = ident(field)
        annotation = py_type(docs, file_name, field_schema, imports)
        if field not in required:
            annotation = f"NotRequired[{annotation}]"
        lines.append(f"    {field_name}: {annotation}")
    return "\n".join(lines) + "\n"


def collect_type_order(
    docs: dict[str, Any], file_name: str, schemas: dict[str, tuple[str, list[str], dict[str, Any]]]
) -> list[str]:
    deps: dict[str, set[str]] = {name: set() for name in schemas}

    def walk(owner: str, current: str, node: Any, seen: set[str]) -> None:
        if not isinstance(node, dict):
            return
        if "$ref" in node:
            target_file, parts, _ = resolve_ref(docs, current, node["$ref"])
            if target_file == file_name and parts:
                dep = parts[-1]
                if dep in schemas and dep != owner:
                    deps[owner].add(dep)
            return
        if "allOf" in node:
            for member in node["allOf"]:
                walk(owner, current, member, seen)
            return
        if "items" in node:
            walk(owner, current, node["items"], seen)
        for value in (node.get("properties") or {}).values():
            walk(owner, current, value, seen)

    for name, (current, _, schema) in schemas.items():
        walk(name, current, schema, set())

    ordered: list[str] = []
    visiting: set[str] = set()
    done: set[str] = set()

    def visit(name: str) -> None:
        if name in done:
            return
        if name in visiting:
            return
        visiting.add(name)
        for dep in sorted(deps[name]):
            visit(dep)
        visiting.remove(name)
        done.add(name)
        ordered.append(name)

    for name in schemas:
        visit(name)
    return ordered


def emit_types_module(
    docs: dict[str, Any], file_name: str, schemas: dict[str, tuple[str, list[str], dict[str, Any]]]
) -> str:
    imports: set[tuple[str, str]] = set()
    blocks: list[str] = []
    for name in collect_type_order(docs, file_name, schemas):
        _, _, schema = schemas[name]
        blocks.append(emit_typed_dict(docs, file_name, ident(name), schema, imports))
    typing_imports = ["Any", "Literal", "NotRequired", "TypedDict"]
    lines = [
        HEADER,
        "from typing import " + ", ".join(typing_imports) + "\n",
    ]
    by_module: dict[str, list[str]] = defaultdict(list)
    for name, module in sorted(imports):
        by_module[module].append(name)
    for module, names in by_module.items():
        lines.append(f"from {module} import {', '.join(sorted(set(names)))}\n")
    lines.append("\n")
    lines.extend(block + "\n" for block in blocks)
    return "".join(lines)


def response_type(
    docs: dict[str, Any], file_name: str, schema: Any | None, imports: set[tuple[str, str]]
) -> str:
    if isinstance(schema, dict) and "allOf" in schema and "$ref" not in schema:
        return "dict[str, Any]"
    return py_type(docs, file_name, schema, imports)


def emit_function(
    docs: dict[str, Any],
    file_name: str,
    system: dict[str, Any],
    operation: dict[str, Any],
    imports: set[tuple[str, str]],
) -> str:
    op_id = ident(operation["id"])
    method = str(operation["method"]).upper()
    path = str(operation["path"])
    mutation = bool(operation.get("mutation"))
    description = str(operation.get("description") or op_id).replace('"', "'")
    menu_id = operation.get("menu")
    menu_title = ""
    for menu in system.get("menus") or []:
        if menu.get("id") == menu_id:
            menu_title = menu.get("title") or menu_id
    params = operation.get("params") or []
    required_args: list[str] = []
    optional_args: list[str] = []
    path_subs: list[str] = []
    query_items: list[str] = []
    body_expr = "None"
    for param in params:
        name = ident(param["name"])
        location = param.get("in")
        required = bool(param.get("required"))
        annotation = py_type(docs, file_name, param.get("schema"), imports)
        if required:
            required_args.append(f"{name}: {annotation}")
        else:
            optional_args.append(f"{name}: {annotation} | None = None")
        if location == "path":
            token = "{" + param["name"] + "}"
            if token not in path:
                raise SpecError(f"{op_id}: path missing {token}")
            path_subs.append(
                f"    path = path.replace({token!r}, quote(str({name}), safe=''))\n"
            )
        elif location == "query":
            query_items.append(f'"{param["name"]}": {name}')
        elif location == "body":
            body_expr = name
        else:
            raise SpecError(f"{op_id}: unsupported param in={location!r}")
    signature = ", ".join(["*"] + required_args + optional_args)
    if signature == "*":
        signature = ""
    ret = response_type(docs, file_name, operation.get("response"), imports)
    doc_lines = [description]
    if mutation:
        doc_lines.insert(0, "写操作。")
    if menu_title:
        doc_lines.append(f"菜单: {menu_title}")
    docstring = "\\n".join(doc_lines)
    query_expr = "{" + ", ".join(query_items) + "}" if query_items else "None"
    lines = [
        f"def {op_id}({signature}) -> {ret}:\n",
        f'    """{docstring}"""\n',
        f"    path = {path!r}\n",
        *path_subs,
        f"    return request({method!r}, _base() + path, query={query_expr}, json_body={body_expr})\n",
    ]
    return "".join(lines)


def emit_system_module(docs: dict[str, Any], file_name: str, doc: dict[str, Any]) -> str:
    system = doc["system"]
    imports: set[tuple[str, str]] = set()
    schemas = named_schemas(file_name, doc)
    type_blocks: list[str] = []
    for name in collect_type_order(docs, file_name, schemas):
        _, _, schema = schemas[name]
        type_blocks.append(emit_typed_dict(docs, file_name, ident(name), schema, imports))
        if "allOf" in schema:
            # allOf named types were merged; py_type of the name itself is the class.
            pass
    functions = [
        emit_function(docs, file_name, system, operation, imports)
        for operation in doc.get("operations") or []
    ]
    env_name = system["base_env"]
    typing_names = ["Any", "Literal", "NotRequired", "TypedDict"]
    lines = [
        HEADER,
        "from os import environ\n",
        "from urllib.parse import quote\n\n",
        "from _http import request\n",
        "from typing import " + ", ".join(typing_names) + "\n",
    ]
    by_module: dict[str, list[str]] = defaultdict(list)
    for name, module in sorted(imports):
        by_module[module].append(name)
    for module, names in by_module.items():
        lines.append(f"from {module} import {', '.join(sorted(set(names)))}\n")
    lines.append("\n")
    lines.append(f"def _base() -> str:\n")
    lines.append(f"    value = environ.get({env_name!r}, '').rstrip('/')\n")
    lines.append(f"    if not value:\n")
    lines.append(f"        raise RuntimeError({env_name!r} + ' is not set')\n")
    lines.append("    return value\n\n")
    for block in type_blocks:
        lines.append(block + "\n")
    for function in functions:
        lines.append(function + "\n")
    return "".join(lines)


def emit_catalog(docs: dict[str, Any]) -> str:
    catalog: dict[str, Any] = {}
    for file_name, doc in docs.items():
        if file_name == COMMON_FILE:
            continue
        system = doc["system"]
        menus = {}
        for menu in system.get("menus") or []:
            menus[menu["id"]] = {
                "title": menu.get("title") or menu["id"],
                "operations": [],
            }
        for operation in doc.get("operations") or []:
            menu_id = operation.get("menu")
            if menu_id not in menus:
                menus[menu_id] = {"title": menu_id, "operations": []}
            menus[menu_id]["operations"].append(
                {
                    "id": operation["id"],
                    "mutation": bool(operation.get("mutation")),
                    "summary": operation.get("description") or operation["id"],
                }
            )
        catalog[system["id"]] = {
            "title": system["title"],
            "domain": system["domain"],
            "module": system["id"],
            "base_env": system["base_env"],
            "menus": menus,
        }
    dumped = pprint.pformat(catalog, width=88, sort_dicts=False)
    return (
        HEADER
        + "from typing import Any\n\n"
        + f"CATALOG: dict[str, Any] = {dumped}\n\n"
        + '''\
def systems_for_domain(domain: str) -> list[str]:
    return [name for name, spec in CATALOG.items() if spec["domain"] == domain]


def operations_for_menu(menu_title: str) -> list[dict[str, Any]]:
    """Resolve a user-facing menu name (or id) to operations across systems."""
    found: list[dict[str, Any]] = []
    needle = menu_title.strip()
    for system_id, spec in CATALOG.items():
        for menu_id, menu in spec["menus"].items():
            if needle in {menu_id, menu["title"], f"{spec['title']}/{menu['title']}"}:
                for operation in menu["operations"]:
                    found.append({
                        "system": system_id,
                        "module": spec["module"],
                        "domain": spec["domain"],
                        "menu": menu["title"],
                        **operation,
                    })
    return found
'''
    )


def write_if_changed(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")


def generate() -> list[str]:
    docs = load_docs()
    written: list[str] = []
    common = emit_types_module(docs, COMMON_FILE, named_schemas(COMMON_FILE, docs[COMMON_FILE]))
    write_if_changed(SCRIPT_DIR / "_gen_common.py", common)
    written.append("_gen_common.py")
    for file_name, doc in docs.items():
        if file_name == COMMON_FILE:
            continue
        if "system" not in doc:
            raise SpecError(f"{file_name} missing system:")
        module = ident(doc["system"]["id"])
        write_if_changed(SCRIPT_DIR / f"{module}.py", emit_system_module(docs, file_name, doc))
        written.append(f"{module}.py")
    write_if_changed(SCRIPT_DIR / "catalog.py", emit_catalog(docs))
    written.append("catalog.py")
    return written


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    try:
        written = generate()
    except SpecError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    print("wrote " + ", ".join(written))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
