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

from __future__ import absolute_import
from __future__ import print_function

#importing printlog() wrapper
from ..debug import printlog

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import GObject

import time
import os

from d_rats.ui.main_common import MainWindowTab
from d_rats.ui import main_events
from d_rats.ui import conntest
from d_rats.sessions import rpc
from d_rats import station_status
from d_rats import signals
from d_rats import image
from d_rats import miscwidgets
from d_rats import inputdialog
from d_rats import utils

def prompt_for_account(config):
    accounts = {}
    for section in config.options("incoming_email"):
        info = config.get("incoming_email", section).split(",")
        key = "%s on %s" % (info[1], info[0])
        accounts[key] = info

    wl2k_call = config.get("user", "callsign")
    wl2k_ssid = config.get("prefs", "msg_wl2k_ssid").strip()
    if wl2k_ssid:
        wl2k_call = "%s-%s" % (wl2k_call, wl2k_ssid)

    accounts["Other"] = ["", "", "", "", "", "110"]
    accounts["WL2K"] = ["@WL2K", wl2k_call, "", "", "", "0"]
    default = accounts.keys()[0]

    account = miscwidgets.make_choice(accounts.keys(), False, default)
    host = Gtk.Entry()
    user = Gtk.Entry()
    pasw = Gtk.Entry()
    ussl = Gtk.CheckButton()
    port = Gtk.SpinButton()
    port.set_adjustment(Gtk.Adjustment.new(110, 1, 65535, 1, 0, 0))
    port.set_digits(0)

    disable = [host, user, pasw, ussl, port]

    pasw.set_visibility(False)

    def choose_account(box):
        info = accounts[box.get_active_text()]
        for i in disable:
            i.set_sensitive(not info[0])
        host.set_text(info[0])
        user.set_text(info[1])
        pasw.set_text(info[2])
        ussl.set_active(info[4] == "True")
        port.set_value(int(info[5]))
    account.connect("changed", choose_account)
    choose_account(account)

    d = inputdialog.FieldDialog(title="Select account")
    d.add_field("Account", account)
    d.add_field("Server", host)
    d.add_field("Username", user)
    d.add_field("Password", pasw)
    d.add_field("Use SSL", ussl)
    d.add_field("Port", port)
    r = d.run()
    d.destroy()
    if r == Gtk.ResponseType.CANCEL:
        return None

    return host.get_text(), user.get_text(), pasw.get_text(), \
        str(ussl.get_active()), str(int(port.get_value()))

class StationsList(MainWindowTab):
    __gsignals__ = {
        "event" : signals.EVENT,
        "notice" : signals.NOTICE,
        "get-station-list" : signals.GET_STATION_LIST,
        "ping-station" : signals.PING_STATION,
        "ping-station-echo" : signals.PING_STATION_ECHO,
        "incoming-chat-message" : signals.INCOMING_CHAT_MESSAGE,
        "submit-rpc-job" : signals.SUBMIT_RPC_JOB,
        "user-send-file" : signals.USER_SEND_FILE,
        }

    _signals = __gsignals__

    def _expire(self):
        now = time.time()
        ttl = self._config.getint("settings", "expire_stations")
        if ttl == 0:
            return

        store = self.__view.get_model()
        iter = store.get_iter_first()
        while iter:
            station, stamp = store.get(iter, 0, 1)
            if (now - stamp) > (ttl * 60):
                printlog("MainStation",": Expired station %s (%i minutes since heard)" % \
                    (station, (now - stamp) / 60))
                self.__calls.remove(station)
                self._update_station_count()
                if not store.remove(iter):
                    break
            else:
                iter = store.iter_next(iter)
        

    def _update(self):
        self._expire()
        self.__view.queue_draw()

        return True

    def _mh(self, _action, station, port):
        action = _action.get_name()

        model = self.__view.get_model()
        iter = model.get_iter_first()
        while iter:
            _station, = model.get(iter, 0)
            if _station == station:
                break
            iter = model.iter_next(iter)

        if action == "ping":
            printlog("MainStation",": executing ping")
            # FIXME: Use the port we saw the user on
            self.emit("ping-station", station, port)
        elif action == "conntest":
            ct = conntest.ConnTestAssistant(station, port)
            ct.connect("ping-echo-station",
                       lambda a, *v: self.emit("ping-station-echo", *v))
            ct.run()
        elif action == "remove":
            self.__calls.remove(station)
            self._update_station_count()
            model.remove(iter)
        elif action == "reset":
            model.set(iter, 1, time.time())
            
        #asking positions to remote stations
        elif action == "reqpos":
            printlog("MainStation",": executing position request to: %s" % station)
            job = rpc.RPCPositionReport(station, "Position Request")
           
            def log_result(job, state, result):
                rc = result.get("rc", "(Error)")
                msg = result.get("msg", "(Error)")
                if rc == "KO":
                    event = main_events.Event(None,
                                                "%s %s: %s" % (station,
                                               _(" says "),
                                                msg))
                    self.emit("event", event)
                else:
                      # rc == "OK": 
                    event = main_events.Event(None, result)             
                    printlog("MainStation",": result returned: %s" % str(result))
                    printlog("MainStation",": event returned: %s" % event)
            job.set_station(station)
            job.connect("state-change", log_result)

            # FIXME: Send on the port where we saw this user
            self.emit("submit-rpc-job", job, port)
            
        elif action == "clearall":
            model.clear()
            self.__calls = []
            self._update_station_count()
        elif action == "pingall":
            printlog("MainStation",": executing ping all")
            stationlist = self.emit("get-station-list")
            for port in stationlist.keys():
                printlog("MainStation",": Doing CQCQCQ ping on port %s" % port)
                self.emit("ping-station", "CQCQCQ", port)
        elif action == "reqposall":
            printlog("MainStation",": requesting position to all known stations")
            job = rpc.RPCPositionReport("CQCQCQ", "Position Request")
            job.set_station(".")
            stationlist = self.emit("get-station-list")
            for port in stationlist.keys():
                self.emit("submit-rpc-job", job, port)
        elif action == "sendfile":
            fn = self._config.platform.gui_open_file()
            if not fn:
                return

            fnl = fn.lower()
            if fnl.endswith(".jpg") or fnl.endswith(".jpeg") or \
                    fnl.endswith(".png") or fnl.endswith(".gif"):
                fn = image.send_image(fn)
                if not fn:
                    return

            name = os.path.basename(fn)
            self.emit("user-send-file", station, port, fn, name)
        elif action == "version":
            def log_result(job, state, result):
                if state == "complete":
                    msg = "Station %s running D-RATS %s on %s" % (\
                        job.get_dest(),
                        result.get("version", "Unknown"),
                        result.get("os", "Unknown"))
                    printlog("MainStation",": Station %s reports version info: %s" % (job.get_dest(), result))

                else:
                    msg = "No version response from %s" % job.get_dest()
                event = main_events.Event(None, msg)
                self.emit("event", event)

            job = rpc.RPCGetVersion(station, "Version Request")
            job.connect("state-change", log_result)
            self.emit("submit-rpc-job", job, port)
        elif action == "mcheck":
            def log_result(job, state, result):
                msg = "Mail check via %s: %s" % (job.get_dest(),
                                                 result.get("msg",
                                                            "No response"))
                event = main_events.Event(None, msg)
                self.emit("event", event)

            vals = prompt_for_account(self._config)
            if vals is None:
                return

            job = rpc.RPCCheckMail(station, "Mail Check")
            job.set_account(vals[0], vals[1], vals[2], vals[4], vals[3])
            job.connect("state-change", log_result)
            self.emit("submit-rpc-job", job, port)
        elif action == "qrz":
            import webbrowser
            callsign = station.split("-")
            printlog("MainStation",": looking on QRZ.com for %s " % callsign[0])
            webbrowser.open('https://www.qrz.com/lookup?callsign=%s' % callsign[0], new=2)


    def _make_station_menu(self, station, port):
        xml = """
<ui>
  <popup name="menu">
    <menuitem action="ping"/>
    <menuitem action="conntest"/>
    <menuitem action="reqpos"/>
    <menuitem action="sendfile"/>
    <menuitem action="version"/>
    <menuitem action="mcheck"/>
    <menuitem action="qrz"/>
    <separator/>
    <menuitem action="remove"/>
    <menuitem action="reset"/>
    <separator/>
    <menuitem action="clearall"/>
    <menuitem action="pingall"/>
    <menuitem action="reqposall"/>
  </popup>
</ui>
"""
        ag = Gtk.ActionGroup.new("menu")
        actions = [("ping", _("Ping"), None),
                   ("conntest", _("Test Connectivity"), None),
                   ("reqpos", _("Request Position"), None),
                   ("sendfile", _("Send file"), None),
                   ("remove", _("Remove"), Gtk.STOCK_DELETE),
                   ("reset", _("Reset"), Gtk.STOCK_JUMP_TO),
                   ("version", _("Get version"), Gtk.STOCK_ABOUT),
                   ("mcheck", _("Request mail check"), None),
                   ("qrz", _("Check on Qrz.com"), None)]

        for action, label, stock in actions:
            a = Gtk.Action.new(action, label, None, stock)
            a.connect("activate", self._mh, station, port)
            a.set_sensitive(station is not None)
            ag.add_action(a)

        actions = [("clearall", _("Clear All"), Gtk.STOCK_CLEAR),
                   ("pingall", _("Ping All Stations"), None),
                   ("reqposall", _("Request all positions"), None)]
        for action, label, stock in actions:
            a = Gtk.Action.new(action, label, None, stock)
            a.connect("activate", self._mh, station, port)
            ag.add_action(a)

        uim = Gtk.UIManager()
        uim.insert_action_group(ag, 0)
        uim.add_ui_from_string(xml)

        return uim.get_object("/menu")

    def _mouse_cb(self, view, event):
        if event.button != 3:
            return

        if event.window == view.get_bin_window():
            x, y = event.get_coords()
            pathinfo = view.get_path_at_pos(int(x), int(y))
            if pathinfo is None:
                station = None
                port = None
            else:
                view.set_cursor_on_cell(pathinfo[0], None, None, False)
                (model, iter) = view.get_selection().get_selected()
                station, port = model.get(iter, 0, 5)

        menu = self._make_station_menu(station, port)
        menu.popup(None, None, None, event.button, event.time)

    def __init__(self, wtree, config):
        MainWindowTab.__init__(self, wtree, config, "main")

        frame, self.__view, = self._getw("stations_frame", "stations_view")

        store = Gtk.ListStore(GObject.TYPE_STRING,  # Station
                              GObject.TYPE_INT,     # Timestamp
                              GObject.TYPE_STRING,  # Message
                              GObject.TYPE_INT,     # Status
                              GObject.TYPE_STRING,  # Status message
                              GObject.TYPE_STRING)  # Port
        store.set_sort_column_id(1, Gtk.SortType.DESCENDING)
        self.__view.set_model(store)

        try:
            self.__view.set_tooltip_column(2)
        except AttributeError:
            printlog("MainStation",": This version of GTK is old; disabling station tooltips")

        self.__view.connect("button_press_event", self._mouse_cb)

        def render_call(col, rend, model, iter):
            call, ts, status = model.get(iter, 0, 1, 3)
            sec = time.time() - ts

            hour = 3600
            day = (hour*24)

            if sec < 60:
                msg = call
            elif sec < hour:
                msg = "%s (%im)" % (call, (sec / 60))
            elif sec < day:    
                msg = "%s (%ih %im)" % (call, sec / 3600, (sec % 3600) / 60)
            else:
                msg = "%s (%id %ih)" % (call, sec / day, (sec % day) / 3600)

            if status == station_status.STATUS_ONLINE:
                color = "blue"
            elif status == station_status.STATUS_UNATTENDED:
                color = "#CC9900"
            elif status == station_status.STATUS_OFFLINE:
                color = "grey"
            else:
                color = "black"

            rend.set_property("markup", "<span color='%s'>%s</span>" % (color,
                                                                        msg))

        r = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn(_("Stations"), r, text=0)
        col.set_cell_data_func(r, render_call)
        self.__view.append_column(col)

        self.__calls = []
        self._update_station_count()

        status, msg = self._getw("stations_status", "stations_smsg")

        try:
            status.set_tooltip_text(_("This is the state other stations will " +
                                      "see when requesting your status"))
            msg.set_tooltip_text(_("This is the message other stations will " +
                                   "see when requesting your status"))
        except AttributeError:
            pass

        def set_status(cb):
            # TODO this changed with Gtk 3
            # Commenting it out for now
            print("TODO: main_stations.StationsList,set_status is broken")
            print(type(cb))
            #self.__status = cb.get_active_text()
            #self._config.set("state", "status_state", self.__status)

        def set_smsg(e):
            self.__smsg = e.get_text()
            self._config.set("state", "status_msg", self.__smsg)

        # TODO This changed with GTK3.  I think I need to attach a liststore
        # object to the combo boxes.   I think that glade generated the
        # wrong window for this.
        #for s in sorted(station_status.get_status_msgs().values()):
        #    if s not in [_("Unknown"), _("Offline")]:
        #        status.append_text(s)

        status.connect("changed", set_status)
        msg.connect("changed", set_smsg)

        prev_status = self._config.get("state", "status_state")
        # TODO This chainged with GTK3.
        # Commenting it out for now.
        #if not utils.combo_select(status, prev_status):
        #    utils.combo_select(status,
        #                       station_status.get_status_msgs().values()[0])
        msg.set_text(self._config.get("state", "status_msg"))
        set_status(status)
        set_smsg(msg)

        GObject.timeout_add(30000, self._update)

    def _update_station_count(self):
            hdr, = self._getw("stations_header")
            if hdr:
                hdr.set_markup("<b>Stations (%i)</b>" % len(self.__calls))
            #TODO: Do we need an else clause here if all stations are removed?

    def saw_station(self, station, port, status=0, smsg=""):
        status_changed = False

        if station == "CQCQCQ":
            return

        store = self.__view.get_model()

        ts = time.time()
        msg = "%s <b>%s</b> %s <i>%s</i>\r\n%s: <b>%s</b>" % \
            (_("Station"),
             station,
             _("last seen at"),
             time.strftime("%X %x",
                           time.localtime(ts)),
             _("Port"),
             port)

        status_val = station_status.get_status_msgs().get(status, "Unknown")
        if station not in self.__calls:
            if smsg:
                msg += "\r\nStatus: <b>%s</b> (<i>%s</i>)" % (status_val, smsg)
            self.__calls.append(station)
            store.append((station, ts, msg, status, smsg, port))
            self.__view.queue_draw()
            status_changed = True
            self._update_station_count()
        else:
            iter = store.get_iter_first()
            while iter:
                call, _status, _smsg = store.get(iter, 0, 3, 4)
                if call == station:
                    status_changed = (status and (_status != status) or \
                                          (smsg and (_smsg != smsg)))

                    if _status > 0 and status == 0:
                        status = _status
                    if not smsg:
                        smsg = _smsg

                    msg += "\r\nStatus: <b>%s</b> (<i>%s</i>)" % (status_val,
                                                                  smsg)
                    store.set(iter, 1, ts, 2, msg, 3, status, 4, smsg, 5, port)
                    break
                iter = store.iter_next(iter)

        if status_changed and status > 0 and \
                self._config.getboolean("prefs", "chat_showstatus"):
            self.emit("incoming-chat-message",
                      station,
                      "CQCQCQ",
                      "%s %s: %s (%s %s)" % (_("Now"), status_val, smsg,
                                             _("Port"), port))
            
    def get_status(self):
        sval = station_status.get_status_vals()[self.__status]

        return sval, self.__smsg

    def get_stations(self):
        stations = []
        store = self.__view.get_model()
        iter = store.get_iter_first()
        while iter:
            call, ts, port = store.get(iter, 0, 1, 5)
            station = station_status.Station(call)
            station.set_heard(ts)
            station.set_port(port)
            stations.append(station)
            iter = store.iter_next(iter)

        return stations
