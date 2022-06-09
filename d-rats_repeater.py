#!/usr/bin/python
'''D-Rats Repeater.'''
# pylint wants only 100 lines per module.
# pylint does not like the module name, wants "snake_case" compliance.
# pylint: disable=too-many-lines, invalid-name
#
# Copyright 2008 Dan Smith <dsmith@danplanet.com>
# Python3 conversion Copyright 2022 John Malmberg <wb8tyw@qsl.net>
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

import ast
import logging
import os
import threading
import time
import socket
import configparser

# This makes pylance happy with out overriding settings
# from the invoker of the class
if not '_' in locals():
    import gettext
    _ = gettext.gettext

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import GObject

from d_rats import dplatform
from d_rats import transport
from d_rats import comm
from d_rats.miscwidgets import make_choice
from d_rats import miscwidgets
from d_rats.config import prompt_for_port

gettext.install("D-RATS")

IN = 0
OUT = 1
PEEK = 2


class CallInfo:
    '''
    Call Information.

    :param call: Call sign
    :type call: str
    :param call_transport: Transport call was heard on
    :type call_transport: :class:`Transporter`
    '''

    def __init__(self, call, call_transport):
        self.__call = call
        self.just_heard(call_transport)

    def get_call(self):
        '''
        Get call.

        :returns: Call sign
        :rtype: str
        '''
        return self.__call

    def just_heard(self, heard_transport):
        '''
        Just heard.

        :param heard_transport: Transport that had something heard
        :type heard_transport: :class:`Transporter`
        '''
        self.__heard = time.time()
        self.__transport = heard_transport

    def last_heard(self):
        '''
        Last heard.

        :returns: Time for last heard station
        :type float:
        '''
        return time.time() - self.__heard

    def last_transport(self):
        '''
        Last transport.

        :returns: Last transport heard
        :rtype: :class:`Transporter`
        '''
        return self.__transport


def call_in_list(call_info, call):
    '''
    Call in list?

    :param call_info: list of callsign information objects
    :type call_info: list[:class:`CallInfo`]
    :param call: Call sign to lookup
    :type call: str
    :returns true: If call sign is found
    :rtype: bool
    '''
    for info in call_info:
        if call == info.get_call():
            return True
    return False


# pylint wants only 7 instance attributes per class
# pylint: disable=too-many-instance-attributes
class Repeater:
    '''
    Repeater.

    :param ident: Identity string, Default 'D-RATS Network Proxy'
    :type ident: str
    :param require_auth: True is authorization required
    :type require_auth: bool
    :param trust_local: True if local should be trusted
    :type trust_local: bool
    :param gps_okay_ports: List of GPS active TCP/IP ports, default None
    :type gps_ok_ports: list
    '''

    def __init__(self, ident="D-RATS Network Proxy",
                 require_auth=False, trust_local=False, gps_okay_ports=None):
        self.logger = logging.getLogger("Repeater")
        self.paths = []
        self.calls = {}
        self.thread = None
        self.enabled = True
        self.socket = None
        self.repeat_thread = None
        self.ident = ident
        self.require_auth = require_auth
        self.trust_local = trust_local
        self.condition = threading.Condition()
        self.gps_socket = None
        self.gps_sockets = []
        self.gps_okay_ports = []
        if gps_okay_ports:
            self.gps_okay_ports = gps_okay_ports

        # Forget port for a station after 10 minutes
        self.__call_timeout = 600

    def __should_repeat_gps(self, gps_transport, _frame):
        if not self.gps_okay_ports:
            return True
        return gps_transport.name in self.gps_okay_ports

    # pylint wants a max of 12 branches per function or method
    # pylint: disable=too-many-branches
    def __repeat(self, rpt_transport, frame):
        if frame.d_station == "!":
            return
        gps_start = '$'
        if not isinstance(frame.data, str):
            gps_start = b'$'
        if frame.s_station == frame.d_station == "CQCQCQ" and \
                frame.session == 1 and \
                frame.data.startswith(gps_start) and \
                self.__should_repeat_gps(rpt_transport, frame):
            for sock in self.gps_sockets:
                sock.send(frame.data)

        src_info = self.calls.get(frame.s_station, None)
        if src_info is None and frame.s_station != "CQCQCQ":

            self.logger.info("__repeat: Adding new station %s to port %s",
                             frame.s_station, rpt_transport)
            self.calls[frame.s_station] = CallInfo(frame.s_station,
                                                   rpt_transport)
        elif src_info:
            if src_info.last_transport() != rpt_transport:
                self.logger.info("__repeat: Station %s moved to port %s",
                                 frame.s_station, rpt_transport)

            src_info.just_heard(rpt_transport)

        dst_info = self.calls.get(frame.d_station, None)
        if dst_info is not None:
            if not dst_info.last_transport().enabled:
                self.logger.info("__repeat: Last transport for %s is dead",
                                 frame.d_station)
            elif dst_info.last_heard() < self.__call_timeout:
                self.logger.info("__repeat: Delivering frame to %s at %s",
                                 frame.d_station, dst_info.last_transport())
                dst_info.last_transport().send_frame(frame.get_copy())
                return
            self.logger.info("__repeat: Last port for %s was %i sec"
                             " ago (>%i sec)",
                             frame.d_station,
                             dst_info.last_heard(),
                             self.__call_timeout)

        self.logger.info("__repeat: Repeating frame to %s on all ports",
                         frame.d_station)
        for path in self.paths[:]:
            if path == rpt_transport:
                continue
            if not path.enabled:
                self.logger.info("__repeat: Found a stale path, removing...")
                path.disable()
                self.paths.remove(path)
            else:
                path.send_frame(frame.get_copy())

    def add_new_transport(self, new_transport):
        '''
        Add new transport.

        :param new_transport: Transport to add
        :type new_transport: :class:`Transporter`
        '''
        self.paths.append(new_transport)

        def handler(frame):
            self.condition.acquire()
            try:
                self.__repeat(new_transport, frame)
            # pylint: disable=broad-except
            except Exception:
                self.logger.info("add_new_transport: Generic Exception",
                                 exc_info=True)
            self.condition.release()

        new_transport.inhandler = handler

    def auth_exchange(self, pipe):
        '''
        Authorization Exchange.

        :param pipe: socket object
        :type pipe: socket
        :returns: Data for exchange
        :rtype: tuple[str, str]
        '''
        username = password = None
        count = 0

        def readline(sock):
            data = ""
            while "\r\n" not in data:
                try:
                    data_part = sock.read(32)
                except socket.timeout:
                    continue

                if data_part == b"":
                    break

                data += data_part.decode('utf-8', 'replace')
            return data.strip()

        while (not username or not password) and count < 3:
            line = readline(pipe)
            if not line:
                continue
            try:
                cmd, value = line.split(" ", 1)
            except ValueError:
                pipe.write(b"501 Invalid Syntax\r\n")
                break

            cmd = cmd.upper()

            if cmd == "USER" and not username and not password:
                username = value
            elif cmd == "PASS" and username and not password:
                password = value
            else:
                pipe.write(b"201 Protocol violation\r\n")
                break

            if username and not password:
                pipe.write(b"102 %s okay\r\n" % cmd)

        if not username or not password:
            self.logger.info("auth_exchange: Negotiation failed with client")

        return username, password

    def auth_user(self, pipe):
        '''
        Authorize user.

        :param pipe: Pipe object
        :type pipe: socket
        :return: True if authorized
        :rtype: bool
        '''
        # pylint: disable=protected-access
        host, _port = pipe._socket.getpeername()

        if not self.require_auth:
            pipe.write(b"100 Authentication not required\r\n")
            return True
        if self.trust_local and host == "127.0.0.1":
            pipe.write(b"100 Authentication not required for localhost\r\n")
            return True

        auth_fname = dplatform.get_platform().config_file("users.txt")
        try:
            auth = open(auth_fname)
            lines = auth.readlines()
            auth.close()
        except (NameError, FileNotFoundError) as err:
            self.logger.info("auth_user: Failed to open %s: %s",
                             auth_fname, err)

        pipe.write(b"101 Authorization required\r\n")
        username, password = self.auth_exchange(pipe)

        lno = 1
        for line in lines:
            line = line.strip()
            try:
                user, passwd = line.split(" ", 1)
                user = user.upper()
            except ValueError as err:
                self.logger.info("auth_user: Failed to parse "
                                 "line %i in users.txt: %s",
                                 lno, line)
                continue

            if user == username and passwd == password:
                self.logger.info("Authorized user %s", user)
                pipe.write(b"200 Authorized\r\n")
                return True

        self.logger.info("auth_user: User %s failed to authenticate", username)
        pipe.write(b"500 Not authorized\r\n")
        return False

    def accept_new(self):
        '''Accept new.'''
        if not self.socket:
            return

        try:
            (csocket, addr) = self.socket.accept()
        except BlockingIOError:
            return

        addr_str = "%s:%i" % addr
        self.logger.info("accept_new: Accepted new client %s", addr_str)

        path = comm.SocketDataPath(csocket)
        tport = transport.Transporter(path,
                                      authfn=self.auth_user,
                                      warmup_timeout=0)
        self.add_new_transport(tport)

    def accept_new_gps(self):
        '''Accept new GPS.'''
        if not self.gps_socket:
            return

        try:
            (csocket, addr) = self.gps_socket.accept()
        except BlockingIOError:
            return

        addr_str = "%s:$i" % addr
        self.logger.info("accept_new_gps: Accepted new GPS client %s", addr_str)
        self.gps_sockets.append(csocket)

    @staticmethod
    def listen_on(port):
        '''
        Listen on.

        :param port: TCP/IP port number
        :type port: int
        :returns: socket object
        :rtype: socket
        '''
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setblocking(0)
        sock.setsockopt(socket.SOL_SOCKET,
                        socket.SO_REUSEADDR,
                        1)
        sock.bind(('0.0.0.0', port))
        sock.listen(0)

        return sock

    def _repeat(self):
        while self.enabled:
            self.condition.acquire()
            self.accept_new()
            self.accept_new_gps()
            self.condition.release()

            time.sleep(0.5)

        self.logger.info("_repeat: Repeater thread ended")

    def repeat(self):
        '''Repeat.'''
        self.repeat_thread = threading.Thread(target=self._repeat)
        self.repeat_thread.setDaemon(True)
        self.repeat_thread.start()

    def stop(self):
        '''Stop.'''
        self.enabled = False

        self.condition.acquire()
        self.condition.notify()
        self.condition.release()

        if self.repeat_thread:
            self.logger.info("stop: Stopping repeater")
            self.repeat_thread.join()

        for path in self.paths:
            self.logger.info("stop: Stopping")
            path.disable()

        if self.socket:
            self.socket.close()


class RepeaterUI:
    '''Repeater UI.'''

    def __init__(self):
        self.logger = logging.getLogger("RepeaterUI")
        self.repeater = None
        self.tap = None
        self.tick = 0

        self.platform = dplatform.get_platform()
        self.config = self.load_config()

    def load_config(self):
        '''
        Load configuration.

        :returns: Config object
        :rtype: :class:`DratsConfig`

        '''
        self.config_fn = self.platform.config_file("repeater.config")
        config = configparser.ConfigParser()
        config.add_section("settings")
        config.set("settings", "devices", "[]")
        config.set("settings", "acceptnet", "True")
        config.set("settings", "netport", "9000")
        config.set("settings", "id", "W1AW")
        config.set("settings", "idfreq", "30")
        config.set("settings", "require_auth", "False")
        config.set("settings", "trust_local", "True")
        config.set("settings", "gpsport", "9500")

        config.add_section("tweaks")
        config.set("tweaks", "allow_gps", "")

        config.read(self.config_fn)

        return config

    # pylint wants a max of 15 local variables
    # pylint: disable=too-many-locals
    def add_outgoing_paths(self, ident, paths):
        '''
        Add outgoing paths.

        :param ident: Path id
        :type ident: str
        :param path: Paths data
        :type path: list[tuple]
        '''
        require_auth = self.config.get("settings", "require_auth") == "True"
        trust_local = self.config.get("settings", "trust_local") == "True"
        gps_okay_ports = self.config.get("tweaks", "allow_gps").split(",")
        self.logger.info("add_outgoing_path: Repeater id is %s", ident)
        self.repeater = Repeater(ident, require_auth,
                                 trust_local, gps_okay_ports)
        for dev, param in paths:
            timeout = 0
            if dev.startswith("net:"):
                try:
                    _net, host, port = dev.split(":", 2)
                    port = int(port)
                except ValueError as err:
                    self.logger.info("add_outgoing_paths: "
                                     "Invalid net string: %s (%s)",
                                     dev, err)
                    continue

                self.logger.info("add_outgoing_paths: Socket %s %i (%s)",
                                 host, port, param)

                if param:
                    if ident == 'MYCALL':
                        self.logger.info("add_outgoing_paths: "
                                         "invalid callsign %s for %s",
                                         ident, dev)
                        continue
                    path = comm.SocketDataPath((host, port, ident, param))
                else:
                    path = comm.SocketDataPath((host, port))
            elif dev.startswith("tnc-ax25:"):
                if ident == 'MYCALL':
                    self.logger.info("add_outgoing_paths: "
                                     "invalid callsign %s for %s",
                                     ident, dev)
                    continue
                _tnc, radio_port, tncport, digi_path = port.split(":")
                digi_path = digi_path.replace(";", ",")
                radio_port = "%s:%s" % (radio_port, tncport)
                new_dev = dev.replace('tnc-ax25:', "")
                param_int = int(param)
                self.logger.info("add_outgoing_paths: TNC-AX25 %s %i",
                                 new_dev, param_int)
                path = comm.TNCAX25DataPath((new_dev, param_int,
                                             ident, digi_path))
            elif dev.startswith("tnc:"):
                try:
                    _tnc, port, device = dev.split(":", 2)
                    device = int(device)
                except ValueError as err:
                    self.logger.info("add_outgoing_paths: "
                                     "Invalid tnc string: %s (%s)",
                                     dev, err)
                    continue
                new_dev = dev.replace('tnc:', "")
                param_int = int(param)
                self.logger.info("add_outgoing_paths: TNC %s %i",
                                 new_dev, param_int)
                path = comm.TNCDataPath((new_dev, param_int))
            elif dev.startswith("dongle:"):
                if ident == 'MYCALL':
                    self.logger.info("add_outgoing_paths: "
                                     "invalid callsign %s for %s",
                                     ident, dev)
                    continue
                self.logger.info("add_outgoing_paths: Dongle %s",
                                 new_dev)
                path = comm.SocketDataPath(("127.0.0.1", 20003, ident, None))
            elif dev.startswith("agwpe:"):
                new_dev = dev.replace("agwpe:", "")
                self.logger.info("add_outgoing_paths: AGWPE %s",
                                 new_dev)
                path = comm.AGWDataPath(new_dev, 0.5)
            else:
                param_int = int(param)
                self.logger.info("add_outgoing_paths: Serial: %s %i",
                                 dev, param_int)
                path = comm.SerialDataPath((dev, param_int))
                timeout = 3

            path.connect()
            tport = transport.Transporter(path, warmup_timeout=timeout,
                                          name=dev)
            self.repeater.add_new_transport(tport)


# pylint wants a max of 7 instance attributes
# pylint: disable=too-many-instance-attributes
class RepeaterGUI(RepeaterUI):
    '''Repeater GUI.'''

    def __init__(self):
        RepeaterUI.__init__(self)

        self.logger = logging.getLogger("RepeaterGUI")
        self.window = Gtk.Window()
        # self.window = Gtk.Window(Gtk.WINDOW_TOPLEVEL)
        self.window.set_default_size(450, 380)
        self.window.connect("delete_event", self.ev_delete)
        self.window.connect("destroy", self.sig_destroy)
        self.window.set_title("D-RATS Repeater Proxy")
        self.traffic_buffer = None
        self.traffic_view = None
        self.conn_list = None
        self.trust_local = None
        self.req_auth = None
        self.id_freq = None
        self.entry_id = None
        self.entry_port = None
        self.entry_gpsport = None
        self.net_enabled = None
        self.dev_list = None

        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 5)

        self.tabs = Gtk.Notebook()
        self.tabs.append_page(self.make_settings(), Gtk.Label.new("Settings"))
        # pylint: disable=fixme
        # FIXME: later
        # self.tabs.append_page(self.make_monitor(), Gtk.Label.new("Monitor"))
        self.tabs.show()

        vbox.pack_start(self.tabs, 1, 1, 1)
        vbox.pack_start(self.make_bottom_buttons(), 0, 0, 0)
        vbox.show()

        self.window.add(vbox)
        self.window.show()

        # GLib.timeout_add(1000, self.update)

        try:
            if self.config.get("settings", "state") == "True":
                self.button_on(None)
        except (configparser.NoOptionError, OSError):
            self.logger.info("__init__: Starting repeater error.",
                             exc_info=True)

    def add_serial(self, _widget):
        '''
        Add serial port button click handler.

        :param _widget: Button widget, unused
        :type _widget: :class:`Gtk.Button`
        '''
        _name, portspec, param = prompt_for_port(None, pname=False)
        if portspec is None:
            return

        self.dev_list.add_item(portspec, param)

    def save_config(self, config):
        '''
        Save config.

        :param config: Config object
        :type config: :class:`DratsConfig`
        '''
        self.sync_config()
        file_handle = open(self.config_fn, "w")
        config.write(file_handle)
        file_handle.close()

    def sig_destroy(self, _widget, _data=None):
        '''
        Destroy Event handler.

        Signals that the widget is being destroyed.

        :param _widget: :class:`Gtk.Window`
        :param _data: Unused, default None
        '''
        self.button_off(None, False)
        # Documentation states this signal should not be used
        # for saving the widget state.
        self.save_config(self.config)
        Gtk.main_quit()

    def ev_delete(self, _widget, _event):
        '''
        Delete Event handler.

        This event is signaled by a top level window being closed.

        :param _widget: Widget being deleted, Unused
        :type _widget: :class:`Gtk.Window`
        :param _event: Event signaled, Unused
        :type _event: :class:`Gtk.Event`
        :returns: True to stop other handlers from handling event.
        :rtype bool
        '''
        self.button_off(None, False)
        self.save_config(self.config)
        if self.repeater:
            self.repeater.stop()
        Gtk.main_quit()
        return False

    def make_side_buttons(self):
        '''
        Make side buttons.

        :returns: Gtk.Box object with buttons
        :rtype: :class:`Gtk.Box`
        '''
        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 2)

        but_add = Gtk.Button.new_with_label("Add")
        but_add.connect("clicked", self.add_serial)
        but_add.set_size_request(75, 30)
        but_add.show()
        vbox.pack_start(but_add, 0, 0, 0)

        but_remove = Gtk.Button.new_with_label("Remove")
        but_remove.set_size_request(75, 30)
        but_remove.connect("clicked", self.button_remove)
        but_remove.show()
        vbox.pack_start(but_remove, 0, 0, 0)

        vbox.show()

        return vbox

    def load_devices(self):
        '''Load devices.'''
        try:
            devices = ast.literal_eval(self.config.get("settings", "devices"))
            for device, radio in devices:
                self.dev_list.add_item(device, radio)
        except (ValueError, configparser.NoOptionError) as err:
            self.logger.info("load_devices: Unable to load devices %s", err)

    def make_devices(self):
        '''
        Make Devices.

        :returns: Gtk.Frame object
        :rtype: :class:`Gtk.Frame`
        '''
        frame = Gtk.Frame.new("Paths")

        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 2)
        frame.add(vbox)

        hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 2)

        self.dev_list = miscwidgets.ListWidget([(GObject.TYPE_STRING, "Device"),
                                                (GObject.TYPE_STRING, "Param")])
        self.dev_list.show()
        self.load_devices()

        # sw = Gtk.ScrolledWindow()
        list_box = Gtk.ListBox()
        list_box.add(self.dev_list)
        list_box.show()

        hbox.pack_start(list_box, 1, 1, 1)
        hbox.pack_start(self.make_side_buttons(), 0, 0, 0)
        hbox.show()

        vbox.pack_start(hbox, 1, 1, 1)

        vbox.show()
        frame.show()

        return frame

    def make_network(self):
        '''
        Make Network.

        :returns: Gtk.Frame object
        :rtype: :class:`Gtk.Frame`
        '''
        frame = Gtk.Frame.new("Network")

        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 2)
        frame.add(vbox)
        hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 2)


        self.net_enabled = Gtk.CheckButton.new_with_label(
            "Accept incoming connections")
        try:
            accept = self.config.getboolean("settings", "acceptnet")
        except configparser.NoOptionError:
            accept = True

        self.net_enabled.set_active(accept)
        self.net_enabled.show()

        hbox.pack_start(self.net_enabled, 0, 0, 0)

        self.entry_port = Gtk.Entry()
        try:
            port = self.config.get("settings", "netport")
        except configparser.NoOptionError:
            port = "9000"

        self.entry_gpsport = Gtk.Entry()
        try:
            gpsport = self.config.get("settings", "gpsport")
        except configparser.NoOptionError:
            port = "9500"

        self.entry_gpsport.set_text(gpsport)
        self.entry_gpsport.set_size_request(100, -1)
        self.entry_gpsport.show()
        hbox.pack_end(self.entry_gpsport, 0, 0, 0)

        lab = Gtk.Label.new("GPS Port:")
        lab.show()
        hbox.pack_end(lab, 0, 0, 0)

        self.entry_port.set_text(port)
        self.entry_port.set_size_request(100, -1)
        self.entry_port.show()
        hbox.pack_end(self.entry_port, 0, 0, 0)

        lab = Gtk.Label.new("Port:")
        lab.show()
        hbox.pack_end(lab, 0, 0, 0)

        hbox.show()
        vbox.pack_start(hbox, 0, 0, 0)

        vbox.show()
        frame.show()

        return frame

    def make_bottom_buttons(self):
        '''
        Make bottom buttons.

        :returns: Gtk.Box object with buttons
        :rtype: :class:`Gtk.Box`
        '''
        hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 2)

        self.but_on = Gtk.Button.new_with_label("On")
        self.but_on.set_size_request(75, 30)
        self.but_on.connect("clicked", self.button_on)
        self.but_on.show()
        hbox.pack_start(self.but_on, 0, 0, 0)

        self.but_off = Gtk.Button.new_with_label("Off")
        self.but_off.set_size_request(75, 30)
        self.but_off.connect("clicked", self.button_off)
        self.but_off.set_sensitive(False)
        self.but_off.show()
        hbox.pack_start(self.but_off, 0, 0, 0)

        hbox.show()

        return hbox

    def make_id(self):
        '''
        Make ID for Repeater Callsign.

        :returns: Gtk.Frame object
        :rtype: :class:`Gtk.Frame`
        '''
        frame = Gtk.Frame.new("Repeater Callsign")

        hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 2)

        self.entry_id = Gtk.Entry()
        try:
            deftxt = self.config.get("settings", "id")
        except configparser.NoOptionError:
            self.logger.info("make_id 'id' broad-except",
                             exc_info=True)
            deftxt = "MYCALL"

        self.entry_id.set_text(deftxt)
        self.entry_id.set_max_length(8)
        self.entry_id.show()
        hbox.pack_start(self.entry_id, 1, 1, 1)

        try:
            idfreq = self.config.get("settings", "idfreq")
        except configparser.NoOptionError:
            idfreq = "30"

        self.id_freq = make_choice(["Never", "30", "60", "120"],
                                   True,
                                   idfreq)
        self.id_freq.set_size_request(75, -1)
        # self.id_freq.show()
        hbox.pack_start(self.id_freq, 0, 0, 0)

        hbox.show()
        frame.add(hbox)
        frame.show()

        return frame

    def make_auth(self):
        '''
        Make authentication.

        :returns: Gtk.Frame object
        :rtype: :class:`Gtk.Frame`
        '''
        frame = Gtk.Frame.new("Authentication")

        hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 20)

        def toggle_option(check_button, option):
            '''
            Toggle Option CheckButton toggled handler.

            :param check_button: Button widget signaled
            :type check_button: :class:`Gtk.CheckButton`
            :param option: option name
            :type option: str
            '''
            self.config.set("settings", option,
                            str(check_button.get_active()))

        self.req_auth = Gtk.CheckButton.new_with_label("Require Authentication")
        self.req_auth.connect("toggled", toggle_option, "require_auth")
        self.req_auth.show()
        self.req_auth.set_active(self.config.getboolean("settings",
                                                        "require_auth"))
        hbox.pack_start(self.req_auth, 0, 0, 0)

        self.trust_local = Gtk.CheckButton.new_with_label("Trust localhost")
        self.trust_local.connect("toggled", toggle_option, "trust_local")
        self.trust_local.show()
        self.trust_local.set_active(self.config.getboolean("settings",
                                                           "trust_local"))
        hbox.pack_start(self.trust_local, 0, 0, 0)

        def clicked_edit_users(_button):
            '''
            Clicked Edit Users Button handler.

            :param _button: Button Widget signaled, unused
            :type _button: :class:`Gtk.Button`
            '''
            platform = dplatform.get_platform()
            platform.open_text_file(platform.config_file("users.txt"))

        edit_users = Gtk.Button.new_with_label("Edit Users")
        edit_users.connect("clicked", clicked_edit_users)
        edit_users.show()
        edit_users.set_size_request(75, 30)
        hbox.pack_end(edit_users, 0, 0, 0)

        hbox.show()
        frame.add(hbox)
        frame.show()
        return frame

    def make_settings(self):
        '''
        Make settings display.

        :returns: Gtk.Box with settings
        :rtype: :class:`Gtk.Box`
        '''
        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 5)

        hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 5)

        vbox.pack_start(self.make_devices(), 1, 1, 1)
        vbox.pack_start(self.make_network(), 0, 0, 0)
        vbox.pack_start(self.make_auth(), 0, 0, 0)
        vbox.pack_start(self.make_id(), 0, 0, 0)

        vbox.pack_start(hbox, 0, 0, 0)
        hbox.show()
        vbox.show()

        self.settings = vbox

        return vbox

    def make_connected(self):
        '''
        Connected Paths.

        :returns: Gtk.Frame object with paths
        :rtype: :class:`Gtk.Frame`
        '''
        frame = Gtk.Frame.new("Connected Paths")

        idlist = miscwidgets.ListWidget([(GObject.TYPE_STRING, "ID")])
        idlist.show()

        self.conn_list = Gtk.ScrolledWindow()
        self.conn_list.add(idlist)
        self.conn_list.show()

        frame.add(self.conn_list)
        frame.show()

        return frame

    def make_traffic(self):
        '''
        Make Traffic Monitor.

        :returns: Gtk Frame Object for traffic monitor
        :rtype: :class:`Gtk.Frame`
        '''
        frame = Gtk.Frame.new("Traffic Monitor")

        self.traffic_buffer = Gtk.TextBuffer()
        self.traffic_view = Gtk.TextView.new_with_buffer(
            buffer=self.traffic_buffer)
        self.traffic_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.traffic_view.show()

        self.traffic_buffer.create_mark("end",
                                        self.traffic_buffer.get_end_iter(),
                                        False)

        scroll_window = Gtk.ScrolledWindow()
        scroll_window.set_policy(Gtk.PolicyType.AUTOMATIC,
                                 Gtk.PolicyType.AUTOMATIC)
        scroll_window.add(self.traffic_view)
        scroll_window.show()

        frame.add(scroll_window)
        frame.show()

        return frame

    def make_monitor(self):
        '''
        Make Monitor.

        :returns: Box object that is displayed.
        :rtype: :class:`Gtk.Box`
        '''
        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 5)

        vbox.pack_start(self.make_connected(), 1, 1, 1)
        vbox.pack_start(self.make_traffic(), 1, 1, 1)

        vbox.show()

        return vbox

    def sync_config(self):
        '''Synchronize Config.'''
        ident = self.entry_id.get_text()
        # idfreq = self.id_freq.get_active_text()
        port = self.entry_port.get_text()
        acceptnet = str(self.net_enabled.get_active())
        devices = self.dev_list.get_values()
        if not devices:
            devices = '[]'
        auth = self.req_auth.get_active()
        local = self.trust_local.get_active()
        gpsport = self.entry_gpsport.get_text()

        self.config.set("settings", "id", ident)
        # self.config.set("settings", "idfreq", idfreq)
        self.config.set("settings", "netport", port)
        self.config.set("settings", "acceptnet", acceptnet)
        self.config.set("settings", "devices", devices)
        self.config.set("settings", "require_auth", str(auth))
        self.config.set("settings", "trust_local", str(local))
        self.config.set("settings", "gpsport", gpsport)

    def button_remove(self, _widget):
        '''
        Button Remove clicked handler.

        :param _widget: Button being clicked, unused
        :type _widget: :class:`Gtk.Button`
        '''
        self.dev_list.remove_selected()

    def button_on(self, _widget):
        '''
        Button On clicked handler.

        :param _widget: Button clicked, unused
        :type _widget: :class:`Gtk.Widget`
        '''
        self.tick = 0

        self.config.set("settings", "state", "True")
        self.save_config(self.config)

        self.but_off.set_sensitive(True)
        self.but_on.set_sensitive(False)
        self.settings.set_sensitive(False)

        self.add_outgoing_paths(self.config.get("settings", "id"),
                                self.dev_list.get_values())

        try:
            port = int(self.entry_port.get_text())
            gpsport = int(self.entry_gpsport.get_text())
            enabled = self.net_enabled.get_active()
        except ValueError:
            port = 0
            gpsport = 0

        if port and enabled:
            self.repeater.socket = self.repeater.listen_on(port)
            self.repeater.gps_socket = self.repeater.listen_on(gpsport)

        #self.tap = LoopDataPath("TAP", self.repeater.condition)
        #self.repeater.paths.append(self.tap)

        self.repeater.repeat()

    def button_off(self, _widget, user=True):
        '''
        Button Off.

        :param _widget: Unused
        :param user: Mode of operation, Default True
        '''
        if user:
            self.config.set("settings", "state", "False")
            self.save_config(self.config)

        self.but_off.set_sensitive(False)
        self.but_on.set_sensitive(True)
        self.settings.set_sensitive(True)

        if self.repeater:
            self.repeater.stop()
            self.repeater = None
            self.tap = None

    def update(self):
        '''Update.'''
        if self.repeater:
            paths = self.repeater.paths
            path_list = [(x.ident,) for x in paths]
        else:
            path_list = []

        if ("TAP",) in path_list:
            path_list.remove(("TAP",))

        self.conn_list.get_child().set_values(path_list)

        # self.tap not currently implemented
        # if self.tap:
        #     traffic = self.tap.peek()
        #     end = self.traffic_buffer.get_end_iter()
        #     self.traffic_buffer.insert(end, utils.filter_to_ascii(traffic))
        #
        #     count = self.traffic_buffer.get_line_count()
        #     if count > 200:
        #         start = self.traffic_buffer.get_start_iter()
        #         limit = self.traffic_buffer.get_iter_at_line(count - 200)
        #         self.traffic_buffer.delete(start, limit)
        #
        #     endmark = self.traffic_buffer.get_mark("end")
        #     self.traffic_view.scroll_to_mark(endmark, 0.0, True, 0, 1)
        # try:
        #     limit = int(self.id_freq.get_active_text())
        #     if (self.tick / 60) == limit:
        #         self.repeater.send_data(None, self.entry_id.get_text())
        #         self.tick = 0
        # except ValueError:
        #     pass

        self.tick += 1

        return True


class RepeaterConsole(RepeaterUI):
    '''Repeater Console.'''

    def __init__(self):
        RepeaterUI.__init__(self)
        self.logger = logging.getLogger("RepeaterConsole")

    def main(self):
        '''Main Routine.'''
        devices = ast.literal_eval(self.config.get("settings", "devices"))
        self.add_outgoing_paths(self.config.get("settings", "id"), devices)

        try:
            acceptnet = ast.literal_eval(self.config.get("settings",
                                                         "acceptnet"))
            netport = int(self.config.get("settings", "netport"))
            gpsport = int(self.config.get("settings", "gpsport"))
            idfreq = self.config.get("settings", "idfreq")
            if idfreq == "Never":
                idfreq = 0
            else:
                idfreq = int(idfreq)
        except (ValueError, configparser.NoOptionError) as err:
            self.logger.info("main: Failed to parse network info: %s", err)
            acceptnet = False

        if acceptnet:
            self.repeater.socket = self.repeater.listen_on(netport)
            self.repeater.gps_socket = self.repeater.listen_on(gpsport)

        self.repeater.repeat()

        while True:
            try:
                time.sleep(0.25)
            except KeyboardInterrupt:
                self.repeater.stop()
                break


def main():
    '''D-Rats Repeater main program.'''

    import argparse

    gettext.install("D-RATS")
    lang = gettext.translation("D-RATS",
                               localedir="locale",
                               fallback=True)
    lang.install()
    # pylint: disable=global-statement
    global _
    _ = lang.gettext

    platform = dplatform.get_platform()
    def_config_dir = platform.config_dir()

    # pylint: disable=too-few-public-methods
    class LoglevelAction(argparse.Action):
        '''
        Custom Log Level action.

        This allows entering a log level command line argument
        as either a known log level name or a number.
        '''

        def __init__(self, option_strings, dest, nargs=None, **kwargs):
            if nargs is not None:
                raise ValueError("nargs is not allowed")
            argparse.Action.__init__(self, option_strings, dest, **kwargs)

        def __call__(self, parser, namespace, values, option_strings=None):
            level = values.upper()
            level_name = logging.getLevelName(level)
            # Contrary to documentation, the above returns for me
            # an int if given a name or number of a known named level and
            # str if given a number for a level with out a name.
            if isinstance(level_name, int):
                level_name = level
            elif level_name.startswith('Level '):
                level_name = int(level)
            setattr(namespace, self.dest, level_name)

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description=_('DRATS-REPEATER'))
    parser.add_argument('-c', '--config',
                        default=def_config_dir,
                        help="Use alternate configuration directory")

    # While loglevel actually returns an int, it needs to be set to the
    # default type of str for the action routine to handle both named and
    # numbered levels.
    parser.add_argument('--loglevel',
                        action=LoglevelAction,
                        default='INFO',
                        help=_('LOGLEVEL TO TEST WITH'))

    parser.add_argument("-d", "--debug",
                        action="store_true",
                        help="Show debug messages on stdout")

    parser.add_argument("-C", "--console",
                        action="store_true",
                        help="Run in console mode only")

    parser.add_argument("-L", "--log",
                        dest="log_path",
                        help="Use alternate log file directory")

    args = parser.parse_args()

    log_filename = platform.config_file("repeater.log")
    if args.log_path:
        log_filename = os.path.join(args.log_path, "repeater.log")

    if args.debug:
        logging.basicConfig(
            format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
            datefmt="%m/%d/%Y %H:%M:%S",
            level=args.loglevel)
    else:
        logging.basicConfig(
            filename=log_filename,
            format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
            datefmt="%m/%d/%Y %H:%M:%S",
            level=args.loglevel)

    if args.config:
        dplatform.get_platform(args.config)

    if args.console:
        repeater = RepeaterConsole()
        repeater.main()
    else:

        # Not needed since version 3.11
        # GObject.threads_init()

        _gui = RepeaterGUI()
        Gtk.main()

if __name__ == "__main__":
    main()
