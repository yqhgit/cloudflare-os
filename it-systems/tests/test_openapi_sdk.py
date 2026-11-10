"""Acceptance tests for the OpenAPI client, per-system transport, and sandbox helpers."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "it-systems"
SCRIPT = SKILL / "scripts"

import sys

sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(SCRIPT))

import gen_it_clients  # noqa: E402
from config.campaigns import getCampaign, listCampaigns  # noqa: E402
from config.cert_file_service import uploadFile  # noqa: E402
from config.labels import createLabel  # noqa: E402
from sdk import emit, find, pages, preview  # noqa: E402
from sdk.preview import TRUNCATION_MARK  # noqa: E402
from sdk.spec import SpecError, load_documents  # noqa: E402


def _generated_sources() -> list[Path]:
    paths = []
    for directory in (SCRIPT / "config", SCRIPT / "analytics"):
        paths.extend(directory.glob("*.py"))
        paths.extend(directory.glob("*.pyi"))
    return [path for path in paths if path.name not in {"_http.py", "__init__.py"}]


class GeneratorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        gen_it_clients.generate(SKILL)

    def test_byte_stable(self) -> None:
        before = {path: path.read_bytes() for path in _generated_sources()}
        report = (SKILL / "gen_report.txt").read_bytes()
        gen_it_clients.generate(SKILL)
        after = {path: path.read_bytes() for path in _generated_sources()}
        self.assertEqual(before, after)
        self.assertEqual(report, (SKILL / "gen_report.txt").read_bytes())

    def test_upload_file_contract(self) -> None:
        source = (SCRIPT / "config" / "cert_file_service.py").read_text(encoding="utf-8")
        evidence = (SCRIPT / "config" / "evidence_file_service.py").read_text(encoding="utf-8")
        self.assertIn('"/evidenceFileService/uploadFile"', evidence)
        self.assertIn("def uploadFile(", evidence)
        self.assertIn('files={"file": file}', source)
        self.assertIn("-> dict", source)
        self.assertTrue(uploadFile.__doc__.startswith("写操作。"))
        self.assertIn("字段未知，先用 preview", uploadFile.__doc__)
        self.assertNotIn("localhost", source)
        self.assertNotIn("Cookie", source)
        self.assertNotIn("Authorization", source)

    def test_missing_operation_id_is_skipped(self) -> None:
        report = (SKILL / "gen_report.txt").read_text(encoding="utf-8")
        self.assertIn("missing operationId", report)
        self.assertIn("/noId/ping", report)
        names = " ".join(path.name for path in _generated_sources())
        self.assertNotIn("no_id", names)

    def test_pagination_params_are_explicit(self) -> None:
        self.assertIn("page", listCampaigns.__annotations__)
        self.assertIn("pageSize", listCampaigns.__annotations__)
        self.assertNotIn("page", getCampaign.__annotations__)
        self.assertNotIn("pageSize", getCampaign.__annotations__)
        self.assertIn("分页参数: page, pageSize", listCampaigns.__doc__)

    def test_servers_url_is_not_used(self) -> None:
        for path in _generated_sources():
            self.assertNotIn("localhost", path.read_text(encoding="utf-8"))

    def test_search_post_is_not_a_mutation(self) -> None:
        from analytics.funnels import searchFunnels
        self.assertFalse(searchFunnels.__doc__.startswith("写操作。"))

    def test_local_ref_is_inlined(self) -> None:
        self.assertEqual(getCampaign.__annotations__["id"], "str")

    def test_overlay_drops_unlisted_operation(self) -> None:
        report = (SKILL / "gen_report.txt").read_text(encoding="utf-8")
        self.assertIn("/admin/rebuildIndex", report)
        self.assertIn("excluded by overlay", report)
        names = " ".join(path.name for path in _generated_sources())
        self.assertNotIn("admin", names)
        self.assertEqual(find("重建", root=SKILL), [])


class _Response:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return self.payload

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *args: object) -> bool:
        return False


class TransportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.captured: list[urllib.request.Request] = []
        self.environ = mock.patch.dict(os.environ, {"IT_CONFIG_BASE": "https://config.example/productuom"}, clear=False)
        self.environ.start()
        os.environ.pop("IT_ANALYTICS_BASE", None)

    def tearDown(self) -> None:
        self.environ.stop()

    def _urlopen(self, payload: bytes = b'{"ok": true}', status: int | None = None):
        def urlopen(req: urllib.request.Request, timeout: int = 0):
            self.captured.append(req)
            if status is not None:
                raise urllib.error.HTTPError(
                    req.full_url, status, "error", hdrs=None, fp=io.BytesIO(payload),
                )
            return _Response(payload)
        return urlopen

    def test_upload_is_multipart_without_cookie(self) -> None:
        os.environ["COOKIE"] = "session=secret"
        os.environ["Authorization"] = "Bearer secret"
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "card.bin"
            target.write_bytes(b"png-bytes")
            with mock.patch("sdk.transport.urllib.request.urlopen", self._urlopen()):
                uploadFile(file=str(target))
                from config._http import request
                request(
                    "POST", "/certFileService/uploadFile", operation="uploadFile",
                    files={"file": str(target)}, headers={"Cookie": "a=b", "X-Route": "east"},
                )
        generated = self.captured[0]
        direct = self.captured[1]
        self.assertTrue(generated.full_url.startswith(
            "https://config.example/productuom/certFileService/uploadFile"))
        self.assertNotIn("localhost", generated.full_url)
        self.assertFalse(generated.has_header("Cookie"))
        self.assertFalse(direct.has_header("Cookie"))
        self.assertFalse(direct.has_header("Authorization"))
        self.assertEqual(direct.get_header("X-route"), "east")
        self.assertIn(b"png-bytes", generated.data or b"")
        content_type = generated.get_header("Content-type") or ""
        self.assertTrue(content_type.startswith("multipart/form-data"))

    def test_path_is_encoded_and_optional_query_is_omitted(self) -> None:
        with mock.patch("sdk.transport.urllib.request.urlopen", self._urlopen()):
            getCampaign(id="a/b")
            listCampaigns(status="open")
        self.assertIn("/campaigns/a%2Fb", self.captured[0].full_url)
        self.assertNotIn("page=", self.captured[1].full_url)
        self.assertIn("status=open", self.captured[1].full_url)

    def test_json_body_drops_none(self) -> None:
        with mock.patch("sdk.transport.urllib.request.urlopen", self._urlopen()):
            createLabel(name="vip")
        body = json.loads(self.captured[0].data.decode())
        self.assertEqual(body, {"name": "vip"})

    def test_forbidden_is_the_response_text(self) -> None:
        with mock.patch("sdk.transport.urllib.request.urlopen", self._urlopen(b"no menu", 403)):
            with self.assertRaises(RuntimeError) as raised:
                getCampaign(id="1")
        self.assertIn("403", str(raised.exception))
        self.assertIn("no menu", str(raised.exception))
        self.assertIn("getCampaign", str(raised.exception))

    def test_config_does_not_use_the_analytics_base(self) -> None:
        os.environ["IT_ANALYTICS_BASE"] = "https://analytics.example"
        os.environ.pop("IT_CONFIG_BASE")
        with self.assertRaises(RuntimeError) as raised:
            getCampaign(id="1")
        self.assertIn("IT_CONFIG_BASE", str(raised.exception))
        self.assertNotIn("analytics.example", str(raised.exception))
        config_source = (SCRIPT / "config" / "_http.py").read_text(encoding="utf-8")
        analytics_source = (SCRIPT / "analytics" / "_http.py").read_text(encoding="utf-8")
        self.assertIn("IT_CONFIG_BASE", config_source)
        self.assertNotIn("IT_ANALYTICS_BASE", config_source)
        self.assertIn("IT_ANALYTICS_BASE", analytics_source)
        self.assertNotIn("IT_CONFIG_BASE", analytics_source)

    def test_absolute_url_is_refused(self) -> None:
        from config._http import request
        with self.assertRaises(RuntimeError) as raised:
            request("GET", "https://evil.example/secret", operation="nope")
        self.assertIn("refused", str(raised.exception))


class SdkTest(unittest.TestCase):
    def test_find_returns_the_upload_operation_only(self) -> None:
        hits = find("证件", root=SKILL)
        self.assertEqual([hit["id"] for hit in hits], ["uploadFile"])
        self.assertEqual(hits[0]["system"], "config")
        blob = json.dumps(hits, ensure_ascii=False)
        self.assertNotIn("openapi", blob)
        self.assertNotIn("localhost", blob)
        self.assertNotIn("listCampaigns", blob)
        self.assertTrue(hits[0]["mutation"])
        self.assertTrue(hits[0]["fields_unknown"])
        self.assertEqual(hits[0]["module"], "config.cert_file_service")

    def test_preview_lists_real_keys(self) -> None:
        described = preview({"id": "c1", "name": "活动", "nested": {"k": 1}}, n=5)
        self.assertEqual(described["type"], "dict")
        self.assertEqual(described["keys"], ["id", "name", "nested"])
        rows = preview([{"status": "open"}, {"status": "closed"}], n=5)
        self.assertEqual(rows["array_len"], 2)
        self.assertEqual(rows["keys"], ["status"])
        self.assertEqual(len(rows["sample"]), 2)

    def test_emit_truncates_and_keeps_the_full_file(self) -> None:
        value = {"rows": ["x" * 100 for _ in range(2000)]}
        full = json.dumps(value, ensure_ascii=False, indent=2)
        with mock.patch.dict(os.environ, {"IT_SESSION_DIR": str(ROOT / ".it-session-test")}):
            with mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
                emit(value)
            printed = stdout.getvalue()
        self.assertIn(TRUNCATION_MARK, printed)
        self.assertLess(printed.index(TRUNCATION_MARK), len(full))
        folder = ROOT / ".it-session-test"
        files = list(folder.glob("emit-*.json"))
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].read_text(encoding="utf-8"), full)
        self.assertNotIn(TRUNCATION_MARK, files[0].read_text(encoding="utf-8"))
        files[0].unlink()
        folder.rmdir()

    def test_pages_stops_at_max_pages(self) -> None:
        seen: list[tuple[int, int]] = []

        def fetch(page: int, size: int) -> dict[str, int]:
            seen.append((page, size))
            return {"page": page}

        batches = list(pages(fetch, start=2, size=15, max_pages=3))
        self.assertEqual(seen, [(2, 15), (3, 15), (4, 15)])
        self.assertEqual([batch["page"] for batch in batches], [2, 3, 4])


class OverlayAndRefTest(unittest.TestCase):
    def test_offline_refs_and_overlay(self) -> None:
        root = Path(tempfile.mkdtemp())
        spec_dir = root / "specs" / "config"
        spec_dir.mkdir(parents=True)
        (spec_dir / "api.yaml").write_text(
            """
openapi: 3.0.3
info: {title: t, version: "1"}
paths:
  /items/{id}:
    get:
      operationId: getItem
      parameters:
      - name: id
        in: path
        required: true
        schema:
          $ref: '#/components/schemas/ItemId'
      responses:
        '200':
          description: ok
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Item'
  /items/rebuild:
    post:
      operationId: rebuildIndex
      summary: 重建
      responses:
        '200': {description: ok}
  /remote:
    get:
      operationId: remoteCall
      parameters:
      - name: q
        in: query
        schema:
          $ref: https://example.com/schema.json#/Q
      responses:
        '200': {description: ok}
  /external:
    get:
      operationId: externalCall
      responses:
        '200':
          description: ok
          content:
            application/json:
              schema:
                $ref: ./other.yaml#/Thing
  /cycle:
    get:
      operationId: cycleCall
      responses:
        '200':
          description: ok
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/LoopA'
components:
  schemas:
    ItemId: {type: integer}
    ItemCode: {type: string}
    Item:
      type: object
      properties:
        code:
          $ref: '#/components/schemas/ItemCode'
    LoopA:
      $ref: '#/components/schemas/LoopB'
    LoopB:
      $ref: '#/components/schemas/LoopA'
""",
            encoding="utf-8",
        )
        overlay_dir = root / "overlays"
        overlay_dir.mkdir()
        (overlay_dir / "config.yaml").write_text(
            """
overlay: 1
include:
  - operationId: getItem
  - operationId: remoteCall
  - operationId: externalCall
  - operationId: cycleCall
  - operationId: notInSpec
""",
            encoding="utf-8",
        )
        operations, skipped = load_documents(root)
        self.assertEqual([item.operation_id for item in operations], ["getItem"])
        self.assertEqual(operations[0].params[0].py_type, "int")
        self.assertEqual(operations[0].response_fields, (("code", "str"),))
        reasons = [item.reason for item in skipped]
        self.assertIn("excluded by overlay", reasons)
        self.assertTrue(any(reason.startswith("remote $ref is not fetched offline: https://") for reason in reasons))
        self.assertTrue(any(reason.startswith("external $ref is not resolved: ./other.yaml") for reason in reasons))
        self.assertTrue(any(reason.startswith("cyclic $ref:") for reason in reasons))
        self.assertTrue(any(reason.startswith("overlay include matched nothing: operationId=notInSpec") for reason in reasons))

    def test_missing_overlay_generates_nothing(self) -> None:
        root = Path(tempfile.mkdtemp())
        spec_dir = root / "specs" / "config"
        spec_dir.mkdir(parents=True)
        (spec_dir / "api.yaml").write_text(
            """
openapi: 3.0.3
info: {title: t, version: "1"}
paths:
  /ping:
    get:
      operationId: ping
      responses:
        '200': {description: ok}
""",
            encoding="utf-8",
        )
        operations, skipped = load_documents(root)
        self.assertEqual(operations, [])
        self.assertIn("no overlay; nothing is generated", skipped[0].reason)

    def test_bad_overlay_fails(self) -> None:
        root = Path(tempfile.mkdtemp())
        spec_dir = root / "specs" / "config"
        spec_dir.mkdir(parents=True)
        (spec_dir / "api.yaml").write_text("openapi: 3.0.3\ninfo: {title: t, version: '1'}\npaths: {}\n", encoding="utf-8")
        overlay_dir = root / "overlays"
        overlay_dir.mkdir()
        (overlay_dir / "config.yaml").write_text("overlay: 1\ninclude:\n  - method: get\n", encoding="utf-8")
        with self.assertRaises(SpecError):
            load_documents(root)


if __name__ == "__main__":
    unittest.main()
