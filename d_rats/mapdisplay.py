#!/usr/bin/python
'''Map Display'''
# pylint: disable=too-many-lines
#
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

import logging
import os
# import sys
import math
import time
# import random
import shutil
import tempfile
import threading
# import copy
# from math import *

import six.moves.urllib.request # type: ignore
import six.moves.urllib.parse # type: ignore
import six.moves.urllib.error # type: ignore
from six.moves import range # type: ignore
# from six.moves.urllib.error import URLError, HTTPError

import cairo
import gi
gi.require_version("Gtk", "3.0")
# gi.require_version("cairo", "1.0")
gi.require_foreign("cairo")
# from gi.repository import cairo
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GObject
from gi.repository import GLib
gi.require_version("PangoCairo", "1.0")
from gi.repository import PangoCairo

if not '_' in locals():
    import gettext
    _ = gettext.gettext

# py3 from . import mainapp

from . import dplatform
from . import miscwidgets
from . import inputdialog
from . import utils
# from . import geocode_ui
from . import map_sources
from . import map_source_editor
from . import signals
# from . import debug

##############
from .ui.main_common import ask_for_confirmation
from .gps import GPSPosition, distance, value_with_units, DPRS_TO_APRS

_ = gettext.gettext

CROSSHAIR = "+"

COLORS = ["red", "green", "cornflower blue", "pink", "orange", "grey"]

#set the map location
BASE_DIR = None
MAP_TYPE = None
MAP_URL = None
MAP_URL_KEY = None


class MapDisplayException(Exception):
    '''Generic MapDisplay Exception.'''


class MapFetchUrlException(MapDisplayException):
    '''Map Fetch Url Exception'''


class MapNotConnected(MapFetchUrlException):
    '''Not connected Error.'''


class MapTileNotFound(MapFetchUrlException):
    '''Map Tile Not Found.'''


class MapFetchError(MapFetchUrlException):
    '''Map Unexpected Fetch Error.'''


# pylint: disable=invalid-name
module_logger = logging.getLogger("MapDisplay")


def set_base_dir(basedir, mapurl, mapkey):
    '''
    Set Base Directory.

    :param basedir: Base directory
    :param mapurl: URL of Map
    :param mapkey: Map access key
    '''
    # pylint: disable=global-statement
    global BASE_DIR
    BASE_DIR = basedir
    module_logger.info("BASE_DIR configured to %s: ", BASE_DIR)

    # setup of the url where go to retrieve tiles
    # pylint: disable=global-statement
    global MAP_URL
    MAP_URL = mapurl
    module_logger.info("MAP_URL configured to: %s", MAP_URL)

    # setup of the key to append to the url to retrieve tiles
    # pylint: disable=global-statement
    global MAP_URL_KEY
    MAP_URL_KEY = mapkey
    module_logger.info("MAP_URL_KEY configured to: %s ", MAP_URL_KEY)


CONFIG = None

CONNECTED = True
MAX_TILE_LIFE = 0
PROXY = None


def set_connected(connected):
    '''
    Set Connected.

    :param connected: Set connected state
    '''
    # pylint: disable=global-statement
    global CONNECTED
    CONNECTED = connected


def set_tile_lifetime(lifetime):
    '''
    Set tile Lifetime.

    :param lifetime: Cache lifetime (in Units?)
    '''
    # pylint: disable=global-statement
    global MAX_TILE_LIFE
    MAX_TILE_LIFE = lifetime


def set_proxy(proxy):
    '''
    Set Proxy.

    :param: proxy to set
    '''
    # pylint: disable=global-statement
    global PROXY
    PROXY = proxy


def fetch_url(url, local):
    '''
    Fetch Url.

    :param local: Local file name to store contents
    :raises: MapNotConnected(MapFetchUrlException) if not connected
    :raises: MapTileNotFound(MapFetchUrlException) if tile is not available
    :raises: MapFetchError(MapFetchUrlException) Any other error
    '''
    # pylint: disable=global-statement
    global CONNECTED
    # pylint: disable=global-statement
    global PROXY

    #setup of d-rats user_agent
    from . import version

    if not CONNECTED:
        raise MapNotConnected("Not connected")

    if PROXY:
        # proxies = {"http" : PROXY}
        # This is because of "six" imports
        # pylint: disable=undefined-variable
        authinfo = urllib.request.HTTPBasicAuthHandler() # type: ignore
        proxy_support = six.moves.urllib.request.ProxyHandler({"http" : PROXY})
        # pylint: disable=undefined-variable
        ftp_handler = urllib.request.CacheFTPHandler # type: ignore
        opener = six.moves.urllib.request.build_opener(proxy_support, authinfo,
                                                       ftp_handler)
        six.moves.urllib.request.install_opener(opener)
    # else:
    #    proxies = None
    # data = six.moves.urllib.request.urlopen(url, proxies=proxies)
    req = six.moves.urllib.request.Request(url, None,
                                           version.HTTP_CLIENT_HEADERS)

    # The broad-except is something that needs to be looked at in the future.
    # pylint: disable=broad-except
    try:
        data = six.moves.urllib.request.urlopen(req)
    # The undefined variable is because of "six" imports
    # pylance also reports undefined variables

    # pylint: disable=broad-except
    except six.moves.urllib.error.HTTPError as err:
        if err.code == 404:
            raise MapTileNotFound("404 error code")
        module_logger.info("HTTP error while retrieving tile: "
                           "code: %s, reason: %s - %s [%s]",
                           err.code,
                           err.reason,
                           str(err), url)
        raise MapFetchError(err)
    # pylint: disable=undefined-variable
    except Exception as err:
        module_logger.info("Mapdisplay fetch_url "
                           "Error while retrieving info", exc_info=True)
        raise MapFetchError(err)

    read_data = data.read()
    local_file = open(local, "wb")
    local_file.write(read_data)
    data.close()
    local_file.close()
    return True


class MarkerEditDialog(inputdialog.FieldDialog):
    '''Marker Edit Dialog.'''

    def __init__(self):
        self.logger = logging.getLogger("MarkerEditDialog")
        inputdialog.FieldDialog.__init__(self, title=_("Add Marker"))
        self.logger = logging.getLogger("Initializing")

        self.icons = []
        for sym in sorted(DPRS_TO_APRS.values()):
            icon = utils.get_icon(sym)
            if icon:
                self.icons.append((icon, sym))

        self.add_field(_("Group"), miscwidgets.make_choice([], True))
        self.add_field(_("Name"), Gtk.Entry())
        self.add_field(_("Latitude"), miscwidgets.LatLonEntry())
        self.add_field(_("Longitude"), miscwidgets.LatLonEntry())
        self.add_field(_("Lookup"), Gtk.Button.new_with_label(_("By Address")))
        self.add_field(_("Comment"), Gtk.Entry())
        self.add_field(_("Icon"), miscwidgets.make_pixbuf_choice(self.icons))

        self._point = None

    def set_groups(self, groups, group=None):
        '''
        Set Groups.

        :param groups: Groups to retrieve
        :param group: Optional group text to set
        '''
        grpsel = self.get_field(_("Group"))
        for grp in groups:
            grpsel.append_text(grp)

        if group is not None:
            grpsel.child.set_text(group)
            grpsel.set_sensitive(False)
        else:
            grpsel.child.set_text(_("Misc"))

    # pylint: disable=arguments-differ
    def get_group(self):
        '''
        Get Group

        :returns: Group for marker
        '''
        return self.get_field(_("Group")).child.get_text()

    def set_point(self, point):
        '''
        Set Point.

        :param point: point object
        '''
        self.get_field(_("Name")).set_text(point.get_name())
        self.get_field(_("Latitude")).set_text("%.4f" % point.get_latitude())
        self.get_field(_("Longitude")).set_text("%.4f" % point.get_longitude())
        self.get_field(_("Comment")).set_text(point.get_comment())

        iconsel = self.get_field(_("Icon"))
        if isinstance(point, map_sources.MapStation):
            symlist = [y for x, y in self.icons]
            try:
                iidx = symlist.index(point.get_aprs_symbol())
                iconsel.set_active(iidx)
            except ValueError:
                self.logger.info("No such symbol `%s'", point.get_aprs_symbol())
        else:
            iconsel.set_sensitive(False)

        self._point = point

    def get_point(self):
        '''
        Get Point.

        :returns: point object
        '''
        name = self.get_field(_("Name")).get_text()
        lat = self.get_field(_("Latitude")).value()
        lon = self.get_field(_("Longitude")).value()
        comment = self.get_field(_("Comment")).get_text()
        idx = self.get_field(_("Icon")).get_active()

        self._point.set_name(name)
        self._point.set_latitude(lat)
        self._point.set_longitude(lon)
        self._point.set_comment(comment)

        if isinstance(self._point, map_sources.MapStation):
            self._point.set_icon_from_aprs_sym(self.icons[idx][1])

        return self._point


# These functions taken from:
#   http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames
def deg2num(lat_deg, lon_deg, zoom):
    '''
    Degrees to number.

    :param lat_deg: Latitude in degrees
    :param lon_deg: Longitude in degrees
    :param zoom: Zoom factor
    :returns: Tuple of (x_pos, y_pos) for coordinates
    '''
    # lat_rad = lat_deg * math.pi / 180.0
    lat_rad = math.radians(lat_deg)
    num = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * num)
    ytile = int((1.0 - math.log(math.tan(lat_rad) +
                                (1 / math.cos(lat_rad))) /
                 math.pi) / 2.0 * num)
    return(xtile, ytile)


def num2deg(xtile, ytile, zoom):
    '''
    Number to Degrees.

    :param xtile: X axis position of tile
    :param ytile: Y axis position of tile
    :param zoom: Zoom factor
    :returns: Tuple of (latitude, longitude) in degrees
    '''
    num = 2.0 ** zoom
    lon_deg = xtile / num * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / num)))
    lat_deg = math.degrees(lat_rad)
    return (lat_deg, lon_deg)


class MapTile():
    '''
    Downloads the map tiles.

    :param lat: Latitude
    :param lon: Longitude
    :param zoom: Zoom factor
    '''

    def path_els(self):
        '''
        Path ELS.

        :returns: Latitude and longitude in degrees
        '''
        return deg2num(self.lat, self.lon, self.zoom)

    def tile_edges(self):
        '''
        Tile Edges.

        :returns: Axes of the tile edges
        '''
        north, west = num2deg(self.x_axis, self.y_axis, self.zoom)
        south, east = num2deg(self.x_axis + 1, self.y_axis + 1, self.zoom)
        return (south, west, north, east)

    def lat_range(self):
        '''
        Latitude Range.

        :returns: Tuple of latitude range of tile
        '''
        south, _w, north, _e = self.tile_edges()
        return (north, south)

    def lon_range(self):
        '''
        Longitude Range.

        :returns: Tuple of longitude range of tile
        '''
        _s, west, _n, east = self.tile_edges()
        return (west, east)

    def path(self):
        '''
        Path.

        :returns: Local path for map tile
        '''
        return "%d/%d/%d.png" % (self.zoom, self.x_axis, self.y_axis)

    def bad_path(self):
        '''
        Path for caching tiles that are are not available for download.

        :returns: Local bad path unavailable tiles
        '''
        return "%d/%d/%d.bad" % (self.zoom, self.x_axis, self.y_axis)

    def _local_path(self):
        path = os.path.join(self.dir, self.path())
        if not os.path.isdir(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        return path

    def _local_bad_path(self):
        path = os.path.join(self.dir, self.bad_path())
        if not os.path.isdir(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        return path

    def get_local_tile_path(self):
        '''
        Get the local tile path if it exists.

        :returns: Local file path or None
        '''
        local_cache = self.local_path()
        if os.path.exists(self._local_path()):
            return local_cache
        return None

    def is_local(self):
        '''
        Is local?

        :returns: True if locally cached and cache is not expired
        '''
        local_cache = self._local_path()
        local = os.path.exists(self._local_path())
        if not local:
            local_cache = self._local_bad_path()
            local = os.path.exists(self._local_bad_path())

        if not local:
            return False
        if MAX_TILE_LIFE == 0 or not CONNECTED:
            return local

        time_stamp = os.stat(local_cache).st_mtime
        return (time.time() - time_stamp) < MAX_TILE_LIFE

    def fetch(self):
        '''
        Fetch a tile.

        :returns: True if fetch is successfull or tile is cached.
        '''
        #verify if tile is local, if not fetches from web
        if not self.is_local():
            for tile_num in range(10):
                url = self.remote_path()
                try:
                    fetch_url(url, self._local_path())
                    self.logger.info("opened %s", url)
                    return True
                except MapTileNotFound:
                    self.logger.info("created %s",
                                     self._local_bad_path())
                    with open(self._local_bad_path(), 'w'):
                        pass
                    self.logger.info("fetch: [%i] Not found `%s'",
                                     tile_num, url, exc_info=True)
                except MapFetchUrlException:
                    self.logger.info("fetch: [%i] Failed to fetch `%s'",
                                     tile_num, url, exc_info=True)

            return False
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
        '''
        return MAP_URL + (self.path()) + MAP_URL_KEY

    def __add__(self, count):
        (x_axis, y_axis) = count
        return MapTile(self.x_axis + x_axis, self.y_axis + y_axis, self.zoom)

    def __sub__(self, tile):
        return (self.x_axis - tile.x_axis, self.y_axis - tile.y_axis)

    def __contains__(self, point):
        (lat, lon) = point

        # pylint: disable=fixme
        # FIXME for non-western!
        (lat_max, lat_min) = self.lat_range()
        (lon_min, lon_max) = self.lon_range()

        lat_match = (lat < lat_max and lat > lat_min)
        lon_match = (lon < lon_max and lon > lon_min)

        return lat_match and lon_match

    def __init__(self, lat, lon, zoom):

        self.logger = logging.getLogger("MapTile")
        self.zoom = zoom
        if isinstance(lat, int) and isinstance(lon, int):
            self.x_axis = lat
            self.y_axis = lon
            self.lat, self.lon = num2deg(self.x_axis, self.y_axis, self.zoom)
        else:
            self.lat = lat
            self.lon = lon
            self.x_axis, self.y_axis = deg2num(self.lat, self.lon, self.zoom)

        self.dir = BASE_DIR

        # create the local dir to store tiles if doesn't exist
        if not os.path.isdir(self.dir):
            os.mkdir(self.dir)

    def __str__(self):
        return "%.4f,%.4f (%i,%i)" % \
            (self.lat, self.lon, self.x_axis, self.y_axis)


# pylint: disable=too-few-public-methods
class LoadContext():
    '''
    Tile Context

    :param loaded_tiles: Tile that are loaded
    :param total_tiles: Total tiles
    :param zoom: Zoom setting
    '''

    def __init__(self, loaded_tiles, total_tiles, zoom):
        self.loaded_tiles = loaded_tiles
        self.total_tiles = total_tiles
        self.zoom = zoom


# pylint: disable=too-many-instance-attributes
class MapWidget(Gtk.DrawingArea):
    '''
    MapWidget

    :param window: Parent window
    :param width: Width of widget
    :param height: Height of widget
    :param tilesize: Size of tiles, default 256
    :param status: Optional status
    '''

    __gsignals__ = {
        "redraw-markers" : (GObject.SignalFlags.RUN_LAST,
                            GObject.TYPE_NONE,
                            ()),
        "new-tiles-loaded" : (GObject.SignalFlags.ACTION,
                              GObject.TYPE_NONE,
                              ()),
        }

    def draw_text_marker_at(self, x_axis, y_axis, text, color="yellow"):
        '''
        Draw Text Marker at.

        :param x_axis: X Axis
        :param y_axis: Y Axis
        :param text: Text for marker
        :param color: Color for marker, default is "yellow"
        '''
        # originally commented out.
        self.logger.info("draw_text_marker_at %s at x=%s y=%s",
                         text, x_axis, y_axis)

        # pylint: disable=invalid-name
        gc = self.get_style().black_gc

        # setting the size for the text marker
        if self.zoom < 12:
            size = 'size="x-small"'
        elif self.zoom < 14:
            size = 'size="small"'
        else:
            size = ''
        text = utils.filter_to_ascii(text)

        pango_layout = self.create_pango_layout("")
        markup = '<span %s background="%s">%s</span>' % (size, color, text)
        pango_layout.set_markup(markup)

        self.window.draw_layout(gc, int(x_axis), int(y_axis), pango_layout)

    def draw_image_at(self, x_axis, y_axis, pixbuf):
        '''
        Draw Image At.

        :param x_axis: X Axis
        :param y_axis: Y Axis
        :param pixbuf: Pixbuf to draw
        :returns: Height of pixbuf
        '''
        # originally commented out
        self.logger.info("draw_image_at x=%s y=%s", x_axis, y_axis)
        # pylint: disable=invalid-name
        gc = self.get_style().black_gc

        self.window.draw_pixbuf(gc,
                                pixbuf,
                                0, 0,
                                int(x_axis), int(y_axis))

        return pixbuf.get_height()

    def draw_cross_marker_at(self, x_axis, y_axis):
        '''
        Draw cross marker.

        :param x_axis: X axis
        :param y_axis: Y axis
        '''
        # self.logger.info("draw_cross_marker_at x=%s y=%s", x_axis, y_axis)
        width = 2
        # color_map = self.window.get_colormap()
        # color = color_map.alloc_color("red")
        color = Gdk.RGBA()
        color.parse('red')
        # pylint: disable=invalid-name
        gc = self.window.new_gc(foreground=color,
                                line_width=width)

        x_axis = int(x_axis)
        y_axis = int(y_axis)

        self.window.draw_lines(gc, [(x_axis, y_axis - 5), (x_axis, y_axis + 5)])
        self.window.draw_lines(gc, [(x_axis - 5, y_axis), (x_axis + 5, y_axis)])

    def latlon2xy(self, lat, lon):
        '''
        Translate Latitude and Longitude to X and Y axes.

        :param lat: Latitude
        :param lon: Longitude
        :returns: Tuple of (x_axis, y_axis)'''
        y_axis = 1- ((lat - self.lat_min) / (self.lat_max - self.lat_min))
        x_axis = 1- ((lon - self.lon_min) / (self.lon_max - self.lon_min))

        x_axis *= (self.tilesize * self.width)
        y_axis *= (self.tilesize * self.height)

        y_axis += self.lat_fudge
        x_axis += self.lng_fudge
        return (x_axis, y_axis)

    def xy2latlon(self, x_axis, y_axis):
        '''
        Translate X, Y axes to latitude and longitude.

        :param x_axis: X Axis
        :param y_axis: Y Axis
        :returns: Tuple of (latitude, longitude)
        '''
        y_axis -= self.lat_fudge
        x_axis -= self.lng_fudge

        lon = 1 - (float(x_axis) / (self.tilesize * self.width))
        lat = 1 - (float(y_axis) / (self.tilesize * self.height))

        lat = (lat * (self.lat_max - self.lat_min)) + self.lat_min
        lon = (lon * (self.lon_max - self.lon_min)) + self.lon_min

        return lat, lon

    def draw_marker(self, label, lat, lon, img=None):
        '''
        Draw Marker.

        :param label: label for marker
        :param lat: Latitude for marker
        :param lon: Longitude for marker
        :param img: Option image
        '''
        # self.logger.info(" ----------------- %s, time.ctime())
        # self.logger.info("zoom     =%i", self.zoom)
        # self.logger.info("draw marker for %s at %s %s", label, lat, lon)
        # self.logger.info("fudge    =%i", self.lat_fudge)

        # this is the bg color of the stations markers on the map
        # (before it was red)
        color = "yellow"

        try:
            x_axis, y_axis = self.latlon2xy(lat, lon)

        except ZeroDivisionError:
            return

        if label == CROSSHAIR:
            self.draw_cross_marker_at(x_axis, y_axis)
        else:
            if img:
                y_axis += (4 + self.draw_image_at(x_axis, y_axis, img))
            self.draw_text_marker_at(x_axis, y_axis, label, color)

    def expose(self, _widget, cairo_ctx):
        '''
        Expose.

        :param _widget: MapWidget unused
        :param cairo_ctx: cairo.Context
        '''

        # print("expose type(widget) %s" % type(widget))
        # print("       type(cairo_ctx) %s" % type(cairo_ctx))
        # print("       cairo_ctx.get_target() = %s" %
        #       type(cairo_ctx.get_target()))
        if not self.map_tiles:
            self.load_tiles(cairo_ctx)

        # pylint: disable=invalid-name
        # gc = self.get_style().black_gc
        # self.window.draw_drawable(gc,
        #                          self.pixmap,
        #                          0, 0,
        #                          0, 0,
        #                          -1, -1)
        self.emit("redraw-markers")

    def calculate_bounds(self):
        '''Calculate Bounds.'''
        center = MapTile(self.lat, self.lon, self.zoom)

        # here we set the bounds for the map into the window
        # delta is the mid of the tiles used to draw the map
        # delta is necessary to keep alignment between the map
        # and the station labels
        delta = int(self.height/2)
        topleft = center + (-delta, -delta)
        botright = center + (delta, delta)
        (self.lat_min, _, _, self.lon_min) = botright.tile_edges()
        (_, self.lon_max, self.lat_max, _) = topleft.tile_edges()

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

        self.lng_fudge = 0
        self.lat_fudge = 0

        _south, west, north, _east = center.tile_edges() # type:ignore
        x_axis, y_axis = self.latlon2xy(north, west)
        self.lng_fudge = ((self.width / 2) * self.tilesize) - x_axis
        self.lat_fudge = ((self.height / 2) * self.tilesize) - y_axis

    def broken_tile(self):
        '''
        Broken Tile

        :returns: pixbuf object
        '''
        if self.__broken_tile:
            return self.__broken_tile

        # print("broken_tile created")
        broken = [
            "48 16 3 1",
            "       c #FFFFFFFFFFFF",
            "x      c #FFFF00000000",
            "X      c #000000000000",
            "xx             xx   XX   X   XXX                ",
            " xx           xx    X X  X  X   X               ",
            "  xx         xx     X X  X X     X              ",
            "   xx       xx      X  X X X     X              ",
            "    xx     xx       X  X X X     X              ",
            "     xx   xx        X  X X  X   X               ",
            "      xx xx         X   XX   XXX                ",
            "       xxx                                      ",
            "       xxx                                      ",
            "      xx xx         XXXX     XX   XXXXX   XX    ",
            "     xx   xx        X   X   X  X    X    X  X   ",
            "    xx     xx       X    X X    X   X   X    X  ",
            "   xx       xx      X    X X    X   X   X    X  ",
            "  xx         xx     X    X XXXXXX   X   XXXXXX  ",
            " xx           xx    X   X  X    X   X   X    X  ",
            "xx             xx   XXXX   X    X   X   X    X  "
            ]

        # return GdkPixbuf_new_from_xpm_data(broken)
        # pixmap = Gdk.pixmap_create_from_xpm_d(self.window, None, broken)[0]
        # pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB,
        #                              False,
        #                              8,
        #                              self.tilesize, self.tilesize,
        #                              None, None)
        pixbuf = GdkPixbuf.Pixbuf.new_from_xpm_data(broken)
        pixbuf.fill(0xffffffff)

        # x_axis = y_axis = (self.tilesize / 2)

        # pixbuf.get_from_drawable(pixmap, pixmap.get_colormap(),
        #                         0, 0, x_axis, y_axis, -1, -1)

        # pylint: disable=no-member
        surface = cairo.ImageSurface(cairo.Format.ARGB32(),
                                     pixbuf.get_width(),
                                     pixbuf.get_height())
        # pylint: disable=no-member
        cairo_ctx1 = cairo.Context(surface)
        cairo_ctx2 = Gdk.CairoContext(cairo_ctx1)
        cairo_ctx2.source_pixbuf(pixbuf, 0, 0)
        cairo_ctx2.paint()

        self.__broken_tile = surface

        return surface

    # pylint: disable=too-many-arguments
    def draw_tile(self, path, x_axis, y_axis, tile_ctx=None, cairo_ctx=None):
        '''
        Draw Tile.

        :param path: Path for tile
        :param x_axis: X Axis for tile
        :param y_axis: Y Axis for tile
        :param tile_ctx: LoadContext tile context, Default None
        :param cairo_ctx: cairo.Context object.
        '''
        if not cairo_ctx:
            # print('mapdisplay.MapWidget.draw_tile: ',
            #      "No cairo_ctx passed.")
            return

        if tile_ctx and tile_ctx.zoom != self.zoom:
            # Zoom level has changed, so don't do anything
            return

        # pixmap_gc = self.pixmap.new_gc()

        if path:
            # pylint: disable=broad-except
            try:
                # pylint: disable=no-member
                surface = cairo.ImageSurface.create_from_png(path)
                # print("# draw_tile surface from %s" % path)
                # pixbuf = Gdk.pixbuf_new_from_file(path)
            except cairo.Error as err:
                surface = self.broken_tile()
                # Debugging information
                if err != 'file not found':
                    self.logger.info("draw_tile: path %s error %s",
                                     path, err)

            except Exception as err:
                # print('mapdisplay.MapWidget.draw_tile : ',
                #      " %s (%s) %s" % (path, type(err), err))
                # this is the case  when some jpg tile file cannot be loaded -
                # typically this was due to html content saved as jpg
                # (due to an un trapped http error), or due to really corrupted
                # jpg (e.g. d-rats was closed before completing file save )

                # utils.log_exception()
                # removing broken tiles
                if os.path.exists(path):
                    self.logger.info("draw_tile: Deleting the broken tile"
                                     " to force future download %s", path)
                    os.remove(path)
                # else:
                #   usually this happens when a tile file has not been
                #   created after fetching from the tile as some error was got
                #   self.logger.info("Broken tile  not found"
                #                    " - skipping deletion of: %s", path)

                # print("# draw-tile: broken_tile by exception")
                surface = self.broken_tile()
        else:
            # print("# draw_tile broken tile - no path")
            surface = self.broken_tile()

        if tile_ctx:
            tile_ctx.loaded_tiles += 1
            frac = float(tile_ctx.loaded_tiles) / float(tile_ctx.total_tiles)
            if tile_ctx.loaded_tiles == tile_ctx.total_tiles:
                self.status(0.0, "")
            else:
                self.status(frac, _("Loaded") + " %.0f%%" % (frac * 100.0))

        # self.pixmap.draw_pixbuf(pixmap_gc, pixbuf,
        #                         0, 0, x_axis, y_axis, -1, -1)
        # print(type(surface))
        #print("# draw_tile",
        #      "Set source surface %s %s %s" % (surface, x_axis, y_axis))
        cairo_ctx.save()
        cairo_ctx.set_source_surface(surface, x_axis, y_axis)
        cairo_ctx.paint()
        cairo_ctx.restore()

        #print("# draw_tile",
        #      "type(self) %s, " % type(self),
        #      "type(cairo_ctx) %s, " % type(cairo_ctx))
        # self.queue_draw()

    @utils.run_gtk_locked
    def draw_tile_locked(self, *args):
        '''Draw Tile Locked.'''
        self.draw_tile(*args)

    def load_tiles(self, cairo_ctx=None):
        '''Load Tiles.'''
        self.map_tiles = []
        tile_ctx = LoadContext(0, (self.width * self.height), self.zoom)
        center = MapTile(self.lat, self.lon, self.zoom)

        delta_h = self.height / 2
        delta_w = self.width  / 2

        count = 0
        # total = self.width * self.height

        if not self.get_has_window():
            # Window is not loaded, thus can't load tiles
            # print("mapdisplay.MapWidget.load_tiles: ",
            #       "Window is not loaded!")
            return

        if not cairo_ctx:
            # print("mapdisplay.MapWidget.load_tiles: ",
            #       "No cairo context passed!")
            return

        # print('mapdisplay.MapWidget.load_tiles: ',
        #      "dir(cairo) = %s" % dir(cairo))
        # self.surface = cairo.ImageSurface(cairo.Format.ARGB32(),
        #                                  self.width * self.tilesize,
        #                                  self.height * self.tilesize)
        # print("mapdisplay.MapWidget.load_tiles: ",
        #      "type(self.window) = %s" % type(self.window))
        # self.surface = cairo_ctx.get_target()

        # try:
            # self.pixmap to be removed.
            # print("mapdisplay.MapWidget.load_tiles: ",
            #      "type(self.window) = %s" % type(self.window))
            # self.pixmap = Gdk.Pixmap(self.window,
            #                         self.width * self.tilesize,
            #                         self.height * self.tilesize)
            #
        # pylint: disable=broad-except
        # except Exception as err:
        #    # Window is not loaded, thus can't load tiles
        #    print('mapdisplay.MapWidget.load_tiles: ',
        #          " (%s) %s" % (type(err), err))
        #    return

        # pylint: disable=invalid-name, unused-variable
        # gc = self.pixmap.new_gc()  # gc unused?
        # print('mapdisplay.MapWidget.load_tiles: ',
        #      "type(gc) = %s" % type(gc))
        for i in range(0, self.width):
            for j in range(0, self.height):
                # print("#load-tiles %s , %s", (i, j))
                tile = center + (i - delta_w, j - delta_h)
                if not tile.is_local():
                    message = _("Retrieving")
                else:
                    message = _("Loading")

                tile_path = tile.get_local_tile_path()
                if tile_path:
                    self.draw_tile(tile_path,
                                   self.tilesize * i, self.tilesize * j,
                                   tile_ctx,
                                   cairo_ctx)
                else:
                    self.draw_tile(None, self.tilesize * i, self.tilesize * j)
                    tile.threaded_fetch(self.draw_tile_locked,
                                        self.tilesize * i,
                                        self.tilesize * j,
                                        tile_ctx,
                                        cairo_ctx)
                self.map_tiles.append(tile)
                count += 1

        # time.sleep(10)
        self.calculate_bounds()
        self.emit("new-tiles-loaded")

    def export_to(self, filename, bounds=None):
        '''
        Export To File in PNG format.

        :param filename: Filename to export to
        :param bounds: Optional bounds
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

        pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False,
                                      8, width, height, None, None)
        pixbuf.get_from_drawable(self.pixmap, self.pixmap.get_colormap(),
                                 x_axis, y_axis, 0, 0, width, height)
        pixbuf.save(filename, "png")

    # pylint: disable=too-many-arguments
    def __init__(self, window, width, height, tilesize=256, status=None):
        Gtk.DrawingArea.__init__(self)

        self.logger = logging.getLogger("MapWidget")
        self.__broken_tile = None
        self.pixmap = None  # Replaced by self.surface
        self.surface = None
        self.window = window

        self.height = height
        self.width = width

        # originally commented out
        self.logger.info("height %s, width %s", height, width)
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

        self.set_size_request(self.tilesize * self.width,
                              self.tilesize * self.height)
        self.connect("draw", self.expose)

    def set_center(self, lat, lon):
        '''
        Set Center.

        :param lat: Latitude for center
        :param lon: Longitude for center
        '''
        self.lat = lat
        self.lon = lon
        self.map_tiles = []
        # self.queue_draw()

    def get_center(self):
        '''
        Get Center.

        :returns: Tuple of latitude and longitude
        '''
        return (self.lat, self.lon)

    def set_zoom(self, zoom):
        '''
        Set Zoom.

        :param zoom: Zoom to set
        '''
        if zoom > 18 or zoom == 3:
            return

        self.zoom = zoom
        self.map_tiles = []
        # self.queue_draw()

    def get_zoom(self):
        '''
        Get Zoom.

        :returns: zoom value
        '''
        return self.zoom

    # pylint: disable=too-many-locals
    def scale(self, _widget, cairo_ctx, x_axis, y_axis, pixels=128): # type:ignore
        '''
        Scale.

        :param widget: ScrolledWindow for Map, Unused
        :param cairo_ctx: Cairo Context
        :param x_axis: X axis
        :param y_axis: Y axis
        :param pixels: Optional pixels, default=128
        '''
        # draw the scale-ladder on the map
        shift = 15
        tick = 5

        # rect = Gdk.Rectangle(x-pixels,y-shift-tick,x,y)
        # self.window.invalidate_rect(rect, True)

        (lat_a, lon_a) = self.xy2latlon(self.tilesize, self.tilesize)
        (lat_b, lon_b) = self.xy2latlon(self.tilesize * 2, self.tilesize)

        # calculate width of one tile to show below the ladder scale
        d_width = distance(lat_a, lon_a, lat_b, lon_b) * \
            (float(pixels) / self.tilesize)

        dist = value_with_units(d_width)

        # color = self.window.get_colormap().alloc_color("black")
        color = Gdk.RGBA()
        color.parse('black')
        # pylint: disable=invalid-name
        # gc = self.window.new_gc(line_width=1, foreground=color)
        cairo_ctx.save()
        cairo_ctx.set_source_rgba(color.red,
                                  color.green,
                                  color.blue,
                                  color.alpha)

        # self.window.draw_line(gc, x_axis - pixels,
        #                      y_axis - shift, x_axis, y_axis - shift)
        cairo_ctx.move_to(x_axis - pixels, y_axis - shift)
        cairo_ctx.line_to(x_axis, y_axis - shift)
        # self.window.draw_line(gc, x_axis - pixels, y_axis - shift,
        #                      x_axis - pixels, y_axis - shift - tick)
        cairo_ctx.move_to(x_axis - pixels, y_axis - shift)
        cairo_ctx.line_to(x_axis - pixels, y_axis - shift - tick)
        # self.window.draw_line(gc, x_axis, y_axis - shift,
        #                      x_axis, y_axis - shift - tick)
        cairo_ctx.move_to(x_axis, y_axis - shift)
        cairo_ctx.line_to(x_axis, y_axis - shift - tick)
        # self.window.draw_line(gc, x_axis - (pixels/2), y_axis - shift,
        #                      x_axis - (pixels/2), y_axis - shift - tick)
        cairo_ctx.move_to(x_axis - (pixels/2), y_axis - shift)
        cairo_ctx.line_to(x_axis - (pixels/2), y_axis - shift - tick)

        pango_layout = self.create_pango_layout("")
        pango_layout.set_markup("%s" % dist)
        # self.window.draw_layout(gc, x_axis - pixels, y_axis - shift,
        #                         pango_layout)
        #pango_ctx = widget.get_pango_context()
        #pango_ctx2 = self.get_pango_context()
        PangoCairo.show_layout(cairo_ctx, pango_layout)
        cairo_ctx.paint()
        cairo_ctx.restore()

    def point_is_visible(self, lat, lon):
        '''
        Point is Visible.

        :returns: True if visible
        '''
        for i in self.map_tiles:
            if (lat, lon) in i:
                return True

        return False


# pylint: disable=too-many-public-methods
class MapWindow(Gtk.Window):
    '''
    Map Window

    :param config: Config object
    :param args: Optional arguments
    '''

    __gsignals__ = {
        "reload-sources" : (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE, ()),
        "user-send-chat" : signals.USER_SEND_CHAT,
        "get-station-list" : signals.GET_STATION_LIST,
        }

    _signals = {"user-send-chat" : None,
                "get-station-list" : None,
                }

    def zoom(self, adj, frame):
        '''
        Zoom.

        :param adj: Gtk.Adjustment object
        :param frame: Frame for zoom
        '''

        self.map.set_zoom(int(adj.get_value()))
        frame.set_label(_("Zoom") + " (%i)" % int(adj.get_value()))

    def make_zoom_controls(self):
        '''
        Make zoom controlls

        :returns; Frame object
        '''
        box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 3)
        box.set_border_width(3)
        box.show()

        label = Gtk.Label.new(_("Min"))
        label.show()
        box.pack_start(label, 0, 0, 0)
        def_zoom = 14
        # mm here the allowed zoom levels are from 2 to 17 (increased to 18)
        adj = Gtk.Adjustment.new(value=def_zoom,
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

        zoom_label = _("Zoom") + " (%i)" % def_zoom
        frame = Gtk.Frame.new(zoom_label)
        frame.set_label_align(0.5, 0.5)
        frame.set_size_request(150, 50)
        frame.show()
        frame.add(box)

        scroll_bar.connect("value-changed", self.zoom, frame)

        return frame

    def toggle_show(self, group, *vals):
        '''
        Toggle Show.

        :param group: Group to show
        :param vals: Optional values
        '''
        if group:
            station = vals[1]
        else:
            group = vals[1]
            station = None

        for src in self.map_sources:
            if group != src.get_name():
                continue

            if station:
                try:
                    point = src.get_point_by_name(station)
                except KeyError:
                    continue

                point.set_visible(vals[0])
                self.add_point_visible(point)
            else:
                src.set_visible(vals[0])
                for point in src.get_points():
                    point.set_visible(vals[0])
                    self.update_point(src, point)

            src.save()
            break

        # self.map.queue_draw()

    # pylint: disable=too-many-branches
    def marker_mh(self, action, ident, group):
        '''
        Marker Menu Handler.

        :param action: Gtk.Action
        :param ident: Identification
        :param group: Group for menu
        '''
        menu_action = action.get_name()

        if menu_action == "delete":
            self.logger.info("Deleting %s/%s", group, ident)
            for source in self.map_sources:
                if source.get_name() == group:
                    if not source.get_mutable():
                        return

                    point = source.get_point_by_name(ident)
                    source.del_point(point)
                    source.save()
        elif menu_action == "edit":
            source = None
            for source in self.map_sources:
                if source.get_name() == group:
                    break

            if not source:
                return

            if not source.get_mutable():
                return

            point = None
            for point in source.get_points():
                if point.get_name() == ident:
                    break

            if not point:
                return

            _point = point.dup()
            upoint, _foo = self.prompt_to_set_marker(point, source.get_name())
            if upoint:
                self.del_point(source, _point)
                self.add_point(source, upoint)
                source.save()

    def _make_marker_menu(self, store, iter_value):
        menu_xml = """
<ui>
  <popup name="menu">
    <menuitem action="edit"/>
    <menuitem action="delete"/>
    <menuitem action="center"/>
  </popup>
</ui>
"""
        # Deprecated!  Look at using Gio.SimpleAction related methods
        # and those are being phased out and will not be in gtk4.
        # so this will need a bit of a re-write
        action_group = Gtk.ActionGroup.new("menu")

        try:
            ident, = store.get(iter_value, 1)
            group, = store.get(store.iter_parent(iter_value), 1)
        except TypeError:
            ident = group = None

        edit = Gtk.Action.new("edit", _("Edit"), None, None)
        edit.connect("activate", self.marker_mh, ident, group)
        if not ident:
            edit.set_sensitive(False)
        action_group.add_action(edit)

        delete = Gtk.Action.new("delete", _("Delete"), None, None)
        delete.connect("activate", self.marker_mh, ident, group)
        action_group.add_action(delete)

        center = Gtk.Action.new("center", _("Center on this"), None, None)
        center.connect("activate", self.marker_mh, ident, group)
        # This isn't implemented right now, because I'm lazy
        center.set_sensitive(False)
        action_group.add_action(center)

        uim = Gtk.UIManager()
        uim.insert_action_group(action_group, 0)
        uim.add_ui_from_string(menu_xml)

        return uim.get_widget("/menu")

    def make_marker_popup(self, _widget, view, event):
        '''
        Make Marker Popup.

        :param _widget: Unused
        :param view: View for popup
        :param event: Gdk.Event for popup
        '''
        if event.button != 3:
            return

        if event.window == view.get_bin_window():
            x_axis, y_axis = event.get_coords()
            pathinfo = view.get_path_at_pos(int(x_axis), int(y_axis))
            if pathinfo is None:
                return
            view.set_cursor_on_cell(pathinfo[0], None, None, False)

        (store, iter_value) = view.get_selection().get_selected()

        menu = self._make_marker_menu(store, iter_value)
        if menu:
            menu.popup(None, None, None, None, event.button, event.time)

    def make_marker_list(self):
        '''
        Make Marker List.

        :returns: Scroll Window object
        '''
        cols = [(GObject.TYPE_BOOLEAN, _("Show")),
                (GObject.TYPE_STRING, _("Station")),
                (GObject.TYPE_FLOAT, _("Latitude")),
                (GObject.TYPE_FLOAT, _("Longitude")),
                (GObject.TYPE_FLOAT, _("Distance")),
                (GObject.TYPE_FLOAT, _("Direction")),
                ]
        self.marker_list = miscwidgets.TreeWidget(cols, 1, parent=False)
        self.marker_list.toggle_cb.append(self.toggle_show)
        self.marker_list.connect("click-on-list", self.make_marker_popup)

        # pylint: disable=protected-access
        self.marker_list._view.connect("row-activated", self.recenter_cb)

        def render_station(_col, rend, model, iter_value, _data):
            parent = model.iter_parent(iter_value)
            if not parent:
                parent = iter_value
            group = model.get_value(parent, 1)
            if group in self.colors:
                rend.set_property("foreground", self.colors[group])

        column = self.marker_list._view.get_column(1)
        column.set_expand(True)
        column.set_min_width(150)
        # r = c.get_cell_renderers()[0]
        renderer_text = Gtk.CellRendererText()
        column.set_cell_data_func(renderer_text, render_station)

        def render_coord(_col, rend, model, iter_value, cnum):
            if isinstance(rend, gi.repository.Gtk.Separator):
                return
            if model.iter_parent(iter_value):
                rend.set_property('text', "%.4f" %
                                  model.get_value(iter_value, cnum))
            else:
                rend.set_property('text', '')

        for col in [2, 3]:
            column = self.marker_list._view.get_column(col)
            # renderer_text = column.get_cell_renderers()[0]
            renderer_text = Gtk.CellRendererText()
            column.set_cell_data_func(renderer_text, render_coord, col)

        def render_dist(_col, rend, model, iter_value, cnum):
            if model.iter_parent(iter_value):
                rend.set_property('text', "%.2f" %
                                  model.get_value(iter_value, cnum))
            else:
                rend.set_property('text', '')

        for col in [4, 5]:
            column = self.marker_list._view.get_column(col)
            # renderer_text = column.get_cell_renderers()[0]
            renderer_text = Gtk.CellRendererText()
            column.set_cell_data_func(renderer_text, render_dist, col)

        scrollw = Gtk.ScrolledWindow()
        scrollw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrollw.add(self.marker_list.packable())
        scrollw.set_size_request(-1, 150)
        scrollw.show()

        return scrollw

    def refresh_marker_list(self, group=None):
        '''
        Refresh Marker List.

        :param group: Optional group
        '''
        (lat, lon) = self.map.get_center()
        center = GPSPosition(lat=lat, lon=lon)

        for item in self.marker_list.get_values(group):
            try:
                _parent, children = item
            except ValueError:
                # Empty group
                continue

            parent = _parent[1]
            for child in children:
                this = GPSPosition(lat=child[2], lon=child[3])
                dist = center.distance_from(this)
                bear = center.bearing_to(this)

                self.marker_list.set_item(parent,
                                          child[0],
                                          child[1],
                                          child[2],
                                          child[3],
                                          dist,
                                          bear)

    def make_track(self):
        '''
        Make Track

        :returns: Check button
        '''
        def toggle(check_button, map_window):
            map_window.tracking_enabled = check_button.get_active()

        check_button = Gtk.CheckButton.new_with_label(_("Track center"))
        check_button.connect("toggled", toggle, self)

        check_button.show()

        return check_button

    def clear_map_cache(self):
        '''Clear Map Cache.'''
        dialog = Gtk.MessageDialog(buttons=Gtk.ButtonsType.YES_NO)
        dialog.set_property("text",
                            _("Are you sure you want to delete all"
                              "your map files in \n %s\n?" % BASE_DIR))
        run_status = dialog.run()
        dialog.destroy()

        if run_status == Gtk.ResponseType.YES:
            #dir = os.path.join(dplatform.get_platform().config_dir(), "maps")
            base_dir = BASE_DIR
            shutil.rmtree(base_dir, True)
            # self.map.queue_draw()

    def printable_map(self, bounds=None):
        '''
        Printable Map.

        :param bounds: Optional bounds
        '''
        platform = dplatform.get_platform()

        file_handle = tempfile.NamedTemporaryFile()
        fname = file_handle.name
        file_handle.close()

        map_file = "%s.png" % fname
        html_file = "%s.html" % fname

        time_stamp = time.strftime("%H:%M:%S %d-%b-%Y")

        station_map = _("Station map")
        generated_at = _("Generated at")

        html = """
<html>
<body>
<h2>D-RATS %s</h2>
<h5>%s %s</h5>
<img src="file://%s"/>
</body>
</html>
""" % (station_map, generated_at, time_stamp, map_file)

        self.map.export_to(map_file, bounds)

        file_handle = open(html_file, "w")
        file_handle.write(html)
        file_handle.close()

        platform.open_html_file(html_file)

    def save_map(self, bounds=None):
        '''
        Save Map.

        :param bounds: Optional bounds to save
        '''
        platform = dplatform.get_platform()
        fname = platform.gui_save_file(default_name="map_%s.png" % \
                                       time.strftime("%m%d%Y%_H%M%S"))
        if not fname:
            return

        if not fname.endswith(".png"):
            fname += ".png"
        self.map.export_to(fname, bounds)

    def get_visible_bounds(self):
        '''
        Get Visible Bounds.

        :returns: tuple with bounds
        '''
        hadj = self.scrollw.get_hadjustment()
        vadj = self.scrollw.get_vadjustment()

        return (int(hadj.value), int(vadj.value),
                int(hadj.value + hadj.page_size),
                int(vadj.value + vadj.page_size))

    # pylint: disable=invalid-name
    def mh(self, action):
        '''
        Menu Handler.

        :param _action: Action object
        '''
        menu_action = action.get_name()

        if menu_action == "refresh":
            self.map_tiles = []
            # self.map.queue_draw()
        elif menu_action == "clearcache":
            self.clear_map_cache()
        elif menu_action == "save":
            self.save_map()
        elif menu_action == "savevis":
            self.save_map(self.get_visible_bounds())
        elif menu_action == "printable":
            self.printable_map()
        elif menu_action == "printablevis":
            self.printable_map(self.get_visible_bounds())
        elif menu_action == "editsources":
            srced = map_source_editor.MapSourcesEditor(self.config)
            srced.run()
            srced.destroy()
            self.emit("reload-sources")

    def make_menu(self):
        '''
        Make Menu.

        :returns: Menu object
        '''
        menu_xml = """
<ui>
  <menubar name="MenuBar">
    <menu action="map">
      <menuitem action="refresh"/>
      <menuitem action="clearcache"/>
      <menuitem action="editsources"/>
      <menu action="export">
        <menuitem action="printable"/>
        <menuitem action="printablevis"/>
        <menuitem action="save"/>
        <menuitem action="savevis"/>
      </menu>
    </menu>
  </menubar>
</ui>
"""
        actions = [('map', None, "_" + _("Map"), None, None, self.mh),
                   ('refresh', None, "_" + _("Refresh"), None, None, self.mh),
                   ('clearcache', None, "_" + _("Delete local Map cache"),
                    None, None, self.mh),
                   ('editsources', None, _("Edit Sources"),
                    None, None, self.mh),
                   #('startmapserver', None,
                   # _("Start map server (on google maps layer)"),
                   # None, None, self.mh),
                   ('export', None, "_" + _("Export"),
                    None, None, self.mh),
                   ('printable', None, "_" + _("Printable"),
                    "<Control>p", None, self.mh),
                   ('printablevis', None, _("Printable (visible area)"),
                    "<Control><Alt>P", None, self.mh),
                   ('save', None, "_" + _("Save Image"),
                    "<Control>s", None, self.mh),
                   ('savevis', None, _('Save Image (visible area)'),
                    "<Control><Alt>S", None, self.mh),
                   ]

        uim = Gtk.UIManager()
        self.menu_ag = Gtk.ActionGroup.new("MenuBar")

        self.menu_ag.add_actions(actions)

        uim.insert_action_group(self.menu_ag, 0)
        # pylint: disable=unused-variable
        menuid = uim.add_ui_from_string(menu_xml)

        # Deprecated.
        self._accel_group = uim.get_accel_group()

        # Deprecated.
        return uim.get_widget("/MenuBar")

    def make_controls(self):
        '''
        Make Controls.

        :returns: Box object
        '''
        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 2)

        vbox.pack_start(self.make_zoom_controls(), 0, 0, 0)
        vbox.pack_start(self.make_track(), 0, 0, 0)

        vbox.show()

        return vbox

    def make_bottom_pane(self):
        '''
        Make Bottom Pane.

        :returns: Box object
        '''
        box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 2)

        box.pack_start(self.make_marker_list(), 1, 1, 1)
        box.pack_start(self.make_controls(), 0, 0, 0)

        box.show()

        return box

    # pylint: disable=no-self-use
    def scroll_to_center(self, widget):
        '''
        Scroll to Center.

        :param widget: ScrolledWindow Widget to Center
        '''
        adjustment = widget.get_vadjustment()
        adjustment.set_value((adjustment.get_upper() -
                              adjustment.get_page_size()) / 2)

        adjustment = widget.get_hadjustment()
        adjustment.set_value((adjustment.get_upper() -
                              adjustment.get_page_size()) / 2)

    def center_on(self, lat, lon):
        '''
        Center On.

        :param lat: Latitude to center on
        :param long: Longitude to center on
        '''
        hadj = self.scrollw.get_hadjustment()
        vadj = self.scrollw.get_vadjustment()

        x_axis, y_axis = self.map.latlon2xy(lat, lon)

        hadj.set_value(x_axis - (hadj.page_size / 2))
        vadj.set_value(y_axis - (vadj.page_size / 2))

    def status(self, frac, message):
        '''
        Status.

        :param frac: Fraction
        :param message: Status message
        '''
        self.sb_prog.set_text(message)
        self.sb_prog.set_fraction(frac)

    def recenter(self, lat, lon):
        '''
        Recenter.

        :param lat: Latitude to recenter on
        :param lon: Longitude to recenter on
        '''
        self.map.set_center(lat, lon)
        self.map.load_tiles()
        self.refresh_marker_list()
        self.center_on(lat, lon)
        # self.map.queue_draw()

    def refresh(self):
        '''Refresh.'''
        print("mapdisplay.MapWindow.refresh: ",
              "Could not find where this is called!")
        self.map.load_tiles()

    def prompt_to_set_marker(self, point, group=None):
        '''
        Prompt to set marker.

        :param point: Point to set marker on
        :param group: Optional group
        :returns: Tuple of (point, group) or (None, None)
        '''
        # def do_address(_button, latw, lonw, namew):
        #    dlg = geocode_ui.AddressAssistant()
        #    if dlg.geocoders:
        #        run_status = dlg.run()
        #        if run_status == Gtk.ResponseType.OK:
        #            if not namew.get_text():
        #                namew.set_text(dlg.place)
        #            latw.set_text("%.5f" % dlg.lat)
        #            lonw.set_text("%.5f" % dlg.lon)

        dialog = MarkerEditDialog()

        sources = []
        for src in self.map_sources:
            if src.get_mutable():
                sources.append(src.get_name())

        dialog.set_groups(sources, group)
        dialog.set_point(point)
        run_status = dialog.run()
        if run_status == Gtk.ResponseType.OK:
            point = dialog.get_point()
            group = dialog.get_group()
        dialog.destroy()

        if run_status == Gtk.ResponseType.OK:
            return point, group
        return None, None

    def prompt_to_send_loc(self, _lat, _lon):
        '''
        Prompt to send location.

        :param _lat: Latitude, not used
        :param _lon: Longitude, not used
        '''
        dialog = inputdialog.FieldDialog(title=_("Broadcast Location"))

        callsign_e = Gtk.Entry()
        callsign_e.set_max_length(8)
        dialog.add_field(_("Callsign"), callsign_e)
        desc_e = Gtk.Entry()
        desc_e.set_max_length(20)
        dialog.add_field(_("Description"), desc_e)
        dialog.add_field(_("Latitude"), miscwidgets.LatLonEntry())
        dialog.add_field(_("Longitude"), miscwidgets.LatLonEntry())
        dialog.get_field(_("Latitude")).set_text("%.4f" % _lat)
        dialog.get_field(_("Longitude")).set_text("%.4f" % _lon)

        while dialog.run() == Gtk.ResponseType.OK:
            try:
                call = dialog.get_field(_("Callsign")).get_text()
                desc = dialog.get_field(_("Description")).get_text()
                lat = dialog.get_field(_("Latitude")).get_text()
                lon = dialog.get_field(_("Longitude")).get_text()

                fix = GPSPosition(lat=lat, lon=lon, station=call)
                fix.comment = desc

                for port in self.emit("get-station-list").keys():
                    self.emit("user-send-chat",
                              "CQCQCQ", port,
                              fix.to_NMEA_GGA(), True)

                break
            # pylint: disable=broad-except
            except Exception as err:
                print("Mapdiplay.MapWindow.prompt_to_send_loc",
                      " Broad Exception (%s) %s" % (type(err), err))
                utils.log_exception()
                except_dialog = Gtk.MessageDialog(buttons=Gtk.ButtonsType.OK,
                                                  parent=dialog)
                except_dialog.set_property("text",
                                           _("Invalid value") + ": %s" % err)
                except_dialog.run()
                except_dialog.destroy()

        dialog.destroy()

    def recenter_cb(self, view, path, column, data=None):
        '''
        Recenter Callback.

        :param view: Gtk.TreeView object that received signal
        :param path: Gtk.TreePath for the activated row
        :param column: Gtk.TreeviewColumn that was activated
        :param data: Optional data, Default None
        '''
        model = view.get_model()
        if model.iter_parent(model.get_iter(path)) is None:
            return

        items = self.marker_list.get_selected()

        self.center_mark = items[1]
        self.recenter(items[2], items[3])

        self.sb_center.pop(self.STATUS_CENTER)
        self.sb_center.push(self.STATUS_CENTER,
                            _("Center") + ": %s" % self.center_mark)

    def make_popup(self, vals):
        '''
        Make Popup.

        :param vals: Values for popup
        :returns: Widget
        '''
        def _an(cap):
            return cap.replace(" ", "_")

        xml = ""
        # pylint: disable=consider-iterating-dictionary
        for action in [_an(x) for x in self._popup_items.keys()]:
            xml += "<menuitem action='%s'/>\n" % action

        xml = """
<ui>
  <popup name="menu">
    <menuitem action='title'/>
    <separator/>
    %s
  </popup>
</ui>
""" % xml
        action_group = Gtk.ActionGroup.new("menu")

        title = Gtk.Action.new("title",
                               "%.4f,%.4f" % (vals["lat"], vals["lon"]),
                               None,
                               None)
        title.set_sensitive(False)
        action_group.add_action(title)

        for name, handler in self._popup_items.items():
            action = Gtk.Action.new(_an(name), name, None, None)
            action.connect("activate", handler, vals)
            action_group.add_action(action)

        uim = Gtk.UIManager()
        uim.insert_action_group(action_group, 0)
        uim.add_ui_from_string(xml)

        return uim.get_widget("/menu")

    def mouse_click_event(self, widget, event):
        '''
        Mouse Click Event.

        :param widget: Gtk.ScrolledWindow Widget clicked on
        :param event: Gtk.EventButton that triggered this handler
        :returns: True to stop other handlers from processing the event.
        '''
        x_axis, y_axis = event.get_coords()

        hadj = widget.get_hadjustment()
        vadj = widget.get_vadjustment()
        mx_axis = x_axis + int(hadj.get_value())
        my_axis = y_axis + int(vadj.get_value())

        lat, lon = self.map.xy2latlon(mx_axis, my_axis)

        self.logger.info("Button %i at %i,%i",
                         event.button, mx_axis, my_axis)
        # See comment below.
        # pylint: disable=protected-access
        if event.button == 3:
            vals = {"lat" : lat,
                    "lon" : lon,
                    "x" : mx_axis,
                    "y" : my_axis}
            menu = self.make_popup(vals)
            if menu:
                menu.popup(None, None, None, None, event.button, event.time)
        elif event.type == Gdk.EventType.BUTTON_PRESS:
            self.logger.info("Clicked: %.4f,%.4f", lat, lon)
            # The crosshair marker has been missing since 0.3.0
            # self.set_marker(GPSPosition(station=CROSSHAIR,
            #                             lat=lat, lon=lon))
        # This is not a protected-access, it is the actual
        # python name for the type.
        elif event.type == Gdk.EventType._2BUTTON_PRESS:
            self.logger.info("recenter on %.4f, %.4f", lat, lon)

            self.recenter(lat, lon)

    def mouse_move_event(self, _widget, event):
        '''
        Mouse Move Event.

        :param _widget: MapWidget that received the signal, Not used.
        :param event: Gdk.EventMotion
        :returns: True to stop other handlers from being invoked
        '''
        if not self.__last_motion:
            GLib.timeout_add(100, self._mouse_motion_handler)
        self.__last_motion = (time.time(), event.x, event.y)

    # pylint: disable=too-many-locals
    def _mouse_motion_handler(self):
        if self.__last_motion is None:
            return False

        time_motion, x_axis, y_axis = self.__last_motion
        if (time.time() - time_motion) < 0.5:
            self.info_window.hide()
            return True

        lat, lon = self.map.xy2latlon(x_axis, y_axis)

        hadj = self.scrollw.get_hadjustment()
        vadj = self.scrollw.get_vadjustment()
        mx_axis = x_axis - int(hadj.get_value())
        my_axis = y_axis - int(vadj.get_value())

        hit = False

        for source in self.map_sources:
            if not source.get_visible():
                continue
            for point in source.get_points():
                if not point.get_visible():
                    continue
                try:
                    _x, _y = self.map.latlon2xy(point.get_latitude(),
                                                point.get_longitude())
                except ZeroDivisionError:
                    continue

                dx_axis = abs(x_axis - _x)
                dy_axis = abs(y_axis - _y)

                if dx_axis < 20 and dy_axis < 20:
                    hit = True

                    date = time.ctime(point.get_timestamp())

                    text = "<b>Station:</b> %s" % point.get_name() + \
                        "\n<b>Latitude:</b> %.5f" % point.get_latitude() + \
                        "\n<b>Longitude:</b> %.5f"% point.get_longitude() + \
                        "\n<b>Last update:</b> %s" % date

                    text += "\n<b>Info</b>: %s" % point.get_comment()

                    label = Gtk.Label()
                    label.set_markup(text)
                    label.show()
                    for child in self.info_window.get_children():
                        self.info_window.remove(child)
                    self.info_window.add(label)

                    posx, posy = self.get_position()
                    posx += mx_axis + 10
                    posy += my_axis - 10

                    self.info_window.move(int(posx), int(posy))
                    self.info_window.show()

                    break

        if not hit:
            self.info_window.hide()

        self.sb_coords.pop(self.STATUS_COORD)
        self.sb_coords.push(self.STATUS_COORD, "%.4f, %.4f" % (lat, lon))

        self.__last_motion = None

        return False

    def ev_destroy(self, _widget, _data=None):
        '''
        Event Destroy

        Signaled when all holders of a reference to a widget should release
        the reference that they hold.

        May result in finalization of the widget if all references are released
        Any return value usage not documented in Gtk 3
        :param _widget: Widget (unused)
        :param _data: data (unused)
        :returns: True to stop other handlers for this signal from running
        '''
        self.hide()
        return True

    def ev_delete(self, _widget, _event, _data=None):
        '''
        Event Delete.  Intercepts the closing of a window so that it
        can be hidden and re-used.

        Hides this object
        :param _widget: Widget (unused)
        :param _event: event (unused)
        :param _data: data (unused)
        :returns: True to stop other handlers for this signal from running
        '''
        self.hide()
        return True

    def update_gps_status(self, string):
        '''
        Update GPS Status.

        :param string: GPS status string
        '''
        self.sb_gps.pop(self.STATUS_GPS)
        self.sb_gps.push(self.STATUS_GPS, string)

    def add_point_visible(self, point):
        '''
        Add Point Visible.

        :param point: Point to add
        :returns: True if point is visible
        '''
        if point in self.points_visible:
            self.points_visible.remove(point)

        if self.map.point_is_visible(point.get_latitude(),
                                     point.get_longitude()):
            if point.get_visible():
                self.points_visible.append(point)
                return True
            return False
        return False

    def update_point(self, source, point):
        '''
        Update Point.

        :param source: Map source
        :param point: Point to update
        '''
        (_lat, _lon) = self.map.get_center()
        center = GPSPosition(*self.map.get_center())
        this = GPSPosition(point.get_latitude(), point.get_longitude())

        try:
            self.marker_list.set_item(source.get_name(),
                                      point.get_visible(),
                                      point.get_name(),
                                      point.get_latitude(),
                                      point.get_longitude(),
                                      center.distance_from(this),
                                      center.bearing_to(this))
        # pylint: disable=broad-except
        except Exception as err:
            # print('mapdisplay.MapWindow.update_point: ',
            #      " (%s) %s" % (type(err), err))
            if str(err) == "Item not found":
                # this is evil
                self.logger.info("Adding point instead of updating")
                self.add_point(source, point)

        self.add_point_visible(point)
        # self.map.queue_draw()

    def add_point(self, source, point):
        '''
        Add Point.

        :param source: Map source
        :param point: Point to add
        '''
        (_lat, _lon) = self.map.get_center()
        center = GPSPosition(*self.map.get_center())
        this = GPSPosition(point.get_latitude(), point.get_longitude())

        self.marker_list.add_item(source.get_name(),
                                  point.get_visible(), point.get_name(),
                                  point.get_latitude(),
                                  point.get_longitude(),
                                  center.distance_from(this),
                                  center.bearing_to(this))
        self.add_point_visible(point)
        # self.map.queue_draw()

    def del_point(self, source, point):
        '''
        Delete Point.

        :param source: Map source
        :param point: Point to delete
        '''
        self.marker_list.del_item(source.get_name(), point.get_name())

        if point in self.points_visible:
            self.points_visible.remove(point)

        # self.map.queue_draw()

    def get_map_source(self, name):
        '''
        Get Map Source.

        :param name: Name of map source
        :returns: Map Source for name or None
        '''
        for source in self.get_map_sources():
            if source.get_name() == name:
                return source
        return None

    def add_map_source(self, source):
        '''
        Add Map Source.

        :param source: New map source
        '''
        self.map_sources.append(source)
        self.marker_list.add_item(None,
                                  source.get_visible(), source.get_name(),
                                  0, 0, 0, 0)
        for point in source.get_points():
            self.add_point(source, point)

        #source.connect("point-updated", self.update_point)
        source.connect("point-added", self.add_point)
        source.connect("point-deleted", self.del_point)
        source.connect("point-updated", self.maybe_recenter_on_updated_point)

    def update_points_visible(self):
        '''Update Points Visible.'''
        # print("#update points visible ",
        #      " Called")
        for src in self.map_sources:
            for point in src.get_points():
                # print("# update_points_visible point = %xs" % point)
                self.update_point(src, point)

        # self.map.queue_draw()

    def maybe_recenter_on_updated_point(self, source, point):
        '''
        Maybe Recenter on Updated Point.

        :param source: Source of map
        :param point: Updated point
        '''
        if point.get_name() == self.center_mark and \
                self.tracking_enabled:
            self.logger.info("Center updated")
            self.recenter(point.get_latitude(), point.get_longitude())
        self.update_point(source, point)

    def clear_map_sources(self):
        '''Clean Map Sources.'''
        self.marker_list.clear()
        self.map_sources = []
        self.points_visible = []
        self.update_points_visible()

    def get_map_sources(self):
        '''Get Map Sources.'''
        return self.map_sources

    def redraw_markers(self, map_widget):
        '''
        Redraw Markers.

        :param map_widget: Map widget to redraw
        '''
        # print("#redraw_markers: ")
        for point in self.points_visible:
            map_widget.draw_marker(point.get_name(),
                                   point.get_latitude(),
                                   point.get_longitude(),
                                   point.get_icon())

    # pylint: disable=too-many-statements
    def __init__(self, config):
        Gtk.Window.__init__(self, type=Gtk.WindowType.TOPLEVEL)

        self.logger = logging.getLogger("MapWindow")
        # to force open the mapwindow maximized
        # self.maximize()

        self.config = config
        self.marker_list = None
        self.map_tiles = []

        # pylint: disable=invalid-name
        self.STATUS_COORD = 0
        # pylint: disable=invalid-name
        self.STATUS_CENTER = 1
        # pylint: disable=invalid-name
        self.STATUS_GPS = 2

        self.center_mark = None
        self.tracking_enabled = False

        # this parameter defines the dimension of the map behind the window
        # tiles SHALL be
        #  - ODD due to the mechanism used then to calculate the
        #    offsets to keep aligned the stations markers in the map into the
        #    calculate_bound
        #  - the same for both x and y in the mapwidget creation
        tiles = 9

        self.points_visible = []
        self.map_sources = []

        self.map = MapWidget(self, tiles, tiles, status=self.status)
        # print('MapWidget created.')
        self.map.show()
        # print('map show called')
        self.map.connect("redraw-markers", self.redraw_markers)
        self.map.connect("new-tiles-loaded",
                         lambda m: self.update_points_visible())

        box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 2)

        # print("setting up menubar")
        self.menubar = self.make_menu()
        # print("showing menubar")
        self.menubar.show()
        box.pack_start(self.menubar, 0, 0, 0)
        self.add_accel_group(self._accel_group)

        self.scrollw = Gtk.ScrolledWindow()
        # print('Adding map to viewport')
        self.scrollw.add(self.map)
        # print('Showing map')
        self.scrollw.show()

        # Handle a mouse scroll event.
        def scrolling(_widget, _event, map_window):
            map_window.map.map_tiles = []

        # Handle adjustment change
        def adjusted(_widget, map_window):
            map_window.map.map_tiles = []

        def pre_scale(widget, _cairo_ctx, _map_window): # type:ignore
            # print("type(widget) = %s" % type(widget))
            # print("type(widget.get_window() = %s" % type(widget.get_window()))
            hadj = widget.get_hadjustment()
            vadj = widget.get_vadjustment()

            # p_x = hadj.get_value() + hadj.get_page_size()
            p_y = vadj.get_value() + vadj.get_page_size()

            rect = Gdk.Rectangle()
            rect.height = int(hadj.get_value())
            rect.width = int(vadj.get_value())
            rect.x = int(p_y)
            rect.y = int(p_y)
            # map_window.map.window.invalidate_rect(rect, True)
            window = widget.get_window()
            # window is a Gdk.X11Window
            # print("#pre_scale type(window) = %s" % type(window))
            window.invalidate_rect(rect, True)

        @utils.run_gtk_locked
        def _scale(widget, cairo_ctx, map_window):
            hadj = widget.get_hadjustment()
            vadj = widget.get_vadjustment()

            p_x = hadj.get_value() + hadj.get_page_size()
            p_y = vadj.get_value() + vadj.get_page_size()

            _p_m = map_window.map.scale(widget, cairo_ctx,
                                        int(p_x) - 5, int(p_y))

        def scale(widget, cairo_ctx, map_window):
            GLib.idle_add(_scale, widget, cairo_ctx, map_window)

        self.scrollw.connect("draw", pre_scale, self)
        self.scrollw.connect_after("draw", scale, self)

        self.__last_motion = None

        self.map.add_events(Gdk.EventMask.POINTER_MOTION_MASK)
        self.map.connect("motion-notify-event", self.mouse_move_event)
        self.scrollw.connect("button-press-event", self.mouse_click_event)
        self.scrollw.connect("scroll-event", scrolling, self)
        hadj = self.scrollw.get_hadjustment()
        vadj = self.scrollw.get_vadjustment()
        hadj.connect("value-changed", adjusted, self)
        vadj.connect("value-changed", adjusted, self)

        self.scrollw.connect('realize', self.scroll_to_center)

        hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 2)

        self.sb_coords = Gtk.Statusbar()
        self.sb_coords.show()
        # self.sb_coords.set_has_resize_grip(False)

        self.sb_center = Gtk.Statusbar()
        self.sb_center.show()
        # self.sb_center.set_has_resize_grip(False)

        self.sb_gps = Gtk.Statusbar()
        self.sb_gps.show()

        self.sb_prog = Gtk.ProgressBar()
        self.sb_prog.set_size_request(150, -1)
        self.sb_prog.show()

        hbox.pack_start(self.sb_coords, 1, 1, 1)
        hbox.pack_start(self.sb_center, 1, 1, 1)
        hbox.pack_start(self.sb_prog, 0, 0, 0)
        hbox.pack_start(self.sb_gps, 1, 1, 1)
        hbox.show()

        box.pack_start(self.scrollw, 1, 1, 1)
        box.pack_start(self.make_bottom_pane(), 0, 0, 0)
        box.pack_start(hbox, 0, 0, 0)
        box.show()

        #setup the default dimensions for the map window
        self.set_default_size(800, 600)

        # commented out this to have the possibility to maximize the mapwindow.
        # don't know why Dan put this originally, maybe removing this will
        # create issues in some situations... will see

        # self.set_geometry_hints(max_width=tiles*256, max_height=tiles*256)

        self.markers = {}
        self.colors = {}
        self.color_index = 0

        self.add(box)

        self.connect("destroy", self.ev_destroy)
        self.connect("delete_event", self.ev_delete)

        self._popup_items = {}

        self.add_popup_handler(_("Center here"),
                               lambda a, vals:
                               self.recenter(vals["lat"],
                                             vals["lon"]))

        def set_mark_at(_a, vals):
            '''
            Set Mark at.

            :param _a: Unused.
            :param vals: dict with "lat" and "lon" members
            '''
            pos = map_sources.MapStation("STATION", vals["lat"], vals["lon"])
            pos.set_icon_from_aprs_sym("\\<")
            point, group = self.prompt_to_set_marker(pos)
            if not point:
                return

            for source in self.map_sources:
                self.logger.info("%s,%s", source.get_name(), group)
                if source.get_name() == group:
                    self.logger.info("Adding new point %s to %s",
                                     point.get_name(), source.get_name())
                    source.add_point(point)
                    source.save()
                    return
            # No matching group
            query = "%s %s %s" % \
                (_("Group"), group,
                 _("does not exist.  Do you want to create it?"))
            if not ask_for_confirmation(query):
                return

            # pylint: disable=not-callable
            src = map_sources.MapFileSource.open_source_by_name(self.config,
                                                                group,
                                                                True)
            src.add_point(point)
            src.save()
            self.add_map_source(src)

        self.add_popup_handler(_("New marker here"), set_mark_at)
        self.add_popup_handler(_("Broadcast this location"),
                               lambda a, vals:
                               self.prompt_to_send_loc(vals["lat"],
                                                       vals["lon"]))

        # create the INFO WINDOW which is shown over the map clicking
        # the left mouse button
        self.info_window = Gtk.Window(type=Gtk.WindowType.POPUP)
        self.info_window.set_type_hint(Gdk.WindowTypeHint.MENU)
        self.info_window.set_decorated(False)
        # modify_bg deprecated for override_background_color
        # override_background_color deprecated, use Gtk.StyleProvider and
        # a CSS style class or modifying drawing through the draw signal with
        # Cairo.
        self.info_window.modify_bg(Gtk.StateType.NORMAL,
                                   Gdk.color_parse("yellow"))

    def add_popup_handler(self, name, handler):
        '''
        Add Popup Handler.

        :param name: Name to be handled.
        :param handler: Handler routine
        '''
        self._popup_items[name] = handler

    def set_zoom(self, zoom):
        '''
        Set zoom.

        :param zoom: Zoom level
        '''
        self.map.set_zoom(zoom)

    def set_center(self, lat, lon):
        '''
        Set Center.

        :param lat: Latitude to center on
        :param lon: Longitude to center on
        '''
        self.map.set_center(lat, lon)


def main():
    '''Main program for unit testing.'''

    import sys
    from . import gps
    from . import config

    logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
                        datefmt="%m/%d/%Y %H:%M:%S",
                        level=logging.INFO)
    # pylint: disable=invalid-name
    logger = logging.getLogger("MapDisplay")

    logger.info("__Executing __main__ section")

    # pylint: disable=invalid-name
    lang = gettext.translation("D-RATS",
                               localedir="./locale",
                               languages=["en"],
                               fallback=True)
    lang.install()

    # WB8TYW: DratsConfig takes an unused argument.
    conf = config.DratsConfig(None)

    mapurl = conf.get("settings", "mapurlbase")
    mapkey = ""

    set_connected(True)
    set_tile_lifetime(conf.getint("settings", "map_tile_ttl") * 3600)


    set_base_dir(os.path.join(conf.get("settings", "mapdir"),
                              conf.get("settings", "maptype")), mapurl, mapkey)
    proxy = conf.get("settings", "http_proxy") or None
    set_proxy(proxy)

    if len(sys.argv) == 3:
        map_window = MapWindow(conf)
        map_window.set_center(gps.parse_dms(sys.argv[1]),
                              gps.parse_dms(sys.argv[2]))
        map_window.set_zoom(15)
    else:
        map_window = MapWindow(config)
        map_window.set_center(45.525012, -122.916434)
        map_window.set_zoom(14)

        # m.set_marker(GPSPosition(station="KI4IFW_H",
        #                          lat=45.520, lon=-122.916434))
        # m.set_marker(GPSPosition(station="KE7FTE",
        #                          lat=45.5363, lon=-122.9105))
        # m.set_marker(GPSPosition(station="KA7VQH",
        #                          lat=45.4846, lon=-122.8278))
        # m.set_marker(GPSPosition(station="N7QQU",
        #                          lat=45.5625, lon=-122.8645))
        # m.del_marker("N7QQU")

    map_window.connect("destroy", Gtk.main_quit)
    map_window.show()

    # try:
    Gtk.main()
    # pylint: disable=bare-except
    # except:
    #    pass

if __name__ == "__main__":
    main()
