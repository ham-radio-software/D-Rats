#!/bin/bash

set -ue

# Default list of files to lint
: "${CHANGED_FILES:=}"
if [ -z "$CHANGED_FILES" ]; then
  # Nothing to do
  exit 0
fi

# Default output
: "${SHELLCHECK_OUT:=shellcheck.log}"
# Default directory to start check
: "${BASE_DIR:=.}"

# Follow external references if shellcheck supports it.
external=
if (shellcheck --help | grep "\-\-external") &> /dev/null; then
  external=--external
fi

# Now search for all shell script files
rc=0
pushd "${BASE_DIR}" > /dev/null || exit 1

  rm -f "${SHELLCHECK_OUT}"

  # Template to allow other tools to parse the output
  tmpl="--format=gcc"

  shellcheck="$(command -v shellcheck)"
  if [ -z "${shellcheck}" ]; then
    echo "shellcheck not found"
    exit 1
  fi

  for script_file in ${CHANGED_FILES}; do

    IFS=" " read -r -a shellcheck_cmd <<< \
        "${shellcheck} ${external} ${script_file}"
    if file "$script_file" | grep -q -e 'shell script'; then
      if ! "${shellcheck_cmd[@]}" "${tmpl}" >> "${SHELLCHECK_OUT}" 2>&1; then
        (( rc=rc+PIPESTATUS[0] ))
      fi
    fi
  done
  if [ "$rc" -ne 0 ] && [ -e "${SHELLCHECK_OUT}" ]; then
    if ! grep ':' "${SHELLCHECK_OUT}"; then
      cat "${SHELLCHECK_OUT}"
    fi
  fi
popd > /dev/null || exit 1
exit "${rc}"
