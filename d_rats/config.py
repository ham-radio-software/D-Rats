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


import gtk
import gtk.glade
import gobject
import ConfigParser
import os
import random

import utils
import miscwidgets
import inputdialog
import dplatform
import geocode_ui
import config_tips
import spell

from d_rats.ui.main_common import display_error

BAUD_RATES = ["1200", "2400", "4800", "9600", "19200", "38400", "115200"]

_DEF_USER = {
    "name" : "A. Mateur",
    "callsign" : "",
    "latitude" : "45.802020",
    "longitude" : "9.430000",
    "altitude" : "0",
    "units" : _("Metric"),
}

_DEF_PREFS = {
    "download_dir" : ".",
    "blinkmsg" : "False",
    "noticere" : "",
    "ignorere" : "",
    "signon" : _("Online (D-RATS)"),
    "signoff" : _("Going offline (D-RATS)"),
    "dosignon" : "True",
    "dosignoff" : "True",
    "incomingcolor" : "#00004444FFFF",
    "outgoingcolor": "#DDDD44441111",
    "noticecolor" : "#0000660011DD",
    "ignorecolor" : "#BB88BB88BB88",
    "callsigncolor" : "#FFDD99CC77CC",
    "brokencolor" : "#FFFFFFFF3333",
    "logenabled" : "True",
    "debuglog" : "False",
    "eolstrip" : "True",
    "font" : "Sans 12",
    "callsigns" : "%s" % str([(True , "US")]),
    "logresume" : "True",
    "scrollback" : "1024",
    "restore_stations" : "True",
    "useutc" : "False",
    "language" : "English",
    "allow_remote_files" : "True",
    "blink_chat" : "True",
    "blink_messages" : "True",
    "blink_files" : "True",
    "blink_event" : "False",
    "chat_showstatus" : "True",
    "chat_timestamp" : "True",
    "msg_include_reply" : "False",
    "msg_allow_wl2k" : "True",
    "msg_allow_pop3" : "True",
    "msg_wl2k_server" : "server.winlink.org",
    "msg_wl2k_ssid" : "",
    "msg_wl2k_port" : "8772",
    "toolbar_button_size" : "Default",
    "check_spelling" : "False",
    "confirm_exit" : "False",
    "msg_wl2k_rmscall" : "",
    "msg_wl2k_rmsport" : "",
}

_DEF_SETTINGS = {
    "socket_pw" : "",
    "ddt_block_size" : "512",
    "ddt_block_outlimit" : "4",
    "encoding" : "yenc",
    "compression" : "True",
    "gpsport" : "",
    "gpsenabled" : "False",
    "gpsportspeed" : "4800",
    "aprssymtab" : "/",
    "aprssymbol" : ">",
    "compatmode" : "False",
    "inports" : "[]",
    "outports" : "[]",
    "sockflush" : "0.5",
    "pipelinexfers" : "True",
    
    # MAP WINDOW
    "mapdir" : os.path.join(dplatform.get_platform().config_dir(), "maps"),
    "maptype": "base",
    #"mapurlbase":  "http://a.tile.openstreetmap.org/", 
    "mapurlbase":  "https://tile.openstreetmap.de/",
    "keyformapurlbase": "",

    "mapurlcycle": "https://tile.thunderforest.com/cycle/",
    "keyformapurlcycle": "YOUR APIKEY REQUIRED",
    
    "mapurloutdoors": "https://tile.thunderforest.com/outdoors/",
    "keyformapurloutdoors": "?apikey=5a1a4a79354244a38707d83969fd88a2",
     
    "mapurllandscape": "https://tile.thunderforest.com/landscape/",
    "keyformapurllandscape": "?apikey=5a1a4a79354244a38707d83969fd88a2",
    
    # GPS
    #default icon for our station in the map and gpsfixes
    "default_gps_comment" : "BN  *20",
    #background color for markers in the map window
    "map_marker_bgcolor": "yellow",
    
    "warmup_length" : "8",
    "warmup_timeout" : "3",
    "force_delay" : "-2",
    "ping_info" : "",
    "smtp_server" : "",
    "smtp_replyto" : "",
    "smtp_tls" : "False",
    "smtp_username" : "",
    "smtp_password" : "",
    "smtp_port" : "25",
    "smtp_dogw" : "False",
    "sniff_packets" : "False",
    "map_tile_ttl" : "720",
    "msg_flush" : "60",

    
    "msg_forward" : "False",
    "form_logo_dir" : os.path.join(dplatform.get_platform().config_dir(), "logos"),
    
    "mapserver_ip": "localhost",
    "mapserver_port": "5011",
    "mapserver_active": "False",
    "http_proxy" : "",
    "station_msg_ttl" : "3600",
    "timestamp_positions" : "False",
    "msg_wl2k_mode" : "Network",
    "qst_size_limit" : "2048",
    "msg_pop3_server" : "False",
    "msg_pop3_port" : "9110",
    "msg_smtp_server" : "False",
    "msg_smtp_port" : "9025",
    "delete_from" : "",
    "remote_admin_passwd" : "",
}

_DEF_STATE = {
    "main_size_x" : "640",
    "main_size_y" : "400",
    "main_advanced" : "200",
    "filters" : "[]",
    "show_all_filter" : "False",
    "connected_inet" : "True",
    "qsts_enabled" : "True",
    "sidepane_visible" : "True",
    "status_msg" : "Online (D-RATS)",
    "status_state" : "Online",
    "events_sort" : str(int(gtk.SORT_DESCENDING)),
    "form_email_x" : "600",
    "form_email_y" : "500",
}

_DEF_SOUNDS = {
    "messages" : "",
    "messages_enabled" : "False",
    "chat" : "",
    "chat_enabled" : "False",
    "files" : "",
    "files_enabled" : "False",
}

DEFAULTS = {
    "user" : _DEF_USER,
    "prefs" : _DEF_PREFS,
    "settings" : _DEF_SETTINGS,
    "state" : _DEF_STATE,
    "quick" : {},
    "tcp_in" : {},
    "tcp_out" : {},
    "incoming_email" : {},
    "sounds" : _DEF_SOUNDS,
    "ports" : { "ports_0" : "True,net:ref.d-rats.com:9000,,False,False,RAT", 
                "ports_1" : "False,net:localhost:9000,,False,False,Local RATflector",
                "ports_2" : "False,net:k3pdr.dstargateway.org:9000,,False,False,K3PDR",
                },
}

if __name__ == "__main__":
    import gettext
    gettext.install("D-RATS")

def color_string(color):
    try:
        return color.to_string()
    except:
        return "#%04x%04x%04x" % (color.red, color.green, color.blue)

def load_portspec(wtree, portspec, info, name):
    namewidget = wtree.get_widget("name")
    namewidget.set_text(name)
    namewidget.set_sensitive(False)

    tsel = wtree.get_widget("type")
    if portspec.startswith("net:"):
        tsel.set_active(1)
        net, host, port = portspec.split(":")
        wtree.get_widget("net_host").set_text(host)
        wtree.get_widget("net_port").set_value(int(port))
        wtree.get_widget("net_pass").set_text(info)
    elif portspec.startswith("tnc"):
        tsel.set_active(2)
        if len(portspec.split(":")) == 3:
            tnc, port, tncport = portspec.split(":", 2)
            path = ""
        else:
            tnc, port, tncport, path = portspec.split(":", 3)
        wtree.get_widget("tnc_port").child.set_text(port)
        wtree.get_widget("tnc_tncport").set_value(int(tncport))
        utils.combo_select(wtree.get_widget("tnc_rate"), info)
        wtree.get_widget("tnc_ax25path").set_text(path.replace(";", ","))
        if portspec.startswith("tnc-ax25"):
            wtree.get_widget("tnc_ax25").set_active(True)
    elif portspec.startswith("agwpe:"):
        tsel.set_active(4)
        agw, addr, port = portspec.split(":")
        wtree.get_widget("agw_addr").set_text(addr)
        wtree.get_widget("agw_port").set_value(int(port))
    else:
        tsel.set_active(0)
        wtree.get_widget("serial_port").child.set_text(portspec)
        utils.combo_select(wtree.get_widget("serial_rate"), info)

def prompt_for_port(portspec=None, info=None, pname=None):
    p = os.path.join(dplatform.get_platform().source_dir(), "ui/addport.glade")
    wtree = gtk.glade.XML(p, "addport", "D-RATS")

    ports = dplatform.get_platform().list_serial_ports()

    sportsel = wtree.get_widget("serial_port")
    tportsel = wtree.get_widget("tnc_port")
    sportlst = sportsel.get_model()
    tportlst = tportsel.get_model()
    sportlst.clear()
    tportlst.clear()

    for port in ports:
        sportlst.append((port,))
        tportlst.append((port,))

    if ports:
        sportsel.set_active(0)
        tportsel.set_active(0)

    sratesel = wtree.get_widget("serial_rate")
    tratesel = wtree.get_widget("tnc_rate")
    tprotsel = wtree.get_widget("tnc_ax25")
    tnc_ax25 = wtree.get_widget("tnc_ax25")
    tnc_path = wtree.get_widget("tnc_ax25path")
    tnc_ax25.connect("toggled",
                     lambda b: tnc_path.set_sensitive(b.get_active()))

    sratesel.set_active(3)
    tratesel.set_active(3)

    netaddr = wtree.get_widget("net_host")
    netport = wtree.get_widget("net_port")
    netpass = wtree.get_widget("net_pass")

    agwaddr = wtree.get_widget("agw_addr")
    agwport = wtree.get_widget("agw_port")
    agwport.set_value(8000)

    descriptions = [
        "A D-STAR radio connected to a serial port",
        "A network link to a ratflector instance",
        "A KISS-mode TNC connected to a serial port",
        "A locally-attached dongle",
        "A TNC attached to an AGWPE server",
        ]

    tablist = [_("Serial"), _("Network"), _("TNC"), _("Dongle"), _("AGWPE")]

    def chg_type(tsel, tabs, desc):
        print("Config    : Changed to %s" % tsel.get_active_text())
        tabs.set_current_page(tsel.get_active())

        desc.set_markup("<span fgcolor='blue'>%s</span>" % \
                            descriptions[tsel.get_active()])

    name = wtree.get_widget("name")
    desc = wtree.get_widget("typedesc")
    ttncport = wtree.get_widget("tnc_tncport")
    tabs = wtree.get_widget("editors")
    tabs.set_show_tabs(False)
    tsel = wtree.get_widget("type")
    tsel.set_active(0)
    tsel.connect("changed", chg_type, tabs, desc)

    if portspec:
        load_portspec(wtree, portspec, info, pname)
    elif pname is False:
        name.set_sensitive(False)

    d = wtree.get_widget("addport")

    chg_type(tsel, tabs, desc)
    r = d.run()

    t = tablist[tsel.get_active()]
    if t == _("Serial"):
        portspec = sportsel.get_active_text(), sratesel.get_active_text()
    elif t == _("Network"):
        portspec = "net:%s:%i" % (netaddr.get_text(), netport.get_value()), \
            netpass.get_text()
    elif t == _("TNC"):
        if tprotsel.get_active():
            digi_path = tnc_path.get_text().replace(",", ";")
            portspec = "tnc-ax25:%s:%i:%s" % (tportsel.get_active_text(),
                                              ttncport.get_value(),
                                              digi_path), \
                                              tratesel.get_active_text()
        else:
            portspec = "%s:%s:%i" % (type,
                                     tportsel.get_active_text(),
                                     ttncport.get_value()), \
                                     tratesel.get_active_text()
    elif t == _("Dongle"):
        portspec = "dongle:", ""
    elif t == _("AGWPE"):
        portspec = "agwpe:%s:%i" % (agwaddr.get_text(), agwport.get_value()), ""

    portspec = (name.get_text(),) + portspec
    d.destroy()

    if r:
        return portspec
    else:
        return None, None, None

def disable_with_toggle(toggle, widget):
    toggle.connect("toggled",
                   lambda t, w: w.set_sensitive(t.get_active()), widget)
    widget.set_sensitive(toggle.get_active())

def disable_by_combo(combo, map):
    # Expects a map like:
    # map = {
    #   "value1" : [el1, el2],
    #   "value2" : [el3, el4],
    # }
    def set_disables(combo, map):
        for i in map.values():
            for j in i:
                j.set_sensitive(False)
        for i in map[combo.get_active_text()]:
            i.set_sensitive(True)
    combo.connect("changed", set_disables, map)
    set_disables(combo, map)

class AddressLookup(gtk.Button):
    def __init__(self, caption, latw, lonw, window=None):
        gtk.Button.__init__(self, caption)
        self.connect("clicked", self.clicked, latw, lonw, window)

    def clicked(self, me, latw, lonw, window):
        aa = geocode_ui.AddressAssistant()
        aa.set_transient_for(window)
        r = aa.run()
        if r == gtk.RESPONSE_OK:
            latw.latlon.set_text("%.5f" % aa.lat)
            lonw.latlon.set_text("%.5f" % aa.lon)

class DratsConfigWidget(gtk.HBox):
    def __init__(self, config, sec, name, have_revert=False):
        gtk.HBox.__init__(self, False, 2)

        self.do_not_expand = False

        self.config = config
        self.vsec = sec
        self.vname = name
        self._widget = None

        self.config.widgets.append(self)

        if not config.has_section(sec):
            config.add_section(sec)

        if name is not None:
            if not config.has_option(sec, name):
                self._revert()
            else:
                self.value = config.get(sec, name)
        else:
            self.value = None

        if have_revert:
            rb = gtk.Button(None, gtk.STOCK_REVERT_TO_SAVED)
            rb.connect("clicked", self._revert)
            rb.show()
            self.pack_end(rb, 0, 0, 0)

    def _revert(self, button=None):
        try:
            self.value = DEFAULTS[self.vsec][self.vname]
        except KeyError:
            print("Config    : DEFAULTS has no %s/%s" % (self.vsec, self.vname))
            self.value = ""

        if not self._widget:
            print("Config    : AAACK: No _widget in revert")
            return

        if isinstance(self._widget, gtk.Entry):
            self._widget.set_text(str(self.value))
        elif isinstance(self._widget, gtk.SpinButton):
            self._widget.set_value(float(self.value))
        elif isinstance(self._widget, gtk.CheckButton):
            self._widget.set_active(self.value.upper() == "TRUE")
        elif isinstance(self._widget, miscwidgets.FilenameBox):
            self._widget.set_filename(self.value)
        else:
            print("Config    : AAACK: I don't know how to do a %s" % self._widget.__class__)

    def save(self):
        #print("Config    : "Saving %s/%s: %s" % (self.vsec, self.vname, self.value))
        self.config.set(self.vsec, self.vname, self.value)

    def set_value(self, value):
        pass

    def add_text(self, limit=0, hint=None):
        def changed(entry):
            if entry.get_text() == hint:
                self.value = ""
            else:
                self.value = entry.get_text()

        w = gtk.Entry(limit)
        w.connect("changed", changed)
        w.set_text(self.value)
        w.set_size_request(50, -1)
        w.show()
        self._widget = w

        if hint:
            utils.set_entry_hint(w, hint, bool(self.value))

        self.pack_start(w, 1, 1, 1)

    def add_upper_text(self, limit=0):
        def changed(entry):
            self.value = entry.get_text().upper()

        w = gtk.Entry(limit)
        w.connect("changed", changed)
        w.set_text(self.value)
        w.set_size_request(50, -1)
        w.show()
        self._widget = w

        self.pack_start(w, 1, 1, 1)

    def add_pass(self, limit=0):
        def changed(entry):
            self.value = entry.get_text()

        w = gtk.Entry(limit)
        w.connect("changed", changed)
        w.set_text(self.value)
        w.set_visibility(False)
        w.set_size_request(50, -1)
        w.show()
        self._widget = w

        self.pack_start(w, 1, 1, 1)

    def add_combo(self, choices=[], editable=False, size=80):
        def changed(box):
            self.value = box.get_active_text()

        if self.value not in choices:
            choices.append(self.value)

        w = miscwidgets.make_choice(choices, editable, self.value)
        w.connect("changed", changed)
        w.set_size_request(size, -1)
        w.show()
        self._widget = w

        self.pack_start(w, 1, 1, 1)

    def add_bool(self, label=None):
        if label is None:
            label = _("Enabled")

        def toggled(but, confwidget):
            confwidget.value = str(but.get_active())

        w = gtk.CheckButton(label)
        w.connect("toggled", toggled, self)
        w.set_active(self.value == "True")
        w.show()
        self._widget = w

        self.do_not_expand = True

        self.pack_start(w, 1, 1, 1)

    def add_coords(self):
        def changed(entry, confwidget):
            try:
                confwidget.value = "%3.6f" % entry.value()
            except Exception, e:
                print("Config    : Invalid Coords: %s" % e)
                confwidget.value = "0"

        w = miscwidgets.LatLonEntry()
        w.connect("changed", changed, self)
        print("Config    : Setting LatLon value: %s" % self.value)
        w.set_text(self.value)
        print("Config    : LatLon text: %s" % w.get_text())
        w.show()

        # Dirty ugly hack!
        self.latlon = w

        self.pack_start(w, 1, 1, 1)

    def add_numeric(self, min, max, increment, digits=0):
        def value_changed(sb):
            self.value = "%f" % sb.get_value()

        adj = gtk.Adjustment(float(self.value), min, max, increment, increment)
        w = gtk.SpinButton(adj, digits)
        w.connect("value-changed", value_changed)
        w.show()
        self._widget = w

        self.pack_start(w, 1, 1, 1)

    def add_color(self):
        def color_set(but):
            self.value = color_string(but.get_color())

        w = gtk.ColorButton()
        w.set_color(gtk.gdk.color_parse(self.value))
        w.connect("color-set", color_set)
        w.show()

        self.pack_start(w, 1, 1, 1)

    def add_font(self):
        def font_set(but):
            self.value = but.get_font_name()

        w = gtk.FontButton()
        w.set_font_name(self.value)
        w.connect("font-set", font_set)
        w.show()

        self.pack_start(w, 1, 1, 1)

    def add_path(self):
        def filename_changed(box):
            self.value = box.get_filename()

        w = miscwidgets.FilenameBox(find_dir=True)
        w.set_filename(self.value)
        w.connect("filename-changed", filename_changed)
        w.show()
        self._widget = w

        self.pack_start(w, 1, 1, 1)

    def add_sound(self):
        def filename_changed(box):
            self.value = box.get_filename()

        def test_sound(button):
            print("Config    : Testing playback of %s" % self.value)
            p = dplatform.get_platform()
            p.play_sound(self.value)

        w = miscwidgets.FilenameBox(find_dir=False)
        w.set_filename(self.value)
        w.connect("filename-changed", filename_changed)
        w.show()

        b = gtk.Button(_("Test"), gtk.STOCK_MEDIA_PLAY)
        b.connect("clicked", test_sound)
        b.show()

        box = gtk.HBox(False, 2)
        box.show()
        box.pack_start(w, 1, 1, 1)
        box.pack_start(b, 0, 0, 0)

        self.pack_start(box, 1, 1, 1)

class DratsListConfigWidget(DratsConfigWidget):
    def __init__(self, config, section):
        try:
            DratsConfigWidget.__init__(self, config, section, None)
        except ConfigParser.NoOptionError:
            pass

    def convert_types(self, coltypes, values):
        newvals = []

        i = 0
        while i < len(values):
            gtype, label = coltypes[i]
            value = values[i]

            try:
                if gtype == gobject.TYPE_INT:
                    value = int(value)
                elif gtype == gobject.TYPE_FLOAT:
                    value = float(value)
                elif gtype == gobject.TYPE_BOOLEAN:
                    value = eval(value)
            except ValueError, e:
                print("Config    : Failed to convert %s for %s: %s" % (value, label, e))
                return []

            i += 1
            newvals.append(value)

        return newvals

    def set_sort_column(self, col):
        self.listw.set_sort_column(col)

    def add_list(self, cols, make_key=None):
        def item_set(lw, key):
            pass

        w = miscwidgets.KeyedListWidget(cols)

        def foo(*args):
            return
        w.connect("item-toggled", foo)

        options = self.config.options(self.vsec)
        for option in options:
            vals = self.config.get(self.vsec, option).split(",", len(cols))
            vals = self.convert_types(cols[1:], vals)
            if not vals:
                continue

            try:
                if make_key:
                    key = make_key(vals)
                else:
                    key = vals[0]
                w.set_item(key, *tuple(vals))
            except Exception, e:
                print("Config    : Failed to set item '%s': %s" % (str(vals), e))

        w.connect("item-set", item_set)
        w.show()

        self.pack_start(w, 1, 1, 1)

        self.listw = w

        return w

    def save(self):
        for opt in self.config.options(self.vsec):
            self.config.remove_option(self.vsec, opt)

        count = 0

        for key in self.listw.get_keys():
            vals = self.listw.get_item(key)
            vals = [str(x) for x in vals]
            value = ",".join(vals[1:])
            label = "%s_%i" % (self.vsec, count)
            print("Config    : Setting %s: %s" % (label, value))
            self.config.set(self.vsec, label, value)
            count += 1

class DratsPanel(gtk.Table):
    INITIAL_ROWS = 13
    INITIAL_COLS = 2

    def __init__(self, config):
        gtk.Table.__init__(self, self.INITIAL_ROWS, self.INITIAL_COLS)
        self.config = config
        self.vals = []

        self.row = 0
        self.rows = self.INITIAL_ROWS

    def mv(self, title, *args):
        if self.row+1 == self.rows:
            self.rows += 1
            print("Config    : Resizing box to %i" % self.rows)
            self.resize(self.rows, 2)

        hbox = gtk.HBox(False, 2)

        lab = gtk.Label(title)
        lab.show()
        self.attach(lab, 0, 1, self.row, self.row+1, gtk.SHRINK, gtk.SHRINK, 5)

        for i in args:
            i.show()
            if isinstance(i, DratsConfigWidget):
                if i.do_not_expand:
                    hbox.pack_start(i, 0, 0, 0)
                else:
                    hbox.pack_start(i, 1, 1, 0)
                self.vals.append(i)
            else:
                hbox.pack_start(i, 0, 0, 0)

        hbox.show()
        self.attach(hbox, 1, 2, self.row, self.row+1, yoptions=gtk.SHRINK)

        self.row += 1

    def mg(self, title, *args):
        if len(args) % 2:
            raise Exception("Need label,widget pairs")

        table = gtk.Table(len(args)/2, 2)

        row = 0

        k = { "yoptions" : gtk.SHRINK,
              "xoptions" : gtk.SHRINK,
              "xpadding" : 10,
              "ypadding" : 0}

        for i in range(0, len(args), 2):
            label = gtk.Label(args[i])
            widget = args[i+1]

            label.show()
            widget.show()

            table.attach(label, 0, 1, row, row+1, **k)
            table.attach(widget, 1, 2, row, row+1, **k)

            row += 1

        table.show()
        frame = gtk.Frame(title)
        frame.show()
        frame.add(table)

        self.attach(frame, 1, 2, self.row, self.row+1)

class DratsPrefsPanel(DratsPanel):
    def __init__(self, config):
        DratsPanel.__init__(self, config)

        val = DratsConfigWidget(config, "user", "callsign")
        val.add_upper_text(8)
        self.mv(_("Callsign"), val)

        val = DratsConfigWidget(config, "user", "name")
        val.add_text()
        self.mv(_("Name"), val)

        val1 = DratsConfigWidget(config, "prefs", "dosignon")
        val1.add_bool()
        val2 = DratsConfigWidget(config, "prefs", "signon")
        val2.add_text()
        self.mv(_("Sign-on Message"), val1, val2)
        disable_with_toggle(val1._widget, val2._widget)

        val1 = DratsConfigWidget(config, "prefs", "dosignoff")
        val1.add_bool()
        val2 = DratsConfigWidget(config, "prefs", "signoff")
        val2.add_text()
        self.mv(_("Sign-off Message"), val1, val2)
        disable_with_toggle(val1._widget, val2._widget)

        val = DratsConfigWidget(config, "user", "units")
        val.add_combo([_("Imperial"), _("Metric")])
        self.mv(_("Units"), val)

        val = DratsConfigWidget(config, "prefs", "useutc")
        val.add_bool()
        self.mv(_("Show time in UTC"), val)

        val = DratsConfigWidget(config, "settings", "ping_info")
        val.add_text(hint=_("Version and OS Info"))
        self.mv(_("Ping reply"), val)

        val = DratsConfigWidget(config, "prefs", "language")
        val.add_combo(["English", "German", "Italiano", "Dutch"])
        self.mv(_("Language"), val)

        mval = DratsConfigWidget(config, "prefs", "blink_messages")
        mval.add_bool()

        cval = DratsConfigWidget(config, "prefs", "blink_chat")
        cval.add_bool()

        fval = DratsConfigWidget(config, "prefs", "blink_files")
        fval.add_bool()

        eval = DratsConfigWidget(config, "prefs", "blink_event")
        eval.add_bool()

        self.mg(_("Blink tray on"),
                _("Incoming Messages"), mval,
                _("New Chat Messages"), cval,
                _("Incoming Files"), fval,
                _("Received Events"), eval)

class DratsPathsPanel(DratsPanel):
    def __init__(self, config, window):
        DratsPanel.__init__(self, config)

        val = DratsConfigWidget(config, "prefs", "download_dir", True)
        val.add_path()
        self.mv(_("File Transfer Path"), val)

        val = DratsConfigWidget(config, "settings", "mapdir", True)
        val.add_path()
        self.mv(_("Base Map Storage Path"), val)
           
        val = DratsConfigWidget(config, "settings", "form_logo_dir", True)
        val.add_path()
        self.mv(_("Form Logo Path"), val)
        

class DratsMapPanel(DratsPanel):
    def __init__(self, config, window):
        DratsPanel.__init__(self, config)
       
        
        #asking which map use
        val = DratsConfigWidget(config, "settings", "maptype")
        val.add_combo(["base", "cycle", "outdoors", "landscape"])
        self.mv(_("Map to use"), val)
 
        val = DratsConfigWidget(config, "settings", "mapurlbase", True)
        val.add_text()
        self.mv(_("BaseMap server url"), val)        
 
        #opencycle
        val = DratsConfigWidget(config, "settings", "mapurlcycle", True)
        val.add_text()
        self.mv(_("OpenCycleMap server url"), val)          

        val = DratsConfigWidget(config, "settings", "keyformapurlcycle", True)
        val.add_text()
        self.mv(_("Key string to append to CycleMap url"), val)         
        
        
        #landscape
        val = DratsConfigWidget(config, "settings", "mapurllandscape", True)
        val.add_text()
        self.mv(_("Landscape server url"), val)          

        val = DratsConfigWidget(config, "settings", "keyformapurllandscape", True)
        val.add_text()
        self.mv(_("Key string to append to landscape url"), val)   
        
        
        #outdoors
        val = DratsConfigWidget(config, "settings", "mapurloutdoors", True)
        val.add_text()
        self.mv(_("Outdoors server url"), val)          

        val = DratsConfigWidget(config, "settings", "keyformapurloutdoors", True)
        val.add_text()
        self.mv(_("Key string to append to outdoors url"), val)   


        val = DratsConfigWidget(config, "settings", "map_tile_ttl")
        val.add_numeric(0, 9999999999999, 1)
        self.mv(_("Freshen map after"), val, gtk.Label(_("hours")))
   
        val = DratsConfigWidget(config, "settings", "timestamp_positions")
        val.add_bool()
        self.mv(_("Report position timestamps on map"), val)


class DratsGPSPanel(DratsPanel):
    def __init__(self, config, window):
        DratsPanel.__init__(self, config)

        lat = DratsConfigWidget(config, "user", "latitude")
        lat.add_coords()
        self.mv(_("Latitude"), lat)

        lon = DratsConfigWidget(config, "user", "longitude")
        lon.add_coords()
        self.mv(_("Longitude"), lon)

        geo = AddressLookup(_("Lookup"), lat, lon, window)
        self.mv(_("Lookup by address"), geo)

        alt = DratsConfigWidget(config, "user", "altitude")
        alt.add_numeric(0, 29028, 1)
        self.mv(_("Altitude"), alt)

        ports = dplatform.get_platform().list_serial_ports()

        val = DratsConfigWidget(config, "settings", "gpsenabled")
        val.add_bool()
        self.mv(_("Use External GPS"), val)

        port = DratsConfigWidget(config, "settings", "gpsport")
        port.add_combo(ports, True, 120)
        rate = DratsConfigWidget(config, "settings", "gpsportspeed")
        rate.add_combo(BAUD_RATES, False)
        self.mv(_("External GPS"), port, rate)
        disable_with_toggle(val._widget, port._widget)
        disable_with_toggle(val._widget, rate._widget)

        val1 = DratsConfigWidget(config, "settings", "aprssymtab")
        val1.add_text(1)
        val2 = DratsConfigWidget(config, "settings", "aprssymbol")
        val2.add_text(1)
        self.mv(_("GPS-A Symbol"),
                gtk.Label(_("Table:")), val1,
                gtk.Label(_("Symbol:")), val2)
     
        def gps_comment_from_dprs(button, val):
            import qst
            dprs = qst.do_dprs_calculator(config.get("settings",
                                                     "default_gps_comment"))
            if dprs is not None:
                config.set("settings", "default_gps_comment", dprs)
                val._widget.set_text(dprs)

        val = DratsConfigWidget(config, "settings", "default_gps_comment")
        val.add_text(20)
        but = gtk.Button(_("DPRS"))
        but.connect("clicked", gps_comment_from_dprs, val)
        self.mv(_("Default GPS comment"), val, but)



class DratsGPSExportPanel(DratsPanel):
    def __init__(self, config, window):
        DratsPanel.__init__(self, config)

        val = DratsConfigWidget(config, "settings", "mapserver_active", True)
        val.add_bool()
        self.mv(_("Check to enable export GPS messages as JSON string"), val)  
        
        val = DratsConfigWidget(config, "settings", "mapserver_ip")
        val.add_text(12)
        self.mv(_("IP address"), val)
        
        val = DratsConfigWidget(config, "settings", "mapserver_port")
        val.add_text(6)
        self.mv(_("IP port"), val)
           
       
      
class DratsAppearancePanel(DratsPanel):
    def __init__(self, config):
        DratsPanel.__init__(self, config)

        val = DratsConfigWidget(config, "prefs", "noticere")
        val.add_text()
        self.mv(_("Notice RegEx"), val)

        val = DratsConfigWidget(config, "prefs", "ignorere")
        val.add_text()
        self.mv(_("Ignore RegEx"), val)

        colors = ["Incoming", "Outgoing", "Notice",
                  "Ignore", "Callsign", "Broken"]

        # Mark these strings so they get picked up and become available
        # to the _(i) below
        _trans_colors = [_("Incoming Color"), _("Outgoing Color"),
                         _("Notice Color"), _("Ignore Color"),
                         _("Callsign Color"), _("Broken Color")]

        for i in colors:
            low = i.lower()
            val = DratsConfigWidget(config, "prefs", "%scolor" % low)
            val.add_color()
            self.mv(_("%s Color" % i), val)

        sizes = [_("Default"), _("Large"), _("Small")]
        val = DratsConfigWidget(config, "prefs", "toolbar_button_size")
        val.add_combo(sizes, False)
        self.mv(_("Toolbar buttons"), val)

        val = DratsConfigWidget(config, "prefs", "check_spelling")
        val.add_bool()
        self.mv(_("Check spelling"), val)
        sp = spell.get_spell()
        val._widget.set_sensitive(sp.test())

        val = DratsConfigWidget(config, "prefs", "confirm_exit")
        val.add_bool()
        self.mv(_("Confirm exit"), val)

class DratsChatPanel(DratsPanel):
    def __init__(self, config):
        DratsPanel.__init__(self, config)

        val = DratsConfigWidget(config, "prefs", "logenabled")
        val.add_bool()
        self.mv(_("Log chat traffic"), val)

        val = DratsConfigWidget(config, "prefs", "logresume")
        val.add_bool()
        self.mv(_("Load log tail"), val)

        val = DratsConfigWidget(config, "prefs", "font")
        val.add_font()
        self.mv(_("Chat font"), val)

        val = DratsConfigWidget(config, "prefs", "scrollback")
        val.add_numeric(0, 9999, 1)
        self.mv(_("Scrollback Lines"), val)

        val = DratsConfigWidget(config, "prefs", "chat_showstatus")
        val.add_bool()
        self.mv(_("Show status updates in chat"), val)

        val = DratsConfigWidget(config, "prefs", "chat_timestamp")
        val.add_bool()
        self.mv(_("Timestamp chat messages"), val)

        val = DratsConfigWidget(config, "settings", "qst_size_limit")
        val.add_numeric(1, 9999, 1)
        self.mv(_("QST Size Limit"), val)

class DratsSoundPanel(DratsPanel):
    def __init__(self, config):
        DratsPanel.__init__(self, config)

        def do_snd(k, l):
            snd = DratsConfigWidget(config, "sounds", k)
            snd.add_sound()
            enb = DratsConfigWidget(config, "sounds", "%s_enabled" % k)
            enb.add_bool()
            self.mv(l, snd, enb)

        do_snd("chat", _("Chat activity"))
        do_snd("messages", _("Message activity"))
        do_snd("files", _("File activity"))


class DratsRadioPanel(DratsPanel):
    INITIAL_ROWS = 3

    def mv(self, title, *widgets):
        self.attach(widgets[0], 0, 2, 0, 1)
        widgets[0].show()

        if len(widgets) > 1:
            box = gtk.HBox(True, 2)

            for i in widgets[1:]:
                box.pack_start(i, 0, 0, 0)
                i.show()

            box.show()
            self.attach(box, 0, 2, 1, 2, yoptions=gtk.SHRINK)

    def but_add(self, button, lw):
        name, port, info = prompt_for_port()
        if name:
            lw.set_item(name, True, port, info, False, False, name)

    def but_mod(self, button, lw):
        values = lw.get_item(lw.get_selected())
        print("Config    : Values: %s" % str(values))
        name, port, info = prompt_for_port(values[2], values[3], values[6])
        if name:
            lw.set_item(values[6], values[1], port, info, values[4], values[5], values[6])

    def but_rem(self, button, lw):
        lw.del_item(lw.get_selected())

    def __init__(self, config):
        DratsPanel.__init__(self, config)

        cols = [(gobject.TYPE_STRING, "ID"),
                (gobject.TYPE_BOOLEAN, _("Enabled")),
                (gobject.TYPE_STRING, _("Port")),
                (gobject.TYPE_STRING, _("Settings")),
                (gobject.TYPE_BOOLEAN, _("Sniff")),
                (gobject.TYPE_BOOLEAN, _("Raw Text")),
                (gobject.TYPE_STRING, _("Name"))]

        lab = gtk.Label(_("Configure data paths below.  This may include any number of serial-attached radios and network-attached proxies."))

        val = DratsListConfigWidget(config, "ports")

        def make_key(vals):
            return vals[5]

        lw = val.add_list(cols, make_key)
        add = gtk.Button(_("Add"), gtk.STOCK_ADD)
        add.connect("clicked", self.but_add, lw)
        mod = gtk.Button(_("Edit"), gtk.STOCK_EDIT)
        mod.connect("clicked", self.but_mod, lw)
        rem = gtk.Button(_("Remove"), gtk.STOCK_DELETE)
        rem.connect("clicked", self.but_rem, lw)

        val.set_sort_column(6);

        self.mv(_("Paths"), val, add, mod, rem)

        lw.set_resizable(1, False)

class DratsTransfersPanel(DratsPanel):
    def __init__(self, config):
        DratsPanel.__init__(self, config)

        val = DratsConfigWidget(config, "settings", "ddt_block_size", True)
        val.add_numeric(32, 4096, 32)
        self.mv(_("Block size"), val)

        val = DratsConfigWidget(config, "settings", "ddt_block_outlimit", True)
        val.add_numeric(1, 32, 1)
        self.mv(_("Pipeline blocks"), val)

        val = DratsConfigWidget(config, "prefs", "allow_remote_files")
        val.add_bool()
        self.mv(_("Remote file transfers"), val)

        val = DratsConfigWidget(config, "settings", "warmup_length", True)
        val.add_numeric(0, 64, 8)
        self.mv(_("Warmup Length"), val)

        val = DratsConfigWidget(config, "settings", "warmup_timeout", True)
        val.add_numeric(0, 16, 1)
        self.mv(_("Warmup timeout"), val)

        val = DratsConfigWidget(config, "settings", "force_delay", True)
        val.add_numeric(-32, 32, 1)
        self.mv(_("Force transmission delay"), val)

        val = DratsConfigWidget(config, "settings", "delete_from")
        val.add_text()
        self.mv(_("Allow file deletes from"), val)

        val = DratsConfigWidget(config, "settings", "remote_admin_passwd")
        val.add_pass()
        self.mv(_("Remote admin password"), val)

class DratsMessagePanel(DratsPanel):
    def __init__(self, config):
        DratsPanel.__init__(self, config)

        vala = DratsConfigWidget(config, "settings", "msg_forward")
        vala.add_bool()
        self.mv(_("Automatically forward messages"), vala)

        val = DratsConfigWidget(config, "settings", "msg_flush")
        val.add_numeric(15, 9999, 1)
        lab = gtk.Label(_("seconds"))
        self.mv(_("Queue flush interval"), val, lab)
        disable_with_toggle(vala._widget, val._widget)

        val = DratsConfigWidget(config, "settings", "station_msg_ttl")
        val.add_numeric(0, 99999, 1)
        lab = gtk.Label(_("seconds"))
        self.mv(_("Station TTL"), val, lab)
        disable_with_toggle(vala._widget, val._widget)

        val = DratsConfigWidget(config, "prefs", "msg_include_reply")
        val.add_bool()
        self.mv(_("Include original in reply"), val)

        val = DratsConfigWidget(config, "prefs", "msg_allow_pop3")
        val.add_bool()
        self.mv(_("Allow POP3 Gateway"), val)

        vala = DratsConfigWidget(config, "prefs", "msg_allow_wl2k")
        vala.add_bool()
        self.mv(_("Allow WL2K Gateway"), vala)

        wlm = DratsConfigWidget(config, "settings", "msg_wl2k_mode")
        wlm.add_combo(["Network", "RMS"], False)
        self.mv(_("WL2K Connection"), wlm)

        wl2k_servers = [x + ".winlink.org" for x in ["server",
                                                     "perth",
                                                     "halifax",
                                                     "sandiego",
                                                     "wien"]]
        srv = DratsConfigWidget(config, "prefs", "msg_wl2k_server")
        srv.add_combo(wl2k_servers, True)
        prt = DratsConfigWidget(config, "prefs", "msg_wl2k_port")
        prt.add_numeric(1, 65535, 1)
        lab = gtk.Label(_("Port"))
        self.mv(_("WL2K Network Server"), srv, lab, prt)

        rms = DratsConfigWidget(config, "prefs", "msg_wl2k_rmscall")
        rms.add_upper_text(10)

        lab = gtk.Label(_(" on port "))

        ports = []
        for port in self.config.options("ports"):
            spec = self.config.get("ports", port).split(",")
            if "agwpe" in spec[1]:
                ports.append(spec[-1])

        rpt = DratsConfigWidget(config, "prefs", "msg_wl2k_rmsport")
        rpt.add_combo(ports, False)
        self.mv(_("WL2K RMS Station"), rms, lab, rpt)

        map = {
            "Network" : [srv._widget, prt._widget],
            "RMS"     : [rms._widget, rpt._widget],
            }
        disable_by_combo(wlm._widget, map)
        disable_with_toggle(vala._widget, wlm._widget)

        ssids = [""] + [str(x) for x in range(1,11)]
        val = DratsConfigWidget(config, "prefs", "msg_wl2k_ssid")
        val.add_combo(ssids, True)
        self.mv(_("My Winlink SSID"), val)

        p3s = DratsConfigWidget(config, "settings", "msg_pop3_server")
        p3s.add_bool()
        lab = gtk.Label(_("on port"))
        p3p = DratsConfigWidget(config, "settings", "msg_pop3_port")
        p3p.add_numeric(1, 65535, 1)
        self.mv(_("POP3 Server"), p3s, lab, p3p)
        disable_with_toggle(p3s._widget, p3p._widget)

        sms = DratsConfigWidget(config, "settings", "msg_smtp_server")
        sms.add_bool()
        lab = gtk.Label(_("on port"))
        smp = DratsConfigWidget(config, "settings", "msg_smtp_port")
        smp.add_numeric(1, 65535, 1)
        self.mv(_("SMTP Server"), sms, lab, smp)
        disable_with_toggle(sms._widget, smp._widget)

class DratsNetworkPanel(DratsPanel):
    pass

class DratsTCPPanel(DratsPanel):
    INITIAL_ROWS = 2

    def mv(self, title, *widgets):
        self.attach(widgets[0], 0, 2, 0, 1)
        widgets[0].show()

        if len(widgets) > 1:
            box = gtk.HBox(True, 2)

            for i in widgets[1:]:
                box.pack_start(i, 0, 0, 0)
                i.show()

            box.show()
            self.attach(box, 0, 2, 1, 2, yoptions=gtk.SHRINK)

    def but_rem(self, button, lw):
        lw.del_item(lw.get_selected())

    def prompt_for(self, fields):
        d = inputdialog.FieldDialog()
        for n, t in fields:
            d.add_field(n, gtk.Entry())

        ret = {}

        done = False
        while not done and d.run() == gtk.RESPONSE_OK:
            done = True
            for n, t in fields:
                try:
                    s = d.get_field(n).get_text()
                    if not s:
                        raise ValueError("empty")
                    ret[n] = t(s)
                except ValueError, e:
                    ed = gtk.MessageDialog(buttons=gtk.BUTTONS_OK)
                    ed.set_property("text",
                                    _("Invalid value for") + " %s: %s" % (n, e))
                    ed.run()
                    ed.destroy()
                    done = False
                    break

        d.destroy()

        if done:
            return ret
        else:
            return None

class DratsTCPOutgoingPanel(DratsTCPPanel):
    def but_add(self, button, lw):
        values = self.prompt_for([(_("Local Port"), int),
                                  (_("Remote Port"), int),
                                  (_("Station"), str)])
        if values is None:
            return

        lw.set_item(str(values[_("Local Port")]),
                    values[_("Local Port")],
                    values[_("Remote Port")],
                    values[_("Station")].upper())

    def __init__(self, config):
        DratsTCPPanel.__init__(self, config)

        outcols = [(gobject.TYPE_STRING, "ID"),
                   (gobject.TYPE_INT, _("Local")),
                   (gobject.TYPE_INT, _("Remote")),
                   (gobject.TYPE_STRING, _("Station"))]

        val = DratsListConfigWidget(config, "tcp_out")
        lw = val.add_list(outcols)
        add = gtk.Button(_("Add"), gtk.STOCK_ADD)
        add.connect("clicked", self.but_add, lw)
        rem = gtk.Button(_("Remove"), gtk.STOCK_DELETE)
        rem.connect("clicked", self.but_rem, lw)
        self.mv(_("Outgoing"), val, add, rem)

class DratsTCPIncomingPanel(DratsTCPPanel):
    def but_add(self, button, lw):
        values = self.prompt_for([(_("Port"), int),
                                  (_("Host"), str)])
        if values is None:
            return

        lw.set_item(str(values[_("Port")]),
                    values[_("Port")],
                    values[_("Host")].upper())

    def __init__(self, config):
        DratsTCPPanel.__init__(self, config)

        incols = [(gobject.TYPE_STRING, "ID"),
                  (gobject.TYPE_INT, _("Port")),
                  (gobject.TYPE_STRING, _("Host"))]

        val = DratsListConfigWidget(config, "tcp_in")
        lw = val.add_list(incols)
        add = gtk.Button(_("Add"), gtk.STOCK_ADD)
        add.connect("clicked", self.but_add, lw)
        rem = gtk.Button(_("Remove"), gtk.STOCK_DELETE)
        rem.connect("clicked", self.but_rem, lw)
        self.mv(_("Incoming"), val, add, rem)

class DratsOutEmailPanel(DratsPanel):
    def __init__(self, config):
        DratsPanel.__init__(self, config)

        gw = DratsConfigWidget(config, "settings", "smtp_dogw")
        gw.add_bool()
        self.mv(_("SMTP Gateway"), gw)

        val = DratsConfigWidget(config, "settings", "smtp_server")
        val.add_text()
        self.mv(_("SMTP Server"), val)
        disable_with_toggle(gw._widget, val._widget)

        port = DratsConfigWidget(config, "settings", "smtp_port")
        port.add_numeric(1, 65536, 1)
        mode = DratsConfigWidget(config, "settings", "smtp_tls")
        mode.add_bool("TLS")
        self.mv(_("Port and Mode"), port, mode)
        disable_with_toggle(gw._widget, port._widget)
        disable_with_toggle(gw._widget, mode._widget)

        val = DratsConfigWidget(config, "settings", "smtp_replyto")
        val.add_text()
        self.mv(_("Source Address"), val)
        disable_with_toggle(gw._widget, val._widget)

        val = DratsConfigWidget(config, "settings", "smtp_username")
        val.add_text()
        self.mv(_("SMTP Username"), val)
        disable_with_toggle(gw._widget, val._widget)

        val = DratsConfigWidget(config, "settings", "smtp_password")
        val.add_pass()
        self.mv(_("SMTP Password"), val)
        disable_with_toggle(gw._widget, val._widget)


class DratsInEmailPanel(DratsPanel):
    INITIAL_ROWS = 2

    def mv(self, title, *widgets):
        self.attach(widgets[0], 0, 2, 0, 1)
        widgets[0].show()

        if len(widgets) > 1:
            box = gtk.HBox(True, 2)

            for i in widgets[1:]:
                box.pack_start(i, 0, 0, 0)
                i.show()

            box.show()
            self.attach(box, 0, 2, 1, 2, yoptions=gtk.SHRINK)

    def but_rem(self, button, lw):
        lw.del_item(lw.get_selected())

    def prompt_for_acct(self, fields):
        dlg = inputdialog.FieldDialog()
        for n, t, d in fields:
            if n in self.choices.keys():
                w = miscwidgets.make_choice(self.choices[n], False, d)
            elif n == _("Password"):
                w = gtk.Entry()
                w.set_visibility(False)
                w.set_text(str(d))
            elif t == bool:
                w = gtk.CheckButton(_("Enabled"))
                w.set_active(d)
            else:
                w = gtk.Entry()
                w.set_text(str(d))
            dlg.add_field(n, w)

        ret = {}

        done = False
        while not done and dlg.run() == gtk.RESPONSE_OK:
            done = True
            for n, t, d in fields:
                try:
                    if n in self.choices.keys():
                        v = dlg.get_field(n).get_active_text()
                    elif t == bool:
                        v = dlg.get_field(n).get_active()
                    else:
                        v = dlg.get_field(n).get_text()
                        if not v:
                            raise ValueError("empty")
                    ret[n] = t(v)
                except ValueError, e:
                    ed = gtk.MessageDialog(buttons=gtk.BUTTONS_OK)
                    ed.set_property("text",
                                    _("Invalid value for") + " %s: %s" % (n, e))
                    ed.run()
                    ed.destroy()
                    done = False
                    break

        dlg.destroy()
        if done:
            return ret
        else:
            return None

    def but_add(self, button, lw):
        fields = [(_("Server"), str, ""),
                  (_("Username"), str, ""),
                  (_("Password"), str, ""),
                  (_("Poll Interval"), int, 5),
                  (_("Use SSL"), bool, False),
                  (_("Port"), int, 110),
                  (_("Action"), str, "Form"),
                  (_("Enabled"), bool, True),
                  ]
        ret = self.prompt_for_acct(fields)
        if ret:
            id ="%s@%s" % (ret[_("Server")], ret[_("Username")])
            lw.set_item(id,
                        ret[_("Server")],
                        ret[_("Username")],
                        ret[_("Password")],
                        ret[_("Poll Interval")],
                        ret[_("Use SSL")],
                        ret[_("Port")],
                        ret[_("Action")],
                        ret[_("Enabled")])

    def but_edit(self, button, lw):
        vals = lw.get_item(lw.get_selected())
        fields = [(_("Server"), str, vals[1]),
                  (_("Username"), str, vals[2]),
                  (_("Password"), str, vals[3]),
                  (_("Poll Interval"), int, vals[4]),
                  (_("Use SSL"), bool, vals[5]),
                  (_("Port"), int, vals[6]),
                  (_("Action"), str, vals[7]),
                  (_("Enabled"), bool, vals[8]),
                  ]
        id ="%s@%s" % (vals[1], vals[2])
        ret = self.prompt_for_acct(fields)
        if ret:
            lw.del_item(id)
            id ="%s@%s" % (ret[_("Server")], ret[_("Username")])
            lw.set_item(id,
                        ret[_("Server")],
                        ret[_("Username")],
                        ret[_("Password")],
                        ret[_("Poll Interval")],
                        ret[_("Use SSL")],
                        ret[_("Port")],
                        ret[_("Action")],
                        ret[_("Enabled")])

    def convert_018_values(self, config, section):
        options = config.options(section)
        for opt in options:
            val = config.get(section, opt)
            if len(val.split(",")) < 7:
                val += ",Form"
                config.set(section, opt, val)
                print("Config    : 7-8 Converted %s/%s" % (section, opt))
            if len(val.split(",")) < 8:
                val += ",True"
                config.set(section, opt, val)
                print("Config    : 8-9 Converted %s/%s" % (section, opt))

    def __init__(self, config):
        DratsPanel.__init__(self, config)

        cols = [(gobject.TYPE_STRING, "ID"),
                (gobject.TYPE_STRING, _("Server")),
                (gobject.TYPE_STRING, _("Username")),
                (gobject.TYPE_STRING, _("Password")),
                (gobject.TYPE_INT, _("Poll Interval")),
                (gobject.TYPE_BOOLEAN, _("Use SSL")),
                (gobject.TYPE_INT, _("Port")),
                (gobject.TYPE_STRING, _("Action")),
                (gobject.TYPE_BOOLEAN, _("Enabled"))
                ]

        self.choices = {
            _("Action") : [_("Form"), _("Chat")],
            }

        # Remove after 0.1.9
        self.convert_018_values(config, "incoming_email")

        val = DratsListConfigWidget(config, "incoming_email")

        def make_key(vals):
            return "%s@%s" % (vals[0], vals[1])

        lw = val.add_list(cols, make_key)
        lw.set_password(2);
        add = gtk.Button(_("Add"), gtk.STOCK_ADD)
        add.connect("clicked", self.but_add, lw)
        edit = gtk.Button(_("Edit"), gtk.STOCK_EDIT)
        edit.connect("clicked", self.but_edit, lw)
        rem = gtk.Button(_("Remove"), gtk.STOCK_DELETE)
        rem.connect("clicked", self.but_rem, lw)

        lw.set_sort_column(1)

        self.mv(_("Incoming Accounts"), val, add, edit, rem)

class DratsEmailAccessPanel(DratsPanel):
    INITIAL_ROWS = 2

    def mv(self, title, *widgets):
        self.attach(widgets[0], 0, 2, 0, 1)
        widgets[0].show()

        if len(widgets) > 1:
            box = gtk.HBox(True, 2)

            for i in widgets[1:]:
                box.pack_start(i, 0, 0, 0)
                i.show()

            box.show()
            self.attach(box, 0, 2, 1, 2, yoptions=gtk.SHRINK)

    def but_rem(self, button, lw):
        lw.del_item(lw.get_selected())

    def prompt_for_entry(self, fields):
        dlg = inputdialog.FieldDialog()
        for n, t, d in fields:
            if n in self.choices.keys():
                w = miscwidgets.make_choice(self.choices[n], False, d)
            else:
                w = gtk.Entry()
                w.set_text(str(d))
            dlg.add_field(n, w)

        ret = {}

        done = False
        while not done and dlg.run() == gtk.RESPONSE_OK:
            done = True
            for n, t, d in fields:
                try:
                    if n in self.choices.keys():
                        v = dlg.get_field(n).get_active_text()
                    else:
                        v = dlg.get_field(n).get_text()

                    if n == _("Callsign"):
                        if not v:
                            raise ValueError("empty")
                        else:
                            v = v.upper()
                    ret[n] = t(v)
                except ValueError, e:
                    ed = gtk.MessageDialog(buttons=gtk.BUTTONS_OK)
                    ed.set_property("text",
                                    _("Invalid value for") + "%s: %s" % (n, e))
                    ed.run()
                    ed.destroy()
                    done = False
                    break

        dlg.destroy()
        if done:
            return ret
        else:
            return None

    def but_add(self, button, lw):
        fields = [(_("Callsign"), str, ""),
                  (_("Access"), str, _("Both")),
                  (_("Email Filter"), str, "")]
        ret = self.prompt_for_entry(fields)
        if ret:
            id = "%s/%i" % (ret[_("Callsign")],
                            random.randint(1, 1000))
            lw.set_item(id,
                        ret[_("Callsign")],
                        ret[_("Access")],
                        ret[_("Email Filter")])

    def but_edit(self, button, lw):
        vals = lw.get_item(lw.get_selected())
        if not vals:
            return
        fields = [(_("Callsign"), str, vals[1]),
                  (_("Access"), str, vals[2]),
                  (_("Email Filter"), str, vals[3])]
        id = vals[0]
        ret = self.prompt_for_entry(fields)
        if ret:
            lw.del_item(id)
            lw.set_item(id,
                        ret[_("Callsign")],
                        ret[_("Access")],
                        ret[_("Email Filter")])

    def __init__(self, config):
        DratsPanel.__init__(self, config)

        cols = [(gobject.TYPE_STRING, "ID"),
                (gobject.TYPE_STRING, _("Callsign")),
                (gobject.TYPE_STRING, _("Access")),
                (gobject.TYPE_STRING, _("Email Filter"))]

        self.choices = {
            _("Access") : [_("None"), _("Both"), _("Incoming"), _("Outgoing")],
            }

        val = DratsListConfigWidget(config, "email_access")

        def make_key(vals):
            return "%s/%i" % (vals[0], random.randint(0, 1000))

        lw = val.add_list(cols, make_key)
        add = gtk.Button(_("Add"), gtk.STOCK_ADD)
        add.connect("clicked", self.but_add, lw)
        edit = gtk.Button(_("Edit"), gtk.STOCK_EDIT)
        edit.connect("clicked", self.but_edit, lw)
        rem = gtk.Button(_("Remove"), gtk.STOCK_DELETE)
        rem.connect("clicked", self.but_rem, lw)

        lw.set_sort_column(1)

        self.mv(_("Email Access"), val, add, edit, rem)

class DratsConfigUI(gtk.Dialog):

    def mouse_event(self, view, event):
        x, y = event.get_coords()
        path = view.get_path_at_pos(int(x), int(y))
        if path:
            view.set_cursor_on_cell(path[0])

        try:
            (store, iter) = view.get_selection().get_selected()
            selected, = store.get(iter, 0)
        except Exception, e:
            print("Config    : Unable to find selected: %s" % e)
            return None

        for v in self.panels.values():
            v.hide()
        self.panels[selected].show()

    def move_cursor(self, view, step, count):
        try:
            (store, iter) = view.get_selection().get_selected()
            selected, = store.get(iter, 0)
        except Exception, e:
            print("Config    : Unable to find selected: %s" % e)
            return None

        for v in self.panels.values():
            v.hide()
        self.panels[selected].show()

    def build_ui(self):
        hbox = gtk.HBox(False, 2)

        self.__store = gtk.TreeStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
        self.__tree = gtk.TreeView(self.__store)

        hbox.pack_start(self.__tree, 0, 0, 0)
        self.__tree.set_size_request(150, -1)
        self.__tree.set_headers_visible(False)
        rend = gtk.CellRendererText()
        col = gtk.TreeViewColumn(None, rend, text=1)
        self.__tree.append_column(col)
        self.__tree.show()
        self.__tree.connect("button_press_event", self.mouse_event)
        self.__tree.connect_after("move-cursor", self.move_cursor)

        def add_panel(c, s, l, par, *args):
            p = c(self.config, *args)
            p.show()
            sw = gtk.ScrolledWindow()
            sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
            sw.add_with_viewport(p)
            hbox.pack_start(sw, 1, 1, 1)

            self.panels[s] = sw

            for val in p.vals:
                self.tips.set_tip(val,
                                  config_tips.get_tip(val.vsec, val.vname))

            return self.__store.append(par, row=(s, l))

        prefs = add_panel(DratsPrefsPanel, "prefs", _("Preferences"), None)
        add_panel(DratsPathsPanel, "paths", _("Paths"), prefs, self)
        add_panel(DratsMapPanel, "maps", _("Maps"), prefs, self)
        add_panel(DratsGPSPanel, "gps", _("GPS config"), prefs, self)
        add_panel(DratsGPSExportPanel, "gpsexport", _("Export GPS messages"), prefs, self)
        add_panel(DratsAppearancePanel, "appearance", _("Appearance"), prefs)
        add_panel(DratsChatPanel, "chat", _("Chat"), prefs)
        add_panel(DratsSoundPanel, "sounds", _("Sounds"), prefs)

        add_panel(DratsMessagePanel, "messages", _("Messages"), None)

        radio = add_panel(DratsRadioPanel, "radio", _("Radio"), None)
        add_panel(DratsTransfersPanel, "transfers", _("Transfers"), radio)

        network = add_panel(DratsNetworkPanel, "network", _("Network"), None)
        add_panel(DratsTCPIncomingPanel, "tcpin", _("TCP Gateway"), network)
        add_panel(DratsTCPOutgoingPanel, "tcpout", _("TCP Forwarding"), network)
        add_panel(DratsOutEmailPanel, "smtp", _("Outgoing Email"), network)
        add_panel(DratsInEmailPanel, "email", _("Email Accounts"), network)
        add_panel(DratsEmailAccessPanel, "email_ac", _("Email Access"), network)

        self.panels["prefs"].show()

        hbox.show()
        self.vbox.pack_start(hbox, 1, 1, 1)

        self.__tree.expand_all()

    def save(self):
        for widget in self.config.widgets:
            widget.save()

    def __init__(self, config, parent=None):
        gtk.Dialog.__init__(self,
                            title=_("Config"),
                            buttons=(gtk.STOCK_SAVE, gtk.RESPONSE_OK,
                                     gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL),
                            parent=parent)
        self.config = config
        self.panels = {}
        self.tips = gtk.Tooltips()
        self.build_ui()
        self.set_default_size(800, 400)

class DratsConfig(ConfigParser.ConfigParser):
    def set_defaults(self):
        for sec, opts in DEFAULTS.items():
            if not self.has_section(sec):
                self.add_section(sec)

            for opt, value in opts.items():
                if not self.has_option(sec, opt):
                    self.set(sec, opt, value)

    def __init__(self, mainapp, safe=False):
        ConfigParser.ConfigParser.__init__(self)

        self.platform = dplatform.get_platform()
        self.filename = self.platform.config_file("d-rats.config")
        print("Config    : FILE: %s" % self.filename)
        self.read(self.filename)
        self.widgets = []

        self.set_defaults()

        if self.get("prefs", "download_dir") == ".":
            print("Config    : ", os.path.join(dplatform.get_platform().default_dir(), "D-RATS Shared"))
            default_dir = os.path.join(dplatform.get_platform().default_dir(),
                                       "D-RATS Shared")
            if not os.path.exists(default_dir):
                print("Config    : Creating download directory: %s" % default_dir)
                os.mkdir(default_dir)
                self.set("prefs", "download_dir", default_dir)

        #create the folder structure for map
        map_dir = self.get("settings", "mapdir")
        print("Config    : mapdir=%s" % map_dir)
        
        if not os.path.exists(map_dir):
            print("Config    :  Creating map directory: %s" % map_dir)
            os.mkdir(map_dir)
        if not os.path.exists(os.path.join(map_dir, "base")):
            os.mkdir(os.path.join(map_dir, "base"))
        if not os.path.exists(os.path.join(map_dir, "cycle")):
            os.mkdir(os.path.join(map_dir, "cycle"))
        if not os.path.exists(os.path.join(map_dir, "outdoor")):
            os.mkdir(os.path.join(map_dir, "outdoor"))
        if not os.path.exists(os.path.join(map_dir, "landscape")):
            os.mkdir(os.path.join(map_dir, "landscape"))

    def show(self, parent=None):
        ui = DratsConfigUI(self, parent)
        r = ui.run()
        if r == gtk.RESPONSE_OK:
            ui.save()
            self.save()
        ui.destroy()

        return r == gtk.RESPONSE_OK

    def save(self):
        f = file(self.filename, "w")
        self.write(f)
        f.close()

    def getboolean(self, sec, key):
        try:
            return ConfigParser.ConfigParser.getboolean(self, sec, key)
        except:
            print("Config    : Failed to get boolean: %s/%s" % (sec, key))
            return False

    def getint(self, sec, key):
        return int(float(ConfigParser.ConfigParser.get(self, sec, key)))

    def form_source_dir(self):
        d = os.path.join(self.platform.config_dir(), "Form_Templates")
        if not os.path.isdir(d):
            os.mkdir(d)

        return d

    def form_store_dir(self):
        d = os.path.join(self.platform.config_dir(), "messages")
        if not os.path.isdir(d):
            os.mkdir(d)

        return d

    def ship_obj_fn(self, name):
        return os.path.join(self.platform.source_dir(), name)

    def ship_img(self, name):
        path = self.ship_obj_fn(os.path.join("images", name))
        return gtk.gdk.pixbuf_new_from_file(path)

if __name__ == "__main__":
    #mm: fn = "/home/dan/.d-rats/d-rats.config"
    fn = "d-rats.config"

    cf = ConfigParser.ConfigParser()
    cf.read(fn)
    cf.widgets = []

    c = DratsConfigUI(cf)
    if c.run() == gtk.RESPONSE_OK:
        c.save(fn)
