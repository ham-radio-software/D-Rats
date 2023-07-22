'''Sessions file.py'''
#
# Copyright 2009 Dan Smith <dsmith@danplanet.com>
# Python3 update Copyright 2021-2023 John Malmberg <wb8tyw@qsl.net>
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
import struct
import os
import time
import zlib

from collections import UserDict

from d_rats.sessions import base, stateful

# This makes pylance happy with out overriding settings
# from the invoker of the class
if not '_' in locals():
    import gettext
    _ = gettext.gettext


# pylint: disable=too-many-ancestors
class NotifyDict(UserDict):
    '''
    Notify Dictionary.

    :param callback: Callback function
    :type callback: function
    :param data: data for function
    '''

    def __init__(self, callback, data=None):
        UserDict.__init__(self)
        self.callback = callback
        self.data = data

    def __setitem__(self, name, value):
        self.data[name] = value
        self.callback()


# pylint: disable=too-many-instance-attributes
class FileTransferSession(stateful.StatefulSession):
    '''
    File Transfer Session.

    :param name: Name of session
    :type name: str
    :param status_cb: Status call back, default=None
    :type status_cb: function(dict)
    :param blocksize: Blocksize, default 1024
    :type blocksize: int
    :param outlimit: Outstanding limit, default 8
    :type outlimit: int
    '''

    type = base.T_FILEXFER
    logger = logging.getLogger("FileTransferSession")

    def __init__(self, name, status_cb=None, **kwargs):
        stateful.StatefulSession.__init__(self, name, **kwargs)
        if not status_cb:
            self.status_cb = self.internal_status
        else:
            self.status_cb = status_cb

        self.sent_size = self.recv_size = 0
        self.retries = 0
        self.filename = ""

        self.last_status = ""
        self.stats = NotifyDict(self.status_tick, self.stats)
        self.stats["total_size"] = 0

    def internal_status(self, vals):
        '''
        Internal Status.

        :param vals: dict with "msg' member with status
        :type vals: dict
        '''
        self.logger.info("XFER STATUS: %s", vals["msg"])

    def status(self, msg):
        '''
        Status Message

        :param msg: Message to set as status
        :type msg: str
        '''
        vals = dict(self.stats)

        vals["msg"] = msg
        vals["filename"] = self.filename

        self.status_cb(vals)

        self.last_status = msg

    def status_tick(self):
        '''Status Tick.'''
        self.status(self.last_status)

    # pylint: disable=too-many-branches,too-many-statements
    def send_file(self, filename):
        '''
        Send a file.

        :param filename: Filename to send
        :type filename: str
        :returns: True if file transferred.
        :rtype: bool
        '''
        data = self.get_file_data(filename)
        if not data:
            return False

        base_name = os.path.basename(filename)
        try:
            fname = base_name.encode('utf-8', 'replace')
            # The offer data needs to be encoded in little endian to be
            # compatible with most existing d-rats deployment as that is
            # the native endian for x86.
            # Normal convention is to integers in network data protocols
            # to be in big-endian format.
            offer = struct.pack("<I", len(data)) + fname
            self.write(offer)
        except base.SessionClosedError:
            self.logger.info("send_file: "
                             "Session closed while sending file information")
            return False

        self.filename = base_name

        offset = None

        for _i in range(40):
            self.logger.info("send_file: Waiting for start")
            try:
                resp = self.read()
            except base.SessionClosedError:
                self.logger.info("send_file: "
                                 "Session closed while waiting for start ack")
                return False

            if not resp:
                self.status(_("Waiting for response"))
            elif resp == b"OK":
                self.status(_("Negotiation Complete"))
                offset = 0
                break
            elif resp.startswith(b"RESUME:"):
                _resume, _offset = resp.split(b":", 1)
                self.logger.info("send_file: Got RESUME request at %s",
                                 _offset)
                try:
                    offset = int(_offset)
                except ValueError:
                    self.logger.info("send_file: Unable to parse RESUME value")
                    offset = 0
                self.status(_("Resuming at") + "%i" % offset)
                break
            else:
                self.logger.info("send_file: Got unknown start: `%s'", resp)

            time.sleep(0.5)

        if offset is None:
            self.logger.info("send_file: Did not get start response")
            return False

        self.stats["total_size"] = len(data) + len(offer) - offset
        self.stats["start_time"] = time.time()

        try:
            self.status("Sending")
            self.write(data[offset:], timeout=120)
        except base.SessionClosedError:
            self.logger.info("send_file: Session closed while doing write")

        sent = self.stats["sent_size"]

        self.close()

        if sent != self.stats["total_size"]:
            self.status(_("Failed to send file (incomplete)"))
            return False
        actual = os.stat(filename).st_size
        self.stats["sent_size"] = self.stats["total_size"] = actual
        self.status(_("Complete"))
        return True

    def recv_file(self, dest_dir):
        '''
        Receive a file.

        :param dest_dir: Destination directory
        :type dest_dir: str
        :returns: filename received or None
        :rtype: str
        '''
        self.status(_("Waiting for transfer to start"))
        for _i in range(40):
            try:
                data = self.read()
            except base.SessionClosedError:
                self.logger.info("recv_file: "
                                 "Session closed while waiting for start")
                return None

            if data:
                break
            time.sleep(0.5)

        if not data:
            self.status(_("No start block received!"))
            return None

        # The size data comes in as little endian to be compatible with
        # most existing d-rats deployment as that is the native endian for x86.
        # Normal convention is to integers in network data protocols
        # to be in big-endian format.
        size, = struct.unpack("<I", data[:4])
        name = data[4:].decode('utf-8', 'replace')

        if os.path.isdir(dest_dir):
            filename = os.path.join(dest_dir, name)
        else:
            filename = dest_dir

        partfilename = filename + ".part"

        if os.path.exists(partfilename):
            # partial transfers can not be decompressed.
            data = self.get_file_partial_data(partfilename)
            offset = os.path.getsize(partfilename)
            self.logger.info("recv_file: Part file exists, resuming at %i",
                             offset)
        else:
            data = b""
            offset = 0

        self.status(_("Receiving file") + \
                        " %s " % name + \
                        _("of size") + \
                        " %i" % size)
        self.stats["recv_size"] = offset
        self.stats["total_size"] = size
        self.stats["start_time"] = time.time()

        try:
            if offset:
                self.logger.info("recv_file: Sending resume at %i", offset)
                self.write("RESUME:%i" % offset)
            else:
                self.write("OK")
        except base.SessionClosedError:
            self.logger.info("recv_file: "
                             "Session closed while sending start ack")
            return None

        self.status(_("Waiting for first block"))

        while True:
            try:
                read_data = self.read()
            except base.SessionClosedError:
                self.logger.info("recv_file: SESSION IS CLOSED")
                break

            if read_data:
                data += read_data
                self.status(_("Receiving"))

        try:
            self.put_file_data(filename, data)
            if os.path.exists(partfilename):
                self.logger.info("recv_file: Removing old file part")
                os.remove(partfilename)
        except zlib.error:
            self.logger.debug("recv_file: Failed to write transfer data",
                              exc_info=True)
            # partial data can not be decompressed
            self.put_file_partial_data(partfilename, data)
            return None

        if self.stats["recv_size"] != self.stats["total_size"]:
            self.status(_("Failed to receive file (incomplete)"))
            return None
        actual = os.stat(filename).st_size
        self.stats["recv_size"] = self.stats["total_size"] = actual
        self.status(_("Complete"))
        return filename

    @staticmethod
    def get_file_data(filename):
        '''
        Get file data amd compress it.

        :param filename: Filename to get data from
        :type filename: str
        :returns: Compressed data
        :rtype: bytes
        '''
        with open(filename, "rb") as file_handle:
            data = file_handle.read()

        return zlib.compress(data, 9)

    @staticmethod
    def get_file_partial_data(filename):
        '''
        Get file data from a previous partial transfer..

        :param filename: Filename to get data from
        :type filename: str
        :returns: data
        :rtype: bytes
        '''
        with open(filename, "rb") as file_handle:
            data = file_handle.read()
        return data

    @staticmethod
    def put_file_data(filename, zdata):
        '''
        Put file data that is compressed.

        :param filename: Filename to write
        :type filename: str
        :param zdata:  Compressed data
        :type zdata: bytes
        :raises: :class:`zlib.err` if can not decompress
        '''
        try:
            data = zlib.decompress(zdata)
            with open(filename, "wb") as file_handle:
                file_handle.write(data)
        except zlib.error as err:
            raise err

    @staticmethod
    def put_file_partial_data(filename, data):
        '''
        Put file partial data.

        :param filename: Filename to write
        :type filename: str
        :param data: data
        :type zdata: bytes
        '''
        with open(filename, "wb") as file_handle:
            file_handle.write(data)
