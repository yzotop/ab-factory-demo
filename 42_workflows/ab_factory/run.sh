#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== AB Factory — Workflow Runner ==="
echo

python3 "${SCRIPT_DIR}/run_case.py" --all --keep-runs 10 "$@"

echo
echo "To open a report:"
echo "  cat ${SCRIPT_DIR}/runs/<run_id>/final_report.md"
echo
echo "To run selfcheck:"
echo "  cd ${SCRIPT_DIR} && python3 selfcheck.py"
