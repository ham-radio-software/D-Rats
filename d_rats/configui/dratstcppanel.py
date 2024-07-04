# File: configui/dratstcpanel.py

'''D-Rats TCP Panel Module.'''

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

if not '_' in locals():
    import gettext
    _ = gettext.gettext

from ..inputdialog import FieldDialog
from .dratspanel import DratsPanel


class DratsTCPPanel(DratsPanel):
    '''
    D-Rats TCP Panel.

    :param dialog: D-Rats Config UI Dialog
    :type dialog: :class:`config.DratsConfigUI`
    '''

    INITIAL_ROWS = 2
    logger = logging.getLogger("DratsTCPPanel")

    # pylint: disable=unused-argument
    def __init__(self, dialog=None):
        DratsPanel.__init__(self)

    # pylint: disable=arguments-differ
    def make_view(self, _title, *widgets):
        '''
        Make View.

        set information for a widget.
        :param _title: Title for widget, Unused
        :type _title: str
        :param widgets: Optional arguments
        :type widgets: tuple[:class:`Gtk.Widget`]
        '''

        widgets[0].show()
        widget_height = max(widgets[0].get_preferred_height())

        self.attach(widgets[0], 0, 0, 3, widget_height)

        if len(widgets) > 1:
            box = Gtk.Box.new(orientation=Gtk.Orientation.HORIZONTAL,
                              spacing=2)
            box.set_homogeneous(True)

            for i in widgets[1:]:
                box.pack_start(i, 0, 0, 0)
                i.show()

            box.show()
            box_height = max(box.get_preferred_height())
            self.attach_next_to(box, widgets[0], Gtk.PositionType.BOTTOM,
                                1, box_height)

    @staticmethod
    def but_rem(_button, list_widget):
        '''
        Button Remove.

        :param _button: Unused
        :type _button: :class:`Gtk.Button`
        :param list_widget: widget for button
        :type list_widget: :class:`DratsListConfigWidget`
        '''
        list_widget.del_item(list_widget.get_selected())

    @staticmethod
    def prompt_for(fields):
        '''
        Prompt for.

        :param fields: Fields object
        :type fields: list[str, type]
        :returns: dict of fields
        :rtype: dict
        '''
        field_dialog = FieldDialog()
        for n_field, t_field in fields:
            field_dialog.add_field(n_field, Gtk.Entry())

        ret = {}

        done = False
        # pylint: disable=no-member
        while not done and field_dialog.run() == Gtk.ResponseType.OK:
            done = True
            for n_field, t_field in fields:
                try:
                    s_text = field_dialog.get_field(n_field).get_text()
                    if not s_text:
                        raise ValueError("empty")
                    ret[n_field] = t_field(s_text)
                except ValueError as error:
                    e_dialog = Gtk.MessageDialog(buttons=Gtk.ButtonsType.OK)
                    e_dialog.set_property("text",
                                          _("Invalid value for") +
                                          " %s: %s" % (n_field, error))
                    e_dialog.run()
                    e_dialog.destroy()
                    done = False
                    break

        field_dialog.destroy()

        if done:
            return ret
        return None
