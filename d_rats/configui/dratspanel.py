# File: configui/dratspanel.py

'''Drats Panel for Configuration.'''

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

import gi  # type: ignore # Needed for pylance on Windows.
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk        # type: ignore

from ..dratsconfig import DratsConfig
from .dratsconfigwidget import DratsConfigWidget

from .config_exception import ConfigMessageGroupError


def disable_by_combo(combo, map_var):
    '''
    Disable By Combo.

    :param combo: combo object
    :type combo: :class:`Gtk.ComboBoxText`
    :param map_ver: Dictionary map
    :type map_ver: dict
    '''
    # Expects a map like:
    # map = {
    #   "value1" : [el1, el2],
    #   "value2" : [el3, el4],
    # }
    def set_disables(combo, map_var):
        '''
        Set Disables change handler.

        :param combo: Combo Box widget
        :type: combo: :class:`Gtk.ComboBoxText`
        :param map_ver: Dictionary map
        :type map_ver: dict
        '''
        for i in map_var.values():
            for j in i:
                j.set_sensitive(False)
        for i in map_var[combo.get_active_text()]:
            i.set_sensitive(True)

    combo.connect("changed", set_disables, map_var)
    set_disables(combo, map_var)


def disable_with_toggle(toggle, widget):
    '''
    Disable With Toggle.

    :param toggle: Toggle object
    :type toggle: :class:`DratsConfigWidget`
    :param widget: Widget to toggle
    :type widget: :class:`DratsConfigWidget`
    '''
    toggle.connect("toggled",
                   lambda t, w: w.set_sensitive(t.get_active()), widget)
    widget.set_sensitive(toggle.get_active())


class DratsPanel(Gtk.Grid):
    '''
    D-Rats Configuration Panel.

    :param dialog: D-Rats Config UI Dialog
    :type dialog: :class:`config.DratsConfigUI`
    '''

    logger = logging.getLogger("DratsPanel")
    config = DratsConfig()

    def __init__(self):
        Gtk.Grid.__init__(self)
        self.vals = []

        self.row = 0

    def make_view(self, title, *args):
        '''
        Make View.

        set information for a widget.
        :param title: Title for widget
        :type title: str
        :param args: Optional arguments
        :type args: tuple[str, :class:`Gtk.Widget`]
        '''

        hbox = Gtk.Box.new(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)

        label = Gtk.Label.new(title)
        label.show()

        for i in args:
            i.show()
            if isinstance(i, DratsConfigWidget):
                if i.do_not_expand:
                    hbox.pack_start(i, 0, 0, 0)
                else:
                    hbox.pack_start(i, 1, 1, 0)
                    i.set_hexpand(True)
                self.vals.append(i)
            else:
                hbox.pack_start(i, 0, 0, 0)

        hbox.show()
        self.attach(label, 0, self.row, 1, 1)
        self.attach_next_to(hbox, label, Gtk.PositionType.RIGHT, 1, 1)

        self.row += 1

    def message_group(self, title, *args):
        '''
        Message Group.

        :param title: title of message group
        :type title: str
        :param args: Optional arguments
        :type args: tuple[str, :class:`Gtk.Widget`]
        '''
        if len(args) % 2:
            raise ConfigMessageGroupError("Need label,widget pairs")

        grid = Gtk.Grid.new()
        row = 0

        for i in range(0, len(args), 2):
            label = Gtk.Label.new(args[i])
            widget = args[i+1]

            label.show()
            widget.show()
            grid.attach(label, 0, row, 2, 1)
            grid.attach_next_to(widget, label, Gtk.PositionType.RIGHT,
                                1, 1)
            row += 1

        grid.show()

        frame = Gtk.Frame.new(title)
        frame.show()
        frame.add(grid)

        self.attach(frame, 1, self.row, 1, 1)
        self.row += 1
