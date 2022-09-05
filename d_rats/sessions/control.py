#!/usr/bin/python
'''Control'''
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

from __future__ import absolute_import
from __future__ import print_function
import struct

from six.moves import range

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

    def ack_req(self, dest, data):
        '''
        Ack Request

        :param dest: Destination Callsign
        :param data: Data for frame
        '''
        frame = DDT2EncodedFrame()
        frame.type = T_ACK
        frame.seq = 0
        frame.d_station = dest
        frame.data = data
        self._sm.outgoing(self, frame)

    def ctl_ack(self, frame):
        '''
        Control Ack.

        :param frame: Frame of data
        '''
        try:
            local_session, remote_session = struct.unpack("BB", frame.data)
            session = self._sm.sessions[local_session]
            # pylint: disable=protected-access
            session._rs = remote_session
            print("Control",
                  "   : Signaled waiting session thread (l=%i r=%i)" %
                  (local_session, remote_session))
        # pylint: disable=broad-except
        except Exception as err:
            print("Control",
                  "   : Failed to lookup new session event: %s -%s-" %
                  (type(err), err))

        if session.get_state() == base.ST_CLSW:
            session.set_state(base.ST_CLSD)
        elif session.get_state() == base.ST_OPEN:
            pass
        elif session.get_state() == base.ST_SYNC:
            session.set_state(base.ST_OPEN)
        else:
            print("Control",
                  "   : ACK for session in invalid state: %i" %
                  session.get_state())

    def ctl_end(self, frame):
        '''
        Control End.

        :param frame: Frame object
        '''
        print(("Control   : End of session %s" % frame.data))

        try:
            ident = int(frame.data)
        # pylint: disable=broad-except
        except Exception as err:
            print("Control",
                  "   : Session end request had invalid ID: %s -%s-" %
                  (type(err), err))
            return

        try:
            session = self._sm.sessions[ident]
            session.set_state(base.ST_CLSD)
            self._sm.stop_session(session)
        # pylint: disable=broad-except
        except Exception as err:
            print("Control",
                  "   : Session %s ended but not registered %s -%s-" %
                  (id, type(err), err))
            return

        frame.d_station = frame.s_station
        # pylint: disable=protected-access
        if session._rs:
            # pylint: disable=protected-access
            frame.data = str(session._rs)
        else:
            # pylint: disable=protected-access
            frame.data = str(session._id)
        self._sm.outgoing(self, frame)

    def ctl_new(self, frame):
        '''
        Control New.

        :param frame: Frame object
        '''
        try:
            (ident,) = struct.unpack("B", frame.data[:1])
            name = frame.data[1:]
        # pylint: disable=broad-except
        except Exception as err:
            print("Control",
                  "   : Session request had invalid ID: %s -%s-" %
                  (type(err), err))
            return

        print("Control   : New session %i from remote" % ident)

        exist = self._sm.get_session(rid=ident, rst=frame.s_station)
        if exist:
            # pylint: disable=protected-access
            print("Control",
                  "   : Re-sending ACK for existing session %s:%i:%i" %
                  (frame.s_station, ident, exist._id))
            self.ack_req(frame.s_station, struct.pack("BB", ident, exist._id))
            return

        print("Control   : sending ACK for session request for %i" % ident)

        try:
            c_type = self.stypes[frame.type]
            print("Control   : Got type: %s" % c_type)
            station = c_type(name)
            # pylint: disable=protected-access
            station._rs = ident
            station.set_state(base.ST_OPEN)
        # pylint: disable=broad-except
        except Exception as err:
            log_exception()
            print("Control",
                  "  : Can't start session type `%s': %s -%s-" %
                  (frame.type, type(err), err))
            return

        # pylint: disable=protected-access
        num = self._sm._register_session(station, frame.s_station, "new,in")

        data = struct.pack("BB", id, num)
        self.ack_req(frame.s_station, data)

    def ctl(self, frame):
        '''
        Control.

        :param frame: Frame of data
        '''
        if frame.d_station != self._sm.station:
            print(("Control",
                   "   : Control ignoring frame for station %s" %
                   frame.d_station))
            return

        if frame.type == T_ACK:
            self.ctl_ack(frame)
        elif frame.type == T_END:
            self.ctl_end(frame)
        elif frame.type >= T_NEW:
            self.ctl_new(frame)
        else:
            print(("Control",
                   "   : Unknown control message type %i" % frame.type))

    def new_session(self, session):
        '''
        New Session.

        :param session: Session object
        :returns: True if session created
        '''
        frame = DDT2EncodedFrame()
        frame.type = T_NEW + session.type
        frame.seq = 0
        # pylint: disable=protected-access
        frame.d_station = session._st
        # pylint: disable=protected-access
        frame.data = struct.pack("B", int(session._id)) + session.name

        wait_time = 5

        for _i in range(0, 10):
            self._sm.outgoing(self, frame)

            frame.sent_event.wait(10)
            frame.sent_event.clear()

            print("Control   : Sent request, blocking...")
            session.wait_for_state_change(wait_time)

            state = session.get_state()

            if state == base.ST_CLSD:
                print("Control   : Session is closed")
                break
            if state == base.ST_SYNC:
                print("Control   : Waiting for synchronization")
                wait_time = 15
            else:
                # pylint: disable=protected-access
                print("Control",
                      "   : Established session %i:%i" %
                      (session._id, session._rs))
                session.set_state(base.ST_OPEN)
                return True

        session.set_state(base.ST_CLSD)
        print("Control   : Failed to establish session")
        return False

    def end_session(self, session):
        '''
        End Session.

        :param session: Session object
        :returns: True if session is closed normally
        '''
        if session.stateless:
            return True

        while session.get_state() == base.ST_SYNC:
            print("Control   : Waiting for session in SYNC")
            session.wait_for_state_change(2)

        frame = DDT2EncodedFrame()
        frame.type = T_END
        frame.seq = 0
        # pylint: disable=protected-access
        frame.d_station = session._st
        # pylint: disable=protected-access
        if session._rs:
            # pylint: disable=protected-access
            frame.data = str(session._rs)
        else:
            # pylint: disable=protected-access
            frame.data = str(session._id)

        session.set_state(base.ST_CLSW)

        for _attempt in range(0, 3):
            print("Control   : Sending End-of-Session")
            self._sm.outgoing(self, frame)

            frame.sent_event.wait(10)
            frame.sent_event.clear()

            print("Control   : Sent, waiting for response")
            session.wait_for_state_change(15)

            if session.get_state() == base.ST_CLSD:
                print("Control   : Session closed")
                return True

        session.set_state(base.ST_CLSD)
        print("Control   : Session closed because no response")
        return False

    def __init__(self):
        base.Session.__init__(self, "control")
        self.handler = self.ctl

        self.stypes = {T_NEW + base.T_GENERAL  : stateful.StatefulSession,
                       T_NEW + base.T_FILEXFER : file.FileTransferSession,
                       T_NEW + base.T_FORMXFER : form.FormTransferSession,
                       T_NEW + base.T_SOCKET   : sock.SocketSession,
                       }
