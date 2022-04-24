#!/usr/bin/python
'''Pluginsrv'''
#
# Copyright 2009 Dan Smith <dsmith@danplanet.com>
# Copyright 2021-2022 John. E. Malmberg - Python3 Conversion
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
import os
import threading

from xmlrpc.server import SimpleXMLRPCServer

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GObject

from .sessions import rpc
from . import signals
from . import utils


class PluginSrvException(Exception):
    '''Generic PluginSrv Exception.'''


class ProxyStationNotHeard(PluginSrvException):
    '''Station Not Heard Exception.'''


class ProxyInvalidRPCName(PluginSrvException):
    '''Invalid RPC Name Exception.'''


class DRatsChatEvent():
    '''
    DRats Chat Event.

    :param src_station: Source station, default None
    :type src_station: str
    '''

    def __init__(self, src_station=None):
        self.__event = threading.Event()
        self.__src_station = src_station
        self.__text = None

    def get_src_station(self):
        '''
        Get source station.

        :returns: Source station
        :rtype: str
        '''
        return self.__src_station

    def set_chat_info(self, src, text):
        '''
        Set Chat Info

        :param src: Source Station for chat event
        :type src: str
        :param text: Text for chat event
        :type text: str
        '''
        self.__src_station = src
        self.__text = text

    def get_text(self):
        '''
        Get Text.

        :returns: Event text
        :rtype: str
        '''
        return self.__text

    def set(self):
        '''Set Event.'''
        self.__event.set()

    def wait(self, timeout):
        '''
        Wait for a timeout.

        :param timeout: Timeout to wait in seconds
        :type timeout: float
        '''
        self.__event.wait(timeout)


class DRatsPluginProxy(GObject.GObject):
    '''DRats Plugin Proxy'''

    __gsignals__ = {
        "user-send-chat" : signals.USER_SEND_CHAT,
        "get-station-list" : signals.GET_STATION_LIST,
        "user-send-file" : signals.USER_SEND_FILE,
        "submit-rpc-job" : signals.SUBMIT_RPC_JOB,
        }
    _signals = __gsignals__

    def __init__(self):
        GObject.GObject.__init__(self)
        self.logger = logging.getLogger("DRatsPluginProxy")
        self.__idcount = 0
        self.__persist = {}

        self.__events = {
            "chat" : [],
            }

    def get_port(self, stationid):
        '''
        Get port for a station identification.

        :param stationid: Station identification to get the port for
        :type stationid: str
        :returns: port
        :rtype: str
        :raises: :class:`ProxyStationNotHeard` when port is not known
        '''
        ports = self.emit("get-station-list")
        port = utils.port_for_stationid(ports, stationid)
        if not port:
            raise ProxyStationNotHeard("Station ID %s not heard" % stationid)
        return port

    def send_chat(self, port, message):
        '''
        Send a chat message on port

        :param port: Port to send message on
        :type port: str
        :param message: Message to send
        :type message: str
        :returns: 0
        :rtype: int
        '''
        self.logger.info("send_chat: port %s: %s", port, message)
        self.emit("user-send-chat", "CQCQCQ", port, message, False)

        return 0

    def list_ports(self):
        '''
        List of port names.

        :returns: List of port names
        :rtype: list[str]
        '''
        slist = self.emit("get-station-list")
        return list(slist.keys())

    def send_file(self, stationid, filename, port=None):
        '''
        Send a file to station identification specified by filename on
        an optional port.

        If port is not specified, the last-heard port for station
        identification will be used.

        :param stationid: Destination.
        :type stationid: str
        :param filename: File to send.
        :type filename: str
        :param port: Optional port to use.
        :type port: str
        :returns: 0
        :rtype: int
        :raises: :class:`ProxyStationNotHeard` if last port can not be
                 determined.
        '''
        if not port:
            port = self.get_port(stationid)

        sname = os.path.basename(filename)

        self.logger.info("send_file: %s to %s on port %s",
                         filename, stationid, port)
        self.emit("user-send-file", stationid, port, filename, sname)

        return 0

    def submit_rpcjob(self, stationid, rpcname, port=None, params=None):
        '''
        Submit an RPC job to station identification of type rpcname.

        Optionally specify the port to be used.
        The @params structure is a key=value list of function(value)
        items to call on the job object before submission.

        :param stationid: Destination Station
        :type stationid: str
        :param rpcname: Name of the rpcname
        :type rpcname: str
        :param port: Optional port.
        :type port: str
        :param params: Optional parameters for RPC job
        :type params: dict
        :returns: Job identification number
        :rtype: int
        :raises: :class:`ProxyInvalidRPCName` If an invalid RPC name used
        '''
        if not rpcname in rpc.RPC_JOBS:
            raise ProxyInvalidRPCName("Invalid RPC function call name")

        if not port:
            port = self.get_port(stationid)

        rpc_job_class = getattr(rpc, rpcname)
        job = rpc_job_class(stationid, 'New Job')
        if params:
            for key, val in params:
                func = job.__getattribute__(key)
                self.logger.info("submit_rpcjob: params"
                                 "func %s, %s"
                                 " key %s, %s"
                                 " val %s, %s",
                                 type(func), func, type(key), key, type(val), val)
                func(val)


        ident = self.__idcount
        self.__idcount += 1

        def record_result(_job, _state, result, ident):
            self.__persist[ident] = result
        job.connect("state-change", record_result, ident)
        self.emit("submit-rpc-job", job, port)
        return ident

    def get_result(self, ident):
        '''
        Get the result of job ident.

        :param ident: Ident of job.
        :type ident: int
        :returns: Job result if in persist state
        :rtype: dict
        '''
        if ident in self.__persist:
            result = self.__persist[ident]
            del self.__persist[ident]
        else:
            result = {}

        return result

    def wait_for_chat(self, timeout, src_stationid=None):
        '''
        Wait for a chat message for timeout seconds.

        Optional filter src_stationid avoids returning until a chat message
        from that station identification is received.

        :param timeout: Time out to wait
        :type timeout: float
        :param src_stationid: Optional Station Identification to wait for
                              message from
        :type src_stationid: str
        :returns: Source station identification and chat text
        :rtype: tuple[str, str]
        '''
        event = DRatsChatEvent(src_stationid)
        self.__events["chat"].append(event)
        event.wait(timeout)

        if event.get_text():
            return event.get_src_station(), event.get_text()
        return "", ""

    def incoming_chat_message(self, src, _dst, text):
        '''
        Incoming Chat Message.

        :param src: Source of message
        :type src: str
        :param _dst: Destination of message, Unused
        :type _dst: str
        :param text: Text of message
        :type text: str
        '''
        for event in self.__events["chat"]:
            if not event.get_src_station():
                event.set_chat_info(src, text)
                event.set()
            elif event.get_src_station() == src:
                event.set_chat_info(src, text)
                event.set()


class DRatsPluginServer(SimpleXMLRPCServer):
    '''DRats Plugin Server'''

    def __init__(self):

        SimpleXMLRPCServer.__init__(self, ("localhost", 9100))
        self.logger = logging.getLogger("DRatsPluginServer")
        self.__thread = None

        self.__proxy = DRatsPluginProxy()

        self.register_function(self.__proxy.send_chat, "send_chat")
        self.register_function(self.__proxy.list_ports, "list_ports")
        self.register_function(self.__proxy.send_file, "send_file")
        self.register_function(self.__proxy.submit_rpcjob, "submit_rpcjob")
        self.register_function(self.__proxy.get_result, "get_result")
        self.register_function(self.__proxy.wait_for_chat, "wait_for_chat")

    def serve_background(self):
        '''Serve Background'''
        self.__thread = threading.Thread(target=self.serve_forever)
        self.__thread.setDaemon(True)
        self.__thread.start()
        self.logger.info("Started serve_forever() thread")

    def incoming_chat_message(self, *args):
        '''
        Incoming Chat Message.

        :param args: Arguments for chat message
        '''
        self.__proxy.incoming_chat_message(*args)

    def get_proxy(self):
        '''
        Get Proxy.

        :returns: Proxy
        '''
        return self.__proxy
