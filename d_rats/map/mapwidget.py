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

# Silence pylint warnings
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
