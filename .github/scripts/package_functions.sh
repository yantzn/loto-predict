#!/usr/bin/env bash
# Cloud Functions用のデプロイzipを生成するスクリプト
# - 各functions/配下のmain.pyを含むディレクトリをzip化
# - 共通コードやsrc/も同梱
# - 依存requirementsはルートのrequirements-base.txtを正本とする
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FUNCTIONS_DIR="${ROOT_DIR}/functions"
SRC_DIR="${ROOT_DIR}/src"
DIST_DIR="${ROOT_DIR}/dist"
BASE_REQUIREMENTS="${ROOT_DIR}/requirements-base.txt"

rm -rf "${DIST_DIR}"
mkdir -p "${DIST_DIR}"

# 指定functionディレクトリをzip化
package_function() {
  local function_name="$1"
  local zip_name="$2"
  local function_dir="${FUNCTIONS_DIR}/${function_name}"
  local common_dir="${FUNCTIONS_DIR}/common"
  local build_dir

  # main.py必須
  if [[ ! -d "${function_dir}" ]]; then
    echo "Function directory not found: ${function_dir}" >&2
    exit 1
  fi
  if [[ ! -f "${function_dir}/main.py" ]]; then
    echo "main.py not found: ${function_dir}/main.py" >&2
    exit 1
  fi
  if [[ ! -f "${BASE_REQUIREMENTS}" ]]; then
    echo "Base requirements not found: ${BASE_REQUIREMENTS}" >&2
    exit 1
  fi

  build_dir="$(mktemp -d)"

  echo "Packaging ${function_name} -> ${zip_name}"

  # function固有コード
  cp -R "${function_dir}/." "${build_dir}/"

  # 共通コード
  if [[ -d "${common_dir}" ]]; then
    cp -R "${common_dir}" "${build_dir}/common"
  fi
  # src/も同梱
  if [[ -d "${SRC_DIR}" ]]; then
    mkdir -p "${build_dir}/src"
    cp -R "${SRC_DIR}/." "${build_dir}/src/"
  fi
  # 依存requirementsはルートのものをコピー
  cp "${BASE_REQUIREMENTS}" "${build_dir}/requirements.txt"
  # サブディレクトリのrequirements.txtは削除（混入防止）
  find "${build_dir}" -mindepth 2 -type f -name "requirements.txt" -delete || true
  (
    cd "${build_dir}"
    zip -qr "${DIST_DIR}/${zip_name}" .
  )
  rm -rf "${build_dir}"
}

# 各functionをパッケージ化
package_function "fetch_loto_results" "fetch_loto_results.zip"
package_function "import_loto_results_to_bq" "import_loto_results_to_bq.zip"
package_function "generate_prediction_and_notify" "generate_prediction_and_notify.zip"

echo "Packaged files:"
ls -lh "${DIST_DIR}"
