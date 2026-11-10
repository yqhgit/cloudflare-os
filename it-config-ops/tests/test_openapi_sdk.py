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
SKILL = ROOT / "skills" / "it-config-ops"
SCRIPT = SKILL / "scripts"

import sys

sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(SCRIPT))

import gen_it_clients  # noqa: E402
from ops.campaigns import getCampaign, listCampaigns  # noqa: E402
from ops.cert_file_service import uploadFile  # noqa: E402
from ops.labels import createLabel  # noqa: E402
from sdk import emit, find, pages, preview  # noqa: E402
from sdk.preview import TRUNCATION_MARK  # noqa: E402


def _generated_sources() -> list[Path]:
    paths = []
    for directory in (SCRIPT / "ops", SCRIPT / "ana"):
        paths.extend(directory.glob("*.py"))
        paths.extend(directory.glob("*.pyi"))
    return [path for path in paths if path.name not in {"_http.py", "__init__.py"}]


class GeneratorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        gen_it_clients.generate(SKILL)

    def test_byte_stable(self) -> None:
        before = {path: path.read_bytes() for path in _generated_sources()}
        report = (SCRIPT / "gen_report.txt").read_bytes()
        gen_it_clients.generate(SKILL)
        after = {path: path.read_bytes() for path in _generated_sources()}
        self.assertEqual(before, after)
        self.assertEqual(report, (SCRIPT / "gen_report.txt").read_bytes())

    def test_upload_file_contract(self) -> None:
        source = (SCRIPT / "ops" / "cert_file_service.py").read_text(encoding="utf-8")
        self.assertIn('files={"file": file}', source)
        self.assertIn("-> dict", source)
        self.assertTrue(uploadFile.__doc__.startswith("写操作。"))
        self.assertIn("字段未知，先用 preview", uploadFile.__doc__)
        self.assertNotIn("localhost", source)
        self.assertNotIn("Cookie", source)
        self.assertNotIn("Authorization", source)

    def test_missing_operation_id_is_skipped(self) -> None:
        report = (SCRIPT / "gen_report.txt").read_text(encoding="utf-8")
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
        from ana.funnels import searchFunnels
        self.assertFalse(searchFunnels.__doc__.startswith("写操作。"))


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
        self.environ = mock.patch.dict(os.environ, {"IT_OPS_BASE": "https://ops.example/productuom"}, clear=False)
        self.environ.start()
        os.environ.pop("IT_ANA_BASE", None)

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
                from ops._http import request
                request(
                    "POST", "/certFileService/uploadFile", operation="uploadFile",
                    files={"file": str(target)}, headers={"Cookie": "a=b", "X-Route": "east"},
                )
        generated = self.captured[0]
        direct = self.captured[1]
        self.assertTrue(generated.full_url.startswith(
            "https://ops.example/productuom/certFileService/uploadFile"))
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

    def test_ops_does_not_use_the_analytics_base(self) -> None:
        os.environ["IT_ANA_BASE"] = "https://ana.example"
        os.environ.pop("IT_OPS_BASE")
        with self.assertRaises(RuntimeError) as raised:
            getCampaign(id="1")
        self.assertIn("IT_OPS_BASE", str(raised.exception))
        self.assertNotIn("ana.example", str(raised.exception))
        ops_source = (SCRIPT / "ops" / "_http.py").read_text(encoding="utf-8")
        ana_source = (SCRIPT / "ana" / "_http.py").read_text(encoding="utf-8")
        self.assertIn("IT_OPS_BASE", ops_source)
        self.assertNotIn("IT_ANA_BASE", ops_source)
        self.assertIn("IT_ANA_BASE", ana_source)
        self.assertNotIn("IT_OPS_BASE", ana_source)

    def test_absolute_url_is_refused(self) -> None:
        from ops._http import request
        with self.assertRaises(RuntimeError) as raised:
            request("GET", "https://evil.example/secret", operation="nope")
        self.assertIn("refused", str(raised.exception))


class SdkTest(unittest.TestCase):
    def test_find_returns_the_upload_operation_only(self) -> None:
        hits = find("ops", "证件", SKILL)
        self.assertEqual([hit["id"] for hit in hits], ["uploadFile"])
        blob = json.dumps(hits, ensure_ascii=False)
        self.assertNotIn("openapi", blob)
        self.assertNotIn("localhost", blob)
        self.assertNotIn("listCampaigns", blob)
        self.assertTrue(hits[0]["mutation"])
        self.assertTrue(hits[0]["fields_unknown"])
        self.assertEqual(hits[0]["module"], "ops.cert_file_service")

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


if __name__ == "__main__":
    unittest.main()
