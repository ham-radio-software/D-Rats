#!/usr/bin/env python3
'''
Internationalization Test.

This is for testing and demonstrating code maintenance for D-Rats
developers.
'''
#
# Copyright 2021-2023 John Malmberg <wb8tyw@gmail.com>
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
import glob
import logging
import os
from pathlib import Path
import sys
import pycountry


def main():
    '''Main function for unit testing.'''

    # This logging config must be done before logging anything.
    # Default is "WARNING" is tracked.

    # Eventually this logging should be used for both stdout/file and for the
    # logging to the D-rats event window.
    # A handler will be used to route messages to the D-RATS event window.

    logging.basicConfig(level=logging.INFO)

    # Each class should have their own logger.
    logger = logging.getLogger("language test")

    # Get the current locale information
    # Was a nice idea, however this function is being removed from python3
    # default_locale = locale.getdefaultlocale()
    default_locale='en_US.UTF-8'
    envs = ['LC_ALL', 'LC_CTYPE', 'LANG', 'LANGUAGE']
    for env in envs:
        # Need to guess the country
        if env in os.environ:
            default_locale = os.environ[env]
            # default_country_code = default_locale[3:5]
            break

    language = None
    language = pycountry.languages.get(alpha_2=default_locale[0][0:2])

    # Demonstrate exception handling if locale is not found.
    try:
        language_name = language.name
    except AttributeError:
        language_name = None

    logger.info("defaults language code: %s, encoding: %s, language %s",
                default_locale[0], default_locale[1], language_name)

    gettext.install("D-RATS")

    # the os.environ['LC_ALL'] is the value that Anti-X Linux uses to
    # determine what the default locale.  For Anti-X Linux it needs to
    # be set to a string that specifies the language, country. and
    # encoding in spite of examples showing othersise/
    # export LC_ALL=en_US.UTF-8

    # How to find what lanaguges are available
    localedir="./locale"

    for mo_file in glob.glob("locale/*/LC_MESSAGES/D-RATS.mo"):
        parts = Path(mo_file).parts
        indx = 0
        for part in parts:
            indx += 1
            if part == 'locale':
                locale_name = parts[indx]
                language = pycountry.languages.get(alpha_2=locale_name)
                language_name = locale_name  # fallback should not be needed.
                if language:
                    language_name = language.name
                logger.info("Language found %s", language_name)

    # Note from Maurizio: While waiting to load from D-Rats config,
    # am forcing language to see if it gets loaded as in D-rats gettext
    # doesn't make any visible effect
    lang = gettext.translation("D-RATS",
                               localedir,
                               languages=['it'], #forcing to 'it'
                               fallback=True)
    lang.install()
    _ = lang.gettext

    # We should use a package to parse configuration options here
    # for now this will be need to be edited as needed.

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
