#!/usr/bin/python
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
from . import dplatform
import datetime
from . import subst

import threading
import serial
import socket

from math import pi,cos,acos,sin,atan2

from . import utils
from six.moves import range

if __name__ == "__main__":
    import gettext
    gettext.install("D-RATS")

TEST = "$GPGGA,180718.02,4531.3740,N,12255.4599,W,1,07,1.4,50.6,M,-21.4,M,,*63 KE7JSS  ,440.350+ PL127.3"

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
for i in range(0, 26):
    asciival = ord("A") + i
    char = chr(asciival)

    pri = "/"
    sec = "\\"

    DPRS_TO_APRS["P%s" % char] = pri + char
    DPRS_TO_APRS["L%s" % char] = pri + char.lower()
    DPRS_TO_APRS["A%s" % char] = sec + char
    DPRS_TO_APRS["S%s" % char] = sec + char.lower()

    if i <= 15:
        pchar = chr(ord(" ") + i)
        DPRS_TO_APRS["B%s" % char] = pri + pchar
        DPRS_TO_APRS["O%s" % char] = sec + pchar
    elif i >= 17:
        pchar = chr(ord(" ") + i + 9)
        DPRS_TO_APRS["M%s" % char] = pri + pchar
        DPRS_TO_APRS["N%s" % char] = sec + pchar

    if i <= 5:
        char = chr(ord("S") + i)
        pchar = chr(ord("[") + i)
        DPRS_TO_APRS["H%s" % char] = pri + pchar
        DPRS_TO_APRS["D%s" % char] = sec + pchar

#for k in sorted(DPRS_TO_APRS.keys()):
#    print "%s => %s" % (k, DPRS_TO_APRS[k])

APRS_TO_DPRS = {}
for k,v in DPRS_TO_APRS.items():
    APRS_TO_DPRS[v] = k

def dprs_to_aprs(symbol):
    if len(symbol) < 2:
        print(("Gps       : Invalid DPRS symbol: `%s'" % symbol))
        return None
    else:
        return DPRS_TO_APRS.get(symbol[0:2], None)

def parse_dms(string):
    string = string.replace(u"\u00b0", " ")
    string = string.replace('"', ' ')
    string = string.replace("'", ' ')
    string = string.replace('  ', ' ')
    string = string.strip()
    
    try:
        (d, m, s) = string.split(' ', 3)
    
        deg = int(d)
        min = int(m)
        sec = float(s)
    except Exception as e:
        deg = min = sec = 0

    if deg < 0:
        mul = -1
    else:
        mul = 1

    deg = abs(deg)
   
    return (deg + (min / 60.0) + (sec / 3600.0)) * mul

def set_units(units):
    global EARTH_RADIUS
    global EARTH_UNITS

    if units == _("Imperial"):
        EARTH_RADIUS = 3963.1
        EARTH_UNITS = "mi"
    elif units == _("Metric"):
        EARTH_RADIUS = 6380.0
        EARTH_UNITS = "km"
    print(("Gps       : Set GPS units to %s" % units))

def value_with_units(value):
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

def NMEA_checksum(string):
    checksum = 0
    for i in string:
        checksum ^= ord(i)

    return "*%02x" % checksum

def GPSA_checksum(string):
    def calc(buf):
        icomcrc = 0xffff

        for _char in buf:
            char = ord(_char)
            for i in range(0, 8):
                xorflag = (((icomcrc ^ char) & 0x01) == 0x01)
                icomcrc = (icomcrc >> 1) & 0x7fff
                if xorflag:
                    icomcrc ^= 0x8408
                char = (char >> 1) & 0x7f
        return (~icomcrc) & 0xffff

    return calc(string)

def DPRS_checksum(callsign, msg):
    csum = 0
    string = "%-8s,%s" % (callsign, msg)
    for i in string:
        csum ^= ord(i)

    return "*%02X" % csum

def deg2rad(deg):
    return deg * (pi / 180)

def rad2deg(rad):
    return rad / (pi / 180)

def dm2deg(deg, min):
    return deg + (min / 60.0)

def deg2dm(decdeg):
    deg = int(decdeg)
    min = (decdeg - deg) * 60.0

    return deg, min

def nmea2deg(nmea, dir="N"):
    deg = int(nmea) / 100
    try:
        min = nmea % (deg * 100)
    except ZeroDivisionError as e:
        min = int(nmea)

    if dir == "S" or dir == "W":
        m = -1
    else:
        m = 1

    return dm2deg(deg, min) * m

def deg2nmea(deg):
    deg, min = deg2dm(deg)

    return (deg * 100) + min

def meters2feet(meters):
    return meters * 3.2808399

def feet2meters(feet):
    return feet * 0.3048

def distance(lat_a, lon_a, lat_b, lon_b):
    lat_a = deg2rad(lat_a)
    lon_a = deg2rad(lon_a)
    
    lat_b = deg2rad(lat_b)
    lon_b = deg2rad(lon_b)
    
    earth_radius = EARTH_RADIUS
    
    #print "cos(La)=%f cos(la)=%f" % (cos(lat_a), cos(lon_a))
    #print "cos(Lb)=%f cos(lb)=%f" % (cos(lat_b), cos(lon_b))
    #print "sin(la)=%f" % sin(lon_a)
    #print "sin(lb)=%f" % sin(lon_b)
    #print "sin(La)=%f sin(Lb)=%f" % (sin(lat_a), sin(lat_b))
    #print "cos(lat_a) * cos(lon_a) * cos(lat_b) * cos(lon_b) = %f" % (\
    #    cos(lat_a) * cos(lon_a) * cos(lat_b) * cos(lon_b))
    #print "cos(lat_a) * sin(lon_a) * cos(lat_b) * sin(lon_b) = %f" % (\
    #    cos(lat_a) * sin(lon_a) * cos(lat_b) * sin(lon_b))
    #print "sin(lat_a) * sin(lat_b) = %f" % (sin(lat_a) * sin(lat_b))

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

    distance = acos(tmp)

    return distance * earth_radius

def parse_date(string, fmt):
    try:
        return datetime.datetime.strptime(string, fmt)
    except AttributeError as e:
        print("Gps       : Enabling strptime() workaround for Python <= 2.4.x")

    vals = {}

    for c in "mdyHMS":
        i = fmt.index(c)
        vals[c] = int(string[i-1:i+1])

    if len(list(vals.keys())) != (len(fmt) / 2):
        raise Exception("Not all date bits converted")

    return datetime.datetime(vals["y"] + 2000,
                             vals["m"],
                             vals["d"],
                             vals["H"],
                             vals["M"],
                             vals["S"])

class GPSPosition(object):
    """Represents a position on the globe, either from GPS data or a static
    positition"""
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

        if int(_checksum[1:], 16) != int(checksum[1:], 16):
            print("Gps       : ----------")
            print(("Gps       : Failed to parse DPRS comment: %s " % self.comment))
            print(("Gps       : CHECKSUM(%s): %s != %s" % (self.station,int(_checksum[1:], 16),int(checksum[1:], 16))))
            print(("Gps       : Checksum : %s " % checksum))
            print(("Gps       : _checksum: %s " % _checksum))
            print(("Gps       : astidx   : %i " % astidx))
            print("Gps       : ----------")
            raise Exception("DPRS checksum failed")

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
        self.APRSIcon = None
        self._original_comment = ""
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
            self._original_comment = update._original_comment

        if update.APRSIcon:
            self.APRSIcon = update.APRSIcon

        return self

    def __str__(self):
        if self.valid:
            if self.current:
                dist = self.distance_from(self.current)
                bear = self.current.bearing_to(self)
                distance = " - %.1f %s " % (dist, EARTH_UNITS) + \
                    _("away") + \
                    " @ %.1f " % bear + \
                    _("degrees")
            else:
                distance = ""

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

                dir = " (" + _("Heading") +" %.0f at %s)" % (self.direction,
                                                             speed)
            else:
                dir = ""

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
                distance,
                dir)
        else:
            return "(" + _("Invalid GPS data") + ")"

    def _NMEA_format(self, val, latitude):
        if latitude:
            if val > 0:
                d = "N"
            else:
                d = "S"
        else:
            if val > 0:
                d = "E"
            else:
                d = "W"

        return "%.3f,%s" % (deg2nmea(abs(val)), d)

    def station_format(self):
        if " " in self.station:
            call, extra = self.station.split(" ", 1)
            sta = "%-7.7s%1.1s" % (call.strip(),
                                   extra.strip())
        else:
            sta = self.station

        return sta

    def to_NMEA_GGA(self, ssid=" "):
        """Returns an NMEA-compliant GPGGA sentence"""
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

    def to_NMEA_RMC(self):
        """Returns an NMEA-compliant GPRMC sentence"""
        tstamp = time.strftime("%H%M%S")
        dstamp = time.strftime("%d%m%y")

        lat = self._NMEA_format(self.latitude, True)
        lon = self._NMEA_format(self.longitude, False)

        if self.speed:
            speed = "%03.1f" % self.speed
        else:
            speed = "000.0"

        if self.direction:
            dir = "%03.1f" % self.direction
        else:
            dir = "000.0"

        data = "GPRMC,%s,A,%s,%s,%s,%s,%s,000.0,W" % ( \
            tstamp,
            lat,
            lon,
            speed,
            dir,
            dstamp)

        sta = self.station_format()

        return "$%s%s\r\n%-8.8s,%-20.20s\r\n" % (data,
                                                 NMEA_checksum(data),
                                                 sta,
                                                 self.comment)

    def to_APRS(self, dest="APRATS", symtab="/", symbol=">"):
        """Returns a GPS-A (APRS-compliant) string"""

        stamp = time.strftime("%H%M%S", time.gmtime())

        if " " in self.station:
            sta = self.station.replace(" ", "-")
        else:
            sta = self.station

        s = "%s>%s,DSTAR*:/%sh" % (sta, dest, stamp)

        if self.latitude > 0:
            ns = "N"
            Lm = 1
        else:
            ns = "S"
            Lm = -1

        if self.longitude > 0:
            ew = "E"
            lm = 1
        else:
            ew = "W"            
            lm = -1

        s += "%07.2f%s%s%08.2f%s%s" % (deg2nmea(self.latitude * Lm), ns,
                                        symtab,
                                        deg2nmea(self.longitude * lm), ew,
                                        symbol)
        if self.speed and self.direction:
            s += "%03.0f/%03.0f" % (float(self.direction), float(self.speed))

        if self.altitude:
            s += "/A=%06i" % meters2feet(float(self.altitude))
        else:
            s += "/"

        if self.comment:
            l = 43
            if self.altitude:
                l -= len("/A=xxxxxx")

            s += "%s" % self.comment[:l]

        s += "\r"

        return "$$CRC%04X,%s\n" % (GPSA_checksum(s), s)

    def set_station(self, station, comment="D-RATS"):
        self.station = station
        self.comment = comment
        self._original_comment = comment

        if len(self.comment) >=7 and "*" in self.comment[-3:-1]:
            self._parse_dprs_comment()

    def distance_from(self, pos):
        return distance(self.latitude, self.longitude,
                        pos.latitude, pos.longitude)

    def bearing_to(self, pos):
        lat_me = deg2rad(self.latitude)
        lon_me = deg2rad(self.longitude)

        lat_u = deg2rad(pos.latitude)
        lon_u = deg2rad(pos.longitude)

        lat_d = deg2rad(pos.latitude - self.latitude)
        lon_d = deg2rad(pos.longitude - self.longitude)

        y = sin(lon_d) * cos(lat_u)
        x = cos(lat_me) * sin(lat_u) - \
            sin(lat_me) * cos(lat_u) * cos(lon_d)

        bearing = rad2deg(atan2(y, x))

        return (bearing + 360) % 360

    def set_relative_to_current(self, current):
        self.current = current

    def coordinates(self):
        return "%.4f,%.4f" % (self.latitude, self.longitude)

    def fuzzy_to(self, pos):
        dir = self.bearing_to(pos)

        dirs = ["N", "NNE", "NE", "ENE", "E",
                "ESE", "SE", "SSE", "S",
                "SSW", "SW", "WSW", "W",
                "WNW", "NW", "NNW"]

        delta = 22.5
        angle = 0

        direction = "?"
        for i in dirs:
            if dir > angle and dir < (angle + delta):
                direction = i
            angle += delta

        return "%.1f %s %s" % (self.distance_from(pos),
                               EARTH_UNITS,
                               direction)

class NMEAGPSPosition(GPSPosition):
    """A GPSPosition initialized from a NMEA sentence"""
    def _test_checksum(self, string, csum):
        try:
            idx = string.index("*")
        except:
            print("Gps       : String does not contain '*XY' checksum")
            return False

        segment = string[1:idx]

        csum = csum.upper()
        _csum = NMEA_checksum(segment).upper()

        if csum != _csum:
            print(("Gps       : Failed checksum: %s != %s" % (csum, _csum)))

        return csum == _csum


    def _parse_GPGGA(self, string):
        elements = string.split(",", 14)
        if len(elements) < 15:
            raise Exception("Unable to split GPGGA" % len(elements))

        t = time.strftime("%m%d%y") + elements[1]
        if "." in t:
            t = t.split(".")[0]
        self.date = parse_date(t, "%m%d%y%H%M%S")

        self.latitude = nmea2deg(float(elements[2]), elements[3])
        self.longitude = nmea2deg(float(elements[4]), elements[5])

        print(("Gps       :  %f,%f" % (self.latitude, self.longitude)))

        self.satellites = int(elements[7])
        self.altitude = float(elements[9])

        m = re.match("^([0-9]*)(\*[A-z0-9]{2})\r?\n?(.*)$", elements[14])
        if not m:
            raise Exception("No checksum (%s)" % elements[14])

        csum = m.group(2)
        if "," in m.group(3):
            sta, com = m.group(3).split(",", 1)
            if not sta.strip().startswith("$"):
                self.station = utils.filter_to_ascii(sta.strip()[0:8])
                self.comment = utils.filter_to_ascii(com.strip()[0:20])
                self._original_comment = self.comment

        if len(self.comment) >=7 and "*" in self.comment[-3:-1]:
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
            raise Exception("Unable to split GPRMC (%i)" % len(elements))

        t = elements[1]
        d = elements[9]

        if "." in t:
            t = t.split(".", 2)[0]

        self.date = parse_date(d+t, "%d%m%y%H%M%S")

        self.latitude = nmea2deg(float(elements[3]), elements[4])
        self.longitude = nmea2deg(float(elements[5]), elements[6])

        self.speed = float(elements[7])
        self.direction = float(elements[8])

        if "*" in elements[11]:
            end = 11 # NMEA <=2.0
        elif "*" in elements[12]:
            end = 12 # NMEA 2.3
        else:
            raise Exception("GPRMC has no checksum in 12 or 13")

        m = re.match("^.?(\*[A-z0-9]{2})", elements[end])
        if not m:
            print(("Gps       :  Invalid end: %s" % elements[end]))
            return

        csum = m.group(1)
        if "," in station:
            sta, com = station.split(",", 1)
            self.station = utils.filter_to_ascii(sta.strip())
            self.comment = utils.filter_to_ascii(com.strip())
            self._original_comment = self.comment

        if len(self.comment) >= 7 and "*" in self.comment[-3:-1]:
            self._parse_dprs_comment()

        if elements[2] != "A":
            self.valid = False
            print(("Gps       : GPRMC marked invalid by GPS (%s)" % elements[2]))
        else:
            print("Gps       : GPRMC is valid")
            self.valid = self._test_checksum(string, csum)

    def _from_NMEA_GPGGA(self, string):
        string = string.replace('\r', ' ')
        string = string.replace('\n', ' ') 
        try:
            self._parse_GPGGA(string)
        except Exception as e:
            import traceback
            import sys
            traceback.print_exc(file=sys.stdout)
            print(("Gps       : Invalid GPS data: %s" % e))
            self.valid = False

    def _from_NMEA_GPRMC(self, string):
        try:
            self._parse_GPRMC(string)
        except Exception as e:
            import traceback
            import sys
            traceback.print_exc(file=sys.stdout)
            print(("Gps       : Invalid GPS data: %s" % e))
            self.valid = False

    def __init__(self, sentence, station=_("UNKNOWN")):
        GPSPosition.__init__(self)

        if sentence.startswith("$GPGGA"):
            self._from_NMEA_GPGGA(sentence)
        elif sentence.startswith("$GPRMC"):
            self._from_NMEA_GPRMC(sentence)
        else:
            print(("Gps       : Unsupported GPS sentence type: %s" % sentence))

class APRSGPSPosition(GPSPosition):
    def _parse_date(self, string):
        prefix = string[0]
        suffix = string[-1]
        digits = string[1:-1]

        if suffix == "z":
            ds = digits[0:2] + \
                time.strftime("%m%y", time.gmtime()) + \
                digits[2:] + "00"
        elif suffix == "/":
            ds = digits[0:2] + time.strftime("%m%y") + digits[2:] + "00"
        elif suffix == "h":
            ds = time.strftime("%d%m%y", time.gmtime()) + digits
        else:
            print(("Gps       : Unknown APRS date suffix: `%s'" % suffix))
            return datetime.datetime.now()

        d = parse_date(ds, "%d%m%y%H%M%S")

        if suffix in "zh":
            delta = datetime.datetime.utcnow() - datetime.datetime.now()
        else:
            delta = datetime.timedelta(0)

        return d - delta

    def _parse_GPSA(self, string):
        m = re.match("^\$\$CRC([A-Z0-9]{4}),(.*)$", string)
        if not m:
            return

        crc = m.group(1)
        _crc = "%04X" % GPSA_checksum(m.group(2))

        if crc != _crc:
            print(("Gps       : APRS CRC mismatch: %s != %s (%s)" % (crc, _crc, m.group(2))))
            return

        elements = string.split(",")
        if not elements[0].startswith("$$CRC"):
            print("Gps       : Missing $$CRC...")
            return

        self.station, dst = elements[1].split(">")

        path, data = elements[2].split(":")

        # 1 = Entire stamp or ! or =
        # 2 = stamp prefix
        # 3 = stamp suffix
        # 4 = latitude
        # 5 = N/S
        # 6 = symbol table
        # 7 = longitude
        # 8 = E/W
        # 9 = symbol
        #10 = comment
        #11 = altitude string
        
        expr = "^(([@/])[0-9]{6}([/hz])|!|=)" + \
            "([0-9]{1,4}\.[0-9]{2})([NS])(.)?" + \
            "([0-9]{5}\.[0-9]{2})([EW])(.)" + \
            "([^/]*)(/A=[0-9]{6})?"

        m = re.search(expr, data)
        if not m:
            print(("Gps       : Did not match GPS-A: `%s'" % data))
            return

        if m.group(1) in "!=":
            self.date = datetime.datetime.now()
        elif m.group(2) in "@/":
            self.date = self._parse_date(m.group(1))
        else:
            print(("Gps       : Unknown timestamp prefix: %s" % m.group(1)))
            self.date = datetime.datetime.now()

        self.latitude = nmea2deg(float(m.group(4)), m.group(5))
        self.longitude = nmea2deg(float(m.group(7)), m.group(8))
        self.comment = m.group(10).strip()
        self._original_comment = self.comment
        self.APRSIcon = m.group(6) + m.group(9)

        if len(m.groups()) == 11 and m.group(11):
            _, alt = m.group(11).split("=")
            self.altitude = feet2meters(int(alt))

        self.valid = True

    def _from_APRS(self, string):
        self.valid = False
        try:
            self._parse_GPSA(string)
        except Exception as e:
            print(("Gps       : Invalid APRS: %s" % e))
            return False

        return self.valid        

    def __init__(self, message):
        GPSPosition.__init__(self)

        self._from_APRS(message)

class MapImage(object):
    def __init__(self, center):
        self.key = "ABQIAAAAWot3KuWpenfCAGfQ65FdzRTaP0xjRaMPpcw6bBbU2QUEXQBgHBR5Rr2HTGXYVWkcBFNkPvxtqV4VLg"
        self.center = center
        self.markers = [center]

    def add_markers(self, markers):
        self.markers += markers

    def get_image_url(self):
        el = [ "key=%s" % self.key,
               "center=%s" % self.center.coordinates(),
               "size=400x400"]

        mstr = "markers="
        index = ord("a")
        for m in self.markers:
            mstr += "%s,blue%s|" % (m.coordinates(), chr(index))
            index += 1

        el.append(mstr)

        return "http://maps.google.com/staticmap?%s" % ("&".join(el))

    def station_table(self):
        table = ""

        index = ord('A')
        for m in self.markers:
            table += "<tr><td>%s</td><td>%s</td><td>%s</td>\n" % (\
                chr(index),
                m.station,
                m.coordinates())
            index += 1
            
        return table

    def make_html(self):
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
        f = tempfile.NamedTemporaryFile(suffix=".html")
        name = f.name
        f.close()
        f = open(name, "w")
        f.write(self.make_html())
        f.flush()
        f.close()
        p = dplatform.get_platform()
        p.open_html_file(f.name)

class GPSSource(object):
    def __init__(self, port, rate=4800):
        self.port = port
        self.enabled = False
        self.broken = None

        try:
            self.serial = serial.Serial(port=port, baudrate=rate, timeout=1)
        except Exception as e:
            print(("Gps       : Unable to open port `%s': %s" % (port, e)))
            self.broken = _("Unable to open GPS port")

        self.thread = None

        self.last_valid = False
        self.position = GPSPosition()

    def start(self):
        if self.broken:
            print("Gps       : Not starting broken GPSSource")
            return

        self.invalid = 100
        self.enabled = True
        self.thread = threading.Thread(target=self.gpsthread)
        self.thread.setDaemon(True)
        self.thread.start()

    def stop(self):
        if self.thread and self.enabled:
            self.enabled = False
            self.thread.join()
            self.serial.close()

    def gpsthread(self):
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
                        print(_("ME") + ": xxxxxxxxxxxxxxxxxxxxxxxxxxxxx %s" % self.position)
                    elif position.valid:
                        self.position = position
                    else:
                        print(("Gps       : Could not parse: %s" % line))

    def get_position(self):
        return self.position

    def status_string(self):
        if self.broken:
            return self.broken
        elif self.invalid < 10 and self.position.satellites >= 3:
            return _("GPS Locked") + " (%i sats)" % self.position.satellites
        else:
            return _("GPS Not Locked")

class NetworkGPSSource(GPSSource):
    def __init__(self, port):
        self.port = port
        self.enabled = False
        self.thread = None
        self.position = GPSPosition()
        print(("Gps       : NetworkGPSPosition: %s" % self.position))
        self.last_valid = False
        self.sock = None
        self.broken = None

    def start(self):
        self.enabled = True
        self.thread = threading.Thread(target=self.gpsthread)
        self.thread.setDaemon(True)
        self.thread.start()

    def stop(self):
        if self.thread and self.enabled:
            self.enabled = False
            self.thread.join()

    def connect(self):
        try:
            _, host, port = self.port.split(":", 3)
            port = int(port)
        except ValueError as e:
            print(("Gps       : Unable to parse %s (%s)" % (self.port, e)))
            self.broken = _("Unable to parse address")
            return False

        print(("Gps       : Connecting to %s:%i" % (host, port)))

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((host, port))
            self.sock.settimeout(10)
        except Exception as e:
            print(("Gps       : Unable to connect: %s" % e))
            self.broken = _("Unable to connect") + ": %s" % e
            self.sock = None
            return False

        self.sock.send("r\n")

        return True

    def gpsthread(self):
        while self.enabled:
            if not self.sock:
                if not self.connect():
                    time.sleep(1)
                    continue

            try:
                data = self.sock.recv(1024)
            except Exception as e:
                self.sock.close()
                self.sock = None
                print("Gps       : GPSd Socket closed")
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
                 print(("Gps       : Could not parse: %s" % line))

    def get_position(self):
        return self.position

    def status_string(self):
        if self.broken:
            return self.broken
        elif self.last_valid and self.position.satellites >= 3:
            return _("GPSd Locked") + " (%i sats)" % self.position.satellites
        else:
            return _("GPSd Not Locked")

class StaticGPSSource(GPSSource):
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
        print(("Gps       : StaticGPSPosition: %s" % self.position))
    def start(self):
        pass

    def stop(self):
        pass

    def get_position(self):
        return self.position

    def status_string(self):
        return _("Static position")

def parse_GPS(string):
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
        except Exception as e:
            print(("Gps       :  Exception during GPS parse: %s" % e))
            string = string[string.index("$")+1:]

    if not fixes:
        return None

    fix = fixes[0]
    fixes = fixes[1:]

    for extra in fixes:
        print(("Gps       : Appending fix: %s" % extra))
        fix += extra

    return fix

if __name__ == "__main__":
    nmea_strings = [
        "$GPRMC,010922,A,4603.6695,N,07307.3033,W,0.6,66.8,060508,16.1,W,A*1D\r\nVE2SE  9,MV  VE2SE@RAC.CA*32",
        "$GPGGA,203008.78,4524.9729,N,12246.9580,W,1,03,3.8,00133,M,,,,*39",
        "$GPGGA,183324.518,4533.0875,N,12254.5939,W,2,04,3.4,48.6,M,-19.6,M,1.2,0000*74",
        "$GPRMC,215348,A,4529.3672,N,12253.2060,W,0.0,353.8,030508,17.5,E,D*3C",
        "$GPGGA,075519,4531.254,N,12259.400,W,1,3,0,0.0,M,0,M,,*55\r\nK7HIO   ,GPS Info",
        "$GPRMC,074919.04,A,4524.9698,N,12246.9520,W,00.0,000.0,260508,19.,E*79",
        "$GPRMC,123449.089,A,3405.1123,N,08436.4301,W,000.0,000.0,021208,,,A*71",
        "$GPRMC,123449.089,A,3405.1123,N,08436.4301,W,000.0,000.0,021208,,,A*71\r\nKK7DS  M,LJ  DAN*C",
        "$GPRMC,230710,A,2748.1414,N,08238.5556,W,000.0,033.1,111208,004.3,W*77",
        ]
                     
    print("Gps       : -- NMEA --")
    
    for s in nmea_strings:
        p = NMEAGPSPosition(s)
        if p.valid:
            print(("Gps       : Pass: %s" % str(p)))
        else:
            print(("Gps       : ** FAIL: %s" % s))
        
    aprs_strings = [
        "$$CRCCE3E,AE5PL-T>API282,DSTAR*:!3302.39N/09644.66W>/\r",
        "$$CRC1F72,KI4IFW-1>APRATS,DSTAR*:@291930/4531.50N/12254.98W>APRS test beacon /A=000022",
        "$$CRC80C3,VA2PBI>APU25N,DSTAR*:=4539.33N/07330.28W-73 de Pierre D-Star Montreal {UIV32N}",
        "$$CRCA31F,VA2PBI>API282,DSTAR*:/221812z4526.56N07302.34W/\r",
        '$$CRCF471,AB9FT-ML>APRATS,DSTAR*:@214235h0.00S/00000.00W>ON D-RATS at Work\r',
        ]

    print("Gps       :  \n-- GPS-A --")

    for s in aprs_strings:
        p = APRSGPSPosition(s)
        if p.valid:
            print(("Gps       :  Pass: %s" % str(p)))
        else:
            print(("Gps       :  ** FAIL: %s" % s))

