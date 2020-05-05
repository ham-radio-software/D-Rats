#!/usr/bin/python
#
# Copyright 2009 Dan Smith <dsmith@danplanet.com>
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

import time
import threading
import os
from glob import glob

import libxml2
import gobject

import utils
import dplatform

class Callable:
    def __init__(self, target):
        self.__call__ = target

class MapItem(object):
    pass

class MapPoint(gobject.GObject):
    __gsignals__ = {
        "updated" : (gobject.SIGNAL_RUN_LAST,
                     gobject.TYPE_NONE,
                     (gobject.TYPE_STRING,)),
        }

    def _retr_hook(self, method, attribute):
        pass

    def __init__(self):
        gobject.GObject.__init__(self)
        self.__latitude = 0.0
        self.__longitude = 0.0
        self.__altitude = 0.0
        self.__name = ""
        self.__comment = ""
        self.__icon = None
        self.__timestamp = time.time()
        self.__visible = True

    def dup(self):
        p = MapPoint()

        for i in ["latitude", "longitude", "altitude", "name",
                  "comment", "icon", "timestamp", "visible"]:
            k = "_MapPoint__" + i
            p.__dict__[k] = self.__dict__[k]

        return p

    def __getattr__(self, name):
        _get, name = name.split("_", 1)

        self._retr_hook(_get, name)

        attrname = "_MapPoint__%s" % name

        #print self.__dict__.keys()
        if not hasattr(self, attrname):
            raise ValueError("No such attribute `%s'" % attrname)

        def get():
            return self.__dict__[attrname]

        def set(val):
            self.__dict__[attrname] = val

        if _get == "get":
            return get
        elif _get == "set":
            return set
        else:
            pass

    def __repr__(self):
        msg = "%s@%.4f,%.4f" % (self.get_name(),
                                self.get_latitude(),
                                self.get_longitude())
        return msg

    def __str__(self):
        return self.get_name()

    def __eq__(self, point):
        return self.get_name() == point.get_name()

class MapStation(MapPoint):
    def __init__(self, call, lat, lon, alt=0.0, comment=""):
        MapPoint.__init__(self)
        self.set_latitude(lat)
        self.set_longitude(lon)
        self.set_altitude(alt)
        self.set_name(call)
        self.set_comment(comment)
        self._aprs_sym = ""
        # FIXME: Set icon from DPRS comment

    def set_icon_from_aprs_sym(self, symbol):
        self.set_icon(utils.get_icon(symbol))
        self._aprs_sym = symbol

    def get_aprs_symbol(self):
        return self._aprs_sym

def _xdoc_getnodeval(ctx, nodespec):
    items = ctx.xpathEval(nodespec)
    if len(items) == 0:
        raise Exception("No data for %s" % nodespec)
    if len(items) > 1:
        raise Exception("Too many nodes")

    return items[0].getContent()

class MapPointThreaded(MapPoint):
    def __init__(self):
        MapPoint.__init__(self)

        self.__thread = None
        self.__ts = 0

    def __start_thread(self):
        if self.__thread and self.__thread.isAlive():
            print "Threaded Point: Still waiting on a thread"
            return

        self.__thread = threading.Thread(target=self.__thread_fn)
        self.__thread.setDaemon(True)
        self.__thread.start()

    def _retr_hook(self, method, attribute):
        if time.time() - self.__ts > 60:
            try:
                self.__ts = time.time()
                self.__start_thread()
            except Exception, e:
                print "Can't start: %s" % e

    def __thread_fn(self):
        self.do_update()
        gobject.idle_add(self.emit, "updated", "FOO")

class MapUSGSRiver(MapPointThreaded):
    def do_update(self):
        print "[River %s] Doing update..." % self.__site
        if  not self.__have_site:
            try:
                self.__parse_site()
                self.__have_site = True
            except Exception, e:
                utils.log_exception()
                print "[River %s] Failed to parse site: %s" % (self.__site, e)
                self.set_name("Invalid river %s" % self.__site)

        try:
            self.__parse_level()
        except Exception, e:
            utils.log_exception()
            print "[River %s] Failed to parse level: %s" % (self.__site, e)

        print "[River %s] Done with update" % self.__site

    def __parse_site(self):
        url = "http://waterdata.usgs.gov/nwis/inventory?search_site_no=%s&format=sitefile_output&sitefile_output_format=xml&column_name=agency_cd&column_name=site_no&column_name=station_nm&column_name=dec_lat_va&column_name=dec_long_va&column_name=alt_va" % self.__site

        p = dplatform.get_platform()
        try:
            fn, headers = p.retrieve_url(url)
            content = file(fn).read()
        except Exception, e:
            print "[NSGS] Failed to fetch info for %s: %s" % (self.__site, e)
            self.set_name("NSGS NWIS Site %s" % self.__site)
            return

        doc = libxml2.parseMemory(content, len(content))

        ctx = doc.xpathNewContext()

        base = "/usgs_nwis/site/"

        self._basename = _xdoc_getnodeval(ctx, base + "station_nm")

        self.set_name(self._basename)
        self.set_latitude(float(_xdoc_getnodeval(ctx, base + "dec_lat_va")))
        self.set_longitude(float(_xdoc_getnodeval(ctx, base + "dec_long_va")))
        self.set_altitude(float(_xdoc_getnodeval(ctx, base + "alt_va")))

    def __parse_level(self):
        url = "http://waterdata.usgs.gov/nwis/uv?format=rdb&period=1&site_no=%s" % self.__site

        p = dplatform.get_platform()
        try:
            fn, headers = p.retrieve_url(url)
            line = file(fn).readlines()[-1]
        except Exception, e:
            print "[NSGS] Failed to fetch info for site %s: %s" % (self.__site,
                                                                   e)
            self.set_comment("No data")
            self.set_timestamp(time.time())

            return

        fields = line.split("\t")

        self._height_ft = float(fields[3])
        self.set_comment("River height: %.1f ft" % self._height_ft)
        self.set_timestamp(time.time())

    def __init__(self, site):
        MapPointThreaded.__init__(self)
        self.__site = site
        self.__have_site = False

        self.set_icon(utils.get_icon("/w"))

class MapNBDCBuoy(MapPointThreaded):
    def do_update(self):
        p = dplatform.get_platform()
        try:
            fn, headers = p.retrieve_url(self.__url)
            content = file(fn).read()
        except Exception, e:
            print "[NBDC] Failed to fetch info for %i: %s" % (self.__buoy, e)
            self.set_name("NBDC %s" % self.__buoy)
            return

        try:
            doc = libxml2.parseMemory(content, len(content))
        except Exception, e:
            print "[NBDC] Failed to parse document %s: %s" % (self.__url, e)
            self.set_name("NBDC Unknown Buoy %s" % self.__buoy)
            return

        ctx = doc.xpathNewContext()
        ctx.xpathRegisterNs("georss", "http://www.georss.org/georss")
        base = "/rss/channel/item/"

        self.set_name(_xdoc_getnodeval(ctx, base + "title"))

        try:
            s = _xdoc_getnodeval(ctx, base + "description")
        except Exception, e:
            print "[Buoy %s] Unable to get description: %s" % (self.__buoy, e)
            return

        for i in ["<strong>", "</strong>", "<br />", "&#176;"]:
            s = s.replace("%s" % i, "")
        self.set_comment(s)
        self.set_timestamp(time.time())

        try:
            slat, slon = _xdoc_getnodeval(ctx, base + "georss:point").split(" ", 1)
        except Exception, e:
            utils.log_exception()
            print "[Buoy %s]: Result has no georss:point" % self.__buoy
            return

        self.set_latitude(float(slat))
        self.set_longitude(float(slon))

        print "[Buoy %s] Done with update" % self.__buoy

    def __init__(self, buoy):
        MapPointThreaded.__init__(self)

        self.__buoy = buoy
        self.__url = "http://www.ndbc.noaa.gov/data/latest_obs/%s.rss" % buoy
        
        self.set_icon(utils.get_icon("\\N"))

class MapSourceFailedToConnect(Exception):
    pass

class MapSourcePointError(Exception):
    pass

class MapSource(gobject.GObject):
    __gsignals__ = {
        "point-added" : (gobject.SIGNAL_RUN_LAST,
                         gobject.TYPE_NONE,
                         (gobject.TYPE_PYOBJECT,)),
        "point-deleted" : (gobject.SIGNAL_RUN_LAST,
                           gobject.TYPE_NONE,
                           (gobject.TYPE_PYOBJECT,)),
        "point-updated" : (gobject.SIGNAL_RUN_LAST,
                           gobject.TYPE_NONE,
                           (gobject.TYPE_PYOBJECT,)),
        }

    def __init__(self, name, description, color="red"):
        gobject.GObject.__init__(self)

        self._name = name
        self._description = description
        self._points = {}
        self._color = color
        self._visible = True
        self._mutable = True

    def save(self):
        pass

    def add_point(self, point):
        had = self._points.has_key(point.get_name())
        self._points[point.get_name()] = point
        if had:
            self.emit("point-updated", point)
        else:
            self.emit("point-added", point)

    def del_point(self, point):
        del self._points[point.get_name()]
        self.emit("point-deleted", point)

    def get_points(self):
        return self._points.values()

    def get_point_by_name(self, name):
        return self._points[name]

    def get_color(self):
        return self._color

    def get_name(self):
        return self._name

    def set_name(self, name):
        self._name = name

    def get_description(self):
        return self._description

    def get_visible(self):
        return self._visible

    def set_visible(self, visible):
        self._visible = visible

    def get_mutable(self):
        return self._mutable

class MapFileSource(MapSource):
    def _enumerate(config):
        dirpath = os.path.join(config.platform.config_dir(),
                               "static_locations")
        files = glob(os.path.join(dirpath, "*.*"))
        
        return [os.path.splitext(os.path.basename(f))[0] for f in files]

    enumerate = Callable(_enumerate)

    def _open_source_by_name(config, name, create=False):
        dirpath = os.path.join(config.platform.config_dir(),
                               "static_locations")

        path = os.path.join(dirpath, "%s.csv" % name)

        if create and not os.path.exists(path):
            f = file(path, "a").close()

        return MapFileSource(name, "Static file", path)

    open_source_by_name = Callable(_open_source_by_name)

    def __parse_line(self, line):
        try:
            id, icon, lat, lon, alt, comment, show = line.split(",", 6)
        except Exception, e:
            raise MapSourcePointError(str(e))
        
        if alt:
            alt = float(alt)
        else:
            alt = 0.0

        point = MapStation(id, float(lat), float(lon), float(alt), comment)
        point.set_visible(show.upper().strip() == "TRUE")
        if icon and icon != "None":
            point.set_icon_from_aprs_sym(icon)

        return point

    def save(self):
        self._need_save = 0
        f = file(self._fn, "w")

        for point in self.get_points():
            f.write("%s,%s,%f,%f,%f,%s,%s%s" % (point.get_name(),
                                                point.get_aprs_symbol(),
                                                point.get_latitude(),
                                                point.get_longitude(),
                                                point.get_altitude(),
                                                point.get_comment(),
                                                point.get_visible(),
                                                os.linesep))
        f.close()                  

    def __init__(self, name, description, fn, create=False):
        MapSource.__init__(self, name, description)

        self._fn = fn

        self.__need_save = 0

        try:
            input = file(fn)
        except Exception, e:
            msg = "Failed to open %s: %s" % (fn, e)
            print msg
            raise MapSourceFailedToConnect(msg)

        lines = input.readlines()
        for line in lines:
            try:
                point = self.__parse_line(line)
            except Exception, e:
                print "Failed to parse: %s" % e
                continue

            self._points[point.get_name()] = point

    def get_filename(self):
        return self._fn

class MapUSGSRiverSource(MapSource):
    def _open_source_by_name(config, name):
        if not config.has_section("rivers"):
            return None
        if not config.has_option("rivers", name):
            return None
        sites = tuple(config.get("rivers", name).split(","))
        try:
            _name = config.get("rivers", "%s.label" % name)
        except Exception, e:
            print "No option %s.label" % name
            print e
            _name = name

        return MapUSGSRiverSource(_name, "NWIS Rivers", *sites)

    open_source_by_name = Callable(_open_source_by_name)

    def _enumerate(config):
        if not config.has_section("rivers"):
            return []
        options = config.options("rivers")

        return [x for x in options if not x.endswith(".label")]

    enumerate = Callable(_enumerate)

    def packed_name(self):
        name = []
        for i in self.get_name():
            if (ord(i) > ord("A") and ord(i) < ord("Z")) or\
                    (ord(i) > ord("a") and ord(i) < ord("z")):
                name.append(i)

        return "".join(name)

    def _point_updated(self, point, foo):
        if not self._points.has_key(point.get_name()):
            self._points[point.get_name()] = point
            self.emit("point-added", point)
        else:
            self.emit("point-updated", point)

    def __init__(self, name, description, *sites):
        MapSource.__init__(self, name, description)

        self.__sites = sites
        self._mutable = False

        for site in sites:
            point = MapUSGSRiver(site)
            point.connect("updated", self._point_updated)

    def get_sites(self):
        return self.__sites

class MapNBDCBuoySource(MapSource):
    def _open_source_by_name(config, name):
        if not config.has_section("buoys"):
            return None
        if not config.has_option("buoys", name):
            return None
        _sites = config.get("buoys", name).split(",")
        try:
            _name = config.get("buoys", "%s.label" % name)
        except Exception, e:
            print "No option %s.label" % name
            print e
            _name = name
        sites = tuple([x for x in _sites])

        return MapNBDCBuoySource(_name, "NBDC Buoys", *sites)

    open_source_by_name = Callable(_open_source_by_name)

    def _enumerate(config):
        if not config.has_section("buoys"):
            return []
        options = config.options("buoys")

        return [x for x in options if not x.endswith(".label")]

    enumerate = Callable(_enumerate)

    def packed_name(self):
        name = []
        for i in self.get_name():
            if (ord(i) > ord("A") and ord(i) < ord("Z")) or\
                    (ord(i) > ord("a") and ord(i) < ord("z")):
                name.append(i)

        return "".join(name)

    def _point_updated(self, point, foo):
        if not self._points.has_key(point.get_name()):
            self._points[point.get_name()] = point
            self.emit("point-added", point)
        else:
            self.emit("point-updated", point)

    def __init__(self, name, description, *buoys):
        MapSource.__init__(self, name, description)

        self.__buoys = buoys
        self._mutable = False

        for buoy in buoys:
            point = MapNBDCBuoy(buoy)
            point.connect("updated", self._point_updated)

    def get_buoys(self):
        return self.__buoys

