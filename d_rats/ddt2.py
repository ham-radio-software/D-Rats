'''ddt2'''
#
# Copyright 2008 Dan Smith <dsmith@danplanet.com>
# Copyright 2021-2022 John. E. Malmberg - Python3 Conversion
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

import logging
import struct
import zlib
import sys
import threading

from .crc_checksum import calc_checksum
from . import yencode
from . import utils

ENCODED_HEADER = b"[SOB]"
ENCODED_TRAILER = b"[EOB]"


def encode(data):
    '''
    yencode data.

    :param data: Data to encode
    :type data: bytes
    :returns: encoded data
    :rtype: bytes
    '''
    # :type data: str for python2
    return yencode.yencode_buffer(data)


def decode(data):
    '''
    ydecode data.

    :param data: Data to decode
    :type data: bytes
    :returns: decoded data
    :rtype: bytes
    '''
    # :type data: bytearray for python2
    return yencode.ydecode_buffer(data)


# pylint wants a max of 7 instance attributes
# pylint: disable=too-many-instance-attributes
class DDT2Frame():
    '''DDT2 Frame'''

    format = "!BHBBHH8s8s"
    cso = 6
    csl = 2

    def __init__(self):
        self.logger = logging.getLogger("DDT2Frame")
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
        :rtype: float
        '''
        if not self._xmit_e:
            self.logger.info("get_xmit_bps: Block not sent, "
                             "can't determine BPS!")
            return 0

        if self._xmit_s == self._xmit_e:
            return self._xmit_z * 100 # Fudge for sockets

        return self._xmit_z / (self._xmit_e - self._xmit_s)

    def set_compress(self, compress=True):
        '''
        set compression.

        :params compress: Default True for compressed data
        :type compress: bool
        '''
        self.compress = compress

    def get_packed(self):
        '''
        get packed data

        :returns: packed data
        :rtype: bytes
        '''
        # :rtype: str for python2
        data = self.data
        # python2 zlib.compress needs a str type
        # python3 zlib.compress needs a bytes type
        # data should always be a bytes, but we can not guarantee that
        # at this time.
        if sys.version_info[0] == 2:
            if not isinstance(self.data, str):
                data = str(self.data)
        else:
            if isinstance(data, str):
                data = self.data.encode('utf-8', 'replace')
        if self.compress:
            data = zlib.compress(data, 9)
        else:
            self.magic = (~self.magic) & 0xFF

        length = len(data)

        # self.s_station/d_station need to be str type
        # On python 3, struct needs them to byte type,
        # so we need to convert them.
        if sys.version_info[0] > 2:
            s_sta = self.s_station
            d_sta = self.d_station
            if isinstance(self.s_station, str):
                s_sta = self.s_station.encode('utf-8', 'replace')
            if isinstance(self.d_station, str):
                d_sta = self.d_station.encode('utf-8', 'replace')
            s_station = bytes(s_sta.ljust(8, b"~"))
            d_station = bytes(d_sta.ljust(8, b"~"))
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

        self.logger.debug("get_packed: seq:%s session:%s type:%s",
                          self.seq, self.session, self.type)
        # utils.hexprintlog(val)
        # if self.session == 0 and self.type not in [1, 2]:
        #    traceback.print_stack()

        self._xmit_z = len(val) + len(data)

        return val + data

    # pylint wants a max of 12 branches
    # pylint: disable=too-many-branches
    def unpack(self, val):
        '''
        unpack a frame

        :param val: Frame to unpack
        :type val: bytes
        :returns: True if frame unpacked
        :rtype: bool
        '''
        # :type val: bytearray for python2
        magic = val[0]
        # python2 compatibility hack
        if isinstance(magic, str):
            magic = ord(val[0])
        if magic == 0xDD:
            self.compress = True
        elif magic == 0x22:
            self.compress = False
        else:
            self.logger.info("unpack: Magic 0x%X not recognized", magic)
            return False

        header = val[:25]
        data = val[25:]

        (magic, self.seq, self.session, self.type,
         checksum, length,
         s_station, d_station) = struct.unpack(self.format, header)
        self.logger.debug("unpack: seq:%s session:%s type:%s",
                          self.seq, self.session, self.type)
        # utils.hexprintlog(header)
        in_header = struct.pack(self.format,
                                magic,
                                self.seq,
                                self.session,
                                self.type,
                                0,
                                length,
                                s_station,
                                d_station)

        in_checksum = calc_checksum(in_header + data)

        s_station = s_station.replace(b"~", b"")
        d_station = d_station.replace(b"~", b"")
        if isinstance(s_station, str):
            self.s_station = s_station
        else:
            self.s_station = s_station.decode('utf-8', 'replace')
        if isinstance(d_station, str):
            self.d_station = d_station
        else:
            self.d_station = d_station.decode('utf-8', 'replace')

        if in_checksum != checksum:
            self.logger.info("unpack: Checksum failed: %s != %s",
                             checksum, in_checksum)
            return False

        if self.compress:
            if sys.version_info[0] > 2:
                self.data = zlib.decompress(data)
            else:
                comp_data = zlib.decompress(str(data))
                self.data = bytes(comp_data)
        else:
            self.data = data

        return True

    def __str__(self):
        if self.compress:
            code = "+"
        else:
            code = "-"

        # data = utils.filter_to_ascii(self.data[:20])
        # former limit of first 20 characters
        data = utils.filter_to_ascii(self.data)
        # self.logger.info("-----------")
        # self.logger.info("DDT2%s: %i:%i:%i %s->%s (%s...[%i])" c,
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
        :rtype: :class:`DDT2Frame`
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

    def __init__(self):
        DDT2Frame.__init__(self)
        self.logger = logging.getLogger("DDT2EncodedFrame")

    def get_packed(self):
        '''
        Get packed frame.

        :returns: Returns encoded frame
        :rtype: bytes
        '''
        raw = DDT2Frame.get_packed(self)

        encoded = encode(raw)

        return ENCODED_HEADER + encoded + ENCODED_TRAILER

    def unpack(self, val):
        '''
        unpack frame.

        :param val: Frame to unpack
        :type val: bytes
        :returns: False if can not unpack frame
        :rtype: bool
        '''
        try:
            if (sys.version_info[0] > 2) and isinstance(val, str):
                val = val.encode('utf-8', 'replace')

            h_index = val.index(ENCODED_HEADER) + len(ENCODED_TRAILER)
            t_index = val.rindex(ENCODED_TRAILER)
            payload = val[h_index:t_index]
        except ValueError:
            self.logger.info("unpack: Block has no header/trailer",
                             exc_info=True)
            return False

        decoded = decode(payload)
        return DDT2Frame.unpack(self, decoded)


class DDT2RawData(DDT2Frame):
    '''DDT2 Raw Data'''

    def __init__(self):
        DDT2Frame.__init__(self)
        self.logger = logging.getLogger("DDT2RawFrame")

    def get_packed(self):
        '''
        Get packed raw data.
        :returns: data
        :rtype: bytes
        '''
        return self.data

    def unpack(self, _val):
        '''
        unpack raw data.

        :param _val: Unused
        :type _val: bytes
        :returns: data
        :rtype: bytes
        '''
        # WB8TYW: This appears to be broken.
        # the data member is directly updated to it appears to work
        # once the data is populated, it will be interpreted as a true value.
        return self.data


def test_symmetric(logger, compress=True):
    '''
    Test Symmetric operations.

    :param logger: Logger object
    :type logger: :class:`logging.Logger`
    :param compress: Test with compression
    :type compress: bool
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
    logger.info("packed_frame: %s", packed_frame)

    fout = DDT2EncodedFrame()
    fout.unpack(packed_frame)

    # logger.info(fout.__dict__)
    logger.info("fout: %s", fout)


def test_crap(logger):
    '''
    Test routine.

    :param logger: Logger object
    :type logger: :class:`Logger`
    '''
    frame = DDT2EncodedFrame()
    if frame.unpack(b"[SOB]foobar[EOB]"):
        logger.info("FAIL")
    else:
        logger.info("PASS")


def main():
    '''Unit Test.'''
    logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
                        level=logging.INFO)
    logger = logging.getLogger("DDT2.test")
    test_symmetric(logger)
    test_symmetric(logger, True)
    test_crap(logger)

if __name__ == "__main__":
    main()
