#!/usr/bin/env python3
'''Python pre-build.'''
# Copyright 2008 Dan Smith <dsmith@danplanet.com>
# review 2015-2020 Maurizio Andreotti  <iz2lxi@yahoo.it>
# Copyright 2022 John. E. Malmberg - Python3 Conversion
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

from __future__ import absolute_import
from __future__ import print_function

from os import system
from os import makedirs
from os.path import dirname
from os.path import join
from os.path import realpath
from glob import glob


def default_build():
    '''Default Build.'''

    # towncrier needs a changes directory
    my_dir = realpath(dirname(__file__))
    changes = join(my_dir, 'changes')
    makedirs(changes, exist_ok=True)

    system('towncrier build --yes')

    doc_srcs = ['changelog', 'NEWS.rst']
    for file_name in doc_srcs:
        file_gz = file_name + ".gz"
        system("gzip -c %s > %s" % (file_name, file_gz))

    man_src_files = glob("share/*.1")
    for file_name in man_src_files:
        file_gz = file_name + ".gz"
        system("gzip -c %s > %s" % (file_name, file_gz))

    locale_po_files = glob("locale/*/LC_MESSAGES/D-RATS.po")
    for file_name in locale_po_files:
        locale_dir = dirname(file_name)
        command = "msgfmt -o %s/D-RATS.mo %s/D-RATS" % (locale_dir, locale_dir)
        system(command)


default_build()
