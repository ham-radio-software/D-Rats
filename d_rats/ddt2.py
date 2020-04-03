#!/usr/bin/python
#
# Copyright 2008 Dan Smith <dsmith@danplanet.com>
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

import struct
import zlib
import base64
import yencode

import threading

import utils

ENCODED_HEADER = "[SOB]"
ENCODED_TRAILER = "[EOB]"

   
    
def update_crc(c, crc):
    for _ in range(0,8):
        c <<= 1

        if (c & 0400) != 0:
            v = 1
        else:
            v = 0
            
        if (crc & 0x8000):
            crc <<= 1
            crc += v
            crc ^= 0x1021
        else:
            crc <<= 1
            crc += v

    return crc & 0xFFFF

def calc_checksum(data):
    checksum = 0
    for i in data:
        checksum = update_crc(ord(i), checksum)

    checksum = update_crc(0, checksum)
    checksum = update_crc(0, checksum)

    return checksum

def encode(data):
    return yencode.yencode_buffer(data)

def decode(data):
    return yencode.ydecode_buffer(data)

class DDT2Frame(object):
    format = "!BHBBHH8s8s"
    cso = 6
    csl = 2

    def __init__(self):
        self.seq = 0
        self.session = 0
        self.type = 0
        self.d_station = ""
        self.s_station = ""
        self.data = ""
        self.magic = 0xDD

        self.sent_event = threading.Event()
        self.ackd_event = threading.Event()

        self.compress = True

        self._xmit_s = 0
        self._xmit_e = 0
        self._xmit_z = 0

    def get_xmit_bps(self):
        if not self._xmit_e:
            print "Ddt2      : Block not sent, can't determine BPS!"
            return 0

        if self._xmit_s == self._xmit_e:
            return self._xmit_z * 100 # Fudge for sockets

        return self._xmit_z / (self._xmit_e - self._xmit_s)

    def set_compress(self, compress=True):
        self.compress = compress

    def get_packed(self):
        if self.compress:
            data = zlib.compress(self.data, 9)
        else:
            data = self.data
            self.magic = (~self.magic) & 0xFF

        length = len(data)
        
        s_station = self.s_station.ljust(8, "~")
        d_station = self.d_station.ljust(8, "~")

        val = struct.pack(self.format,
                          self.magic,
                          self.seq,
                          self.session,
                          self.type,
                          0,
                          length,
                          s_station,
                          d_station)

        checksum = calc_checksum(val + data)

        val = struct.pack(self.format,
                          self.magic,
                          self.seq,
                          self.session,
                          self.type,
                          checksum,
                          length,
                          s_station,
                          d_station)

        self._xmit_z = len(val) + len(data)

        return val + data

    def unpack(self, val):
        magic = ord(val[0])
        if magic == 0xDD:
            self.compress = True
        elif magic == 0x22:
            self.compress = False
        else:
            print "Ddt2      : Magic 0x%X not recognized" % magic
            return False

        header = val[:25]
        data = val[25:]

        (magic, self.seq, self.session, self.type,
         checksum, length,
         self.s_station, self.d_station) = struct.unpack(self.format, header)

        _header = struct.pack(self.format,
                              magic,
                              self.seq,
                              self.session,
                              self.type,
                              0,
                              length,
                              self.s_station,
                              self.d_station)

        _checksum = calc_checksum(_header + data)

        self.s_station = self.s_station.replace("~", "")
        self.d_station = self.d_station.replace("~", "")

        if _checksum != checksum:
            print "Ddt2      : Checksum failed: %s != %s" % (checksum, _checksum)
            return False

        if self.compress:
            self.data = zlib.decompress(data)
        else:
            self.data = data

        return True

    def __str__(self):
        if self.compress:
            c = "+"
        else:
            c = "-"

        #data = utils.filter_to_ascii(self.data[:20]) #tolto il limite dei 20 caratteri 
        data = utils.filter_to_ascii(self.data)
        #print "-----------" #
        #print "Ddt2      : DDT2%s: %i:%i:%i %s->%s (%s...[%i])" % (c,
        #                                                self.seq,
        #                                                self.session,
        #                                                self.type,
        #                                                self.s_station,
        #                                                self.d_station,
        #                                                data,
        #                                                len(self.data))
        
        return "DDT2%s: %i:%i:%i %s->%s (%s...[%i])" % (c,
                                                        self.seq,
                                                        self.session,
                                                        self.type,
                                                        self.s_station,
                                                        self.d_station,
                                                        data,
                                                        len(self.data))


    def get_copy(self):
        f = self.__class__()
        f.seq = self.seq
        f.session = self.session
        f.type = self.type
        f.s_station = self.s_station
        f.d_station = self.d_station
        f.data = self.data
        f.set_compress(self.compress)
        return f

class DDT2EncodedFrame(DDT2Frame):
    def get_packed(self):
        raw = DDT2Frame.get_packed(self)

        encoded = encode(raw)

        return ENCODED_HEADER + encoded + ENCODED_TRAILER

    def unpack(self, val):
        try:
            h = val.index(ENCODED_HEADER) + len(ENCODED_TRAILER)
            t = val.rindex(ENCODED_TRAILER)
            payload = val[h:t]
        except Exception, e:
            print "Ddt2      : Block has no header/trailer: %s" % e
            return False

        try:
            decoded = decode(payload)
        except Exception, e:
            print "Ddt2      : Unable to decode frame: %s" % e
            return False

        return DDT2Frame.unpack(self, decoded)

class DDT2RawData(DDT2Frame):
    def get_packed(self):
        return self.data

    def unpack(self, string):
        return self.data

def test_symmetric(compress=True):
    fin = DDT2EncodedFrame()
    fin.type = 1
    fin.session = 2
    fin.seq = 3
    fin.s_station = "FOO"
    fin.d_station = "BAR"
    fin.data = "This is a test"
    fin.set_compress(compress)
    p = fin.get_packed()

    print p

    fout = DDT2EncodedFrame()
    fout.unpack(p)

    #print fout.__dict__
    print fout

def test_crap():
    f = DDT2EncodedFrame()
    try:
        if f.unpack("[SOB]foobar[EOB]"):
            print "FAIL"
        else:
            print "PASS"
    except Exception, e:
        print "PASS"

if __name__ == "__main__":
    test_symmetric()
    test_symmetric(False)
    test_crap()
