import random
import time

import gobject

from d_rats import signals, dplatform, gps, utils, station_status
from d_rats.version import DRATS_VERSION
from d_rats.sessions import base, stateless
from d_rats.ddt2 import DDT2EncodedFrame, DDT2RawData

class ChatSession(stateless.StatelessSession, gobject.GObject):
    __gsignals__ = {
        "incoming-chat-message" : signals.INCOMING_CHAT_MESSAGE,
        "outgoing-chat-message" : signals.OUTGOING_CHAT_MESSAGE,
        "ping-request" : signals.PING_REQUEST,
        "ping-response" : signals.PING_RESPONSE,
        "incoming-gps-fix" : signals.INCOMING_GPS_FIX,
        "station-status" : signals.STATION_STATUS,
        "get-current-status" : signals.GET_CURRENT_STATUS,
        }

    _signals = __gsignals__

    __cb = None
    __cb_data = None

    type = base.T_STATELESS

    T_DEF = 0
    T_PNG_REQ = 1
    T_PNG_RSP = 2
    T_PNG_ERQ = 3
    T_PNG_ERS = 4
    T_STATUS  = 5

    compress = False

    def __init__(self, *args, **kwargs):
        stateless.StatelessSession.__init__(self, *args, **kwargs)
        gobject.GObject.__init__(self)

        self.set_ping_function()
        self.handler = self.incoming_data

        self.__ping_handlers = {}

    def set_ping_function(self, func=None):
        if func is not None:
            self.pingfn = func
        else:
            self.pingfn = self.ping_data

    def ping_data(self):
        p = dplatform.get_platform()
        return _("Running") + " D-RATS %s (%s)" % (DRATS_VERSION,
                                                   p.os_version_string())

    def _emit(self, signal, *args):
        gobject.idle_add(self.emit, signal, *args)

    def _incoming_chat(self, frame):
        self._emit("incoming-chat-message",
                   frame.s_station,
                   frame.d_station,
                   unicode(frame.data, "utf-8"))

    def _incoming_gps(self, fix):
        self._emit("incoming-gps-fix", fix)

    def incoming_data(self, frame):
        print("Chat      : Got chat frame: %s" % frame)
        if frame.type == self.T_DEF:
            fix = gps.parse_GPS(frame.data)
            if fix and fix.valid:
                self._incoming_gps(fix)
            else:
                self._incoming_chat(frame)

        elif frame.type == self.T_PNG_REQ:
            self._emit("ping-request",
                       frame.s_station, frame.d_station, "Request")

            if frame.d_station == "CQCQCQ":
                delay = random.randint(0,50) / 10.0
                print("Chat      : Broadcast ping, waiting %.1f sec" % delay)
                time.sleep(delay)
            elif frame.d_station != self._sm.station:
                return # Not for us

            frame.d_station = frame.s_station
            frame.type = self.T_PNG_RSP

            try:
                frame.data = self.pingfn()
            except Exception, e:
                print("Chat      : Ping function failed: %s" % e)
                return

            self._sm.outgoing(self, frame)

            try:
                s, m = self.emit("get-current-status")
                self.advertise_status(s, m)
            except Exception, e:
                print("Chat      : Exception while getting status for ping reply:")
                utils.log_exception()

            self._emit("ping-response",
                       frame.s_station,
                       frame.d_station,
                       unicode(frame.data, "utf-8"))
        elif frame.type == self.T_PNG_RSP:
            print("Chat      : PING OUT")
            self._emit("ping-response",
                       frame.s_station, frame.d_station, frame.data)
        elif frame.type == self.T_PNG_ERQ:
            self._emit("ping-request", frame.s_station, frame.d_station,
                       "%s %i %s" % (_("Echo request of"),
                                     len(frame.data),
                                     _("bytes")))

            if frame.d_station == "CQCQCQ":
                delay = random.randint(0, 100) / 10.0
                print("Chat      : Broadcast ping echo, waiting %.1f sec" % delay)
                time.sleep(delay)
            elif frame.d_station != self._sm.station:
                return # Not for us

            frame.d_station = frame.s_station
            frame.type = self.T_PNG_ERS

            self._sm.outgoing(self, frame)

            self._emit("ping-response", frame.s_station, frame.d_station,
                       "%s %i %s" % (_("Echo of"),
                                    len(frame.data),
                                    _("bytes")))
        elif frame.type == self.T_PNG_ERS:
            self._emit("ping-response", frame.s_station, frame.d_station,
                       "%s %i %s" % (_("Echo of"),
                                     len(frame.data),
                                     _("bytes")))
            if self.__ping_handlers.has_key(frame.s_station):
                cb, data = self.__ping_handlers[frame.s_station]
                try:
                    cb(*data)
                except Exception:
                    print("Chat      : Exception while running ping callback")
                    utils.log_exception()
        elif frame.type == self.T_STATUS:
            try:
                s = int(frame.data[0])
            except Exception:
                print("Chat      : Unable to parse station status: %s" % {frame.s_station :
                                                                  frame.data})
                s = 0

            self._emit("station-status", frame.s_station, s, frame.data[1:])

    def write_raw(self, data):
        f = DDT2RawData()
        f.data = data
        f.type = self.T_DEF

        print("Chat      : Sending raw: %s" % data)

        self._sm.outgoing(self, f)

    def write(self, data, dest="CQCQCQ"):
        self._emit("outgoing-chat-message", self._sm.station, self._st, data)
        stateless.StatelessSession.write(self, data, dest)

    def ping_station(self, station):
        f = DDT2EncodedFrame()
        f.d_station = station
        f.type = self.T_PNG_REQ
        f.data = "Ping Request"
        f.set_compress(False)
        self._sm.outgoing(self, f)
        print("Chat      : pinging %s" % f.d_station)
        self._emit("ping-request", f.s_station, f.d_station, "Request")

    def ping_echo_station(self, station, data, cb=None, *cbdata):
        if cb:
            self.__ping_handlers[station] = (cb, cbdata)

        f = DDT2EncodedFrame()
        f.d_station = station
        f.type = self.T_PNG_ERQ
        f.data = data
        f.set_compress(False)
        self._sm.outgoing(self, f)
        self._emit("ping-request", f.s_station, f.d_station,
                   "%s %i %s" % (_("Echo of"),
                                 len(data),
                                 _("bytes")))

    def advertise_status(self, stat, msg):
        if stat > station_status.STATUS_MAX or stat < station_status.STATUS_MIN:
            raise Exception("Status integer %i out of range" % stat)
        f = DDT2EncodedFrame()
        f.d_station = "CQCQCQ"
        f.type = self.T_STATUS
        f.data = "%i%s" % (stat, msg)
        self._sm.outgoing(self, f)
