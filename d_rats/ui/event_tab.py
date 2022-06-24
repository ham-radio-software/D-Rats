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
from d_rats.ui.main_events import Event

from d_rats import utils
from d_rats import signals

# This makes pylance happy with out overriding settings
# from the invoker of the class
if not '_' in locals():
    import gettext
    _ = gettext.gettext


FILTER_HINT = _("Enter filter text")


class EventTab(MainWindowTab):
    '''
    Event Tab.

    :param wtree: Widget tree
    :type wtree: :class:`Gtk.Widget`
    :param config: D-Rats configuration
    :type config: :class:`DratsConfig`
    :param window: Mainwindow window widget
    :type: window: :class:`Gtk.ApplicationWindow`
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

    def __init__(self, wtree, config, window):
        MainWindowTab.__init__(self, wtree, config,
                               window=window, prefix="event")

        self.logger = logging.getLogger("EventTab")

        self.__ctr = 0

        eventlist = self._get_widget("list")

        eventlist.connect("button_press_event", self._mouse_cb)

        self.store = Gtk.ListStore(GObject.TYPE_STRING,  # 0: id
                                   GObject.TYPE_OBJECT,  # 1: icon
                                   GObject.TYPE_INT,     # 2: timestamp
                                   GObject.TYPE_STRING,  # 3: message
                                   GObject.TYPE_STRING,  # 4: details
                                   GObject.TYPE_INT,     # 5: order
                                   GObject.TYPE_PYOBJECT,# 6: event
                                   )
        self.filter_icon = None
        event_filter = self.store.filter_new()
        self._filter_text_entry = self._wtree.get_object("event_searchtext")
        event_filter.set_visible_func(self.filter_rows, self)
        eventlist.set_model(event_filter)

        col = Gtk.TreeViewColumn("", Gtk.CellRendererPixbuf(), pixbuf=1)
        eventlist.append_column(col)

        def render_time(_col, rend, model, model_iter, _data):
            '''
            Render Time Cell Layout Data Function.

            :param _col: Cell layout, unused
            :type _col: :class:`Gtk.CellLayout
            :param rend: Cell Renderer
            :type rend: :class:`Gtk.CellRendererText`
            :param model: Tree Model
            :type model: :class:`Gtk.ListStore`
            :param tree_iter: Gtk TreeIter for row
            :type msg_iter: :class:`Gtk.TreeIter`
            :param _data: Optional Data
            :type _data: any
            '''
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

        typesel = self._get_widget("typesel")
        typesel.set_active(0)
        typesel.connect("changed", self._type_selected, event_filter)

        filtertext = self._get_widget("searchtext")
        filtertext.connect("changed", self._search_text, event_filter)
        utils.set_entry_hint(filtertext, FILTER_HINT)

        self._load_pixbufs()

        event = Event(None, _("D-RATS Started"))
        self.event(event)

    def filter_rows(self, model, row_iter, _data):
        '''
        Filter Rows Gtk Tree Model Filter Visible Callback Function.

        :param model: Model to get romes from
        :type: model: :class:`EventTab`
        :param row_iter: Iterated row to get data from.
        :type row_iter: :class:`Gtk.TreeIter`
        :param data: Optional data,Unused
        :type: data: any
        :returns: True if no filter icon, or if icon matches the filter icon
        :rtype: bool
        '''
        search = self._filter_text_entry.get_text()

        icon, message = model.get(row_iter, 1, 3)

        if search != FILTER_HINT:
            if search and message and search.upper() not in message.upper():
                return False

        if self.filter_icon is None:
            return True
        return icon == self.filter_icon

    def _mh_xfer(self, _action, event):
        '''
        Menu Handler Transfer Activate Handler.

        :param _action: Action widget
        :type _action: :class:`Gtk.Action`
        :param event: Event to act on.
        :type_event: :class:`Event`
        '''
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

        # UIManager does not work in GTK-3
        # uim = Gtk.UIManager()
        # uim.insert_action_group(gtk_action_group, 0)
        # uim.add_ui_from_string(xml)

        # return uim.get_object("/menu")

    def _mouse_cb(self, view, uievent):
        '''
        Mouse Button Click Event Handler.

        :param view: Widget signaled
        :type view: :class:`Gtk.TreeView`
        :param uievent: Signaled event
        :type uievent: :class:`Gtk.EventButton`
        '''
        if uievent.button != 3:
            # print("uievent button !=3", uievent.button)
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
            Event.EVENT_TYPES[Event.EVENT_SESSION] : self._make_session_menu,
            }

        menufn = menus.get(event_type, None)
        if menufn:
            menu = menufn(event_id, event)
            menu.popup(None, None, None, None, uievent.button, uievent.time)

    def _type_selected(self, typesel, filtermodel):
        '''
        Type Selected Change Handler.

        :param typesel: Widget signaled
        :type typesel: :class:`Gtk.Editable`
        :param filtermodel: Filter model
        :type filtermodel: :class:`Gtk.TreeModel`
        '''
        event_filter = typesel.get_active_text()
        self.logger.info("_type_selected: Filter set on %s", event_filter)
        filter_type = None
        if event_filter == _("All"):
            filter_type = None
        elif event_filter == _("File Transfers"):
            filter_type = Event.EVENT_FILE_XFER
        elif event_filter == _("Form Transfers"):
            filter_type = Event.EVENT_FORM_XFER
        elif event_filter == _("Pings") or event_filter == _("Ping"):
            filter_type = Event.EVENT_PING
        elif event_filter == _("Position Reports"):
            filter_type = Event.EVENT_POS_REPORT

        if filter_type is None:
            self.filter_icon = None
        else:
            self.filter_icon = Event.EVENT_TYPES[filter_type]

        filtermodel.refilter()

    @staticmethod
    def _search_text(_searchtext, filtermodel):
        '''
        Search Text Change Handler.

        :param _searchtext: Widget signaled
        :type _searchtext: :class:`Gtk.Editable`
        :param filtermodel: Filter model
        :type filtermodel: :class:`Gtk.TreeModel`
        '''
        filtermodel.refilter()

    def _load_pixbufs(self):
        Event.set_event_icon(Event.EVENT_INFO,
                             self._config.ship_img("event_info.png"))
        Event.set_event_icon(Event.EVENT_FILE_XFER,
                             self._config.ship_img("folder.png"))
        Event.set_event_icon(Event.EVENT_FORM_XFER,
                             self._config.ship_img("message.png"))
        Event.set_event_icon(Event.EVENT_PING,
                             self._config.ship_img("event_ping.png"))
        Event.set_event_icon(Event.EVENT_SESSION,
                             self._config.ship_img("event_session.png"))
        Event.set_event_icon(Event.EVENT_POS_REPORT,
                             self._config.ship_img("event_posreport.png"))

    def __change_sort(self, column):
        '''
        Change Sort Click Handler.

        :param column: Column to change
        :type column: :class:`Gtk.TreeViewColumn`
        '''
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

    def _event(self, event):
        '''
        _event delayed run routine.

        Used to update the event window.

        :param event: Event to log.
        :type event: :class:`Event`
        '''
        scroll_window = self._get_widget("sw")
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
        if event.group_id is not None:
            event_iter = self.store.get_iter_first()
            while event_iter:
                group, = self.store.get(event_iter, 0)
                if group == str(event.group_id):
                    break
                event_iter = self.store.iter_next(event_iter)

        if not event_iter:
            event_iter = self.store.append()

        if event.isfinal:
            gid = ""
        else:
            gid = event.group_id or ""

        self.store.set(event_iter,
                       0, gid,
                       1, Event.EVENT_TYPES[event.evtype],
                       2, time.time(),
                       3, event.message,
                       4, event.details,
                       5, self.__ctr,
                       6, event)
        self.__ctr += 1

        self._notice()
        self.emit("status", event.message)

        def top_scroll(adj):
            '''
            Top Scroll Adjustment.

            Delayed run method.

            :param adj: Adjustment
            :type adj: :class:`Gtk.Adjustment`
            '''
            adj.set_value(0.0)

        def bot_scroll(adj):
            '''
            Bottom Scroll Adjustment.

            Delayed run method.

            :param adj: Adjustment
            :type adj: :class:`Gtk.Adjustment`
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
        :type event: :class:`Event`
        '''
        GLib.idle_add(self._event, event)

    def finalize_last(self, group):
        '''
        Finalize last event.
        :param group: Event group
        :type group: str
        :returns: True if the event is finalized, otherwise False.
        :rtype: bool
        '''
        # Need to find out what finalizing last even means to make
        # this documentation more useful.
        event_iter = self.store.get_iter_first()
        while event_iter:
            event_group, = self.store.get(event_iter, 0)
            if event_group == group:
                self.store.set(event_iter, 0, "")
                return True
            event_iter = self.store.iter_next(event_iter)

        return False

    def last_event_time(self, group):
        '''
        Get last event time for a group.

        :param group: Event Group
        :type group: str
        :returns: Returns time of last event or 0 if no last event found
        :rtype: float
        '''
        event_iter = self.store.get_iter_first()
        while event_iter:
            event_group, stamp = self.store.get(event_iter, 0, 2)
            if event_group == group:
                return stamp
            event_iter = self.store.iter_next(event_iter)

        return 0
