#!/bin/bash

set -ue

# Default list of files to lint
: "${CHANGED_FILES:=}"
if [ -z "$CHANGED_FILES" ]; then
  # Nothing to do
  exit 0
fi

# Default output
: "${PYLINT_OUT:=pylint.log}"
# Extra Pylint Options
: "${PYLINT_OPTS:=}"
# Default directory to start check
: "${BASE_DIR:=.}"

# Default checking
# pylint_rc="$(find "${BASE_DIR}" -name pylint.rc -print -quit)"

# Now search for all python files
rc=0
pushd "${BASE_DIR}" > /dev/null || exit 1

  rm -f "${PYLINT_OUT}"

  # Template to allow other tools to parse the output
  tmpl="{path}:{line}: pylint-{symbol}: {msg}"

  pylint="$(command -v pylint)"
  if [ -z "${pylint}" ]; then
    echo "pylint not found"
    exit 1
  fi

  for script_file in ${CHANGED_FILES}; do

    IFS=" " read -r -a pylint_cmd <<< "${pylint} ${PYLINT_OPTS} ${script_file}"
    if file "$script_file" | grep -q -e 'Python script'; then
      if ! python "${pylint_cmd[@]}" --msg-template "${tmpl}" >> \
        "${PYLINT_OUT}" 2>&1; then
        (( rc=rc+PIPESTATUS[0] ))
      fi
    fi
  done
  if [ -e "${PYLINT_OUT}" ]; then
    if ! grep ':' "${PYLINT_OUT}"; then
      # we have out pylint finding something?
      cat "${PYLINT_OUT}"
    fi
  fi
popd > /dev/null || exit 1
exit "${rc}"
