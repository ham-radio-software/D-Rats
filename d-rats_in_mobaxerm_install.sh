#!/usr/bin/bash

set -uex
# MobaXterm has some of these packages built in.
# curl git wget

# MobaXterm uses aliases which are needed in a setup script
apt_get='/bin/MobaBox.exe apt-get'
mkdir='/usr/bin/busybox mkdir'

# This is needed to prevent pop ups that pause the install
DEBIAN_FRONTEND=noninteractive
export DEBIAN_FRONTEND
# Update to current and add packages
# apt-get --assume-yes update
$apt_get -y upgrade
$apt_get -y install \
  aspell aspell-de aspell-en aspell-es aspell-it \
  ffmpeg \
  gedit gettext git gcc-core \
  libgtk3_0 libjpeg-devel libportaudio-devel \
  python39 python39-devel python39-gi python39-lxml \
  python3-pip python39-sphinx \
  zlib-devel

pypi_dir=/usr/local/lib/pypi
$mkdir -p "$pypi_dir"

pathadd() {
    if [ -d "$1" ] && [[ ":$PATH:" != *":$1:"* ]]; then
        PATH="$1${PATH:+":$PATH"}"
    fi
}

if [ -e "$pypi_dir/bin/pip3" ]; then
  pathadd "$pypi_dir/bin"
else
  # Pip always complains if a newer version is available until
  # you upgrade to it.
  ls "$pypi_dir/bin"
  echo "upgrading pip, this will warn that pip needs upgrading"
  pip3 install --upgrade --target="$pypi_dir" pip
  pathadd "$pypi_dir/bin"
  ls "$pypi_dir/bin"
fi
# Need to set PYTHONPATH to use the PyPi packages
PYTHONPATH="$pypi_dir"
export PYTHONPATH
ls "$pypi_dir/bin"
# If we do not include pip here, for some reason pip removes the
# binary for it.  Why???
"$pypi_dir/bin"/pip3 install --upgrade --target="$pypi_dir" \
  feedparser \
  geopy \
  pip \
  Pillow \
  pyaudio \
  pydub \
  pycountry \
  pyserial

if [ ! -e "$HOME/d-rats-git" ]; then
  git clone https://github.com/ham-radio-software/D-Rats.git \
    "$HOME/d-rats-git"
else
  pushd "$HOME/d-rats-git"
    git pull
  popd
fi

# Handle lzhuf
if [ ! -e /usr/bin/lzhuf ]; then
   lzexe="/drives/c/Program Files/lzhuf/lzhuf.exe"
   if [ -e "$lzexe" ]; then
     ln -s "$lzexe" /usr/bin/lzhuf
   else
     echo "lzhuf is not installed!  Install from"
     echo "https://groups.io/g/d-rats/files/D-Rats/Windows"
     echo "groups.io d-rats free membership required"
     echo "Then re-run this script."
   fi
fi


if [ ! -e "$HOME/d-rats" ]; then
  cat << 'EOF' > "$HOME/d-rats"
#!/bin/bash
PYTHONPATH=/usr/local/lib/pypi
export PYTHONPATH
$HOME/d-rats-git/d-rats.py "$@"
EOF
chmod 755 "$HOME/d-rats"
fi
