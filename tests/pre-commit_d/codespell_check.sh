#!/bin/bash

set -ue

# Default list of files to lint
: "${CHANGED_FILES:=}"
if [ -z "$CHANGED_FILES" ]; then
  # Nothing to do
  exit 0
fi

# Default output
: "${CODESPELL_OUT:=codespell.log}"
# Default directory to start check
: "${BASE_DIR:=.}"

# Now search for all shell script files
rc=0
pushd "${BASE_DIR}" > /dev/null || exit 1

  rm -f "${CODESPELL_OUT}"

  codespell="$(command -v codespell)"
  if [ -z "${codespell}" ]; then
    echo "codespell not found"
    exit 0
  fi

  for script_file in ${CHANGED_FILES}; do
    IFS=" " read -r -a codespell_cmd <<< "${codespell} ${script_file}"
    if ! "${codespell_cmd[@]}" >> "${CODESPELL_OUT}" 2>&1; then
      (( rc=rc+PIPESTATUS[0] ))
    fi
  done

  if [ "$rc" -ne 0 ] && [ -e "${CODESPELL_OUT}" ]; then
    if ! grep ':' "${CODESPELL_OUT}"; then
      # We have something not reported above?
      cat "${CODESPELL_OUT}"
    fi
  fi
popd > /dev/null || exit 1
exit "${rc}"
