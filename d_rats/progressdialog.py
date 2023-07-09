'''Progress Dialog Widget'''
# Copyright 2008 Dan Smith <dsmith@danplanet.com>
# Copyright 2021-2023 John. E. Malmberg - Python3 Conversion
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

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import Gdk

# Note this class is not currently used.

class ProgressDialog(Gtk.Window):
    '''
    Progress Dialog Window.

    :param title: Title for window
    :type title: str
    :param parent: Is a parent Window
    :type parent: bool
    '''

    def __init__(self, title, parent=None):
        Gtk.Window.__init__(self, type=Gtk.WindowType.TOPLEVEL)
        self.set_modal(True)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_title(title)
        if parent:
            self.set_transient_for(parent)

        self.set_resizable(False)

        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 2)

        self.label = Gtk.Label.new("")
        self.label.set_size_request(100, 50)
        self.label.show()

        self.pbar = Gtk.ProgressBar()
        self.pbar.show()

        vbox.pack_start(self.label, 0, 0, 0)
        vbox.pack_start(self.pbar, 0, 0, 0)

        vbox.show()

        self.add(vbox)

    def set_text(self, text):
        '''
        Set Text.

        :param text: Text to set
        :type text: str
        '''
        self.label.set_text(text)
        self.queue_draw()

        while Gtk.events_pending():
            Gtk.main_iteration_do(False)

    def set_fraction(self, frac):
        '''
        Set Fraction.

        :param frac: Fraction to set
        :type frac: float
        '''
        self.pbar.set_fraction(frac)
        self.queue_draw()

        while Gtk.events_pending():
            Gtk.main_iteration_do(False)


def test():
    '''Unit Test'''

    window = ProgressDialog("ProgressBar")
    window.connect("destroy", Gtk.main_quit)

    window.set_fraction(0.25)
    window.show()

    try:
        Gtk.main()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    test()
