'''Map Bottom Panel Module.'''
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

import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk

from .. import map as Map


# This makes pylance happy with out overriding settings
# from the invoker of the class
if not '_' in locals():
    import gettext
    _ = gettext.gettext


class MapMakeTrack(Gtk.CheckButton):
    '''
    Enable making a track on map

    :param map_window: Parent Map window
    :type map_window: :class:`map.MapWindow`
    '''
    def __init__(self, map_window):
        Gtk.CheckButton.__init__(self)
        self.set_label(_("Track center"))

        def toggle(check_button, map_window):
            map_window.tracking_enabled = check_button.get_active()

        self.connect("toggled", toggle, map_window)
        self.show()


class MapControls(Gtk.Box):
    '''
    Make Controls for Map

    :param map_window: Parent Map window
    :type map_window: :class:`map.MapWindow`
    '''
    def __init__(self, map_window):
        Gtk.Box.__init__(self)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_spacing(2)
        zoom_control = Map.ZoomControls(map_window.map_widget)
        self.pack_start(zoom_control, False, False, False)
        make_track = MapMakeTrack(map_window)
        self.pack_start(make_track, False, False, False)
        self.show()


class MapBottomPanel(Gtk.Box):
    '''
    Map Bottom Panel.

    :param map_window: Parent Map window
    :type map_window: :class:`map.MapWindow`
    '''
    def __init__(self, map_window):
        Gtk.Box.__init__(self)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.set_spacing(2)
        marker_list = Map.MarkerList(map_window)
        self.pack_start(marker_list, True, True, True)
        controls = MapControls(map_window)
        self.pack_start(controls, False, False, False)
        self.show()
