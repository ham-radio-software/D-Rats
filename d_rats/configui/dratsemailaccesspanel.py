# File: configui/dratsemailaccesspanel.py

'''D-Rats Email Access Panel Module.'''

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
import random

import gi  # type: ignore # Needed for pylance on Windows.
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk        # type: ignore
from gi.repository import GObject    # type: ignore

if not '_' in locals():
    import gettext
    _ = gettext.gettext

from .dratspanel import DratsPanel
from .dratslistconfigwidget import DratsListConfigWidget
from ..miscwidgets import make_choice
from ..inputdialog import FieldDialog


class DratsEmailAccessPanel(DratsPanel):
    '''
    D-Rats Email Access Panel.

    :param dialog: D-Rats Config UI Dialog, unused.
    :type dialog: :class:`config.DratsConfigUI`
    '''

    INITIAL_ROWS = 2
    logger = logging.getLogger("DratsEmailAccessPanel")

    # pylint: disable=unused-argument
    def __init__(self, dialog=None):
        DratsPanel.__init__(self)

        cols = [(GObject.TYPE_STRING, "ID"),
                (GObject.TYPE_STRING, _("Callsign")),
                (GObject.TYPE_STRING, _("Access")),
                (GObject.TYPE_STRING, _("Email Filter"))]

        self.choices = {
            _("Access") : [_("None"), _("Both"), _("Incoming"), _("Outgoing")],
            }

        val = DratsListConfigWidget(section="email_access")

        def make_key(vals):
            return "%s/%i" % (vals[0], random.randint(0, 1000))

        list_widget = val.add_list(cols, make_key)
        add = Gtk.Button.new_with_label(_("Add"))
        add.connect("clicked", self.but_add, list_widget)
        edit = Gtk.Button.new_with_label(_("Edit"))
        edit.connect("clicked", self.but_edit, list_widget)
        rem = Gtk.Button.new_with_label(_("Remove"))
        rem.connect("clicked", self.but_rem, list_widget)

        list_widget.set_sort_column(1)

        self.make_view(_("Email Access"), val, add, edit, rem)

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
        # self.attach(widgets[0], 0, 2, 0, 1)

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
            # self.attach(box, 0, 2, 1, 2, yoptions=Gtk.AttachOptions.SHRINK)
            self.attach_next_to(box, widgets[0], Gtk.PositionType.BOTTOM,
                                1, box_height)


    @staticmethod
    def but_rem(_button, list_widget):
        '''
        Button Remove.

        :param _button: Button widget unused
        :type _button: :class:`Gtk.Button`
        :param list_widget: Listing widget
        :type list_widget: :class:`DratsListConfigWidget`
        '''
        list_widget.del_item(list_widget.get_selected())

    def prompt_for_entry(self, fields):
        '''
        Prompt for entry.

        :param fields: Fields for entry
        :type fields: list[tuple(str, type, any)]
        :returns: Dictionary of fields or None
        :rtype: dict
        '''
        dlg = FieldDialog()
        for n_field, t_field, d_field in fields:
            if n_field in list(self.choices.keys()):
                choice = make_choice(self.choices[n_field],
                                     False, d_field)
            else:
                choice = Gtk.Entry()
                choice.set_text(str(d_field))
            dlg.add_field(n_field, choice)

        ret = {}

        done = False
        # pylint: disable=no-member
        while not done and dlg.run() == Gtk.ResponseType.OK:
            done = True
            for n_field, t_field, _d_field in fields:
                try:
                    if n_field in list(self.choices.keys()):
                        value = dlg.get_field(n_field).get_active_text()
                    else:
                        value = dlg.get_field(n_field).get_text()

                    if n_field == _("Callsign"):
                        if not value:
                            raise ValueError("empty")
                        value = value.upper()
                    ret[n_field] = t_field(value)
                except ValueError as error:
                    e_dialog = Gtk.MessageDialog(buttons=Gtk.ButtonsType.OK)
                    e_dialog.set_property("text",
                                          _("Invalid value for") + "%s: %s" %
                                          (n_field, error))
                    e_dialog.run()
                    e_dialog.destroy()
                    done = False
                    break

        dlg.destroy()
        if done:
            return ret
        return None

    def but_add(self, _button, list_widget):
        '''
        Button Add.

        :param _button: widget, not used
        :type _button: :class:`Gtk.Button`
        :param list_widget: List widget
        :type list_widget: :class:`DratsListConfigWidget`
        '''
        fields = [(_("Callsign"), str, ""),
                  (_("Access"), str, _("Both")),
                  (_("Email Filter"), str, "")]
        ret = self.prompt_for_entry(fields)
        if ret:
            id_val = "%s/%i" % (ret[_("Callsign")],
                                random.randint(1, 1000))
            list_widget.set_item(id_val,
                                 ret[_("Callsign")],
                                 ret[_("Access")],
                                 ret[_("Email Filter")])

    def but_edit(self, _button, list_widget):
        '''
        Button Edit.

        :param _button: Button widget, not used
        :type _button: :class:`Gtk.Button`
        :param list_widget: List widget
        :type list_widget: :class:`DratsListConfigWidget`
        '''
        vals = list_widget.get_item(list_widget.get_selected())
        if not vals:
            return
        fields = [(_("Callsign"), str, vals[1]),
                  (_("Access"), str, vals[2]),
                  (_("Email Filter"), str, vals[3])]
        id_val = vals[0]
        ret = self.prompt_for_entry(fields)
        if ret:
            list_widget.del_item(id_val)
            list_widget.set_item(id_val,
                                 ret[_("Callsign")],
                                 ret[_("Access")],
                                 ret[_("Email Filter")])
