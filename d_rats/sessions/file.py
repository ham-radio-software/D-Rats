'''Sessions file.py'''

from __future__ import absolute_import
from __future__ import print_function

try:
    # python2
    from UserDict import UserDict
except ModuleNotFoundError:
    # python3
    from collections import UserDict

import struct
import os
import time
import zlib

from six.moves import range
from d_rats.sessions import base, stateful


# pylint: disable=too-many-ancestors
class NotifyDict(UserDict):
    '''Notify Dictionary'''

    def __init__(self, callback, data=None):
        UserDict.__init__(self)
        self.callback = callback
        self.data = data

    def __setitem__(self, name, value):
        self.data[name] = value
        self.callback()


class FileTransferSession(stateful.StatefulSession):
    '''File Transfer Session'''

    type = base.T_FILEXFER

    # pylint: disable=no-self-use
    def internal_status(self, vals):
        '''Internal Status'''
        print("XFER STATUS: %s" % vals["msg"])

    def status(self, msg):
        '''Status'''
        vals = dict(self.stats)

        vals["msg"] = msg
        vals["filename"] = self.filename

        self.status_cb(vals)

        self.last_status = msg

    def status_tick(self):
        '''Status Tick'''
        self.status(self.last_status)

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

    def get_file_data(self, filename):
        '''Get the file data'''
        print("*** get_file_data uncompressed called!")
        file_handle = open(filename, "rb")
        data = file_handle.read()
        file_handle.close()

        return data

    def put_file_data(self, filename, data):
        '''Put the file data'''
        print("*** put_file_data uncompressed called!")
        file_handle = open(filename, "wb")
        file_handle.write(data)
        file_handle.close()

    # pylint: disable=too-many-branches,too-many-statements
    def send_file(self, filename):
        '''Send a file'''
        data = self.get_file_data(filename)
        if not data:
            return False

        try:
            offer = struct.pack("I", len(data)) + os.path.basename(filename)
            self.write(offer)
        except base.SessionClosedError:
            print("Session closed while sending file information")
            return False

        self.filename = os.path.basename(filename)

        offset = None

        for _i in range(40):
            print("Waiting for start")
            try:
                resp = self.read()
            except base.SessionClosedError:
                print("Session closed while waiting for start ack")
                return False

            if not resp:
                self.status(_("Waiting for response"))
            elif resp == "OK":
                self.status(_("Negotiation Complete"))
                offset = 0
                break
            elif resp.startswith("RESUME:"):
                _resume, _offset = resp.split(":", 1)
                print("Got RESUME request at %s" % _offset)
                try:
                    offset = int(_offset)
                # pylint: disable=broad-except
                except Exception as err:
                    print("Unable to parse RESUME value: %s" % err)
                    offset = 0
                self.status(_("Resuming at") + "%i" % offset)
                break
            else:
                print("Got unknown start: `%s'" % resp)

            time.sleep(0.5)

        if offset is None:
            print("Did not get start response")
            return False

        self.stats["total_size"] = len(data) + len(offer) - offset
        self.stats["start_time"] = time.time()

        try:
            self.status("Sending")
            self.write(data[offset:], timeout=120)
        except base.SessionClosedError:
            print("Session closed while doing write")

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
        '''Receive a file'''
        self.status(_("Waiting for transfer to start"))
        for _i in range(40):
            try:
                data = self.read()
            except base.SessionClosedError:
                print("Session closed while waiting for start")
                return None

            if data:
                break
            else:
                time.sleep(0.5)

        if not data:
            self.status(_("No start block received!"))
            return None

        size, = struct.unpack("I", data[:4])
        name = data[4:]

        if os.path.isdir(dest_dir):
            filename = os.path.join(dest_dir, name)
        else:
            filename = dest_dir

        partfilename = filename + ".part"

        if os.path.exists(partfilename):
            data = self.get_file_data(partfilename)
            offset = os.path.getsize(partfilename)
            print("Part file exists, resuming at %i" % offset)
        else:
            data = ""
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
                print("Sending resume at %i" % offset)
                self.write("RESUME:%i" % offset)
            else:
                self.write("OK")
        except base.SessionClosedError:
            print("Session closed while sending start ack")
            return None

        self.status(_("Waiting for first block"))

        while True:
            try:
                read_data = self.read()
            except base.SessionClosedError:
                print("SESSION IS CLOSED")
                break

            if read_data:
                data += read_data
                self.status(_("Receiving"))

        try:
            self.put_file_data(filename, data)
            if os.path.exists(partfilename):
                print("Removing old file part")
                os.remove(partfilename)
        # pylint: disable=broad-except
        except Exception as err:
            print("Failed to write transfer data: %s" % err)
            self.put_file_data(partfilename, data)
            return None

        if self.stats["recv_size"] != self.stats["total_size"]:
            self.status(_("Failed to receive file (incomplete)"))
            return None
        actual = os.stat(filename).st_size
        self.stats["recv_size"] = self.stats["total_size"] = actual
        self.status(_("Complete"))
        return filename

    # pylint: disable=no-self-use
    def get_file_data(self, filename):
        '''Get file data Compressed'''
        print("*** get)_file_data compressed called!")
        file_handle = open(filename, "rb")
        data = file_handle.read()
        file_handle.close()

        return zlib.compress(data, 9)

    # pylint: disable=no-self-use
    def put_file_data(self, filename, zdata):
        '''Put file data compressed'''
        print("*** put_file_data compressed called!")
        try:
            data = zlib.decompress(zdata)
            file_handle = open(filename, "wb")
            file_handle.write(data)
            file_handle.close()
        except zlib.error as err:
            raise err
