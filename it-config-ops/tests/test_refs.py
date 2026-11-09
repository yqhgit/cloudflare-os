from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from gen_it_clients import (  # noqa: E402
    SpecError,
    load_docs,
    merge_all_of,
    py_type,
    resolve_ref,
)


class RefResolutionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.docs = load_docs()

    def test_in_file_ref(self) -> None:
        target, parts, node = resolve_ref(
            self.docs, "cmdb.yaml", "#/components/schemas/Nic"
        )
        self.assertEqual(target, "cmdb.yaml")
        self.assertEqual(parts[-1], "Nic")
        self.assertEqual(node["required"], ["name", "addr"])

    def test_cross_file_ref(self) -> None:
        target, parts, node = resolve_ref(
            self.docs, "cmdb.yaml", "common.yaml#/schemas/ServerRef"
        )
        self.assertEqual(target, "common.yaml")
        self.assertEqual(parts, ["schemas", "ServerRef"])
        self.assertIn("ip", node["properties"])

    def test_nested_ref_on_common_property(self) -> None:
        _target, _parts, node = resolve_ref(
            self.docs, "common.yaml", "#/schemas/ServerRef"
        )
        ip_schema = node["properties"]["ip"]
        self.assertEqual(ip_schema["$ref"], "#/schemas/IpAddress")
        _, _, ip = resolve_ref(self.docs, "common.yaml", ip_schema["$ref"])
        self.assertEqual(ip["type"], "string")

    def test_cycle_is_rejected(self) -> None:
        docs = {
            "loop.yaml": {
                "schemas": {
                    "A": {"$ref": "#/schemas/B"},
                    "B": {"$ref": "#/schemas/A"},
                }
            }
        }
        with self.assertRaises(SpecError) as ctx:
            resolve_ref(docs, "loop.yaml", "#/schemas/A")
        self.assertIn("cyclic $ref", str(ctx.exception))

    def test_allof_merges_ref_and_local_fields(self) -> None:
        schema = self.docs["firewall.yaml"]["components"]["schemas"]["FirewallRuleUpdate"]
        merged = merge_all_of(self.docs, "firewall.yaml", schema)
        self.assertIn("device", merged["properties"])
        self.assertIn("change_ticket", merged["properties"])
        self.assertEqual(merged["properties"]["device"]["$ref"], "common.yaml#/schemas/ServerRef")

    def test_py_type_preserves_named_ref(self) -> None:
        imports: set[tuple[str, str]] = set()
        annotation = py_type(
            self.docs,
            "ops_bi.yaml",
            {"$ref": "common.yaml#/schemas/ServerRef"},
            imports,
        )
        self.assertEqual(annotation, "ServerRef")
        self.assertIn(("ServerRef", "_gen_common"), imports)


if __name__ == "__main__":
    unittest.main()
