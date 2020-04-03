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

import threading

from d_rats import transport

T_STATELESS = 0
T_GENERAL   = 1
T_UNUSED2   = 2 # Old non-pipelined FileTransfer
T_UNUSED3   = 3 # Old non-pipelined FormTransfer
T_SOCKET    = 4
T_FILEXFER  = 5
T_FORMXFER  = 6
T_RPC       = 7

ST_OPEN     = 0
ST_CLSD     = 1
ST_CLSW     = 2
ST_SYNC     = 3

class SessionClosedError(Exception):
    pass

class Session(object):
    _sm = None
    _id = None
    _st = None
    _rs = None
    type = None

    def __init__(self, name):
        self.name = name
        self.inq = transport.BlockQueue()
        self.handler = None
        self.state_event = threading.Event()
        self.state = ST_CLSD

        self.stats = { "sent_size"   : 0,
                       "recv_size"   : 0,
                       "sent_wire"   : 0,
                       "recv_wire"   : 0,
                       "retries"     : 0,
                       }

    def send_blocks(self, blocks):
        for b in blocks:
            self._sm.outgoing(self, b)

    def recv_blocks(self):
        return self.inq.dequeue_all()

    def close(self, force=False):
        print "Got close request"
        if force:
            self.state = ST_CLSD

        if self._sm:
            self._sm.stop_session(self)

    def notify(self):
        pass

    def read(self):
        pass

    def write(self, dest="CQCQCQ"):
        pass

    def set_state(self, state):
        if state not in [ST_OPEN, ST_CLSD, ST_SYNC]:
            return False

        self.state = state
        self.state_event.set()
        self.notify()

    def get_state(self):
        return self.state
    
    def wait_for_state_change(self, timeout=None):
        before = self.state

        self.state_event.clear()
        self.state_event.wait(timeout)

        return self.state != before

    def get_station(self):
        return self._st

    def get_name(self):
        return self.name
