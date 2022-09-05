#!/usr/bin/python
'''Version information'''
#
# Copyright 2009 Dan Smith <dsmith@danplanet.com>
# minor mods 2015-2020 by Maurizio Andreotti iz2lxi
#                         <maurizioandreottilc@gmail.com>
# Copyright 2021-2022 John. E. Malmberg - Python3 Conversion
#
# #this module contains the d-rats version variables

from __future__ import print_function

import logging

if __name__ == "__main__":
    import gettext
    # pylint: disable=invalid-name
    lang = gettext.translation("D-RATS",
                               localedir="./locale",
                               fallback=True)
    lang.install()
    _ = lang.gettext

# DRATS_VERSION_NUM can not have "-" characters in it.
# That will break w2lk
DRATS_VERSION_NUM = "0.4.00 Alpha"
DRATS_VERSION = DRATS_VERSION_NUM + " pre-release1"
DRATS_NAME = "d-rats"
DRATS_DESCRIPTION = "D-RATS"
DRATS_LONG_DESCRIPTION = "A communications tool for D-STAR"
AUTHORS = "Dan Smith, KK7DS" \
          " Maurizio Andreotti, IZ2LXI" \
          " Marius Petrescu, YO2LOJ" \
          " John E. Malmberg, WB8TYW"
AUTHORS_EMAIL = "Dan Smith KK7DS <dsmith@danplanet.com>\n"  \
          "Maurizio Andreotti IZ2LXI <maurizio.iz2lxi@gmail.com>\n" \
          "Marius Petrescu YO2LOJ <marius@yo2loj.ro>\n" \
          "John E. Malmberg WB8TYW <wb8tyw@wsl.net>"
AUTHOR_COPYRIGHT = "2008-2010 Dan Smith (KK7DS)\n" \
          "2014-2022 Maurizio Andreotti (IZ2LXI) &\n"  \
          "Marius Petrescu (YO2LOJ)\n" \
          "2021-2022 John E. Malmberg (WB8TYW)."
DATA_COPYRIGHT = "Location and Map data Copyright www.thunderforest.com and\n" \
          "copyright OpenStreetMap Contributors, www.osm.org/copyright.\n" \
          "Some Map Data courtesy of the U.S. Geological Survey.\n" \
          "Weather data provided by OpenWeather (TM), openweathermap.org"
COPYRIGHT = 'Copyright ' + AUTHOR_COPYRIGHT + '\n' + DATA_COPYRIGHT
LICENSE = "You should have received a copy of the" \
	      " GNU General Public License along with this program." \
		  "  If not, see <http://www.gnu.org/licenses/>."
WEBSITE = "https://groups.io/g/d-rats"
TRANSLATIONS = "Italian: Leo, IZ5FSA"

HTTP_CLIENT_HEADERS = {'User-Agent':  DRATS_NAME + "/" +  DRATS_VERSION}

# pylint: disable=invalid-name
module_logger = logging.getLogger("Version")

module_logger.info("HTTP_CLIENT_HEADERS=%s", HTTP_CLIENT_HEADERS)


def main():
    '''Main package for testing.'''

    logging.basicConfig(level=logging.INFO)

    # Each class should have their own logger.
    logger = logging.getLogger("version_test")

    logger.info("DRATS_VERSION:         %s", DRATS_VERSION)
    logger.info("DRATS_NAME:            %s", DRATS_NAME)
    logger.info("DRATS_DESCRIPTION:     %s", DRATS_DESCRIPTION)
    logger.info("DRATS_LONG_DESCRIPTION:%s", DRATS_LONG_DESCRIPTION)
    logger.info("AUTHORS:               %s", AUTHORS)
    logger.info("AUTHORS_EMAIL:         %s", AUTHORS_EMAIL)
    logger.info("COPYRIGHT:             %s", COPYRIGHT)
    logger.info("LICENSE:               %s", LICENSE)
    logger.info("WEBSITE:               %s", WEBSITE)
    logger.info("TRANSLATIONS:          %s", TRANSLATIONS)


if __name__ == "__main__":
    main()
