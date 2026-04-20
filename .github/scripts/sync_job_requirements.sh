#!/usr/bin/env bash
# jobs/backfill_loto_history/ へ requirements-base.txt をコピーする
# - Docker build のソースコンテキストに含める必要があるため
# - Dockerfile が requirements-base.txt を参照するため
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BASE_REQUIREMENTS="${ROOT_DIR}/requirements-base.txt"
JOB_DIR="${ROOT_DIR}/jobs/backfill_loto_history"

if [[ ! -f "${BASE_REQUIREMENTS}" ]]; then
  echo "Base requirements not found: ${BASE_REQUIREMENTS}" >&2
  exit 1
fi
if [[ ! -d "${JOB_DIR}" ]]; then
  echo "Backfill job directory not found: ${JOB_DIR}" >&2
  exit 1
fi

cp "${BASE_REQUIREMENTS}" "${JOB_DIR}/requirements-base.txt"

echo "Copied ${BASE_REQUIREMENTS} to ${JOB_DIR}/requirements-base.txt"
