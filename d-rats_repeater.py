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

from __future__ import absolute_import
from __future__ import print_function
import threading
import time
import socket
import six.moves.configparser
import os

import gettext
gettext.install("D-RATS")

from d_rats import dplatform
from d_rats import transport
from d_rats import comm
from d_rats.debug import printlog

if __name__ == "__main__":
    from optparse import OptionParser

    o = OptionParser()
    o.add_option("-c", "--config",
                 dest="config",
                 help="Use alternate configuration directory")
    o.add_option("-d", "--debug",
                 dest="debug",
                 action="store_true",
                 help="Show debug messages on stdout")
    o.add_option("-C", "--console",
                 dest="console",
                 action="store_true",
                 help="Run in console mode only")
    o.add_option("-L", "--log",
                 dest="logpath",
                 help="Use alternate log file directory")
    (opts, args) = o.parse_args()

    if opts.config:
        dplatform.get_platform(opts.config)

from d_rats.comm import SWFSerial
from d_rats import utils

def call_with_lock(lock, fn, *args):
    lock.acquire()
    r = fn(*args)
    lock.release()
    return r

IN = 0
OUT = 1
PEEK = 2

def DEBUG(str):
    pass
    #print str

class CallInfo:
    def __init__(self, call, transport):
        self.__call = call
        self.just_heard(transport)

    def get_call(self):
        return self.__call

    def just_heard(self, transport):
        self.__heard = time.time()
        self.__transport = transport

    def last_heard(self):
        return time.time() - self.__heard

    def last_transport(self):
        return self.__transport

def call_in_list(callinfo, call):
    for info in callinfo:
        if call == info.get_call():
            return True
    return False

class Repeater:
    def __init__(self, id="D-RATS Network Proxy", reqauth=False, trustlocal=False, gps_okay_ports=[]):
        self.paths = []
        self.calls = {}
        self.thread = None
        self.enabled = True
        self.socket = None
        self.repeat_thread = None
        self.id = id
        self.reqauth = reqauth
        self.trustlocal = trustlocal
        self.condition = threading.Condition()
        self.gps_socket = None
        self.gps_sockets = []
        self.gps_okay_ports = gps_okay_ports

        # Forget port for a station after 10 minutes
        self.__call_timeout = 600

    def __should_repeat_gps(self, transport, frame):
        if not self.gps_okay_ports:
            return True
        else:
            return transport.name in self.gps_okay_ports

    def __repeat(self, transport, frame):
        if frame.d_station == "!":
            return

        if frame.s_station == frame.d_station == "CQCQCQ" and \
                frame.session == 1 and \
                frame.data.startswith("$") and \
                self.__should_repeat_gps(transport, frame):
            for s in self.gps_sockets:
                s.send(frame.data)

        srcinfo = self.calls.get(frame.s_station, None)
        if srcinfo is None and frame.s_station != "CQCQCQ":

            printlog("Repeater  : Adding new station %s to port %s" % (frame.s_station,transport))
            self.calls[frame.s_station] = CallInfo(frame.s_station,
                                                   transport)
        elif srcinfo:
            if srcinfo.last_transport() != transport:
                printlog("Repeater  : Station %s moved to port %s" % (frame.s_station,transport))

            srcinfo.just_heard(transport)

        dstinfo = self.calls.get(frame.d_station, None)
        if dstinfo is not None:
            if not dstinfo.last_transport().enabled:
                printlog("Repeater  : Last transport for %s is dead" % frame.d_station)
            elif dstinfo.last_heard() < self.__call_timeout:
                printlog("Repeater  : Delivering frame to %s at %s" % (frame.d_station, dstinfo.last_transport()))
                dstinfo.last_transport().send_frame(frame.get_copy())
                return
            else:
                printlog("Repeater  : Last port for %s was %i sec ago (>%i sec)" % \
                    (frame.d_station,
                     dstinfo.last_heard(),
                     self.__call_timeout))
                
        printlog("Repeater  : Repeating frame to %s on all ports" % frame.d_station)
        for path in self.paths[:]:
            if path == transport:
                continue
            if not path.enabled:
                printlog("Repeater  : Found a stale path, removing...")
                path.disable()
                self.paths.remove(path)
            else:
                path.send_frame(frame.get_copy())

    def add_new_transport(self, transport):
        self.paths.append(transport)

        def handler(frame):
            self.condition.acquire()
            try:
                self.__repeat(transport, frame)
            except Exception as e:
                printlog("Repeater  : Exception during __repeat: %s" % e)
            self.condition.release()

        transport.inhandler = handler

    def auth_exchange(self, pipe):
        username = password = None
        count = 0

        def readline(_s):
            data = ""
            while "\r\n" not in data:
                try:
                    _d = _s.read(32)
                except socket.timeout:
                    continue

                if _d == "":
                    break

                data += _d
            return data.strip()

        while (not username or not password) and count < 3:
            line = readline(pipe)
            if not line:
                continue
            try:
                cmd, value = line.split(" ", 1)
            except Exception as e:
                printlog("Repeater  : Unable to read auth command: `%s': %s" % (line, e))

                pipe.write("501 Invalid Syntax\r\n")
                break

            cmd = cmd.upper()

            if cmd == "USER" and not username and not password:
                username = value
            elif cmd == "PASS" and username and not password:
                password = value
            else:
                pipe.write("201 Protocol violation\r\n")
                break

            if username and not password:
                pipe.write("102 %s okay\r\n" % cmd)

        if not username or not password:
            printlog("Repeater  : Negotiation failed with client")

        return username, password

    def auth_user(self, pipe):
        host, port = pipe._socket.getpeername()

        if not self.reqauth:
            pipe.write("100 Authentication not required\r\n")
            return True
        elif self.trustlocal and host == "127.0.0.1":
            pipe.write("100 Authentication not required for localhost\r\n")
            return True
          
        auth_fn = dplatform.get_platform().config_file("users.txt")
        try:
            auth = open(auth_fn)
            lines = auth.readlines()
            auth.close()
        except Exception as e:
            printlog("Repeater  : Failed to open %s: %s" % (auth_fn, e))

        pipe.write("101 Authorization required\r\n")
        username, password = self.auth_exchange(pipe)

        lno = 1
        for line in lines:
            line = line.strip()
            try:
                u, p = line.split(" ", 1)
                u = u.upper()
            except Exception as e:
                printlog("Repeater  : Failed to parse line %i in users.txt: %s" % (lno, line))
                continue

            if u == username and p == password:
                printlog(("Authorized user %s" % u))
                pipe.write("200 Authorized\r\n")
                return True

        printlog("Repeater  : User %s failed to authenticate" % username)
        pipe.write("500 Not authorized\r\n")
        return False

    def accept_new(self):
        if not self.socket:
            return

        try:
            (csocket, addr) = self.socket.accept()
        except:
            return

        printlog("Repeater  : Accepted new client %s:%i" % addr)

        path = comm.SocketDataPath(csocket)
        tport = transport.Transporter(path,
                                      authfn=self.auth_user,
                                      warmup_timeout=0)
        self.add_new_transport(tport)

    def accept_new_gps(self):
        if not self.gps_socket:
            return

        try:
            (csocket, addr) = self.gps_socket.accept()
        except:
            return

        printlog("Repeater  : Accepted new GPS client %s:%i" % addr)
        self.gps_sockets.append(csocket)

    def listen_on(self, port):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setblocking(0)
        s.setsockopt(socket.SOL_SOCKET,
                     socket.SO_REUSEADDR,
                     1)
        s.bind(('0.0.0.0', port))
        s.listen(0)

        return s

    def _repeat(self):
        while self.enabled:
            self.condition.acquire()
            self.accept_new()
            self.accept_new_gps()
            self.condition.release()

            time.sleep(0.5)

        printlog("Repeater  : Repeater thread ended")

    def repeat(self):
        self.repeat_thread = threading.Thread(target=self._repeat)
        self.repeat_thread.setDaemon(True)
        self.repeat_thread.start()

    def stop(self):
        self.enabled = False

        self.condition.acquire()
        self.condition.notify()
        self.condition.release()

        if self.repeat_thread:
            printlog("Repeater  : Stopping repeater")
            self.repeat_thread.join()

        for p in self.paths:
            printlog("Repeater  : Stopping")
            p.disable()

        if self.socket:
            self.socket.close()

class RepeaterUI:
    def __init__(self):
        self.repeater = None
        self.tap = None
        self.tick = 0

        self.platform = dplatform.get_platform()
        self.config = self.load_config()

    def load_config(self):
        self.config_fn = self.platform.config_file("repeater.config")
        config = six.moves.configparser.ConfigParser()
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
        config.set("tweaks",  "allow_gps", "")

        config.read(self.config_fn)

        return config

    def add_outgoing_paths(self, id, paths):
        reqauth = self.config.get("settings", "require_auth") == "True"
        trustlocal = self.config.get("settings", "trust_local") == "True"
        gps_okay_ports = self.config.get("tweaks", "allow_gps").split(",")
        printlog("Repeater  : Repeater id is %s" % id)
        self.repeater = Repeater(id, reqauth, trustlocal, gps_okay_ports)
        for dev,param in paths:
            to = 0
            if dev.startswith("net:"):
                try:
                    net, host, port = dev.split(":", 2)
                    port = int(port)
                except Exception as e:
                    printlog(("Invalid net string: %s (%s)" % (dev, e)))
                    continue

                printlog("Repeater  : Socket %s %i (%s)" % (host, port, param))

                if param:
                    path = comm.SocketDataPath((host, port, id, param))
                else:
                    path = comm.SocketDataPath((host, port))
            elif dev.startswith("tnc:"):
                try:
                    tnc, port, device = dev.split(":", 2)
                    device = int(device)
                except Exception as e:
                    printlog("Repeater  : Invalid tnc string: %s (%s)" % (dev, e))
                    continue
                printlog("Repeater  : TNC %s %i" % (dev.replace("tnc:", ""), int(param)))
                path = comm.TNCDataPath((dev.replace("tnc:", ""), int(param)))
            else:
                printlog("Repeater  : Serial: %s %i" % (dev, int(param)))
                path = comm.SerialDataPath((dev, int(param)))
                to = 3

            path.connect()
            tport = transport.Transporter(path, warmup_timout=to,
                                          name=dev)
            self.repeater.add_new_transport(tport)


class RepeaterGUI(RepeaterUI):
    def add_serial(self, widget):
        name, portspec, param = prompt_for_port(None, pname=False)
        if portspec is None:
            return

        self.dev_list.add_item(portspec, param)

    def save_config(self, config):
        self.sync_config()
        f = open(self.config_fn, "w")
        config.write(f)
        f.close()

    def sig_destroy(self, widget, data=None):
        self.button_off(None, False)
        self.save_config(self.config)
        gtk.main_quit()

    def ev_delete(self, widget, event, data=None):
        self.button_off(None, False)
        self.save_config(self.config)
        self.repeater.stop()
        gtk.main_quit()

    def make_side_buttons(self):
        vbox = gtk.VBox(False, 2)

        but_add = gtk.Button("Add")
        but_add.connect("clicked", self.add_serial)
        but_add.set_size_request(75, 30)
        but_add.show()
        vbox.pack_start(but_add, 0,0,0)

        but_remove = gtk.Button("Remove")
        but_remove.set_size_request(75, 30)
        but_remove.connect("clicked", self.button_remove)
        but_remove.show()
        vbox.pack_start(but_remove, 0,0,0)

        vbox.show()
        
        return vbox

    def load_devices(self):
        try:
            l = eval(self.config.get("settings", "devices"))
            for d,r in l:
                self.dev_list.add_item(d, r)
        except Exception as e:
            printlog(("Unable to load devices: %s" % e))

    def make_devices(self):
        frame = gtk.Frame("Paths")

        vbox = gtk.VBox(False, 2)
        frame.add(vbox)

        hbox = gtk.HBox(False, 2)

        self.dev_list = miscwidgets.ListWidget([(gobject.TYPE_STRING, "Device"),
                                                (gobject.TYPE_STRING, "Param")])
        self.dev_list.show()
        self.load_devices()

        sw = gtk.ScrolledWindow()
        sw.add_with_viewport(self.dev_list)
        sw.show()

        hbox.pack_start(sw, 1,1,1)
        hbox.pack_start(self.make_side_buttons(), 0,0,0)
        hbox.show()

        vbox.pack_start(hbox, 1,1,1)
        
        vbox.show()
        frame.show()

        return frame

    def make_network(self):
        frame = gtk.Frame("Network")

        vbox = gtk.VBox(False, 2)
        frame.add(vbox)
        hbox = gtk.HBox(False, 2)


        self.net_enabled = gtk.CheckButton("Accept incoming connections")
        try:
            accept = self.config.getboolean("settings", "acceptnet")
        except:
            accept = True

        self.net_enabled.set_active(accept)
        self.net_enabled.show()

        hbox.pack_start(self.net_enabled, 0,0,0)

        self.entry_port = gtk.Entry()
        try:
            port = self.config.get("settings", "netport")
        except:
            port = "9000"
        
        self.entry_gpsport = gtk.Entry()
        try:
            gpsport = self.config.get("settings", "gpsport")
        except :
            port = "9500"

        self.entry_gpsport.set_text(gpsport)
        self.entry_gpsport.set_size_request(100, -1)
        self.entry_gpsport.show()
        hbox.pack_end(self.entry_gpsport, 0,0,0)

        lab = gtk.Label("GPS Port:")
        lab.show()
        hbox.pack_end(lab, 0,0,0)

        self.entry_port.set_text(port)
        self.entry_port.set_size_request(100, -1)
        self.entry_port.show()
        hbox.pack_end(self.entry_port, 0,0,0)

        lab = gtk.Label("Port:")
        lab.show()
        hbox.pack_end(lab, 0,0,0)

        hbox.show()
        vbox.pack_start(hbox, 0,0,0)

        vbox.show()
        frame.show()

        return frame

    def make_bottom_buttons(self):
        hbox = gtk.HBox(False, 2)

        self.but_on = gtk.Button("On")
        self.but_on.set_size_request(75, 30)
        self.but_on.connect("clicked", self.button_on)
        self.but_on.show()
        hbox.pack_start(self.but_on, 0,0,0)

        self.but_off = gtk.Button("Off")
        self.but_off.set_size_request(75, 30)
        self.but_off.connect("clicked", self.button_off)
        self.but_off.set_sensitive(False)
        self.but_off.show()
        hbox.pack_start(self.but_off, 0,0,0)

        hbox.show()

        return hbox        

    def make_id(self):
        frame = gtk.Frame("Repeater Callsign")

        hbox = gtk.HBox(False, 2)

        self.entry_id = gtk.Entry()
        try:
            deftxt = self.config.get("settings", "id")
        except:
            deftxt = "W1AW"

        self.entry_id.set_text(deftxt)
        self.entry_id.set_max_length(8)
        self.entry_id.show()
        hbox.pack_start(self.entry_id, 1,1,1)

        try:
            idfreq = self.config.get("settings", "idfreq")
        except:
            idfreq = "30"

        self.id_freq = make_choice(["Never", "30", "60", "120"],
                                   True,
                                   idfreq)
        self.id_freq.set_size_request(75, -1)
        #self.id_freq.show()
        hbox.pack_start(self.id_freq, 0,0,0)

        hbox.show()
        frame.add(hbox)
        frame.show()

        return frame

    def make_auth(self):
        frame = gtk.Frame("Authentication")

        hbox = gtk.HBox(False, 20)

        def toggle_option(cb, option):
            self.config.set("settings", option, str(cb.get_active()))

        self.req_auth = gtk.CheckButton("Require Authentication")
        self.req_auth.connect("toggled", toggle_option, "require_auth")
        self.req_auth.show()
        self.req_auth.set_active(self.config.getboolean("settings",
                                                        "require_auth"))
        hbox.pack_start(self.req_auth, 0, 0, 0)

        self.trust_local = gtk.CheckButton("Trust localhost")
        self.trust_local.connect("toggled", toggle_option, "trust_local")
        self.trust_local.show()
        self.trust_local.set_active(self.config.getboolean("settings",
                                                           "trust_local"))
        hbox.pack_start(self.trust_local, 0, 0, 0)

        def do_edit_users(but):
            p = dplatform.get_platform()
            p.open_text_file(p.config_file("users.txt"))

        edit_users = gtk.Button("Edit Users")
        edit_users.connect("clicked", do_edit_users)
        edit_users.show()
        edit_users.set_size_request(75, 30)
        hbox.pack_end(edit_users, 0, 0, 0)

        hbox.show()
        frame.add(hbox)
        frame.show()
        return frame

    def make_settings(self):
        vbox = gtk.VBox(False, 5)

        hbox = gtk.HBox(False, 5)

        vbox.pack_start(self.make_devices(), 1,1,1)
        vbox.pack_start(self.make_network(), 0,0,0)
        vbox.pack_start(self.make_auth(), 0,0,0)
        vbox.pack_start(self.make_id(), 0,0,0)

        vbox.pack_start(hbox, 0, 0, 0)
        hbox.show()
        vbox.show()

        self.settings = vbox

        return vbox

    def make_connected(self):
        frame = gtk.Frame("Connected Paths")

        idlist = miscwidgets.ListWidget([(gobject.TYPE_STRING, "ID")])
        idlist.show()

        self.conn_list = gtk.ScrolledWindow()
        self.conn_list.add_with_viewport(idlist)
        self.conn_list.show()

        frame.add(self.conn_list)
        frame.show()

        return frame

    def make_traffic(self):
        frame = gtk.Frame("Traffic Monitor")

        self.traffic_buffer = gtk.TextBuffer()
        self.traffic_view = gtk.TextView(buffer=self.traffic_buffer)
        self.traffic_view.set_wrap_mode(gtk.WRAP_WORD)
        self.traffic_view.show()

        self.traffic_buffer.create_mark("end",
                                        self.traffic_buffer.get_end_iter(),
                                        False)

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.add(self.traffic_view)
        sw.show()

        frame.add(sw)
        frame.show()

        return frame

    def make_monitor(self):
        vbox = gtk.VBox(False, 5)

        vbox.pack_start(self.make_connected(), 1,1,1)
        vbox.pack_start(self.make_traffic(), 1,1,1)

        vbox.show()

        return vbox

    def sync_config(self):
        id = self.entry_id.get_text()
        #idfreq = self.id_freq.get_active_text()
        port = self.entry_port.get_text()
        acceptnet = str(self.net_enabled.get_active())
        devices = self.dev_list.get_values()
        auth = self.req_auth.get_active()
        local = self.trust_local.get_active()
        gpsport = self.entry_gpsport.get_text()

        self.config.set("settings", "id", id)
        #self.config.set("settings", "idfreq", idfreq)
        self.config.set("settings", "netport", port)
        self.config.set("settings", "acceptnet", acceptnet)
        self.config.set("settings", "devices", devices)
        self.config.set("settings", "require_auth", str(auth))
        self.config.set("settings", "trust_local", str(local))
        self.config.set("settings", "gpsport", gpsport)

    def button_remove(self, widget):
        self.dev_list.remove_selected()

    def button_on(self, widget, data=None):
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
        except:
            port = 0
            gpsport = 0

        if port and enabled:
            self.repeater.socket = self.repeater.listen_on(port)
            self.repeater.gps_socket = self.repeater.listen_on(gpsport)

        #self.tap = LoopDataPath("TAP", self.repeater.condition)
        #self.repeater.paths.append(self.tap)

        self.repeater.repeat()

    def button_off(self, widget, user=True):
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
        if self.repeater:
            paths = self.repeater.paths
            l = [(x.id,) for x in paths]
        else:
            l = []

        if ("TAP",) in l:
            l.remove(("TAP",))

        self.conn_list.child.set_values(l)            

        if self.tap:
            traffic = self.tap.peek()
            end = self.traffic_buffer.get_end_iter()
            self.traffic_buffer.insert(end, utils.filter_to_ascii(traffic))

            count = self.traffic_buffer.get_line_count()
            if count > 200:
                start = self.traffic_buffer.get_start_iter()
                limit = self.traffic_buffer.get_iter_at_line(count - 200)
                self.traffic_buffer.delete(start, limit)

            endmark = self.traffic_buffer.get_mark("end")
            self.traffic_view.scroll_to_mark(endmark, 0.0, True, 0, 1)
        try:
            limit = int(self.id_freq.get_active_text())
            if (self.tick / 60) == limit:
                self.repeater.send_data(None, self.entry_id.get_text())
                self.tick = 0
        except:
            pass

        self.tick += 1

        return True

    def __init__(self):
        RepeaterUI.__init__(self)

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_default_size(450, 380)
        self.window.connect("delete_event", self.ev_delete)
        self.window.connect("destroy", self.sig_destroy)
        self.window.set_title("D-RATS Repeater Proxy")

        vbox = gtk.VBox(False, 5)

        self.tabs = gtk.Notebook()
        self.tabs.append_page(self.make_settings(), gtk.Label("Settings"))
        # FIXME: later
        # self.tabs.append_page(self.make_monitor(), gtk.Label("Monitor"))
        self.tabs.show()

        vbox.pack_start(self.tabs, 1,1,1)
        vbox.pack_start(self.make_bottom_buttons(), 0,0,0)
        vbox.show()

        self.window.add(vbox)
        self.window.show()

        #gobject.timeout_add(1000, self.update)

        try:
            if self.config.get("settings", "state") == "True":
                self.button_on(None, None)
        except Exception as e:
            printlog(e)

class RepeaterConsole(RepeaterUI):
    def main(self):
        devices = eval(self.config.get("settings", "devices"))
        self.add_outgoing_paths(self.config.get("settings", "id"), devices)

        try:
            acceptnet = eval(self.config.get("settings", "acceptnet"))
            netport = int(self.config.get("settings", "netport"))
            gpsport = int(self.config.get("settings", "gpsport"))
            idfreq = self.config.get("settings", "idfreq")
            if idfreq == "Never":
                idfreq = 0
            else:
                idfreq = int(idfreq)
        except Exception as e:
            printlog("Repeater  : Failed to parse network info: %s" % e)
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
       

if __name__=="__main__":
    import sys


    if not opts.debug:
        if opts.logpath:
            f = open(opts.logpath + "/repeater.log", "a", 0)
        else:
            p = dplatform.get_platform()
            #f = file(p.config_file("repeater.log"), "w", 0)
            f = open(p.config_file("repeater.log"), "a", 0)
        if f:
            sys.stdout = f
            sys.stderr = f
        else:
            printlog("Repeater  : Failed to open log")

    if opts.console:
        r = RepeaterConsole()
        r.main()
    else:
        import gtk
        import gobject
        from d_rats.miscwidgets import make_choice
        from d_rats import miscwidgets
        from d_rats.config import prompt_for_port

        gobject.threads_init()

        g = RepeaterGUI()
        gtk.main()

