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

# This makes pylance happy with out overriding settings
# from the invoker of the class
if not '_' in locals():
    import gettext
    _ = gettext.gettext


class MapPosition():
    '''
    Map Position.

    :param latitude: Latitude of position, Default 0.0
    :type latitude: float
    :param longitude: Longitude of position, Default 0.0
    :type longitude: float
    '''

    def __init__(self, latitude=0.0, longitude=0.0):
        self.latitude = latitude
        self.longitude = longitude
        self._format = "%.4f, %.4f"

    def set_format(self, format_string=None):
        '''
        Set the format string

        :param format_string: Format, default "%.4f, %.4f"
        :type format_string: str
        :returns: Formatted position
        :rtype: str
        '''
        if format_string:
            self._format = format_string

    def __str__(self):
        return self._format % (self.latitude, self.longitude)


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
    :param status: Status callback function
    :type status: function(float, str)
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
    def __init__(self, width, height, tilesize=256, status=None):
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
        self.status = status

        self.lat = 0
        self.lon = 0
        self.zoom = 1

        self.lat_max = self.lat_min = 0
        self.lon_max = self.lon_min = 0
        self.lng_fudge = 0
        self.lat_fudge = 0

        self.lat_fudge = 0
        self.lng_fudge = 0

        self.map_tiles = []
        self.x_axis = 0
        self.y_axis = 0

        #self.set_size_request(self.tilesize * self.width,
        #                      self.tilesize * self.height)
        #self.connect("draw", self.expose)

    def set_zoom(self, zoom):
        '''
        Set Zoom Level.

        If the Zoom level changes, this should cause a Map redraw.
        :param zoom: Zoom level to set
        :type zoom: int
        '''
        # What should happen for zoom in [0, 1, 2]?
        if zoom > 18 or zoom == 3:
            return

        self.zoom = zoom
        self.map_tiles = []
        # self.queue_draw()

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

        return MapPosition(lat, lon)
