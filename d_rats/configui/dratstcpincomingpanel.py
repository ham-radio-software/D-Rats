# File: configui/dratstcpincomingpanel.py

'''D-Rats TCP Incoming Panel Module.'''

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

import gi  # type: ignore # Needed for pylance on Windows.
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk        # type: ignore
from gi.repository import GObject    # type: ignore

from .dratslistconfigwidget import DratsListConfigWidget
from .dratstcppanel import DratsTCPPanel


class DratsTCPIncomingPanel(DratsTCPPanel):
    '''
    D-Rats TCP Incoming Panel.

    :param dialog: D-Rats Config UI Dialog
    :type dialog: :class:`config.DratsConfigUI`
    '''
    logger = logging.getLogger("DratsTCPIncomingPanel")

    def __init__(self, dialog=None):
        DratsTCPPanel.__init__(self)

        incols = [(GObject.TYPE_STRING, "ID"),
                  (GObject.TYPE_INT, _("Port")),
                  (GObject.TYPE_STRING, _("Host"))]

        val = DratsListConfigWidget(section="tcp_in")
        list_widget = val.add_list(incols)
        add = Gtk.Button.new_with_label(_("Add"))
        add.connect("clicked", self.but_add, list_widget)
        rem = Gtk.Button.new_with_label(_("Remove"))
        rem.connect("clicked", self.but_rem, list_widget)
        self.make_view(_("Incoming"), val, add, rem)

    def but_add(self, _button, list_widget):
        '''
        Button Add.

        :param _button: Unused
        :type _button: :class:`Gtk.Widget`
        :param list_widget: widget for button
        :type list_widget: :class:`DratsListConfigWidget`
        '''
        values = self.prompt_for([(_("Port"), int),
                                  (_("Host"), str)])
        if values is None:
            return

        list_widget.set_item(str(values[_("Port")]),
                             values[_("Port")],
                             values[_("Host")].upper())
