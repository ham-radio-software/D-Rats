#!/bin/bash

set -ue

# Default list of files to lint
: "${CHANGED_FILES:=}"
if [ -z "$CHANGED_FILES" ]; then
  # Nothing to do
  exit 0
fi

# Default output
: "${YAMLLINT_OUT:=yamllint.log}"
# Default directory to start check
: "${BASE_DIR:=.}"

# Now search for all shell script files
rc=0
pushd "${BASE_DIR}" > /dev/null || exit 1

  rm -f "${YAMLLINT_OUT}"

  if ! yamllint="$(command -v yamllint)"; then
    echo "yamllint not found"
    exit 0
  fi

  for script_file in ${CHANGED_FILES}; do

    IFS=" " read -r -a yamllint_cmd <<< \
        "${yamllint} --strict --format github ${script_file}"
    if [[ "$script_file" == *.yml ]]; then
      if ! "${yamllint_cmd[@]}" >> "${YAMLLINT_OUT}" 2>&1; then
        (( rc=rc+PIPESTATUS[0] ))
      fi
    fi
  done
  if [ "$rc" -ne 0 ] && [ -e "${YAMLLINT_OUT}" ]; then
    if ! grep '::' "${YAMLLINT_OUT}"; then
      cat "${YAMLLINT_OUT}"
    fi
  fi
popd > /dev/null || exit 1
exit "${rc}"
