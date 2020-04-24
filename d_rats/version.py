#!/usr/bin/python
#
# Copyright 2009 Dan Smith <dsmith@danplanet.com>
# minor mods 2015-2020 by Maurizio Andreotti <iz2lxi> maurizioandreottilc@gmail.com>
#
##this module contains the d-rats version variables
#latest version being 0.3.3 updated to 0.3.4 (which is the alpha for this documentation project)

DRATS_VERSION = "0.3.7 alfa 20200423b"
DRATS_NAME="d-rats"
DRATS_DESCRIPTION="D-RATS"
DRATS_LONG_DESCRIPTION = "A communications tool for D-STAR"
AUTHORS = "Dan Smith, KK7DS" +chr(13)+ \
          "Maurizio Andreotti, IZ2LXI" +chr(13)+ \
          "Marius Petrescu, YO2LOJ"
AUTHORS_EMAIL= "Dan Smith KK7DS <dsmith@danplanet.com>;" +chr(13)+ \
          "Maurizio Andreotti IZ2LXI <maurizioandreottilc@gmail.com>" +chr(13)+ \
          "Marius Petrescu YO2LOJ <marius@yo2loj.ro>"
COPYRIGHT ="Copyright 2010 Dan Smith (KK7DS)" +chr(13)+ \
          "Copyright 2014-2020 Maurizio Andreotti (IZ2LXI) &" +chr(13)+ \
          "Marius Petrescu (YO2LOJ)"
LICENCE ="You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>."
WEBSITE =""
TRANSLATIONS  ="Italian: Leo, IZ5FSA"
		
if __name__ == "__main__":
	print("DRATS_VERSION:         ", DRATS_VERSION)
	print("DRATS_NAME:            ", DRATS_NAME)
	print("DRATS_DESCRIPTION:     ", DRATS_DESCRIPTION)
	print("DRATS_LONG_DESCRIPTION:", DRATS_LONG_DESCRIPTION)
	print("AUTHORS:               ", AUTHORS)
	print("AUTHORS_EMAIL:         ", AUTHORS_EMAIL)
	print("COPYRIGHT:             ", COPYRIGHT)
	print("LICENCE:               ", LICENCE)
	print("WEBSITE:               ", WEBSITE)
	print("TRANSLATIONS:          ", TRANSLATIONS)
