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

import time
import os
from datetime import datetime

import gobject
import gtk

from d_rats.ui.main_common import MainWindowElement, MainWindowTab
from d_rats import utils
from d_rats import signals

EVENT_INFO       = 0
EVENT_FILE_XFER  = 1
EVENT_FORM_XFER  = 2
EVENT_PING       = 3
EVENT_POS_REPORT = 4
EVENT_SESSION    = 5

cEVENT_GROUP_NONE = -1

_EVENT_TYPES = {EVENT_INFO : None,
                EVENT_FILE_XFER : None,
                EVENT_FORM_XFER : None,
                EVENT_PING : None,
                EVENT_POS_REPORT : None,
                EVENT_SESSION : None,
                }

FILTER_HINT = _("Enter filter text")

class Event(object):
    def __init__(self, group_id, message, evtype=EVENT_INFO):
        self._group_id = group_id

        if evtype not in _EVENT_TYPES.keys():
            raise Exception("Invalid event type %i" % evtype)
        self._evtype = evtype
        self._message = message
        self._isfinal = False
        self._details = ""

    def set_as_final(self):
        "This event ends a series of events in the given group"
        self._isfinal = True

    def is_final(self):
        return self._isfinal

    def set_details(self, details):
        self._details = details

class FileEvent(Event):
    def __init__(self, group_id, message):
        Event.__init__(self, group_id, message, EVENT_FILE_XFER)

class FormEvent(Event):
    def __init__(self, group_id, message):
        Event.__init__(self, group_id, message, EVENT_FORM_XFER)

class PingEvent(Event):
    def __init__(self, group_id, message):
        Event.__init__(self, group_id, message, EVENT_PING)

class PosReportEvent(Event):
    def __init__(self, group_id, message):
        Event.__init__(self, group_id, message, EVENT_POS_REPORT)

class SessionEvent(Event):
    def __init__(self, session_id, port_id, message):
        group_id = "%s_%s" % (session_id, port_id)
        message = "[%s] %s" % (port_id, message)
        Event.__init__(self, group_id, message, EVENT_SESSION)
        self.__portid = port_id
        self.__sessionid = session_id
        self.__restart_info = None

    def get_portid(self):
        return self.__portid

    def get_sessionid(self):
        return self.__sessionid

    def set_restart_info(self, restart_info):
        self.__restart_info = restart_info

    def get_restart_info(self):
        return self.__restart_info

def filter_rows(model, iter, evtab):
    search = evtab._wtree.get_widget("event_searchtext").get_text()

    icon, message = model.get(iter, 1, 3)

    if search != FILTER_HINT:
        if search and message and search.upper() not in message.upper():
            return False

    if evtab._filter_icon is None:
        return True
    else:
        return icon == evtab._filter_icon

class EventTab(MainWindowTab):
    __gsignals__ = {
        "event" : signals.EVENT,
        "notice" : signals.NOTICE,
        "user-stop-session" : signals.USER_STOP_SESSION,
        "user-cancel-session" : signals.USER_CANCEL_SESSION,
        "user-send-file" : signals.USER_SEND_FILE,
        "status" : signals.STATUS,
        }

    _signals = __gsignals__

    def _mh_xfer(self, _action, event):
        action = _action.get_name()

        sid = event.get_sessionid()
        portid = event.get_portid()

        if action == "stop":
            self.emit("user-stop-session", sid, portid)
        elif action == "cancel":
            self.emit("user-cancel-session", sid, portid)
        elif action == "restart":
            station, filename = event.get_restart_info()
            sname = os.path.basename(filename)
            self.emit("user-send-file", station, portid, filename, sname)
            event.set_restart_info(None)

    def _make_session_menu(self, sid, event):
        xml = """
<ui>
  <popup name="menu">
    <menuitem action="stop"/>
    <menuitem action="cancel"/>
    <menuitem action="restart"/>
  </popup>
</ui>
"""
        ag = gtk.ActionGroup("menu")

        actions = [("stop", _("Stop"), not event.is_final()),
                   ("cancel", _("Cancel"), not event.is_final()),
                   ("restart", _("Restart"), event.get_restart_info())]
        for action, label, sensitive in actions:
            a = gtk.Action(action, label, None, None)
            a.connect("activate", self._mh_xfer, event)
            a.set_sensitive(bool(sensitive))
            ag.add_action(a)

        uim = gtk.UIManager()
        uim.insert_action_group(ag, 0)
        uim.add_ui_from_string(xml)

        return uim.get_widget("/menu")

    def _mouse_cb(self, view, uievent):
        if uievent.button != 3:
            return

        if uievent.window == view.get_bin_window():
            x, y = uievent.get_coords()
            pathinfo = view.get_path_at_pos(int(x), int(y))
            if pathinfo is None:
                return
            else:
                view.set_cursor_on_cell(pathinfo[0])

        (model, iter) = view.get_selection().get_selected()
        type, id, event = model.get(iter, 1, 0, 6)

        menus = {
            _EVENT_TYPES[EVENT_SESSION] : self._make_session_menu,
            }
                
        menufn = menus.get(type, None)
        if menufn:
            menu = menufn(id, event)
            menu.popup(None, None, None, uievent.button, uievent.time)

    def _type_selected(self, typesel, filtermodel):
        filter = typesel.get_active_text()
        print "Filter on %s" % filter

        if filter == _("All"):
            t = None
        elif filter == _("File Transfers"):
            t = EVENT_FILE_XFER
        elif filter == _("Form Transfers"):
            t = EVENT_FORM_XFER
        elif filter == _("Pings"):
            t = EVENT_PING
        elif filter == _("Position Reports"):
            t = EVENT_POS_REPORT

        if t is None:
            self._filter_icon = None
        else:
            self._filter_icon = _EVENT_TYPES[t]

        filtermodel.refilter()

    def _search_text(self, searchtext, filtermodel):
        filtermodel.refilter()

    def _load_pixbufs(self):
        _EVENT_TYPES[EVENT_INFO] = self._config.ship_img("event_info.png")
        _EVENT_TYPES[EVENT_FILE_XFER] = self._config.ship_img("folder.png")
        _EVENT_TYPES[EVENT_FORM_XFER] = self._config.ship_img("message.png")
        _EVENT_TYPES[EVENT_PING] = self._config.ship_img("event_ping.png")
        _EVENT_TYPES[EVENT_SESSION] = self._config.ship_img("event_session.png")
        _EVENT_TYPES[EVENT_POS_REPORT] = \
            self._config.ship_img("event_posreport.png")

    def __change_sort(self, column):
        srt = column.get_sort_order()

        if srt == gtk.SORT_ASCENDING:
            srt = gtk.SORT_DESCENDING
        else:
            srt = gtk.SORT_ASCENDING

        self._config.set("state", "events_sort", int(srt))

        self.store.set_sort_column_id(5, srt)
        column.set_sort_order(srt)

    def _get_sort_asc(self):
        srt = self._config.getint("state", "events_sort")
        return srt == gtk.SORT_ASCENDING

    def __init__(self, wtree, config):
        MainWindowTab.__init__(self, wtree, config, "event")

        self.__ctr = 0

        eventlist, = self._getw("list")

        eventlist.connect("button_press_event", self._mouse_cb)

        self.store = gtk.ListStore(gobject.TYPE_STRING,  # 0: id
                                   gobject.TYPE_OBJECT,  # 1: icon
                                   gobject.TYPE_INT,     # 2: timestamp
                                   gobject.TYPE_STRING,  # 3: message
                                   gobject.TYPE_STRING,  # 4: details
                                   gobject.TYPE_INT,     # 5: order
                                   gobject.TYPE_PYOBJECT,# 6: event
                                   )
        self._filter_icon = None
        filter = self.store.filter_new()
        filter.set_visible_func(filter_rows, self)
        eventlist.set_model(filter)

        col = gtk.TreeViewColumn("", gtk.CellRendererPixbuf(), pixbuf=1)
        eventlist.append_column(col)

        def render_time(col, rend, model, iter):
            val, = model.get(iter, 2)
            stamp = datetime.fromtimestamp(val)
            rend.set_property("text", stamp.strftime("%Y-%m-%d %H:%M:%S"))

        r = gtk.CellRendererText()
        col = gtk.TreeViewColumn(_("Time"), r, text=2)
        col.set_cell_data_func(r, render_time)
        col.set_sort_column_id(5)
        col.connect("clicked", self.__change_sort)
        eventlist.append_column(col)

        try:
            srt = int(self._config.get("state", "events_sort"))
        except ValueError:
            srt = gtk.SORT_DESCENDING
        self.store.set_sort_column_id(5, srt)
        col.set_sort_indicator(True)
        col.set_sort_order(srt)

        r = gtk.CellRendererText()
        col = gtk.TreeViewColumn(_("Description"), r, text=3)
        eventlist.append_column(col)

        typesel, = self._getw("typesel")
        typesel.set_active(0)
        typesel.connect("changed", self._type_selected, filter)

        filtertext, = self._getw("searchtext")
        filtertext.connect("changed", self._search_text, filter)
        utils.set_entry_hint(filtertext, FILTER_HINT)

        self._load_pixbufs()

        event = Event(None, _("D-RATS Started"))
        self.event(event)

    @utils.run_gtk_locked
    def _event(self, event):
        sw, = self._getw("sw")
        adj = sw.get_vadjustment()
        top_scrolled = (adj.get_value() == 0.0)
        bot_scrolled = (adj.get_value() == (adj.upper - adj.page_size))
        if (adj.page_size == adj.upper) and self._get_sort_asc():
            # This means we're top-sorted, but only because there aren't
            # enough items to have a scroll bar.  So, if we're sorted
            # ascending, default to bottom-sort if we cross that boundary
            top_scrolled = False
            bot_scrolled = True

        iter = None
        if event._group_id != None:
            iter = self.store.get_iter_first()
            while iter:
                group, = self.store.get(iter, 0)
                if group == str(event._group_id):
                    break
                iter = self.store.iter_next(iter)

        if not iter:
            iter = self.store.append()

        if event._isfinal:
            gid = ""
        else:
            gid = event._group_id or ""

        self.store.set(iter,
                       0, gid,
                       1, _EVENT_TYPES[event._evtype],
                       2, time.time(),
                       3, event._message,
                       4, event._details,
                       5, self.__ctr,
                       6, event)
        self.__ctr += 1

        self._notice()
        self.emit("status", event._message)

        @utils.run_gtk_locked
        def top_scroll(adj):
            adj.set_value(0.0)
        @utils.run_gtk_locked
        def bot_scroll(adj):
            adj.set_value(adj.upper - adj.page_size)

        if top_scrolled:
            gobject.idle_add(top_scroll, adj)
        elif bot_scrolled:
            gobject.idle_add(bot_scroll, adj)

    def event(self, event):
        gobject.idle_add(self._event, event)

    def finalize_last(self, group):
        iter = self.store.get_iter_first()
        while iter:
            _group, = self.store.get(iter, 0)
            if _group == group:
                self.store.set(iter, 0, "")
                return True
            iter = self.store.iter_next(iter)

        return False

    def last_event_time(self, group):
        iter = self.store.get_iter_first()
        while iter:
            _group, stamp = self.store.get(iter, 0, 2)
            if _group == group:
                return stamp
            iter = self.store.iter_next(iter)

        return 0
