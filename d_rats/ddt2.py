#!/usr/bin/python
'''ddt2'''
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

from __future__ import absolute_import
from __future__ import print_function

import struct
import zlib
# import base64
import sys

import threading

from six.moves import range

from . import yencode
from . import utils

#importing printlog() wrapper
from .debug import printlog

ENCODED_HEADER = b"[SOB]"
ENCODED_TRAILER = b"[EOB]"


def update_crc(c_byte, crc):
    '''
    Update the CRC.

    :param c_byte: Character byte to add
    :param crc: CRC to update
    :returns: 16 bit CRC
    '''
    # python 2 compatibility hack
    if isinstance(c_byte, str):
        c_byte = ord(c_byte)
    for _ in range(0, 8):
        c_byte <<= 1

        if (c_byte & 0o400) != 0:
            value = 1
        else:
            value = 0

        if crc & 0x8000:
            crc <<= 1
            crc += value
            crc ^= 0x1021
        else:
            crc <<= 1
            crc += value

    return crc & 0xFFFF


def calc_checksum(data):
    '''
    Calculate a checksum

    :param data: Data to checksum
    :returns: checksum
    '''
    checksum = 0
    for i in data:
        checksum = update_crc(i, checksum)

    checksum = update_crc(0, checksum)
    checksum = update_crc(0, checksum)
    return checksum


def encode(data):
    '''
    yencode data.

    :param data: Data to encode
    :returns: encoded data
    '''
    return yencode.yencode_buffer(data)


def decode(data):
    '''
    ydecode data.

    :param data: Data to decode
    :returns: decoded data
    '''
    return yencode.ydecode_buffer(data)


# pylint: disable=too-many-instance-attributes
class DDT2Frame():
    '''DDT2 Frame'''

    format = "!BHBBHH8s8s"
    cso = 6
    csl = 2

    def __init__(self):
        self.seq = 0
        self.session = 0
        self.type = 0
        self.d_station = ""
        self.s_station = ""
        self.data = b""
        self.magic = 0xDD

        self.sent_event = threading.Event()
        self.ackd_event = threading.Event()

        self.compress = True

        self._xmit_s = 0
        self._xmit_e = 0
        self._xmit_z = 0

    def get_xmit_bps(self):
        '''
        Get Transmit bps

        :returns: bps value
        '''
        if not self._xmit_e:
            printlog("Ddt2", "      : Block not sent, can't determine BPS!")
            return 0

        if self._xmit_s == self._xmit_e:
            return self._xmit_z * 100 # Fudge for sockets

        return self._xmit_z / (self._xmit_e - self._xmit_s)

    def set_compress(self, compress=True):
        '''
        set compression.

        :params compress: Default True for compressed data
        '''
        self.compress = compress

    def get_packed(self):
        '''
        get packed data

        :returns: packed data
        '''
        data = self.data
        # python2 zlib.compress needs a string
        # python3 zlib.compress needs a bytearray
        # data should always be a bytearray, but we can not guarantee that
        # at this time.
        if sys.version_info[0] == 2:
            if not isinstance(self.data, str):
                data = str(self.data)
        else:
            if isinstance(data, str):
                # ISO-8859-1 is 8 bit tolerant and should be builtin.
                data = self.data.encode('ISO-8859-1')
        if self.compress:
            data = zlib.compress(data, 9)
        else:
            self.magic = (~self.magic) & 0xFF

        length = len(data)

        if sys.version_info[0] > 2:
            s_sta = self.s_station
            d_sta = self.d_station
            if isinstance(self.s_station, str):
                s_sta = self.s_station.encode('ISO-8859-1')
            if isinstance(self.d_station, str):
                d_sta = self.d_station.encode('ISO-8859-1')
            s_station = bytearray(s_sta.ljust(8, b"~"))
            d_station = bytearray(d_sta.ljust(8, b"~"))
        else:
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
        '''
        unpack a frame

        :param val: Frame to unpack
        :returns: True if frame unpacked
        '''
        magic = val[0]
        # python2 compatibility hack
        if isinstance(magic, str):
            magic = ord(val[0])
        if magic == 0xDD:
            self.compress = True
        elif magic == 0x22:
            self.compress = False
        else:
            printlog(("Ddt2      : Magic 0x%X not recognized" % magic))
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
        self.s_station = self.s_station.replace(b"~", b"")
        self.d_station = self.d_station.replace(b"~", b"")

        if _checksum != checksum:
            printlog("Ddt2",
                     "      : Checksum failed: %s != %s" %
                     (checksum, _checksum))
            return False

        if self.compress:
            if sys.version_info[0] > 2:
                self.data = zlib.decompress(data)
            else:
                comp_data = zlib.decompress(str(data))
                self.data = bytearray(comp_data)
        else:
            self.data = data

        return True

    def __str__(self):
        if self.compress:
            code = "+"
        else:
            code = "-"

        # data = utils.filter_to_ascii(self.data[:20])
        # tolto il limite dei 20 caratteri
        data = utils.filter_to_ascii(self.data)
        # printlog("-----------" #)
        # printlog("Ddt2      : DDT2%s: %i:%i:%i %s->%s (%s...[%i])" % (c,
        #                                                self.seq,
        #                                                self.session,
        #                                                self.type,
        #                                                self.s_station,
        #                                                self.d_station,
        #                                                data,
        #                                                len(self.data))

        return "DDT2%s: %i:%i:%i %s->%s (%s...[%i])" % (code,
                                                        self.seq,
                                                        self.session,
                                                        self.type,
                                                        self.s_station,
                                                        self.d_station,
                                                        data,
                                                        len(self.data))

    def get_copy(self):
        '''
        Get a copy of the frame.

        :returns: copy of the frame
        '''
        frame = self.__class__()
        frame.seq = self.seq
        frame.session = self.session
        frame.type = self.type
        frame.s_station = self.s_station
        frame.d_station = self.d_station
        frame.data = self.data
        frame.set_compress(self.compress)
        return frame


class DDT2EncodedFrame(DDT2Frame):
    '''DDT2 Encoded Frame'''

    def get_packed(self):
        '''
        Get packed frame.

        :returns: Returns encoded frame
        '''
        raw = DDT2Frame.get_packed(self)

        encoded = encode(raw)

        return ENCODED_HEADER + encoded + ENCODED_TRAILER

    def unpack(self, val):
        '''
        unpack frame.

        :param val: Frame to unpack
        :returns: Unpacked frame or False if can not unpack frame
        '''
        try:
            if (sys.version_info[0] > 2) and isinstance(val, str):
                val = val.encode('ISO-8859-1')

            h_index = val.index(ENCODED_HEADER) + len(ENCODED_TRAILER)
            t_index = val.rindex(ENCODED_TRAILER)
            payload = val[h_index:t_index]
        # pylint: disable=broad-except
        except Exception as err:
            printlog("Ddt2      : Block has no header/trailer: %s" % err)
            return False

        try:
            decoded = decode(payload)
        # pylint: disable=broad-except
        except Exception as err:
            printlog("Ddt2      : Unable to decode frame: %s" % err)
            return False

        return DDT2Frame.unpack(self, decoded)


class DDT2RawData(DDT2Frame):
    '''DDT2 Raw Data'''

    def get_packed(self):
        '''
        Get packed raw data.
        :returns: data
        '''
        return self.data

    def unpack(self, _string):
        '''
        unpack raw data.

        :param _string: Unused
        :returns: data
        '''
        return self.data

def test_symmetric(compress=True):
    '''
    Test Symmetric operations.

    :param compress: Test with compression
    '''
    fin = DDT2EncodedFrame()
    fin.type = 1
    fin.session = 2
    fin.seq = 3
    fin.s_station = "FOO"
    fin.d_station = "BAR"
    fin.data = b"This is a test"
    fin.set_compress(compress)
    packed_frame = fin.get_packed()

    printlog(("Ddt2      :%s" % packed_frame))

    fout = DDT2EncodedFrame()
    fout.unpack(packed_frame)

    #printlog((fout.__dict__)
    printlog(("Ddt2      :%s" % fout))

def test_crap():
    '''Test routine'''
    frame = DDT2EncodedFrame()
    try:
        if frame.unpack(b"[SOB]foobar[EOB]"):
            printlog("Ddt2", "      : FAIL")
        else:
            printlog("Ddt2", "      : PASS")
    # pylint: disable=broad-except
    except Exception as err:
        printlog("Generic Exception %s %s" % (type(err), err))
        printlog("Ddt2", "      : PASS")

if __name__ == "__main__":
    test_symmetric()
    test_symmetric(False)
    test_crap()
