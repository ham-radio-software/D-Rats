#!/usr/bin/python
'''Main Chat'''
#
# Copyright 2009 Dan Smith <dsmith@danplanet.com>
# Copyright 2021 John. E. Malmberg - Python3 Conversion
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

# this is the user interface for the chat tab

import logging
import os
import time
import re
from datetime import datetime

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import GObject
from gi.repository import Pango
from gi.repository import GLib

from d_rats.ui.main_common import MainWindowElement, MainWindowTab
from d_rats.ui.main_common import ask_for_confirmation, display_error, \
    set_toolbar_buttons
from d_rats import inputdialog, utils
from d_rats import qst
from d_rats import signals
from d_rats import spell


if not '_' in locals():
    import gettext
    _ = gettext.gettext


class LoggedTextBuffer(Gtk.TextBuffer):
    '''
    Logged Text Buffer.

    :param logfile: Logfile name
    :type logfile: str
    '''

    def __init__(self, logfile):
        Gtk.TextBuffer.__init__(self)
        self.__logfile = open(logfile, "a+", 1)

    def get_logfile(self):
        '''
        Get logfile.

        :returns: Logfile name
        :rtype: str
        '''
        return self.__logfile.name

    # pylint: disable=arguments-differ
    def insert_with_tags_by_name(self, log_iter, text, *attrs):
        '''
        Insert with tags by name.

        :param log_iter: log entry
        :param text: Log text
        :type text: str
        :param *attrs: Additional attributes
        '''
        Gtk.TextBuffer.insert_with_tags_by_name(self, log_iter, text, *attrs)
        self.__logfile.write(text)


class ChatQM(MainWindowElement):
    '''
    Chat QM.

    :param wtree: Widget Tree object
    :param config: Configuration object
    :type config: :class:`DratsConfig`
    '''

    __gsignals__ = {
        "user-sent-qm" : (GObject.SignalFlags.RUN_LAST,
                          GObject.TYPE_NONE,
                          (GObject.TYPE_STRING, # Content
                           GObject.TYPE_STRING, # Should be empty
                           ))
        }

    def __init__(self, wtree, config):
        MainWindowElement.__init__(self, wtree, config, "chat", _("Chat"))

        self.logger = logging.getLogger("ChatQM")
        # pylint: disable=unbalanced-tuple-unpacking
        qm_add, qm_rem, qm_list = self._getw("qm_add", "qm_remove",
                                             "qm_list")

        store = Gtk.ListStore(GObject.TYPE_STRING, GObject.TYPE_STRING)
        store.connect("row-deleted", self._reorder_rows)
        qm_list.set_model(store)
        qm_list.set_headers_visible(False)
        qm_list.set_reorderable(True)
        qm_list.connect("row-activated", self._send_qm)

        renderer = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn("", renderer, text=0)
        qm_list.append_column(col)

        for key in sorted(self._config.options("quick")):
            store.append((self._config.get("quick", key), key))

        qm_add.connect("clicked", self._add_qm, store)
        qm_rem.connect("clicked", self._rem_qm, qm_list)

    def _send_qm(self, view, path, _col):
        model = view.get_model()
        query_iter = model.get_iter(path)
        text = model.get(query_iter, 0)[0]
        self.emit("user-sent-qm", text, "")

    def _add_qm(self, _button, store):
        dialog = inputdialog.TextInputDialog(title=_("Add Quick Message"))
        dialog.label.set_text(_("Enter text for the new quick message:"))
        result = dialog.run()
        if result == Gtk.ResponseType.OK:
            key = time.strftime("%Y%m%d%H%M%S")
            store.append((dialog.text.get_text(), key))
            self._config.set("quick", key, dialog.text.get_text())
        dialog.destroy()

    def _rem_qm(self, _button, view):
        (store, query_iter) = view.get_selection().get_selected()
        if not query_iter:
            return

        if not ask_for_confirmation(_("Really delete?"),
                                    self._wtree.get_object("mainwindow")):
            return

        key, = store.get(query_iter, 1)
        store.remove(query_iter)
        self._config.remove_option("quick", key)

    def _reorder_rows(self, model, _path):
        for row_i in self._config.options("quick"):
            self._config.remove_option("quick", row_i)

        row_i = 0
        row_iter = model.get_iter_first()
        while row_iter:
            msg, = model.get(row_iter, 0)
            self.logger.info("_reorder_rows: Setting %i: %s", row_i, msg)
            self._config.set("quick", "msg_%i" % row_i, msg)
            row_iter = model.iter_next(row_iter)
            row_i += 1


class ChatQST(MainWindowElement):
    '''
    Chat QST.

    :param wtree: Widget Tree object
    :param config: configuration object
    :type config: :class:`DratsConfig`
    '''

    __gsignals__ = {
        "qst-fired" : (GObject.SignalFlags.RUN_LAST,
                       GObject.TYPE_NONE,
                       (GObject.TYPE_STRING,  # Content
                        GObject.TYPE_STRING,  # QST config key
                        GObject.TYPE_BOOLEAN, # Is raw
                        )),
        }

    def __init__(self, wtree, config):
        MainWindowElement.__init__(self, wtree, config, "chat", _("Chat"))

        self.logger = logging.getLogger("ChatQST")
        # pylint: disable=unbalanced-tuple-unpacking
        qst_add, qst_rem, qst_edit, qst_list = self._getw("qst_add",
                                                          "qst_remove",
                                                          "qst_edit",
                                                          "qst_list")

        self._store = Gtk.ListStore(GObject.TYPE_STRING,
                                    GObject.TYPE_STRING,
                                    GObject.TYPE_STRING,
                                    GObject.TYPE_FLOAT,
                                    GObject.TYPE_STRING,
                                    GObject.TYPE_BOOLEAN)
        qst_list.set_model(self._store)
        qst_list.connect("row-activated", self._send_qst)

        def render_remaining(_col, rend, model, qst_iter, _data):
            qst_id, qst_e = model.get(qst_iter, 0, 5)
            try:
                _qst_object, qst_c = self._qsts[qst_id]
            except KeyError:
                qst_e = None

            if not qst_e:
                qst_s = ""
            elif qst_c > 90:
                qst_s = "%i mins" % (qst_c / 60)
            else:
                qst_s = "%i sec" % qst_c

            rend.set_property("text", qst_s)

        typ = Gtk.TreeViewColumn("Type",
                                 Gtk.CellRendererText(), text=1)
        frq = Gtk.TreeViewColumn("Freq",
                                 Gtk.CellRendererText(), text=2)

        renderer = Gtk.CellRendererProgress()
        cnt = Gtk.TreeViewColumn("Remaining", renderer, value=3)
        cnt.set_cell_data_func(renderer, render_remaining)

        msg = Gtk.TreeViewColumn("Content",
                                 Gtk.CellRendererText(), text=4)

        renderer = Gtk.CellRendererToggle()
        renderer.connect("toggled", self._toggle_qst, self._store, 5, 0, 2)
        enb = Gtk.TreeViewColumn("On", renderer, active=5)

        qst_list.append_column(typ)
        qst_list.append_column(frq)
        qst_list.append_column(cnt)
        qst_list.append_column(enb)
        qst_list.append_column(msg)

        self._qsts = {}
        self.reconfigure()

        qst_add.connect("clicked", self._add_qst, qst_list)
        qst_rem.connect("clicked", self._rem_qst, qst_list)
        qst_edit.connect("clicked", self._edit_qst, qst_list)

        GLib.timeout_add(1000, self._tick)

    def _send_qst(self, view, path, _col):
        store = view.get_model()
        qst_id = store[path][0]

        qst_object, _c = self._qsts[qst_id]
        self._qsts[qst_id] = (qst_object, 0)

    # pylint: disable=too-many-arguments
    def _toggle_qst(self, _rend, path, store, enbcol, idcol, fcol):
        val = store[path][enbcol] = not store[path][enbcol]
        qst_id = store[path][idcol]
        freq = store[path][fcol]

        self._config.set(qst_id, "enabled", val)

        qst_object, _qst_c = self._qsts[qst_id]
        self._qsts[qst_id] = qst_object, self._remaining_for(freq) * 60

    def _add_qst(self, _button, _view):
        dialog = qst.QSTEditDialog(self._config,
                                   "qst_%s" % time.strftime("%Y%m%d%H%M%S"))
        if dialog.run() == Gtk.ResponseType.OK:
            dialog.save()
            self.reconfigure()
        dialog.destroy()

    def _rem_qst(self, _button, view):
        (model, qst_iter) = view.get_selection().get_selected()
        if not qst_iter:
            return

        if not ask_for_confirmation(_("Really delete?"),
                                    self._wtree.get_object("mainwindow")):
            return

        ident, = model.get(qst_iter, 0)
        self._config.remove_section(ident)
        self._store.remove(qst_iter)

    def _edit_qst(self, _button, view):
        (model, qst_iter) = view.get_selection().get_selected()
        if not qst_iter:
            return

        ident, = model.get(qst_iter, 0)

        dialog = qst.QSTEditDialog(self._config, ident)
        if dialog.run() == Gtk.ResponseType.OK:
            dialog.save()
            self.reconfigure()
        dialog.destroy()

    # pylint: disable=no-self-use
    def _remaining_for(self, freq):
        if freq.startswith(":"):
            n_min = int(freq[1:])
            c_min = datetime.now().minute
            cnt = n_min - c_min
            if n_min <= c_min:
                cnt += 60
        else:
            cnt = int(freq)

        return cnt

    def _qst_fired(self, qst_object, content, key):
        self.emit("qst-fired", content, key, qst_object.raw)

    def _tick(self):
        qst_iter = self._store.get_iter_first()
        while qst_iter:
            qst_i, _t, qst_f, qst_p, _c, qst_e = self._store.get(qst_iter,
                                                                 0, 1, 2, 3,
                                                                 4, 5)
            if qst_e:
                qst_object, cnt = self._qsts[qst_i]
                cnt -= 1
                if cnt <= 0:
                    qst_object.fire()
                    cnt = self._remaining_for(qst_f) * 60

                self._qsts[qst_i] = (qst_object, cnt)
            else:
                cnt = 0

            if qst_f.startswith(":"):
                period = 3600
            else:
                period = int(qst_f) * 60

            qst_p = (float(cnt) / period) * 100.0
            self._store.set(qst_iter, 3, qst_p)

            qst_iter = self._store.iter_next(qst_iter)

        return True

    def reconfigure(self):
        '''Reconfigure.'''
        self._store.clear()

        qsts = [qst_x for qst_x in self._config.sections()
                if qst_x.startswith("qst_")]
        for qst_i in qsts:
            qst_type = self._config.get(qst_i, "type")
            qst_config = self._config.get(qst_i, "content")
            qst_freq = self._config.get(qst_i, "freq")
            qst_enabled = self._config.getboolean(qst_i, "enabled")
            self._store.append((qst_i, qst_type, qst_freq, 0.0,
                                qst_config, qst_enabled))

            qst_class = qst.get_qst_class(qst_type)
            if not qst_class:
                self.logger.info("Reconfigure: Error : unable to get "
                                 " QST class `%s'", qst_type)
                continue
            qst_object = qst_class(self._config, qst_config, qst_i)
            qst_object.connect("qst-fired", self._qst_fired)

            self._qsts[qst_i] = (qst_object,
                                 self._remaining_for(qst_freq) * 60)


# pylint: disable=too-many-instance-attributes
class ChatTab(MainWindowTab):
    '''
    Chat Tab.

    :param wtree: Widget Tree object
    :param config: Configuration data
    :type config: :class:`DratsConfig`
    '''

    __gsignals__ = {
        "event" : signals.EVENT,
        "notice" : signals.NOTICE,
        "user-send-chat" : signals.USER_SEND_CHAT,
        }

    _signals = __gsignals__

    def __init__(self, wtree, config):
        MainWindowTab.__init__(self, wtree, config, "chat", _("Chat"))

        self.logger = logging.getLogger("ChatTab")
        # pylint: disable=unbalanced-tuple-unpacking
        entry, send, dest = self._getw("entry", "send", "destination")
        # pylint: disable=unbalanced-tuple-unpacking
        self.__filtertabs, = self._getw("filtertabs")
        self.__filters = {}

        self.__filtertabs.remove_page(0)
        self.__filtertabs.connect("switch-page", self._tab_selected)
        self.__filtertabs.connect("page-reordered", self._tab_reordered)

        self.__tb_buttons = {}

        self.__ports = []

        add_filter = self._wtree.get_object("main_menu_addfilter")
        add_filter.connect("activate", self._add_filter)

        delf = self._wtree.get_object("main_menu_delfilter")
        delf.connect("activate", self._del_filter)

        vlog = self._wtree.get_object("main_menu_viewlog")
        vlog.connect("activate", self._view_log)

        send.connect("clicked", self._send_button, dest, entry)
        send.set_can_default(True)
        #send.set_flags(Gtk.CAN_DEFAULT)
        send.connect("draw", lambda w, e: w.grab_default())

        if self._config.getboolean("prefs", "check_spelling"):
            spell.prepare_TextBuffer(entry.get_buffer())

        entry.set_wrap_mode(Gtk.WrapMode.WORD)
        entry.connect("key-press-event", self._enter_to_send, dest)
        entry.grab_focus()

        self._qm = ChatQM(wtree, config)
        self._qst = ChatQST(wtree, config)
        self._qm.connect("user-sent-qm", self._send_msg, False, dest)
        self._qst.connect("qst-fired", self._send_msg, dest)

        self._last_date = 0

        bcast = self._wtree.get_object("main_menu_bcast")
        bcast.connect("activate", self._bcast_file, dest)

        clear = self._wtree.get_object("main_menu_clear")
        clear.connect("activate", self._clear)

        try:
            dest.set_tooltip_text(_("Choose the port where chat " +
                                    "and QST messages will be sent"))
        except AttributeError:
            # Old PyGTK doesn't have this
            pass

        self._init_toolbar()

        self.reconfigure()

    def display_line(self, text, incoming, *attrs, **kwargs):
        '''
        Display a single line of text with datestamp.

        :param text: Text to display
        :type text: str
        :param incoming: Message is incoming
        :type incoming: bool
        :param *attrs: Additional attributes
        :param *kwargs: Key word arguments
        '''
        if (time.time() - self._last_date) > 600:
            stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        else:
            stamp = time.strftime("%H:%M:%S")

        if self._config.getboolean("prefs", "chat_timestamp"):
            line = "[%s] %s" % (stamp, text)
        else:
            line = text

        self._last_date = time.time()

        self._display_line(line, incoming, "default", *attrs, **kwargs)

    def _highlight_tab(self, num):
        child = self.__filtertabs.get_nth_page(num)
        label = self.__filtertabs.get_tab_label(child)
        mkup = "<span color='red'>%s</span>" % label.get_text()
        label.set_markup(mkup)

    def _unhighlight_tab(self, num):
        child = self.__filtertabs.get_nth_page(num)
        label = self.__filtertabs.get_tab_label(child)
        label.set_markup(label.get_text())

    def _display_matching_filter(self, text):
        for filter_item, display in self.__filters.copy().items():
            if filter_item and filter_item in text:
                return display

        return self.__filters[None]

    def _display_selected(self):
        cur = self.__filtertabs.get_current_page()
        return self.__filtertabs.get_nth_page(cur).get_child()

    # pylint: disable=no-self-use
    def _maybe_highlight_header(self, buffer, mark):
        start = buffer.get_iter_at_mark(mark)
        flags = Gtk.TextSearchFlags.TEXT_ONLY
        # The forward_search method returns None when a match is not
        # found, this causes a TypeError on python when it tries to
        # assign it to a tuple.
        try:
            _s, end_hl = start.forward_search("] ", flags, None)
        except TypeError:
            return
        try:
            _s, end = end_hl.forward_search(": ", flags, None)
        except TypeError:
            return

        # If we get here, we saw '] FOO: ' so highlight between
        # the start and the end
        buffer.apply_tag_by_name("bold", start, end)

    def _display_for_channel(self, channel):
        if channel in self.__filters:
            return self.__filters[channel]
        return None

    # pylint: disable=too-many-locals
    def _display_line(self, text, apply_filters, *attrs, **kwargs):
        # self.logger.info("_display_line: text: %s", text)
        match = re.match("^([^#].*)(#[^/]+)//(.*)$", text)
        # self.logger.info("_display_line: match: %s", match)
        # self.logger.info("_display: kwargs: %s", kwargs)
        # self.logger.info("_display: apply_filters: %s", apply_filters)
        # self.logger.info("_display: attrs: %s", attrs)
        # private channel
        if "priv_src" in kwargs.keys():
            channel = "@%s" % kwargs["priv_src"]
            display = self._display_for_channel(channel)
            if not display:
                self.logger.info("_display_line: Creating channel %s", channel)
                self._build_filter(channel)
                self._save_filters()
                display = self._display_for_channel(channel)
        elif match and apply_filters:
            channel = match.group(2)
            text = match.group(1) + match.group(3)
            display = self._display_for_channel(channel)
        elif apply_filters:
            display = self._display_matching_filter(text)
            # self.logger.info("_display_line: apply_filters display: %s",
            #                  display)
            noticere = self._config.get("prefs", "noticere")
            ignorere = self._config.get("prefs", "ignorere")
            if noticere and re.search(noticere, text):
                attrs += ("noticecolor",)
            elif ignorere and re.search(ignorere, text):
                attrs += ("ignorecolor",)
        else:
            display = self._display_selected()

        if not display:
            # We don't have anywhere to display this, so ignore it
            return

        buffer = display.get_buffer()
        scroll_window = display.get_parent()

        (_start, end) = buffer.get_bounds()
        mark = buffer.create_mark(None, end, True)
        buffer.insert_with_tags_by_name(end, text + os.linesep, *attrs)
        self._maybe_highlight_header(buffer, mark)
        buffer.delete_mark(mark)

        adj = scroll_window.get_vadjustment()
        bot_scrolled = (adj.get_value() ==
                        (adj.get_upper() - adj.get_page_size()))

        endmark = buffer.get_mark("end")
        if bot_scrolled:
            display.scroll_to_mark(endmark, 0.0, True, 0, 1)

        tabnum = self.__filtertabs.page_num(display.get_parent())
        if tabnum != self.__filtertabs.get_current_page() and \
                "ignorecolor" not in attrs:
            self._highlight_tab(tabnum)

        if apply_filters and "ignorecolor" not in attrs:
            self._notice()

    def _send_button(self, _button, dest, entry):
        buffer = entry.get_buffer()
        start, end = buffer.get_bounds()
        text = buffer.get_text(start, end, True)
        if not text:
            return

        dcall = "CQCQCQ"

        num = self.__filtertabs.get_current_page()
        child = self.__filtertabs.get_nth_page(num)
        channel = self.__filtertabs.get_tab_label(child).get_text()

        # DISCRIMINATE IF SENDING THE MSG TO A CHANNEL
        # (I.E. a selected user like a private chat)
        if channel.startswith("#"):
            text = channel + "//" + text
        elif channel.startswith("@"):
            dcall = channel[1:]

        port = dest.get_active_text()
        buffer.delete(*buffer.get_bounds())
        self.emit("user-send-chat", dcall, port, text, False)

    def _send_msg(self, _qm, msg, conf_key, raw, dest):
        current_text = _("Current")
        if conf_key:
            try:
                port = self._config.get(conf_key, "port")
            # pylint: disable=broad-except
            except Exception:
                self.logger.info("_send_msg of conf_key broad-except",
                                 exc_info=True)
                port = current_text
        else:
            port = current_text

        if port == current_text:
            # port = dest.get_active_text()
            port = dest.get_active()
            self.emit("user-send-chat", "CQCQCQ", port, msg, raw)
        elif port == _("All"):
            for i in self.__ports:
                self.emit("user-send-chat", "CQCQCQ", i, msg, raw)

    def _bcast_file(self, _but, dest):
        download_dir = self._config.get("prefs", "download_dir")
        file_name = self._config.platform.gui_open_file(download_dir)
        if not file_name:
            return

        try:
            file_handle = open(file_name, 'r')
        # pylint: disable=broad-except
        except Exception as err:
            self.logger.info("_bcast_file broad-except", exc_info=True)
            display_error(_("Unable to open file %s: %s") % (file_name, err))
            return

        data = file_handle.read()
        file_handle.close()

        if len(data) > (2 << 12):
            display_error(_("File is too large to send (>8KB)"))
            return

        # port = dest.get_active_text()
        port = dest.get_active()
        self.emit("user-send-chat", "CQCQCQ", port, "\r\n" + data, False)

    def _clear(self, _but):
        display = self._display_selected()
        display.get_buffer().set_text("")

    def _tab_selected(self, _tabs, _page, num):
        #
        self._unhighlight_tab(num)

        # activate the removefilter button in case we are not on
        # the main chat channel (num!=0)
        delf = self._wtree.get_object("main_menu_delfilter")
        delf.set_sensitive(num != 0)
        self.__tb_buttons[_("Remove Filter")].set_sensitive(num != 0)

    def _tab_reordered(self, _tabs, _page, _num):
        self._save_filters()

    def _save_filters(self):
        rev = {}
        for key, val in self.__filters.copy().items():
            rev[val] = key

        filters = []
        for i in range(0, self.__filtertabs.get_n_pages()):
            display = self.__filtertabs.get_nth_page(i).get_child()
            if rev.get(display, None):
                filters.append(rev[display])

        self._config.set("state", "filters", str(filters))

    def _add_filter(self, _but):
        dialog = inputdialog.TextInputDialog(title=_("Create filter"))
        dialog.label.set_text(_("Enter a filter search string:"))
        result = dialog.run()
        text = dialog.text.get_text()
        dialog.destroy()

        if not text:
            return

        if result == Gtk.ResponseType.OK:
            self._build_filter(text)
            self._save_filters()

    def _del_filter(self, _but):
        idx = self.__filtertabs.get_current_page()
        page = self.__filtertabs.get_nth_page(idx)
        text = self.__filtertabs.get_tab_label(page).get_text()
        self.logger.info("_del_filter: removing %s", text)
        if text != "Main":
            del self.__filters[text]
            self.__filtertabs.remove_page(idx)
        else:
            display_error("Mainchat  : Cannot remove Main tab")
        self._save_filters()

    def _view_log(self, _but):
        display = self._display_selected()
        file_name = display.get_buffer().get_logfile()
        self._config.platform.open_text_file(file_name)

    def _enter_to_send(self, view, event, dest):
        if event.keyval == 65293:
            # print("_enter_to_send dest=%s" % dest)
            self._send_button(None, dest, view)
            return True
        if event.keyval >= 65470 and event.keyval <= 65482:
            index = event.keyval - 65470
            msgs = sorted(self._config.options("quick"))
            # port = dest.get_active_text()
            port = dest.get_active()
            if index < len(msgs):
                msg = self._config.get("quick", msgs[index])
                self.emit("user-send-chat", "CQCQCQ", port, msg, False)
                return True
        return False

    def _join_channel(self, _button):
        while True:
            dialog = inputdialog.TextInputDialog(title=_("Join Channel"))
            dialog.label.set_text(_("Enter channel name:"))
            result = dialog.run()
            text = dialog.text.get_text()
            dialog.destroy()

            if not text:
                return
            if result != Gtk.ResponseType.OK:
                return

            if text.startswith("#"):
                text = text[1:]

            if re.match("^[A-z0-9_-]+$", text):
                self._build_filter("#" + text)
                self._save_filters()
                break

            display_error(_("Channel names must be a single-word " +
                            "alphanumeric string"))

    def _query_user(self, _button):
        while True:
            dialog = inputdialog.TextInputDialog(title=_("Query User"))
            dialog.label.set_text(_("Enter station:"))
            result = dialog.run()
            text = dialog.text.get_text()
            dialog.destroy()

            if not text:
                return
            if result != Gtk.ResponseType.OK:
                return

            if text.startswith("@"):
                text = text[1:]

            if re.match("^[A-z0-9_-]+$", text):
                self._build_filter("@" + text.upper())
                self._save_filters()
                break

            display_error(_("Station must be a plain " +
                            "alphanumeric string"))


    def _init_toolbar(self):
        jnchannel = self._config.ship_img("chat-joinchannel.png")
        addfilter = self._config.ship_img("chat-addfilter.png")
        delfilter = self._config.ship_img("chat-delfilter.png")
        queryuser = self._config.ship_img("chat-query.png")

        # pylint: disable=unbalanced-tuple-unpacking
        toolbar, = self._getw("toolbar")
        set_toolbar_buttons(self._config, toolbar)

        buttons = \
            [(addfilter, _("Add Filter"), self._add_filter),
             (delfilter, _("Remove Filter"), self._del_filter),
             (jnchannel, _("Join Channel"), self._join_channel),
             (queryuser, _("Open Private Chat"), self._query_user),
             ]

        count = 0
        for button_i, button_l, button_f in buttons:
            icon = Gtk.Image()
            icon.set_from_pixbuf(button_i)
            icon.show()
            item = Gtk.ToolButton.new(icon, button_l)
            item.connect("clicked", button_f)
            try:
                item.set_tooltip_text(button_l)
            except AttributeError:
                pass
            item.show()
            toolbar.insert(item, count)
            self.__tb_buttons[button_l] = item
            count += 1

    def _reconfigure_colors(self, buffer):
        tags = buffer.get_tag_table()

        if not tags.lookup("incomingcolor"):
            for color in ["red", "blue", "green", "grey"]:
                tag = Gtk.TextTag.new(color)
                tag.set_property("foreground", color)
                tags.add(tag)

            tag = Gtk.TextTag.new("bold")
            tag.set_property("weight", Pango.Weight.BOLD)
            tags.add(tag)

            tag = Gtk.TextTag.new("italic")
            tag.set_property("style", Pango.Style.ITALIC)
            tags.add(tag)

            tag = Gtk.TextTag.new("default")
            tag.set_property("indent", -40)
            tag.set_property("indent-set", True)
            tags.add(tag)

        regular = ["incomingcolor", "outgoingcolor",
                   "noticecolor", "ignorecolor"]
        reverse = ["brokencolor"]

        for i in regular + reverse:
            tag = tags.lookup(i)
            if not tag:
                tag = Gtk.TextTag.new(i)
                tags.add(tag)

            if i in regular:
                tag.set_property("foreground", self._config.get("prefs", i))
            elif i in reverse:
                tag.set_property("background", self._config.get("prefs", i))


    def _reconfigure_font(self, display):
        fontname = self._config.get("prefs", "font")
        font = Pango.FontDescription(fontname)
        display.modify_font(font)

    def _build_filter(self, text):
        if text is not None:
            ffn = self._config.platform.filter_filename(text)
        else:
            ffn = "Main"
        file_name = self._config.platform.log_file(ffn)
        buffer = LoggedTextBuffer(file_name)
        buffer.create_mark("end", buffer.get_end_iter(), False)

        display = Gtk.TextView.new_with_buffer(buffer)
        display.set_wrap_mode(Gtk.WrapMode.CHAR)
        display.set_editable(False)
        display.set_cursor_visible(False)

        scroll_window = Gtk.ScrolledWindow()
        scroll_window.set_policy(Gtk.PolicyType.AUTOMATIC,
                                 Gtk.PolicyType.AUTOMATIC)
        scroll_window.add(display)

        display.show()
        scroll_window.show()

        if text:
            lab = Gtk.Label.new(text)
        else:
            lab = Gtk.Label.new(_("Main"))

        lab.show()

        self.__filtertabs.append_page(scroll_window, lab)
        if text is not None:
            self.__filtertabs.set_tab_reorderable(scroll_window, True)
        self.__filters[text] = display

        self._reconfigure_colors(buffer)
        self._reconfigure_font(display)

    def _configure_filters(self):
        '''Configure Filters.'''
        for i in range(0, self.__filtertabs.get_n_pages()):
            self.__filtertabs.remove_page(i)

        self.__filters = {}

        # pylint: disable=eval-used
        filters = eval(self._config.get("state", "filters"))
        while None in filters:
            filters.remove(None)
        filters.insert(0, None) # Main catch-all

        for chat_filter in filters:
            self._build_filter(chat_filter)

    def reconfigure(self):
        '''Reconfigure.'''
        if not self.__filters:
            # First time only
            self._configure_filters()

        for display in self.__filters.values():
            self._reconfigure_colors(display.get_buffer())
            self._reconfigure_font(display)

        # pylint: disable=unbalanced-tuple-unpacking
        dest, = self._getw("destination")

        self.__ports = []
        for port in self._config.options("ports"):
            spec = self._config.get("ports", port)
            vals = spec.split(",")
            if vals[0] == "True":
                self.__ports.append(vals[-1])
        self.__ports.sort()

        model = dest.get_model()
        if model:
            model.clear()
        else:
            model = Gtk.ListStore(GObject.TYPE_STRING)
            dest.set_model(model)
        for port in self.__ports:
            model.append([port, ""])
        if self.__ports:
            utils.combo_select(dest, self.__ports[0])

    def get_selected_port(self):
        '''
        Get selected port.

        :returns: Selected port text
        :rtype: str
        '''
        # pylint: disable=unbalanced-tuple-unpacking
        dest, = self._getw("destination")
        # return dest.get_active_text()
        return dest.get_active()

    def selected(self):
        '''Process selected tab.'''
        MainWindowTab.selected(self)

        make_visible = ["main_menu_bcast", "main_menu_clear",
                        "main_menu_addfilter", "main_menu_delfilter",
                        "main_menu_viewlog"]

        for name in make_visible:
            item = self._wtree.get_object(name)
            item.set_property("visible", True)

        # pylint: disable=unbalanced-tuple-unpacking
        entry, = self._getw("entry")
        GObject.idle_add(entry.grab_focus)

    def deselected(self):
        '''Process deselected tabs.'''
        MainWindowTab.deselected(self)

        make_invisible = ["main_menu_bcast", "main_menu_clear",
                          "main_menu_addfilter", "main_menu_delfilter",
                          "main_menu_viewlog"]

        for name in make_invisible:
            item = self._wtree.get_object(name)
            item.set_property("visible", False)
