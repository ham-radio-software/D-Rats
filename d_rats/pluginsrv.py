#!/usr/bin/python
'''Pluginsrv'''
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

import os
import threading
from six.moves.xmlrpc_server import SimpleXMLRPCServer

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GObject

from . import signals
from . import utils
# from d_rats.sessions import rpc

# importing printlog() wrapper
from .debug import printlog


class DRatsChatEvent():
    '''DRats Chat Event.'''

    def __init__(self, src_station=None):
        self.__event = threading.Event()
        self.__src_station = src_station
        self.__text = None

    def get_src_station(self):
        '''
        Get source station.

        :returns: Source station
        '''
        return self.__src_station

    def set_chat_info(self, src, text):
        '''
        Set Chat Info

        :param src: Source for chat event
        :param text: Text for chat event
        '''
        self.__src_station = src
        self.__text = text

    def get_text(self):
        '''
        Get Text.

        :returns: Event text
        '''
        return self.__text

    def set(self):
        '''set event.'''
        self.__event.set()

    def wait(self, timeout):
        '''
        Wait for a timeout.

        :param timeout: Timeout to wait in unknown units
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
        self.__idcount = 0
        self.__persist = {}

        self.__events = {
            "chat" : [],
            }

    def get_port(self, station):
        '''
        Get port for station.

        :param station: Station to get the port for
        :raises Exception: when port is not known
        :returns: port
        '''
        ports = self.emit("get-station-list")
        port = utils.port_for_station(ports, station)
        if not port:
            # Need to define this as a specific exception
            raise Exception("Station %s not heard" % station)

        return port

    def send_chat(self, port, message):
        '''
        Send a chat message on port

        :param port: Port to send message on
        :param message: Message to send
        :returns: 0
        '''
        printlog("Pluginsrv",
                 " : Sending chat on port %s: %s" % (port, message))
        self.emit("user-send-chat", "CQCQCQ", port, message, False)

        return 0

    def list_ports(self):
        '''
        List of port names.

        :returns: List of port names
        '''
        slist = self.emit("get-station-list")
        return list(slist.keys())

    def send_file(self, station, filename, port=None):
        '''
        Send a file to station specified by filename on optional port.

        If port is not specified, the last-heard port for station will be
        used.  An exception will be thrown if the last port cannot be
        determined.

        :param station: Destination.
        :param filename: File to send.
        :param port: Optional port to use.
        :raises: Unspecified exception if last port can not be determined.
        :returns: 0
        '''
        # Need to find out exception raised and documented it.
        if not port:
            port = self.get_port(station)

        sname = os.path.basename(filename)

        printlog("Pluginsrv",
                 " : Sending file %s to %s on port %s" %
                 (filename, station, port))
        self.emit("user-send-file", station, port, filename, sname)

        return 0

    def submit_rpcjob(self, station, rpcname, port=None, params=None):
        '''
        Submit an RPC job to station of type rpcname.

        Optionally specify the port to be used.
        The @params structure is a key=value list of function(value)
        items to call on the job object before submission.

        :param station: Destination Station
        :param rpcname: Name of the rpcname
        :param port: Optional port.
        :param params: Optional parameters for RPC job
        :returns: Job specifier to be used with get_result()
        '''
        if not rpcname.isalpha() or not rpcname.startswith("RPC"):
            raise Exception("Invalid RPC function call name")

        if not port:
            port = self.get_port(station)

        # pylint: disable=eval-used
        job = eval("rpcsession.%s('%s', 'New Job')" % (rpcname, station))
        if params:
            for key, val in params:
                func = job.__getattribute__(key)
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
        :returns: Structure, empty until completion
        '''
        if ident in self.__persist:
            result = self.__persist[ident]
            del self.__persist[ident]
        else:
            result = {}

        return result

    def wait_for_chat(self, timeout, src_station=None):
        '''
        Wait for a chat message for timeout seconds.

        Optional filter src_station avoids returning until a chat message
        from that station is received.

        :param timeout: Time out to wait
        :param src_station: Optional Station to wait for message from
        :returns: Two element tuple of source station and chat text
        '''
        event = DRatsChatEvent(src_station)
        self.__events["chat"].append(event)
        event.wait(timeout)

        if event.get_text():
            return event.get_src_station(), event.get_text()
        else:
            return "", ""

    def incoming_chat_message(self, src, _dst, text):
        '''
        Incoming Chat Message.

        :param src: Source of message
        :param dst: Destination of message
        :param text: Text of message
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

        SimpleXMLRPCServer.__init__(self, ("localhost", 0))

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
        printlog("Pluginsrv", " : Started serve_forever() thread")

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
