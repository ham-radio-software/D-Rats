#!/usr/bin/python
'''Main Stations'''
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

import gettext
import time
import os

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import GObject

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
# importing printlog() wrapper
from ..debug import printlog

_ = gettext.gettext


# pylint: disable=too-many-locals
def prompt_for_account(config):
    '''
    Prompt for account.

    :param config: Config object
    '''
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

    dialog = inputdialog.FieldDialog(title="Select account")
    dialog.add_field("Account", account)
    dialog.add_field("Server", host)
    dialog.add_field("Username", user)
    dialog.add_field("Password", pasw)
    dialog.add_field("Use SSL", ussl)
    dialog.add_field("Port", port)
    result = dialog.run()
    dialog.destroy()
    if result == Gtk.ResponseType.CANCEL:
        return None

    return host.get_text(), user.get_text(), pasw.get_text(), \
        str(ussl.get_active()), str(int(port.get_value()))


class StationsList(MainWindowTab):
    '''Stations List'''

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
        stn_iter = store.get_iter_first()
        while stn_iter:
            station, stamp = store.get(stn_iter, 0, 1)
            if (now - stamp) > (ttl * 60):
                printlog("MainStation",
                         ": Expired station %s (%i minutes since heard)" %
                         (station, (now - stamp) / 60))
                self.__calls.remove(station)
                self._update_station_count()
                if not store.remove(stn_iter):
                    break
            else:
                stn_iter = store.iter_next(stn_iter)

    def _update(self):
        self._expire()
        self.__view.queue_draw()

        return True

    # pylint: disable=too-many-locals, too-many-branches, too-many-statements
    def _mh(self, _action, station, port):
        action = _action.get_name()

        model = self.__view.get_model()
        stn_iter = model.get_iter_first()
        while stn_iter:
            _station, = model.get(stn_iter, 0)
            if _station == station:
                break
            stn_iter = model.iter_next(stn_iter)

        if action == "ping":
            printlog("MainStation", ": executing ping")
            # pylint: disable=fixme
            # FIXME: Use the port we saw the user on
            self.emit("ping-station", station, port)
        elif action == "conntest":
            connect_test = conntest.ConnTestAssistant(station, port)
            connect_test.connect("ping-echo-station",
                                 lambda a, *v: self.emit("ping-station-echo",
                                                         *v))
            connect_test.run()
        elif action == "remove":
            self.__calls.remove(station)
            self._update_station_count()
            model.remove(stn_iter)
        elif action == "reset":
            model.set(stn_iter, 1, time.time())

        # asking positions to remote stations
        elif action == "reqpos":
            printlog("MainStation",
                     ": executing position request to: %s" % station)
            job = rpc.RPCPositionReport(station, "Position Request")

            def log_result(_job, _state, result):
                result_code = result.get("rc", "(Error)")
                msg = result.get("msg", "(Error)")
                if result_code == "KO":
                    event = main_events.Event(None,
                                              "%s %s: %s" %
                                              (station, _(" says "),
                                               msg))
                    self.emit("event", event)
                else:
                    # result_code == "OK":
                    event = main_events.Event(None, result)
                    printlog("MainStation",
                             ": result returned: %s" % str(result))
                    printlog("MainStation", ": event returned: %s" % event)
            job.set_station(station)
            job.connect("state-change", log_result)

            # pylint: disable=fixme
            # FIXME: Send on the port where we saw this user
            self.emit("submit-rpc-job", job, port)

        elif action == "clearall":
            model.clear()
            self.__calls = []
            self._update_station_count()
        elif action == "pingall":
            printlog("MainStation", ": executing ping all")
            stationlist = self.emit("get-station-list")
            for port in stationlist:
                printlog("MainStation",": Doing CQCQCQ ping on port %s" % port)
                self.emit("ping-station", "CQCQCQ", port)
        elif action == "reqposall":
            printlog("MainStation",
                     ": requesting position to all known stations")
            job = rpc.RPCPositionReport("CQCQCQ", "Position Request")
            job.set_station(".")
            stationlist = self.emit("get-station-list")
            for port in stationlist.keys():
                self.emit("submit-rpc-job", job, port)
        elif action == "sendfile":
            fname = self._config.platform.gui_open_file()
            if not fname:
                return

            fnl = fname.lower()
            if fnl.endswith(".jpg") or fnl.endswith(".jpeg") or \
                    fnl.endswith(".png") or fnl.endswith(".gif"):
                fname = image.send_image(fname)
                if not fname:
                    return

            name = os.path.basename(fname)
            self.emit("user-send-file", station, port, fname, name)
        elif action == "version":
            def log_result(job, state, result):
                if state == "complete":
                    msg = "Station %s running D-RATS %s on %s" % (\
                        job.get_dest(),
                        result.get("version", "Unknown"),
                        result.get("os", "Unknown"))
                    printlog("MainStation",
                             ": Station %s reports version info: %s" %
                             (job.get_dest(), result))

                else:
                    msg = "No version response from %s" % job.get_dest()
                event = main_events.Event(None, msg)
                self.emit("event", event)

            job = rpc.RPCGetVersion(station, "Version Request")
            job.connect("state-change", log_result)
            self.emit("submit-rpc-job", job, port)
        elif action == "mcheck":
            def log_result(job, _state, result):
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
            printlog("MainStation",
                     ": looking on QRZ.com for %s " % callsign[0])
            webbrowser.open('https://www.qrz.com/lookup?callsign=%s' %
                            callsign[0], new=2)

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
        action_group = Gtk.ActionGroup.new("menu")
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
            new_action = Gtk.Action.new(action, label, None, stock)
            new_action.connect("activate", self._mh, station, port)
            new_action.set_sensitive(station is not None)
            action_group.add_action(new_action)

        actions = [("clearall", _("Clear All"), Gtk.STOCK_CLEAR),
                   ("pingall", _("Ping All Stations"), None),
                   ("reqposall", _("Request all positions"), None)]
        for action, label, stock in actions:
            new_action = Gtk.Action.new(action, label, None, stock)
            new_action.connect("activate", self._mh, station, port)
            action_group.add_action(new_action)

        uim = Gtk.UIManager()
        uim.insert_action_group(action_group, 0)
        uim.add_ui_from_string(xml)

        return uim.get_widget("/menu")

    def _mouse_cb(self, view, event):
        if event.button != 3:
            return

        if event.window == view.get_bin_window():
            x_coord, y_coord = event.get_coords()
            pathinfo = view.get_path_at_pos(int(x_coord), int(y_coord))
            if pathinfo is None:
                station = None
                port = None
            else:
                view.set_cursor_on_cell(pathinfo[0], None, None, False)
                (model, stn_iter) = view.get_selection().get_selected()
                station, port = model.get(stn_iter, 0, 5)

        menu = self._make_station_menu(station, port)
        menu.popup(None, None, None, None, event.button, event.time)

    def __init__(self, wtree, config):
        MainWindowTab.__init__(self, wtree, config, "main")

        self.__smsg = None

        # pylint: disable=unbalanced-tuple-unpacking
        _frame, self.__view, = self._getw("stations_frame", "stations_view")

        self.__status = None
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
            printlog("MainStation",
                     ": This version of GTK is old; disabling station tooltips")

        self.__view.connect("button_press_event", self._mouse_cb)

        def render_call(_col, rend, model, stn_iter, _data):
            call, time_stamp, status = model.get(stn_iter, 0, 1, 3)
            sec = time.time() - time_stamp

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

        renderer = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn(_("Stations"), renderer, text=0)
        col.set_cell_data_func(renderer, render_call)
        self.__view.append_column(col)

        self.__calls = []
        self._update_station_count()

        # pylint: disable=unbalanced-tuple-unpacking
        status, msg = self._getw("stations_status", "stations_smsg")

        try:
            status.set_tooltip_text(_("This is the state other stations will " +
                                      "see when requesting your status"))
            msg.set_tooltip_text(_("This is the message other stations will " +
                                   "see when requesting your status"))
        except AttributeError:
            pass

        def set_status(call_back):
            '''
            Set Status.

            :param call_back: call_back to run when setting status
            '''
            self.__status = call_back.get_active_text()
            self._config.set("state", "status_state", self.__status)

        def set_smsg(e_message):
            '''
            Set smsg

            :param e_message: Message to set
            '''
            self.__smsg = e_message.get_text()
            self._config.set("state", "status_msg", self.__smsg)

        for station in sorted(station_status.get_status_msgs().values()):
            if station not in [_("Unknown"), _("Offline")]:
                status.append_text(station)

        status.connect("changed", set_status)
        msg.connect("changed", set_smsg)

        prev_status = self._config.get("state", "status_state")
        if not utils.combo_select(status, prev_status):
            utils.combo_select(status,
                               station_status.get_status_msgs().values()[0])
        msg.set_text(self._config.get("state", "status_msg"))
        set_status(status)
        set_smsg(msg)

        GObject.timeout_add(30000, self._update)

    def _update_station_count(self):
        # pylint: disable=unbalanced-tuple-unpacking
        hdr, = self._getw("stations_header")
        if hdr:
            hdr.set_markup("<b>Stations (%i)</b>" % len(self.__calls))
        # pylint: disable=fixme
        # TODO: Do we need an else clause here if all stations are removed?

    def saw_station(self, station, port, status=0, smsg=""):
        '''
        Saw Station.

        :param station: Station seen
        :param port: Port station seen on
        :param status: Optional station status
        :param smsg: Optional Station message
        '''
        status_changed = False

        if station == "CQCQCQ":
            return

        store = self.__view.get_model()

        time_stamp = time.time()
        msg = "%s <b>%s</b> %s <i>%s</i>\r\n%s: <b>%s</b>" % \
            (_("Station"),
             station,
             _("last seen at"),
             time.strftime("%X %x",
                           time.localtime(time_stamp)),
             _("Port"),
             port)

        status_val = station_status.get_status_msgs().get(status, "Unknown")
        if station not in self.__calls:
            if smsg:
                msg += "\r\nStatus: <b>%s</b> (<i>%s</i>)" % (status_val, smsg)
            self.__calls.append(station)
            store.append((station, time_stamp, msg, status, smsg, port))
            self.__view.queue_draw()
            status_changed = True
            self._update_station_count()
        else:
            stn_iter = store.get_iter_first()
            while stn_iter:
                call, _status, _smsg = store.get(stn_iter, 0, 3, 4)
                if call == station:
                    status_changed = (status and (_status != status) or \
                                          (smsg and (_smsg != smsg)))

                    if _status > 0 and status == 0:
                        status = _status
                    if not smsg:
                        smsg = _smsg

                    msg += "\r\nStatus: <b>%s</b> (<i>%s</i>)" % (status_val,
                                                                  smsg)
                    store.set(stn_iter, 1, time_stamp,
                              2, msg, 3, status, 4, smsg, 5, port)
                    break
                stn_iter = store.iter_next(stn_iter)

        if status_changed and status > 0 and \
                self._config.getboolean("prefs", "chat_showstatus"):
            self.emit("incoming-chat-message",
                      station,
                      "CQCQCQ",
                      "%s %s: %s (%s %s)" % (_("Now"), status_val, smsg,
                                             _("Port"), port))

    def get_status(self):
        '''
        Get Station Status.

        :returns: Station status
        '''
        sval = station_status.get_status_vals()[self.__status]

        return sval, self.__smsg

    def get_stations(self):
        '''
        Get Stations.

        :returns: List of stations
        '''
        stations = []
        store = self.__view.get_model()
        if not store:
            printlog("MainStation",
                     ": Failed to get station model store.")
            return stations

        stn_iter = store.get_iter_first()
        while stn_iter:
            call, time_stamp, port = store.get(stn_iter, 0, 1, 5)
            station = station_status.Station(call)
            station.set_heard(time_stamp)
            station.set_port(port)
            stations.append(station)
            stn_iter = store.iter_next(stn_iter)

        return stations
