'''Map Status Box Module.'''
#
# Copyright 2021 John Malmberg <wb8tyw@gmail.com>
# Portions derived from works:
# Copyright 2009 Dan Smith <dsmith@danplanet.com>
# review 2019 Maurizio Andreotti  <iz2lxi@yahoo.it>
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

# import logging

import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk


# This makes pylance happy with out overriding settings
# from the invoker of the class
if not '_' in locals():
    import gettext
    _ = gettext.gettext


class MapStatusBox(Gtk.Box):
    '''
    Map Status Box.

    Create a status box for Map information
    '''

    def __init__(self):
        Gtk.Box.__init__(self, Gtk.Orientation.HORIZONTAL, 2)

        self.sb_coords = Gtk.Statusbar()
        self.sb_coords.show()
        # self.sb_coords.set_has_resize_grip(False)

        self.sb_center = Gtk.Statusbar()
        self.sb_center.show()
        # self.sb_center.set_has_resize_grip(False)

        self.sb_gps = Gtk.Statusbar()
        self.sb_gps.show()

        self.sb_prog = Gtk.ProgressBar()
        self.sb_prog.set_show_text(True)
        self.sb_prog.set_size_request(150, -1)
        self.sb_prog.show()

        self.pack_start(self.sb_coords, True, True, True)
        self.pack_start(self.sb_center, True, True, True)
        self.pack_start(self.sb_prog, False, False, False)
        self.pack_start(self.sb_gps, True, True, True)
        self.show()
