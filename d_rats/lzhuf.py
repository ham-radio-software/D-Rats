'''lzhuf module.'''
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
import os
import tempfile
import struct
import subprocess
import sys

from d_rats import crc_checksum
from d_rats.dplatform import Platform


class Lzhuf():
    '''Lzhuf.'''

    logger = logging.getLogger("Lzhuf")
    lzhuf_path = None

    @classmethod
    def _set_lzhuf_path(cls):
        if cls.lzhuf_path:
            return
        cls.lzhuf_path = Platform.get_exe_path('lzhuf')

    @classmethod
    @property
    def have_lzhuf(cls):
        '''
        Have lzhuf?

        Do we have the lzhuf executable?
        :returns: True if we have lzhuf
        :rtype: bool
        '''
        cls._set_lzhuf_path()
        if cls.lzhuf_path:
            return True
        return False

    @classmethod
    def _run(cls, cmd, data):
        '''
        Run lzhuf internal.

        :param cmd: lzhuf command
        :type cmd: str
        :param data: Data to process
        :type data: bytes
        :returns: Processed data
        :rtype: bytes
        '''
        cls._set_lzhuf_path()
        if not cls.lzhuf_path:
            cls.logger.info("lzhuf binary not found")
            return None
        tmp_dir = tempfile.mkdtemp()

        with open(os.path.join(tmp_dir, "input"), "wb") as file_handle:
            file_handle.write(data)

        kwargs = {}
        if sys.platform == 'win32':
            child = subprocess.STARTUPINFO()
            child.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            child.wShowWindow = subprocess.SW_HIDE
            kwargs["startupinfo"] = child

        run = [cls.lzhuf_path, cmd, "input", "output"]

        cls.logger.info("Running %s in %s", run, tmp_dir)

        ret = subprocess.call(run, cwd=tmp_dir, **kwargs)
        cls.logger.info("LZHUF returned %s", ret)
        if ret:
            return None

        with open(os.path.join(tmp_dir, "output"), "rb") as file_handle:
            data = file_handle.read()

        return data

    @classmethod
    def decode(cls, data):
        '''
        Run LZHUF Decode.

        :param data: Encoded data
        :type data: bytes
        :returns: Uncompressed data
        :rtype: bytes
        '''
        return cls._run("d", data[2:])

    @classmethod
    def encode(cls, data):
        '''
        Run LZHUF Encode.

        :param data: Unencoded data
        :type data: bytes
        :returns: Compressed data
        :rtype: bytes
        '''
        lzh = cls._run("e", data)
        if lzh:
            lzh = struct.pack("<H", crc_checksum.calc_checksum(lzh)) + lzh
        else:
            cls.logger.info('encode: lzhuf returned no data')
        return lzh


def main():
    '''Unit Test.'''

    logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
                        datefmt="%m/%d/%Y %H:%M:%S",
                        level=logging.INFO)

    logger = logging.getLogger("lzhuf_test")
    logger.info("Starting test")
    in_data = b'uncompressed'
    encoded = Lzhuf.encode(in_data)
    if encoded:
        decoded = Lzhuf.decode(encoded)
        print("in_data=", in_data)
        print("decoded=", decoded)
        if decoded != in_data:
            logger.info("Sanity test failed!")
        else:
            logger.info("Sanity test passed!")
    else:
        logger.info("Sanity test lzhuf not found!")

if __name__ == "__main__":
    main()
