'''Sock'''
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

import logging
import socket
from threading import Thread

from d_rats.sessions import base, stateful


class SocketSession(stateful.StatefulSession):
    '''
    Socket Session.

    :param name: Session name
    :type name: str
    :param status_cb: Status call back function, Default None
    :type status_cb: function(dict)
    '''
    type = base.T_SOCKET

    IDLE_TIMEOUT = None

    def __init__(self, name, status_cb=None):
        stateful.StatefulSession.__init__(self, name)

        self.logger = logging.getLogger("SocketSession")
        if status_cb:
            self.status_cb = status_cb
        else:
            self.status_cb = self._status

    # pylint: disable=no-self-use
    def _status(self, msg):
        self.logger.info("Socket Status: %s", msg)


# pylint: disable=too-many-instance-attributes
class SocketListener():
    '''
    Socket Listener.

    :param session_mgr: SessionManager object
    :type session_mgr: :class:`SessionManager`
    :param dest: Destination to listen to
    :param dest: str
    :param sport: Source Port
    :type dport: int
    :param dport: Destination Port
    :type dport: int
    :param addr: TCP address, default='0.0.0.0'
    :type addr: str
    '''

    # pylint: disable=too-many-arguments
    def __init__(self, session_mgr, dest, sport, dport, addr='0.0.0.0'):
        # pylint: disable=invalid-name
        self.sm = session_mgr
        self.logger = logging.getLogger("SocketListener")
        self.dest = dest
        self.sport = sport
        self.dport = dport
        self.addr = addr
        self.enabled = True
        self.lsock = None
        self.dsock = None
        self.thread = Thread(target=self.listener)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        '''Stop.'''
        self.enabled = False
        self.thread.join()

    def listener(self):
        '''Listener.'''
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET,
                        socket.SO_REUSEADDR,
                        1)
        sock.settimeout(0.25)
        sock.bind(('0.0.0.0', self.sport))
        sock.listen(0)

        self.lsock = sock

        name = "TCP:%i" % self.dport

        while self.enabled:
            # pylint: disable=broad-except
            try:
                (self.dsock, addr) = sock.accept()
            except socket.timeout:
                continue
            except Exception:
                self.logger.info("listener: Socket broad exception",
                                 exc_info=True)
                self.enabled = False
                break

            self.logger.info("listener: %i: Incoming socket connection from %s",
                             self.dport, addr)

            session = self.sm.start_session(name=name,
                                            dest=self.dest,
                                            cls=SocketSession)

            while session.get_state() != base.ST_CLSD and self.enabled:
                session.wait_for_state_change(1)

            self.logger.info("listener: %s ended", name)
            self.dsock.close()
            self.dsock = None

        sock.close()
        self.logger.info("listener: TCP:%i shutdown", self.dport)
