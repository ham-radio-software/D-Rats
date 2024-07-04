# File: configui/defaults.py

'''
D-Rats Configuration Defaults.

This is default values for the D-Rats configuration.
'''

# Copyright 2009 Dan Smith <dsmith@danplanet.com>
# review 2015-2020 Maurizio Andreotti  <iz2lxi@yahoo.it>
# Copyright 2021-2024 John. E. Malmberg - Python3 Conversion
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


import os
HAVE_PYCOUNTRY = False
try:
    from pycountry import languages
    HAVE_PYCOUNTRY = True
except (ModuleNotFoundError, ImportError):
    pass

import gi  # type: ignore # Needed for pylance on Windows.
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk        # type: ignore


if not '_' in locals():
    import gettext
    _ = gettext.gettext

from .aprs_dprs import AprsDprsCodes
from .dplatform import Platform


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

DEFAULT_LANGUAGE = "English"
DEFAULT_LANGUAGE_CODE = 'en'
# getdefaultlocale being removed from python.
# DEFAULT_LOCALE = locale.getdefaultlocale()
DEFAULT_LOCALE = "en_US.UTF-8"
DEFAULT_COUNTRY = "United States"
DEFAULT_COUNTRY_CODE = "US"
envs = ['LC_ALL', 'LC_CTYPE', 'LANG', 'LANGUAGE']
for env in envs:
    # Need to guess the country
    if env in os.environ:
        DEFAULT_LOCALE = os.environ[env]
        DEFAULT_COUNTRY_CODE = DEFAULT_LOCALE[3:5]
        break

if HAVE_PYCOUNTRY:
    LANGUAGE_OBJECT = languages.get(alpha_2=DEFAULT_LOCALE[0][0:2])
    if LANGUAGE_OBJECT:
        DEFAULT_LANGUAGE = LANGUAGE_OBJECT.name
        DEFAULT_LANGUAGE_CODE = LANGUAGE_OBJECT.alpha_2

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
    "country": DEFAULT_COUNTRY,
    "language" : DEFAULT_LANGUAGE,
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
    "aprssymtab" : AprsDprsCodes.APRS_CAR_CODE[0],
    "aprssymbol" : AprsDprsCodes.APRS_CAR_CODE[1],
    "compatmode" : "False",
    "inports" : "[]",
    "outports" : "[]",
    "sockflush" : "0.5",
    "pipelinexfers" : "True",

    # Weather APIs
    "qst_owuri" : "https://api.openweathermap.org/data/2.5/",
    "qst_owappid" : "ecd42c31b76e59e83de5cb8c16f7bd95a",

    # MAPS APIs
    "mapdir" : os.path.join(Platform.get_platform().config_dir(), "maps"),
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
    "default_gps_comment" : "BN",          # default icon for our station in
                                           # the map and gps fixes
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

    "form_logo_dir" : os.path.join(Platform.get_platform().config_dir(),
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
