# File: configui/dratsinemailpanel.py

'''D-Rats Incoming Email Panel Module.'''

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
from gi.repository import GObject    # type: ignore

if not '_' in locals():
    import gettext
    _ = gettext.gettext

from .dratspanel import DratsPanel
from .dratslistconfigwidget import DratsListConfigWidget
from ..miscwidgets import make_choice
from ..inputdialog import FieldDialog


class DratsInEmailPanel(DratsPanel):
    '''
    D-Rats In Email Panel.

    :param dialog: D-Rats Config UI Dialog
    :type dialog: :class:`config.DratsConfigUI`
    '''

    INITIAL_ROWS = 2
    logger = logging.getLogger("DratsInEmailPanel")

    # pylint: disable=unused-argument
    def __init__(self, dialog=None):
        DratsPanel.__init__(self)

        cols = [(GObject.TYPE_STRING, "ID"),
                (GObject.TYPE_STRING, _("Server")),
                (GObject.TYPE_STRING, _("Username")),
                (GObject.TYPE_STRING, _("Password")),
                (GObject.TYPE_INT, _("Poll Interval")),
                (GObject.TYPE_BOOLEAN, _("Use SSL")),
                (GObject.TYPE_INT, _("Port")),
                (GObject.TYPE_STRING, _("Action")),
                (GObject.TYPE_BOOLEAN, _("Enabled"))
                ]

        self.choices = {
            _("Action") : [_("Form"), _("Chat")],
            }

        # Remove after 0.1.9
        self.convert_018_values("incoming_email")

        val = DratsListConfigWidget(section="incoming_email")

        def make_key(vals):
            return "%s@%s" % (vals[0], vals[1])

        list_widget = val.add_list(cols, make_key)
        list_widget.set_password(2)
        add = Gtk.Button.new_with_label(_("Add"))
        add.connect("clicked", self.but_add, list_widget)
        edit = Gtk.Button.new_with_label(_("Edit"))
        edit.connect("clicked", self.but_edit, list_widget)
        rem = Gtk.Button.new_with_label(_("Remove"))
        rem.connect("clicked", self.but_rem, list_widget)

        list_widget.set_sort_column(1)

        self.make_view(_("Incoming Accounts"), val, add, edit, rem)

    # pylint: disable=arguments-differ
    def make_view(self, _title, *widgets):
        '''
        Make View.

        set information for a widget
        :param _title: Title for widget
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

    def but_rem(self, _button, list_widget):
        '''
        Button remove.

        :param _button: Unused
        :type _button: :class:`Gtk.Button`
        :param list_widget: widget for button
        :type list_widget: :class:`DratsListConfigWidget`
        '''
        vals = list_widget.get_selected()
        if not vals:
            self.logger.info("but_rem: Nothing selected for remove!")
            return
        list_widget.del_item(vals)

    # pylint wants a max of 12 branches
    # pylint: disable=too-many-branches
    def prompt_for_acct(self, fields):
        '''
        Prompt For Account.

        :param fields: Fields for account dialog
        :type fields: list[tuple[str, type, any]]
        :returns: Dictionary containing account information
        :rtype: dict:
        '''
        dlg = FieldDialog()
        for n_field, t_field, d_field in fields:
            if n_field in list(self.choices.keys()):
                entry = make_choice(self.choices[n_field],
                                    False, d_field)
            elif n_field == _("Password"):
                entry = Gtk.Entry()
                entry.set_visibility(False)
                entry.set_text(str(d_field))
            elif t_field == bool:
                entry = Gtk.CheckButton.new_with_label(_("Enabled"))
                entry.set_active(d_field)
            else:
                entry = Gtk.Entry()
                entry.set_text(str(d_field))
            dlg.add_field(n_field, entry)

        ret = {}

        done = False
        # pylint: disable=no-member
        while not done and dlg.run() == Gtk.ResponseType.OK:
            done = True
            for n_field, t_field, _d_field in fields:
                try:
                    if n_field in list(self.choices.keys()):
                        value = dlg.get_field(n_field).get_active_text()
                    elif t_field == bool:
                        value = dlg.get_field(n_field).get_active()
                    else:
                        value = dlg.get_field(n_field).get_text()
                        if not value:
                            raise ValueError("empty")
                    ret[n_field] = t_field(value)
                except ValueError as error:
                    e_dialog = Gtk.MessageDialog(buttons=Gtk.ButtonsType.OK)
                    e_dialog.set_property("text",
                                          _("Invalid value for") + " %s: %s" %
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

        :param _button: Unused
        :type _button: :class:`Gtk.Button`
        :param list_widget: widget for button
        :type list_widget: :class:`DratsListConfigWidget`
        '''
        fields = [(_("Server"), str, ""),
                  (_("Username"), str, ""),
                  (_("Password"), str, ""),
                  (_("Poll Interval"), int, 5),
                  (_("Use SSL"), bool, False),
                  (_("Port"), int, 110),
                  (_("Action"), str, "Form"),
                  (_("Enabled"), bool, True),
                  ]
        ret = self.prompt_for_acct(fields)
        if ret:
            id_val = "%s@%s" % (ret[_("Server")], ret[_("Username")])
            list_widget.set_item(id_val,
                                 ret[_("Server")],
                                 ret[_("Username")],
                                 ret[_("Password")],
                                 ret[_("Poll Interval")],
                                 ret[_("Use SSL")],
                                 ret[_("Port")],
                                 ret[_("Action")],
                                 ret[_("Enabled")])

    def but_edit(self, _button, list_widget):
        '''
        Button Edit.

        :param _button: Unused
        :type _button: :class:`Gtk.Button`
        :param list_widget: widget for button
        :type list_widget: :class:`DratsListConfigWidget`
        '''
        # The code that sets up this button should not activate it
        # unless the button has something to do.
        vals = list_widget.get_item(list_widget.get_selected())
        if not vals:
            self.logger.info("but_edit: Nothing selected for editing!")
            return
        fields = [(_("Server"), str, vals[1]),
                  (_("Username"), str, vals[2]),
                  (_("Password"), str, vals[3]),
                  (_("Poll Interval"), int, vals[4]),
                  (_("Use SSL"), bool, vals[5]),
                  (_("Port"), int, vals[6]),
                  (_("Action"), str, vals[7]),
                  (_("Enabled"), bool, vals[8]),
                  ]
        id_val = "%s@%s" % (vals[1], vals[2])
        ret = self.prompt_for_acct(fields)
        if ret:
            list_widget.del_item(id_val)
            id_val = "%s@%s" % (ret[_("Server")], ret[_("Username")])
            list_widget.set_item(id_val,
                                 ret[_("Server")],
                                 ret[_("Username")],
                                 ret[_("Password")],
                                 ret[_("Poll Interval")],
                                 ret[_("Use SSL")],
                                 ret[_("Port")],
                                 ret[_("Action")],
                                 ret[_("Enabled")])

    def convert_018_values(self, section):
        '''
        Convert 018 Values.

        :param section: Section to convert
        :type section: str
        '''
        if not self.config.has_section(section):
            return
        options = self.config.options(section)
        for opt in options:
            val = self.config.get(section, opt)
            if len(val.split(",")) < 7:
                val += ",Form"
                self.config.set(section, opt, val)
                self.logger.info("7-8 Converted %s/%s", section, opt)
            if len(val.split(",")) < 8:
                val += ",True"
                self.config.set(section, opt, val)
                self.logger.info("8-9 Converted %s/%s", section, opt)
