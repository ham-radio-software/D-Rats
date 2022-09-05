#!/usr/bin/python
'''Version information'''
#
# Copyright 2009 Dan Smith <dsmith@danplanet.com>
# minor mods 2015-2020 by Maurizio Andreotti iz2lxi
#                         <maurizioandreottilc@gmail.com>
#
# #this module contains the d-rats version variables

from __future__ import print_function

#importing printlog() wrapper
from .debug import printlog

import sys

DRATS_VERSION = "0.4.00 Alpha"
DRATS_NAME="d-rats"
DRATS_DESCRIPTION="D-RATS"
DRATS_LONG_DESCRIPTION = "A communications tool for D-STAR"
AUTHORS = "Dan Smith, KK7DS" \
          " Maurizio Andreotti, IZ2LXI" \
          " Marius Petrescu, YO2LOJ" \
          " John E. Malmberg, WB8TYW"
AUTHORS_EMAIL = "Dan Smith KK7DS <dsmith@danplanet.com>;\n"  \
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

printlog("Version", "   : HTTP_CLIENT_HEADERS=%s" % HTTP_CLIENT_HEADERS)

if __name__ == "__main__":
	printlog("Version", "   : DRATS_VERSION:         ", DRATS_VERSION)
	printlog("Version", "   : DRATS_NAME:            ", DRATS_NAME)
	printlog("Version", "   : DRATS_DESCRIPTION:     ", DRATS_DESCRIPTION)
	printlog("Version", "   : DRATS_LONG_DESCRIPTION:", DRATS_LONG_DESCRIPTION)
	printlog("Version", "   : AUTHORS:               ", AUTHORS)
	printlog("Version", "   : AUTHORS_EMAIL:         ", AUTHORS_EMAIL)
	printlog("Version", "   : COPYRIGHT:             ", COPYRIGHT)
	printlog("Version", "   : LICENSE:               ", LICENSE)
	printlog("Version", "   : WEBSITE:               ", WEBSITE)
	printlog("Version", "   : TRANSLATIONS:          ", TRANSLATIONS)
