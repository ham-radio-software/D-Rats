#!/bin/bash

set -uex

# First create teh base.pot file
xgettext -d D-RATS -o locale/base.pot -D . *.py

# Next directory - Because of an odd string in ax25 need to specify a --from-code
xgettext -d D-RATS -o locale/base.pot -j --from-code ISO-8859-15 d_rats/*.py
# Repeat for each directory
# Any warnings probably need to be looked at.
xgettext -d D-RATS -o locale/base.pot -j d_rats/map/*.py
xgettext -d D-RATS -o locale/base.pot -j d_rats/sessions/*.py
xgettext -d D-RATS -o locale/base.pot -j d_rats/sessions/*.py
xgettext -d D-RATS -o locale/base.pot -j -L Glade ui/*.glade
