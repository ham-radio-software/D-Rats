#!/bin/bash

set -ue

# Default list of files to lint
: "${CHANGED_FILES:=}"
if [ -z "$CHANGED_FILES" ]; then
  # Nothing to do
  exit 0
fi

# Default output
: "${XMLLINT_OUT:=xmllint.log}"
# Default directory to start check
: "${BASE_DIR:=.}"

# Now search for all shell script files
rc=0
pushd "${BASE_DIR}" > /dev/null || exit 1

  rm -f "${XMLLINT_OUT}"

  if ! xmllint="$(command -v xmllint)"; then
    echo "xmllint not found"
    exit 0
  fi

  for script_file in ${CHANGED_FILES}; do

    IFS=" " read -r -a xmllint_cmd <<< \
        "${xmllint} --noout ${script_file}"
    if file "$script_file" | grep -q -E '(XML|HTML)\s.*document'; then
      if ! "${xmllint_cmd[@]}" >> "${XMLLINT_OUT}" 2>&1; then
        (( rc=rc+PIPESTATUS[0] ))
      fi
    fi
  done
  if [ "$rc" -ne 0 ] && [ -e "${XMLLINT_OUT}" ]; then
    if ! grep ':' "${XMLLINT_OUT}"; then
      cat "${XMLLINT_OUT}"
    fi
  fi
popd > /dev/null || exit 1
exit "${rc}"
