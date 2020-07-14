#!/usr/bin/python
#
# Copyright 2009 Dan Smith <dsmith@danplanet.com>
# minor mods 2015-2020 by Maurizio Andreotti <iz2lxi> maurizioandreottilc@gmail.com>
#
##this module contains the d-rats version variables

from __future__ import print_function
#importing printlog() wrapper
from .debug import printlog

import sys

DRATS_VERSION = "0.3.10 beta 2 "
DRATS_NAME="d-rats"
DRATS_DESCRIPTION="D-RATS"
DRATS_LONG_DESCRIPTION = "A communications tool for D-STAR"
AUTHORS = "Dan Smith, KK7DS" +chr(13)+ \
          "Maurizio Andreotti, IZ2LXI" +chr(13)+ \
          "Marius Petrescu, YO2LOJ"
AUTHORS_EMAIL= "Dan Smith KK7DS <dsmith@danplanet.com>;" +chr(13)+ \
          "Maurizio Andreotti IZ2LXI <maurizio.iz2lxi@gmail.com>" +chr(13)+ \
          "Marius Petrescu YO2LOJ <marius@yo2loj.ro>"
COPYRIGHT ="Copyright 2010 Dan Smith (KK7DS)" +chr(13)+ \
          "Copyright 2014-2020 Maurizio Andreotti (IZ2LXI) &" +chr(13)+ \
          "Marius Petrescu (YO2LOJ)"
LICENCE ="You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>."
WEBSITE =""
TRANSLATIONS  ="Italian: Leo, IZ5FSA"

HTTP_CLIENT_HEADERS = {'User-Agent':  DRATS_NAME + "/" +  DRATS_VERSION }
printlog("Version : headers=%s" % HTTP_CLIENT_HEADERS)
		
if __name__ == "__main__":
	printlog("DRATS_VERSION:         ", DRATS_VERSION)
	printlog("DRATS_NAME:            ", DRATS_NAME)
	printlog("DRATS_DESCRIPTION:     ", DRATS_DESCRIPTION)
	printlog("DRATS_LONG_DESCRIPTION:", DRATS_LONG_DESCRIPTION)
	printlog("AUTHORS:               ", AUTHORS)
	printlog("AUTHORS_EMAIL:         ", AUTHORS_EMAIL)
	printlog("COPYRIGHT:             ", COPYRIGHT)
	printlog("LICENCE:               ", LICENCE)
	printlog("WEBSITE:               ", WEBSITE)
	printlog("TRANSLATIONS:          ", TRANSLATIONS)
