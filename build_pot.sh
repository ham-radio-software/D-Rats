#!/bin/bash

set -uex

# First create the base.pot file
xgettext -d D-RATS -o locale/base.pot -D . ./*.py

# Next directory - Because of an odd string in ax25 need to
# specify a --from-code
xgettext -d D-RATS -o locale/base.pot -j --from-code ISO-8859-15 d_rats/*.py
# Repeat for each directory
# Any warnings probably need to be looked at.
xgettext -d D-RATS -o locale/base.pot -j d_rats/map/*.py
xgettext -d D-RATS -o locale/base.pot -j d_rats/sessions/*.py
xgettext -d D-RATS -o locale/base.pot -j d_rats/ui/*.py
xgettext -d D-RATS -o locale/base.pot -j -L Glade ui/*.glade

while IFS= read -r -d '' file_name; do
    locale_dir="$(dirname "$file_name")"
     msgfmt -o "$locale_dir/D-RATS.mo" "$locale_dir/D-RATS"
done <  <(find locale -name '*.po' -print0)
