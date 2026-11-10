"""Search local OpenAPI docs. The full document stays on disk."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sdk.spec import load_documents

MAX_MATCHES = 20


def find(system: str, query: str, root: Path | None = None) -> list[dict[str, Any]]:
    """Return up to 20 operations whose id, summary, description, path, or tag contains query."""
    needle = query.casefold().strip()
    if not needle:
        return []
    operations, _skipped = load_documents(root)
    matches = []
    for operation in operations:
        if operation.system != system:
            continue
        haystack = "\n".join((
            operation.operation_id,
            operation.summary,
            operation.description,
            operation.path,
            " ".join(operation.tags),
        )).casefold()
        if needle not in haystack:
            continue
        matches.append({
            "id": operation.operation_id,
            "method": operation.method,
            "path": operation.path,
            "module": f"{operation.system}.{operation.module}",
            "params": [param.name for param in operation.params],
            "mutation": operation.mutation,
            "fields_unknown": operation.fields_unknown,
            "summary": operation.summary[:200],
        })
    return matches[:MAX_MATCHES]
