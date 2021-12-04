'''Map Widget Module.'''
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
    :param tilesize: Size of tiles, default 256
    :type tilesize: int
    :param window: Parent window
    :type status: :class:`mapWindow`
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

    def __init__(self, width, height, tilesize=256, window=None):
        Gtk.DrawingArea.__init__(self)

        self.logger = logging.getLogger("MapWidget")
        # self.__broken_tile = None
        # self.pixmap = None  # Replaced by self.surface
        # self.surface = None
        # self.window = window
        self.height = height
        self.width = width

        # size of a map tile in Gtk window dimensions
        self.tilesize = tilesize
        # apparently a tile is 128 * 128 pixels in a cairo_context
        self.pixels = 128
        # The above appear to be contants in the d-rats program.

        # originally commented out
        # printlog("Mapdisplay",
        #        ": mapwidget - height %s, width %s" % (height, width))
        self.map_window = window

        self.position = None

        self._lat_max = self._lat_min = 0
        self._lon_max = self._lon_min = 0
        self._lng_fudge = 0
        self._lat_fudge = 0

        self.map_tiles = []
        self.map_visible = {}

        self.set_size_request(self.tilesize * self.width,
                              self.tilesize * self.height)
        self.connect("draw", Map.Draw.handler)

    def calculate_bounds(self):
        '''Calculate Bounds.'''
        center = Map.Tile(position=self.position)

        # here we set the bounds for the map into the window
        # delta is the mid of the tiles used to draw the map
        # delta is necessary to keep alignment between the map
        # and the station labels
        delta = int(self.height / 2)
        topleft = center + (-delta, -delta)
        botright = center + (delta, delta)
        (self._lat_min, _, _, self._lon_min) = botright.tile_edges()
        (_, self._lon_max, self._lat_max, _) = topleft.tile_edges()

        # I have no idea why, but for some reason we can calculate the
        # longitude (x) just fine, but not the latitude (y).  The result
        # of either latlon2xy() or tile_edges() is bad, which causes the
        # y calculation of a given latitude to be off by some amount.
        # The amount grows large at small values of zoom (zoomed out) and
        # starts to seriously affect the correctness of marker placement.
        # Until I figure out why that is, we calculate a fudge factor below.
        #
        # To do this, we ask the center tile for its NW corner's
        # coordinates.  We then ask latlon2xy() (with fudge of zero) what
        # the corresponding x,y is.  Since we know what the correct value
        # should be, we record the offset and use that to shift the y in
        # further calculations for this zoom level.

        self._lng_fudge = 0
        self._lat_fudge = 0

        _south, west, north, _east = center.tile_edges()
        x_axis, y_axis = self.latlon2xy(Map.Position(north, west))
        self._lng_fudge = ((self.width / 2) * self.tilesize) - x_axis
        self._lat_fudge = ((self.height / 2) * self.tilesize) - y_axis

    # pylint: disable=no-self-use
    def center_on(self, position):
        '''
        Center On.

        :param position: position for new center
        :type position: :class:`Map.MapPosition`
        '''
        # The scroll adjustments have no value until being exposed
        # So we need to tell the expose handler to center them.
        Map.Draw.set_center(position)

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

    def latlon2xy(self, pos):
        '''
        Translate Latitude and Longitude to X and Y map coordinates

        :param pos: postion in latitude and longitude
        :type pos: :class:`Map.MapPosition`
        :returns: x and y coordinate on map
        :rtype: tuple
        '''
        y_axis = 1- ((pos.latitude - self._lat_min) /
                     (self._lat_max - self._lat_min))
        x_axis = 1- ((pos.longitude - self._lon_min) /
                     (self._lon_max - self._lon_min))

        x_axis *= (self.tilesize * self.width)
        y_axis *= (self.tilesize * self.height)

        y_axis += self._lat_fudge
        x_axis += self._lng_fudge
        return (x_axis, y_axis)

    def map_scale_pango_layout(self):
        '''
        Map Scale Pango Layout.

        :returns: Map scale text in a pango layout
        :rtype: :class:`Pango.Layout`
        '''
        pos_a = self.xy2latlon(self.tilesize, self.tilesize)
        pos_b = self.xy2latlon(self.tilesize * 2, self.tilesize)

        # calculate width of one tile to show below the ladder scale
        d_width = pos_a.distance(pos_b) * (float(self.pixels) / self.tilesize)

        dist = value_with_units(d_width)

        # This layout needs to be replaced when the map_widget pango_context
        # is changed.
        pango_layout = self.create_pango_layout(dist)
        return pango_layout


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
        self.center_on(self.position)
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

    def xy2latlon(self, x_axis, y_axis):
        '''
        Translate X, Y axes to latitude and longitude.

        :param x_axis: X Axis
        :param y_axis: Y Axis
        :returns: Position of the coordinate
        :rtype: :class:`map.MapPosition`
        '''
        y_axis -= self._lat_fudge
        x_axis -= self._lng_fudge

        lon = 1 - (float(x_axis) / (self.tilesize * self.width))
        lat = 1 - (float(y_axis) / (self.tilesize * self.height))

        lat = (lat * (self._lat_max - self._lat_min)) + self._lat_min
        lon = (lon * (self._lon_max - self._lon_min)) + self._lon_min

        return Map.Position(lat, lon)
