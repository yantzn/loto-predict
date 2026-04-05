#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FUNCTIONS_DIR="${ROOT_DIR}/functions"
SRC_DIR="${ROOT_DIR}/src"
DIST_DIR="${ROOT_DIR}/dist"

rm -rf "${DIST_DIR}"
mkdir -p "${DIST_DIR}"

package_function() {
  local function_name="$1"
  local zip_name="$2"
  local function_dir="${FUNCTIONS_DIR}/${function_name}"
  local common_dir="${FUNCTIONS_DIR}/common"
  local build_dir

  if [[ ! -d "${function_dir}" ]]; then
    echo "Function directory not found: ${function_dir}" >&2
    exit 1
  fi

  if [[ ! -f "${function_dir}/main.py" ]]; then
    echo "main.py not found: ${function_dir}/main.py" >&2
    exit 1
  fi

  build_dir="$(mktemp -d)"

  echo "Packaging ${function_name} -> ${zip_name}"

  cp -R "${function_dir}/." "${build_dir}/"

  if [[ -d "${common_dir}" ]]; then
    cp -R "${common_dir}" "${build_dir}/common"
  fi

  if [[ -d "${SRC_DIR}" ]]; then
    mkdir -p "${build_dir}/src"
    cp -R "${SRC_DIR}/." "${build_dir}/src/"
  fi

  (
    cd "${build_dir}"
    zip -qr "${DIST_DIR}/${zip_name}" .
  )

  rm -rf "${build_dir}"
}

package_function "fetch_loto_results" "fetch_loto_results.zip"
package_function "import_loto_results_to_bq" "import_loto_results_to_bq.zip"
package_function "generate_prediction_and_notify" "generate_prediction_and_notify.zip"

echo "Packaged files:"
ls -lh "${DIST_DIR}"
