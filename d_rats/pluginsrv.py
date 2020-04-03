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

import os
import threading
from SimpleXMLRPCServer import SimpleXMLRPCServer

import gobject

import signals
import utils
from d_rats.sessions import rpc

class DRatsChatEvent(object):
    def __init__(self, src_station=None):
        self.__event = threading.Event()
        self.__src_station = src_station
        self.__text = None

    def get_src_station(self):
        return self.__src_station

    def set_chat_info(self, src, text):
        self.__src_station = src
        self.__text = text

    def get_text(self):
        return self.__text

    def set(self):
        self.__event.set()

    def wait(self, timeout):
        self.__event.wait(timeout)

class DRatsPluginProxy(gobject.GObject):
    __gsignals__ = {
        "user-send-chat" : signals.USER_SEND_CHAT,
        "get-station-list" : signals.GET_STATION_LIST,
        "user-send-file" : signals.USER_SEND_FILE,
        "submit-rpc-job" : signals.SUBMIT_RPC_JOB,
        }
    _signals = __gsignals__

    def __init__(self):
        gobject.GObject.__init__(self)
        self.__idcount = 0
        self.__persist = {}

        self.__events = {
            "chat" : [],
            }

    def get_port(self, station):
        ports = self.emit("get-station-list")
        port = utils.port_for_station(ports, station)
        if not port:
            raise Exception("Station %s not heard" % station)

        return port

    def send_chat(self, port, message):
        """Send a chat @message on @port"""
        print "Pluginsrv/send_chat: Sending chat on port %s: %s" % (port, message)
        self.emit("user-send-chat", "CQCQCQ", port, message, False)

        return 0

    def list_ports(self):
        """Return a list of port names"""
        slist = self.emit("get-station-list")
        return slist.keys()

    def send_file(self, station, filename, port=None):
        """Send a file to @station specified by @filename on optional port.
        If @port is not specified, the last-heard port for @station will be
        used.  An exception will be thrown if the last port cannot be
        determined"""
        if not port:
            port = self.get_port(station)

        sname = os.path.basename(filename)

        print "Pluginsrv/send_file: Sending file %s to %s on port %s" % (filename, station, port)
        self.emit("user-send-file", station, port, filename, sname)

        return 0

    def submit_rpcjob(self, station, rpcname, port=None, params={}):
        """Submit an RPC job to @station of type @rpcname.  Optionally
        specify the @port to be used.  The @params structure is a key=value
        list of function(value) items to call on the job object before
        submission.  Returns a job specifier to be used with get_result()."""
        if not rpcname.isalpha() or not rpcname.startswith("RPC"):
            raise Exception("Invalid RPC function call name")

        if not port:
            port = self.get_port(station)

        job = eval("rpcsession.%s('%s', 'New Job')" % (rpcname, station))
        for key, val in params:
            func = job.__getattribute__(key)
            func(val)

        ident = self.__idcount
        self.__idcount += 1

        def record_result(job, state, result, ident):
            self.__persist[ident] = result
        job.connect("state-change", record_result, ident)

        self.emit("submit-rpc-job", job, port)

        return ident

    def get_result(self, ident):
        """Get the result of job @ident.  Returns a structure, empty until
        completion"""
        if self.__persist.has_key(ident):
            result = self.__persist[ident]
            del self.__persist[ident]
        else:
            result = {}

        return result

    def wait_for_chat(self, timeout, src_station=None):
        """Wait for a chat message for @timeout seconds.  Optional filter
        @src_station avoids returning until a chat message from that
        station is received"""
        
        ev = DRatsChatEvent(src_station)
        self.__events["chat"].append(ev)
        ev.wait(timeout)

        if ev.get_text():
            return ev.get_src_station(), ev.get_text()
        else:
            return "", ""

    def incoming_chat_message(self, src, dst, text):
        for ev in self.__events["chat"]:
            if not ev.get_src_station():
                ev.set_chat_info(src, text)
                ev.set()
            elif ev.get_src_station() == src:
                ev.set_chat_info(src, text)
                ev.set()

class DRatsPluginServer(SimpleXMLRPCServer):
    def __init__(self):
        SimpleXMLRPCServer.__init__(self, ("localhost", 9100))

        self.__thread = None

        self.__proxy = DRatsPluginProxy()
            
        self.register_function(self.__proxy.send_chat, "send_chat")
        self.register_function(self.__proxy.list_ports, "list_ports")
        self.register_function(self.__proxy.send_file, "send_file")
        self.register_function(self.__proxy.submit_rpcjob, "submit_rpcjob")
        self.register_function(self.__proxy.get_result, "get_result")
        self.register_function(self.__proxy.wait_for_chat, "wait_for_chat")

    def serve_background(self):
        self.__thread = threading.Thread(target=self.serve_forever)
        self.__thread.setDaemon(True)
        self.__thread.start()
        print "Pluginsrv: Started serve_forever() thread"
                               
    def incoming_chat_message(self, *args):
        self.__proxy.incoming_chat_message(*args)

    def get_proxy(self):
        return self.__proxy
