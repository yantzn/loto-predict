#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="${ROOT_DIR}/dist"

rm -rf "${DIST_DIR}"
mkdir -p "${DIST_DIR}"

package_function() {
  local func_name="$1"
  local temp_dir
  temp_dir="$(mktemp -d)"

  mkdir -p "${temp_dir}/src"
  cp -R "${ROOT_DIR}/src/loto_predict" "${temp_dir}/src/"
  cp "${ROOT_DIR}/functions/${func_name}/main.py" "${temp_dir}/main.py"
  cp "${ROOT_DIR}/functions/${func_name}/requirements.txt" "${temp_dir}/requirements.txt"

  (
    cd "${temp_dir}"
    zip -qr "${DIST_DIR}/${func_name}.zip" .
  )

  rm -rf "${temp_dir}"
}

package_function "fetch_loto_results"
package_function "import_loto_results_to_bq"
package_function "generate_prediction_and_notify"

echo "Packaged functions into ${DIST_DIR}"
