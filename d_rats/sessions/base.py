#!/usr/bin/python
'''Base Session.'''
#
# Copyright 2009 Dan Smith <dsmith@danplanet.com>
# Python3 update Copyright 2021-2022 John Malmberg <wb8tyw@qsl.net>
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
import threading

from d_rats import transport

T_STATELESS = 0
T_GENERAL = 1
T_UNUSED2 = 2 # Old non-pipelined FileTransfer
T_UNUSED3 = 3 # Old non-pipelined FormTransfer
T_SOCKET = 4
T_FILEXFER = 5
T_FORMXFER = 6
T_RPC = 7

ST_OPEN = 0
ST_CLSD = 1
ST_CLSW = 2
ST_SYNC = 3


class BaseSessionException(Exception):
    '''Generic Base Session Exception.'''


class SessionClosedError(BaseSessionException):
    '''Session Closed Error.'''


class Session():
    '''
    Session.

    :param name: Name of session
    :type name: str
    '''
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

        self.stats = {"sent_size"  : 0,
                      "recv_size"  : 0,
                      "sent_wire"  : 0,
                      "recv_wire"  : 0,
                      "retries"    : 0,
                     }

    def send_blocks(self, blocks):
        '''
        Send blocks.

        Can not find anything using this.
        :param blocks: List of blocks to send
        :type blocks: list of :class:`DDT2EncodedFrame`
        '''
        # wb8tyw: stateful.py overrides this class and appears to be
        # the only user of this class.
        for block in blocks:
            self._sm.outgoing(self, block)

    def recv_blocks(self):
        '''
        Receive blocks.

        :returns: blocks received.
        :rtype: list of :class:`DDT2EncodedFrame`
        '''
        return self.inq.dequeue_all()

    def close(self, force=False):
        '''
        Close.

        :param force: True if forcing a close
        :type force: bool
        '''
        # print("Base      : Got close request")
        if force:
            self.state = ST_CLSD

        if self._sm:
            self._sm.stop_session(self)

    def notify_event(self):
        '''Notify Event Change.'''

    def read(self):
        '''Read.'''

    def write(self, dest="CQCQCQ"):
        '''
        Write.

        :param dest: Destination callsign, default='CQCQCQ'
        :type dest: str
        '''

    def set_state(self, state):
        '''
        Set state

        :param state: State to set
        :type state: int
        :returns: False if state is not legal to set
        :rtype: bool
        '''
        if state not in [ST_OPEN, ST_CLSD, ST_SYNC]:
            return False

        self.state = state
        self.state_event.set()
        self.notify_event()
        return True

    def get_state(self):
        '''
        Get state.

        :returns: state
        :rtype: int
        '''
        return self.state

    def wait_for_state_change(self, timeout=None):
        '''
        Wait for state change.

        :param timeout: default=None
        :type timeout: float
        :returns: True if the state changed.
        :rtype: bool:
        '''
        before = self.state

        self.state_event.clear()
        self.state_event.wait(timeout)

        return self.state != before

    def get_station(self):
        '''
        Get station.

        :returns station
        :rtype: str
        '''
        return self._st

    def get_name(self):
        '''
        Get name.

        :returns: name
        :rtype: str
        '''
        return self.name
