#!/usr/bin/env python3
'''
Internationalization Test.

This is for testing and demonstrating code maintenance for D-Rats
developers.
'''
#
# Copyright 2021 John Malmberg <wb8tyw@gmail.com>
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import gettext
import logging
import sys

def main():
    '''Main function for unit testing.'''



    gettext.install("D-RATS")

    # Need to find out how to auto select locale from the environment and
    # default to english if it is not specified.
    lang = gettext.translation("D-RATS",
                               localedir="locale",
                               fallback=True)
    lang.install()
    _ = lang.gettext

    # We should use a package to parse configuration options here
    # for now this will be need to be edited as needed.

    # This logging config must be done before logging anything.
    # Default is "WARNING" is tracked.

    # Eventually this logging should be used for both stdout/file and for the
    # logging to the D-rats event window.
    # A handler will be used to route messages to the D-RATS event window.

    logging.basicConfig(level=logging.INFO)

    # Each class should have their own logger.
    logger = logging.getLogger("language_test")

    # The text inside the _() function is the default text that
    # is displayed if there is not a international language in use.
    # So we want it to be brief but meaningful, and I am recommending
    # that it be in all uppercase, so it is obvious if a translation
    # entry is missing.
    print(_("HELLO_WORLD"))

    # Diagnostic Log messages should not be internationalized as they may
    # need to be posted and discussed.
    # One to internationalize logged messages is to assign each diagnostic
    # message a unique code that would not get translated, and then have
    # local translated text.

    if len(sys.argv) == 3:
        logger.warning('CMD_ARGS_NOT_IMPL: %s',
                       _('COMMAND ARGS NOT IMPLEMENTED!'))
    else:
        logger.warning('DEFAULT_NOT_IMPL: %s',
                       _('DEFAULT ARGUMENTS NOT IMPLEMENTED!'))

    logger.info('UNIT_TEST1: %s', _('EXECUTING UNIT TEST FUNCTION.'))

if __name__ == "__main__":
    main()
