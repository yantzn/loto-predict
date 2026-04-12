#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BASE_REQUIREMENTS="${ROOT_DIR}/requirements-base.txt"
JOB_DIR="${ROOT_DIR}/jobs/backfill_loto_history"
JOB_REQUIREMENTS="${JOB_DIR}/requirements.txt"

if [[ ! -f "${BASE_REQUIREMENTS}" ]]; then
  echo "Base requirements not found: ${BASE_REQUIREMENTS}" >&2
  exit 1
fi

if [[ ! -d "${JOB_DIR}" ]]; then
  echo "Backfill job directory not found: ${JOB_DIR}" >&2
  exit 1
fi

cp "${BASE_REQUIREMENTS}" "${JOB_REQUIREMENTS}"

echo "Generated ${JOB_REQUIREMENTS} from ${BASE_REQUIREMENTS}"
