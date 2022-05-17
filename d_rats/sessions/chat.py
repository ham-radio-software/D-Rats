'''Sessions Chat.'''
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
import random
import time

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib
from gi.repository import GObject

from d_rats import signals, dplatform, gps, utils, station_status
from d_rats.version import DRATS_VERSION
from d_rats.sessions import base, stateless
from d_rats.ddt2 import DDT2EncodedFrame, DDT2RawData

# This makes pylance happy with out overriding settings
# from the invoker of the class
if not '_' in locals():
    import gettext
    _ = gettext.gettext


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

        self.logger = logging.getLogger("ChatSession")
        self.set_ping_function()
        self.handler = self.incoming_data

        self.__ping_handlers = {}

    def set_ping_function(self, func=None):
        '''
        Set ping function for generating ping text

        :param func: Optional function.  Default is ping_data
        :type func: function
        '''
        if func is not None:
            self.pingfn = func
        else:
            self.pingfn = self.ping_data

    @staticmethod
    def ping_data():
        '''
        Setup ping data.

        :returns: A standard ping response text with d-rats version
        :rtype: str
        '''
        pform = dplatform.get_platform()
        return _("Running") + " D-RATS %s (%s)" % (DRATS_VERSION,
                                                   pform.os_version_string())

    def _emit(self, signal, *args):
        GLib.idle_add(self.emit, signal, *args)

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
        :type frame: :class:`DDT2Frame`
        '''
        self.logger.debug("incoming_data: Got chat frame: %s", frame)
        frame_data = frame.data.decode('utf-8', 'replace')
        if frame.type == self.T_DEF:
            fix = gps.parse_GPS(frame_data)
            if fix and fix.valid:
                self._incoming_gps(fix)
            else:
                self._incoming_chat(frame)

        elif frame.type == self.T_PNG_REQ:
            self._emit("ping-request",
                       frame.s_station, frame.d_station, "Request")

            if frame.d_station == "CQCQCQ":
                delay = random.randint(0, 50) / 10.0
                self.logger.debug("incoming_data: Broadcast ping, "
                                  "waiting %.1f sec", delay)
                time.sleep(delay)
            elif frame.d_station != self._sm.station:
                return # Not for us

            frame.d_station = frame.s_station
            frame.type = self.T_PNG_RSP

            try:
                data = self.pingfn()
                if isinstance(data, str):
                    frame.data = str.encode(data)
                else:
                    frame.data = data
                frame_data = frame.data
            # pylint: disable=broad-except
            except Exception:
                self.logger.info("incoming_data: Ping function failed",
                                 exc_info=True)
                return

            self._sm.outgoing(self, frame)

            try:
                status, msg = self.emit("get-current-status")
                self.advertise_status(status, msg)
            # pylint: disable=broad-except
            except Exception:
                self.logger.info("incoming_data:"
                                 " Exception while getting status"
                                 " for ping reply:", exc_info=True)
                utils.log_exception()

            self._emit("ping-response",
                       frame.s_station,
                       frame.d_station,
                       frame_data)
        elif frame.type == self.T_PNG_RSP:
            self.logger.debug("incoming_data: PING OUT")
            self._emit("ping-response",
                       frame.s_station, frame.d_station, frame_data)
        elif frame.type == self.T_PNG_ERQ:
            self._emit("ping-request", frame.s_station, frame.d_station,
                       "%s %i %s" % (_("Echo request of"),
                                     len(frame_data),
                                     _("bytes")))

            if frame.d_station == "CQCQCQ":
                delay = random.randint(0, 100) / 10.0
                self.logger.debug("incoming_data: Broadcast ping echo, "
                                  "waiting %.1f sec", delay)
                time.sleep(delay)
            elif frame.d_station != self._sm.station:
                return # Not for us

            frame.d_station = frame.s_station
            frame.type = self.T_PNG_ERS

            self._sm.outgoing(self, frame)

            self._emit("ping-response", frame.s_station, frame.d_station,
                       "%s %i %s" % (_("Echo of"),
                                     len(frame_data),
                                     _("bytes")))
        elif frame.type == self.T_PNG_ERS:
            self._emit("ping-response", frame.s_station, frame.d_station,
                       "%s %i %s" % (_("Echo of"),
                                     len(frame_data),
                                     _("bytes")))
            if frame.s_station in self.__ping_handlers:
                call_back, data = self.__ping_handlers[frame.s_station]
                try:
                    call_back(*data)
                # pylint: disable=broad-except
                except Exception:
                    self.logger.info("incoming_data: "
                                     "Exception while running ping callback",
                                     exc_info=True)
                    utils.log_exception()
        elif frame.type == self.T_STATUS:
            try:
                # python 3 code
                status_byte = frame.data[0] - ord('0')
            except TypeError:
                status_byte = ord(frame.data[0]) - ord('0')
            if status_byte > station_status.STATUS_MAX or \
                    status_byte < station_status.STATUS_MIN:
                self.logger.info("incoming_data: "
                                 "Unable to parse station status: %s",
                                 {frame.s_station : frame.data})
                status_byte = 0

            self._emit("station-status",
                       frame.s_station, status_byte, frame.data[1:])

    def write_raw(self, data):
        '''
        Write raw data.

        :param data: Data to send
        :type data: str or bytes
        '''
        frame = DDT2RawData()
        if isinstance(data, str):
            frame.data = str.encode(data)
        else:
            frame.data = data
        frame.type = self.T_DEF

        self.logger.debug("write_raw: Sending raw: %s", data)

        self._sm.outgoing(self, frame)

    def write(self, data, dest="CQCQCQ"):
        '''
        Write chat message to destination.

        :param data: Data to send
        :type data: str
        :param dest: Destination station, default "CQCQCQ"
        :type dest: str
        '''
        self._emit("outgoing-chat-message", self._sm.station, self._st, data)
        stateless.StatelessSession.write(self, data, dest)

    def ping_station(self, station):
        '''
        Ping a station.

        :param station: Station to ping
        :type station: str
        '''
        frame = DDT2EncodedFrame()
        frame.d_station = station
        frame.type = self.T_PNG_REQ
        frame.data = b"Ping Request"
        frame.set_compress(False)
        self._sm.outgoing(self, frame)
        self.logger.debug("pinging %s", frame.d_station)
        self._emit("ping-request", frame.s_station, frame.d_station, "Request")

    # This needs to be fixed once the python3 conversion is done.
    # Fixing the order now breaks python2
    # pylint: disable=keyword-arg-before-vararg
    def ping_echo_station(self, station, data, call_back=None, *cbdata):
        '''
        Ping echo request to station

        :param station: Station to ping
        :type station: str
        :param data: Data for station to echo
        :type data: str
        :param call_back: Call back routine
        :type call_back: function
        :param cbdata: Call Back data
        '''
        if call_back:
            self.__ping_handlers[station] = (call_back, cbdata)

        frame = DDT2EncodedFrame()
        frame.d_station = station
        frame.type = self.T_PNG_ERQ
        if isinstance(data, str):
            frame.data = str.encode(data)
        else:
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
        :type stat: int
        :param msg: Status message
        :type msg: str
        :raises: ChatInvalidStatus for unknown status codes.
        '''
        if stat > station_status.STATUS_MAX or stat < station_status.STATUS_MIN:
            raise ChatInvalidStatus("Status integer %i out of range" % stat)
        frame = DDT2EncodedFrame()
        frame.d_station = "CQCQCQ"
        frame.type = self.T_STATUS
        status_msg = "%i%s" % (stat, msg)
        frame.data = str.encode(status_msg)
        self._sm.outgoing(self, frame)
