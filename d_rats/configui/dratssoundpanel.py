# File: configui/dratssoundpanel.py

'''D-Rats Sound Panel Module.'''

# Copyright 2009 Dan Smith <dsmith@danplanet.com>
# review 2015-2020 Maurizio Andreotti  <iz2lxi@yahoo.it>
# Copyright 2021-2024 John. E. Malmberg - Python3 Conversion
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

import logging

if not '_' in locals():
    import gettext
    _ = gettext.gettext

from .dratspanel import DratsPanel
from .dratsconfigwidget import DratsConfigWidget


class DratsSoundPanel(DratsPanel):
    '''
    D-Rats Sound Panel.

    :param dialog: D-Rats Config UI Dialog
    :type dialog: :class:`config.DratsConfigUI`
    '''
    logger = logging.getLogger("DratsSoundPanel")

    # pylint: disable=unused-argument
    def __init__(self, dialog=None):
        DratsPanel.__init__(self)

        def do_snd(tab, tab_text):
            snd = DratsConfigWidget(section="sounds", name=tab)
            snd.add_sound()
            enb = DratsConfigWidget(section="sounds",
                                    name="%s_enabled" % tab)
            enb.add_bool()
            self.make_view(tab_text, snd, enb)

        # This is going to be a problem if the locale is ever changed
        do_snd("chat", _("Chat activity"))
        do_snd("messages", _("Message activity"))
        do_snd("files", _("File activity"))
