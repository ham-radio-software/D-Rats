#!/usr/bin/python
#
# Copyright 2009 Dan Smith <dsmith@danplanet.com>
# review 2015 Maurizio Andreotti  <iz2lxi@yahoo.it>
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
from .debug import printlog

import sys
if __name__ == "__main__":
    sys.path.insert(0, ".")
    from . import mainapp
    from . import dplatform
    
    # gettext is the module for translating the labels in different languages  
    import gettext
    lang = gettext.translation("D-RATS", localedir="./locale", languages=["en"])
    lang.install()
    
    printlog("Mainwin","  : sys.path=", sys.path)

from . import version
import os
import time

import libxml2
import gtk
import gtk.glade
import gobject
import subprocess

from d_rats.ui.main_messages import MessagesTab
from d_rats.ui.main_chat import ChatTab
from d_rats.ui.main_events import EventTab
from d_rats.ui.main_files import FilesTab
from d_rats.ui.main_stations import StationsList
from d_rats.ui.main_common import MainWindowElement, prompt_for_station, \
    ask_for_confirmation

from d_rats.version import \
    DRATS_VERSION, \
    DRATS_NAME, \
    DRATS_DESCRIPTION, \
    DRATS_LONG_DESCRIPTION, \
    AUTHORS, \
    COPYRIGHT, \
    AUTHORS_EMAIL, \
    TRANSLATIONS, \
    WEBSITE

from d_rats import formbuilder
from d_rats import signals

class MainWindow(MainWindowElement):
    __gsignals__ = {
        "config-changed" : signals.CONFIG_CHANGED,
        "show-map-station" : signals.SHOW_MAP_STATION,
        "ping-station" : signals.PING_STATION,
        "get-station-list" : signals.GET_STATION_LIST,
        "user-send-chat" : signals.USER_SEND_CHAT,
        "get-chat-port" : signals.GET_CHAT_PORT,
        }
    _signals = __gsignals__

    def _delete(self, window, event):
        if self._config.getboolean("prefs", "confirm_exit"):
            if not ask_for_confirmation("Really exit D-RATS?", window):
                return True

        window.set_default_size(*window.get_size())

    def _destroy(self, window):
        w, h = window.get_size()

        maximized = window.maximize_initially
        self._config.set("state", "main_maximized", maximized)
        if not maximized:
            self._config.set("state", "main_size_x", w)
            self._config.set("state", "main_size_y", h)

        gtk.main_quit()

    def _connect_menu_items(self, window):
        def do_save_and_quit(but):
            window.set_default_size(*window.get_size())
            window.destroy()
        #added 3.9.10
        #def do_check_conns(but);
         #   return
            
        def do_about(but):
            # show the "about window" 
            d = gtk.AboutDialog()
            d.set_transient_for(self._wtree.get_widget("mainwindow"))

            verinfo = "Python %s\nGTK %s\nPyGTK %s\nLibXML using %.1f KB\n" %(\
                sys.version.split()[0],
                ".".join([str(x) for x in gtk.gtk_version]),
                ".".join([str(x) for x in gtk.pygtk_version]),
                libxml2.memoryUsed() / 1024.0)

            d.set_name(DRATS_NAME)
            d.set_version(DRATS_VERSION)
            d.set_copyright(COPYRIGHT)
            d.set_website(WEBSITE)
            d.set_authors((AUTHORS,))
            d.set_comments(DRATS_DESCRIPTION)
            d.set_translator_credits(TRANSLATIONS)
            d.set_comments(verinfo)

            d.run()
            d.destroy()

        def do_debug(but):
            path = self._config.platform.config_file("debug.log")
            if os.path.exists(path):
                self._config.platform.open_text_file(path)
            else:
                d = gtk.MessageDialog(buttons=gtk.BUTTONS_OK,
                                      parent=window)
                d.set_property("text",
                               "Debug log not available")
                d.run()
                d.destroy()

        def do_prefs(but):
            saved = self._config.show(parent=window)
            if saved:
                self.emit("config-changed")
                for tabs in self.tabs.values():
                    tabs.reconfigure()

        def do_map(but):
            # shows the map window passing our username and callsign as defined in the preferecens
            call = self._config.get("user", "callsign")
            self.emit("show-map-station", call)

        def do_message_templates(but):
            d = formbuilder.FormManagerGUI(self._config.form_source_dir())

        def do_ping(but):
            station_list = self.emit("get-station-list")
            stations = []
            for portlist in station_list.values():
                stations += [str(x) for x in portlist]
            station, port = prompt_for_station(stations, self._config)
            if station:
                self.emit("ping-station", station, port)

        def do_conninet(but):
            self._config.set("state", "connected_inet", but.get_active())
            printlog("Mainwin","  : change on connection status to %s" % but.get_active())

        def do_showpane(but, pane):
            self._config.set("state", "sidepane_visible", but.get_active())
            if but.get_active():
                pane.show()
            else:
                pane.hide()

        def do_dq(but):
            
            c = self._config
            #xxxxx
            wtree = gtk.glade.XML(c.ship_obj_fn("ui/mainwindow.glade"),
                                  "dquery_dialog", "D-RATS")
            dlg = wtree.get_widget("dquery_dialog")
            cmd = wtree.get_widget("dq_cmd")
            dlg.set_modal(True)
            dlg.set_transient_for(window)
            r = dlg.run()
            d = cmd.get_text()
            dlg.destroy()
            if r == gtk.RESPONSE_OK:
                port = self.emit("get-chat-port")

                # original d-rats string 
                self.emit("user-send-chat", "CQCQCQ", port, "?D*%s?" % d, True)
                
                #sample rs-ms1a string CQCQCQ: $$Msg,IZ2LXI,,0011DCtest transmission
                #self.emit("user-send-chat", "CQCQCQ", port, "$$Msg,IZ000,,0011D,%s" % d, True)
              
                
        def do_proxy(but):
            if sys.platform != "darwin":
                args = []
            else:
                args = [sys.executable]
            if os.path.exists("./d-rats_repeater"):
                args.append("./d-rats_repeater")
            else:
                args.append("d-rats_repeater")
            printlog("Mainwin","  : Running proxy: %s" % str(args))
            p = subprocess.Popen(args)

        quit = self._wtree.get_widget("main_menu_quit")
        quit.connect("activate", do_save_and_quit)

        about = self._wtree.get_widget("main_menu_about")
        about.connect("activate", do_about)

        debug = self._wtree.get_widget("main_menu_debuglog")
        debug.connect("activate", do_debug)

        menu_prefs = self._wtree.get_widget("main_menu_prefs")
        menu_prefs.connect("activate", do_prefs)

        menu_map = self._wtree.get_widget("main_menu_map")
        img = gtk.Image()
        img.set_from_file("images/map.png")
        menu_map.set_image(img)
        menu_map.connect("activate", do_map)

        menu_templates = self._wtree.get_widget("main_menu_msgtemplates")
        menu_templates.connect("activate", do_message_templates)

        ping = self._wtree.get_widget("main_menu_ping")
        img = gtk.Image()
        img.set_from_file("images/event_ping.png")
        ping.set_image(img)
        ping.connect("activate", do_ping)

        conn = self._wtree.get_widget("main_menu_conninet")
        conn.set_active(self._config.getboolean("state", "connected_inet"))
        self._config.platform.set_connected(conn.get_active())
        conn.connect("activate", do_conninet)

        sspw = self._wtree.get_widget("main_menu_showpane")
        pane = self._wtree.get_widget("main_stations_frame")
        sspw.set_active(self._config.getboolean("state", "sidepane_visible"))
        if not sspw.get_active():
            pane.hide()
        sspw.connect("activate", do_showpane, pane)

        dq = self._wtree.get_widget("main_menu_dq")
        dq.connect("activate", do_dq)

        proxy = self._wtree.get_widget("main_menu_proxy")
        proxy.connect("activate", do_proxy)

    def _page_name(self, index=None):
        if index is None:
            index = self._tabs.get_current_page()

        tablabels = ["messages", "chat", "files", "event"]
        return tablabels[index]

    def _tab_switched(self, tabs, page, page_num):
        tab = self._page_name(page_num)
        self.tabs[self._current_tab].deselected()
        self._current_tab = tab
        self.tabs[self._current_tab].selected()

    def _maybe_blink(self, tab, key):
        blink = self._config.getboolean("prefs", "blink_%s" % key)
        if blink and not self.__window.is_active():
            self.__window.set_urgency_hint(True)

        if key == "event":
            sounde = False
        else:
            sounde = self._config.getboolean("sounds", "%s_enabled" % key)
            soundf = self._config.get("sounds", key)
        if sounde:
            self._config.platform.play_sound(soundf)

    def _got_focus(self, window, event):
        #got focus"
        self.__window.set_urgency_hint(False)

    def __init__(self, config):
        #init"
        from . import mainapp
        wtree = gtk.glade.XML(config.ship_obj_fn("ui/mainwindow.glade"),
                              "mainwindow", "D-RATS")
        MainWindowElement.__init__(self, wtree, config, "")
        self.__window = self._wtree.get_widget("mainwindow")
        self._tabs = self._wtree.get_widget("main_tabs")
        self._tabs.connect("switch-page", self._tab_switched)
        self.tabs = {}
        self.__last_status = 0
        self.tabs["chat"] = ChatTab(wtree, config)
        self.tabs["messages"] = MessagesTab(wtree, config)
        self.tabs["event"] = EventTab(wtree, config)
        self.tabs["files"] = FilesTab(wtree, config)
        self.tabs["stations"] = StationsList(wtree, config)
        for label, tab in self.tabs.items():
            tab.connect("notice", self._maybe_blink, label)
        self._current_tab = "messages"
        ic = "incomingcolor"
        cpr = COPYRIGHT

        self.tabs["chat"]._display_line("D-RATS v%s" % DRATS_VERSION, True, ic)
        self.tabs["chat"]._display_line(cpr, True, ic)
        self.tabs["chat"]._display_line("", True)

        self.__window.connect("destroy", self._destroy)
        self.__window.connect("delete_event", self._delete)
        self.__window.connect("focus-in-event", self._got_focus)

        self._connect_menu_items(self.__window)

        h = self._config.getint("state", "main_size_x")
        w = self._config.getint("state", "main_size_y")
        if self._config.getboolean("state", "main_maximized"):
            self.__window.maximize()
            self.__window.set_default_size(h, w)
        else:
            self.__window.resize(h, w)

        try:
            import gtkmacintegration
            mbar = self._wtree.get_widget("menubar1")
            mbar.hide()
            gtkmacintegration.gtk_mac_menu_set_menu_bar(mbar)
            gtkmacintegration.gtk_mac_menu_set_global_key_handler_enabled(False)
            printlog("Mainwin","  : Enabled OSX menubar integration")
        except ImportError:
            pass

        self.__window.show()

        gobject.timeout_add(3000, self.__update_status)

    def __update_status(self):
        #printlog("Mainwin","  : updating status")
        if (time.time() - self.__last_status) > 30:
            sb = self._wtree.get_widget("statusbar")
            id = sb.get_context_id("default")
            sb.pop(id)

        return True

    def set_status(self, msg):
        # ("mainwindow: setting status")
        sb = self._wtree.get_widget("statusbar")
        cb = self._wtree.get_widget("callbar")

        self.__last_status = time.time()

        id = sb.get_context_id("default")
        sb.pop(id)
        sb.push(id, msg)

        call = self._config.get("user", "callsign")
        self.__window.set_title("D-RATS: %s" % call)
        cb.pop(0)
        cb.push(0, call)

if __name__ == "__main__":
    wtree = gtk.glade.XML("ui/mainwindow.glade", "mainwindow")

    from d_rats import config
    conf = config.DratsConfig(None)

    def test(chat, station, msg):
        printlog("Mainwin","  : %s->%s" % (station, msg))

    chat = ChatTab(wtree, conf)
    chat.connect("user-sent-message", test)

    msgs = MessagesTab(wtree, conf)

    gtk.main()
