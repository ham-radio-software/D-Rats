#!/usr/bin/python
'''Map Sources'''
#
# Copyright 2009 Dan Smith <dsmith@danplanet.com>
# Copyright 2022 John. E. Malmberg - Python3 Conversion
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
import re
import time
import threading
import os
import urllib
from glob import glob
from lxml import etree
from six.moves.configparser import NoSectionError # type: ignore
from six.moves.configparser import NoOptionError # type: ignore

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GObject

from . import utils
from . import dplatform


class MapSourcesException(Exception):
    '''Generic Map Source Exception.'''


class MapStationException(MapSourcesException):
    '''Generic MapSources.MapStation Exception.'''


class MapStationDataError(MapStationException):
    '''Map Station Data Error.'''


class MapStationNodeError(MapStationException):
    '''Map Station Node Error.'''


class MapSourceException(MapSourcesException):
    '''Generic Mapsources.mapsource Exception.'''


class MapSourceFailedToConnect(MapSourceException):
    '''MapSourceFailedToConnect.'''


class MapSourcePointError(MapSourceException):
    '''MapSourcePointError.'''


# pylint: disable=too-few-public-methods
class MapItem():
    '''MapItem.'''


# pylint: disable=too-many-instance-attributes
class MapPoint(GObject.GObject):
    '''MapPoint.'''

    __gsignals__ = {
        "updated" : (GObject.SignalFlags.RUN_LAST,
                     GObject.TYPE_NONE,
                     (GObject.TYPE_STRING,)),
        }

    def __init__(self):
        GObject.GObject.__init__(self)
        self.__latitude = 0.0
        self.__longitude = 0.0
        self.__altitude = 0.0
        self.__name = ""
        self.__comment = ""
        self.__icon = None
        self.__timestamp = time.time()
        self.__visible = True

    def _retr_hook(self, method, attribute):
        pass

    def dup(self):
        '''
        Duplicate a MapPoint.

        :returns: Copy of this object
        :rtype: :class:`MapPoint`
        '''
        point = MapPoint()

        for i in ["latitude", "longitude", "altitude", "name",
                  "comment", "icon", "timestamp", "visible"]:
            k = "_MapPoint__" + i
            point.__dict__[k] = self.__dict__[k]

        return point

    def __getattr__(self, name):
        _get, name = name.split("_", 1)

        self._retr_hook(_get, name)

        attrname = "_MapPoint__%s" % name

        if not hasattr(self, attrname):
            raise ValueError("No such attribute `%s'" % attrname)

        def get():
            return self.__dict__[attrname]

        # pylint: disable=redefined-builtin
        def set(val):
            self.__dict__[attrname] = val

        if _get == "get":
            return get
        if _get == "set":
            return set
        # Probably should raise an exception
        return None

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
    '''
    Map Station.

    :param call: Call sign for station
    :type call: str
    :param lat: Latitude for station
    :type lat: float
    :param lon: Longitude for station
    :type lon: float
    :param alt: Altitude for station, default 0.0
    :type alt: float
    :param comment: Comment for station, default ""
    :type comment: str
    '''

    # pylint: disable=too-many-arguments
    def __init__(self, call, lat, lon, alt=0.0, comment=""):
        MapPoint.__init__(self)
        self.set_latitude(lat)
        self.set_longitude(lon)
        self.set_altitude(alt)
        self.set_name(call)
        self.set_comment(comment)
        self._aprs_sym = ""
        # pylint: disable=fixme
        # FIXME: Set icon from DPRS comment

    def set_icon_from_aprs_sym(self, symbol):
        '''
        Set Icon From APRS symbol.

        :param symbol: Symbol to set icon
        '''
        self.set_icon(utils.get_icon(symbol))
        self._aprs_sym = symbol

    def get_aprs_symbol(self):
        '''
        Get Aprs Symbol.

        :returns: APRS symbol
        '''
        return self._aprs_sym


def _xdoc_getnodeval(doc, nodespec, namespaces=None):
    '''
    XDOC Get node value.

    :param doc: Source document
    :type doc: :class:`etree._Element`
    :param nodespec: node to look up
    :type nodespec: str
    :param namespaces: Name space data
    :type namespaces: dict
    :raises: :class:`MapStationDataError` if no items found
    :raises: :class:`MapStationNodeError` if node is not unique
    :returns: requested content
    :rtype: str
    '''
    items = doc.xpath(nodespec, namespaces=namespaces)
    if not items:
        raise MapStationDataError("No data for %s" % nodespec)
    if len(items) > 1:
        raise MapStationNodeError("Too many nodes")

    return items[0].text


class MapPointThreaded(MapPoint):
    '''Map Point Threaded.'''

    def __init__(self):
        MapPoint.__init__(self)

        self.logger = logging.getLogger("MapPointThreaded")
        self.__thread = None
        self.__ts = 0

    def __start_thread(self):
        if self.__thread and self.__thread.isAlive():
            self.logger.info("Threaded Point: Still waiting on a thread")
            return

        self.__thread = threading.Thread(target=self.__thread_fn)
        self.__thread.setDaemon(True)
        self.__thread.start()

    def _retr_hook(self, method, attribute):
        if time.time() - self.__ts > 60:
            try:
                self.__ts = time.time()
                self.__start_thread()
            # pylint: disable=broad-except
            except Exception:
                self.logger.info("_retr_hook: Can't start", exc_info=True)

    def __thread_fn(self):
        self.do_update()
        GObject.idle_add(self.emit, "updated", "FOO")


class MapUSGSRiver(MapPointThreaded):
    '''
    Map USGS River.

    :param site: Site information.
    '''

    def __init__(self, site):
        MapPointThreaded.__init__(self)
        self.logger = logging.getLogger("MapUSGSRiver")
        self.__site = site
        self.__have_site = False
        self._height_ft = None
        self._basename = None

        self.set_icon(utils.get_icon("/w"))

    def do_update(self):
        '''Do update.'''
        self.logger.info("[River %s] Doing update...", self.__site)
        if  not self.__have_site:
            try:
                self.__parse_site()
                self.__have_site = True
            # pylint: disable=broad-except
            except Exception:
                utils.log_exception()
                self.logger.info("do_update: [River %s] Failed to parse site",
                                 self.__site, exc_info=True)
                self.set_name("Invalid river %s" % self.__site)

        try:
            self.__parse_level()
        # pylint: disable=broad-except
        except Exception:
            utils.log_exception()
            self.logger.info("do_update: [River %s] Failed to parse level",
                             self.__site, exc_info=True)

        self.logger.info("do_update: [River %s] Done with update", self.__site)

    def __parse_site(self):
        url = "http://waterservices.usgs.gov/nwis/site/" \
              "?format=mapper&sites=%s&siteOutput=expanded&siteStatus=all" % \
              self.__site

        platform = dplatform.get_platform()
        try:
            filter_filename, _headers = platform.retrieve_url(url)
            content = open(filter_filename).read()
        except urllib.error.HTTPError as err:
            self.set_name("NSGS NWIS Site %s" % self.__site)
            if err.code == 400:
                self.logger.info("__parse_site [NSGS] Failed %s: %s %s",
                                 self.__site, err.code, err.reason)
                return
            self.logger.info("__parse_site [NSGS] Failed to fetch info for %s",
                             self.__site, exc_info=True)
            return

        pattern = r'encoding="UTF-8"'
        content = re.sub(pattern, '', content)
        doc = etree.fromstring(content)

        sites = doc[0]
        site = sites[0]
        self.set_name(site.get('sna'))
        self.set_latitude(float(site.get('lat')))
        self.set_longitude(float(site.get('lng')))

    def __parse_level(self):
        url = \
            "http://waterdata.usgs.gov/nwis/uv?format=rdb&period=1&site_no=%s" \
            % self.__site

        platform = dplatform.get_platform()
        try:
            file_name, _headers = platform.retrieve_url(url)
            line = open(file_name).readlines()[-1]
        except urllib.error.HTTPError as err:
            self.set_comment("No data")
            self.set_timestamp(time.time())
            if err.code == 400:
                self.logger.info("__parse_level: [NSGS] Failed %s: %s %s",
                                 self.__site, err.code, err.reason)
                return
            self.logger.info("__parse_level: [NSGS] Failed to fetch "
                             "info for site %s",
                             self.__site, exc_info=True)
            return

        fields = line.split("\t")

        self._height_ft = float(fields[4])
        self.set_comment("River height: %.1f ft" % self._height_ft)
        self.set_timestamp(time.time())


class MapNBDCBuoy(MapPointThreaded):
    '''
    Map NBDC Buoy.

    :param buoy: Buoy information
    '''

    def __init__(self, buoy):
        MapPointThreaded.__init__(self)
        self.logger = logging.getLogger("MapNBDCBuoy")
        self.__buoy = buoy
        self.__url = "http://www.ndbc.noaa.gov/data/latest_obs/%s.rss" % buoy

        self.set_icon(utils.get_icon("\\N"))

    def do_update(self):
        '''Do Update.'''
        platform = dplatform.get_platform()
        try:
            fname, _headers = platform.retrieve_url(self.__url)
            content = open(fname).read()
        except urllib.error.HTTPError as err:
            self.set_name("NBDC %s" % self.__buoy)
            if err.code == 400:
                self.logger.info("do_update: [NBDC] Failed %s: %s %s",
                                 self.__buoy, err.code, err.reason)
                return
            self.logger.info("do_update: [NBDC] Failed to fetch info for %s",
                             self.__buoy, exc_info=True)
            return

        try:
            doc = etree.fromstring(content)
        except (etree.ParseError, etree.ParserError):
            self.logger.info("do_update: [NBDC] Failed to parse document %s",
                             self.__url, exc_info=True)
            self.set_name("NBDC Unknown Buoy %s" % self.__buoy)
            return

        namespaces = {'georss': 'http://www.georss.org/georss'}
        base = "/rss/channel/item/"

        self.set_name(_xdoc_getnodeval(doc, base + "title", namespaces))

        try:
            descrip = _xdoc_getnodeval(doc, base + "description", namespaces)
        except MapStationException:
            self.logger.info("do_update :[Buoy %s] Unable to get description",
                             self.__buoy, exc_info=True)
            return

        for i in ["<strong>", "</strong>", "<br />", "&#176;"]:
            descrip = descrip.replace("%s" % i, "")
        self.set_comment(descrip)
        self.set_timestamp(time.time())

        try:
            slat, slon = _xdoc_getnodeval(doc,
                                          base + "georss:point",
                                          namespaces).split(" ", 1)
        except MapStationException:
            utils.log_exception()
            self.logger.info("do_update: [Buoy %s]: Result has no georss:point",
                             self.__buoy, exc_info=True)
            return

        self.set_latitude(float(slat))
        self.set_longitude(float(slon))

        self.logger.info("do_update: [Buoy %s] Done with update", self.__buoy)


class MapSource(GObject.GObject):
    '''
    MapSource.

    :param name: Map source name
    :type name: str
    :param description: Map source description
    :type description: str
    :param color: Color of map source, default "red"
    :type color: str
    '''

    __gsignals__ = {
        "point-added" : (GObject.SignalFlags.RUN_LAST,
                         GObject.TYPE_NONE,
                         (GObject.TYPE_PYOBJECT,)),
        "point-deleted" : (GObject.SignalFlags.RUN_LAST,
                           GObject.TYPE_NONE,
                           (GObject.TYPE_PYOBJECT,)),
        "point-updated" : (GObject.SignalFlags.RUN_LAST,
                           GObject.TYPE_NONE,
                           (GObject.TYPE_PYOBJECT,)),
        }

    def __init__(self, name, description, color="red"):
        GObject.GObject.__init__(self)

        self._name = name
        self._description = description
        self._points = {}
        self._color = color
        self._visible = True
        self._mutable = True

    def save(self):
        '''Save.'''

    def add_point(self, point):
        '''
        Add Point.

        :param point: Point to add
        :type point: :class:`MapPoint`
        '''
        had = point.get_name() in self._points
        self._points[point.get_name()] = point
        if had:
            self.emit("point-updated", point)
        else:
            self.emit("point-added", point)

    def del_point(self, point):
        '''
        Delete Point.

        :param point: Point to delete
        :type point: :class:`MapPoint`
        '''
        del self._points[point.get_name()]
        self.emit("point-deleted", point)

    def get_points(self):
        '''
        Get Points.

        :returns: List of points
        :rtype: list of :class:`MapPoint`
        '''
        return list(self._points.values())

    def get_point_by_name(self, name):
        '''
        Get Point by Name.

        :param name: Name of point
        :returns: Point data
        :rtype: :class:`MapPoint`
        '''
        return self._points[name]

    def get_color(self):
        '''
        Get Color.

        :returns: Color property
        :rtype: str
        '''
        return self._color

    def get_name(self):
        '''
        Get Name.

        :returns: Name
        :rtype: str
        '''
        return self._name

    def set_name(self, name):
        '''
        Set Name.

        :param name: Name of source
        :type name: str
        '''
        self._name = name

    def get_description(self):
        '''
        Get Description.

        :returns: Description
        :rtype: str
        '''
        return self._description

    def get_visible(self):
        '''
        Get Visible.

        :returns: Visible state
        :rtype: bool
        '''
        return self._visible

    def set_visible(self, visible):
        '''
        Set Visible.

        :param visible: Visible state
        :type visible: bool
        '''
        self._visible = visible

    def get_mutable(self):
        '''
        Get Mutable.

        :returns: Mutable state
        :rtype: bool
        '''
        return self._mutable


class MapFileSource(MapSource):
    '''
    MapFileSource.

    :param name: Name of map source
    :type name: str
    :param description: Description of map source
    :type description: str
    :param filename: Map source filename
    :type filename: str
    :param _create: Unused default to False
    :type _create: bool
    '''

    def __init__(self, name, description, filename, _create=False):
        MapSource.__init__(self, name, description)

        self.logger = logging.getLogger("MapFileSource")
        self._fn = filename

        self._need_save = 0

        try:
            input_handle = open(filename)
        except (PermissionError, FileNotFoundError) as err:
            msg = "Failed to open %s: %s" % (filename, err)
            self.logger.info("Failed to open %s: %s")
            raise MapSourceFailedToConnect(msg)

        lines = input_handle.readlines()
        for line in lines:
            try:
                point = self.__parse_line(line)
            except MapSourcePointError:
                continue

            self._points[point.get_name()] = point

    @staticmethod
    def enumerate(config):
        '''
        Enumerate.

        :param config: Configuration data
        :type config: :class:`DratsConfig`
        :returns: list of matching files
        :rtype: list of str
        '''
        # pylint: disable=no-member
        dirpath = os.path.join(config.platform.config_dir(),
                               "static_locations")
        files = glob(os.path.join(dirpath, "*.*"))

        return [os.path.splitext(os.path.basename(f))[0] for f in files]

    @staticmethod
    def open_source_by_name(config, name, create=False):
        '''
        Open Source By Name.

        :param config: Configuration data
        :type config: :class:`DratsConfig`
        :param name: Name of map source
        :type name: str
        :param create: Flag to create a source, default False
        :type create: bool
        :returns: filenames for sources
        :rtype: list of str
        '''
        # pylint: disable=no-member
        dirpath = os.path.join(config.platform.config_dir(),
                               "static_locations")

        path = os.path.join(dirpath, "%s.csv" % name)
        if create and not os.path.exists(path):
            _file_handle = open(path, "a").close()

        return MapFileSource(name, "Static file", path)

    # open_source_by_name = Callable(_open_source_by_name)
    def __parse_line(self, line):

        try:
            ident, icon, lat, lon, alt, comment, show = line.split(",", 6)
        except ValueError:
            self.logger.info("parse_line failed (%s)")
            raise MapSourcePointError

        if alt:
            alt = float(alt)
        else:
            alt = 0.0

        point = MapStation(ident, float(lat), float(lon), float(alt), comment)
        point.set_visible(show.upper().strip() == "TRUE")
        if icon and icon != "None":
            point.set_icon_from_aprs_sym(icon)

        return point

    def save(self):
        '''Save.'''
        self._need_save = 0
        handle = open(self._fn, "w")

        for point in self.get_points():
            handle.write("%s,%s,%f,%f,%f,%s,%s%s" % (point.get_name(),
                                                     point.get_aprs_symbol(),
                                                     point.get_latitude(),
                                                     point.get_longitude(),
                                                     point.get_altitude(),
                                                     point.get_comment(),
                                                     point.get_visible(),
                                                     os.linesep))
        handle.close()

    def get_filename(self):
        '''Get Filename'''
        return self._fn


class MapUSGSRiverSource(MapSource):
    '''
    Map USGS River Source.

    :param name: Map source name
    :type name: str
    :param description: Map source description
    :type description: str
    :param sites: Optional site information
    :type sites: str
    '''

    def __init__(self, name, description, *sites):
        MapSource.__init__(self, name, description)

        self.__sites = sites
        self._mutable = False
        for site in sites:
            if site:
                point = MapUSGSRiver(site)
                point.connect("updated", self._point_updated)

    @staticmethod
    def open_source_by_name(config, name, _create=False):
        '''
        Open Source By Name.

        :param config: Configuration data
        :type config: :class:`DratsConfig`
        :param name: Name of map source
        :type name: str
        :param _create: Flag to create a source, default False, Unused
        :type _create: bool
        :returns: filenames for sources
        :rtype: list of str
        '''
        # pylint: disable=no-member
        if not config.has_section("rivers"):
            return None
        # pylint: disable=no-member
        if not config.has_option("rivers", name):
            return None
        # pylint: disable=no-member
        sites = tuple(config.get("rivers", name).split(","))
        try:
            # pylint: disable=no-member
            _name = config.get("rivers", "%s.label" % name)
        except (NoSectionError, NoOptionError):
            logger = logging.getLogger("MapUSGSRiverSource_static:")
            logger.info("_open_source_by_name: No option %s.label",
                        name, exc_info=True)
            _name = name

        return MapUSGSRiverSource(_name, "NWIS Rivers", *sites)

    @staticmethod
    def enumerate(config):
        '''
        Enumerate.

        :param config: Configuration data
        :type config: :class:`DratsConfig`
        :returns: filenames for sources
        :rtype: list of str
        '''
          # pylint: disable=no-member
        if not config.has_section("rivers"):
            return []
        # pylint: disable=no-member
        options = config.options("rivers")

        return [x for x in options if not x.endswith(".label")]

    def packed_name(self):
        '''
        Packed Name.

        :returns: fixed up or packed name
        :rtype: str
        '''
        name = []
        for i in self.get_name():
            if (ord(i) > ord("A") and ord(i) < ord("Z")) or\
                    (ord(i) > ord("a") and ord(i) < ord("z")):
                name.append(i)

        return "".join(name)

    def _point_updated(self, point, _unused):
        if point.get_name() not in self._points:
            self._points[point.get_name()] = point
            self.emit("point-added", point)
        else:
            self.emit("point-updated", point)

    def get_sites(self):
        '''
        Get Sites.

        :returns: sites for source
        :rtype: str
        '''
        return self.__sites


class MapNBDCBuoySource(MapSource):
    '''
    Map NBDC Buoy Source.

    :param name: Name of source
    :type name: str
    :param description: Description of source
    :type description: str
    :param *buoys: Optional buoy information
    '''

    def __init__(self, name, description, *buoys):
        MapSource.__init__(self, name, description)

        self.__buoys = buoys
        self._mutable = False

        for buoy in buoys:
            point = MapNBDCBuoy(buoy)
            point.connect("updated", self._point_updated)

    @staticmethod
    def open_source_by_name(config, name, _create=False):
        '''
        Open Source By Name.

        :param config: Configuration data
        :type config: :class:`DratsConfig`
        :param name: Name of map source
        :type name: str
        :param _create: Flag to create a source, default False, Unused
        :type _create: bool
        :returns: filenames for sources
        :rtype: list of str
        '''
        # pylint: disable=no-member
        if not config.has_section("buoys"):
            return None
        # pylint: disable=no-member
        if not config.has_option("buoys", name):
            return None
        # pylint: disable=no-member
        _sites = config.get("buoys", name).split(",")
        try:
            # pylint: disable=no-member
            _name = config.get("buoys", "%s.label" % name)
        except (NoSectionError, NoOptionError):
            logger = logging.getLogger("MapNBDCBuoySource")
            logger.info("_open_source_by_name: No option %s.label",
                        name, exc_info=True)
            _name = name
        sites = tuple([x for x in _sites])

        return MapNBDCBuoySource(_name, "NBDC Buoys", *sites)

    @staticmethod
    def enumerate(config):
        '''
        Enumerate.

        :param config: Configuration data
        :type config: :class:`DratsConfig`
        :returns: filenames for sources
        :rtype: list of str
        '''
        # pylint: disable=no-member
        if not config.has_section("buoys"):
            return []
        # pylint: disable=no-member
        options = config.options("buoys")

        return [x for x in options if not x.endswith(".label")]

    def packed_name(self):
        '''
        Packed name.

        :returns: Fixed up or packed name
        :rtype; str
        '''
        name = []
        for i in self.get_name():
            if (ord(i) > ord("A") and ord(i) < ord("Z")) or\
                    (ord(i) > ord("a") and ord(i) < ord("z")):
                name.append(i)

        return "".join(name)

    def _point_updated(self, point, _unused):
        if point.get_name() not in self._points:
            self._points[point.get_name()] = point
            self.emit("point-added", point)
        else:
            self.emit("point-updated", point)

    def get_buoys(self):
        '''
        Get Buoys.

        :returns: buoys for source
        :rtype: str
        '''
        return self.__buoys
