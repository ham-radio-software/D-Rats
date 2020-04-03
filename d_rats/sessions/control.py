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

import struct

from d_rats.utils import log_exception
from d_rats.ddt2 import DDT2EncodedFrame
from d_rats.sessions import base, stateful, stateless
from d_rats.sessions import file, form, sock

T_PNG = 0
T_END = 1
T_ACK = 2
T_NEW = 3

class ControlSession(base.Session):
    stateless = True

    def ack_req(self, dest, data):
        f = DDT2EncodedFrame()
        f.type = T_ACK
        f.seq = 0
        f.d_station = dest
        f.data = data
        self._sm.outgoing(self, f)

    def ctl_ack(self, frame):
        try:
            l, r = struct.unpack("BB", frame.data)
            session = self._sm.sessions[l]
            session._rs = r
            print "Signaled waiting session thread (l=%i r=%i)" % (l, r)
        except Exception, e:
            print "Failed to lookup new session event: %s" % e

        if session.get_state() == base.ST_CLSW:
            session.set_state(base.ST_CLSD)
        elif session.get_state() == base.ST_OPEN:
            pass
        elif session.get_state() == base.ST_SYNC:
            session.set_state(base.ST_OPEN)
        else:
            print "ACK for session in invalid state: %i" % session.get_state()
        
    def ctl_end(self, frame):
        print "End of session %s" % frame.data

        try:
            id = int(frame.data)
        except Exception, e:
            print "Session end request had invalid ID: %s" % e
            return

        try:
            session = self._sm.sessions[id]
            session.set_state(base.ST_CLSD)
            self._sm.stop_session(session)
        except Exception, e:
            print "Session %s ended but not registered" % id
            return

        frame.d_station = frame.s_station
        if session._rs:
            frame.data = str(session._rs)
        else:
            frame.data = str(session._id)
        self._sm.outgoing(self, frame)

    def ctl_new(self, frame):
        try:
            (id,) = struct.unpack("B", frame.data[:1])
            name = frame.data[1:]
        except Exception, e:
            print "Session request had invalid ID: %s" % e
            return

        print "New session %i from remote" % id

        exist = self._sm.get_session(rid=id, rst=frame.s_station)
        if exist:
            print "Re-acking existing session %s:%i:%i" % (frame.s_station,
                                                           id,
                                                           exist._id)
            self.ack_req(frame.s_station, struct.pack("BB", id, exist._id))
            return

        print "ACK'ing session request for %i" % id

        try:
            c = self.stypes[frame.type]
            print "Got type: %s" % c
            s = c(name)
            s._rs = id
            s.set_state(base.ST_OPEN)
        except Exception, e:
            log_exception()
            print "Can't start session type `%s': %s" % (frame.type, e)
            return
                
        num = self._sm._register_session(s, frame.s_station, "new,in")

        data = struct.pack("BB", id, num)
        self.ack_req(frame.s_station, data)

    def ctl(self, frame):
        if frame.d_station != self._sm.station:
            print "Control ignoring frame for station %s" % frame.d_station
            return

        if frame.type == T_ACK:
            self.ctl_ack(frame)
        elif frame.type == T_END:
            self.ctl_end(frame)
        elif frame.type >= T_NEW:
            self.ctl_new(frame)
        else:
            print "Unknown control message type %i" % frame.type
            
    def new_session(self, session):
        f = DDT2EncodedFrame()
        f.type = T_NEW + session.type
        f.seq = 0
        f.d_station = session._st
        f.data = struct.pack("B", int(session._id)) + session.name

        wait_time = 5

        for i in range(0,10):
            self._sm.outgoing(self, f)

            f.sent_event.wait(10)
            f.sent_event.clear()

            print "Sent request, blocking..."
            session.wait_for_state_change(wait_time)

            state = session.get_state()

            if state == base.ST_CLSD:
                print "Session is closed"
                break
            elif state == base.ST_SYNC:
                print "Waiting for synchronization"
                wait_time = 15
            else:
                print "Established session %i:%i" % (session._id, session._rs)
                session.set_state(base.ST_OPEN)
                return True

        session.set_state(base.ST_CLSD)
        print "Failed to establish session"
        return False
        
    def end_session(self, session):
        if session.stateless:
            return

        while session.get_state() == base.ST_SYNC:
            print "Waiting for session in SYNC"
            session.wait_for_state_change(2)

        f = DDT2EncodedFrame()
        f.type = T_END
        f.seq = 0
        f.d_station = session._st
        if session._rs:
            f.data = str(session._rs)
        else:
            f.data = str(session._id)

        session.set_state(base.ST_CLSW)

        for i in range(0, 3):
            print "Sending End-of-Session"
            self._sm.outgoing(self, f)

            f.sent_event.wait(10)
            f.sent_event.clear()

            print "Sent, waiting for response"
            session.wait_for_state_change(15)

            if session.get_state() == base.ST_CLSD:
                print "Session closed"
                return True

        session.set_state(base.ST_CLSD)
        print "Session closed because no response"
        return False
            
    def __init__(self):
        base.Session.__init__(self, "control")
        self.handler = self.ctl

        self.stypes = { T_NEW + base.T_GENERAL  : stateful.StatefulSession,
                        T_NEW + base.T_FILEXFER : file.FileTransferSession,
                        T_NEW + base.T_FORMXFER : form.FormTransferSession,
                        T_NEW + base.T_SOCKET   : sock.SocketSession,
                        }

