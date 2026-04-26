#!/usr/bin/env bash
# jobs/backfill_loto_history/ へ requirements.txt と src をコピーする
# - Cloud Run Job の --source デプロイで必要な実行ファイルを揃えるため
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BASE_REQUIREMENTS="${ROOT_DIR}/requirements-base.txt"
JOB_DIR="${ROOT_DIR}/jobs/backfill_loto_history"
SRC_DIR="${ROOT_DIR}/src"

if [[ ! -f "${BASE_REQUIREMENTS}" ]]; then
  echo "Base requirements not found: ${BASE_REQUIREMENTS}" >&2
  exit 1
fi
if [[ ! -d "${JOB_DIR}" ]]; then
  echo "Backfill job directory not found: ${JOB_DIR}" >&2
  exit 1
fi
if [[ ! -d "${SRC_DIR}" ]]; then
  echo "Source directory not found: ${SRC_DIR}" >&2
  exit 1
fi

cp "${BASE_REQUIREMENTS}" "${JOB_DIR}/requirements.txt"
rm -f "${JOB_DIR}/requirements-base.txt"
rm -rf "${JOB_DIR}/src"
cp -R "${SRC_DIR}" "${JOB_DIR}/src"

echo "Copied ${BASE_REQUIREMENTS} to ${JOB_DIR}/requirements.txt"
echo "Copied ${SRC_DIR} to ${JOB_DIR}/src"
