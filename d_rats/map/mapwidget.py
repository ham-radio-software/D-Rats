'''Map Widget Module.'''
#
# Copyright 2021-2022 John Malmberg <wb8tyw@gmail.com>
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

import logging
import time

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import Gdk

from ..gps import value_with_units
from .. import map as Map

# This makes pylance happy with out overriding settings
# from the invoker of the class
if not '_' in locals():
    import gettext
    _ = gettext.gettext


# pylint: disable=too-many-instance-attributes
class MapWidget(Gtk.DrawingArea):
    '''
    MapWidget

    :param width: Width of widget
    :type width: int
    :param height: Height of widget
    :type height: int
    :param window: Parent window
    :type status: :class:`Map.MapWindow`
    '''

    #__gsignals__ = {
    #    "redraw-markers" : (GObject.SignalFlags.RUN_LAST,
    #                        GObject.TYPE_NONE,
    #                        ()),
    #    "new-tiles-loaded" : (GObject.SignalFlags.ACTION,
    #                          GObject.TYPE_NONE,
    #                          ()),
    #    }
    #_color_black = None
    _x_fudge = 0
    _y_fudge = 0
    LAT_MAX = 90
    LON_MAX = 180

    def __init__(self, width, height, window=None):
        Gtk.DrawingArea.__init__(self)

        self.logger = logging.getLogger("MapWidget")
        self.height = height
        self.width = width

        # size of a map tile in Gtk window dimensions
        self.tilesize = Map.Tile.get_tilesize()
        # this is used for drawing the scale.
        self.pixels = self.tilesize / 2
        # The above appear to be constants in the d-rats program.

        # originally commented out
        # self.logger.debug(mapwidget - height %s, width %s", height, width)
        self.map_window = window

        self.position = None

        self._lat_max = self._lat_min = 0
        self._lon_max = self._lon_min = 0

        self.map_tiles = []
        self.map_visible = {}

        self.set_size_request(self.tilesize * self.width,
                              self.tilesize * self.height)
        self.connect("draw", Map.Draw.handler)

    # pylint wants a maximum of 15 local variables
    # pylint: disable=too-many-locals
    def calculate_bounds(self):
        '''Calculate Bounds.'''
        center = Map.Tile.center

        # here we set the bounds for the map into the window
        # delta is the mid of the tiles used to draw the map
        # delta is necessary to keep alignment between the map
        # and the station labels
        delta_h, delta_w = Map.Tile.get_display_center()
        topleft = center + (-delta_w, -delta_h)
        botright = center + (delta_w, delta_h)
        (lat_min, _, _, lon_min) = botright.tile_edges()
        (_, lon_max, lat_max, _) = topleft.tile_edges()
        # For use in comparisons, these values need to always be positive.
        # So we must add the self.LAT_MAX and self.LON_MAX to them.
        self._lat_min = lat_min + self.LAT_MAX
        self._lat_max = lat_max + self.LAT_MAX
        self._lon_min = lon_min + self.LON_MAX
        self._lon_max = lon_max + self.LON_MAX

    def export_to(self, filename, bounds):
        '''
        Export To File in PNG format.

        :param filename: Filename to export to
        :type filename: str
        :param bounds: bounds of screen
        :type bounds: tuple of 4 items
        '''
        if not bounds:
            x_axis = 0
            y_axis = 0
            bounds = (0, 0, -1, -1)
            width = self.tilesize * self.width
            height = self.tilesize * self.height
        else:
            x_axis = bounds[0]
            y_axis = bounds[1]
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]

        gdk_window = self.get_window()
        self.queue_draw()
        time.sleep(1)
        pixbuf = Gdk.pixbuf_get_from_window(gdk_window,
                                            x_axis, y_axis,
                                            width, height)
        pixbuf.savev(filename, "png", [], [])

    def map_scale_pango_layout(self):
        '''
        Map Scale Pango Layout.

        :returns: Map scale text in a pango layout
        :rtype: :class:`Pango.Layout`
        '''
        pos_a = Map.Tile.display2deg(self.tilesize, self.tilesize)
        pos_b = Map.Tile.display2deg(self.tilesize * 2, self.tilesize)

        # calculate width of one tile to show below the ladder scale
        d_width = pos_a.distance(pos_b) * (float(self.pixels) / self.tilesize)

        dist = value_with_units(d_width)

        # This layout needs to be replaced when the map_widget pango_context
        # is changed.
        pango_layout = self.create_pango_layout(dist)
        return pango_layout

    def point_is_visible(self, point):
        '''
        Point is Visible.

        :param point: Point to check
        :type point: :class:`MapPosition`
        :returns: True if visible
        :rtype: bool
        '''
        position = Map.Position(point.get_latitude(), point.get_longitude())
        for i in self.map_tiles:
            if position in i:
                return True

        return False

    # def scroll_event(self, widget, event):
    #    '''
    #    Mouse Wheel Scroll Event.
    #
    #    :param widget: Scroll widget
    #    :type widget: :class:`Gtk.ScrolledWindow`
    #    :param event: Event that was signaled
    #    :type event: :class:`Gdk.EventScroll`
    #    '''
    #    Does not appear useful to handle.

    def set_center(self, position):
        '''
        Set Center.

        :param position: position for new center
        :type position: :class:`Map.MapPosition`
        '''
        self.position = position
        #self.map_tiles = []
        #self.refresh_marker_list()

        # The scroll adjustments have no value until being exposed
        # So we need to tell the expose handler to center them.
        Map.Draw.set_center(position)
        Map.Tile.set_center(position)
        self.queue_draw()

    def value_x_event(self, _widget):
        '''
        Scrolling value of X or Y change.

        :param _widget: adjustment widget, currently unused
        :type _widget: :class:`Gtk.Adjustment`
        '''
        self.queue_draw()

    def value_y_event(self, _widget):
        '''
        Scrolling value of y change.

        :param _widget: adjustment widget, Currently unused.
        :type _widget: :class:`Gtk.Adjustment`
        '''
        self.queue_draw()
