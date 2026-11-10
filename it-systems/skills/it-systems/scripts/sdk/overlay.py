"""Allow-list applied on top of a vendor OpenAPI document.

The YAML under specs/ stays untouched. An operation becomes a stub only when
overlays/<system>.yaml names its operationId or its method and path. find()
reads the same filtered list, so a trimmed operation cannot be discovered later.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sdk.spec import METHODS, SpecError


@dataclass(frozen=True)
class Include:
    operation_id: str | None
    method: str | None
    path: str | None

    def label(self) -> str:
        parts: list[str] = []
        if self.operation_id:
            parts.append(f"operationId={self.operation_id}")
        if self.method:
            parts.append(self.method)
        if self.path:
            parts.append(self.path)
        return " ".join(parts)


@dataclass(frozen=True)
class Overlay:
    source: str
    entries: tuple[Include, ...]

    def matching(self, method: str, path: str, operation_id: str) -> tuple[int, ...]:
        hits: list[int] = []
        for index, entry in enumerate(self.entries):
            if entry.operation_id is not None and entry.operation_id != operation_id:
                continue
            if entry.method is not None and entry.method != method.upper():
                continue
            if entry.path is not None and entry.path != path:
                continue
            hits.append(index)
        return tuple(hits)


def overlay_path(root: Path, system: str) -> Path:
    return root / "overlays" / f"{system}.yaml"


def load_overlay(root: Path, system: str) -> Overlay | None:
    """Return None when this system has no overlay file."""
    path = overlay_path(root, system)
    if not path.is_file():
        return None
    import yaml

    with path.open(encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    if not isinstance(document, dict):
        raise SpecError(f"{path.name}: overlay is not a mapping")
    if document.get("overlay") != 1:
        raise SpecError(f"{path.name}: overlay must set overlay: 1")
    unknown = set(document) - {"overlay", "include", "info"}
    if unknown:
        raise SpecError(f"{path.name}: unknown overlay fields: {', '.join(sorted(unknown))}")
    if "info" in document and not isinstance(document["info"], dict):
        raise SpecError(f"{path.name}: info is not a mapping")
    include = document.get("include")
    if not isinstance(include, list):
        raise SpecError(f"{path.name}: include must be a list")
    entries: list[Include] = []
    for index, raw in enumerate(include, start=1):
        entries.append(_entry(path.name, index, raw))
    return Overlay(path.name, tuple(entries))


def _entry(source: str, index: int, raw: object) -> Include:
    if not isinstance(raw, dict):
        raise SpecError(f"{source}: include[{index}] is not a mapping")
    unknown = set(raw) - {"operationId", "method", "path"}
    if unknown:
        raise SpecError(f"{source}: include[{index}] has unknown fields: {', '.join(sorted(unknown))}")
    operation_id = raw.get("operationId")
    method = raw.get("method")
    path = raw.get("path")
    if operation_id is not None and (not isinstance(operation_id, str) or not operation_id):
        raise SpecError(f"{source}: include[{index}] operationId is empty")
    if method is not None:
        if not isinstance(method, str) or method.lower() not in METHODS:
            raise SpecError(f"{source}: include[{index}] method is not an HTTP method")
        method = method.upper()
    if path is not None and (not isinstance(path, str) or not path.startswith("/")):
        raise SpecError(f"{source}: include[{index}] path must start with /")
    if operation_id is None and (method is None or path is None):
        raise SpecError(f"{source}: include[{index}] needs operationId or method and path")
    return Include(operation_id, method, path)
