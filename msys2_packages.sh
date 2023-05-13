#!/usr/bin/bash

mingw='mingw-w64-x86_64'

pacman -Syu --noconfirm \
    "${mingw}-ca-certificates" \
    "${mingw}-python" \
    "${mingw}-gtk3" \
    "${mingw}-gettext" \
    "${mingw}-python3-gobject" \
    "${mingw}-aspell" "${mingw}-aspell-en" \
    "${mingw}-python-pywin32" \
    "${mingw}-python-lxml" \
    "${mingw}-python-pyserial" \
    "${mingw}-python-pillow"

if [[ "$1" == dev* ]]; then
  # packaging
  # no aspell-it dictionary at this time.
  pacman -Syu --noconfirm \
    "${mingw}-gcc" \
    "${mingw}-glade" \
    "${mingw}-make" \
    "${mingw}-python-codespell" \
    "${mingw}-python-pylint" \
    "${mingw}-python-setuptools" \
    "${mingw}-python-virtualenv"

    # This should not be needed, but is for now.
    ln -sf /mingw64/bin/mingw32-make.exe /mingw64/bin/make.exe
fi
