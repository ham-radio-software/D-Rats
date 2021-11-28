'''Map Tile Module.'''
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

import os
import logging
import math
import threading
import time

import gi
gi.require_version("Gtk", "3.0")
#from gi.repository import Gtk
#from gi.repository import Gdk
from gi.repository import GLib

from .. import map as Map

# This makes pylance happy with out overriding settings
# from the invoker of the class
if not '_' in locals():
    import gettext
    _ = gettext.gettext


class MapTile():
    '''
    Map Tile Information

    This should be instantiated with either a position or
    the x_axis and y_axis specified.

    :param position: Latitude and Longitude, default None
    :type position: :class:`Map.MapPosition`
    :param x_axis: X axis of tile on map, default None
    :type x_axis: float
    :param y_axis: Y axis of tile on map, default None
    '''

    _base_dir = None
    _connected = False
    _map_key = None
    _map_url_key = None
    _proxy = None
    _tile_lifetime = 0
    _zoom = 0

    def __init__(self, position=None, x_axis=None, y_axis=None):

        self.logger = logging.getLogger("MapTile")
        if position:
            self.position = position
            self.x_axis, self.y_axis = self.deg2num(self.position)
        else:
            self.x_axis = x_axis
            self.y_axis = y_axis
            self.position = self.num2deg(self.x_axis, self.y_axis)

    def __str__(self):
        return "%s (%i,%i)" % (self.position, self.x_axis, self.y_axis)

    @classmethod
    def get_base_dir(cls):
        '''
        Get base directory for maps.

        :returns: Base directory
        :rtype: str
        '''
        return cls._base_dir

    @classmethod
    def set_connected(cls, connected):
        '''
        Sets if allowed to connect to the internet to download map data.

        :param connected: Connection state
        :type connected: bool
        '''
        cls._connected = connected

    @classmethod
    def set_map_info(cls, base_dir, map_url, map_url_key=None):
        '''
        Sets the map url and optional access key

        :param base_dir: Base Directory
        :type base_dir: str
        :param map_url: Url to map source
        :type map_url: str
        :param map_key: Key to allow access to maps
        :type map_key: str
        '''
        if not os.path.isdir(base_dir):
            os.makedirs(base_dir, mode=0o644, exist_ok=True)
        cls._base_dir = base_dir
        cls._map_url = map_url
        cls._map_key = map_url_key

    @classmethod
    def set_proxy(cls, proxy):
        '''
        Sets the proxy for use in accessing map data

        :param proxy: Proxy access string
        :type proxy: str
        '''
        cls._proxy = proxy

    @classmethod
    def set_tile_lifetime(cls, lifetime):
        '''
        Sets the lifetime to cache a tile

        :param lifetime: Tile lifetime in seconds
        :type lifetime: int
        '''
        cls._tile_lifetime = lifetime

    @classmethod
    def set_zoom(cls, zoom):
        '''
        Sets the zoom level to use.

        :param zoom: zoom_level
        :type zoom: int
        '''
        cls._zoom = zoom

    # The deg2num function taken from:
    #   http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames
    def deg2num(self, position):
        '''
        Degrees to number.

        :param position: Latitude and longitude
        :type position: :class:`Map.MapPosition`
        :returns: x_axis, and y_axis on map for coordinates
        :rtype: tuple of (int, int)
        '''
        # lat_rad = lat_deg * math.pi / 180.0
        lat_rad = math.radians(position.latitude)
        num = 2.0 ** self._zoom
        xtile = int((position.longitude + 180.0) / 360.0 * num)
        ytile = int((1.0 - math.log(math.tan(lat_rad) +
                                    (1 / math.cos(lat_rad))) /
                     math.pi) / 2.0 * num)
        return (xtile, ytile)

    # The deg2num function taken from:
    #   http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames
    def num2deg(self, xtile, ytile):
        '''
        Number to Degrees.

        :param xtile: X axis position of tile
        :type xtile: int
        :param ytile: Y axis position of tile
        :type ytile: int
        :returns: Map position in longitude and latitude
        :rtype: :class:`Map.MapPosition`
        '''
        num = 2.0 ** self._zoom
        lon_deg = xtile / num * 360.0 - 180.0
        lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / num)))
        lat_deg = math.degrees(lat_rad)
        return Map.Position(lat_deg, lon_deg)

    def path_els(self):
        '''
        Path ELS.

        :returns: Latitude and longitude in degrees
        '''
        return self.deg2num(self.position)

    def tile_edges(self):
        '''
        Tile Edges.

        :returns: Tuple for the North west and south east corner
                  of a tile
        :rtype: tuple of (float, float, float, float)
        '''
        northwest = self.num2deg(self.x_axis, self.y_axis)
        southeast = self.num2deg(self.x_axis + 1, self.y_axis + 1)
        return (southeast.latitude, northwest.longitude,
                northwest.latitude, southeast.longitude)

    def path(self):
        '''
        Path.

        :returns: Local path for map tile
        :rtype: str
        '''
        return "%d/%d/%d.png" % (self._zoom, self.x_axis, self.y_axis)

    def bad_path(self):
        '''
        Path for caching tiles that are are not available for download.

        :returns: Local bad path for unavailable tiles
        :rtype: str
        '''
        return "%d/%d/%d.bad" % (self._zoom, self.x_axis, self.y_axis)

    def _local_path(self):
        if not self._base_dir:
            return None
        path = os.path.join(self._base_dir, self.path())
        if not os.path.isdir(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        return path

    def _local_bad_path(self):
        if not self._base_dir:
            return None
        path = os.path.join(self._base_dir, self.bad_path())
        if not os.path.isdir(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        return path

    def get_local_tile_path(self):
        '''
        Get the local tile path if it exists.

        :returns: Local file path or None
        :rtype str:
        '''
        local_cache = self.local_path()
        if os.path.exists(self._local_path()):
            return local_cache
        return None

    def is_local(self):
        '''
        Is local?

        :returns: True if locally cached and cache is not expired
        :rtype: bool
        '''
        local_cache = self._local_path()
        local = os.path.exists(self._local_path())
        if not local:
            local_cache = self._local_bad_path()
            local = os.path.exists(self._local_bad_path())

        if not local:
            return False
        if self._tile_lifetime == 0 or not self._connected:
            return local

        time_stamp = os.stat(local_cache).st_mtime
        return (time.time() - time_stamp) < self._tile_lifetime

    def fetch(self):
        '''
        Fetch a tile.

        :returns: True if fetch is successfull or tile is cached.
        :rtype: bool
        '''
        #verify if tile is local, if not fetches from web
        if self.is_local():
            return True
        print("fetch", self.is_local())
        #for tile_num in range(10):
            #url = self.remote_path()
            #try:
                #fetch_url(url, self._local_path())
                #self.logger.info("fetch: opened %s", url)
                #return True
            # except MapTileNotFound:
            #    self.logger.info("fetch: created %s",
            #                     self._local_bad_path())
            #    with open(self._local_bad_path(), 'w'):
            #        pass
            #    self.logger.info("fetch: [%i] Not found `%s'",
            #                     tile_num, url, exc_info=True)
            #except MapFetchUrlException as err:
            #    self.logger.info("fetch: [%i] Failed to fetch `%s'",
            #                     tile_num, url, exc_info=True)

        return False


    def _thread(self, callback, *args):
        if self.fetch():
            fname = self._local_path()
        else:
            fname = None

        GLib.idle_add(callback, fname, *args)

    def threaded_fetch(self, callback, *args):
        '''
        Threaded fetch.

        :param callback: Callback for fetch
        :param args: Optional arguments
        '''
        _args = (callback,) + args
        tfetch = threading.Thread(target=self._thread, args=_args)
        tfetch.setDaemon(True)
        tfetch.start()

    def local_path(self):
        '''
        Local Path.

        :returns: Local path
        '''
        path = self._local_path()
        self.fetch()
        return path

    def remote_path(self):
        '''
        Remote Path.

        :returns: URL of path
        :rtype: str
        '''
        return self._map_url + (self.path()) + self._map_url_key

    def __add__(self, count):
        (x_axis, y_axis) = count
        return MapTile(x_axis=self.x_axis + x_axis,
                       y_axis=self.y_axis + y_axis)

    def __sub__(self, tile):
        return (self.x_axis - tile.x_axis, self.y_axis - tile.y_axis)

    def __contains__(self, point):

        # pylint: disable=fixme
        # FIXME for non-western!
        (lat_max, lon_max, lat_min, lon_min) = self.tile_edges()

        lat_match = lat_min < point.latitude < lat_max
        lon_match = lon_min < point.longitude < lon_max

        return lat_match and lon_match
