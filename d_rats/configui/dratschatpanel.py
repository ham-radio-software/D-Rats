# File: configui/dratschatpanel.py

'''D-Rats Chat Panel Module.'''

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


class DratsChatPanel(DratsPanel):
    '''
    D-Rats Chat Panel.

    :param dialog: D-Rats Config UI Dialog
    :type dialog: :class:`config.DratsConfigUI`
    '''
    logger = logging.getLogger("DratsChatPanel")

    # pylint: disable=unused-argument
    def __init__(self, dialog=None):
        DratsPanel.__init__(self)

        val = DratsConfigWidget(section="prefs", name="logenabled")
        val.add_bool()
        self.make_view(_("Log chat traffic"), val)

        val = DratsConfigWidget(section="prefs", name="logresume")
        val.add_bool()
        self.make_view(_("Load log tail"), val)

        val = DratsConfigWidget(section="prefs", name="font")
        val.add_font()
        self.make_view(_("Chat font"), val)

        val = DratsConfigWidget(section="prefs", name="scrollback")
        val.add_numeric(0, 9999, 1)
        self.make_view(_("Scrollback Lines"), val)

        val = DratsConfigWidget(section="prefs", name="chat_showstatus")
        val.add_bool()
        self.make_view(_("Show status updates in chat"), val)

        val = DratsConfigWidget(section="prefs", name="chat_timestamp")
        val.add_bool()
        self.make_view(_("Timestamp chat messages"), val)

        val = DratsConfigWidget(section="settings", name="qst_size_limit")
        val.add_numeric(1, 9999, 1)
        self.make_view(_("QST Size Limit"), val)

        # weather api
        val = DratsConfigWidget(section="settings",
                                name="qst_owuri",
                                have_revert=True)
        val.add_text()
        self.make_view(_("OpenWeather uri"), val)

        val = DratsConfigWidget(section="settings",
                                name="qst_owappid",
                                have_revert=True)
        val.add_text()
        self.make_view(_("OpenWeather appid"), val)
