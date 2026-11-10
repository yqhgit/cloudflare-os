#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 tools/gen_it_clients.py
PYTHONPATH=skills/it-config-ops/scripts python3 -m unittest discover -s tests -v
