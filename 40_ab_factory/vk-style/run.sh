#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== AB Factory — Validate & Summarize ==="
echo

python3 "${SCRIPT_DIR}/tools/validate_cases.py"
echo
python3 "${SCRIPT_DIR}/tools/summarize_cases.py"
