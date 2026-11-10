#!/usr/bin/env python3
"""Generate Python clients from specs/<system>/*.yaml. Does not call an LLM."""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "script"))

from sdk.spec import Operation, Param, load_documents  # noqa: E402

HEADER = '"""GENERATED from specs/{system}/*.yaml — do not edit. Re-run tools/gen_it_clients.py."""\n'


def _docstring(operation: Operation) -> str:
    lines: list[str] = []
    if operation.mutation:
        lines.append("写操作。")
    if operation.summary:
        lines.append(operation.summary)
    if operation.description and operation.description != operation.summary:
        if lines:
            lines.append("")
        lines.append(operation.description)
    paging = [param.name for param in operation.params if param.pagination]
    if paging:
        lines.append("")
        lines.append("分页参数: " + ", ".join(paging) + "。")
    field_text = ", ".join(f"{name}: {py_type}" for name, py_type in operation.response_fields)
    lines.append("")
    if operation.fields_unknown:
        lines.append(f"返回 {operation.return_type}。字段未知，先用 preview 查看真实结构。")
    elif field_text:
        lines.append(f"返回 {operation.return_type}。字段: {field_text}。")
    else:
        lines.append(f"返回 {operation.return_type}。")
    body = "\n".join(lines).replace('"""', '\\"\\"\\"')
    if "\n" not in body:
        return f'    """{body}"""'
    first, _, rest = body.partition("\n")
    indented = "\n".join(("    " + line) if line else "" for line in rest.split("\n"))
    return f'    """{first}\n{indented}\n    """'


def _signature(operation: Operation) -> str:
    parts: list[str] = []
    for param in operation.params:
        if param.required:
            parts.append(f"{param.name}: {param.py_type}")
        else:
            parts.append(f"{param.name}: {param.py_type} | None = None")
    arguments = ", ".join(parts)
    if arguments:
        arguments = "*, " + arguments
    return f"def {operation.operation_id}({arguments}) -> {operation.return_type}:"


def _mapping(params: list[Param]) -> str:
    return "{" + ", ".join(f'"{param.name}": {param.name}' for param in params) + "}"


def _call(operation: Operation) -> str:
    arguments = [
        f'"{operation.method}"',
        f'"{operation.path}"',
        f'operation="{operation.operation_id}"',
    ]
    groups = {
        "path_params": [param for param in operation.params if param.location == "path"],
        "query": [param for param in operation.params if param.location == "query"],
        "headers": [param for param in operation.params if param.location == "header"],
        "json_body": [param for param in operation.params if param.location == "body"],
        "form": [param for param in operation.params if param.location == "form"],
        "files": [param for param in operation.params if param.location == "file"],
    }
    for key, params in groups.items():
        if params:
            arguments.append(f"{key}={_mapping(params)}")
    joined = ",\n        ".join(arguments)
    return f"    return request(\n        {joined},\n    )"


def _render_module(system: str, operations: list[Operation]) -> str:
    chunks = [
        HEADER.format(system=system),
        "from __future__ import annotations\n\n",
        f"from {system}._http import request\n\n",
    ]
    for operation in operations:
        chunks.append(f"{_signature(operation)}\n{_docstring(operation)}\n{_call(operation)}\n\n")
    return "".join(chunks)


def _render_pyi(operations: list[Operation]) -> str:
    chunks = ["from __future__ import annotations\n\n"]
    for operation in operations:
        chunks.append(f"{_signature(operation)}\n{_docstring(operation)}\n    ...\n\n")
    return "".join(chunks)


def _report(skipped: list) -> str:
    if not skipped:
        return "skipped: none\n"
    lines = ["skipped:"]
    for item in skipped:
        lines.append(f"- {item.system} {item.source} {item.method} {item.path}: {item.reason}")
    return "\n".join(lines) + "\n"


def generate(root: Path | None = None) -> None:
    root = root or ROOT
    operations, skipped = load_documents(root)
    by_module: dict[tuple[str, str], list[Operation]] = defaultdict(list)
    for operation in operations:
        by_module[(operation.system, operation.module)].append(operation)

    written: set[Path] = set()
    for (system, module), group in sorted(by_module.items()):
        group.sort(key=lambda item: item.operation_id)
        directory = root / "script" / system
        directory.mkdir(parents=True, exist_ok=True)
        py_path = directory / f"{module}.py"
        pyi_path = directory / f"{module}.pyi"
        py_path.write_text(_render_module(system, group), encoding="utf-8")
        pyi_path.write_text(_render_pyi(group), encoding="utf-8")
        written.add(py_path)
        written.add(pyi_path)

    for system_dir in (root / "script").glob("*"):
        if not system_dir.is_dir() or system_dir.name in {"sdk", "__pycache__"}:
            continue
        for path in system_dir.glob("*"):
            if path.suffix not in {".py", ".pyi"} or path.name in {"_http.py", "__init__.py"}:
                continue
            if path not in written and path.read_text(encoding="utf-8").startswith('"""GENERATED'):
                path.unlink()

    (root / "script" / "gen_report.txt").write_text(_report(skipped), encoding="utf-8")


def main() -> None:
    generate()


if __name__ == "__main__":
    main()
