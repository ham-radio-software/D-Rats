#!/usr/bin/python
# pylint: disable=too-many-lines
#
# Copyright 2009 Dan Smith <dsmith@danplanet.com>
# review 2015-2020 Maurizio Andreotti  <iz2lxi@yahoo.it>
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

'''D-Rats Configuration Module'''

from __future__ import absolute_import
from __future__ import print_function

import os
import random
import logging
import six.moves.configparser # type: ignore
from six.moves import range # type: ignore

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GObject

if __name__ == "__main__":
    import gettext
    # pylint: disable=invalid-name
    lang = gettext.translation("D-RATS",
                               localedir="./locale",
                               fallback=True)
    lang.install()
    _ = lang.gettext

from . import utils
from . import miscwidgets
from . import inputdialog

from . import dplatform
# change from 0.3.3> was this commented out which causes pylint error.
from . import geocode_ui

from . import config_tips
from . import spell

# from .ui.main_common import display_error

BAUD_RATES = ["1200", "2400", "4800", "9600", "19200", "38400", "115200"]

# these settings are used to populate the config when D-Rats is executed the
# first time
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
    "callsigns" : "%s" % str([(True, "US")]),
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
    "msg_wl2k_password" : "",
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

    # Weather APIs
    "qst_owuri" : "https://api.openweathermap.org/data/2.5/",
    "qst_owappid" : "ecd42c31b76e59e83de5cb8c16f7bd95a",

    # MAPS APIs
    "mapdir" : os.path.join(dplatform.get_platform().config_dir(), "maps"),
    "maptype": "base",
    # "mapurlbase":  "http://a.tile.openstreetmap.org/",
    "mapurlbase":  "https://tile.openstreetmap.de/",
    "keyformapurlbase": "",

    "mapurlcycle": "https://tile.thunderforest.com/cycle/",
    "keyformapurlcycle": "?apikey=YOUR APIKEY REQUIRED",

    "mapurloutdoors": "https://tile.thunderforest.com/outdoors/",
    "keyformapurloutdoors": "?apikey=5a1a4a79354244a38707d83969fd88a2",

    "mapurllandscape": "https://tile.thunderforest.com/landscape/",
    "keyformapurllandscape": "?apikey=5a1a4a79354244a38707d83969fd88a2",

    # GPS
    "default_gps_comment" : "BN  *20",     # default icon for our station in
                                           # the map and gpsfixes
    "map_marker_bgcolor": "yellow",        # background color for markers in
                                           # the map window

    "warmup_length" : "16",                # changed from 8 to 16 in 0.3.6
    "warmup_timeout" : "0",                # changed from 3 to 0 in 0.3.6
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

    "msg_flush" : "30",           # changed from 60 to 30sec in 0.3.6
    "msg_forward" : "True",       # changed from False to True in 0.3.6
    "station_msg_ttl" : "600",    # changed from 3660 to 600 in 0.3.6

    "form_logo_dir" : os.path.join(dplatform.get_platform().config_dir(),
                                   "logos"),

    "mapserver_ip": "localhost",
    "mapserver_port": "5011",
    "mapserver_active": "False",
    "http_proxy" : "",

    "timestamp_positions" : "False",
    "msg_wl2k_mode" : "Network",
    "qst_size_limit" : "2048",
    "msg_pop3_server" : "False",
    "msg_pop3_port" : "9110",
    "msg_smtp_server" : "False",
    "msg_smtp_port" : "9025",
    "delete_from" : "",
    "remote_admin_passwd" : "",
    "expire_stations" : "60",
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
    "events_sort" : str(int(Gtk.SortType.DESCENDING)),
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

# these settings are used when D-Rats is opened any time
# (not just the first time) before that the config file is loaded
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

    # the "ports" setting in particular is magic in the sense that all lines
    # here are recreated any time that D-Rats starts in config file regardless
    # if the users deletes them
    "ports" : {"ports_0" : "True,net:ref.d-rats.com:9000,,False,False,RAT"},
}


class ConfigException(Exception):
    '''Generic D-Rats Configuration Exception.'''


class ConfigMessageGroupError(ConfigException):
    '''Message Group Error'''


def color_string(color):
    '''
    Convert color to string.

    :param color: Color object
    :returns: String with color
    '''
    try:
        return color.to_string()
    # pylint: disable=bare-except
    except:
        logger = logging.getLogger("Configure_color_string")
        logger.info("Bare except", exc_info=True)
        return "#%04x%04x%04x" % (color.red, color.green, color.blue)


def load_portspec(wtree, portspec, info, name):
    '''
    Load in a port specification.

    :param portspec: Port specification object
    :param info: Port information
    :param name: Port name
    '''
    namewidget = wtree.get_object("name")
    namewidget.set_text(name)
    namewidget.set_sensitive(False)

    tsel = wtree.get_object("type")
    if portspec.startswith("net:"):
        tsel.set_active(1)
        _net, host, port = portspec.split(":")
        wtree.get_object("net_host").set_text(host)
        wtree.get_object("net_port").set_value(int(port))
        wtree.get_object("net_pass").set_text(info)
    elif portspec.startswith("tnc"):
        tsel.set_active(2)
        if len(portspec.split(":")) == 3:
            _tnc, port, tncport = portspec.split(":", 2)
            path = ""
        else:
            _tnc, port, tncport, path = portspec.split(":", 3)
        wtree.get_object("tnc_port").get_child().set_text(port)
        wtree.get_object("tnc_tncport").set_value(int(tncport))
        utils.combo_select(wtree.get_object("tnc_rate"), info)
        wtree.get_object("tnc_ax25path").set_text(path.replace(";", ","))
        if portspec.startswith("tnc-ax25"):
            wtree.get_object("tnc_ax25").set_active(True)
    elif portspec.startswith("agwpe:"):
        tsel.set_active(4)
        _agw, addr, port = portspec.split(":")
        wtree.get_object("agw_addr").set_text(addr)
        wtree.get_object("agw_port").set_value(int(port))
    else:
        tsel.set_active(0)
        wtree.get_object("serial_port").get_child().set_text(portspec)
        utils.combo_select(wtree.get_object("serial_rate"), info)


# pylint: disable=too-many-locals,too-many-branches,too-many-statements
def prompt_for_port(portspec=None, info=None, pname=None):
    '''
    Prompt for port.

    :param portspec: portspec object, default None
    :param info: Port information, default None
    :param pname: Port name, default None
    :returns: portspec object or a tuple of (None, None, None)
    '''
    wtree = Gtk.Builder()
    path = os.path.join(dplatform.get_platform().source_dir(),
                        "ui/addport.glade")
    wtree.add_from_file(path)

    ports = dplatform.get_platform().list_serial_ports()

    sportsel = wtree.get_object("serial_port")
    tportsel = wtree.get_object("tnc_port")
    sportlst = sportsel.get_model()
    tportlst = tportsel.get_model()
    sportlst.clear()
    tportlst.clear()

    for port in ports:
        sportlst.append((port, ""))
        tportlst.append((port, ""))

    if ports:
        sportsel.set_active(0)
        tportsel.set_active(0)

    sratesel = wtree.get_object("serial_rate")
    tratesel = wtree.get_object("tnc_rate")
    tprotsel = wtree.get_object("tnc_ax25")
    tnc_path = wtree.get_object("tnc_ax25path")
    tprotsel.connect("toggled",
                     lambda b: tnc_path.set_sensitive(b.get_active()))

    sratesel.set_active(3)
    tratesel.set_active(3)

    netaddr = wtree.get_object("net_host")
    netport = wtree.get_object("net_port")
    netpass = wtree.get_object("net_pass")

    agwaddr = wtree.get_object("agw_addr")
    agwport = wtree.get_object("agw_port")
    agwport.set_value(8000)

    menutabs = []
    for _i in range(5):
        menutabs.append({})

    menutabs[0]['descrip'] = _("A D-STAR radio connected to a serial port")
    menutabs[1]['descrip'] = _("A network link to a ratflector instance")
    menutabs[2]['descrip'] = _("A KISS-mode TNC connected to a serial port")
    menutabs[3]['descrip'] = _("A locally-attached dongle")
    menutabs[4]['descrip'] = _("A TNC attached to an AGWPE server")

    def chg_type(tsel, tabs, desc):
        active = tsel.get_active()
        if active < 0:
            active = 0
            tsel.set_active(0)
        logger = logging.getLogger("Configure_prompt_for_port_chg_type")
        logger.info("Changed to %s", tsel.get_active_text())

        tabs.set_current_page(active)

        desc.set_markup("<span fgcolor='blue'>%s</span>" %
                        menutabs[active]['descrip'])

    name = wtree.get_object("name")
    desc = wtree.get_object("typedesc")
    ttncport = wtree.get_object("tnc_tncport")
    tabs = wtree.get_object("editors")
    tabs.set_show_tabs(False)
    tsel = wtree.get_object("type")
    tsel.set_active(0)
    tsel.connect("changed", chg_type, tabs, desc)

    if portspec:
        load_portspec(wtree, portspec, info, pname)
    elif pname is False:
        name.set_sensitive(False)

    add_port = wtree.get_object("addport")

    chg_type(tsel, tabs, desc)
    run_result = add_port.run()

    active = tsel.get_active()
    if active == 0:
        portspec = sportsel.get_active_text(), sratesel.get_active_text()
    elif active == 1:
        portspec = "net:%s:%i" % (netaddr.get_text(), netport.get_value()), \
            netpass.get_text()
    elif active == 2:
        if tprotsel.get_active():
            digi_path = tnc_path.get_text().replace(",", ";")
            portspec = "tnc-ax25:%s:%i:%s" % (tportsel.get_active_text(),
                                              ttncport.get_value(),
                                              digi_path), \
                                              tratesel.get_active_text()
        else:
            portspec = "tnc:%s:%i" % (tportsel.get_active_text(),
                                      ttncport.get_value()), \
                                      tratesel.get_active_text()
    elif active == 3:
        portspec = "dongle:", ""
    elif active == 4:
        portspec = "agwpe:%s:%i" % (agwaddr.get_text(), agwport.get_value()), ""

    portspec = (name.get_text(),) + portspec
    add_port.destroy()

    if run_result == Gtk.ResponseType.APPLY:
        return portspec
    return None, None, None


def disable_with_toggle(toggle, widget):
    '''
    Disable With Toggle.

    :param toggle: Toggle object
    :param widget: Widget to toggle
    '''
    toggle.connect("toggled",
                   lambda t, w: w.set_sensitive(t.get_active()), widget)
    widget.set_sensitive(toggle.get_active())


def disable_by_combo(combo, map_var):
    '''
    Disable By Combo.

    :param combo: combo object
    :param map_ver: Dictionary map
    '''
    # Expects a map like:
    # map = {
    #   "value1" : [el1, el2],
    #   "value2" : [el3, el4],
    # }
    def set_disables(combo, map_var):
        for i in map_var.values():
            for j in i:
                j.set_sensitive(False)
        for i in map_var[combo.get_active_text()]:
            i.set_sensitive(True)
    combo.connect("changed", set_disables, map_var)
    set_disables(combo, map_var)


class AddressLookup(Gtk.Button):
    '''
    Lookup Latitude and Longitude.

    :param caption: Caption for lookup
    :param latw: Latitude
    :param lonw: Longitude
    :param window: Window object, default=None
    '''

    def __init__(self, caption, latw, lonw, window=None):
        Gtk.Button.__init__(self, caption)
        self.logger = logging.getLogger("ConfigAddressLookup")
        self.connect("clicked", self.clicked, latw, lonw, window)

    # pylint: disable=arguments-differ
    def clicked(self, _me, latw, lonw, window):
        assistant = geocode_ui.AddressAssistant()
        if assistant.geocoders:
            assistant.set_transient_for(window)
            run_result = assistant.run()
            if run_result == Gtk.ResponseType.OK:
                latw.latlon.set_text("%.5f" % assistant.lat)
                lonw.latlon.set_text("%.5f" % assistant.lon)
            return


# pylint: disable=too-many-instance-attributes
class DratsConfigWidget(Gtk.Box):
    '''
    D-rats configuration Widget.

    :param config: DratsConfig object
    :param sec: Config file section
    :param name: Name of configuration
    :param have_revert: Flag if reverting is allowed, default False
    '''

    def __init__(self, config, sec, name, have_revert=False):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL,
                         spacing=2)

        self.do_not_expand = False

        self.config = config
        self.vsec = sec
        self.vname = name
        self._widget = None
        self._in_init = True
        self.latlon = None

        self.config.widgets.append(self)
        self.logger = logging.getLogger("DratsConfigWidget")

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
            # rb = Gtk.Button(None, Gtk.STOCK_REVERT_TO_SAVED)
            rbutton = Gtk.Button.new_with_label(_('Revert'))
            rbutton.connect("clicked", self._revert)
            rbutton.show()
            self.pack_end(rbutton, 0, 0, 0)

    def _revert(self, _button=None):
        try:
            self.value = DEFAULTS[self.vsec][self.vname]
        except KeyError:
            self.logger.info("DEFAULTS has no %s/%s", self.vsec, self.vname)
            self.value = ""

        # Nothing else to do if called from __init_()
        if self._in_init:
            return

        if not self._widget:
            self.logger.info("AAACK: No _widget in revert for %s/%s",
                             self.vsec, self.vname)
            return

        if isinstance(self._widget, Gtk.Entry):
            self._widget.set_text(str(self.value))
        elif isinstance(self._widget, Gtk.SpinButton):
            self._widget.set_value(float(self.value))
        elif isinstance(self._widget, Gtk.CheckButton):
            self._widget.set_active(self.value.upper() == "TRUE")
        elif isinstance(self._widget, miscwidgets.FilenameBox):
            self._widget.set_filename(self.value)
        else:
            self.logger.info("AAACK: I don't know how to do a %s",
                             self._widget.__class__)

    def save(self):
        '''Save Configuration.'''
        # printlog("Config",
        #          "    : "Saving %s/%s: %s" %
        #          (self.vsec, self.vname, self.value))
        self.config.set(self.vsec, self.vname, self.value)

    def set_value(self, value):
        '''
        Set value.

        :param value: Value to set
        '''

    def add_text(self, limit=0, hint=None):
        '''
        Add Text Entry Box.

        :param limit: limit value, default 0
        :param hint: Text hint, default None
        '''
        def changed(entry):
            if entry.get_text() == hint:
                self.value = ""
            else:
                self.value = entry.get_text()

        entry = Gtk.Entry()
        entry.set_max_length(limit)
        entry.connect("changed", changed)
        entry.set_text(self.value)
        entry.set_size_request(50, -1)
        entry.show()
        self._widget = entry

        if hint:
            utils.set_entry_hint(entry, hint, bool(self.value))

        self.pack_start(entry, 1, 1, 1)

    def add_upper_text(self, limit=0):
        '''
        Add upper case text entry.

        :param limit: Limit of text, default 0
        '''
        def changed(entry):
            self.value = entry.get_text().upper()

        entry = Gtk.Entry()
        entry.set_max_length(limit)
        entry.connect("changed", changed)
        entry.set_text(self.value)
        entry.set_size_request(50, -1)
        entry.show()
        self._widget = entry

        self.pack_start(entry, 1, 1, 1)

    def add_pass(self, limit=0):
        '''
        Add a password entry.

        :param limit: Limit default 0
        '''
        def changed(entry):
            self.value = entry.get_text()

        entry = Gtk.Entry()
        entry.set_max_length(limit)
        entry.connect("changed", changed)
        entry.set_text(self.value)
        entry.set_visibility(False)
        entry.set_size_request(50, -1)
        entry.show()
        self._widget = entry

        self.pack_start(entry, 1, 1, 1)

    # pylint: disable=dangerous-default-value
    def add_combo(self, choices=[], editable=False, size=80):
        '''
        Add a combo box.

        :param choices: List of choices, default []
        :pram editable: Flag for editable, defult False
        :param size: Size of combo box, default 80
        '''
        def changed(box):
            self.value = box.get_active_text()

        if self.value not in choices:
            choices.append(self.value)

        widget = miscwidgets.make_choice(choices, editable, self.value)
        widget.connect("changed", changed)
        widget.set_size_request(size, -1)
        widget.show()
        self._widget = widget

        self.pack_start(widget, 1, 1, 1)

    def add_bool(self, label=None):
        '''
        Add boolean button.

        :param label: Label for button, default None
        '''
        if label is None:
            label = _("Enabled")

        def toggled(but, confwidget):
            confwidget.value = str(but.get_active())

        button = Gtk.CheckButton.new_with_label(label)
        button.connect("toggled", toggled, self)
        button.set_active(self.value == "True")
        button.show()
        self._widget = button

        self.do_not_expand = True

        self.pack_start(button, 1, 1, 1)

    def add_coords(self):
        '''Add coordinates.'''
        def changed(entry, confwidget):
            try:
                confwidget.value = "%3.6f" % entry.value()
            # pylint: disable=broad-except
            except Exception:
                self.logger.info("Invalid Coords", exc_info=True)
                confwidget.value = "0"

        entry = miscwidgets.LatLonEntry()
        entry.connect("changed", changed, self)
        self.logger.info("Setting LatLon value: %s", self.value)
        entry.set_text(self.value)
        self.logger.info("LatLon text: %s", entry.get_text())
        entry.show()

        # Dirty ugly hack!
        self.latlon = entry

        self.pack_start(entry, 1, 1, 1)

    def add_numeric(self, min_val, max_val, increment, digits=0):
        '''
        Add numeric.

        :param min_val: Minimum value
        :param max_val: Maximum value
        :param increment: Increment for adjustments
        :param digits: Number of digits, default 0
        '''

        def value_changed(srcbox):
            self.value = "%f" % srcbox.get_value()

        adj = Gtk.Adjustment.new(float(self.value), min_val, max_val,
                                 increment, increment, 0)
        button = Gtk.SpinButton()
        button.set_adjustment(adj)
        button.set_digits(digits)
        button.connect("value-changed", value_changed)
        button.show()
        self._widget = button

        self.pack_start(button, 1, 1, 1)

    def add_color(self):
        '''Add Color.'''
        def color_set(color_button):
            # self.value = color_string(color_button.get_color())
            rgba = color_button.get_rgba()
            self.value = rgba.to_string()

        button = Gtk.ColorButton()
        #button.set_color(Gdk.color_parse(self.value))
        if self.value:
            rgba = Gdk.RGBA()
            if rgba.parse(self.value):
                button.set_rgba(rgba)
        button.connect("color-set", color_set)
        button.show()

        self.pack_start(button, 1, 1, 1)

    def add_font(self):
        '''Add font.'''
        def font_set(fontbutton):
            self.value = fontbutton.get_font()

        button = Gtk.FontButton()
        if self.value:
            button.set_font(self.value)
        button.connect("font-set", font_set)
        button.show()

        self.pack_start(button, 1, 1, 1)

    def add_path(self):
        '''Add path.'''
        def filename_changed(box):
            self.value = box.get_filename()

        fname_box = miscwidgets.FilenameBox(find_dir=True)
        fname_box.set_filename(self.value)
        fname_box.connect("filename-changed", filename_changed)
        fname_box.show()
        self._widget = fname_box

        self.pack_start(fname_box, 1, 1, 1)

    def add_sound(self):
        '''Add Sound.'''
        def filename_changed(box):
            self.value = box.get_filename()

        def test_sound(_button):
            self.logger.info("Testing playback of %s", self.value)
            platform_info = dplatform.get_platform()
            platform_info.play_sound(self.value)

        fname_box = miscwidgets.FilenameBox(find_dir=False)
        fname_box.set_filename(self.value)
        fname_box.connect("filename-changed", filename_changed)
        fname_box.show()

        button = Gtk.Button.new_with_label(_("Test"))
        button.connect("clicked", test_sound)
        button.show()

        box = Gtk.Box.new(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        box.show()
        box.pack_start(fname_box, 1, 1, 1)
        box.pack_start(button, 0, 0, 0)

        self.pack_start(box, 1, 1, 1)


class DratsListConfigWidget(DratsConfigWidget):
    '''
    D-Rats List Configuration Widget.

    :param config: DratsConfig object
    :param section: Section of configuration file
    '''

    def __init__(self, config, section):
        try:
            DratsConfigWidget.__init__(self, config, section, None)
        except six.moves.configparser.NoOptionError:
            pass
        self.listw = None
        self.logger = logging.getLogger("DratsListConfigWidget")

    # pylint: disable=no-self-use
    def convert_types(self, coltypes, values):
        '''
        Convert Types.

        :param coltypes: List of column types
        :param values: list of values to convert
        :returns: list of converted value
        '''
        newvals = []

        i = 0
        while i < len(values):
            gtype, label = coltypes[i]
            value = values[i]

            try:
                if gtype == GObject.TYPE_INT:
                    value = int(value)
                elif gtype == GObject.TYPE_FLOAT:
                    value = float(value)
                elif gtype == GObject.TYPE_BOOLEAN:
                    # pylint: disable=eval-used
                    value = eval(value)
            except ValueError:
                self.logger.info("Failed to convert %s for %s",
                                 value, label, exc_info=True)
                return []

            i += 1
            newvals.append(value)

        return newvals

    def set_sort_column(self, col):
        '''
        Set Sort Column.

        :param col: Column to sort
        '''
        self.listw.set_sort_column(col)

    def add_list(self, cols, make_key=None):
        '''
        Add to list.

        :param cols: list of columns
        :param make_key: key for columns, default None
        '''
        def item_set(_listwidget, _key):
            pass

        list_widget = miscwidgets.KeyedListWidget(cols)

        # pylint: disable=unused-argument
        def dummy(*args):
            return

        list_widget.connect("item-toggled", dummy)

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
                list_widget.set_item(key, *tuple(vals))
            # pylint: disable=broad-except
            except Exception:
                self.logger.info("Failed to set item '%s'",
                                 str(vals), exc_info=True)

        list_widget.connect("item-set", item_set)
        list_widget.show()

        self.pack_start(list_widget, 1, 1, 1)

        self.listw = list_widget

        return list_widget

    def save(self):
        '''Save.'''
        for opt in self.config.options(self.vsec):
            self.config.remove_option(self.vsec, opt)

        count = 0

        for key in self.listw.get_keys():
            vals = self.listw.get_item(key)
            vals = [str(x) for x in vals]
            value = ",".join(vals[1:])
            label = "%s_%i" % (self.vsec, count)
            self.logger.info("Setting %s: %s", label, value)
            self.config.set(self.vsec, label, value)
            count += 1


class DratsPanel(Gtk.Grid):
    '''
    D-Rats Configuration Panel.

    :param config: DratsConfig object
    '''

    def __init__(self, config):
        Gtk.Grid.__init__(self)
        self.config = config
        self.vals = []

        self.row = 0

        self.logger = logging.getLogger("DratsPanel")

    def make_view(self, title, *args):
        '''
        Make View.

        set information for a widget.
        :param title: Title for widget
        :param *args: Optional arguments
        '''

        hbox = Gtk.Box.new(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)

        label = Gtk.Label.new(title)
        label.show()

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
        self.attach(label, 0, self.row, 1, 1)
        self.attach_next_to(hbox, label, Gtk.PositionType.RIGHT, 1, 1)

        self.row += 1

    def message_group(self, title, *args):
        '''
        Message Group.

        :param title: title of message group
        :param *args: Optional arguments
        '''
        if len(args) % 2:
            raise ConfigMessageGroupError("Need label,widget pairs")

        grid = Gtk.Grid.new()
        row = 0

        for i in range(0, len(args), 2):
            label = Gtk.Label.new(args[i])
            widget = args[i+1]

            label.show()
            widget.show()
            grid.attach(label, 0, row, 2, 1)
            grid.attach_next_to(widget, label, Gtk.PositionType.RIGHT,
                                1, 1)
            row += 1

        grid.show()

        frame = Gtk.Frame.new(title)
        frame.show()
        frame.add(grid)

        self.attach(frame, 1, self.row, 1, 1)
        self.row += 1


class DratsPrefsPanel(DratsPanel):
    '''
    D-Rats Preferences Panel.

    :param config: DratsConfig object
    '''

    def __init__(self, config):
        DratsPanel.__init__(self, config)
        self.logger = logging.getLogger("DratsPrefConfig")

        val = DratsConfigWidget(config, "user", "callsign")
        val.add_upper_text(8)
        self.make_view(_("Callsign"), val)

        val = DratsConfigWidget(config, "user", "name")
        val.add_text()
        self.make_view(_("Name"), val)

        val1 = DratsConfigWidget(config, "prefs", "dosignon")
        val1.add_bool()
        val2 = DratsConfigWidget(config, "prefs", "signon")
        val2.add_text()
        self.make_view(_("Sign-on Message"), val1, val2)
        # pylint: disable=protected-access
        disable_with_toggle(val1._widget, val2._widget)

        val1 = DratsConfigWidget(config, "prefs", "dosignoff")
        val1.add_bool()
        val2 = DratsConfigWidget(config, "prefs", "signoff")
        val2.add_text()
        self.make_view(_("Sign-off Message"), val1, val2)
        # pylint: disable=protected-access
        disable_with_toggle(val1._widget, val2._widget)

        val = DratsConfigWidget(config, "user", "units")
        val.add_combo([_("Imperial"), _("Metric")])
        self.make_view(_("Units"), val)

        val = DratsConfigWidget(config, "prefs", "useutc")
        val.add_bool()
        self.make_view(_("Show time in UTC"), val)

        val = DratsConfigWidget(config, "settings", "ping_info")
        val.add_text(hint=_("Version and OS Info"))
        self.make_view(_("Ping reply"), val)

        val = DratsConfigWidget(config, "prefs", "language")
        val.add_combo(["English", "German", "Italiano", "Dutch"])
        self.make_view(_("Language"), val)

        mval = DratsConfigWidget(config, "prefs", "blink_messages")
        mval.add_bool()

        cval = DratsConfigWidget(config, "prefs", "blink_chat")
        cval.add_bool()

        fval = DratsConfigWidget(config, "prefs", "blink_files")
        fval.add_bool()

        event_val = DratsConfigWidget(config, "prefs", "blink_event")
        event_val.add_bool()

        self.message_group(_("Blink tray on"),
                           _("Incoming Messages"), mval,
                           _("New Chat Messages"), cval,
                           _("Incoming Files"), fval,
                           _("Received Events"), event_val)


class DratsPathsPanel(DratsPanel):
    '''
    D-Rats Paths Panel.

    :param config: DratsConfig object
    '''

    def __init__(self, config, _window):
        DratsPanel.__init__(self, config)
        self.logger = logging.getLogger("DratsPathsPanel")

        val = DratsConfigWidget(config, "prefs", "download_dir", True)
        val.add_path()
        self.make_view(_("File Transfer Path"), val)

        val = DratsConfigWidget(config, "settings", "mapdir", True)
        val.add_path()
        self.make_view(_("Base Map Storage Path"), val)

        val = DratsConfigWidget(config, "settings", "form_logo_dir", True)
        val.add_path()
        self.make_view(_("Form Logo Path"), val)


class DratsMapPanel(DratsPanel):
    '''
    D-Rats MAP Panel.

    :param config: DratsConfig object
    :param _window: Unused
    '''

    def __init__(self, config, _window):
        DratsPanel.__init__(self, config)
        self.logger = logging.getLogger("DratsMapPanel")

        #asking which map to use
        val = DratsConfigWidget(config, "settings", "maptype")
        val.add_combo(["base", "cycle", "outdoors", "landscape"])
        self.make_view(_("Map to use"), val)

        val = DratsConfigWidget(config, "settings", "mapurlbase", True)
        val.add_text()
        self.make_view(_("BaseMap server url"), val)

        #opencycle
        val = DratsConfigWidget(config, "settings", "mapurlcycle", True)
        val.add_text()
        self.make_view(_("OpenCycleMap server url"), val)

        val = DratsConfigWidget(config, "settings", "keyformapurlcycle", True)
        val.add_text()
        self.make_view(_("Key string to append to CycleMap url"), val)

        #landscape
        val = DratsConfigWidget(config, "settings", "mapurllandscape", True)
        val.add_text()
        self.make_view(_("Landscape server url"), val)

        val = DratsConfigWidget(config, "settings", "keyformapurllandscape", True)
        val.add_text()
        self.make_view(_("Key string to append to landscape url"), val)

        #outdoors
        val = DratsConfigWidget(config, "settings", "mapurloutdoors", True)
        val.add_text()
        self.make_view(_("Outdoors server url"), val)

        val = DratsConfigWidget(config, "settings", "keyformapurloutdoors", True)
        val.add_text()
        self.make_view(_("Key string to append to outdoors url"), val)

        val = DratsConfigWidget(config, "settings", "map_tile_ttl")
        val.add_numeric(0, 9999999999999, 1)
        self.make_view(_("Freshen map after"), val, Gtk.Label.new(_("hours")))

        val = DratsConfigWidget(config, "settings", "timestamp_positions")
        val.add_bool()
        self.make_view(_("Report position timestamps on map"), val)


class DratsGPSPanel(DratsPanel):
    '''
    D-rats GPS Panel.

    :param config: DratsConfig object
    :param _window: Unused
    '''

    def __init__(self, config, _window):
        DratsPanel.__init__(self, config)
        self.logger = logging.getLogger("DratsGPSPanel")

        lat = DratsConfigWidget(config, "user", "latitude")
        lat.add_coords()
        self.make_view(_("Latitude"), lat)

        lon = DratsConfigWidget(config, "user", "longitude")
        lon.add_coords()
        self.make_view(_("Longitude"), lon)

        #geo = AddressLookup(_("Lookup"), lat, lon, window)
        #self.make_view(_("Lookup by address"), geo)

        alt = DratsConfigWidget(config, "user", "altitude")
        alt.add_numeric(0, 29028, 1)
        self.make_view(_("Altitude"), alt)

        ports = dplatform.get_platform().list_serial_ports()

        val = DratsConfigWidget(config, "settings", "gpsenabled")
        val.add_bool()
        self.make_view(_("Use External GPS"), val)

        port = DratsConfigWidget(config, "settings", "gpsport")
        port.add_combo(ports, True, 120)
        rate = DratsConfigWidget(config, "settings", "gpsportspeed")
        rate.add_combo(BAUD_RATES, False)
        self.make_view(_("External GPS"), port, rate)
        # pylint: disable=protected-access
        disable_with_toggle(val._widget, port._widget)
        # pylint: disable=protected-access
        disable_with_toggle(val._widget, rate._widget)

        val1 = DratsConfigWidget(config, "settings", "aprssymtab")
        val1.add_text(1)
        val2 = DratsConfigWidget(config, "settings", "aprssymbol")
        val2.add_text(1)
        self.make_view(_("GPS-A Symbol"),
                       Gtk.Label.new(_("Table:")), val1,
                       Gtk.Label.new(_("Symbol:")), val2)

        def gps_comment_from_dprs(_button, val):
            from . import qst
            dprs = qst.do_dprs_calculator(config.get("settings",
                                                     "default_gps_comment"))
            self.logger.info("Setting GPS comment to DPRS: %s ", dprs)
            if dprs is not None:
                config.set("settings", "default_gps_comment", dprs)
                # pylint: disable=protected-access
                val._widget.set_text(dprs)

        val = DratsConfigWidget(config, "settings", "default_gps_comment")
        val.add_text(20)
        but = Gtk.Button.new_with_label(_("DPRS"))
        but.connect("clicked", gps_comment_from_dprs, val)
        self.make_view(_("Default GPS comment"), val, but)


class DratsGPSExportPanel(DratsPanel):
    '''
    D-Rats GPS Export Panel.

    :param config: DratsConfig object
    :param _window: unused
    '''

    def __init__(self, config, _window):
        DratsPanel.__init__(self, config)
        self.logger = logging.getLogger("DratsGPSExportConfig")
        val = DratsConfigWidget(config, "settings", "mapserver_active", True)
        val.add_bool()
        self.make_view(_("Check to enable export GPS messages as JSON string"),
                       val)

        val = DratsConfigWidget(config, "settings", "mapserver_ip")
        val.add_text(12)
        self.make_view(_("IP address"), val)

        val = DratsConfigWidget(config, "settings", "mapserver_port")
        val.add_text(6)
        self.make_view(_("IP port"), val)


class DratsAppearancePanel(DratsPanel):
    '''
    D-Rats Appearance Panel.

    :param config: DratsConfig object
    '''

    def __init__(self, config):
        DratsPanel.__init__(self, config)
        self.logger = logging.getLogger("DratsAppearancePanel")

        val = DratsConfigWidget(config, "prefs", "noticere")
        val.add_text()
        self.make_view(_("Notice RegEx"), val)

        val = DratsConfigWidget(config, "prefs", "ignorere")
        val.add_text()
        self.make_view(_("Ignore RegEx"), val)

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
            self.make_view(_("%s Color" % i), val)

        sizes = [_("Default"), _("Large"), _("Small")]
        val = DratsConfigWidget(config, "prefs", "toolbar_button_size")
        val.add_combo(sizes, False)
        self.make_view(_("Toolbar buttons"), val)

        val = DratsConfigWidget(config, "prefs", "check_spelling")
        val.add_bool()
        self.make_view(_("Check spelling"), val)
        sp_val = spell.get_spell()
        # pylint: disable=protected-access
        val._widget.set_sensitive(sp_val.test())

        val = DratsConfigWidget(config, "prefs", "confirm_exit")
        val.add_bool()
        self.make_view(_("Confirm exit"), val)

        val = DratsConfigWidget(config, "settings", "expire_stations")
        val.add_numeric(0, 9999, 1)
        cap = Gtk.Label.new(_("minutes"))
        self.make_view(_("Expire stations after"), val, cap)


class DratsChatPanel(DratsPanel):
    '''
    D-Rats Chat Panel.

    :param config: DratsConfig object
    '''

    def __init__(self, config):
        DratsPanel.__init__(self, config)
        self.logger = logging.getLogger("DratsChatPanel")

        val = DratsConfigWidget(config, "prefs", "logenabled")
        val.add_bool()
        self.make_view(_("Log chat traffic"), val)

        val = DratsConfigWidget(config, "prefs", "logresume")
        val.add_bool()
        self.make_view(_("Load log tail"), val)

        val = DratsConfigWidget(config, "prefs", "font")
        val.add_font()
        self.make_view(_("Chat font"), val)

        val = DratsConfigWidget(config, "prefs", "scrollback")
        val.add_numeric(0, 9999, 1)
        self.make_view(_("Scrollback Lines"), val)

        val = DratsConfigWidget(config, "prefs", "chat_showstatus")
        val.add_bool()
        self.make_view(_("Show status updates in chat"), val)

        val = DratsConfigWidget(config, "prefs", "chat_timestamp")
        val.add_bool()
        self.make_view(_("Timestamp chat messages"), val)

        val = DratsConfigWidget(config, "settings", "qst_size_limit")
        val.add_numeric(1, 9999, 1)
        self.make_view(_("QST Size Limit"), val)

        # weather api
        val = DratsConfigWidget(config, "settings", "qst_owuri", True)
        val.add_text()
        self.make_view(_("OpenWeather uri"), val)

        val = DratsConfigWidget(config, "settings", "qst_owappid", True)
        val.add_text()
        self.make_view(_("OpenWeather appid"), val)


class DratsSoundPanel(DratsPanel):
    '''
    D-Rats Sound Panel.

    :param config: DratsConfig object
    '''

    def __init__(self, config):
        DratsPanel.__init__(self, config)
        self.logger = logging.getLogger("DratsSoundPanel")

        def do_snd(tab, tab_text):
            snd = DratsConfigWidget(config, "sounds", tab)
            snd.add_sound()
            enb = DratsConfigWidget(config, "sounds", "%s_enabled" % tab)
            enb.add_bool()
            self.make_view(tab_text, snd, enb)

        do_snd("chat", _("Chat activity"))
        do_snd("messages", _("Message activity"))
        do_snd("files", _("File activity"))


class DratsRadioPanel(DratsPanel):
    '''
    D-Rats Radio Panel.

    :param config: DratsConfig object
    '''

    INITIAL_ROWS = 3

    def __init__(self, config):
        DratsPanel.__init__(self, config)
        self.logger = logging.getLogger("DratsRadioPanel")

        cols = [(GObject.TYPE_STRING, "ID"),
                (GObject.TYPE_BOOLEAN, _("Enabled")),
                (GObject.TYPE_STRING, _("Port")),
                (GObject.TYPE_STRING, _("Settings")),
                (GObject.TYPE_BOOLEAN, _("Sniff")),
                (GObject.TYPE_BOOLEAN, _("Raw Text")),
                (GObject.TYPE_STRING, _("Name"))]

        _lab = Gtk.Label.new(_("Configure data paths below."
                               "  This may include any number of"
                               " serial-attached radios and"
                               " network-attached proxies."))

        port_config_list = DratsListConfigWidget(config, "ports")

        def make_key(vals):
            return vals[5]

        list_widget = port_config_list.add_list(cols, make_key)
        add = Gtk.Button.new_with_label(_("Add"))
        add.connect("clicked", self.but_add, list_widget)
        mod = Gtk.Button.new_with_label(_("Edit"))
        mod.connect("clicked", self.but_mod, list_widget)
        rem = Gtk.Button.new_with_label(_("Remove"))
        rem.connect("clicked", self.but_rem, list_widget)

        port_config_list.set_sort_column(6)

        self.make_view(_("Paths"), port_config_list, add, mod, rem)

        list_widget.set_resizable(1, False)

    def make_view(self, title, *widgets):
        '''
        Make View.

        :param _title: Title of view, Unused
        :param *widgets: Widgets to place in view
        '''
        # self.attach(widgets[0], 0, 2, 0, 1)
        widgets[0].show()
        widget_height = max(widgets[0].get_preferred_height())
        self.attach(widgets[0], 0, 0, 3, widget_height)



        if len(widgets) > 1:
            box = Gtk.Box.new(orientation=Gtk.Orientation.HORIZONTAL,
                              spacing=2)
            box.set_homogeneous(True)

            for i in widgets[1:]:
                box.pack_start(i, 0, 0, 0)
                i.show()

            box.show()
            box_height = max(box.get_preferred_height())
            # self.attach(box, 0, 2, 1, 2, yoptions=Gtk.AttachOptions.SHRINK)
            self.attach_next_to(box, widgets[0], Gtk.PositionType.BOTTOM,
                                1, box_height)


    # pylint: disable=no-self-use
    def but_add(self, _button, list_widget):
        '''
        Button Add.

        :param _button: Unused
        :param list_widget: list widget object
        '''
        name, port, info = prompt_for_port()
        if name:
            list_widget.set_item(name, True, port, info, False, False, name)

    # pylint: disable=no-self-use
    def but_mod(self, _button, list_widget):
        '''
        Button Modify.

        :param _button: Unused
        :param list_widget: list widget object
        '''
        values = list_widget.get_item(list_widget.get_selected())
        self.logger.info("Values: %s", str(values))
        name, port, info = prompt_for_port(values[2], values[3], values[6])
        if name:
            list_widget.set_item(values[6], values[1], port, info, values[4],
                                 values[5], values[6])

    def but_rem(self, _button, list_widget):
        '''
        Button remove.

        :param _button: Unused
        :param list_widget: list widget object
        '''
        list_widget.del_item(list_widget.get_selected())



class DratsTransfersPanel(DratsPanel):
    '''
    D-Rats Transfers Panel.

    :param config: DratsConfig object
    '''

    def __init__(self, config):
        DratsPanel.__init__(self, config)
        self.logger = logging.getLogger("DratsTransfersPanel")

        val = DratsConfigWidget(config, "settings", "ddt_block_size", True)
        val.add_numeric(32, 4096, 32)
        self.make_view(_("Block size"), val)

        val = DratsConfigWidget(config, "settings", "ddt_block_outlimit", True)
        val.add_numeric(1, 32, 1)
        self.make_view(_("Pipeline blocks"), val)

        val = DratsConfigWidget(config, "prefs", "allow_remote_files")
        val.add_bool()
        self.make_view(_("Remote file transfers"), val)

        val = DratsConfigWidget(config, "settings", "warmup_length", True)
        val.add_numeric(0, 64, 8)
        self.make_view(_("Warmup Length"), val)

        val = DratsConfigWidget(config, "settings", "warmup_timeout", True)
        val.add_numeric(0, 16, 1)
        self.make_view(_("Warmup timeout"), val)

        val = DratsConfigWidget(config, "settings", "force_delay", True)
        val.add_numeric(-32, 32, 1)
        self.make_view(_("Force transmission delay"), val)

        val = DratsConfigWidget(config, "settings", "delete_from")
        val.add_text()
        self.make_view(_("Allow file deletes from"), val)

        val = DratsConfigWidget(config, "settings", "remote_admin_passwd")
        val.add_pass()
        self.make_view(_("Remote admin password"), val)


class DratsMessagePanel(DratsPanel):
    '''
    D-Rats Message Panel.

    :param config: DratsConfig object
    '''

    # pylint: disable=too-many-locals,too-many-statements
    def __init__(self, config):
        DratsPanel.__init__(self, config)
        self.logger = logging.getLogger("DratsMessagePanel")

        vala = DratsConfigWidget(config, "settings", "msg_forward")
        vala.add_bool()
        self.make_view(_("Automatically forward messages"), vala)

        val = DratsConfigWidget(config, "settings", "msg_flush")
        val.add_numeric(15, 9999, 1)
        lab = Gtk.Label.new(_("seconds"))
        self.make_view(_("Queue flush interval"), val, lab)
        # pylint: disable=protected-access
        disable_with_toggle(vala._widget, val._widget)

        val = DratsConfigWidget(config, "settings", "station_msg_ttl")
        val.add_numeric(0, 99999, 1)
        lab = Gtk.Label.new(_("seconds"))
        self.make_view(_("Station TTL"), val, lab)
        # pylint: disable=protected-access
        disable_with_toggle(vala._widget, val._widget)

        val = DratsConfigWidget(config, "prefs", "msg_include_reply")
        val.add_bool()
        self.make_view(_("Include original in reply"), val)

        val = DratsConfigWidget(config, "prefs", "msg_allow_pop3")
        val.add_bool()
        self.make_view(_("Allow POP3 Gateway"), val)

        vala = DratsConfigWidget(config, "prefs", "msg_allow_wl2k")
        vala.add_bool()
        self.make_view(_("Allow WL2K Gateway"), vala)

        wlm = DratsConfigWidget(config, "settings", "msg_wl2k_mode")
        wlm.add_combo(["Network", "RMS"], False)
        self.make_view(_("WL2K Connection"), wlm)

        wl2k_servers = [x + ".winlink.org" for x in ["server",
                                                     "perth",
                                                     "halifax",
                                                     "sandiego",
                                                     "wien"]]
        srv = DratsConfigWidget(config, "prefs", "msg_wl2k_server")
        srv.add_combo(wl2k_servers, True)
        prt = DratsConfigWidget(config, "prefs", "msg_wl2k_port")
        prt.add_numeric(1, 65535, 1)
        lab = Gtk.Label.new(_("Port"))
        pwd = DratsConfigWidget(config, "prefs", "msg_wl2k_password")
        pwd.add_pass()
        ptab = Gtk.Label.new(_("Password"))
        self.make_view(_("WL2K Network Server"), srv, lab, prt, ptab, pwd)

        rms = DratsConfigWidget(config, "prefs", "msg_wl2k_rmscall")
        rms.add_upper_text(10)

        lab = Gtk.Label.new(_(" on port "))

        ports = []
        if self.config.has_section("ports"):
            for port in self.config.options("ports"):
                spec = self.config.get("ports", port).split(",")
                if "agwpe" in spec[1]:
                    ports.append(spec[-1])

        rpt = DratsConfigWidget(config, "prefs", "msg_wl2k_rmsport")
        rpt.add_combo(ports, False)
        self.make_view(_("WL2K RMS Station"), rms, lab, rpt)

        net_map = {
            # pylint: disable=protected-access
            "Network" : [srv._widget, prt._widget, pwd._widget],
            # pylint: disable=protected-access
            "RMS"     : [rms._widget, rpt._widget],
            }
        # pylint: disable=protected-access
        disable_by_combo(wlm._widget, net_map)
        # pylint: disable=protected-access
        disable_with_toggle(vala._widget, wlm._widget)

        ssids = [""] + [str(x) for x in range(1, 11)]
        val = DratsConfigWidget(config, "prefs", "msg_wl2k_ssid")
        val.add_combo(ssids, True)
        self.make_view(_("My Winlink SSID"), val)

        p3s = DratsConfigWidget(config, "settings", "msg_pop3_server")
        p3s.add_bool()
        lab = Gtk.Label.new(_("on port"))
        p3p = DratsConfigWidget(config, "settings", "msg_pop3_port")
        p3p.add_numeric(1, 65535, 1)
        self.make_view(_("POP3 Server"), p3s, lab, p3p)
        # pylint: disable=protected-access
        disable_with_toggle(p3s._widget, p3p._widget)

        sms = DratsConfigWidget(config, "settings", "msg_smtp_server")
        sms.add_bool()
        lab = Gtk.Label.new(_("on port"))
        smp = DratsConfigWidget(config, "settings", "msg_smtp_port")
        smp.add_numeric(1, 65535, 1)
        self.make_view(_("SMTP Server"), sms, lab, smp)
        # pylint: disable=protected-access
        disable_with_toggle(sms._widget, smp._widget)


class DratsNetworkPanel(DratsPanel):
    '''D-Rats Network Panel'''
    # pass


class DratsTCPPanel(DratsPanel):
    '''D-Rats TCP Panel.'''

    INITIAL_ROWS = 2

    def make_view(self, _title, *widgets):
        '''
        Make View.

        set information for a widget.
        :param title: Title for widget
        :param *args: Optional arguments
        '''

        #self.attach(widgets[0], 0, 2, 0, 1)
        widgets[0].show()
        widget_height = max(widgets[0].get_preferred_height())

        self.attach(widgets[0], 0, 0, 3, widget_height)

        if len(widgets) > 1:
            box = Gtk.Box.new(orientation=Gtk.Orientation.HORIZONTAL,
                              spacing=2)
            box.set_homogeneous(True)

            for i in widgets[1:]:
                box.pack_start(i, 0, 0, 0)
                i.show()

            box.show()
            box_height = max(box.get_preferred_height())
            # self.attach(box, 0, 2, 1, 2, yoptions=Gtk.AttachOptions.SHRINK)
            self.attach_next_to(box, widgets[0], Gtk.PositionType.BOTTOM,
                                1, box_height)

    # pylint: disable=no-self-use
    def but_rem(self, _button, list_widget):
        '''
        Button Remove.

        :param _button: Unused
        :param list_widget: widget for button
        '''
        list_widget.del_item(list_widget.get_selected())

    # pylint: disable=no-self-use
    def prompt_for(self, fields):
        '''
        Prompt for.

        :param fields: Fields object
        :returns: dict of fields
        '''
        field_dialog = inputdialog.FieldDialog()
        for n_field, t_field in fields:
            field_dialog.add_field(n_field, Gtk.Entry())

        ret = {}

        done = False
        while not done and field_dialog.run() == Gtk.ResponseType.OK:
            done = True
            for n_field, t_field in fields:
                try:
                    s_text = field_dialog.get_field(n_field).get_text()
                    if not s_text:
                        raise ValueError("empty")
                    ret[n_field] = t_field(s_text)
                except ValueError as error:
                    e_dialog = Gtk.MessageDialog(buttons=Gtk.ButtonsType.OK)
                    e_dialog.set_property("text",
                                          _("Invalid value for") +
                                          " %s: %s" % (n_field, error))
                    e_dialog.run()
                    e_dialog.destroy()
                    done = False
                    break

        field_dialog.destroy()

        if done:
            return ret
        return None


class DratsTCPOutgoingPanel(DratsTCPPanel):
    '''
    D-Rats TCP Outgoing Panel.

    :param config: DratsConfig object
    '''

    def __init__(self, config):
        DratsTCPPanel.__init__(self, config)
        self.logger = logging.getLogger("DratsTCPOutgoingPanel")

        outcols = [(GObject.TYPE_STRING, "ID"),
                   (GObject.TYPE_INT, _("Local")),
                   (GObject.TYPE_INT, _("Remote")),
                   (GObject.TYPE_STRING, _("Station"))]

        val = DratsListConfigWidget(config, "tcp_out")
        list_widget = val.add_list(outcols)
        add = Gtk.Button.new_with_label(_("Add"))
        add.connect("clicked", self.but_add, list_widget)
        rem = Gtk.Button.new_with_label(_("Remove"))
        rem.connect("clicked", self.but_rem, list_widget)
        self.make_view(_("Outgoing"), val, add, rem)

    def but_add(self, _button, list_widget):
        '''
        Button Add.

        :param _button: Unused
        :param list_widget: widget for button
        '''
        values = self.prompt_for([(_("Local Port"), int),
                                  (_("Remote Port"), int),
                                  (_("Station"), str)])
        if values is None:
            return

        list_widget.set_item(str(values[_("Local Port")]),
                             values[_("Local Port")],
                             values[_("Remote Port")],
                             values[_("Station")].upper())


class DratsTCPIncomingPanel(DratsTCPPanel):
    '''
    D-Rats TCP Incoming Panel.

    :param config: DratsConfig object
    '''

    def __init__(self, config):
        DratsTCPPanel.__init__(self, config)
        self.logger = logging.getLogger("DratsTCPIncomingPanel")

        incols = [(GObject.TYPE_STRING, "ID"),
                  (GObject.TYPE_INT, _("Port")),
                  (GObject.TYPE_STRING, _("Host"))]

        val = DratsListConfigWidget(config, "tcp_in")
        list_widget = val.add_list(incols)
        add = Gtk.Button.new_with_label(_("Add"))
        add.connect("clicked", self.but_add, list_widget)
        rem = Gtk.Button.new_with_label(_("Remove"))
        rem.connect("clicked", self.but_rem, list_widget)
        self.make_view(_("Incoming"), val, add, rem)

    def but_add(self, _button, list_widget):
        '''
        Button Add.

        :param _button: Unused
        :param list_widget: widget for button
        '''
        values = self.prompt_for([(_("Port"), int),
                                  (_("Host"), str)])
        if values is None:
            return

        list_widget.set_item(str(values[_("Port")]),
                             values[_("Port")],
                             values[_("Host")].upper())



class DratsOutEmailPanel(DratsPanel):
    '''
    D-Rats Out Email Panel

    :param config: DratsConfig object
    '''

    def __init__(self, config):
        DratsPanel.__init__(self, config)
        self.logger = logging.getLogger("DratsOutEmailPanel")

        gateway = DratsConfigWidget(config, "settings", "smtp_dogw")
        gateway.add_bool()
        self.make_view(_("SMTP Gateway"), gateway)

        val = DratsConfigWidget(config, "settings", "smtp_server")
        val.add_text()
        self.make_view(_("SMTP Server"), val)
        # pylint: disable=protected-access
        disable_with_toggle(gateway._widget, val._widget)

        port = DratsConfigWidget(config, "settings", "smtp_port")
        port.add_numeric(1, 65536, 1)
        mode = DratsConfigWidget(config, "settings", "smtp_tls")
        mode.add_bool("TLS")
        self.make_view(_("Port and Mode"), port, mode)
        # pylint: disable=protected-access
        disable_with_toggle(gateway._widget, port._widget)
        # pylint: disable=protected-access
        disable_with_toggle(gateway._widget, mode._widget)

        val = DratsConfigWidget(config, "settings", "smtp_replyto")
        val.add_text()
        self.make_view(_("Source Address"), val)
        # pylint: disable=protected-access
        disable_with_toggle(gateway._widget, val._widget)

        val = DratsConfigWidget(config, "settings", "smtp_username")
        val.add_text()
        self.make_view(_("SMTP Username"), val)
        # pylint: disable=protected-access
        disable_with_toggle(gateway._widget, val._widget)

        val = DratsConfigWidget(config, "settings", "smtp_password")
        val.add_pass()
        self.make_view(_("SMTP Password"), val)
        # pylint: disable=protected-access
        disable_with_toggle(gateway._widget, val._widget)


class DratsInEmailPanel(DratsPanel):
    '''
    D-Rats In Email Panel.

    :param config: DratsConfig object
    '''

    INITIAL_ROWS = 2

    def __init__(self, config):
        DratsPanel.__init__(self, config)
        self.logger = logging.getLogger("DratsInEmailPanel")

        cols = [(GObject.TYPE_STRING, "ID"),
                (GObject.TYPE_STRING, _("Server")),
                (GObject.TYPE_STRING, _("Username")),
                (GObject.TYPE_STRING, _("Password")),
                (GObject.TYPE_INT, _("Poll Interval")),
                (GObject.TYPE_BOOLEAN, _("Use SSL")),
                (GObject.TYPE_INT, _("Port")),
                (GObject.TYPE_STRING, _("Action")),
                (GObject.TYPE_BOOLEAN, _("Enabled"))
                ]

        self.choices = {
            _("Action") : [_("Form"), _("Chat")],
            }

        # Remove after 0.1.9
        self.convert_018_values(config, "incoming_email")

        val = DratsListConfigWidget(config, "incoming_email")

        def make_key(vals):
            return "%s@%s" % (vals[0], vals[1])

        list_widget = val.add_list(cols, make_key)
        list_widget.set_password(2)
        add = Gtk.Button.new_with_label(_("Add"))
        add.connect("clicked", self.but_add, list_widget)
        edit = Gtk.Button.new_with_label(_("Edit"))
        edit.connect("clicked", self.but_edit, list_widget)
        rem = Gtk.Button.new_with_label(_("Remove"))
        rem.connect("clicked", self.but_rem, list_widget)

        list_widget.set_sort_column(1)

        self.make_view(_("Incoming Accounts"), val, add, edit, rem)

    def make_view(self, title, *widgets):
        '''
        Make View.

        set information for a widget.
        :param title: Title for widget
        :param *args: Optional arguments
        '''
        # self.attach(widgets[0], 0, 2, 0, 1)

        widgets[0].show()
        widget_height = max(widgets[0].get_preferred_height())
        self.attach(widgets[0], 0, 0, 3, widget_height)

        if len(widgets) > 1:
            box = Gtk.Box.new(orientation=Gtk.Orientation.HORIZONTAL,
                              spacing=2)
            box.set_homogeneous(True)

            for i in widgets[1:]:
                box.pack_start(i, 0, 0, 0)
                i.show()

            box.show()
            box_height = max(box.get_preferred_height())
            # self.attach(box, 0, 2, 1, 2, yoptions=Gtk.AttachOptions.SHRINK)
            self.attach_next_to(box, widgets[0], Gtk.PositionType.BOTTOM,
                                1, box_height)


    # pylint: disable=no-self-use
    def but_rem(self, _button, list_widget):
        '''
        Button remove.

        :param _button: Unused
        :param list_widget: widget for button
        '''
        list_widget.del_item(list_widget.get_selected())

    # pylint: disable=too-many-branches
    def prompt_for_acct(self, fields):
        '''
        Prompt For Account.

        :param fields: Fields for account dialog
        :returns: Dict containing account information
        '''
        dlg = inputdialog.FieldDialog()
        for n_field, t_field, d_field in fields:
            if n_field in list(self.choices.keys()):
                entry = miscwidgets.make_choice(self.choices[n_field],
                                                False, d_field)
            elif n_field == _("Password"):
                entry = Gtk.Entry()
                entry.set_visibility(False)
                entry.set_text(str(d_field))
            elif t_field == bool:
                entry = Gtk.CheckButton.new_with_label(_("Enabled"))
                entry.set_active(d_field)
            else:
                entry = Gtk.Entry()
                entry.set_text(str(d_field))
            dlg.add_field(n_field, entry)

        ret = {}

        done = False
        while not done and dlg.run() == Gtk.ResponseType.OK:
            done = True
            for n_field, t_field, _d_field in fields:
                try:
                    if n_field in list(self.choices.keys()):
                        value = dlg.get_field(n_field).get_active_text()
                    elif t_field == bool:
                        value = dlg.get_field(n_field).get_active()
                    else:
                        value = dlg.get_field(n_field).get_text()
                        if not value:
                            raise ValueError("empty")
                    ret[n_field] = t_field(value)
                except ValueError as error:
                    e_dialog = Gtk.MessageDialog(buttons=Gtk.ButtonsType.OK)
                    e_dialog.set_property("text",
                                          _("Invalid value for") + " %s: %s" %
                                          (n_field, error))
                    e_dialog.run()
                    e_dialog.destroy()
                    done = False
                    break

        dlg.destroy()
        if done:
            return ret
        return None

    def but_add(self, _button, list_widget):
        '''
        Button Add.

        :param _button: Unused
        :param list_widget: widget for button
        '''
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
            id_val = "%s@%s" % (ret[_("Server")], ret[_("Username")])
            list_widget.set_item(id_val,
                                 ret[_("Server")],
                                 ret[_("Username")],
                                 ret[_("Password")],
                                 ret[_("Poll Interval")],
                                 ret[_("Use SSL")],
                                 ret[_("Port")],
                                 ret[_("Action")],
                                 ret[_("Enabled")])

    def but_edit(self, _button, list_widget):
        '''
        Button Edit.

        :param _button: Unused
        :param list_widget: widget for button
        '''
        vals = list_widget.get_item(list_widget.get_selected())
        fields = [(_("Server"), str, vals[1]),
                  (_("Username"), str, vals[2]),
                  (_("Password"), str, vals[3]),
                  (_("Poll Interval"), int, vals[4]),
                  (_("Use SSL"), bool, vals[5]),
                  (_("Port"), int, vals[6]),
                  (_("Action"), str, vals[7]),
                  (_("Enabled"), bool, vals[8]),
                  ]
        id_val = "%s@%s" % (vals[1], vals[2])
        ret = self.prompt_for_acct(fields)
        if ret:
            list_widget.del_item(id_val)
            id_val = "%s@%s" % (ret[_("Server")], ret[_("Username")])
            list_widget.set_item(id_val,
                                 ret[_("Server")],
                                 ret[_("Username")],
                                 ret[_("Password")],
                                 ret[_("Poll Interval")],
                                 ret[_("Use SSL")],
                                 ret[_("Port")],
                                 ret[_("Action")],
                                 ret[_("Enabled")])

    def convert_018_values(self, config, section):
        '''
        Convert 018 Values.

        :param config: Configuration object
        :param section: Section to convert
        '''
        if not config.has_section(section):
            return
        options = config.options(section)
        for opt in options:
            val = config.get(section, opt)
            if len(val.split(",")) < 7:
                val += ",Form"
                config.set(section, opt, val)
                self.logger.info("7-8 Converted %s/%s", section, opt)
            if len(val.split(",")) < 8:
                val += ",True"
                config.set(section, opt, val)
                self.logger.info("8-9 Converted %s/%s", section, opt)


class DratsEmailAccessPanel(DratsPanel):
    '''
    D-Rats Email Access Panel.

    :param config: DratsConfig object
    '''

    INITIAL_ROWS = 2

    def __init__(self, config):
        DratsPanel.__init__(self, config)
        self.logger = logging.getLogger("DratsEmailAccessPanel")

        cols = [(GObject.TYPE_STRING, "ID"),
                (GObject.TYPE_STRING, _("Callsign")),
                (GObject.TYPE_STRING, _("Access")),
                (GObject.TYPE_STRING, _("Email Filter"))]

        self.choices = {
            _("Access") : [_("None"), _("Both"), _("Incoming"), _("Outgoing")],
            }

        val = DratsListConfigWidget(config, "email_access")

        def make_key(vals):
            return "%s/%i" % (vals[0], random.randint(0, 1000))

        list_widget = val.add_list(cols, make_key)
        add = Gtk.Button.new_with_label(_("Add"))
        add.connect("clicked", self.but_add, list_widget)
        edit = Gtk.Button.new_with_label(_("Edit"))
        edit.connect("clicked", self.but_edit, list_widget)
        rem = Gtk.Button.new_with_label(_("Remove"))
        rem.connect("clicked", self.but_rem, list_widget)

        list_widget.set_sort_column(1)

        self.make_view(_("Email Access"), val, add, edit, rem)

    def make_view(self, title, *widgets):
        '''
        Make View.

        set information for a widget.
        :param title: Title for widget
        :param *args: Optional arguments
        '''
        # self.attach(widgets[0], 0, 2, 0, 1)

        widgets[0].show()
        widget_height = max(widgets[0].get_preferred_height())
        self.attach(widgets[0], 0, 0, 3, widget_height)

        if len(widgets) > 1:
            box = Gtk.Box.new(orientation=Gtk.Orientation.HORIZONTAL,
                              spacing=2)
            box.set_homogeneous(True)

            for i in widgets[1:]:
                box.pack_start(i, 0, 0, 0)
                i.show()

            box.show()
            box_height = max(box.get_preferred_height())
            # self.attach(box, 0, 2, 1, 2, yoptions=Gtk.AttachOptions.SHRINK)
            self.attach_next_to(box, widgets[0], Gtk.PositionType.BOTTOM,
                                1, box_height)


    # pylint: disable=no-self-use
    def but_rem(self, _button, list_widget):
        '''
        Button Remove.

        :param _button: Button widget unused
        :param list_widget: Listing widget
        '''
        list_widget.del_item(list_widget.get_selected())

    def prompt_for_entry(self, fields):
        '''
        Prompt for entry.

        :param fields: Fields for entry
        :returns: Dictionary of fields or None
        '''
        dlg = inputdialog.FieldDialog()
        for n_field, t_field, d_field in fields:
            if n_field in list(self.choices.keys()):
                choice = miscwidgets.make_choice(self.choices[n_field],
                                                 False, d_field)
            else:
                choice = Gtk.Entry()
                choice.set_text(str(d_field))
            dlg.add_field(n_field, choice)

        ret = {}

        done = False
        while not done and dlg.run() == Gtk.ResponseType.OK:
            done = True
            for n_field, t_field, _d_field in fields:
                try:
                    if n_field in list(self.choices.keys()):
                        value = dlg.get_field(n_field).get_active_text()
                    else:
                        value = dlg.get_field(n_field).get_text()

                    if n_field == _("Callsign"):
                        if not value:
                            raise ValueError("empty")
                        else:
                            value = value.upper()
                    ret[n_field] = t_field(value)
                except ValueError as error:
                    e_dialog = Gtk.MessageDialog(buttons=Gtk.ButtonsType.OK)
                    e_dialog.set_property("text",
                                          _("Invalid value for") + "%s: %s" %
                                          (n_field, error))
                    e_dialog.run()
                    e_dialog.destroy()
                    done = False
                    break

        dlg.destroy()
        if done:
            return ret
        return None

    def but_add(self, _button, list_widget):
        '''
        Button Add.

        :param _button: Button widget, not used
        :param list_widget: List widget
        '''
        fields = [(_("Callsign"), str, ""),
                  (_("Access"), str, _("Both")),
                  (_("Email Filter"), str, "")]
        ret = self.prompt_for_entry(fields)
        if ret:
            id_val = "%s/%i" % (ret[_("Callsign")],
                                random.randint(1, 1000))
            list_widget.set_item(id_val,
                                 ret[_("Callsign")],
                                 ret[_("Access")],
                                 ret[_("Email Filter")])

    def but_edit(self, _button, list_widget):
        '''
        Button Edit.

        :param _button: Button widget, not used
        :param list_widget: List widget
        '''
        vals = list_widget.get_item(list_widget.get_selected())
        if not vals:
            return
        fields = [(_("Callsign"), str, vals[1]),
                  (_("Access"), str, vals[2]),
                  (_("Email Filter"), str, vals[3])]
        id_val = vals[0]
        ret = self.prompt_for_entry(fields)
        if ret:
            list_widget.del_item(id_val)
            list_widget.set_item(id_val,
                                 ret[_("Callsign")],
                                 ret[_("Access")],
                                 ret[_("Email Filter")])


class DratsConfigUI(Gtk.Dialog):
    '''
    D-Rats Configuration UI.

    :param config: DratsConfig object
    :param parent: Parent object, default None
    '''

    def __init__(self, config, parent=None):
        Gtk.Dialog.__init__(self, parent=parent)
        self.set_title(_("Config"))
        self.add_button(_("Save"), Gtk.ResponseType.OK)
        self.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        self.config = config
        self.logger = logging.getLogger("DratsConfigUI")
        self.panels = {}
        #self.tips = Gtk.Tooltips()
        self.build_ui()
        self.set_default_size(800, 400)

    def mouse_event(self, view, event):
        '''
        Mouse Event.

        :param view: View object
        :param event: Mouse event
        '''
        x_coord, y_coord = event.get_coords()
        path = view.get_path_at_pos(int(x_coord), int(y_coord))
        if path:
            view.set_cursor_on_cell(path[0], None, None, False)

        try:
            (store, iter_val) = view.get_selection().get_selected()
            selected, = store.get(iter_val, 0)
        # pylint: disable=broad-except
        except Exception:
            self.logger.info("Unable to find selected item", exc_info=True)

        for value in self.panels.values():
            value.hide()
        self.panels[selected].show()

    def move_cursor(self, view, _step, _count):
        '''
        Move Cursor.

        :param view: View to move cursor on
        :param _step: Unused
        :param _count: Unused
        '''
        try:
            (store, _iter) = view.get_selection().get_selected()
            selected, = store.get(iter, 0)
        # pylint: disable=broad-except
        except Exception:
            self.logger.info("Unable to move cursor", exc_info=True)

        for value in self.panels.values():
            value.hide()
        self.panels[selected].show()

    def build_ui(self):
        '''Build UI.'''
        hbox = Gtk.Box.new(orientation=Gtk.Orientation.HORIZONTAL,
                           spacing=2)

        self.__store = Gtk.TreeStore(GObject.TYPE_STRING, GObject.TYPE_STRING)
        self.__tree = Gtk.TreeView.new_with_model(self.__store)

        hbox.pack_start(self.__tree, 0, 0, 0)
        self.__tree.set_size_request(150, -1)
        self.__tree.set_headers_visible(False)
        rend = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn(None, rend, text=1)
        self.__tree.append_column(col)
        self.__tree.show()
        self.__tree.connect("button_press_event", self.mouse_event)
        self.__tree.connect_after("move-cursor", self.move_cursor)

        def add_panel(c_arg, s_arg, l_arg, par, *args):
            panel = c_arg(self.config, *args)
            panel.show()
            scroll_w = Gtk.ScrolledWindow()
            scroll_w.set_policy(Gtk.PolicyType.AUTOMATIC,
                                Gtk.PolicyType.AUTOMATIC)
            scroll_w.add(panel)
            hbox.pack_start(scroll_w, 1, 1, 1)

            self.panels[s_arg] = scroll_w

            for val in panel.vals:
                try:
                    val.set_tooltip_text(config_tips.get_tip(val.vsec,
                                                             val.vname))
                # pylint: disable=bare-except
                except:
                    self.logger.info("Could not add tool tip %s to %s type %s",
                                     config_tips.get_tip(val.vsec, val.vname),
                                     val.vname,
                                     type(val),
                                     exc_info=True)
                #self.tips.set_tip(val,
                #                  config_tips.get_tip(val.vsec, val.vname))

            return self.__store.append(par, row=(s_arg, l_arg))

        prefs = add_panel(DratsPrefsPanel, "prefs", _("Preferences"), None)
        add_panel(DratsPathsPanel, "paths", _("Paths"), prefs, self)
        add_panel(DratsMapPanel, "maps", _("Maps"), prefs, self)
        add_panel(DratsGPSPanel, "gps", _("GPS config"), prefs, self)
        add_panel(DratsGPSExportPanel, "gpsexport", _("Export GPS messages"),
                  prefs, self)
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
        '''Save.'''
        for widget in self.config.widgets:
            widget.save()


# pylint: disable=too-many-ancestors
class DratsConfig(six.moves.configparser.ConfigParser):
    '''
    D-Rats Configuration.

    :param: _mainapp: Unused
    :param: _safe: Unused, default=False
    '''

    def __init__(self, _mainapp, _safe=False):
        six.moves.configparser.ConfigParser.__init__(self)

        self.platform = dplatform.get_platform()
        self.filename = self.platform.config_file("d-rats.config")
        self.logger = logging.getLogger("DratsConfig")

        self.logger.info("File %s", self.filename)
        self.read(self.filename)
        self.widgets = []

        self.set_defaults()

        # create "D-RATS Shared" folder for file transfers
        if self.get("prefs", "download_dir") == ".":
            default_dir = os.path.join(dplatform.get_platform().default_dir(),
                                       "D-RATS Shared")
            self.logger.info("%s", default_dir)
            if not os.path.exists(default_dir):
                self.logger.info("Creating directory for downloads: %s",
                                 default_dir)
                os.mkdir(default_dir)
                self.set("prefs", "download_dir", default_dir)

        # create the folder structure for storing the map tiles
        map_dir = self.get("settings", "mapdir")
        if not os.path.exists(map_dir):
            self.logger.info("Creating directory for maps: %s", map_dir)
            os.mkdir(map_dir)
        if not os.path.exists(os.path.join(map_dir, "base")):
            os.mkdir(os.path.join(map_dir, "base"))
        if not os.path.exists(os.path.join(map_dir, "cycle")):
            os.mkdir(os.path.join(map_dir, "cycle"))
        if not os.path.exists(os.path.join(map_dir, "outdoors")):
            os.mkdir(os.path.join(map_dir, "outdoors"))
        if not os.path.exists(os.path.join(map_dir, "landscape")):
            os.mkdir(os.path.join(map_dir, "landscape"))

    def set_defaults(self):
        '''
        Set Defaults.

        Set default value if not already present
        '''
        for sec, opts in DEFAULTS.items():
            if not self.has_section(sec):
                self.add_section(sec)

            for opt, value in opts.items():
                if not self.has_option(sec, opt):
                    self.set(sec, opt, value)

    def show(self, parent=None):
        '''
        Show.

        :returns: True if the result is ok.
        '''
        drats_ui = DratsConfigUI(self, parent)
        result = drats_ui.run()
        if result == Gtk.ResponseType.OK:
            drats_ui.save()
            self.save()
        drats_ui.destroy()

        return result == Gtk.ResponseType.OK

    def save(self):
        '''Save Configuration.'''
        file_handle = open(self.filename, "w")
        self.write(file_handle)
        file_handle.close()

    # pylint: disable=arguments-differ
    def getboolean(self, sec, key):
        '''
        Get Boolean value.

        :param sec: Section of parameter file
        :param key: Key in section
        :returns: Boolean value'''
        try:
            return six.moves.configparser.ConfigParser.getboolean(self,
                                                                  sec, key)
        # pylint: disable=broad-except
        except Exception:
            self.logger.info("Failed to get boolean: %s/%s", sec, key,
                             exc_info=True)
            return False

    # pylint: disable=arguments-differ
    def getint(self, sec, key):
        '''
        Get Integer.

        :param sec: Section of parameter file
        :param key: Key in section
        :returns: integer value.'''
        return int(float(six.moves.configparser.ConfigParser.get(self,
                                                                 sec, key)))

    def form_source_dir(self):
        '''
        Form Source Directory.

        Directory is created if if does not exist.
        :returns: Form storage directory
        '''
        form_dir = os.path.join(self.platform.config_dir(), "Form_Templates")
        if not os.path.isdir(form_dir):
            os.mkdir(form_dir)

        return form_dir

    def form_store_dir(self):
        '''
        Form Store directroy.

        Directroy is created if it does not exist.
        :returns: Form storage directory
        '''
        form_dir = os.path.join(self.platform.config_dir(), "messages")
        if not os.path.isdir(form_dir):
            os.mkdir(form_dir)

        return form_dir

    def ship_obj_fn(self, name):
        '''
        Ship Object Filename.

        :param name: Filename for object
        :returns: Path for object
        '''
        return os.path.join(self.platform.source_dir(), name)

    def ship_img(self, name):
        '''
        Ship Image.

        :param name: Name of the image file
        :returns: GdkPixbuf of image
        '''
        path = self.ship_obj_fn(os.path.join("images", name))
        return GdkPixbuf.Pixbuf.new_from_file(path)


def main():
    '''Main package for testing.'''
    import sys
    sys.path.insert(0, ".")

    logging.basicConfig(level=logging.INFO)

    # Each class should have their own logger.
    logger = logging.getLogger("config_test")

    logger.info("sys.path=%s", sys.path)
    # mm: fn = "/home/dan/.d-rats/d-rats.config"
    filename = "d-rats.config"

    parser = six.moves.configparser.ConfigParser()
    parser.read(filename)
    parser.widgets = []

    config = DratsConfigUI(parser)
    if config.run() == Gtk.ResponseType.OK:
        config.save()


if __name__ == "__main__":
    #if not __package__:
    #    # pylint: disable=redefined-builtin
    #    __package__ = '__main__'
    main()
