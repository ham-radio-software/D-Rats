#!/usr/bin/python
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

import os
import sys

import math
import six.moves.urllib.request, six.moves.urllib.parse, six.moves.urllib.error
from six.moves.urllib.error import URLError, HTTPError
import time
import random
import shutil
import tempfile
import threading
import copy

import gtk
import gobject
from math import *

if __name__ == "__main__":
    import gettext
    # pylint: disable=invalid-name
    lang = gettext.translation("D-RATS",
                               localedir="./locale",
                               languages=["en"],
                               fallback=True)
    lang.install()


#py3 from . import mainapp
#importing printlog() wrapper
from .debug import printlog
from . import dplatform
from . import miscwidgets
from . import inputdialog
from . import utils
from . import geocode_ui
from . import map_sources
from . import map_source_editor
from . import signals
from . import debug

##############
from .ui.main_common import ask_for_confirmation
from .gps import GPSPosition, distance, value_with_units, DPRS_TO_APRS
from six.moves import range

CROSSHAIR = "+"

COLORS = ["red", "green", "cornflower blue", "pink", "orange", "grey"]

#set the map location
BASE_DIR = None
MAP_TYPE = None
MAP_URL = None
MAP_URL_KEY = None

def set_base_dir(basedir, mapurl, mapkey):
    
    global BASE_DIR
    BASE_DIR = basedir 
    printlog("Mapdisplay",": BASE_DIR configured to %s: " % BASE_DIR)
  
    #setup of the url where go to retrieve tiles
    global MAP_URL
    MAP_URL = mapurl 
    printlog("Mapdisplay",": MAP_URL configured to: %s" % MAP_URL)
    
    #setup of the key to append to the url to retrieve tiles
    global MAP_URL_KEY
    MAP_URL_KEY = mapkey 
    printlog("Mapdisplay",": MAP_URL_KEY configured to: %s " %MAP_URL_KEY)
    
CONFIG = None

CONNECTED = True
MAX_TILE_LIFE = 0
PROXY = None

def set_connected(connected):
    global CONNECTED
    CONNECTED = connected

def set_tile_lifetime(lifetime):
    global MAX_TILE_LIFE
    MAX_TILE_LIFE = lifetime

def set_proxy(proxy):
    global PROXY
    PROXY = proxy

def fetch_url(url, local):   
    global CONNECTED
    global PROXY
  
    #setup of d-rats user_agent
    from . import version  

    if not CONNECTED:
        raise Exception("Not connected")

    if PROXY:
        #proxies = {"http" : PROXY}
        authinfo = urllib.request.HTTPBasicAuthHandler()
        proxy_support = six.moves.urllib.request.ProxyHandler({"http" : PROXY})
        opener = six.moves.urllib.request.build_opener(proxy_support, authinfo,
                                     urllib.request.CacheFTPHandler)
        six.moves.urllib.request.install_opener(opener)
    else:
        proxies = None
    #data = six.moves.urllib.request.urlopen(url, proxies=proxies)
    req = six.moves.urllib.request.Request(url, None, version.HTTP_CLIENT_HEADERS)

    try:
        data = six.moves.urllib.request.urlopen(req)
    except HTTPError as e:
        if e.code == 404:
            return
        else:
            printlog("HTTP error while retrieving tile: "
                    "code: {}, reason: {} - {} [{}]".format( e.code, e.reason, str(e), url)
            )
            return
    except Exception as e:
            printlog("Mapdisplay","Error while retrieving info from {}".format(str(e)))
            return

    d = data.read()
    local_file = open(local, "wb")
    local_file.write(d)
    data.close()
    local_file.close()
                

class MarkerEditDialog(inputdialog.FieldDialog):
    def __init__(self):
        printlog("Mapdisplay"," : markereditdialog")
        inputdialog.FieldDialog.__init__(self, title=_("Add Marker"))

        self.icons = []
        for sym in sorted(DPRS_TO_APRS.values()):
            icon = utils.get_icon(sym)
            if icon:
                self.icons.append((icon, sym))

        self.add_field(_("Group"), miscwidgets.make_choice([], True))
        self.add_field(_("Name"), gtk.Entry())
        self.add_field(_("Latitude"), miscwidgets.LatLonEntry())
        self.add_field(_("Longitude"), miscwidgets.LatLonEntry())
        self.add_field(_("Lookup"), gtk.Button("By Address"))
        self.add_field(_("Comment"), gtk.Entry())
        self.add_field(_("Icon"), miscwidgets.make_pixbuf_choice(self.icons))

        self._point = None

    def set_groups(self, groups, group=None):
        grpsel = self.get_field(_("Group"))
        for grp in groups:
            grpsel.append_text(grp)

        if group is not None:
            grpsel.child.set_text(group)
            grpsel.set_sensitive(False)
        else:
            grpsel.child.set_text(_("Misc"))

    def get_group(self):
        return self.get_field(_("Group")).child.get_text()

    def set_point(self, point):
        self.get_field(_("Name")).set_text(point.get_name())
        self.get_field(_("Latitude")).set_text("%.4f" % point.get_latitude())
        self.get_field(_("Longitude")).set_text("%.4f" % point.get_longitude())
        self.get_field(_("Comment")).set_text(point.get_comment())

        iconsel = self.get_field(_("Icon"))
        if isinstance(point, map_sources.MapStation):
            symlist = [y for x,y in self.icons]
            try:
                iidx = symlist.index(point.get_aprs_symbol())
                iconsel.set_active(iidx)
            except ValueError:
                printlog("Mapdisplay",": No such symbol `%s'" % point.get_aprs_symbol())
        else:
            iconsel.set_sensitive(False)

        self._point = point

    def get_point(self):
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
    #lat_rad = lat_deg * math.pi / 180.0
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n)
    return(xtile, ytile)

def num2deg(xtile, ytile, zoom):
    n = 2.0 ** zoom
    lon_deg = xtile / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
    lat_deg = math.degrees(lat_rad)
    return (lat_deg, lon_deg)

class MapTile(object):
    #this class downloads the map tiles
    def path_els(self):
        return deg2num(self.lat, self.lon, self.zoom)

    def tile_edges(self):
        n, w = num2deg(self.x, self.y, self.zoom)
        s, e = num2deg(self.x+1, self.y+1, self.zoom)
        return (s, w, n, e)

    def lat_range(self):
        s, w, n, e = self.tile_edges()
        return (n, s)

    def lon_range(self):
        s, w, n, e = self.tile_edges()
        return (w, e)

    def path(self):
        return "%d/%d/%d.png" % (self.zoom, self.x, self.y)

    def _local_path(self):
        path = os.path.join(self.dir, self.path())
        if not os.path.isdir(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        return path

    def is_local(self):
        if MAX_TILE_LIFE == 0 or not CONNECTED:
            return os.path.exists(self._local_path())
        else:
            try:
                ts = os.stat(self._local_path()).st_mtime
                return (time.time() - ts) < MAX_TILE_LIFE
            except OSError:
                return False

    def fetch(self):
        #verify if tile is local, if not fetches from web
        if not self.is_local():
            for i in range(10):
                url = self.remote_path()
                try:
                    fetch_url(url, self._local_path())
                    printlog("Mapdisplay",": opened %s" % url)
                    return True
                except Exception as e:
                    printlog("Mapdisplay",": [%i] Failed to fetch `%s': %s" % (i, url, e))

            return False
        else:
            return True

    def _thread(self, cb, *args):
        if self.fetch():
            fname = self._local_path()
        else:
            fname = None

        gobject.idle_add(cb, fname, *args)

    def threaded_fetch(self, cb, *args):
        _args = (cb,) + args
        t = threading.Thread(target=self._thread, args=_args)
        t.setDaemon(True)
        t.start()

    def local_path(self):
        path = self._local_path()
        self.fetch()
        return path

    def remote_path(self):
        return MAP_URL + (self.path()) + MAP_URL_KEY

    def __add__(self, count):
        (x, y) = count
        return MapTile(self.x+x, self.y+y, self.zoom)

    def __sub__(self, tile):
        return (self.x - tile.x, self.y - tile.y)

    def __contains__(self, point):
        (lat, lon) = point

        # FIXME for non-western!
        (lat_max, lat_min) = self.lat_range()
        (lon_min, lon_max) = self.lon_range()

        lat_match = (lat < lat_max and lat > lat_min)
        lon_match = (lon < lon_max and lon > lon_min)

        return lat_match and lon_match

    def __init__(self, lat, lon, zoom):
        
        self.zoom = zoom
        if isinstance(lat, int) and isinstance(lon, int):
            self.x = lat
            self.y = lon
            self.lat, self.lon = num2deg(self.x, self.y, self.zoom)
        else:
            self.lat = lat
            self.lon = lon
            self.x, self.y = deg2num(self.lat, self.lon, self.zoom)

        self.dir = BASE_DIR 

        #create the local dir to store tiles if doesn't exist 
        if not os.path.isdir(self.dir):
            os.mkdir(self.dir)
            
    def __str__(self):
        return "%.4f,%.4f (%i,%i)" % (self.lat, self.lon, self.x, self.y)

class LoadContext(object):
    pass

class MapWidget(gtk.DrawingArea):
    __gsignals__ = {
        "redraw-markers" : (gobject.SIGNAL_RUN_LAST,
                            gobject.TYPE_NONE,
                            ()),
        "new-tiles-loaded" : (gobject.SIGNAL_ACTION,
                              gobject.TYPE_NONE,
                              ()),
        }

    def draw_text_marker_at(self, x, y, text, color="yellow"):
        #printlog("Mapdisplay",": draw_text_marker_at %s at x=%s y=%s" %(text, x, y))

        gc = self.get_style().black_gc
        
        #setting the size for the text marker 
        if self.zoom < 12:
            size = 'size="x-small"'
        elif self.zoom < 14:    
            size = 'size="small"'
        else:
            size = ''
        text = utils.filter_to_ascii(text)

        pl = self.create_pango_layout("")
        markup = '<span %s background="%s">%s</span>' % (size, color, text)
        pl.set_markup(markup)
       
        self.window.draw_layout(gc, int(x), int(y), pl)

    def draw_image_at(self, x, y, pb):
        #printlog("Mapdisplay",": draw_image_at x=%s y=%s" %(x, y))
        gc = self.get_style().black_gc

        self.window.draw_pixbuf(gc,
                                pb,
                                0, 0,
                                int(x), int(y))

        return pb.get_height()

    def draw_cross_marker_at(self, x, y):
        #printlog("Mapdisplay",": draw_cross_marker_at x=%s y=%s" %(x, y))
        width = 2
        cm = self.window.get_colormap()
        color = cm.alloc_color("red")
        gc = self.window.new_gc(foreground=color,
                                line_width=width)

        x = int(x)
        y = int(y)

        self.window.draw_lines(gc, [(x, y-5), (x, y+5)])
        self.window.draw_lines(gc, [(x-5, y), (x+5, y)])

    def latlon2xy(self, lat, lon):
        y = 1- ((lat - self.lat_min) / (self.lat_max - self.lat_min))
        x = 1- ((lon - self.lon_min) / (self.lon_max - self.lon_min))

        x *= (self.tilesize * self.width)
        y *= (self.tilesize * self.height)

        y += self.lat_fudge
        x += self.lng_fudge
        return (x, y)

    def xy2latlon(self, x, y):
        y -= self.lat_fudge
        x -= self.lng_fudge

        lon = 1 - (float(x) / (self.tilesize * self.width))
        lat = 1 - (float(y) / (self.tilesize * self.height))

        lat = (lat * (self.lat_max - self.lat_min)) + self.lat_min
        lon = (lon * (self.lon_max - self.lon_min)) + self.lon_min

        return lat, lon 
    

    def draw_marker(self, label, lat, lon, img=None):
        #printlog("Mapdisplay",": ----------------- %s" % time.ctime())
        #printlog("Mapdisplay",": zoom     =%i" % self.zoom)
        #printlog("Mapdisplay",": draw marker for %s at %s %s" %(label, lat, lon))
        #printlog("Mapdisplay",": fudge    =%i" % self.lat_fudge)
        
        color = "yellow" #this is the bg color of the stations markers on the map (before it was red)

        try:
            x, y = self.latlon2xy(lat, lon)

        except ZeroDivisionError:
            return

        if label == CROSSHAIR:
            self.draw_cross_marker_at(x, y)
        else:
            if img:
                y += (4 + self.draw_image_at(x, y, img))
            self.draw_text_marker_at(x, y, label, color)

    def expose(self, area, event):
        if len(self.map_tiles) == 0:
            self.load_tiles()

        gc = self.get_style().black_gc
        self.window.draw_drawable(gc,
                                  self.pixmap,
                                  0, 0,
                                  0, 0,
                                  -1, -1)
        self.emit("redraw-markers")

    def calculate_bounds(self):
        center = MapTile(self.lat, self.lon, self.zoom)
        
        # here we set the bounds for the map into the window
        # delta is the mid of the tiles used to draw the map
        # delta is necessary to keep alignment between the map and the station labels
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
        
        s, w, n, e = center.tile_edges()
        x, y = self.latlon2xy(n, w)
        self.lng_fudge = ((self.width / 2) * self.tilesize) - x  
        self.lat_fudge = ((self.height / 2) * self.tilesize) - y
        
    def broken_tile(self):
        if self.__broken_tile:
            return self.__broken_tile

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

        # return gtk.gdk.pixbuf_new_from_xpm_data(broken)
        pm = gtk.gdk.pixmap_create_from_xpm_d(self.window, None, broken)[0]
        pb = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB,
                            False,
                            8,
                            self.tilesize, self.tilesize)
        pb.fill(0xffffffff)

        x = y = (self.tilesize / 2)

        pb.get_from_drawable(pm, pm.get_colormap(), 0, 0, x, y, -1, -1)

        self.__broken_tile = pb

        return pb

    def draw_tile(self, path, x, y, ctx=None):
        if ctx and ctx.zoom != self.zoom:
            # Zoom level has changed, so don't do anything
            return

        gc = self.pixmap.new_gc()
        if path:
            try:
                pb = gtk.gdk.pixbuf_new_from_file(path)
            except Exception as e:
                #this is the case  when some jpg tile file cannot be loaded - typically this was due to html content 
                # saved as jpg (due to an un trapped http error), or due to really corrupted jpg 
                #(e.g. d-rats was closed before completig file save )
                
                #utils.log_exception()
                #removing broken tiles                
                if os.path.exists(path):
                    printlog("Mapdisplay",": Deleting the broken tile to force future download %s" % path)
                    os.remove(path)
                #else:
                    #usually this happens when a tile file has not been create after fetching from the tile as some error was got
                    #printlog(("Mapdisplay: broken tile  not found - skipping deletion of: %s" % path))
                    
                pb = self.broken_tile()
        else:
            pb = self.broken_tile()

        if ctx:
            ctx.loaded_tiles += 1
            frac = float(ctx.loaded_tiles) / float(ctx.total_tiles)
            if ctx.loaded_tiles == ctx.total_tiles:
                self.status(0.0, "")
            else:
                self.status(frac, _("Loaded") + " %.0f%%" % (frac * 100.0))

        self.pixmap.draw_pixbuf(gc, pb, 0, 0, x, y, -1, -1)
        self.queue_draw()

    @utils.run_gtk_locked
    def draw_tile_locked(self, *args):
        self.draw_tile(*args)

    def load_tiles(self):
        self.map_tiles = []
        ctx = LoadContext()
        ctx.loaded_tiles = 0
        ctx.total_tiles = self.width * self.height
        ctx.zoom = self.zoom
        center = MapTile(self.lat, self.lon, self.zoom)

        delta_h = self.height / 2
        delta_w = self.width  / 2

        count = 0
        total = self.width * self.height

        if not self.window:
            # Window is not loaded, thus can't load tiles
            return

        try:
            self.pixmap = gtk.gdk.Pixmap(self.window,
                                         self.width * self.tilesize,
                                         self.height * self.tilesize)
        except Exception as e:
            # Window is not loaded, thus can't load tiles
            return

        gc = self.pixmap.new_gc()

        for i in range(0, self.width):
            for j in range(0, self.height):
                tile = center + (i - delta_w, j - delta_h)
                if not tile.is_local():
                    message = _("Retrieving")
                else:
                    message = _("Loading")

                if tile.is_local():
                    path = tile._local_path()
                    self.draw_tile(tile._local_path(),
                                   self.tilesize * i, self.tilesize * j,
                                   ctx)
                else:
                    self.draw_tile(None, self.tilesize * i, self.tilesize * j)
                    tile.threaded_fetch(self.draw_tile_locked,
                                        self.tilesize * i,
                                        self.tilesize * j,
                                        ctx)
                self.map_tiles.append(tile)
                count += 1

        self.calculate_bounds()
        self.emit("new-tiles-loaded")

    def export_to(self, filename, bounds=None):
        if not bounds:
            x = 0
            y = 0
            bounds = (0,0,-1,-1)
            width = self.tilesize * self.width
            height = self.tilesize * self.height
        else:
            x = bounds[0]
            y = bounds[1]
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]

        pb = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, False, 8, width, height)
        pb.get_from_drawable(self.pixmap, self.pixmap.get_colormap(),
                             x, y, 0, 0, width, height)
        pb.save(filename, "png")

    def __init__(self, width, height, tilesize=256, status=None):
        gtk.DrawingArea.__init__(self)

        self.__broken_tile = None

        self.height = height
        self.width = width
        
        #printlog("Mapdisplay",": mapwidget - height %s, width %s" % (height, width))
        self.tilesize = tilesize
        self.status = status

        self.lat = 0
        self.lon = 0
        self.zoom = 1

        self.lat_max = self.lat_min = 0
        self.lon_max = self.lon_min = 0
        self.lng_fudge = 0
        self.lat_fudge = 0

        self.map_tiles = []

        self.set_size_request(self.tilesize * self.width,
                              self.tilesize * self.height)
        self.connect("expose-event", self.expose)

    def set_center(self, lat, lon):
        self.lat = lat
        self.lon = lon
        self.map_tiles = []
        self.queue_draw()

    def get_center(self):
        return (self.lat, self.lon)

    def set_zoom(self, zoom):
        if zoom > 18 or zoom == 3:
            return

        self.zoom = zoom
        self.map_tiles = []
        self.queue_draw()

    def get_zoom(self):
        return self.zoom

    def scale(self, x, y, pixels=128):
        #draw the scale-ladder on the map  
        shift = 15
        tick = 5
        
        #rect = gtk.gdk.Rectangle(x-pixels,y-shift-tick,x,y)
        #self.window.invalidate_rect(rect, True)

        (lat_a, lon_a) = self.xy2latlon(self.tilesize, self.tilesize)
        (lat_b, lon_b) = self.xy2latlon(self.tilesize * 2, self.tilesize)

        # calculate width of one tile to show below the ladder scale
        d = distance(lat_a, lon_a, lat_b, lon_b) * (float(pixels) / self.tilesize)

        dist = value_with_units(d)

        color = self.window.get_colormap().alloc_color("black")
        gc = self.window.new_gc(line_width=1, foreground=color)

        self.window.draw_line(gc, x-pixels, y-shift, x, y-shift)
        self.window.draw_line(gc, x-pixels, y-shift, x-pixels, y-shift-tick)
        self.window.draw_line(gc, x, y-shift, x, y-shift-tick)
        self.window.draw_line(gc, x-(pixels/2), y-shift, x-(pixels/2), y-shift-tick)

        pl = self.create_pango_layout("")
        pl.set_markup("%s" % dist)
        self.window.draw_layout(gc, x-pixels, y-shift, pl)

    def point_is_visible(self, lat, lon):
        for i in self.map_tiles:
            if (lat, lon) in i:
                return True

        return False

class MapWindow(gtk.Window):
    __gsignals__ = {
        "reload-sources" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
        "user-send-chat" : signals.USER_SEND_CHAT,
        "get-station-list" : signals.GET_STATION_LIST,
        }

    _signals = {"user-send-chat" : None,
                "get-station-list" : None,
                }

    def zoom(self, widget, frame):
        adj = widget.get_adjustment()

        self.map.set_zoom(int(adj.value))
        frame.set_label(_("Zoom") + " (%i)" % int(adj.value))

    def make_zoom_controls(self):
        box = gtk.HBox(False, 3)
        box.set_border_width(3)
        box.show()

        l = gtk.Label(_("Min"))
        l.show()
        box.pack_start(l, 0,0,0)
        #mm here the allowed zoom levels are from 2 to 17 (incresed to 18) 
        adj = gtk.Adjustment(value=14,
                             lower=2,
                             upper=18,
                             step_incr=1,
                             page_incr=3)
        sb = gtk.HScrollbar(adj)
        sb.show()
        box.pack_start(sb, 1,1,1)

        l = gtk.Label(_("Max"))
        l.show()
        box.pack_start(l, 0,0,0)

        frame = gtk.Frame(_("Zoom"))
        frame.set_label_align(0.5, 0.5)
        frame.set_size_request(150, 50)
        frame.show()
        frame.add(box)

        sb.connect("value-changed", self.zoom, frame)

        return frame

    def toggle_show(self, group, *vals):
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

        self.map.queue_draw()

    def marker_mh(self, _action, id, group):
        action = _action.get_name()

        if action == "delete":
            printlog(("Mapdisplay: Deleting %s/%s" % (group, id)))
            for source in self.map_sources:
                if source.get_name() == group:
                    if not source.get_mutable():
                        return

                    point = source.get_point_by_name(id)
                    source.del_point(point)
                    source.save()
        elif action == "edit":
            for source in self.map_sources:
                if source.get_name() == group:
                    break

            if not source.get_mutable():
                return

            if not source:
                return

            for point in source.get_points():
                if point.get_name() == id:
                    break

            if not point:
                return

            _point = point.dup()
            upoint, foo = self.prompt_to_set_marker(point, source.get_name())
            if upoint:
                self.del_point(source, _point)
                self.add_point(source, upoint)
                source.save()

    def _make_marker_menu(self, store, iter):
        menu_xml = """
<ui>
  <popup name="menu">
    <menuitem action="edit"/>
    <menuitem action="delete"/>
    <menuitem action="center"/>
  </popup>
</ui>
"""
        ag = gtk.ActionGroup("menu")

        try:
            id, = store.get(iter, 1)
            group, = store.get(store.iter_parent(iter), 1)
        except TypeError:
            id = group = None

        edit = gtk.Action("edit", _("Edit"), None, None)
        edit.connect("activate", self.marker_mh, id, group)
        if not id:
            edit.set_sensitive(False)
        ag.add_action(edit)

        delete = gtk.Action("delete", _("Delete"), None, None)
        delete.connect("activate", self.marker_mh, id, group)
        ag.add_action(delete)

        center = gtk.Action("center", _("Center on this"), None, None)
        center.connect("activate", self.marker_mh, id, group)
        # This isn't implemented right now, because I'm lazy
        center.set_sensitive(False)
        ag.add_action(center)

        uim = gtk.UIManager()
        uim.insert_action_group(ag, 0)
        uim.add_ui_from_string(menu_xml)

        return uim.get_widget("/menu")

    def make_marker_popup(self, _, view, event):
        if event.button != 3:
            return

        if event.window == view.get_bin_window():
            x, y = event.get_coords()
            pathinfo = view.get_path_at_pos(int(x), int(y))
            if pathinfo is None:
                return
            else:
                view.set_cursor_on_cell(pathinfo[0])

        (store, iter) = view.get_selection().get_selected()

        menu = self._make_marker_menu(store, iter)
        if menu:
            menu.popup(None, None, None, event.button, event.time)

    def make_marker_list(self):
        cols = [(gobject.TYPE_BOOLEAN, _("Show")),
                (gobject.TYPE_STRING,  _("Station")),
                (gobject.TYPE_FLOAT,   _("Latitude")),
                (gobject.TYPE_FLOAT,   _("Longitude")),
                (gobject.TYPE_FLOAT,   _("Distance")),
                (gobject.TYPE_FLOAT,   _("Direction")),
                ]
        self.marker_list = miscwidgets.TreeWidget(cols, 1, parent=False)
        self.marker_list.toggle_cb.append(self.toggle_show)
        self.marker_list.connect("click-on-list", self.make_marker_popup)

        self.marker_list._view.connect("row-activated", self.recenter_cb)

        def render_station(col, rend, model, iter):
            parent = model.iter_parent(iter)
            if not parent:
                parent = iter
            group = model.get_value(parent, 1)
            if group in self.colors:
                rend.set_property("foreground", self.colors[group])

        c = self.marker_list._view.get_column(1)
        c.set_expand(True)
        c.set_min_width(150)
        r = c.get_cell_renderers()[0]
        c.set_cell_data_func(r, render_station)

        def render_coord(col, rend, model, iter, cnum):
            if model.iter_parent(iter):
                rend.set_property('text', "%.4f" % model.get_value(iter, cnum))
            else:
                rend.set_property('text', '')

        for col in [2, 3]:
            c = self.marker_list._view.get_column(col)
            r = c.get_cell_renderers()[0]
            c.set_cell_data_func(r, render_coord, col)

        def render_dist(col, rend, model, iter, cnum):
            if model.iter_parent(iter):
                rend.set_property('text', "%.2f" % model.get_value(iter, cnum))
            else:
                rend.set_property('text', '')

        for col in [4, 5]:
            c = self.marker_list._view.get_column(col)
            r = c.get_cell_renderers()[0]
            c.set_cell_data_func(r, render_dist, col)

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.add(self.marker_list.packable())
        sw.set_size_request(-1, 150)
        sw.show()

        return sw

    def refresh_marker_list(self, group=None):
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
        def toggle(cb, mw):
            mw.tracking_enabled = cb.get_active()

        cb = gtk.CheckButton(_("Track center"))
        cb.connect("toggled", toggle, self)

        cb.show()

        return cb

    def clear_map_cache(self):
        d = gtk.MessageDialog(buttons=gtk.BUTTONS_YES_NO)
        d.set_property("text", _("Are you sure you want to delete all your map files in \n %s\n?" % BASE_DIR))
        r = d.run()
        d.destroy()

        if r == gtk.RESPONSE_YES:
            #dir = os.path.join(dplatform.get_platform().config_dir(), "maps")
            dir = BASE_DIR
            shutil.rmtree(dir, True)
            self.map.queue_draw()

    def printable_map(self, bounds=None):
        p = dplatform.get_platform()

        f = tempfile.NamedTemporaryFile()
        fn = f.name
        f.close()

        mf = "%s.png" % fn
        hf = "%s.html" % fn

        ts = time.strftime("%H:%M:%S %d-%b-%Y")

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
""" % (station_map, generated_at, ts, mf)

        self.map.export_to(mf, bounds)

        f = open(hf, "w")
        f.write(html)
        f.close()

        p.open_html_file(hf)

    def save_map(self, bounds=None):
        p = dplatform.get_platform()
        f = p.gui_save_file(default_name="map_%s.png" % \
                                time.strftime("%m%d%Y%_H%M%S"))
        if not f:
            return

        if not f.endswith(".png"):
            f += ".png"
        self.map.export_to(f, bounds)

    def get_visible_bounds(self):
        ha = self.sw.get_hadjustment()
        va = self.sw.get_vadjustment()

        return (int(ha.value), int(va.value),
                int(ha.value + ha.page_size), int(va.value + va.page_size))

    def mh(self, _action):
        action = _action.get_name()

        if action == "refresh":
            self.map_tiles = []
            self.map.queue_draw()
        elif action == "clearcache":
            self.clear_map_cache()
        elif action == "save":
            self.save_map()
        elif action == "savevis":
            self.save_map(self.get_visible_bounds())          
        elif action == "printable":
            self.printable_map()
        elif action == "printablevis":
            self.printable_map(self.get_visible_bounds())
        elif action == "editsources":
            srced = map_source_editor.MapSourcesEditor(self.config)
            srced.run()
            srced.destroy()
            self.emit("reload-sources")

    def make_menu(self):
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
                   ('clearcache', None, "_" + _("Delete local Map cache"), None, None, self.mh),
                   ('editsources', None, _("Edit Sources"), None, None, self.mh),
         #          ('startmapserver', None, _("Start map server (on google maps layer)"), None, None, self.mh),
                   ('export', None, "_" + _("Export"), None, None, self.mh),
                   ('printable', None, "_" + _("Printable"), "<Control>p", None, self.mh),
                   ('printablevis', None, _("Printable (visible area)"), "<Control><Alt>P", None, self.mh),
                   ('save', None, "_" + _("Save Image"), "<Control>s", None, self.mh),
                   ('savevis', None, _('Save Image (visible area)'), "<Control><Alt>S", None, self.mh),
                   ]

        uim = gtk.UIManager()
        self.menu_ag = gtk.ActionGroup("MenuBar")

        self.menu_ag.add_actions(actions)

        uim.insert_action_group(self.menu_ag, 0)
        menuid = uim.add_ui_from_string(menu_xml)

        self._accel_group = uim.get_accel_group()

        return uim.get_widget("/MenuBar")

    def make_controls(self):
        vbox = gtk.VBox(False, 2)

        vbox.pack_start(self.make_zoom_controls(), 0,0,0)
        vbox.pack_start(self.make_track(), 0,0,0)

        vbox.show()

        return vbox

    def make_bottom_pane(self):
        box = gtk.HBox(False, 2)

        box.pack_start(self.make_marker_list(), 1,1,1)
        box.pack_start(self.make_controls(), 0,0,0)

        box.show()

        return box

    def scroll_to_center(self, widget):
        a = widget.get_vadjustment()
        a.set_value((a.upper - a.page_size) / 2)

        a = widget.get_hadjustment()
        a.set_value((a.upper - a.page_size) / 2)

    def center_on(self, lat, lon):
        ha = self.sw.get_hadjustment()
        va = self.sw.get_vadjustment()

        x, y = self.map.latlon2xy(lat, lon)

        ha.set_value(x - (ha.page_size / 2))
        va.set_value(y - (va.page_size / 2))

    def status(self, frac, message):
        self.sb_prog.set_text(message)
        self.sb_prog.set_fraction(frac)

    def recenter(self, lat, lon):
        self.map.set_center(lat, lon)
        self.map.load_tiles()
        self.refresh_marker_list()
        self.center_on(lat, lon)
        self.map.queue_draw()

    def refresh(self):
        self.map.load_tiles()

    def prompt_to_set_marker(self, point, group=None):
        def do_address(button, latw, lonw, namew):
            dlg = geocode_ui.AddressAssistant()
            r = dlg.run()
            if r == gtk.RESPONSE_OK:
                if not namew.get_text():
                    namew.set_text(dlg.place)
                latw.set_text("%.5f" % dlg.lat)
                lonw.set_text("%.5f" % dlg.lon)

        d = MarkerEditDialog()

        sources = []
        for src in self.map_sources:
            if src.get_mutable():
                sources.append(src.get_name())

        d.set_groups(sources, group)
        d.set_point(point)
        r = d.run()
        if r == gtk.RESPONSE_OK:
            point = d.get_point()
            group = d.get_group()
        d.destroy()

        if r == gtk.RESPONSE_OK:
            return point, group
        else:
            return None, None

    def prompt_to_send_loc(self, _lat, _lon):
        d = inputdialog.FieldDialog(title=_("Broadcast Location"))

        d.add_field(_("Callsign"), gtk.Entry(8))
        d.add_field(_("Description"), gtk.Entry(20))
        d.add_field(_("Latitude"), miscwidgets.LatLonEntry())
        d.add_field(_("Longitude"), miscwidgets.LatLonEntry())
        d.get_field(_("Latitude")).set_text("%.4f" % _lat)
        d.get_field(_("Longitude")).set_text("%.4f" % _lon)

        while d.run() == gtk.RESPONSE_OK:
            try:
                call = d.get_field(_("Callsign")).get_text()
                desc = d.get_field(_("Description")).get_text()
                lat = d.get_field(_("Latitude")).get_text()
                lon = d.get_field(_("Longitude")).get_text()

                fix = GPSPosition(lat=lat, lon=lon, station=call)
                fix.comment = desc

                for port in self.emit("get-station-list").keys():
                    self.emit("user-send-chat",
                              "CQCQCQ", port,
                              fix.to_NMEA_GGA(), True)

                break
            except Exception as e:
                utils.log_exception()
                ed = gtk.MessageDialog(buttons=gtk.BUTTONS_OK, parent=d)
                ed.set_property("text", _("Invalid value") + ": %s" % e)
                ed.run()
                ed.destroy()

        d.destroy()

    def recenter_cb(self, view, path, column, data=None):
        model = view.get_model()
        if model.iter_parent(model.get_iter(path)) == None:
            return

        items = self.marker_list.get_selected()

        self.center_mark = items[1]
        self.recenter(items[2], items[3])

        self.sb_center.pop(self.STATUS_CENTER)
        self.sb_center.push(self.STATUS_CENTER, _("Center") + ": %s" % self.center_mark)

    def make_popup(self, vals):
        def _an(cap):
            return cap.replace(" ", "_")

        xml = ""
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
        ag = gtk.ActionGroup("menu")

        t = gtk.Action("title",
                       "%.4f,%.4f" % (vals["lat"], vals["lon"]),
                       None,
                       None)
        t.set_sensitive(False)
        ag.add_action(t)

        for name, handler in self._popup_items.items():
            action = gtk.Action(_an(name), name, None, None)
            action.connect("activate", handler, vals)
            ag.add_action(action)

        uim = gtk.UIManager()
        uim.insert_action_group(ag, 0)
        uim.add_ui_from_string(xml)

        return uim.get_widget("/menu")

    def mouse_click_event(self, widget, event):
        x,y = event.get_coords()

        ha = widget.get_hadjustment()
        va = widget.get_vadjustment()
        mx = x + int(ha.get_value())
        my = y + int(va.get_value())

        lat, lon = self.map.xy2latlon(mx, my)

        printlog(("Mapdisplay: Button %i at %i,%i" % (event.button, mx, my)))
        if event.button == 3:
            vals = { "lat" : lat,
                     "lon" : lon,
                     "x" : mx,
                     "y" : my }
            menu = self.make_popup(vals)
            if menu:
                menu.popup(None, None, None, event.button, event.time)
        elif event.type == gtk.gdk.BUTTON_PRESS:
            printlog("Mapdisplay",": Clicked: %.4f,%.4f" % (lat, lon))
            # The crosshair marker has been missing since 0.3.0
            #self.set_marker(GPSPosition(station=CROSSHAIR,
            #                            lat=lat, lon=lon))
        elif event.type == gtk.gdk._2BUTTON_PRESS:
            printlog(("Mapdisplay: recenter on %.4f, %.4f" % (lat,lon)))

            self.recenter(lat, lon)

    def mouse_move_event(self, widget, event):
        if not self.__last_motion:
            gobject.timeout_add(100, self._mouse_motion_handler)
        self.__last_motion = (time.time(), event.x, event.y)

    def _mouse_motion_handler(self):
        if self.__last_motion == None:
            return False

        t, x, y = self.__last_motion
        if (time.time() - t) < 0.5:
            self.info_window.hide()
            return True

        lat, lon = self.map.xy2latlon(x, y)

        ha = self.sw.get_hadjustment()
        va = self.sw.get_vadjustment()
        mx = x - int(ha.get_value())
        my = y - int(va.get_value())

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

                dx = abs(x - _x)
                dy = abs(y - _y)

                if dx < 20 and dy < 20:
                    hit = True

                    date = time.ctime(point.get_timestamp())

                    text = "<b>Station:</b> %s" % point.get_name() + \
                        "\n<b>Latitude:</b> %.5f" % point.get_latitude() + \
                        "\n<b>Longitude:</b> %.5f"% point.get_longitude() + \
                        "\n<b>Last update:</b> %s" % date

                    text += "\n<b>Info</b>: %s" % point.get_comment()

                    label = gtk.Label()
                    label.set_markup(text)
                    label.show()
                    for child in self.info_window.get_children():
                        self.info_window.remove(child)
                    self.info_window.add(label)

                    posx, posy = self.get_position()
                    posx += mx + 10
                    posy += my - 10

                    self.info_window.move(int(posx), int(posy))
                    self.info_window.show()

                    break


        if not hit:
            self.info_window.hide()

        self.sb_coords.pop(self.STATUS_COORD)
        self.sb_coords.push(self.STATUS_COORD, "%.4f, %.4f" % (lat, lon))

        self.__last_motion = None

        return False

    def ev_destroy(self, widget, data=None):
        self.hide()
        return True

    def ev_delete(self, widget, event, data=None):
        self.hide()
        return True

    def update_gps_status(self, string):
        self.sb_gps.pop(self.STATUS_GPS)
        self.sb_gps.push(self.STATUS_GPS, string)

    def add_point_visible(self, point):
        if point in self.points_visible:
            self.points_visible.remove(point)

        if self.map.point_is_visible(point.get_latitude(),
                                     point.get_longitude()):
            if point.get_visible():
                self.points_visible.append(point)
                return True
            else:
                return False
        else:
            return False

    def update_point(self, source, point):
        (lat, lon) = self.map.get_center()
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
        except Exception as e:
            if str(e) == "Item not found":
                # this is evil
                printlog("Mapdisplay",": Adding point instead of updating")
                return self.add_point(source, point)

        self.add_point_visible(point)
        self.map.queue_draw()

    def add_point(self, source, point):
        (lat, lon) = self.map.get_center()
        center = GPSPosition(*self.map.get_center())
        this = GPSPosition(point.get_latitude(), point.get_longitude())

        self.marker_list.add_item(source.get_name(),
                                  point.get_visible(), point.get_name(),
                                  point.get_latitude(),
                                  point.get_longitude(),
                                  center.distance_from(this),
                                  center.bearing_to(this))
        self.add_point_visible(point)
        self.map.queue_draw()

    def del_point(self, source, point):
        self.marker_list.del_item(source.get_name(), point.get_name())

        if point in self.points_visible:
            self.points_visible.remove(point)

        self.map.queue_draw()

    def get_map_source(self, name):
        for source in self.get_map_sources():
            if source.get_name() == name:
                return source
        return None

    def add_map_source(self, source):
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
        for src in self.map_sources:
            for point in src.get_points():
                self.update_point(src, point)

        self.map.queue_draw()

    def maybe_recenter_on_updated_point(self, source, point):
        if point.get_name() == self.center_mark and \
                self.tracking_enabled:
            printlog("Mapdisplay",": Center updated")
            self.recenter(point.get_latitude(), point.get_longitude())
        self.update_point(source, point)

    def clear_map_sources(self):
        self.marker_list.clear()
        self.map_sources = []
        self.points_visible = []
        self.update_points_visible()

    def get_map_sources(self):
        return self.map_sources

    def redraw_markers(self, map):
        for point in self.points_visible:
            map.draw_marker(point.get_name(),
                            point.get_latitude(),
                            point.get_longitude(),
                            point.get_icon())

    def __init__(self, config, *args):
   #     gtk.Window.__init__(self, *args)
        gtk.Window.__init__(self,gtk.WINDOW_TOPLEVEL, *args)
        
        # to force open the mapwindow maximized
        # self.maximize()
       
        self.config = config
        
        self.STATUS_COORD = 0
        self.STATUS_CENTER = 1
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
        
        self.map = MapWidget(tiles, tiles, status=self.status)
        self.map.show()
        self.map.connect("redraw-markers", self.redraw_markers)
        self.map.connect("new-tiles-loaded",
                         lambda m: self.update_points_visible())

        box = gtk.VBox(False, 2)

        self.menubar = self.make_menu()
        self.menubar.show()
        box.pack_start(self.menubar, 0,0,0)
        self.add_accel_group(self._accel_group)

        self.sw = gtk.ScrolledWindow()
        self.sw.add_with_viewport(self.map)
        self.sw.show()


        def pre_scale(sw, event, mw):
            ha = mw.sw.get_hadjustment()
            va = mw.sw.get_vadjustment()

            px = ha.get_value() + ha.page_size
            py = va.get_value() + va.page_size

            rect = gtk.gdk.Rectangle(int(ha.get_value()), int(va.get_value()),
                                     int(py), int(py))
            mw.map.window.invalidate_rect(rect, True)

        @utils.run_gtk_locked
        def _scale(sw, event, mw):
            ha = mw.sw.get_hadjustment()
            va = mw.sw.get_vadjustment()

            px = ha.get_value() + ha.page_size
            py = va.get_value() + va.page_size

            pm = mw.map.scale(int(px) - 5, int(py))

        def scale(sw, event, mw):
            gobject.idle_add(_scale, sw, event, mw)

        self.sw.connect("expose-event", pre_scale, self)
        self.sw.connect_after("expose-event", scale, self)

        self.__last_motion = None

        self.map.add_events(gtk.gdk.POINTER_MOTION_MASK)
        self.map.connect("motion-notify-event", self.mouse_move_event)
        self.sw.connect("button-press-event", self.mouse_click_event)

        self.sw.connect('realize', self.scroll_to_center)

        hbox = gtk.HBox(False, 2)

        self.sb_coords = gtk.Statusbar()
        self.sb_coords.show()
        self.sb_coords.set_has_resize_grip(False)

        self.sb_center = gtk.Statusbar()
        self.sb_center.show()
        self.sb_center.set_has_resize_grip(False)

        self.sb_gps = gtk.Statusbar()
        self.sb_gps.show()

        self.sb_prog = gtk.ProgressBar()
        self.sb_prog.set_size_request(150, -1)
        self.sb_prog.show()

        hbox.pack_start(self.sb_coords, 1,1,1)
        hbox.pack_start(self.sb_center, 1,1,1)
        hbox.pack_start(self.sb_prog, 0,0,0)
        hbox.pack_start(self.sb_gps, 1,1,1)
        hbox.show()

        box.pack_start(self.sw, 1,1,1)
        box.pack_start(self.make_bottom_pane(), 0,0,0)
        box.pack_start(hbox, 0,0,0)
        box.show()

        #setup the default dimensions for the map window
        self.set_default_size(800,600)
        
        # commented out this to have the possibility to maximize the mapwindow.
        # dont know why Dan put this originally, maybe removing this will create issues 
        # in some situations... will see
       
        #self.set_geometry_hints(max_width=tiles*256, max_height=tiles*256)

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

        def set_mark_at(a, vals):
            p = map_sources.MapStation("STATION", vals["lat"], vals["lon"])
            p.set_icon_from_aprs_sym("\\<")
            point, group = self.prompt_to_set_marker(p)
            if not point:
                return

            for source in self.map_sources:
                printlog(("Mapdisplay: %s,%s" % (source.get_name(), group)))
                if source.get_name() == group:
                    printlog(("Mapdisplay: Adding new point %s to %s" % (point.get_name(),source.get_name())))
                    source.add_point(point)
                    source.save()
                    return
            # No matching group
            q = "%s %s %s" % \
                (_("Group"), group,
                 _("does not exist.  Do you want to create it?"))
            if not ask_for_confirmation(q):
                return

            s = map_sources.MapFileSource.open_source_by_name(self.config,
                                                              group,
                                                              True)
            s.add_point(point)
            s.save()
            self.add_map_source(s)

        self.add_popup_handler(_("New marker here"), set_mark_at)
        self.add_popup_handler(_("Broadcast this location"),
                               lambda a, vals:
                                   self.prompt_to_send_loc(vals["lat"],
                                                           vals["lon"]))

        # create the INFO WINDOW which is shown over the map clicking the left mouse button       
        self.info_window = gtk.Window(gtk.WINDOW_POPUP)
        self.info_window.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_MENU)     
        self.info_window.set_decorated(False)
        self.info_window.modify_bg(gtk.STATE_NORMAL,
                                   gtk.gdk.color_parse("yellow"))

    def add_popup_handler(self, name, handler):
        self._popup_items[name] = handler

    def set_zoom(self, zoom):
        self.map.set_zoom(zoom)

    def set_center(self, lat, lon):
        self.map.set_center(lat, lon)


def main():
    '''Main program for unit testing'''

    printlog("Mapdisplay",": __Executing __main__ section")
    import sys
    from . import gps
    from . import config

    # WB8TYW: DratsConfig takes an unused argument.
    conf = config.DratsConfig(None)

    mapurl = conf.get("settings", "mapurlbase")
    mapkey = ""

    set_connected(True)
    set_tile_lifetime(conf.getint("settings","map_tile_ttl") * 3600)


    set_base_dir(os.path.join(conf.get("settings", "mapdir"),
                 conf.get("settings", "maptype")), mapurl, mapkey)
    proxy = conf.get("settings", "http_proxy") or None
    set_proxy(proxy)

    if len(sys.argv) == 3:
        m = MapWindow(conf)
        m.set_center(gps.parse_dms(sys.argv[1]),
                     gps.parse_dms(sys.argv[2]))
        m.set_zoom(15)
    else:
        m = MapWindow(config)
        m.set_center(45.525012, -122.916434)
        m.set_zoom(14)

        # m.set_marker(GPSPosition(station="KI4IFW_H", lat=45.520, lon=-122.916434))
        # m.set_marker(GPSPosition(station="KE7FTE", lat=45.5363, lon=-122.9105))
        # m.set_marker(GPSPosition(station="KA7VQH", lat=45.4846, lon=-122.8278))
        # m.set_marker(GPSPosition(station="N7QQU", lat=45.5625, lon=-122.8645))
        # m.del_marker("N7QQU")

    m.show()

    try:   
        gtk.main()
    except:
        pass

if __name__ == "__main__":
    main()
