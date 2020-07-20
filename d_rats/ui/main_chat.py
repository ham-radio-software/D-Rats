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

#importing printlog() wrapper
from ..debug import printlog


# this is the user interface for the chat tab

import os
import time
import re
from datetime import datetime

import gobject
import gtk
import pango

from d_rats.ui.main_common import MainWindowElement, MainWindowTab
from d_rats.ui.main_common import ask_for_confirmation, display_error, \
    set_toolbar_buttons
from d_rats import inputdialog, utils
from d_rats import qst
from d_rats import signals
from d_rats import spell

class LoggedTextBuffer(gtk.TextBuffer):
    def __init__(self, logfile):
        gtk.TextBuffer.__init__(self)
        self.__logfile = file(logfile, "a", 0)

    def get_logfile(self):
        return self.__logfile.name

    def insert_with_tags_by_name(self, iter, text, *attrs):
        gtk.TextBuffer.insert_with_tags_by_name(self, iter, text, *attrs)
        self.__logfile.write(text)

class ChatQM(MainWindowElement):
    __gsignals__ = {
        "user-sent-qm" : (gobject.SIGNAL_RUN_LAST,
                          gobject.TYPE_NONE,
                          (gobject.TYPE_STRING, # Content
                           gobject.TYPE_STRING, # Should be empty
                           ))
        }

    def _send_qm(self, view, path, col):
        model = view.get_model()
        iter = model.get_iter(path)
        text = model.get(iter, 0)[0]
        self.emit("user-sent-qm", text, "")

    def _add_qm(self, button, store):
        d = inputdialog.TextInputDialog(title=_("Add Quick Message"))
        d.label.set_text(_("Enter text for the new quick message:"))
        r = d.run()
        if r == gtk.RESPONSE_OK:
            key = time.strftime("%Y%m%d%H%M%S")
            store.append((d.text.get_text(), key))
            self._config.set("quick", key, d.text.get_text())
        d.destroy()

    def _rem_qm(self, button, view):
        (store, iter) = view.get_selection().get_selected()
        if not iter:
            return

        if not ask_for_confirmation(_("Really delete?"),
                                    self._wtree.get_widget("mainwindow")):
            return

        key, = store.get(iter, 1)
        store.remove(iter)
        self._config.remove_option("quick", key)

    def _reorder_rows(self, model, path):
        for i in self._config.options("quick"):
            self._config.remove_option("quick", i)
        
        i = 0
        iter = model.get_iter_first()
        while iter:
            msg, = model.get(iter, 0)
            printlog("Mainchat","  : Setting %i: %s" % (i, msg))
            self._config.set("quick", "msg_%i" % i, msg)
            iter = model.iter_next(iter)
            i += 1

    def __init__(self, wtree, config):
        MainWindowElement.__init__(self, wtree, config, "chat")

        qm_add, qm_rem, qm_list = self._getw("qm_add", "qm_remove",
                                             "qm_list")

        store = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
        store.connect("row-deleted", self._reorder_rows)
        qm_list.set_model(store)
        qm_list.set_headers_visible(False)
        qm_list.set_reorderable(True)
        qm_list.connect("row-activated", self._send_qm)

        r = gtk.CellRendererText()
        col = gtk.TreeViewColumn("", r, text=0)
        qm_list.append_column(col)

        for key in sorted(self._config.options("quick")):
            store.append((self._config.get("quick", key), key))

        qm_add.connect("clicked", self._add_qm, store)
        qm_rem.connect("clicked", self._rem_qm, qm_list)

class ChatQST(MainWindowElement):
    __gsignals__ = {
        "qst-fired" : (gobject.SIGNAL_RUN_LAST,
                       gobject.TYPE_NONE,
                       (gobject.TYPE_STRING,  # Content
                        gobject.TYPE_STRING,  # QST config key
                        gobject.TYPE_BOOLEAN, # Is raw
                        )),
        }

    def _send_qst(self, view, path, col):
        store = view.get_model()
        id = store[path][0]

        q, c = self._qsts[id]
        self._qsts[id] = (q, 0)

    def _toggle_qst(self, rend, path, store, enbcol, idcol, fcol):
        val = store[path][enbcol] = not store[path][enbcol]
        id = store[path][idcol]
        freq = store[path][fcol]

        self._config.set(id, "enabled", val)

        q, c = self._qsts[id]
        self._qsts[id] = q, self._remaining_for(freq) * 60

    def _add_qst(self, button, view):
        d = qst.QSTEditDialog(self._config,
                              "qst_%s" % time.strftime("%Y%m%d%H%M%S"))
        if d.run() == gtk.RESPONSE_OK:
            d.save()
            self.reconfigure()
        d.destroy()

    def _rem_qst(self, button, view):
        (model, iter) = view.get_selection().get_selected()
        if not iter:
            return

        if not ask_for_confirmation(_("Really delete?"),
                                    self._wtree.get_widget("mainwindow")):
            return

        ident, = model.get(iter, 0)
        self._config.remove_section(ident)
        self._store.remove(iter)

    def _edit_qst(self, button, view):
        (model, iter) = view.get_selection().get_selected()
        if not iter:
            return

        ident, = model.get(iter, 0)

        d = qst.QSTEditDialog(self._config, ident)
        if d.run() == gtk.RESPONSE_OK:
            d.save()
            self.reconfigure()
        d.destroy()

    def __init__(self, wtree, config):
        MainWindowElement.__init__(self, wtree, config, "chat")

        qst_add, qst_rem, qst_edit, qst_list = self._getw("qst_add",
                                                          "qst_remove",
                                                          "qst_edit",
                                                          "qst_list")

        self._store = gtk.ListStore(gobject.TYPE_STRING,
                                    gobject.TYPE_STRING,
                                    gobject.TYPE_STRING,
                                    gobject.TYPE_FLOAT,
                                    gobject.TYPE_STRING,
                                    gobject.TYPE_BOOLEAN)
        qst_list.set_model(self._store)
        qst_list.connect("row-activated", self._send_qst)

        def render_remaining(col, rend, model, iter):
            id, e = model.get(iter, 0, 5)
            try:
                q, c = self._qsts[id]
            except KeyError:
                e = None

            if not e:
                s = ""
            elif c > 90:
                s = "%i mins" % (c / 60)
            else:
                s = "%i sec" % c

            rend.set_property("text", s)

        typ = gtk.TreeViewColumn("Type",
                                 gtk.CellRendererText(), text=1)
        frq = gtk.TreeViewColumn("Freq",
                                 gtk.CellRendererText(), text=2)

        r = gtk.CellRendererProgress()
        cnt = gtk.TreeViewColumn("Remaining", r, value=3)
        cnt.set_cell_data_func(r, render_remaining)

        msg = gtk.TreeViewColumn("Content",
                                 gtk.CellRendererText(), text=4)

        r = gtk.CellRendererToggle()
        r.connect("toggled", self._toggle_qst, self._store, 5, 0, 2)
        enb = gtk.TreeViewColumn("On", r, active=5)

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

        gobject.timeout_add(1000, self._tick)

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

    def _qst_fired(self, q, content, key):
        self.emit("qst-fired", content, key, q.raw)

    def _tick(self):
        iter = self._store.get_iter_first()
        while iter:
            i, t, f, p, c, e = self._store.get(iter, 0, 1, 2, 3, 4, 5)
            if e:
                q, cnt = self._qsts[i]
                cnt -= 1
                if cnt <= 0:
                    q.fire()
                    cnt = self._remaining_for(f) * 60

                self._qsts[i] = (q, cnt)
            else:
                cnt = 0

            if f.startswith(":"):
                period = 3600
            else:
                period = int(f) * 60

            p = (float(cnt) / period) * 100.0
            self._store.set(iter, 3, p)

            iter = self._store.iter_next(iter)

        return True

    def reconfigure(self):
        self._store.clear()

        qsts = [x for x in self._config.sections() if x.startswith("qst_")]
        for i in qsts:
            t = self._config.get(i, "type")
            c = self._config.get(i, "content")
            f = self._config.get(i, "freq")
            e = self._config.getboolean(i, "enabled")
            self._store.append((i, t, f, 0.0, c, e))
                              
            qc = qst.get_qst_class(t)
            if not qc:
                printlog("Mainchat","  : Error : unable to get QST class `%s'" % t)
                continue
            q = qc(self._config, c, i)
            q.connect("qst-fired", self._qst_fired)

            self._qsts[i] = (q, self._remaining_for(f) * 60)

class ChatTab(MainWindowTab):
    __gsignals__ = {
        "event" : signals.EVENT,
        "notice" : signals.NOTICE,
        "user-send-chat" : signals.USER_SEND_CHAT,
        }

    _signals = __gsignals__

    def display_line(self, text, incoming, *attrs, **kwargs):
        """Display a single line of text with datestamp"""

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
        for filter, display in self.__filters.items():
            if filter and filter in text:
                return display

        return self.__filters[None]

    def _display_selected(self):
        cur = self.__filtertabs.get_current_page()
        return self.__filtertabs.get_nth_page(cur).child

    def _maybe_highlight_header(self, buffer, mark):
        start = buffer.get_iter_at_mark(mark)
        try:
            s, e = start.forward_search("] ", 0)
        except:
            return
        try:
            s, end = e.forward_search(": ", 0)
        except:
            return

        # If we get here, we saw '] FOO: ' so highlight between
        # the start and the end
        buffer.apply_tag_by_name("bold", start, end)
        
    def _display_for_channel(self, channel):
        if self.__filters.has_key(channel):
            return self.__filters[channel]
        else:
            return None

    def _display_line(self, text, apply_filters, *attrs, **kwargs):
        #printlog("Mainchat","  : text: %s " % text)
        match = re.match("^([^#].*)(#[^/]+)//(.*)$", text)
        printlog("Mainchat","  : match: %s " % match)
        printlog("Mainchat","  : kwargs: %s " % kwargs)
        printlog("Mainchat","  : apply_filters: %s " % apply_filters)
    #    printlog("Mainchat","  : attrs: %s " % attrs)
        #private channel
        if "priv_src" in kwargs.keys():
            channel = "@%s" % kwargs["priv_src"]
            display = self._display_for_channel(channel)
            if not display:
                printlog("Mainchat","  : Creating channel %s" % channel)
                self._build_filter(channel)
                self._save_filters()
                display = self._display_for_channel(channel)
        elif match and apply_filters:
            channel = match.group(2)
            text = match.group(1) + match.group(3)
            display = self._display_for_channel(channel)
        elif apply_filters:
            display = self._display_matching_filter(text)
            printlog("Mainchat","  : display: %s " % display)
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
        sw = display.parent

        (start, end) = buffer.get_bounds()
        mark = buffer.create_mark(None, end, True)
        buffer.insert_with_tags_by_name(end, text + os.linesep, *attrs)
        self._maybe_highlight_header(buffer, mark)
        buffer.delete_mark(mark)

        adj = sw.get_vadjustment()
        bot_scrolled = (adj.get_value() == (adj.upper - adj.page_size))

        endmark = buffer.get_mark("end")
        if bot_scrolled:
            display.scroll_to_mark(endmark, 0.0, True, 0, 1)

        tabnum = self.__filtertabs.page_num(display.parent)
        if tabnum != self.__filtertabs.get_current_page() and \
                "ignorecolor" not in attrs:
            self._highlight_tab(tabnum)

        if apply_filters and "ignorecolor" not in attrs:
            self._notice()

    def _send_button(self, button, dest, entry):
        buffer = entry.get_buffer()
        text = buffer.get_text(*buffer.get_bounds())
        if not text:
            return

        dcall = "CQCQCQ"

        num = self.__filtertabs.get_current_page()
        child = self.__filtertabs.get_nth_page(num)
        channel = self.__filtertabs.get_tab_label(child).get_text()
        
        # DISCRIMINATE IF SENDING THE MSG TO A CHANNEL (I.E. a selected user like a private chat)
        if channel.startswith("#"):
            text = channel + "//" + text
        elif channel.startswith("@"):
            dcall = channel[1:]

        port = dest.get_active_text()
        buffer.delete(*buffer.get_bounds())

        self.emit("user-send-chat", dcall, port, text, False)

    def _send_msg(self, qm, msg, conf_key, raw, dest):
        if conf_key:
            try:
                port = self._config.get(conf_key, "port")
            except:
                port = _("Current")
        else:
            port = _("Current")
            
        if port == _("Current"):
            port = dest.get_active_text()
            self.emit("user-send-chat", "CQCQCQ", port, msg, raw)
        elif port == _("All"):
            for i in self.__ports:
                self.emit("user-send-chat", "CQCQCQ", i, msg, raw)

    def _bcast_file(self, but, dest):
        dir = self._config.get("prefs", "download_dir")
        fn = self._config.platform.gui_open_file(dir)
        if not fn:
            return

        try:
            f = file(fn)
        except Exception, e:
            display_error(_("Unable to open file %s: %s") % (fn, e))
            return

        data = f.read()
        f.close()

        if len(data) > (2 << 12):
            display_error(_("File is too large to send (>8KB)"))
            return

        port = dest.get_active_text()
        self.emit("user-send-chat", "CQCQCQ", port, "\r\n" + data, False)

    def _clear(self, but):
        display = self._display_selected()
        display.get_buffer().set_text("")

    def _tab_selected(self, tabs, page, num):
        #
        self._unhighlight_tab(num)
        
        #activate the removefilter button in case we are not on the main chat channel (num!=0)
        delf = self._wtree.get_widget("main_menu_delfilter")
        delf.set_sensitive(num != 0)
        self.__tb_buttons[_("Remove Filter")].set_sensitive(num != 0)

    def _tab_reordered(self, tabs, page, num):
        self._save_filters()

    def _save_filters(self):
        rev = {}
        for key, val in self.__filters.items():
            rev[val] = key

        filters = []
        for i in range(0, self.__filtertabs.get_n_pages()):
            display = self.__filtertabs.get_nth_page(i).child
            if rev.get(display, None):
                filters.append(rev[display])

        self._config.set("state", "filters", str(filters))

    def _add_filter(self, but):
        d = inputdialog.TextInputDialog(title=_("Create filter"))
        d.label.set_text(_("Enter a filter search string:"))
        r = d.run()
        text = d.text.get_text()
        d.destroy()

        if not text:
            return

        if r == gtk.RESPONSE_OK:
            self._build_filter(text)
            self._save_filters()

    def _del_filter(self, but):
        idx = self.__filtertabs.get_current_page()
        page = self.__filtertabs.get_nth_page(idx)
        text = self.__filtertabs.get_tab_label(page).get_text()
        printlog("Mainchat","  : removing %s " % text)
        if (text!= "Main"):
            del self.__filters[text]
            self.__filtertabs.remove_page(idx)
        else:
            display_error("Mainchat  : Cannot remove Main tab")
        self._save_filters()

    def _view_log(self, but):
        display = self._display_selected()
        fn = display.get_buffer().get_logfile()
        self._config.platform.open_text_file(fn)

    def _enter_to_send(self, view, event, dest):
        if event.keyval == 65293:
            self._send_button(None, dest, view)
            return True
        elif event.keyval >= 65470 and event.keyval <= 65482:
            index = event.keyval - 65470
            msgs = sorted(self._config.options("quick"))
            port = dest.get_active_text()
            if index < len(msgs):
                msg = self._config.get("quick", msgs[index])
                self.emit("user-send-chat", "CQCQCQ", port, msg, False)

    def _join_channel(self, button):
        while True:
            d = inputdialog.TextInputDialog(title=_("Join Channel"))
            d.label.set_text(_("Enter channel name:"))
            r = d.run()
            text = d.text.get_text()
            d.destroy()
    
            if not text:
                return
            elif r != gtk.RESPONSE_OK:
                return

            if text.startswith("#"):
                text = text[1:]

            if re.match("^[A-z0-9_-]+$", text):
                self._build_filter("#" + text)
                self._save_filters()
                break

            display_error(_("Channel names must be a single-word " +
                            "alphanumeric string"))

    def _query_user(self, button):
        while True:
            d = inputdialog.TextInputDialog(title=_("Query User"))
            d.label.set_text(_("Enter station:"))
            r = d.run()
            text = d.text.get_text()
            d.destroy()
    
            if not text:
                return
            elif r != gtk.RESPONSE_OK:
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

        tb, = self._getw("toolbar")
        set_toolbar_buttons(self._config, tb)

        buttons = \
            [(addfilter, _("Add Filter"), self._add_filter),
             (delfilter, _("Remove Filter"), self._del_filter),
             (jnchannel, _("Join Channel"), self._join_channel),
             (queryuser, _("Open Private Chat"), self._query_user),
             ]

        c = 0
        for i, l, f in buttons:
            icon = gtk.Image()
            icon.set_from_pixbuf(i)
            icon.show()
            item = gtk.ToolButton(icon, l)
            item.connect("clicked", f)
            try:
                item.set_tooltip_text(l)
            except AttributeError:
                pass
            item.show()
            tb.insert(item, c)
            self.__tb_buttons[l] = item
            c += 1

    def __init__(self, wtree, config):
        MainWindowTab.__init__(self, wtree, config, "chat")

        entry, send, dest = self._getw("entry", "send", "destination")
        self.__filtertabs, = self._getw("filtertabs")
        self.__filters = {}

        self.__filtertabs.remove_page(0)
        self.__filtertabs.connect("switch-page", self._tab_selected)
        self.__filtertabs.connect("page-reordered", self._tab_reordered)

        self.__tb_buttons = {}

        self.__ports = []

        addf = self._wtree.get_widget("main_menu_addfilter")
        addf.connect("activate", self._add_filter)

        delf = self._wtree.get_widget("main_menu_delfilter")
        delf.connect("activate", self._del_filter)

        vlog = self._wtree.get_widget("main_menu_viewlog")
        vlog.connect("activate", self._view_log)

        send.connect("clicked", self._send_button, dest, entry)
        send.set_flags(gtk.CAN_DEFAULT)
        send.connect("expose-event", lambda w, e: w.grab_default())

        if self._config.getboolean("prefs", "check_spelling"):
            spell.prepare_TextBuffer(entry.get_buffer())

        entry.set_wrap_mode(gtk.WRAP_WORD)
        entry.connect("key-press-event", self._enter_to_send, dest)
        entry.grab_focus()

        self._qm = ChatQM(wtree, config)
        self._qst = ChatQST(wtree, config)
        self._qm.connect("user-sent-qm", self._send_msg, False, dest)
        self._qst.connect("qst-fired", self._send_msg, dest)

        self._last_date = 0

        bcast = self._wtree.get_widget("main_menu_bcast")
        bcast.connect("activate", self._bcast_file, dest)

        clear = self._wtree.get_widget("main_menu_clear")
        clear.connect("activate", self._clear)

        try:
            dest.set_tooltip_text(_("Choose the port where chat " +
                                    "and QST messages will be sent"))
        except AttributeError:
            # Old PyGTK doesn't have this
            pass

        self._init_toolbar()

        self.reconfigure()

    def _reconfigure_colors(self, buffer):
        tags = buffer.get_tag_table()

        if not tags.lookup("incomingcolor"):
            for color in ["red", "blue", "green", "grey"]:
                tag = gtk.TextTag(color)
                tag.set_property("foreground", color)
                tags.add(tag)

            tag = gtk.TextTag("bold")
            tag.set_property("weight", pango.WEIGHT_BOLD)
            tags.add(tag)

            tag = gtk.TextTag("italic")
            tag.set_property("style", pango.STYLE_ITALIC)
            tags.add(tag)

            tag = gtk.TextTag("default")
            tag.set_property("indent", -40)
            tag.set_property("indent-set", True)
            tags.add(tag)

        regular = ["incomingcolor", "outgoingcolor",
                   "noticecolor", "ignorecolor"]
        reverse = ["brokencolor"]

        for i in regular + reverse:
            tag = tags.lookup(i)
            if not tag:
                tag = gtk.TextTag(i)
                tags.add(tag)

            if i in regular:
                tag.set_property("foreground", self._config.get("prefs", i))
            elif i in reverse:
                tag.set_property("background", self._config.get("prefs", i))


    def _reconfigure_font(self, display):
        fontname = self._config.get("prefs", "font")
        font = pango.FontDescription(fontname)
        display.modify_font(font)

    def _build_filter(self, text):
        if text is not None:
            ffn = self._config.platform.filter_filename(text)
        else:
            ffn = "Main"
        fn = self._config.platform.log_file(ffn)
        buffer = LoggedTextBuffer(fn)
        buffer.create_mark("end", buffer.get_end_iter(), False)

        display = gtk.TextView(buffer)
        display.set_wrap_mode(gtk.WRAP_WORD_CHAR)
        display.set_editable(False)
        display.set_cursor_visible(False)

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.add(display)

        display.show()
        sw.show()

        if text:
            lab = gtk.Label(text)
        else:
            lab = gtk.Label(_("Main"))

        lab.show()

        self.__filtertabs.append_page(sw, lab)
        if text is not None:
            self.__filtertabs.set_tab_reorderable(sw, True)
        self.__filters[text] = display

        self._reconfigure_colors(buffer)
        self._reconfigure_font(display)

    def _configure_filters(self):
        for i in range(0, self.__filtertabs.get_n_pages()):
            self.__filtertabs.remove_page(i)

        self.__filters = {}

        filters = eval(self._config.get("state", "filters"))
        while None in filters:
            filters.remove(None)
        filters.insert(0, None) # Main catch-all

        for filter in filters:
            self._build_filter(filter)

    def reconfigure(self):
        if not self.__filters.has_key(None):
            # First time only
            self._configure_filters()

        for display in self.__filters.values():
            self._reconfigure_colors(display.get_buffer())
            self._reconfigure_font(display)

        dest, = self._getw("destination")

        self.__ports = []
        for p in self._config.options("ports"):
            spec = self._config.get("ports", p)
            vals = spec.split(",")
            if vals[0] == "True":
                self.__ports.append(vals[-1])
        self.__ports.sort()

        model = dest.get_model()
        if model:
            model.clear()
        else:
            model = gtk.ListStore(gobject.TYPE_STRING)
            dest.set_model(model)
        for port in self.__ports:
            model.append((port,))
        if self.__ports:
            utils.combo_select(dest, self.__ports[0])

    def get_selected_port(self):
        dest, = self._getw("destination")
        return dest.get_active_text()

    def selected(self):
        MainWindowTab.selected(self)

        make_visible = ["main_menu_bcast", "main_menu_clear",
                        "main_menu_addfilter", "main_menu_delfilter",
                        "main_menu_viewlog"]
        
        for name in make_visible:
            item = self._wtree.get_widget(name)
            item.set_property("visible", True)

        entry, = self._getw("entry")
        gobject.idle_add(entry.grab_focus)

    def deselected(self):
        MainWindowTab.deselected(self)

        make_invisible = ["main_menu_bcast", "main_menu_clear",
                          "main_menu_addfilter", "main_menu_delfilter",
                          "main_menu_viewlog"]
        
        for name in make_invisible:
            item = self._wtree.get_widget(name)
            item.set_property("visible", False)
