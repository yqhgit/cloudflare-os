from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from gen_it_clients import generate  # noqa: E402


class GeneratorStableTest(unittest.TestCase):
    def test_second_run_is_byte_identical(self) -> None:
        generate()
        snapshot = {
            path.name: path.read_bytes()
            for path in sorted((ROOT / "script").glob("*.py"))
            if path.name not in {"__init__.py", "_http.py"}
        }
        generate()
        again = {
            path.name: path.read_bytes()
            for path in sorted((ROOT / "script").glob("*.py"))
            if path.name not in {"__init__.py", "_http.py"}
        }
        self.assertEqual(snapshot, again)
        self.assertIn(b"from _gen_common import", snapshot["cmdb.py"])
        self.assertIn(b"class FirewallRuleUpdate", snapshot["firewall.py"])


if __name__ == "__main__":
    unittest.main()
