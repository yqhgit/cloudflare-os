from __future__ import annotations

import io
import json
import os
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "script"
sys.path.insert(0, str(SCRIPT))

os.environ["IT_CMDB_BASE"] = "https://cmdb.test.example"
os.environ["IT_FIREWALL_BASE"] = "https://fw.test.example"
os.environ["IT_OPS_BI_BASE"] = "https://bi.test.example"

import cmdb  # noqa: E402
import firewall  # noqa: E402
import ops_bi  # noqa: E402
from catalog import operations_for_menu, systems_for_domain  # noqa: E402


class FakeResponse:
    def __init__(self, payload: object, status: int = 200) -> None:
        self._raw = json.dumps(payload).encode("utf-8")
        self.status = status

    def read(self) -> bytes:
        return self._raw

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def captured_urlopen(store: list[object]):
    def urlopen(req, timeout=30):  # noqa: ANN001
        store.append(req)
        return FakeResponse({"ok": True, "url": req.full_url, "method": req.get_method()})

    return urlopen


class GeneratedHttpTest(unittest.TestCase):
    def test_get_server_encodes_path(self) -> None:
        seen: list[object] = []
        with mock.patch("urllib.request.urlopen", captured_urlopen(seen)):
            cmdb.get_server(ip="10.0.0.1")
        req = seen[0]
        self.assertEqual(req.get_method(), "GET")
        self.assertEqual(req.full_url, "https://cmdb.test.example/api/servers/10.0.0.1")

    def test_list_servers_omits_null_query(self) -> None:
        seen: list[object] = []
        with mock.patch("urllib.request.urlopen", captured_urlopen(seen)):
            cmdb.list_servers()
        self.assertEqual(seen[0].full_url, "https://cmdb.test.example/api/servers")

    def test_list_servers_query(self) -> None:
        seen: list[object] = []
        with mock.patch("urllib.request.urlopen", captured_urlopen(seen)):
            cmdb.list_servers(idc="n1")
        self.assertEqual(seen[0].full_url, "https://cmdb.test.example/api/servers?idc=n1")

    def test_missing_required_raises_before_http(self) -> None:
        with mock.patch("urllib.request.urlopen") as urlopen:
            with self.assertRaises(TypeError):
                cmdb.get_server()
            urlopen.assert_not_called()

    def test_patch_body_and_mutation_doc(self) -> None:
        seen: list[object] = []
        with mock.patch("urllib.request.urlopen", captured_urlopen(seen)):
            cmdb.patch_server_tags(ip="10.0.0.1", body={"add": ["gpu"], "remove": ["idle"]})
        req = seen[0]
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(
            json.loads(req.data.decode("utf-8")),
            {"add": ["gpu"], "remove": ["idle"]},
        )
        self.assertTrue(cmdb.patch_server_tags.__doc__.startswith("写操作。"))

    def test_firewall_query_uses_shared_ip_type(self) -> None:
        seen: list[object] = []
        with mock.patch("urllib.request.urlopen", captured_urlopen(seen)):
            firewall.list_rules(device_ip="10.0.0.1")
        self.assertEqual(
            seen[0].full_url,
            "https://fw.test.example/api/rules?device_ip=10.0.0.1",
        )

    def test_ops_bi_query_params(self) -> None:
        seen: list[object] = []
        with mock.patch("urllib.request.urlopen", captured_urlopen(seen)):
            ops_bi.query_cpu(ip="10.0.0.1", start="2026-01-01T00:00:00Z", end="2026-01-01T01:00:00Z")
        self.assertIn("ip=10.0.0.1", seen[0].full_url)
        self.assertTrue(seen[0].full_url.startswith("https://bi.test.example/api/metrics/cpu?"))

    def test_http_403_surfaces_status_and_body(self) -> None:
        def urlopen(req, timeout=30):  # noqa: ANN001
            raise urllib.error.HTTPError(
                req.full_url, 403, "Forbidden", hdrs=None, fp=io.BytesIO(b"no permission")
            )

        with mock.patch("urllib.request.urlopen", urlopen):
            with self.assertRaises(RuntimeError) as ctx:
                cmdb.get_server(ip="10.0.0.1")
        self.assertIn("403", str(ctx.exception))
        self.assertIn("no permission", str(ctx.exception))

    def test_allowlist_rejects_unregistered_host(self) -> None:
        from _http import request

        with self.assertRaises(PermissionError):
            request("GET", "https://evil.example/api")

    def test_catalog_menus_and_domains(self) -> None:
        self.assertCountEqual(systems_for_domain("it"), ["cmdb", "firewall"])
        self.assertEqual(systems_for_domain("ops"), ["ops_bi"])
        ops = operations_for_menu("机器管理")
        self.assertEqual({item["id"] for item in ops}, {"get_server", "list_servers"})
        self.assertEqual(ops[0]["module"], "cmdb")
        alerts = operations_for_menu("alerts")
        self.assertEqual(alerts[0]["id"], "list_alerts")
        self.assertEqual(alerts[0]["domain"], "ops")


class CrossSystemTest(unittest.TestCase):
    def test_one_script_calls_three_systems_with_shared_ref(self) -> None:
        urls: list[str] = []

        def urlopen(req, timeout=30):  # noqa: ANN001
            urls.append(req.full_url)
            if "/servers/" in req.full_url and req.get_method() == "GET":
                return FakeResponse({
                    "identity": {"ip": "10.0.0.1", "hostname": "app-1"},
                    "idc": "n1",
                    "tags": ["prod"],
                })
            if "/metrics/cpu" in req.full_url:
                return FakeResponse({
                    "server": {"ip": "10.0.0.1"},
                    "metric": "cpu",
                    "points": [{"ts": "2026-01-01T00:00:00Z", "value": 0.4}],
                })
            if "/rules" in req.full_url:
                return FakeResponse([{
                    "id": "r1",
                    "device": {"ip": "10.0.0.1"},
                    "action": "allow",
                    "port": 443,
                }])
            raise AssertionError(req.full_url)

        with mock.patch("urllib.request.urlopen", urlopen):
            server = cmdb.get_server(ip="10.0.0.1")
            ip = server["identity"]["ip"]
            series = ops_bi.query_cpu(
                ip=ip, start="2026-01-01T00:00:00Z", end="2026-01-01T01:00:00Z"
            )
            rules = firewall.list_rules(device_ip=ip)

        self.assertEqual(ip, "10.0.0.1")
        self.assertEqual(series["server"]["ip"], ip)
        self.assertEqual(rules[0]["device"]["ip"], ip)
        self.assertEqual(len(urls), 3)
        self.assertTrue(any("cmdb.test.example" in url for url in urls))
        self.assertTrue(any("bi.test.example" in url for url in urls))
        self.assertTrue(any("fw.test.example" in url for url in urls))


if __name__ == "__main__":
    unittest.main()
