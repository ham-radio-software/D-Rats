#!/usr/bin/python
'''Main Events'''
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

import logging
import time
import os
from datetime import datetime

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import GLib
from gi.repository import GObject

from d_rats.ui.main_common import MainWindowTab
from d_rats import utils
from d_rats import signals

# This makes pylance happy with out overriding settings
# from the invoker of the class
if not '_' in locals():
    import gettext
    _ = gettext.gettext

EVENT_INFO = 0
EVENT_FILE_XFER = 1
EVENT_FORM_XFER = 2
EVENT_PING = 3
EVENT_POS_REPORT = 4
EVENT_SESSION = 5

# cEVENT_GROUP_NONE = -1

_EVENT_TYPES = {EVENT_INFO : None,
                EVENT_FILE_XFER : None,
                EVENT_FORM_XFER : None,
                EVENT_PING : None,
                EVENT_POS_REPORT : None,
                EVENT_SESSION : None,
                }

FILTER_HINT = _("Enter filter text")


class EventException(Exception):
    '''Generic Event Exception.'''


class InvalidEventType(EventException):
    '''Invalid Event Type Error.'''


class Event():
    '''
    Event.

    :param group_id: Group ID
    :param message: Event message
    :param evtype: event type, Default EVENT_INFO
    :type evtype: int
    :raises: :class:`InvalidEventType` if the event type validation fails
    '''

    def __init__(self, group_id, message, evtype=EVENT_INFO):
        self._group_id = group_id

        if evtype not in _EVENT_TYPES.keys():
            raise InvalidEventType("Invalid event type %i" % evtype)
        self._evtype = evtype
        self._message = message
        self._isfinal = False
        self._details = ""

    def set_as_final(self):
        '''
        Set Event as final.

        This event ends a series of events in the given group.
        '''
        self._isfinal = True

    def is_final(self):
        '''
        Is event final?

        :returns: True if the event is final
        :rtype: bool
        '''
        return self._isfinal

    def set_details(self, details):
        '''
        Set event details.

        :param details: Event details
        '''
        self._details = details


class FileEvent(Event):
    '''
    File Event.
    '''
    def __init__(self, group_id, message):
        Event.__init__(self, group_id, message, EVENT_FILE_XFER)


class FormEvent(Event):
    '''
    Form Event.
    '''

    def __init__(self, group_id, message):
        Event.__init__(self, group_id, message, EVENT_FORM_XFER)


class PingEvent(Event):
    '''
    Ping Event.
    '''

    def __init__(self, group_id, message):
        Event.__init__(self, group_id, message, EVENT_PING)


class PosReportEvent(Event):
    '''
    Position Report Event.
    '''

    def __init__(self, group_id, message):
        Event.__init__(self, group_id, message, EVENT_POS_REPORT)


class SessionEvent(Event):
    '''
    Session Event.

    :param session_id: Session ID
    :param port_id: Port Id
    :param message: message for event
    '''

    def __init__(self, session_id, port_id, message):
        group_id = "%s_%s" % (session_id, port_id)
        message = "[%s] %s" % (port_id, message)
        Event.__init__(self, group_id, message, EVENT_SESSION)
        self.__portid = port_id
        self.__sessionid = session_id
        self.__restart_info = None

    def get_portid(self):
        '''
        Get Port ID

        :returns: Port ID
        '''
        return self.__portid

    def get_sessionid(self):
        '''
        Get Session ID

        :returns:  Session ID
        '''
        return self.__sessionid

    def set_restart_info(self, restart_info):
        '''
        Set Restart Information.

        :param restart_info: Restart information
        '''
        self.__restart_info = restart_info

    def get_restart_info(self):
        '''
        Get Restart Information.

        :returns: Restart information
        '''
        return self.__restart_info


def filter_rows(model, row_iter, evtab):
    '''
    Filter roles.

    :param model: Model to get romes from
    :param row_iter: Iterated row to get
    :param evtab: Event table
    :returns: True if no filter icon, or if icon matches the filter icon
    :rtype: bool
    '''
    # Probably needs a better doc-string
    # pylint: disable=protected-access
    search = evtab._wtree.get_object("event_searchtext").get_text()

    icon, message = model.get(row_iter, 1, 3)

    if search != FILTER_HINT:
        if search and message and search.upper() not in message.upper():
            return False

    # pylint: disable=protected-access
    if evtab._filter_icon is None:
        return True
    # pylint: disable=protected-access
    return icon == evtab._filter_icon


class EventTab(MainWindowTab):
    '''
    Event Tab.

    :param wtree: Widget tree
    :param config:
    :type config: :class:`DratsConfig`
    '''

    __gsignals__ = {
        "event" : signals.EVENT,
        "notice" : signals.NOTICE,
        "user-stop-session" : signals.USER_STOP_SESSION,
        "user-cancel-session" : signals.USER_CANCEL_SESSION,
        "user-send-file" : signals.USER_SEND_FILE,
        "status" : signals.STATUS,
        }

    _signals = __gsignals__

    def __init__(self, wtree, config):
        MainWindowTab.__init__(self, wtree, config, "event", _("Event Log"))

        # Each class should have their own logger.
        self.logger = logging.getLogger("EventTab")

        self.__ctr = 0

        # pylint: disable=unbalanced-tuple-unpacking
        eventlist, = self._getw("list")

        eventlist.connect("button_press_event", self._mouse_cb)

        self.store = Gtk.ListStore(GObject.TYPE_STRING,  # 0: id
                                   GObject.TYPE_OBJECT,  # 1: icon
                                   GObject.TYPE_INT,     # 2: timestamp
                                   GObject.TYPE_STRING,  # 3: message
                                   GObject.TYPE_STRING,  # 4: details
                                   GObject.TYPE_INT,     # 5: order
                                   GObject.TYPE_PYOBJECT,# 6: event
                                   )
        self._filter_icon = None
        event_filter = self.store.filter_new()
        event_filter.set_visible_func(filter_rows, self)
        eventlist.set_model(event_filter)

        col = Gtk.TreeViewColumn("", Gtk.CellRendererPixbuf(), pixbuf=1)
        eventlist.append_column(col)

        def render_time(_col, rend, model, model_iter, _data):
            val, = model.get(model_iter, 2)
            stamp = datetime.fromtimestamp(val)
            rend.set_property("text", stamp.strftime("%Y-%m-%d %H:%M:%S"))

        renderer = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn(_("Time"), renderer, text=2)
        col.set_cell_data_func(renderer, render_time)
        col.set_sort_column_id(5)
        col.connect("clicked", self.__change_sort)
        eventlist.append_column(col)

        try:
            srt = int(self._config.get("state", "events_sort"))
        except ValueError:
            srt = Gtk.SortType.DESCENDING
        self.store.set_sort_column_id(5, srt)
        col.set_sort_indicator(True)
        col.set_sort_order(srt)

        renderer = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn(_("Description"), renderer, text=3)
        eventlist.append_column(col)

        # pylint: disable=unbalanced-tuple-unpacking
        typesel, = self._getw("typesel")
        typesel.set_active(0)
        typesel.connect("changed", self._type_selected, event_filter)

        # pylint: disable=unbalanced-tuple-unpacking
        filtertext, = self._getw("searchtext")
        filtertext.connect("changed", self._search_text, event_filter)
        utils.set_entry_hint(filtertext, FILTER_HINT)

        self._load_pixbufs()

        event = Event(None, _("D-RATS Started"))
        self.event(event)

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

    def _make_session_menu(self, _sid, event):
        xml = """
<ui>
  <popup name="menu">
    <menuitem action="stop"/>
    <menuitem action="cancel"/>
    <menuitem action="restart"/>
  </popup>
</ui>
"""
        gtk_action_group = Gtk.ActionGroup.new("menu")

        actions = [("stop", _("Stop"), not event.is_final()),
                   ("cancel", _("Cancel"), not event.is_final()),
                   ("restart", _("Restart"), event.get_restart_info())]
        for action, label, sensitive in actions:
            gtk_action = Gtk.Action.new(action, label, None, None)
            gtk_action.connect("activate", self._mh_xfer, event)
            gtk_action.set_sensitive(bool(sensitive))
            gtk_action_group.add_action(gtk_action)

        uim = Gtk.UIManager()
        uim.insert_action_group(gtk_action_group, 0)
        uim.add_ui_from_string(xml)

        # pylint: disable=no-member
        return uim.get_object("/menu")

    def _mouse_cb(self, view, uievent):
        if uievent.button != 3:
            return

        if uievent.window == view.get_bin_window():
            coord_x, coord_y = uievent.get_coords()
            pathinfo = view.get_path_at_pos(int(coord_x), int(coord_y))
            if pathinfo is None:
                return
            view.set_cursor_on_cell(pathinfo[0], None, None, False)

        (model, event_iter) = view.get_selection().get_selected()
        event_type, event_id, event = model.get(event_iter, 1, 0, 6)

        menus = {
            _EVENT_TYPES[EVENT_SESSION] : self._make_session_menu,
            }

        menufn = menus.get(event_type, None)
        if menufn:
            menu = menufn(event_id, event)
            menu.popup(None, None, None, None, uievent.button, uievent.time)

    def _type_selected(self, typesel, filtermodel):
        event_filter = typesel.get_active_text()
        self.logger.info("_type_selected: Filter set on %s", event_filter)
        filter_type = None
        # This needs to be fixed.  It means that the internationalization
        # dictionaries are not being properly setup.
        if event_filter == _("All") or event_filter == _("Tutto"):
            filter_type = None
        elif event_filter == _("File Transfers") or \
             event_filter == _("Trasferimento File"):
            filter_type = EVENT_FILE_XFER
        elif event_filter == _("Form Transfers") or \
             event_filter == _("Trasferimento Messaggi"):
            filter_type = EVENT_FORM_XFER
        elif event_filter == _("Pings") or event_filter == _("Ping"):
            filter_type = EVENT_PING
        elif event_filter == _("Position Reports") or \
             event_filter == _("Rapporto di Posizione"):
            filter_type = EVENT_POS_REPORT

        if filter_type is None:
            self._filter_icon = None
        else:
            self._filter_icon = _EVENT_TYPES[filter_type]

        filtermodel.refilter()

    # pylint: disable=no-self-use
    def _search_text(self, _searchtext, filtermodel):
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

        if srt == Gtk.SortType.ASCENDING:
            srt = Gtk.SortType.DESCENDING
        else:
            srt = Gtk.SortType.ASCENDING

        self._config.set("state", "events_sort", int(srt))

        self.store.set_sort_column_id(5, srt)
        column.set_sort_order(srt)

    def _get_sort_asc(self):
        # self.logger.info("_get_sort_asc: sorting events in ascending order")
        srt = self._config.getint("state", "events_sort")
        return srt == Gtk.SortType.ASCENDING

    @utils.run_gtk_locked
    def _event(self, event):
        # pylint: disable=unbalanced-tuple-unpacking
        scroll_window, = self._getw("sw")
        adj = scroll_window.get_vadjustment()
        top_scrolled = (adj.get_value() == 0.0)
        bot_scrolled = (adj.get_value() ==
                        (adj.get_upper() - adj.get_page_size()))
        if (adj.get_page_size() == adj.get_upper()) and self._get_sort_asc():
            # This means we're top-sorted, but only because there aren't
            # enough items to have a scroll bar.  So, if we're sorted
            # ascending, default to bottom-sort if we cross that boundary
            top_scrolled = False
            bot_scrolled = True

        event_iter = None
        # pylint: disable=protected-access
        if event._group_id is not None:
            event_iter = self.store.get_iter_first()
            while event_iter:
                group, = self.store.get(event_iter, 0)
                # pylint: disable=protected-access
                if group == str(event._group_id):
                    break
                event_iter = self.store.iter_next(event_iter)

        if not event_iter:
            event_iter = self.store.append()

        # pylint: disable=protected-access
        if event._isfinal:
            gid = ""
        else:
            # pylint: disable=protected-access
            gid = event._group_id or ""

        self.store.set(event_iter,
                       0, gid,
                       # pylint: disable=protected-access
                       1, _EVENT_TYPES[event._evtype],
                       2, time.time(),
                       # pylint: disable=protected-access
                       3, event._message,
                       # pylint: disable=protected-access
                       4, event._details,
                       5, self.__ctr,
                       6, event)
        self.__ctr += 1

        self._notice()
        # pylint: disable=protected-access
        self.emit("status", event._message)

        @utils.run_gtk_locked
        def top_scroll(adj):
            '''
            Top Scroll Adjustment.

            :param adj: Adjustment
            '''
            adj.set_value(0.0)

        @utils.run_gtk_locked
        def bot_scroll(adj):
            '''
            Bottom Scroll Adjustment.

            :param adj: Adjustment
            '''
            adj.set_value(adj.get_upper() - adj.get_page_size())

        if top_scrolled:
            GLib.idle_add(top_scroll, adj)
        elif bot_scrolled:
            GLib.idle_add(bot_scroll, adj)

    def event(self, event):
        '''
        Add an event.

        :param event: Event to add
        '''
        GLib.idle_add(self._event, event)

    def finalize_last(self, group):
        '''
        Finalize last event.
        :param group: Event group
        :returns: True if the event is finalized, otherwise False.
        '''
        # Need to find out what finalizing last even means to make
        # this documentation more useful.
        event_iter = self.store.get_iter_first()
        while event_iter:
            _group, = self.store.get(event_iter, 0)
            if _group == group:
                self.store.set(event_iter, 0, "")
                return True
            event_iter = self.store.iter_next(event_iter)

        return False

    def last_event_time(self, group):
        '''
        Get last event time for a group.

        :param group: Event Group
        :returns: Returns time of last event or 0 if no last event found
        '''
        event_iter = self.store.get_iter_first()
        while event_iter:
            _group, stamp = self.store.get(event_iter, 0, 2)
            if _group == group:
                return stamp
            event_iter = self.store.iter_next(event_iter)

        return 0
