'''Map Zoom Controls Module.'''
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


class MapZoomControls(Gtk.Frame):
    '''
    Map zoom controls.

    :param map_widget: Map Widget for control
    :type map_widget: :class:`Map.Widget`
    :param zoom: Initial zoom level, Default 14
    :type zoom: int
    '''
    def __init__(self, map_widget, zoom=14):
        Gtk.Frame.__init__(self)
        zoom_label = _("Zoom") + " (%i)" % zoom
        self.set_label(zoom_label)
        self.map_widget = map_widget
        self.set_label_align(0.5, 0.5)
        self.set_size_request(150, 50)
        self.show()

        box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 3)
        box.set_border_width(3)
        box.show()

        label = Gtk.Label.new(_("Min"))
        label.show()
        box.pack_start(label, 0, 0, 0)

        # mm here the allowed zoom levels are from 2 to 17 (increased to 18)
        adj = Gtk.Adjustment.new(value=zoom,
                                 lower=2,
                                 upper=18,
                                 step_increment=1,
                                 page_increment=3,
                                 page_size=0)
        # scroll_bar = Gtk.HScrollbar(adj)
        scroll_bar = Gtk.Scrollbar.new(Gtk.Orientation.HORIZONTAL, adj)
        scroll_bar.show()
        box.pack_start(scroll_bar, 1, 1, 1)

        label = Gtk.Label.new(_("Max"))
        label.show()
        box.pack_start(label, 0, 0, 0)

        self.add(box)

        scroll_bar.connect("value-changed", self.zoom, self)


    def zoom(self, adj, frame):
        '''
        Zoom.

        :param adj: Gtk.Adjustment object
        :param frame: Frame for zoom
        '''
        print("self:", type(self))
        print("adj)", type(adj))
        print("frame", type(frame))
        self.map_widget.set_zoom(int(adj.get_value()))
        self.set_label(_("Zoom") + " (%i)" % int(adj.get_value()))
