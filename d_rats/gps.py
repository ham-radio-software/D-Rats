#!/usr/bin/python
'''GPS Module.'''
# pylint: disable=too-many-lines
#
# Copyright 2009 Dan Smith <dsmith@danplanet.com>
# review 2020 Maurizio Andreotti  <iz2lxi@yahoo.it>
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

import re
import time
import tempfile
import datetime
import gettext

import threading
#from typing import Match

import socket

from math import pi, cos, acos, sin, atan2
import serial
from six.moves import range # type: ignore

#importing printlog() wrapper
from .debug import printlog
from . import dplatform
from . import subst

from . import utils

_ = gettext.gettext

TEST = "$GPGGA,180718.02,4531.3740,N,12255.4599,W,1,07,1.4," \
       "50.6,M,-21.4,M,,*63 KE7JSS  ,440.350+ PL127.3"

EARTH_RADIUS = 3963.1
EARTH_UNITS = "mi"

DEGREE = u"\u00b0"

DPRS_TO_APRS = {}


# The DPRS to APRS mapping is pretty horrific, but the following
# attempts to create a mapping based on looking at the javascript
# for DPRSCalc and a list of regular APRS symbols
#
# http://ham-shack.com/aprs_pri_symbols.html
# http://www.aprs-is.net/DPRSCalc.aspx
def init_dprs_to_aprs():
    '''Initialize DPRS_TO_APRS data.'''
    for indx in range(0, 26):
        asciival = ord("A") + indx
        char = chr(asciival)

        pri = "/"
        sec = "\\"

        DPRS_TO_APRS["P%s" % char] = pri + char
        DPRS_TO_APRS["L%s" % char] = pri + char.lower()
        DPRS_TO_APRS["A%s" % char] = sec + char
        DPRS_TO_APRS["S%s" % char] = sec + char.lower()

        if indx <= 15:
            pchar = chr(ord(" ") + indx)
            DPRS_TO_APRS["B%s" % char] = pri + pchar
            DPRS_TO_APRS["O%s" % char] = sec + pchar
        elif indx >= 17:
            pchar = chr(ord(" ") + indx + 9)
            DPRS_TO_APRS["M%s" % char] = pri + pchar
            DPRS_TO_APRS["N%s" % char] = sec + pchar

        if indx <= 5:
            char = chr(ord("S") + indx)
            pchar = chr(ord("[") + indx)
            DPRS_TO_APRS["H%s" % char] = pri + pchar
            DPRS_TO_APRS["D%s" % char] = sec + pchar


init_dprs_to_aprs()

# for k in sorted(DPRS_TO_APRS.keys()):
#    print "%s => %s" % (k, DPRS_TO_APRS[k])

APRS_TO_DPRS = {}


def init_aprs_to_dprs():
    '''Initialize APRS to DPRS data.'''
    for key, value in DPRS_TO_APRS.items():
        APRS_TO_DPRS[value] = key


init_aprs_to_dprs()


class GpsException(Exception):
    '''Generic GPS module exception.'''


class GpsDateParseError(GpsException):
    '''Error parsing a date.'''


class GpsDprsChecksumError(GpsException):
    '''DPRS Checksum Failed.'''


class GpsNmeaException(GpsException):
    '''NMEA Exception.'''


class GpsGpggaException(GpsNmeaException):
    '''GPGGA handling exception.'''


class GpsGpggaParseError(GpsGpggaException):
    '''GPS GPGGA Parsing Error.'''


class GpsGppgaChecksumError(GpsGpggaException):
    '''GPS GPGGA Checksum Error.'''


class GpsGprmcException(GpsNmeaException):
    '''GPRMC Exception.'''


class GpsGpmrcParseError(GpsGprmcException):
    '''GPS GPRMC Parsing Error.'''
    # raise Exception("Unable to split GPRMC (%i)" % len(elements))


class GpsGpmrcChecksumError(GpsGprmcException):
    '''GPS GPRMC Checksum Error.'''
    # raise Exception("GPRMC has no checksum in 12 or 13")

def dprs_to_aprs(symbol):
    '''
    DPRS to APRS.

    :param symbol: DPRS Symbol
    :returns: APRS Symbol
    '''
    if len(symbol) < 2:
        printlog("Gps", "      : Invalid DPRS symbol: `%s'" % symbol)
        return None
    return DPRS_TO_APRS.get(symbol[0:2], None)


def parse_dms(string):
    '''
    Parse Degrees, Minutes, Seconds.

    :param string: String with coordinates
    :returns: Float with Degrees
    '''
    string = string.replace(u"\u00b0", " ")
    string = string.replace('"', ' ')
    string = string.replace("'", ' ')
    string = string.replace('  ', ' ')
    string = string.strip()

    try:
        (d_str, m_str, s_str) = string.split(' ', 3)

        deg = int(d_str)
        minutes = int(m_str)
        sec = float(s_str)
    # pylint: disable=broad-except
    except Exception as err:
        printlog("GPS/parse_dms :",
                 "Broad exception used here (%s) %s",
                 (type(err), err))
        deg = minutes = sec = 0

    if deg < 0:
        mul = -1
    else:
        mul = 1

    deg = abs(deg)

    return (deg + (minutes / 60.0) + (sec / 3600.0)) * mul


def set_units(units):
    '''
    Set units.

    :param units: String Imperial or Metric adjusted for language.
    '''
    # This will be tricky for getting internationalizion working right.
    # pylint: disable=global-statement
    global EARTH_RADIUS
    # pylint: disable=global-statement
    global EARTH_UNITS

    if units == _("Imperial"):
        EARTH_RADIUS = 3963.1
        EARTH_UNITS = "mi"
    elif units == _("Metric"):
        EARTH_RADIUS = 6380.0
        EARTH_UNITS = "km"
    printlog("Gps", "       : Set GPS units to %s" % units)


def value_with_units(value):
    '''
    Value with units.

    Translates a value to be more human readable
    :param value: value to translate
    :returns: String with value and units
    '''
    if value < 0.5:
        if EARTH_UNITS == "km":
            scale = 1000
            units = "m"
        elif EARTH_UNITS == "mi":
            scale = 5280
            units = "ft"
        else:
            scale = 1
            units = EARTH_UNITS
    else:
        scale = 1
        units = EARTH_UNITS

    return "%.2f %s" % (value * scale, units)


# pylint: disable=invalid-name
def NMEA_checksum(string):
    '''
    NMEA Checksum.

    :param string: String to checksum
    :returns: Checksum string
    '''
    checksum = 0
    for i in string:
        checksum ^= ord(i)

    return "*%02x" % checksum


# pylint: invalid-name
def GPSA_checksum(string):
    '''
    GPSA Checksum.

    :param string: GPS String
    :returns: Checksum
    '''
    def calc(buf):
        icomcrc = 0xffff

        for _char in buf:
            char = ord(_char)
            for _indx in range(0, 8):
                xorflag = (((icomcrc ^ char) & 0x01) == 0x01)
                icomcrc = (icomcrc >> 1) & 0x7fff
                if xorflag:
                    icomcrc ^= 0x8408
                char = (char >> 1) & 0x7f
        return (~icomcrc) & 0xffff

    return calc(string)


# pylint: disable=invalid-name
def DPRS_checksum(callsign, msg):
    '''
    DPRS Checksum.

    :param callsign: Station for message
    :param msg: DPRS message
    :returns: Checksum String
    '''
    csum = 0
    string = "%-8s,%s" % (callsign, msg)
    for i in string:
        csum ^= ord(i)

    return "*%02X" % csum


def deg2rad(deg):
    '''
    Degrees to radans.

    :param deg: Degrees
    :returns: Radians
    '''
    return deg * (pi / 180)


def rad2deg(rad):
    '''
    Radians to Degrees.

    :param rad: Radians
    :returns: degrees
    '''
    return rad / (pi / 180)


def dm2deg(deg, minutes):
    '''
    Degrees and minutes to floating degrees

    :param deg: Degrees
    :param min: Minutes
    :returns: Float contining degrees and minutes
    '''
    return deg + (minutes / 60.0)


def deg2dm(decdeg):
    '''
    Degrees to degrees and minutes

    :param decdeg: Floating degrees value
    :returns: Tuple of degree and minutes
    '''
    deg = int(decdeg)
    minutes = (decdeg - deg) * 60.0

    return deg, minutes


def nmea2deg(nmea, direction="N"):
    '''
    NMEA to Degrees

    :param nmea: NMEA position
    :param direction: Direction in set of ['N', 'S', 'E', 'W'], default 'N'
    :returns: Degrees
    '''
    deg = int(nmea) / 100
    try:
        minutes = nmea % (deg * 100)
    except ZeroDivisionError:
        minutes = int(nmea)

    if direction in ["S", "W"]:
        multiplier = -1
    else:
        multiplier = 1

    return dm2deg(deg, minutes) * multiplier


def deg2nmea(deg):
    '''
    Degrees to NMEA.

    :param deg: Degrees
    :returns: NMEA value
    '''
    deg, minutes = deg2dm(deg)

    return (deg * 100) + minutes


def meters2feet(meters):
    '''
    Meters to Feet

    :param meters: Distance in meters
    :returns: Distance in feet
    '''
    return meters * 3.2808399


def feet2meters(feet):
    '''
    Convert feet to meters.

    :param feet: Distance in feet
    :returns: Distance in meters
    '''
    return feet * 0.3048


def distance(lat_a, lon_a, lat_b, lon_b):
    '''
    Distance between two sets of coordinates.

    :param lat_a: Latitude for first coordinate
    :param lon_a: Longitude for first coordinate
    :param lat b: Latitude for first coordinate
    '''
    lat_a = deg2rad(lat_a)
    lon_a = deg2rad(lon_a)

    lat_b = deg2rad(lat_b)
    lon_b = deg2rad(lon_b)

    earth_radius = EARTH_RADIUS

    # print "cos(La)=%f cos(la)=%f" % (cos(lat_a), cos(lon_a))
    # print "cos(Lb)=%f cos(lb)=%f" % (cos(lat_b), cos(lon_b))
    # print "sin(la)=%f" % sin(lon_a)
    # print "sin(lb)=%f" % sin(lon_b)
    # print "sin(La)=%f sin(Lb)=%f" % (sin(lat_a), sin(lat_b))
    # print "cos(lat_a) * cos(lon_a) * cos(lat_b) * cos(lon_b) = %f" % (\
    #    cos(lat_a) * cos(lon_a) * cos(lat_b) * cos(lon_b))
    # print "cos(lat_a) * sin(lon_a) * cos(lat_b) * sin(lon_b) = %f" % (\
    #    cos(lat_a) * sin(lon_a) * cos(lat_b) * sin(lon_b))
    # print "sin(lat_a) * sin(lat_b) = %f" % (sin(lat_a) * sin(lat_b))

    tmp = (cos(lat_a) * cos(lon_a) * \
               cos(lat_b) * cos(lon_b)) + \
               (cos(lat_a) * sin(lon_a) * \
                    cos(lat_b) * sin(lon_b)) + \
                    (sin(lat_a) * sin(lat_b))

    # Correct round-off error (which is just *silly*)
    if tmp > 1:
        tmp = 1
    elif tmp < -1:
        tmp = -1

    dist = acos(tmp)

    return dist * earth_radius


def parse_date(string, fmt):
    '''
    Parse Date.
    
    :param string: String to parse
    :param fmt: Format string
    :returns: datetime object
    :raises: GpsDateParseError
    '''
    try:
        return datetime.datetime.strptime(string, fmt)
    except AttributeError:
        printlog("Gps",
                 "       : Enabling strptime() workaround for Python <= 2.4.x")

    vals = {}

    for char in "mdyHMS":
        indx = fmt.index(char)
        vals[char] = int(string[indx - 1: indx + 1])

    if len(list(vals.keys())) != (len(fmt) / 2):
        raise GpsDateParseError("Not all date bits converted")

    return datetime.datetime(vals["y"] + 2000,
                             vals["m"],
                             vals["d"],
                             vals["H"],
                             vals["M"],
                             vals["S"])


# pylint: disable=too-many-instance-attributes
class GPSPosition():
    '''
    GPS Position.

    Represents a position on the globe, either from GPS data or
    a static position

    :param lat: Latitude, default 0
    :param lon: Longitude, default 0
    :param station: Station, default "UNKNOWN"
    '''

    def _from_coords(self, lat, lon, alt=0):
        try:
            self.latitude = float(lat)
        except ValueError:
            self.latitude = parse_dms(lat)

        try:
            self.longitude = float(lon)
        except ValueError:
            self.longitude = parse_dms(lon)

        self.altitude = float(alt)
        self.satellites = 3
        self.valid = True

    def _parse_dprs_comment(self):
        symbol = self.comment[0:4].strip()
        astidx = self.comment.rindex("*")
        checksum = self.comment[astidx:]

        _checksum = DPRS_checksum(self.station, self.comment[:astidx])

        # WB8TYW this check was failing and spamming the logs before
        # the gtk3 conversion attempt.  Disabling it for now.
        if int(_checksum[1:], 16) != int(checksum[1:], 16):
            printlog("Gps",
                     "        : Failed to parse DPRS comment: %s " %
                     self.comment)
            printlog("Gps",
                     "        : CHECKSUM(%s): %s != %s" %
                     (self.station,
                      int(_checksum[1:], 16),
                      int(checksum[1:], 16)))
            printlog("Gps",
                     "        : Checksum : %s " %
                     checksum)
            printlog("Gps", "        : _checksum: %s " % _checksum)
            printlog("Gps", "        : astidx   : %i " % astidx)

            raise GpsDprsChecksumError("DPRS checksum failed")

        self.APRSIcon = dprs_to_aprs(symbol)
        self.comment = self.comment[4:astidx].strip()

    def __init__(self, lat=0, lon=0, station="UNKNOWN"):
        self.valid = False
        self.altitude = 0
        self.satellites = 0
        self.station = station
        self.comment = ""
        self.current = None
        self.date = datetime.datetime.now()
        self.speed = None
        self.direction = None
        # pylint: disable=invalid-name
        self.APRSIcon = None
        self._original_comment = ""
        self.latitude = None
        self.longitude = None
        self._from_coords(lat, lon)

    def __iadd__(self, update):
        self.station = update.station

        if not update.valid:
            return self

        if update.satellites:
            self.satellites = update.satellites

        if update.altitude:
            self.altitude = update.altitude

        self.latitude = update.latitude
        self.longitude = update.longitude
        self.date = update.date

        if update.speed:
            self.speed = update.speed
        if update.direction:
            self.direction = update.direction

        if update.comment:
            self.comment = update.comment
            # pylint: disable=protected-access
            self._original_comment = update._original_comment

        if update.APRSIcon:
            self.APRSIcon = update.APRSIcon

        return self

    # pylint: disable=too-many-branches
    def __str__(self):
        if self.valid:
            if self.current:
                dist = self.distance_from(self.current)
                bear = self.current.bearing_to(self)
                new_distance = " - %.1f %s " % (dist, EARTH_UNITS) + \
                    _("away") + \
                    " @ %.1f " % bear + \
                    _("degrees")
            else:
                new_distance = ""

            if self.comment:
                comment = " (%s)" % self.comment
            else:
                comment = ""

            if self.speed and self.direction:
                if EARTH_UNITS == "mi":
                    speed = "%.1f mph" % (float(self.speed) * 1.15077945)
                elif EARTH_UNITS == "m":
                    speed = "%.1f km/h" % (float(self.speed) * 1.852)
                else:
                    speed = "%.2f knots" % float(self.speed)

                direct = " (" + _("Heading") +" %.0f at %s)" % (self.direction,
                                                                speed)
            else:
                direct = ""

            if EARTH_UNITS == "mi":
                alt = "%i ft" % meters2feet(self.altitude)
            else:
                alt = "%i m" % self.altitude

            return "%s " % self.station + \
                _("reporting") + \
                " %.4f,%.4f@%s at %s%s%s%s" % ( \
                self.latitude,
                self.longitude,
                alt,
                self.date.strftime("%H:%M:%S"),
                subst.subst_string(comment),
                new_distance,
                direct)
        else:
            return "(" + _("Invalid GPS data") + ")"

    # pylint: disable=invalid-name, no-self-use
    def _NMEA_format(self, val, latitude):
        if latitude:
            if val > 0:
                direction = "N"
            else:
                direction = "S"
        else:
            if val > 0:
                direction = "E"
            else:
                direction = "W"

        return "%.3f,%s" % (deg2nmea(abs(val)), direction)

    def station_format(self):
        '''Station Format.'''
        if " " in self.station:
            call, extra = self.station.split(" ", 1)
            sta = "%-7.7s%1.1s" % (call.strip(),
                                   extra.strip())
        else:
            sta = self.station

        return sta

    # pylint: disable=invalid-name
    def to_NMEA_GGA(self, _ssid=" "):
        '''
        To NMEA GGA.

        :param _ssid: Unused, default " "
        :returns: an NMEA-compliant GPGGA sentence
        '''
        date = time.strftime("%H%M%S")

        lat = self._NMEA_format(self.latitude, True)
        lon = self._NMEA_format(self.longitude, False)

        data = "GPGGA,%s,%s,%s,1,%i,0,%i,M,0,M,," % ( \
            date,
            lat,
            lon,
            self.satellites,
            self.altitude)

        sta = self.station_format()

        # If we had an original comment (with some encoding), use that instead
        if self._original_comment:
            com = self._original_comment
        else:
            com = self.comment

        return "$%s%s\r\n%-8.8s,%-20.20s\r\n" % (data,
                                                 NMEA_checksum(data),
                                                 sta,
                                                 com)

    # pylint: disable=invalid-name
    def to_NMEA_RMC(self):
        '''
        To NMEA RMC.

        :returns: an NMEA-compliant GPRMC sentence
        '''
        tstamp = time.strftime("%H%M%S")
        dstamp = time.strftime("%d%m%y")

        lat = self._NMEA_format(self.latitude, True)
        lon = self._NMEA_format(self.longitude, False)

        if self.speed:
            speed = "%03.1f" % self.speed
        else:
            speed = "000.0"

        if self.direction:
            direction = "%03.1f" % self.direction
        else:
            direction = "000.0"

        data = "GPRMC,%s,A,%s,%s,%s,%s,%s,000.0,W" % ( \
            tstamp,
            lat,
            lon,
            speed,
            direction,
            dstamp)

        sta = self.station_format()

        return "$%s%s\r\n%-8.8s,%-20.20s\r\n" % (data,
                                                 NMEA_checksum(data),
                                                 sta,
                                                 self.comment)

    # pylint: disable=invalid-name
    def to_APRS(self, dest="APRATS", symtab="/", symbol=">"):
        '''
        To APRS.

        :param dest: Destination, default "APRSATS"
        :param symtab: Symbol tab, default "/"
        :param symbol: Symbol, default ">"
        :returns: a GPS-A (APRS-compliant) string
        '''
        stamp = time.strftime("%H%M%S", time.gmtime())

        if " " in self.station:
            sta = self.station.replace(" ", "-")
        else:
            sta = self.station

        sta_str = "%s>%s,DSTAR*:/%sh" % (sta, dest, stamp)

        if self.latitude > 0:
            northsouth = "N"
            lat_m = 1
        else:
            northsouth = "S"
            lat_m = -1

        if self.longitude > 0:
            eastwest = "E"
            lon_m = 1
        else:
            eastwest = "W"
            lon_m = -1

        sta_str += "%07.2f%s%s%08.2f%s%s" % \
                   (deg2nmea(self.latitude * lat_m),
                    northsouth,
                    symtab,
                    deg2nmea(self.longitude * lon_m),
                    eastwest,
                    symbol)
        if self.speed and self.direction:
            sta_str += "%03.0f/%03.0f" % \
                       (float(self.direction), float(self.speed))

        if self.altitude:
            sta_str += "/A=%06i" % meters2feet(float(self.altitude))
        else:
            # sta_str += "/"
            #  Removed to permit transmit Weather information (WX)
            sta_str += ""

        if self.comment:
            l_data = 43
            if self.altitude:
                l_data -= len("/A=xxxxxx")

            sta_str += "%s" % self.comment[:l_data]

        sta_str += "\r"

        return "$$CRC%04X,%s\n" % (GPSA_checksum(sta_str), sta_str)

    def set_station(self, station, comment="D-RATS"):
        '''
        Set Station

        :param station: Station name
        :param comment: Comment, default 'D-RATS'
        '''
        self.station = station
        self.comment = comment
        self._original_comment = comment

        # Temp disabled as flooding the log
        # if len(self.comment) >= 7 and "*" in self.comment[-3:-1]:
        #     printlog('gps.set_station called _parse_dprs_comment')
        #    self._parse_dprs_comment()

    def distance_from(self, pos):
        '''
        Distance From.

        :param pos: Postion to get distance from
        :returns: Distrance
        '''
        return distance(self.latitude, self.longitude,
                        pos.latitude, pos.longitude)

    def bearing_to(self, pos):
        '''
        Bearing To.

        :param pos: Position to get bearing to
        :returns: Float with Bearing
        '''
        lat_me = deg2rad(self.latitude)
        # lon_me = deg2rad(self.longitude)

        lat_u = deg2rad(pos.latitude)
        # lon_u = deg2rad(pos.longitude)

        # lat_d = deg2rad(pos.latitude - self.latitude)
        lon_d = deg2rad(pos.longitude - self.longitude)

        y = sin(lon_d) * cos(lat_u)
        x = cos(lat_me) * sin(lat_u) - \
            sin(lat_me) * cos(lat_u) * cos(lon_d)

        bearing = rad2deg(atan2(y, x))

        return (bearing + 360) % 360

    def set_relative_to_current(self, current):
        '''
        Set Relative to current.

        :param current: current data
        '''
        self.current = current

    def coordinates(self):
        '''
        Coordinates.

        :returns: String with coordinates
        '''
        return "%.4f,%.4f" % (self.latitude, self.longitude)

    def fuzzy_to(self, pos):
        '''
        Fuzzy to.

        :param pos: Position
        :returns: String describing position'''
        direction = self.bearing_to(pos)

        dirs = ["N", "NNE", "NE", "ENE", "E",
                "ESE", "SE", "SSE", "S",
                "SSW", "SW", "WSW", "W",
                "WNW", "NW", "NNW"]

        delta = 22.5
        angle = 0

        direction = "?"
        for dir_indx in dirs:
            if angle < direction < (angle + delta):
                direction = dir_indx
            angle += delta

        return "%.1f %s %s" % (self.distance_from(pos),
                               EARTH_UNITS,
                               direction)


class NMEAGPSPosition(GPSPosition):
    '''
    A GPSPosition initialized from a NMEA sentence.

    :param sentence: Sentence for initialization
    :param station: Station, default _("UNKNOWN")
    :raises: GpsGpggaException classes on error.
    '''

    # pylint: disable=no-self-use
    def _test_checksum(self, string, csum):
        try:
            idx = string.index("*")
        # pylint: disable=broad-except
        except Exception as err:
            printlog("Gps        :",
                     "String does not contain '*XY' checksum Generic(%s) %s" %
                     (type(err), err))
            return False

        segment = string[1:idx]

        csum = csum.upper()
        _csum = NMEA_checksum(segment).upper()

        if csum != _csum:
            printlog("Gps",
                     "        : Failed checksum: %s != %s" % (csum, _csum))

        return csum == _csum


    def _parse_GPGGA(self, string):
        elements = string.split(",", 14)
        if len(elements) < 15:
            raise GpsGpggaParseError("Unable to split GPGGA" % len(elements))

        time_str = time.strftime("%m%d%y") + elements[1]
        if "." in time_str:
            time_str = time_str.split(".")[0]
        self.date = parse_date(time_str, "%m%d%y%H%M%S")

        self.latitude = nmea2deg(float(elements[2]), elements[3])
        self.longitude = nmea2deg(float(elements[4]), elements[5])

        printlog("Gps", "        :  %f,%f" % (self.latitude, self.longitude))

        self.satellites = int(elements[7])
        self.altitude = float(elements[9])

        match = re.match(r"^([0-9]*)(\*[A-z0-9]{2})\r?\n?(.*)$", elements[14])
        if not match:
            raise GpsGppgaChecksumError("No checksum (%s)" % elements[14])

        csum = match.group(2)
        if "," in match.group(3):
            sta, com = match.group(3).split(",", 1)
            if not sta.strip().startswith("$"):
                self.station = utils.filter_to_ascii(sta.strip()[0:8])
                self.comment = utils.filter_to_ascii(com.strip()[0:20])
                self._original_comment = self.comment

        if len(self.comment) >= 7 and "*" in self.comment[-3:-1]:
            printlog('gps._parse_GPGGA called _parse_dprs_comment')
            self._parse_dprs_comment()

        self.valid = self._test_checksum(string, csum)

    def _parse_GPRMC(self, string):
        if "\r\n" in string:
            nmea, station = string.split("\r\n", 1)
        else:
            nmea = string
            station = ""
        elements = nmea.split(",", 12)
        if len(elements) < 12:
            raise GpsGpmrcParseError("Unable to split GPRMC (%i)" %
                                     len(elements))

        time_str = elements[1]
        date_str = elements[9]

        if "." in time_str:
            time_str = time_str.split(".", 2)[0]

        self.date = parse_date(date_str + time_str, "%d%m%y%H%M%S")

        self.latitude = nmea2deg(float(elements[3]), elements[4])
        self.longitude = nmea2deg(float(elements[5]), elements[6])

        self.speed = float(elements[7])
        self.direction = float(elements[8])

        if "*" in elements[11]:
            end = 11 # NMEA <=2.0
        elif "*" in elements[12]:
            end = 12 # NMEA 2.3
        else:
            raise GpsGpmrcChecksumError("GPRMC has no checksum in 12 or 13")

        match = re.match(r"^.?(\*[A-z0-9]{2})", elements[end])
        if not match:
            printlog("Gps", "        :  Invalid end: %s" % elements[end])
            return

        csum = match.group(1)
        if "," in station:
            sta, com = station.split(",", 1)
            self.station = utils.filter_to_ascii(sta.strip())
            self.comment = utils.filter_to_ascii(com.strip())
            self._original_comment = self.comment

        if len(self.comment) >= 7 and "*" in self.comment[-3:-1]:
            printlog('gps._parse_GPRMC called _parse_dprs_comment')
            self._parse_dprs_comment()

        if elements[2] != "A":
            self.valid = False
            printlog("Gps",
                     "        : GPRMC marked invalid by GPS (%s)" %
                     elements[2])
        else:
            printlog("Gps",
                     "        : GPRMC is valid")
            self.valid = self._test_checksum(string, csum)

    def _from_NMEA_GPGGA(self, string):
        string = string.replace('\r', ' ')
        string = string.replace('\n', ' ')
        try:
            self._parse_GPGGA(string)
        # pylint: disable=broad-except
        except Exception as err:
            import traceback
            import sys
            traceback.print_exc(file=sys.stdout)
            printlog("Gps",
                     "       : Invalid GPS data: Generic (%s) %s" %
                     (type(err), err))
            self.valid = False

    def _from_NMEA_GPRMC(self, string):
        try:
            self._parse_GPRMC(string)
        # pylint: disable=broad-except
        except Exception as err:
            import traceback
            import sys
            traceback.print_exc(file=sys.stdout)
            printlog("Gps",
                     "        : Invalid GPS data: Generic (%s) %s" %
                     (type(err), err))
            self.valid = False

    def __init__(self, sentence, station=_("UNKNOWN")):
        GPSPosition.__init__(self)
        self.latitude = None
        self.longitude = None

        if sentence.startswith("$GPGGA"):
            self._from_NMEA_GPGGA(sentence)
        elif sentence.startswith("$GPRMC"):
            self._from_NMEA_GPRMC(sentence)
        else:
            printlog("Gps",
                     "        : Unsupported GPS sentence type: %s" % sentence)


class APRSGPSPosition(GPSPosition):
    '''APRS GPS Position.'''

    # pylint: disable=no-self-use
    def _parse_date(self, string):
        # prefix = string[0]
        suffix = string[-1]
        digits = string[1:-1]

        if suffix == "z":
            date_str = digits[0:2] + \
                time.strftime("%m%y", time.gmtime()) + \
                digits[2:] + "00"
        elif suffix == "/":
            date_str = digits[0:2] + time.strftime("%m%y") + digits[2:] + "00"
        elif suffix == "h":
            date_str = time.strftime("%d%m%y", time.gmtime()) + digits
        else:
            printlog("Gps",
                     "        : Unknown APRS date suffix: `%s'" % suffix)
            return datetime.datetime.now()

        date_num = parse_date(date_str, "%d%m%y%H%M%S")

        if suffix in "zh":
            delta = datetime.datetime.utcnow() - datetime.datetime.now()
        else:
            delta = datetime.timedelta(0)

        return date_num - delta

    def _parse_GPSA(self, string):
        match = re.match(r"^\$\$CRC([A-Z0-9]{4}),(.*)$", string)
        if not match:
            return

        crc = match.group(1)
        _crc = "%04X" % GPSA_checksum(match.group(2))

        if crc != _crc:
            printlog("Gps",
                     "        : APRS CRC mismatch: %s != %s (%s)" %
                     (crc, _crc, match.group(2)))
            return

        elements = string.split(",")
        if not elements[0].startswith("$$CRC"):
            printlog("Gps       : Missing $$CRC...")
            return

        self.station, _dst = elements[1].split(">")

        _path, data = elements[2].split(":")

        #  1 = Entire stamp or ! or =
        #  2 = stamp prefix
        #  3 = stamp suffix
        #  4 = latitude
        #  5 = N/S
        #  6 = symbol table
        #  7 = longitude
        #  8 = E/W
        #  9 = symbol
        # 10 = comment
        # 11 = altitude string

        expr = r"^(([@/])[0-9]{6}([/hz])|!|=)" + \
            r"([0-9]{1,4}\.[0-9]{2})([NS])(.)?" + \
            r"([0-9]{5}\.[0-9]{2})([EW])(.)" + \
            r"([^/]*)(/A=[0-9]{6})?"

        match = re.search(expr, data)
        if not match:
            printlog("Gps", "        : Did not match GPS-A: `%s'" % data)
            return

        if match.group(1) in "!=":
            self.date = datetime.datetime.now()
        elif match.group(2) in "@/":
            self.date = self._parse_date(match.group(1))
        else:
            printlog("Gps",
                     "        : Unknown timestamp prefix: %s" %
                     match.group(1))
            self.date = datetime.datetime.now()

        self.latitude = nmea2deg(float(match.group(4)), match.group(5))
        self.longitude = nmea2deg(float(match.group(7)), match.group(8))
        self.comment = match.group(10).strip()
        self._original_comment = self.comment
        self.APRSIcon = match.group(6) + match.group(9)

        if len(match.groups()) == 11 and match.group(11):
            _, alt = match.group(11).split("=")
            self.altitude = feet2meters(int(alt))

        self.valid = True

    def _from_APRS(self, string):
        self.valid = False
        try:
            self._parse_GPSA(string)
        # pylint: disable=broad-except
        except Exception as err:
            printlog("Gps",
                     "  : _from_APRS Generic Exception Invalid APRS: (%s) %s" %
                     (type(err), err))
            return False

        return self.valid

    def __init__(self, message):
        self.latitude = None
        self.longitude = None

        GPSPosition.__init__(self)

        self._from_APRS(message)


class MapImage():
    '''
    Map Image.

    :param center: Center of map
    '''

    def __init__(self, center):
        self.key = "ABQIAAAAWot3KuWpenfCAGfQ65FdzRTaP0xjRaMPpcw6bBbU" \
                   "2QUEXQBgHBR5Rr2HTGXYVWkcBFNkPvxtqV4VLg"
        self.center = center
        self.markers = [center]

    def add_markers(self, markers):
        '''Add Markers.'''
        self.markers += markers

    def get_image_url(self):
        '''
        Get Image Url.

        :returns: Google map URL
        '''
        el_data = ["key=%s" % self.key,
                   "center=%s" % self.center.coordinates(),
                   "size=400x400"]

        mstr = "markers="
        index = ord("a")
        for marker in self.markers:
            mstr += "%s,blue%s|" % (marker.coordinates(), chr(index))
            index += 1

        el_data.append(mstr)

        return "http://maps.google.com/staticmap?%s" % ("&".join(el_data))

    def station_table(self):
        '''
        Station Table.

        :returns: String with a table in an HTML fragment
        '''
        table = ""

        index = ord('A')
        for marker in self.markers:
            table += "<tr><td>%s</td><td>%s</td><td>%s</td>\n" % (\
                chr(index),
                marker.station,
                marker.coordinates())
            index += 1

        return table

    def make_html(self):
        '''
        Make html.

        :returns: String with HTML page
        '''
        return """
<html>
  <head>
    <title>Known stations</title>
  </head>
  <body>
    <h1> Known Stations </h1>
    <img src="%s"/><br/><br/>
    <table border="1">
%s
    </table>
  </body>
</html>
""" % (self.get_image_url(), self.station_table())

    def display_in_browser(self):
        '''Display in Browser.'''
        fhandle = tempfile.NamedTemporaryFile(suffix=".html")
        name = fhandle.name
        fhandle.close()
        fhandle = open(name, "w")
        fhandle.write(self.make_html())
        fhandle.flush()
        fhandle.close()
        platform = dplatform.get_platform()
        platform.open_html_file(fhandle.name)


class GPSSource():
    '''
    GPS Source.

    :param port: Port for GPS access
    :param rate: Baud rate, default=4800
    '''

    def __init__(self, port, rate=4800):
        self.port = port
        self.enabled = False
        self.broken = None
        self.invalid = 0

        try:
            self.serial = serial.Serial(port=port, baudrate=rate, timeout=1)
        # pylint: disable=broad-except
        except Exception as err:
            printlog("Gps",
                     "        : Unable to open port `%s': Generic (%s) %s" %
                     (port, type(err), err))
            self.broken = _("Unable to open GPS port")

        self.thread = None

        self.last_valid = False
        self.position = GPSPosition()

    def start(self):
        '''Start.'''
        if self.broken:
            printlog("Gps", "        : Not starting broken GPSSource")
            return

        self.invalid = 100
        self.enabled = True
        self.thread = threading.Thread(target=self.gpsthread)
        self.thread.setDaemon(True)
        self.thread.start()

    def stop(self):
        '''Stop.'''
        if self.thread and self.enabled:
            self.enabled = False
            self.thread.join()
            self.serial.close()

    def gpsthread(self):
        '''GPS Thread.'''
        while self.enabled:
            data = self.serial.read(1024)
            lines = data.split("\r\n")

            for line in lines:
                if line.startswith("$GPGGA") or \
                        line.startswith("$GPRMC"):
                    position = NMEAGPSPosition(line)

                    if position.valid and line.startswith("$GPRMC"):
                        self.invalid = 0
                    elif self.invalid < 10:
                        self.invalid += 1

                    if position.valid and self.position.valid:
                        self.position += position
                        printlog("Gps",
                                 _("ME") +
                                 ": xxxxxxxxxxxxxxxxxxxxxxxxxxxxx %s" %
                                 self.position)
                    elif position.valid:
                        self.position = position
                    else:
                        printlog("Gps", "        : Could not parse: %s" % line)

    def get_position(self):
        '''
        Get position.

        :returns: Position information
        '''
        return self.position

    def status_string(self):
        '''
        Status String.

        :returns: String containing status
        '''
        if self.broken:
            return self.broken
        if self.invalid < 10 and self.position.satellites >= 3:
            return _("GPS Locked") + " (%i sats)" % self.position.satellites
        return _("GPS Not Locked")


class NetworkGPSSource(GPSSource):
    '''
    Network GPS Source.

    :param port: Network port
    '''

    # pylint: disable=super-init-not-called
    def __init__(self, port):
        self.port = port
        self.enabled = False
        self.thread = None
        self.position = GPSPosition()
        printlog("Gps", "        : NetworkGPSPosition: %s" % self.position)
        self.last_valid = False
        self.sock = None
        self.broken = None

    def start(self):
        '''Start.'''
        self.enabled = True
        self.thread = threading.Thread(target=self.gpsthread)
        self.thread.setDaemon(True)
        self.thread.start()

    def stop(self):
        '''Stop.'''
        if self.thread and self.enabled:
            self.enabled = False
            self.thread.join()

    def connect(self):
        '''
        Connect.

        :returns: False if could not connect
        '''
        try:
            _, host, port = self.port.split(":", 3)
            port = int(port)
        except ValueError as err:
            printlog("Gps",
                     "       : Unable to parse %s Generic (%s) %s" %
                     (self.port, type(err), err))
            self.broken = _("Unable to parse address")
            return False

        printlog("Gps", "        : Connecting to %s:%i" % (host, port))

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((host, port))
            self.sock.settimeout(10)
        # pylint: disable=broad-except
        except Exception as err:
            printlog("Gps",
                     "        : Unable to connect: Generic (%s) %s"
                     % (type(err), err))
            self.broken = _("Unable to connect") + ": %s" % err
            self.sock = None
            return False

        self.sock.send("r\n")

        return True

    def gpsthread(self):
        '''GPS Thread.'''
        while self.enabled:
            if not self.sock:
                if not self.connect():
                    time.sleep(1)
                    continue

            try:
                data = self.sock.recv(1024)

            # pylint: disable=broad-except
            except Exception as err:
                self.sock.close()
                self.sock = None
                printlog("Gps",
                         "       : GPSd Socket closed. Generic (%s) %s" %
                         (type(err), err))
                continue

            line = data.strip()

            if not (line.startswith("$GPGGA") or \
                        line.startswith("$GPRMC")):
                continue

            pos = NMEAGPSPosition(line)

            self.last_valid = pos.valid
            if pos.valid and self.position.valid:
                self.position += pos
            elif pos.valid:
                self.position = pos
            else:
                printlog("Gps", "        : Could not parse: %s" % line)

    def get_position(self):
        '''
        Get position.

        :returns: Position information
        '''
        return self.position

    def status_string(self):
        '''
        Status String.

        :returns: String containing status
        '''
        if self.broken:
            return self.broken
        elif self.last_valid and self.position.satellites >= 3:
            return _("GPSd Locked") + " (%i sats)" % self.position.satellites
        return _("GPSd Not Locked")


class StaticGPSSource(GPSSource):
    '''
    Static GPS Source.

    :param lat: Latitude
    :param lon: Longitude
    :param alt: Altitude, default 0
    '''

    # pylint: disable=super-init-not-called
    def __init__(self, lat, lon, alt=0):
        self.lat = lat
        self.lon = lon
        self.alt = alt

        self.position = GPSPosition(self.lat, self.lon)
        self.position.altitude = int(float(alt))
        if EARTH_UNITS == "mi":
            # This is kinda ugly, but assume we're given altitude in the same
            # type of units as we've been asked to display
            self.position.altitude = feet2meters(self.position.altitude)
        printlog("Gps", "       : StaticGPSPosition: %s" % self.position)

    def start(self):
        '''Start.'''

    def stop(self):
        '''Stop.'''

    def get_position(self):
        '''
        Get position.

        :returns: Position information
        '''
        return self.position

    def status_string(self):
        '''
        Status String.

        :returns: String containing status
        '''
        return _("Static position")


def parse_GPS(string):
    '''
    Parse GPS string.

    :param string: GPS data to parse
    :returns: Gps Fix
    '''
    fixes = []

    while "$" in string:
        try:
            if "$GPGGA" in string:
                fixes.append(NMEAGPSPosition(string[string.index("$GPGGA"):]))
                string = string[string.index("$GPGGA")+6:]
            elif "$GPRMC" in string:
                fixes.append(NMEAGPSPosition(string[string.index("$GPRMC"):]))
                string = string[string.index("$GPRMC")+6:]
            elif "$$CRC" in string:
                return APRSGPSPosition(string[string.index("$$CRC"):])
            else:
                string = string[string.index("$")+1:]
        # pylint: disable=broad-except
        except Exception as err:
            printlog("Gps",
                     "        :  Generic Exception during GPS parse: (%s) %s" %
                     (type(err), err))
            string = string[string.index("$")+1:]

    if not fixes:
        return None

    fix = fixes[0]
    fixes = fixes[1:]

    for extra in fixes:
        printlog("Gps", "        : Appending fix: %s" % extra)
        fix += extra

    return fix


def main():
    '''Unit Test.'''

    nmea_strings = [
        "$GPRMC,010922,A,4603.6695,N,07307.3033,W,0.6,66.8,060508," \
            "16.1,W,A*1D\r\nVE2SE  9,MV  VE2SE@RAC.CA*32",
        "$GPGGA,203008.78,4524.9729,N,12246.9580,W,1,03,3.8,00133,M,,,,*39",
        "$GPGGA,183324.518,4533.0875,N,12254.5939,W,2,04,3.4,48.6," \
            "M,-19.6,M,1.2,0000*74",
        "$GPRMC,215348,A,4529.3672,N,12253.2060,W,0.0,353.8,030508,17.5,E,D*3C",
        "$GPGGA,075519,4531.254,N,12259.400,W,1,3,0,0.0,M,0,M,,*55\r\n" \
            "K7HIO   ,GPS Info",
        "$GPRMC,074919.04,A,4524.9698,N,12246.9520,W,00.0,000.0,260508,19.,E*79",
        "$GPRMC,123449.089,A,3405.1123,N,08436.4301,W,000.0,000.0,021208,,,A*71",
        "$GPRMC,123449.089,A,3405.1123,N,08436.4301,W,000.0,000.0,021208," \
            ",,A*71\r\nKK7DS  M,LJ  DAN*C",
        "$GPRMC,230710,A,2748.1414,N,08238.5556,W,000.0,033.1,111208,004.3,W*77",
        ]
    printlog("Gps", "        : -- NMEA --")

    for nmea_str in nmea_strings:
        nmea_pos = NMEAGPSPosition(nmea_str)
        if nmea_pos.valid:
            printlog("Gps", "        : Pass: %s" % str(nmea_pos))
        else:
            printlog("Gps", "      : ** FAIL: %s" % nmea_str)

    aprs_strings = [
        "$$CRCCE3E,AE5PL-T>API282,DSTAR*:!3302.39N/09644.66W>/\r",
        "$$CRC1F72,KI4IFW-1>APRATS,DSTAR*:@291930/4531.50N/12254.98W" \
            ">APRS test beacon /A=000022",
        "$$CRC80C3,VA2PBI>APU25N,DSTAR*:=4539.33N/07330.28W" \
            "-73 de Pierre D-Star Montreal {UIV32N}",
        "$$CRCA31F,VA2PBI>API282,DSTAR*:/221812z4526.56N07302.34W/\r",
        '$$CRCF471,AB9FT-ML>APRATS,DSTAR*:@214235h0.00S/00000.00W" \
            ">ON D-RATS at Work\r',
        ]

    printlog("Gps       :  \n-- GPS-A --")

    for aprs_str in aprs_strings:
        gps_pos = APRSGPSPosition(aprs_str)
        if gps_pos.valid:
            printlog("Gps", "       :  Pass: %s" % str(gps_pos))
        else:
            printlog("Gps", "       :  ** FAIL: %s" % aprs_str)


if __name__ == "__main__":
    main()
