#!/usr/bin/env python3
'''Python setup.py.'''
# Copyright 2008 Dan Smith <dsmith@danplanet.com>
# review 2015-2020 Maurizio Andreotti  <iz2lxi@yahoo.it>
# Copyright 2022-2023 John. E. Malmberg - Python3 Conversion
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License

from os.path import dirname
from glob import glob
from setuptools import setup


def default_build():
    '''Default Build.'''

    data_files = []

    section_files = glob("share/*.desktop")
    data_files.append(('share/applications', section_files))

    data_files.append(('share/pixmaps/', ['share/d-rats2.xpm']))

    section_files = glob("forms/*.x?l")
    data_files.append(('share/d-rats/forms', section_files))

    section_files = glob("images/*")
    section_files.append("share/d-rats2.xpm")
    data_files.append(('share/d-rats/images', section_files))

    ui_files = ['ui/addport.glade', 'ui/mainwindow.glade']

    data_files.append(('share/d-rats/ui', ui_files))
    section_files = ['COPYING']
    data_files.append(('share/doc/d-rats/', section_files))

    section_files = ['share/d-rats.py.1.gz', 'share/d-rats_repeater.py.1.gz']
    data_files.append(('share/man/man1', section_files))

    locale_mo_files = glob("locale/*/LC_MESSAGES/D-RATS.mo")
    mo_prefix = 'share/d-rats/'
    for file_name in locale_mo_files:
        data_files.append((mo_prefix + dirname(file_name), [file_name]))

    version = '0.0.0'
    with open('d_rats/setup_version.py', 'r') as version_file:
        lines = version_file.readlines()
        for line in lines:
            line = line.strip()
            if line.startswith('#'):
                continue
            parts = line.split()
            if parts[0] != "SETUP_VERSION":
                continue
            version = parts[2].strip('"')

    setup(name='D-Rats',
          version=version,
          scripts=['d-rats.py', 'd-rats_repeater.py'],
          data_files=data_files)

print("The setup.py is only used in building a pip installable tarball.")
print("The setup.py is not used for actually installing d-rats" +
      "and will not work.")
default_build()
