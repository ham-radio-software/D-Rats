#!/usr/bin/python
#
# Copyright 2008 Dan Smith <dsmith@danplanet.com>
# Copyright 2021-2022 John. E. Malmberg - Python3 Conversion
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
'''Input Dialog Module.'''

from __future__ import absolute_import
from __future__ import print_function

import logging
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import Gdk

if not '_' in locals():
    import gettext
    _ = gettext.gettext

from .miscwidgets import make_choice


# pylint: disable=too-few-public-methods
class TextInputDialog(Gtk.Dialog):
    '''
    Text Input Dialog.

    :param title: Title for dialog, default None
    :type title: str
    :param parent: Parent widget, default None
    :type parent: :class:`Gtk.Window`
    '''

    def __init__(self, title=None, parent=None):
        Gtk.Dialog.__init__(self, parent=parent)

        if title:
            self.set_title(title)
        self.add_button(_("CANCEL"), Gtk.ResponseType.CANCEL)
        self.add_button(_("OK"), Gtk.ResponseType.OK)
        self.label = Gtk.Label.new()
        self.label.set_size_request(300, 100)
        self.vbox.pack_start(self.label, 1, 1, 0)

        self.text = Gtk.Entry()
        self.text.connect("activate", self.respond_ok, None)
        self.vbox.pack_start(self.text, 1, 1, 0)

        self.label.show()
        self.text.show()

    def respond_ok(self, *_args):
        '''
        Respond Ok

        :param _args: Additional Arguments, Unused
        '''
        self.response(Gtk.ResponseType.OK)


# pylint: disable=too-few-public-methods
class ChoiceDialog(Gtk.Dialog):
    '''
    Choice Dialog.

    :param choices: List of strings with choices
    :type choices: list[str]
    :param title: Title for dialog, default None
    :type title: str
    :param parent: Parent Widget, default None
    :type parent: :class:`Gtk.Window`
    '''

    editable = False

    def __init__(self, choices, title=None, parent=None):
        Gtk.Dialog.__init__(self, parent=parent)

        if title:
            self.set_title(title)
        self.add_button(_("CANCEL"), Gtk.ResponseType.CANCEL)
        self.add_button(_("OK"), Gtk.ResponseType.OK)
        self.label = Gtk.Label.new()
        self.label.set_size_request(300, 100)
        self.vbox.pack_start(self.label, 1, 1, 0)
        self.label.show()

        try:
            default = choices[0]
        except IndexError:
            default = None

        self.choice = make_choice(sorted(choices), self.editable, default)
        self.vbox.pack_start(self.choice, 1, 1, 0)
        self.choice.show()

        self.set_default_response(Gtk.ResponseType.OK)


# pylint: disable=too-few-public-methods
class EditableChoiceDialog(ChoiceDialog):
    '''
    Editable Choice Dialog.

    This class does not appear to be used.
    :param choices: List of strings with choices
    :type choices: list[str]
    :param title: Title for dialog, default None
    :type tile: str
    :param parent: Parent widget, default None
    :type parent: :class:`Gtk.Window`
    '''

    editable = True

    def __init__(self, choices, title=None, parent=None):
        ChoiceDialog.__init__(self, choices, title, parent)

        self.choice.child.set_activates_default(True)


# pylint: disable=too-few-public-methods
class ExceptionDialog(Gtk.MessageDialog):
    '''
    Exception Dialog.

    This class does not appear to be used.
    :param exception: Exception class
    :type exception: Exception
    :param title: Title for dialog, default None
    :param title: str
    :param parent: Parent widget, default None
    :type parent: :class:`Gtk.Window`
    '''
    def __init__(self, exception, title=None, parent=None):
        Gtk.MessageDialog.__init__(self, parent=parent)
        if title:
            self.set_title(title)
        self.add_button(_("OK"), Gtk.ResponseType.OK)
        self.set_property("text", _("An error has occurred"))
        self.format_secondary_text(str(exception))


class FieldDialog(Gtk.Dialog):
    '''
    Field Dialog.

    :param title: Title of dialog, default None
    :type title: str
    :param buttons: List of tuples for buttons, default None
    :type buttons: list[tuple[str, :class:`GtkResponseType`]]
    :param parent: Parent widget, default None
    :type parent: :class:`Gtk.Window`
    '''

    def __init__(self, title=None, buttons=None, parent=None):
        if not buttons:
            buttons = [(_("Ok"), Gtk.ResponseType.OK),
                       (_("Cancel"), Gtk.ResponseType.CANCEL)]
        self.logger = logging.getLogger("FieldDialog")
        self.__fields = {}

        Gtk.Dialog.__init__(self, parent=parent)
        if title:
            self.set_title(title)

        for button, response_type in buttons:
            self.add_button(button, response_type)
        self.set_default_response(Gtk.ResponseType.OK)

        self.set_modal(True)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)

    # Can not find what arguments are actually different as this
    # matches the documentation.
    # pylint: disable=arguments-differ
    def response(self, response):
        '''
        Response logging.

        Writes the response to the console instead emitting it.

        :param response: Response id for emitting.
        :type response: int
        '''
        self.logger.info("Blocking response %d", response)

    def add_field(self, label, widget, _validator=None, full=False):
        '''
        Add field to a widget.

        :param label: Label of field
        :type label: str
        :param widget: Widget for field
        :type widget: :class:`Gtk.Widget`
        :param _validator: Validator for field, default None, Unused
        :param full: Fill the space in the containing box
        :type full: bool
        '''
        if full:
            box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 2)
        else:
            box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 2)
            box.set_homogeneous(True)

        lab = Gtk.Label.new(label)
        lab.show()

        widget.set_size_request(150, -1)
        widget.show()

        box.pack_start(lab, 0, 0, 0)
        if full:
            box.pack_start(widget, 1, 1, 1)
        else:
            box.pack_start(widget, 0, 0, 0)
        box.show()

        if full:
            self.vbox.pack_start(box, 1, 1, 1)
        else:
            self.vbox.pack_start(box, 0, 0, 0)

        self.__fields[label] = widget

    def get_field(self, label):
        '''
        Get field.

        :param label: label of field
        :type label: str
        :returns: Field identified by label
        :rtype: :class:`Gtk.Widget`
        '''
        return self.__fields.get(label, None)


def main():
    '''main function for testing'''

    dialog = FieldDialog(buttons=[(_("Ok"), Gtk.ResponseType.OK)])
    dialog.add_field("Foo", Gtk.Entry())
    dialog.add_field("Bar", make_choice(["A", "B"]))
    dialog.run()
    dialog.connect("destroy", Gtk.main_quit)
    Gtk.main()


if __name__ == "__main__":
    main()
