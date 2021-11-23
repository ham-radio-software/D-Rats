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

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
gi.require_version("PangoCairo", "1.0")

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

    # pylint: disable=too-many-arguments
    def __init__(self, width, height, tilesize=256, window=None):
        Gtk.DrawingArea.__init__(self)

        self.logger = logging.getLogger("MapWidget")
        # self.__broken_tile = None
        # self.pixmap = None  # Replaced by self.surface
        # self.surface = None
        # self.window = window

        self.height = height
        self.width = width

        # originally commented out
        # printlog("Mapdisplay",
        #        ": mapwidget - height %s, width %s" % (height, width))
        self.tilesize = tilesize
        self.mapwindow = window

        self.position = None

        self.lat_max = self.lat_min = 0
        self.lon_max = self.lon_min = 0
        self.lng_fudge = 0
        self.lat_fudge = 0

        self.map_tiles = []
        self.map_visible = {}
        self.map_visible['x_start'] = 0
        self.map_visible['y_start'] = 0
        self.map_visible['x_size'] = 0
        self.map_visible['y_size'] = 0

        self.set_size_request(self.tilesize * self.width,
                              self.tilesize * self.height)
        self.connect("draw", Map.Draw.handler)

    def map_distance_with_units(self, pixels):
        '''
        Map Distance with units.

        :param pixels: Number of pixels per tile
        :type pixels: int
        :returns: Size of a map tile
        :rtype: str
        '''
        pos_a = self.xy2latlon(self.tilesize, self.tilesize)
        pos_b = self.xy2latlon(self.tilesize * 2, self.tilesize)

        # calculate width of one tile to show below the ladder scale
        d_width = pos_a.distance(pos_b) * (float(pixels) / self.tilesize)

        dist = value_with_units(d_width)
        return dist

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
        print("Map.MapWidget.set_center old %s" % position)
        self.position = position
        #self.map_tiles = []
        print("Map.MapWidget.set_center new %s" % position)
        self.queue_draw()

    def value_x_event(self, widget):
        '''
        Scrolling value of X change.

        :param widget: adjustment widget
        :type widget: :class:`Gtk.Adjustment`
        '''
        print("value_x_event", widget.get_value(), widget.get_page_size(),
              self.map_visible['x_start'])
        # self.map_visible['x_start'] = widget.get_value()
        # self.map_visible['x_size'] = widget.get_page_size()
        # self.map_tiles = []
        # Signal a map redraw
        self.queue_draw()

    def value_y_event(self, widget):
        '''
        Scrolling value of y change.

        :param widget: adjustment widget
        :type widget: :class:`Gtk.Adjustment`
        '''
        print("value_y_event", widget.get_value(), widget.get_page_size(),
              self.map_visible['y_start'])
        # self.map_visible['y_start'] = widget.get_value()
        # self.map_visible['y_size'] = widget.get_page_size()
        # self.map_tiles = []
        # Signal a map redraw
        self.queue_draw()

    def xy2latlon(self, x_axis, y_axis):
        '''
        Translate X, Y axes to latitude and longitude.

        :param x_axis: X Axis
        :param y_axis: Y Axis
        :returns: Position of the coordinate
        :rtype: :class:`map.MapPosition`
        '''
        y_axis -= self.lat_fudge
        x_axis -= self.lng_fudge

        lon = 1 - (float(x_axis) / (self.tilesize * self.width))
        lat = 1 - (float(y_axis) / (self.tilesize * self.height))

        lat = (lat * (self.lat_max - self.lat_min)) + self.lat_min
        lon = (lon * (self.lon_max - self.lon_min)) + self.lon_min

        return Map.Position(lat, lon)
