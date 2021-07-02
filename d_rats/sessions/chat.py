'''Sessions Chat'''
from __future__ import absolute_import
from __future__ import print_function
import random
import time

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GObject

from d_rats import signals, dplatform, gps, utils, station_status
from d_rats.version import DRATS_VERSION
from d_rats.sessions import base, stateless
from d_rats.ddt2 import DDT2EncodedFrame, DDT2RawData

#importing printlog() wrapper
from d_rats.debug import printlog


class ChatInvalidStatus(base.BaseSessionException):
    '''Invalid Chat Status.'''


class ChatSession(stateless.StatelessSession, GObject.GObject):
    '''Chat Session'''

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
    T_STATUS = 5

    compress = False

    def __init__(self, *args, **kwargs):
        stateless.StatelessSession.__init__(self, *args, **kwargs)
        GObject.GObject.__init__(self)

        self.set_ping_function()
        self.handler = self.incoming_data

        self.__ping_handlers = {}

    def set_ping_function(self, func=None):
        '''
        Set ping function for generating ping text

        :param func: Optional function.  Default is ping_data
        '''
        if func is not None:
            self.pingfn = func
        else:
            self.pingfn = self.ping_data

    # pylint: disable=no-self-use
    def ping_data(self):
        '''
        Setup ping data.

        :returns: A standard ping response text
        '''
        pform = dplatform.get_platform()
        return _("Running") + " D-RATS %s (%s)" % (DRATS_VERSION,
                                                   pform.os_version_string())

    def _emit(self, signal, *args):
        GObject.idle_add(self.emit, signal, *args)

    def _incoming_chat(self, frame):
        self._emit("incoming-chat-message",
                   frame.s_station,
                   frame.d_station,
                   frame.data.decode('utf-8', 'replace'))

    def _incoming_gps(self, fix):
        self._emit("incoming-gps-fix", fix)

    # pylint: disable=too-many-branches, too-many-statements
    def incoming_data(self, frame):
        '''
        Incoming data.

        :param frame: Frame containing incoming data
        '''
        printlog("Chat", "      : Got chat frame: %s" % frame)
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
                delay = random.randint(0, 50) / 10.0
                printlog("Chat",
                         "      : Broadcast ping, waiting %.1f sec" % delay)
                time.sleep(delay)
            elif frame.d_station != self._sm.station:
                return # Not for us

            frame.d_station = frame.s_station
            frame.type = self.T_PNG_RSP

            try:
                frame.data = self.pingfn()
            # pylint: disable=broad-except
            except Exception as err:
                printlog("Chat", "      : Ping function failed: %s -%s-" %
                         (type(err), err))
                return

            self._sm.outgoing(self, frame)

            try:
                status, msg = self.emit("get-current-status")
                self.advertise_status(status, msg)
            # pylint: disable=broad-except
            except Exception as err:
                printlog("Chat",
                         "      : Exception while getting status"
                         " for ping reply: (%s -%s-)" % (type(err), err))
                utils.log_exception()

            self._emit("ping-response",
                       frame.s_station,
                       frame.d_station,
                       frame.data.decode('utf-8', 'replace'))
        elif frame.type == self.T_PNG_RSP:
            printlog("Chat", "      : PING OUT")
            self._emit("ping-response",
                       frame.s_station, frame.d_station, frame.data)
        elif frame.type == self.T_PNG_ERQ:
            self._emit("ping-request", frame.s_station, frame.d_station,
                       "%s %i %s" % (_("Echo request of"),
                                     len(frame.data),
                                     _("bytes")))

            if frame.d_station == "CQCQCQ":
                delay = random.randint(0, 100) / 10.0
                printlog("Chat",
                         "      : Broadcast ping echo, waiting %.1f sec" %
                         delay)
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
            if frame.s_station in self.__ping_handlers:
                call_back, data = self.__ping_handlers[frame.s_station]
                try:
                    call_back(*data)
                # pylint: disable=broad-except
                except Exception as err:
                    printlog("Chat      : ",
                             "Exception while running ping callback %s -%s-" %
                             (type(err),err))
                    utils.log_exception()
        elif frame.type == self.T_STATUS:
            status_byte = frame.data[0] - ord('0')
            if status_byte > station_status.STATUS_MAX or \
               status_byte < station_status.STATUS_MIN:
                printlog("Chat",
                         "      : Unable to parse station status: %s" %
                         {frame.s_station : frame.data})
                status_byte = 0

            self._emit("station-status",
                       frame.s_station, status_byte, frame.data[1:])

    def write_raw(self, data):
        '''
        Write raw data.

        :param data: Data to send
        '''
        frame = DDT2RawData()
        frame.data = data
        frame.type = self.T_DEF

        printlog("Chat", "      : Sending raw: %s" % data)

        self._sm.outgoing(self, frame)

    def write(self, data, dest="CQCQCQ"):
        '''
        Write chat message to destination.

        :param data: Data to send
        :param dest: Destination station, default "CQCQCQ"
        '''
        self._emit("outgoing-chat-message", self._sm.station, self._st, data)
        stateless.StatelessSession.write(self, data, dest)

    def ping_station(self, station):
        '''
        Ping a station.

        :param station: Station to ping
        '''
        frame = DDT2EncodedFrame()
        frame.d_station = station
        frame.type = self.T_PNG_REQ
        frame.data = "Ping Request"
        frame.set_compress(False)
        self._sm.outgoing(self, frame)
        printlog("Chat", "      : pinging %s" % frame.d_station)
        self._emit("ping-request", frame.s_station, frame.d_station, "Request")

    # This needs to be fixed once the python3 conversion is done.
    # Fixing the order now breaks python2
    # pylint: disable=keyword-arg-before-vararg
    def ping_echo_station(self, station, data, call_back=None, *cbdata):
        '''
        Ping echo request to station

        :param station: Station to ping
        :param data: Data for station to echo
        :param call_back: Call back routine
        :param cbdata: Call Back data
        '''
        if call_back:
            self.__ping_handlers[station] = (call_back, cbdata)

        frame = DDT2EncodedFrame()
        frame.d_station = station
        frame.type = self.T_PNG_ERQ
        frame.data = data
        frame.set_compress(False)
        self._sm.outgoing(self, frame)
        self._emit("ping-request", frame.s_station, frame.d_station,
                   "%s %i %s" % (_("Echo of"),
                                 len(data),
                                 _("bytes")))

    def advertise_status(self, stat, msg):
        '''
        Advertise Status of station.

        :param stat: Station Status
        :param msg: Status message
        :raises: ChatInvalidStatus for unknown status codes.
        '''
        if stat > station_status.STATUS_MAX or stat < station_status.STATUS_MIN:
            raise ChatInvalidStatus("Status integer %i out of range" % stat)
        frame = DDT2EncodedFrame()
        frame.d_station = "CQCQCQ"
        frame.type = self.T_STATUS
        frame.data = "%i%s" % (stat, msg)
        self._sm.outgoing(self, frame)
