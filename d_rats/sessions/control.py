#!/usr/bin/python
'''Control'''
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
import struct

from d_rats.utils import log_exception
from d_rats.ddt2 import DDT2EncodedFrame
from d_rats.sessions import base, stateful
from d_rats.sessions import file, form, sock


T_PNG = 0
T_END = 1
T_ACK = 2
T_NEW = 3


class ControlSession(base.Session):
    '''Control Session.'''

    stateless = True

    def __init__(self):
        base.Session.__init__(self, "control")
        self.logger = logging.getLogger("ControlSession")
        self.handler = self.ctl

        self.stypes = {T_NEW + base.T_GENERAL  : stateful.StatefulSession,
                       T_NEW + base.T_FILEXFER : file.FileTransferSession,
                       T_NEW + base.T_FORMXFER : form.FormTransferSession,
                       T_NEW + base.T_SOCKET   : sock.SocketSession,
                       }

    def ack_req(self, dest, data):
        '''
        Ack Request

        :param dest: Destination Callsign
        :type dest: str
        :param data: Data for frame
        '''
        frame = DDT2EncodedFrame()
        frame.type = T_ACK
        frame.seq = 0
        frame.d_station = dest
        if isinstance(data, str):
            frame.data = data.encode('utf-8', 'replace')
        else:
            frame.data = data
        self._sm.outgoing(self, frame)

    def ctl_ack(self, frame):
        '''
        Control Ack.

        :param frame: Frame of data
        :type frame: :class:`DDT2Frame`
        '''
        try:
            local_session, remote_session = struct.unpack("BB", frame.data)
            session = self._sm.sessions[local_session]
            # pylint: disable=protected-access
            session._rs = remote_session
            self.logger.info("ctl_ack: "
                             "Signaled waiting session thread (l=%i r=%i)",
                             local_session, remote_session)
        # pylint: disable=broad-except
        except Exception:
            self.logger.info("ctl_ack: "
                             "Failed to lookup new session event",
                             exc_info=True)

        if session.get_state() == base.ST_CLSW:
            session.set_state(base.ST_CLSD)
        elif session.get_state() == base.ST_OPEN:
            pass
        elif session.get_state() == base.ST_SYNC:
            session.set_state(base.ST_OPEN)
        else:
            self.logger.info("ctl_ack: "
                             "ACK for session in invalid state: %i",
                             session.get_state())

    def ctl_end(self, frame):
        '''
        Control End.

        :param frame: Frame object
        :type frame: :class:`DDT2Frame`
        '''
        self.logger.debug("ctl_end: End of session %s", frame.data)

        try:
            ident = int(frame.data)
        # pylint: disable=broad-except
        except Exception:
            self.logger.info("ctl_end: "
                             "Session end request had invalid ID",
                             exc_info=True)
            return

        try:
            session = self._sm.sessions[ident]
            session.set_state(base.ST_CLSD)
            self._sm.stop_session(session)
        # pylint: disable=broad-except
        except Exception:
            self.logger.info("ctl_end: "
                             "Session %s ended but not registered",
                             ident, exc_info=True)
            return

        frame.d_station = frame.s_station
        # pylint: disable=protected-access
        if session._rs:
            # pylint: disable=protected-access
            frame.data = str(session._rs).encode('utf-8', 'replace')
        else:
            # pylint: disable=protected-access
            frame.data = str(session._id).encode('utf-8', 'replace')
        self._sm.outgoing(self, frame)

    def ctl_new(self, frame):
        '''
        Control New.

        :param frame: Frame object
        :type frame: :class:`DDT2Frame`
        '''
        try:
            (ident,) = struct.unpack("B", frame.data[:1])
            name = frame.data[1:].decode('utf-8', 'replace')
        # pylint: disable=broad-except
        except Exception:
            self.logger.info("ctl_new: "
                             "Session request had invalid ID", exc_info=True)
            return

        self.logger.info("ctl_new: New session %i from remote", ident)

        exist = self._sm.get_session(rid=ident, rst=frame.s_station)
        if exist:
            # pylint: disable=protected-access
            self.logger.info("ctl_new: "
                             "Re-sending ACK for existing session %s:%i:%i",
                             frame.s_station, ident, exist._id)
            self.ack_req(frame.s_station, struct.pack("BB", ident, exist._id))
            return

        self.logger.info("ctl_new: sending ACK for session request for %i",
                         ident)

        try:
            c_type = self.stypes[frame.type]
            self.logger.info("ctl_new: Got type: %s", c_type)
            station = c_type(name)
            # pylint: disable=protected-access
            station._rs = ident
            station.set_state(base.ST_OPEN)
        # pylint: disable=broad-except
        except Exception:
            log_exception()
            self.logger.info("ctl_new: Can't start session type `%s'",
                             frame.type, exc_info=True)
            return

        # pylint: disable=protected-access
        num = self._sm._register_session(station, frame.s_station, "new,in")

        data = struct.pack("BB", ident, num)
        self.ack_req(frame.s_station, data)

    def ctl(self, frame):
        '''
        Control.

        :param frame: Frame of data
        :type frame: :class:`DDT2Frame`
        '''
        if frame.d_station != self._sm.station:
            self.logger.info("ctl: Control ignoring frame for station %s",
                             frame.d_station)
            return

        if frame.type == T_ACK:
            self.ctl_ack(frame)
        elif frame.type == T_END:
            self.ctl_end(frame)
        elif frame.type >= T_NEW:
            self.ctl_new(frame)
        else:
            self.logger.info("ctl: Unknown control message type %i", frame.type)

    def new_session(self, session):
        '''
        New Session.

        :param session: Session object
        :type session: :class:`Session`
        :returns: True if session created
        :rtype: bool
        '''
        frame = DDT2EncodedFrame()
        frame.type = T_NEW + session.type
        frame.seq = 0
        # frame data is of type bytes with python3
        session_name = session.name.encode('utf-8', 'replace')
        # pylint: disable=protected-access
        frame.d_station = session._st
        # pylint: disable=protected-access

        frame.data = struct.pack("B", int(session._id)) + session_name

        wait_time = 5

        for _i in range(0, 10):
            self._sm.outgoing(self, frame)

            frame.sent_event.wait(10)
            frame.sent_event.clear()

            self.logger.info("new_session: Sent request, blocking...")
            session.wait_for_state_change(wait_time)

            state = session.get_state()

            if state == base.ST_CLSD:
                self.logger.info("new_session: Session is closed")
                break
            if state == base.ST_SYNC:
                self.logger.info("new_session: Waiting for synchronization")
                wait_time = 15
            else:
                # pylint: disable=protected-access
                self.logger.info("new_session: Established session %i:%i",
                                 session._id, session._rs)
                session.set_state(base.ST_OPEN)
                return True

        session.set_state(base.ST_CLSD)
        self.logger.info("new_session: Failed to establish session")
        return False

    def end_session(self, session):
        '''
        End Session.

        :param session: Session object
        :type session: :class:`Session`
        :returns: True if session is closed normally
        :rtype: bool
        '''
        if session.stateless:
            return True

        while session.get_state() == base.ST_SYNC:
            self.logger.info("end_session: Waiting for session in SYNC")
            session.wait_for_state_change(2)

        frame = DDT2EncodedFrame()
        frame.type = T_END
        frame.seq = 0
        # pylint: disable=protected-access
        frame.d_station = session._st
        # pylint: disable=protected-access
        if session._rs:
            # pylint: disable=protected-access
            frame.data = str(session._rs).encode('utf-8', 'replace')
        else:
            # pylint: disable=protected-access
            frame.data = str(session._id).encode('utf-8', 'replace')

        session.set_state(base.ST_CLSW)

        for _attempt in range(0, 3):
            self.logger.info("end_session: Sending End-of-Session")
            self._sm.outgoing(self, frame)

            frame.sent_event.wait(10)
            frame.sent_event.clear()

            self.logger.info("end_session: Sent, waiting for response")
            session.wait_for_state_change(15)

            if session.get_state() == base.ST_CLSD:
                self.logger.info("end_session: Session closed")
                return True

        session.set_state(base.ST_CLSD)
        self.logger.info("end_session: Session closed because no response")
        return False
