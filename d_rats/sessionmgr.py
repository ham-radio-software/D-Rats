#!/usr/bin/python
#
# Copyright 2008 Dan Smith <dsmith@danplanet.com>
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

import time
import threading
import os
import struct
import socket

from ddt2 import DDT2EncodedFrame
import transport

from sessions import base, control, stateful, stateless
from sessions import file, form, sock, sniff

class SessionManager(object):
    def set_comm(self, pipe, **kwargs):
        self.pipe = pipe
        if self.tport:
            self.tport.disable()

        self.tport = transport.Transporter(self.pipe,
                                           inhandler=self.incoming,
                                           **kwargs)

    def set_call(self, callsign):
        self.station = callsign

    def __init__(self, pipe, station, **kwargs):
        self.pipe = self.tport = None
        self.station = station

        self.sniff_session = None

        self.last_frame = 0
        self.sessions = {}
        self.session_cb = {}

        self.set_comm(pipe, **kwargs)

        self._sid_counter = 0
        self._sid_lock = threading.Lock()

        self.control = control.ControlSession()
        self._register_session(self.control, "CQCQCQ", "new,out")

        self._stations_heard = {}

    def get_heard_stations(self):
        return dict(self._stations_heard)

    def manual_heard_station(self, station):
        self._stations_heard[station] = time.time()

    def fire_session_cb(self, session, reason):
        for f,d in self.session_cb.items():
            try:
                f(d, reason, session)
            except Exception, e:
                print("Sessionmgr: Exception in session CB: %s" % e)

    def register_session_cb(self, function, data):
        self.session_cb[function] = data

        for i,s in self.sessions.items():
            self.fire_session_cb(s, "new,existing")

    def shutdown(self, force=False):
        if force:
            self.tport.disable()

        if self.sessions.has_key(self.control._id):
            del self.sessions[self.control._id]

        for s in self.sessions.values():
            print("Sessionmgr: Stopping session `%s'" % s.name)
            s.close(force)

        if not force:
            self.tport.disable()

    def incoming(self, frame):
    #manage incoming sessions
        #record time for marking sessions
        self.last_frame = time.time()

        if frame.s_station not in ["!"]: 
        # if new station let's assign the time to its name
            self._stations_heard[frame.s_station] = time.time()

        if self.sniff_session is not None: #sniff if asked to
            self.sessions[self.sniff_session].handler(frame)

        if frame.d_station != "CQCQCQ" and \
                frame.d_station != self.station and \
                frame.session != 1:
            # Not CQ, not us, and not chat
            print("Sessionmgr: Received frame for station `%s'" % frame.d_station)
            return
        elif frame.s_station == self.station:
            # Either there is another station using our callsign, or
            # this packet arrived back at us due to a loop
            print("Sessionmgr: Received looped frame")
            return
        #
        #mmmmmm 
        # NOTE it could be here we have to add the rs-ms1a packets decoding ?? 
        #      but seems quite late because all portions of the packet seems already split
        #sample rs-ms1a string CQCQCQ: $$Msg,IZ2LXI,,0011DCtest transmission
           #self.emit("user-send-chat", "CQCQCQ", port, "$$Msg,IZ000,,0011D,%s" % d, True)        
        
        if not frame.session in self.sessions.keys():
            print("Sessionmgr: Incoming frame for unknown session `%i'" % frame.session)
            return

        session = self.sessions[frame.session]

        if session.stateless == False and \
                session._st != frame.s_station:
            print("Sessionmgr: Sessionmgr: Received frame from invalid station `%s' (expecting `%s'" % (frame.s_station, session._st))
            return

        if session.handler:
            session.handler(frame)
        else:
            session.inq.enqueue(frame)
            session.notify()

        print("Sessionmgr: Received block %i:%i for session `%s'" % (frame.seq, frame.type, session.name))

    def outgoing(self, session, block):
        self.last_frame = time.time()

        if not block.d_station:
            block.d_station = session._st

        block.s_station = self.station

        if session._rs:
            block.session = session._rs
        else:
            block.session = session._id

        self.tport.send_frame(block)

    def _get_new_session_id(self):
        self._sid_lock.acquire()
        if self._sid_counter >= 255:
            for id in range(0, 255):
                if id not in self.sessions.keys():
                    self._sid_counter = id
        else:
            id = self._sid_counter
            self._sid_counter += 1

        self._sid_lock.release()

        return id

    def _register_session(self, session, dest, reason):
        id = self._get_new_session_id()
        if id is None:
            # FIXME
            print("Sessionmgr: No free slots?  I can't believe it!")

        session._sm = self
        session._id = id
        session._st = dest
        self.sessions[id] = session

        self.fire_session_cb(session, reason)

        return id

    def _deregister_session(self, id):
        if self.sessions.has_key(id):
            self.fire_session_cb(self.sessions[id], "end")

        try:
            del self.sessions[id]
        except Exception, e:
            print("Sessionmgr: No session %s to deregister" % id)

    def start_session(self, name, dest=None, cls=None, **kwargs):
        if not cls:
            if dest:
                s = stateful.StatefulSession(name)
            else:
                s = stateless.StatelessSession(name)
                dest = "CQCQCQ"
        else:
            s = cls(name, **kwargs)

        s.set_state(base.ST_SYNC)
        id = self._register_session(s, dest, "new,out")

        if dest != "CQCQCQ":
            if not self.control.new_session(s):
                self._deregister_session(id)

        return s

    def set_sniffer_session(self, id):
        self.sniff_session = id

    def stop_session(self, session):
        for id, s in self.sessions.items():
            if session.name == s.name:
                self.tport.flush_blocks(id)
                if session.get_state() != base.ST_CLSD:
                    self.control.end_session(session)
                self._deregister_session(id)
                session.close()
                return True

        return False

    def end_session(self, id):
        try:
            del self.sessions[id]
        except Exception, e:
            print("Sessionmgr: Unable to deregister session")

    def get_session(self, rid=None, rst=None, lid=None):
        if not (rid or rst or lid):
            print("Sessionmgr: get_station() with no selectors!")
            return None

        for s in self.sessions.values():
            if rid and s._rs != rid:
                continue

            if rst and s._st != rst:
                continue

            if lid and s._id != lid:
                continue

            return s

        return None

if __name__ == "__main__":
    #p = transport.TestPipe(dst="KI4IFW")

    import comm
    import sys
    import sessions

    #if sys.argv[1] == "KI4IFW":
    #    p = comm.SerialDataPath(("/dev/ttyUSB0", 9600))
    #else:
    #    p = comm.SerialDataPath(("/dev/ttyUSB0", 38400))

    p = comm.SocketDataPath(("localhost", 9000))
    #p.make_fake_data("SOMEONE", "CQCQCQ")
    p.connect()
    sm = SessionManager(p, sys.argv[1])
    s = sm.start_session("chat", dest="CQCQCQ", cls=sessions.ChatSession)

    def cb(data, args):
        print("Sessionmgr: ---------[ CHAT DATA ]------------")

    s.register_cb(cb)

    s.write("This is %s online" % sys.argv[1])

    if sys.argv[1] == "KI4IFW":
        S = sm.start_session("xfer", "KI4IFW", cls=sessions.FileTransferSession)
        S.send_file("inputdialog.py")
    else:
        def h(data, reason, session):
            print("Sessionmgr: Session CB: %s" % reason)
            if reason == "new,in":
                print("Sessionmgr: Receiving file")
                t = threading.Thread(target=session.recv_file,
                                     args=("/tmp",))
                t.setDaemon(True)
                t.start()
                print("Sessionmgr: Done")

        sm.register_session_cb(h, None)

    try:
        while True:
            time.sleep(30)
    except Exception, e:
        print("Sessionmgr: ------- Closing")

    sm.shutdown()

#    blocks = s.recv_blocks()
#    for b in blocks:
#        print("Sessionmgr: Chat message: %s: %s" % (b.get_info()[2], b.get_data()))
