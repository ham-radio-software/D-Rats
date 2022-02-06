'''Map Tile Module.'''
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

import os
import logging
import math
import threading
import time
import urllib.request

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


class MapTileException(Map.MapException):
    '''Generic MapTile Exception.'''


class MapFetchUrlException(MapTileException):
    '''Map Fetch Url Exception.'''


class MapNotConnected(MapFetchUrlException):
    '''Not connected Error.'''


class MapTileNotFound(MapFetchUrlException):
    '''Map Tile Not Found.'''


class MapFetchError(MapFetchUrlException):
    '''Map Unexpected Fetch Error.'''


# pylint wants only 20 public methods.
# pylint: disable=too-many-public-methods
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
    _map_widget = None
    _tilesize = 256

    def __init__(self, position=None, x_axis=None, y_axis=None):

        self.logger = logging.getLogger("MapTile")
        if position:
            self.position = position
            self.x_tile, self.y_tile, self.x_fraction, self.y_fraction = \
               self.deg2tile(self.position)
            # Convert the tile coordinates back to the latitude, longitude
            # as a possible way to determine a future fudge factor.
            self.tile_position = self.num2deg(self.x_tile + self.x_fraction,
                                              self.y_tile + self.y_fraction)
        else:
            self.position = self.num2deg(x_axis, y_axis)
            self.x_tile = x_axis
            self.y_tile = y_axis
            _unused_x, unused_y, self.x_fraction, self.y_fraction = \
                self.deg2tile(self.position)
            self.tile_position = self.position

    def __str__(self):
        return "%s (%i,%i)" % (self.position, self.x_tile, self.y_tile)

    @classmethod
    def get_base_dir(cls):
        '''
        Get base directory for maps.

        :returns: Base directory
        :rtype: str
        '''
        return cls._base_dir

    @classmethod
    def get_tilesize(cls):
        '''
        Get the tile size

        :returns: Tile size
        :rtype: int
        '''
        return cls._tilesize

    @classmethod
    def set_connected(cls, connected):
        '''
        Sets if allowed to connect to the internet to download map data.

        :param connected: Connection state
        :type connected: bool
        '''
        cls._connected = connected

    @classmethod
    def set_map_info(cls, base_dir, map_url, map_url_key):
        '''
        Sets the map url and optional access key

        :param base_dir: Base Directory
        :type base_dir: str
        :param map_url: Url to map source
        :type map_url: str
        :param map_url_key: Key to allow access to maps
        :type map_url_key: str
        '''
        if not os.path.isdir(base_dir):
            os.makedirs(base_dir, mode=0o644, exist_ok=True)
        cls._base_dir = base_dir
        cls._map_url = map_url
        cls._map_key = map_url_key

    @classmethod
    def set_map_widget(cls, map_widget):
        '''
        Set Map Widget.

        :param map_widget: Map display widget
        :type: map_widget: :class:`Map.MapWidget`'''
        cls._map_widget = map_widget

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

    # The deg2xxx functions derived from:
    #   http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames
    @classmethod
    def deg2num(cls, position):
        '''
        Degrees to num number.

        :param position: Latitude and longitude
        :type position: :class:`Map.MapPosition`
        :returns: x_tile, and y_tile on map for coordinates
        :rtype: tuple of (float, float)
        '''
        # lat_rad = lat_deg * math.pi / 180.0
        lat_rad = math.radians(position.latitude)
        num = 2.0 ** cls._zoom
        x_coord = (position.longitude + 180.0) / 360.0 * num
        y_coord = (1.0 - math.log(math.tan(lat_rad) +
                                  (1 / math.cos(lat_rad))) /
                   math.pi) / 2.0 * num
        return (x_coord, y_coord)

    @classmethod
    def deg2tile(cls, position):
        '''
        Degrees to integer tile number and fractional portion.

        :param position: Latitude and longitude
        :type position: :class:`Map.MapPosition`
        :returns: x_tile, and y_tile and their fractional parts on map
        :rtype: tuple of (int, int, float, float)
        '''
        x_coord, y_coord = cls.deg2num(position)

        x_tile = int(x_coord)
        y_tile = int(y_coord)
        x_fraction = x_coord - x_tile
        y_fraction = y_coord - y_tile
        return (x_tile, y_tile, x_fraction, y_fraction)

    @classmethod
    def deg2pixel(cls, position):
        '''
        Degrees to a pixel offset.

        In theory this should be able to be used to plot a point based
        on degrees to a pixel offset on a map grid, and eliminate the
        need for fudge factors.

        In reality I have not been been able to get this to work.
        Points are being plotted at the wrong locations and the amount of
        error in the position is different for different nearby points at
        different zoom levels.

        Leaving this hear in case someone else can figure this out.

        :param position: Latitude and longitude
        :type position: :class:`Map.MapPosition`
        :returns: x_tile, and y_tile on map for coordinates
        :rtype: tuple of (float, float)
        '''
        x_tile, y_tile, x_fraction, y_fraction = cls.deg2tile(position)
        x_offset = cls._tilesize * (x_fraction)
        y_offset = cls._tilesize * (y_fraction)
        # For some reason the sign of the degrees seems to affect how to
        # apply the offset.
        if position.longitude >= 0:
            x_offset = -x_offset - cls._tilesize
        if position.latitude >= 0:
            y_offset = -y_offset - cls._tilesize

        x_coord = x_tile + x_offset
        y_coord = y_tile + y_offset

        return (x_coord, y_coord)

    # The deg2num function derived from:
    #   http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames
    @classmethod
    def num2deg(cls, xtile, ytile):
        '''
        Number to Degrees.

        :param xtile: X axis position of tile
        :type xtile: float
        :param ytile: Y axis position of tile
        :type ytile: float
        :returns: Map position in longitude and latitude
        :rtype: :class:`Map.MapPosition`
        '''
        num = 2.0 ** cls._zoom
        lon_deg = xtile / num * 360.0 - 180.0
        try:
            lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / num)))
        except OverflowError:
            # Appears to happen when the ytile coordinate are out of
            # range for the map.
            lat_rad = 0
        lat_deg = math.degrees(lat_rad)
        return Map.Position(lat_deg, lon_deg)

    # Can not find where this is called.
    def path_els(self):
        '''
        Path ELS.

        :returns: Latitude and longitude as map tile locations
        :rtype: tuple of (int, int)
        '''
        x_tile, y_tile, _x_off, _y_off = self.deg2tile(self.position)
        return (x_tile, y_tile)

    def tile_edges(self):
        '''
        Tile Edges.

        :returns: Tuple for the North west and south east corner
                  of a tile
        :rtype: tuple of (float, float, float, float)
        '''
        northwest = self.num2deg(self.x_tile, self.y_tile)
        southeast = self.num2deg(self.x_tile + 1, self.y_tile + 1)
        return (southeast.latitude, northwest.longitude,
                northwest.latitude, southeast.longitude)

    def path(self):
        '''
        Path.

        :returns: Local path for map tile
        :rtype: str
        '''
        return "%d/%d/%d.png" % (self._zoom, self.x_tile, self.y_tile)

    def bad_path(self):
        '''
        Path for caching tiles that are are not available for download.

        :returns: Local bad path for unavailable tiles
        :rtype: str
        '''
        return "%d/%d/%d.bad" % (self._zoom, self.x_tile, self.y_tile)

    def _local_path(self):
        if not self._base_dir:
            return None
        path = os.path.join(self._base_dir, self.path())
        if not os.path.isdir(os.path.dirname(path)):
            try:
                os.makedirs(os.path.dirname(path))
            except FileExistsError:
                pass
        return path

    def _local_bad_path(self):
        if not self._base_dir:
            return None
        path = os.path.join(self._base_dir, self.bad_path())
        if not os.path.isdir(os.path.dirname(path)):
            try:
                os.makedirs(os.path.dirname(path))
            except FileExistsError:
                pass
        return path

    def get_local_tile_path(self):
        '''
        Get the local tile path if it exists.

        :returns: Local file path or None
        :rtype str:
        '''
        local_cache = self._local_path()
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
        local = os.path.exists(local_cache)
        if not local:
            local_cache = self._local_bad_path()
            local = os.path.exists(local_cache)

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
        for tile_num in range(10):
            url = self.remote_path()
            try:
                self.fetch_url(url, self._local_path())
                self.logger.debug("fetch: opened %s", url)
                if self._map_widget:
                    self._map_widget.queue_draw()
                return True
            except MapTileNotFound:
                self.logger.info("fetch: created %s",
                                 self._local_bad_path())
                with open(self._local_bad_path(), 'w'):
                    pass
                self.logger.info("fetch: [%i] Not found `%s'",
                                 tile_num, url)
            except MapFetchUrlException:
                self.logger.info("fetch: [%i] Failed to fetch `%s'",
                                 tile_num, url, exc_info=True)
            return False

    def fetch_url(self, url, local):
        '''
        Fetch Url.

        :param local: Local file name to store contents
        :raises: MapNotConnected(MapFetchUrlException) if not connected
        :raises: MapTileNotFound(MapFetchUrlException) if tile is not available
        :raises: MapFetchError(MapFetchUrlException) Any other error
        '''
        # for setup of d-rats user_agent
        from .. import version

        if not self._connected:
            raise MapNotConnected("Not connected")

        if self._proxy:
            # proxies = {"http" : PROXY}
            authinfo = urllib.request.HTTPBasicAuthHandler()
            proxy_support = urllib.request.ProxyHandler({"http" : self._proxy})
            ftp_handler = urllib.request.CacheFTPHandler
            opener = urllib.request.build_opener(proxy_support, authinfo,
                                                 ftp_handler)
            urllib.request.install_opener(opener)
        req = urllib.request.Request(url, None,
                                     version.HTTP_CLIENT_HEADERS)

        try:
            data = urllib.request.urlopen(req)
        except urllib.error.HTTPError as err:
            if err.code == 404:
                raise MapTileNotFound("404 error code")
            self.logger.info("HTTP error while retrieving tile", exc_info=True)
            raise MapFetchError(err)

        read_data = data.read()
        local_file = open(local, "wb")
        local_file.write(read_data)
        data.close()
        local_file.close()
        return True

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
        :type callback: function
        :param args: Optional arguments
        '''
        new_args = (callback,) + args
        tfetch = threading.Thread(target=self._thread, args=new_args)
        tfetch.setDaemon(True)
        tfetch.start()

    def local_path(self):
        '''
        Local Path.

        :returns: Local path
        :rtype: str
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
        remote_path = self._map_url + (self.path())
        if self._map_url_key:
            remote_path += self._map_url_key
        return remote_path

    def __add__(self, count):
        (x_axis, y_axis) = count
        x_new = self.x_tile + x_axis
        y_new = self.y_tile + y_axis
        # This can result in wrapping around the map borders
        # need to correct it back to the existing borders.
        map_max = (2 ** self._zoom)
        while x_new < 0:
            x_new += map_max
        while x_new > map_max:
            x_new -= map_max
        while y_new < 0:
            y_new += map_max
        while y_new > map_max:
            y_new -= map_max
        tile = MapTile(x_axis=x_new,
                       y_axis=y_new)
        return tile

    def __sub__(self, tile):
        return (self.x_tile - tile.x_tile, self.y_tile - tile.y_tile)

    def __contains__(self, pos):
        (lat_min, lon_min, lat_max, lon_max) = self.tile_edges()
        # latitude is from -90 to + 90 and longitude is from -180 to 180
        # For checking contains we need to normalize them by adding an offset
        lat_match = (lat_min + 90) < (pos.latitude + 90) < (lat_max + 90)
        lon_match = (lon_min + 180) < (pos.longitude + 180) < (lon_max + 180)

        return lat_match and lon_match
