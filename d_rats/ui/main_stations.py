#!/usr/bin/python
'''Main Stations'''
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
import time
import os

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import GObject
from gi.repository import GLib

from d_rats.ui.main_common import MainWindowTab
from d_rats.ui.account_dialog import AccountDialog
from d_rats.ui import main_events
from d_rats.ui import conntest
from d_rats.sessions import rpc
from d_rats import station_status
from d_rats import signals
from d_rats import image
from d_rats import utils


if not '_' in locals():
    import gettext
    _ = gettext.gettext


class StationsList(MainWindowTab):
    '''
    Stations List.

    :param wtree: Window object
    :param config: Configuration data
    :type config: :class:`DratsConfig`
    :param window: Mainwindow window widget
    :type: window: :class:`Gtk.ApplicationWindow`
    '''

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

    def __init__(self, wtree, config, window):
        MainWindowTab.__init__(self, wtree, config,
                               window=window, prefix="main")

        self.logger = logging.getLogger("StationsList")
        self.__smsg = None

        self.__view = self._get_widget("stations_view")

        self._account_dialog = AccountDialog(self._config)

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
            self.logger.info("This version of GTK is too old;"
                             " disabling station tooltips")

        self.__view.connect("button_press_event", self._mouse_cb)

        renderer = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn(_("Stations"), renderer, text=0)
        col.set_cell_data_func(renderer, self._render_call)
        self.__view.append_column(col)

        self.__calls = []
        self._update_station_count()

        status = self._get_widget("stations_status")
        msg = self._get_widget("stations_smsg")

        try:
            tool_txt = _("This is the state other stations will "
                         "see when requesting your status")
            status.set_tooltip_text(tool_txt)
            msg.set_tooltip_text(tool_txt)
        except AttributeError:
            pass

        def set_status(combo_box):
            '''
            Set Status changed handler:

            :param combo_box: Main Station Status ComboBox widget
            :type combo_box: :class:`Gtk.ComboBoxText`
            '''
            self.__status = combo_box.get_active_text()
            self._config.set("state", "status_state", self.__status)

        def set_smsg(e_message):
            '''
            Set smsg changed handler

            :param e_message: Main Stations Status Message Widget
            :type e_message: :class:`Gtk.GtkEntry`
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

        GLib.timeout_add(30000, self._update)

    @staticmethod
    def _render_call(_col, rend, model, stn_iter, _data):
        '''
        Render Cell Tree Cell Data Function.

        :param _col: Tree Column, unused
        :type _col: :class:`Gtk.TreeViewColumn`
        :param rend: Cell Renderer
        :type rend: :class:`Gtk.CellRendererText`
        :param model: Tree model
        :type model: :class:`Gtk.TreeModel`
        :param stn_iter: Tree Iter for stations
        :type stn_iter: :class:`Gtk.TreeIter`
        :param _data:, Additional data, unused
        :type _data: any
        '''
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

        rend.set_property("markup",
                          "<span color='%s'>%s</span>" % (color, msg))

    def _expire(self):
        now = time.time()
        ttl = self._config.getint("settings", "expire_stations")
        if ttl == 0:
            return

        store = self.__view.get_model()
        if not store:
            self.logger.info("_expire: python3 fails here.")
            return
        stn_iter = store.get_iter_first()
        while stn_iter:
            station, stamp = store.get(stn_iter, 0, 1)
            if (now - stamp) > (ttl * 60):
                self.logger.info("_expire: Expired station %s "
                                 "(%i minutes since heard)",
                                 station, (now - stamp) / 60)
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

    def _menu_handler(self, action, station, port):
        '''
        Menu Activate Handler

        :param action: Menu action widget
        :type action: :class:`Gtk.Action`
        :param station: Remote Station id
        :type station: str
        :param port: Radio Port
        :type port: str
        '''
        action_name = action.get_name()

        if action_name == "ping":
            self._ping_handler(station, port)
        elif action_name == "conntest":
            self._conntest_handler(station, port)
        elif action_name == "remove":
            self._remove_handler(station)
        elif action_name == "reset":
            self._reset_handler(station)

        # asking positions to remote stations
        elif action_name == "reqpos":
            self._reqpos_handler(station, port)
        elif action_name == "clearall":
            self._clear_all_handler()
        elif action_name == "pingall":
            self._pingall_handler()
        elif action_name == "reqposall":
            self._reqposall_handler()
        elif action_name == "sendfile":
            self._sendfile_handler(station, port)
        elif action_name == "version":
            self._version_handler(station, port)
        elif action_name == "mcheck":
            self._mcheck_handler(station, port)
        elif action_name == "qrz":
            self._qrz_handler(station)

    @staticmethod
    def _get_station_iter(model, station):
        '''
        Get Station Iterator.

        :param model: Model for getting iterator
        :type model: :class:`Gtk.ListStore`
        :param station: Station to operate on
        :type station: str
        '''
        station_iter = model.get_iter_first()
        while station_iter:
            test_station = model.get_value(station_iter, 0)
            if test_station == station:
                break
            station_iter = model.iter_next(station_iter)
        return station_iter

    def _ping_handler(self, station, port):
        '''
        Ping Test Menu Item Handler.

        :param station: Station id to operate on
        :type station: str
        :param port: Radio Port
        :type port: str
        '''
        self.logger.info("_menu_handler: executing ping")
        self.emit("ping-station", station, port)

    def _conntest_handler(self, station, port):
        '''
        Connection Test Menu Item Handler.

        :param station: Station id to operate on
        :type station: str
        :param port: Radio Port
        :type port: str
        '''
        connect_test = conntest.ConnTestAssistant(station, port)
        connect_test.connect("ping-echo-station",
                             lambda a, *v: self.emit("ping-station-echo", *v))
        connect_test.run()

    def _remove_handler(self, station):
        '''
        Remove Menu Item Handler.

        :param station: Station id to operate on
        :type station: str
        '''
        self.__calls.remove(station)
        self._update_station_count()
        model = self.__view.get_model()
        station_iter = self._get_station_iter(model, station)
        model.remove(station_iter)

    def _reset_handler(self, station):
        '''
        Reset Menu Item Handler.

        :param station: Station id to operate on
        :type station: str
        '''
        model = self.__view.get_model()
        station_iter = self._get_station_iter(model, station)
        model.set(station_iter, 1, time.time())

    def _reqpos_handler(self, station, port):
        '''
        Request Position Menu Item Handler.

        :param station: Station id to operate on
        :type station: str
        :param port: Radio Port
        :type port: str
        '''
        self.logger.info("_menu_handler: executing position request to: %s",
                         station)
        job = rpc.RPCPositionReport(station, "Position Request")

        def log_result(_job, _state, result):
            '''
            Log Result State-Change event handler.

            :param job: RPC Position Report job
            :type job: :class:`rpc.RPCPositionReport`
            :param state: Job status
            :type state: str
            :param result: Result of rpc job
            :type result: dict
            '''
            result_code = result.get("rc", "(Error)")
            msg = result.get("msg", "(Error)")
            if result_code == "KO":
                event = main_events.Event(None,
                                          "%s %s: %s" %
                                          (station, _(" says "), msg))
                self.emit("event", event)
            else:
                # result_code == "OK":
                event = main_events.Event(None, result)
                self.logger.info("_menu_handler: result returned: %s",
                                 str(result))
                self.logger.info("_menu_handler: event returned: %s", event)
        job.set_station(station)
        job.connect("state-change", log_result)

        self.emit("submit-rpc-job", job, port)

    def _clear_all_handler(self):
        '''Clear All Menu Item Handler.'''
        model = self.__view.get_model()
        model.clear()
        self.__calls = []
        self._update_station_count()

    def _pingall_handler(self):
        '''Ping All Menu Item Handler.'''
        self.logger.info("_menu_handler: executing ping all")
        stationlist = self.emit("get-station-list")
        for station_radio_port in stationlist:
            self.logger.info("_menu_handler: Doing CQCQCQ ping on port %s",
                             station_radio_port)
            self.emit("ping-station", "CQCQCQ", station_radio_port)

    def _reqposall_handler(self):
        '''Request Position All Menu Item Handler.'''
        self.logger.info("_menu_handler: "
                         "requesting position to all known stations")
        job = rpc.RPCPositionReport("CQCQCQ", "Position Request")
        job.set_station(".")
        stationlist = self.emit("get-station-list")
        for station_radio_port in stationlist.keys():
            self.emit("submit-rpc-job", job, station_radio_port)

    def _sendfile_handler(self, station, port):
        '''
        Sendfile Menu Item Handler.

        :param station: Station id to operate on
        :type station: str
        :param port: Radio Port
        :type port: str
        '''
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

    def _version_handler(self, station, port):
        '''
        Version Menu Item Handler.

        :param station: Station id to operate on
        :type station: str
        :param port: Radio Port
        :type port: str
        '''
        def log_result(job, state, result):
            '''
            Log Result State-Change event handler.

            :param job: RPC Get Version job
            :type job: :class:`rpc.RPCGetVersion`
            :param state: Job status
            :type state: str
            :param result: Result of rpc job
            :type result: dict
            '''
            if state == "complete":
                msg = "Station %s running D-RATS %s on %s" % (\
                    job.get_dest(),
                    result.get("version", "Unknown"),
                    result.get("os", "Unknown"))
                self.logger.info("_menu_handler: "
                                 "Station %s reports version info: %s",
                                 job.get_dest(), result)

            else:
                msg = "No version response from %s" % job.get_dest()
            event = main_events.Event(None, msg)
            self.emit("event", event)

        job = rpc.RPCGetVersion(station, "Version Request")
        job.connect("state-change", log_result)
        self.emit("submit-rpc-job", job, port)

    def _mcheck_handler(self, station, port):
        '''
        Mail Check Menu Item Handler.

        :param station: Station id to operate on
        :type station: str
        :param port: Radio Port
        :type port: str
        '''
        # This mail check feature does not appear to have worked
        # in a long time, if ever, and does not appear to be completely
        # implemented.  I am not sure what this check is supposed to
        # to or how to implement it securely.
        def log_result(job, _state, result):
            '''
            Log Result State-Change event handler.

            :param job: RPC Check Mail job
            :type job: :class:`rpc.RPCCheckMail`
            :param state: Job status
            :type state: str
            :param result: Result of rpc job
            :type result: dict
            '''

            msg = "Mail check via %s: %s" % (job.get_dest(),
                                             result.get("msg", "No response"))
            event = main_events.Event(None, msg)
            self.emit("event", event)

        result = self._account_dialog.prompt_for_account()
        if not result:
            return

        job = rpc.RPCCheckMail(station, "Mail Check")
        job.set_account(self._account_dialog)
        job.connect("state-change", log_result)
        self.emit("submit-rpc-job", job, port)

    def _qrz_handler(self, station):
        '''
        QRZ Lookup Menu Item Handler.

        :param station: Station id to operate on
        :type station: str
        '''
        import webbrowser
        callsign = station.split("-")
        self.logger.info("_menu_handler: looking on QRZ.com for %s ",
                         callsign[0])
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
            new_action.connect("activate", self._menu_handler, station, port)
            new_action.set_sensitive(station is not None)
            action_group.add_action(new_action)

        actions = [("clearall", _("Clear All"), Gtk.STOCK_CLEAR),
                   ("pingall", _("Ping All Stations"), None),
                   ("reqposall", _("Request all positions"), None)]
        for action, label, stock in actions:
            new_action = Gtk.Action.new(action, label, None, stock)
            new_action.connect("activate", self._menu_handler, station, port)
            action_group.add_action(new_action)

        uim = Gtk.UIManager()
        uim.insert_action_group(action_group, 0)
        uim.add_ui_from_string(xml)

        return uim.get_widget("/menu")

    def _mouse_cb(self, view, event):
        '''
        Mouse button press event handler.

        :param view: Main Stations View
        :type view: :class:`Gtk.GtkTreeView`
        :param event: Event button triggered.
        :type: event: :class:`Gdk.EventButton`
        '''
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

    def _update_station_count(self):
        hdr = self._get_widget("stations_header")
        if hdr:
            hdr.set_markup("<b>Stations (%i)</b>" % len(self.__calls))
        # Do we need an else clause here if all stations are removed?

    def saw_station(self, station, port, status=0, smsg=""):
        '''
        Saw Station.

        :param station: Station seen
        :type station: str
        :param port: Radio port station seen on
        :type port: str
        :param status: Station status, default 0
        :type status: int
        :param smsg: Optional Station message
        :type smsg: str
        '''
        status_changed = False

        # print("saw_station: %s %s %i %s" % (station, port, status, smsg))
        # import traceback
        # traceback.print_stack()

        # This data can come from many sources, so make sure that any
        # bytes type is converted to str before storage.
        # Eventually need to trace down all callers of this method to
        # make sure that they only pass str types for string data.
        if not isinstance(station, str):
            station = station.decode('utf-8', 'replace')
        if not isinstance(port, str):
            port = port.decode('utf-8', 'replace')
        if not isinstance(smsg, str):
            smsg.decode('utf-8', 'replace')

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
        :rtype: tuple
        '''
        sval = station_status.get_status_vals()[self.__status]

        return sval, self.__smsg

    def get_stations(self):
        '''
        Get Stations.

        :returns: known stations
        :rtype: list[:class:`station_status.Station]`
        '''
        stations = []
        store = self.__view.get_model()
        if not store:
            self.logger.info("get_station: Failed to get station model store.")
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
