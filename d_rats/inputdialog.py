#!/usr/bin/python
#
# Copyright 2008 Dan Smith <dsmith@danplanet.com>
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
'''Input Dialog Module'''

from __future__ import absolute_import
from __future__ import print_function

import gi
gi.require_version("Gtk", "3.0")
# pylint: disable=wrong-import-position
from gi.repository import Gtk
from gi.repository import Gdk

from .miscwidgets import make_choice

class TextInputDialog(Gtk.Dialog):
    '''Text input dialog class'''

    # pylint: disable=unused-argument
    def respond_ok(self, *args):
        ''' Respond Ok '''

        self.response(Gtk.ResponseType.OK)

    def __init__(self, **args):
        buttons = (Gtk.ButtonsType.CANCEL, Gtk.ResponseType.CANCEL,
                   Gtk.ButtonsType.OK, Gtk.ResponseType.OK)
        Gtk.Dialog.__init__(self, buttons=buttons, **args)

        self.label = Gtk.Label.new()
        self.label.set_size_request(300, 100)
        self.vbox.pack_start(self.label, 1, 1, 0)

        self.text = Gtk.Entry()
        self.text.connect("activate", self.respond_ok, None)
        self.vbox.pack_start(self.text, 1, 1, 0)

        self.label.show()
        self.text.show()

class ChoiceDialog(Gtk.Dialog):
    editable = False

    def __init__(self, choices, **args):
        buttons = (Gtk.ButtonsType.CANCEL, Gtk.ResponseType.CANCEL,
                   Gtk.ButtonsType.OK, Gtk.ResponseType.OK)
        Gtk.Dialog.__init__(self, buttons=buttons, **args)

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

class EditableChoiceDialog(ChoiceDialog):
    '''Editable Choice Dialog'''

    editable = True

    def __init__(self, choices, **args):
        ChoiceDialog.__init__(self, choices, **args)

        self.choice.child.set_activates_default(True)

class ExceptionDialog(Gtk.MessageDialog):
    '''Exception for Dialog'''

    def __init__(self, exception, **args):
        Gtk.MessageDialog.__init__(self, buttons=Gtk.ButtonsType.OK, **args)
        self.set_property("text", _("An error has occurred"))
        self.format_secondary_text(str(exception))

class FieldDialog(Gtk.Dialog):
    '''Field Dialog Task'''

    def __init__(self, **kwargs):
        if "buttons" not in list(kwargs.keys()):
            kwargs["buttons"] = (_("Ok"), Gtk.ResponseType.OK,
                                 _("Cancel"),
                                 Gtk.ResponseType.CANCEL)

        self.__fields = {}

        Gtk.Dialog.__init__(self, **kwargs)
        self.set_default_response(Gtk.ResponseType.OK)

        self.set_modal(True)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)

    # Can not find what arguments are actually different
    # pylint: disable=arguments-differ
    def response(self, response):
        '''Response logging'''
        print("Blocking response %d" % response)

    def add_field(self, label, widget, _validator=None, full=False):
        ''' Add field to a widget '''

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
        return self.__fields.get(label, None)


def main():
    '''main function for testing'''

    if not __package__:
        # pylint: disable=redefined-builtin
        __package__ = '__main__'
    import gettext

    lang = gettext.translation("D-RATS",
                               localedir="./locale",
                               languages=["en"],
                               fallback=True)
    lang.install()

    dialog = FieldDialog(buttons=(_("Ok"), Gtk.ResponseType.OK))
    dialog.add_field("Foo", Gtk.Entry())
    dialog.add_field("Bar", make_choice(["A", "B"]))
    dialog.run()
    Gtk.main()
    dialog.destroy()


if __name__ == "__main__":
    main()
