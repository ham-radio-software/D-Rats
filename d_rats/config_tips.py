#!/usr/bin/python
'''Config Tips'''

if not '_' in locals():
    import gettext
    _ = gettext.gettext


TIPS_USER = {
    "latitude" : _("Your current latitude."
                   "  Use decimal degrees (DD.DDDDD)\nor D*M'S\"."
                   "  Use a space for special characters").replace("*",
                                                                   u"\u00B0"),
    "longitude" : _("Your current longitude."
                    "  Use decimal degrees (DD.DDDDD)\nor D*M'S\"."
                    "  Use a space for special characters").replace("*",
                                                                    u"\u00B0"),
    "altitude" : _("Your current altitude"),
}

TIPS_PREFS = {
    "useutc" : _("When enabled, form time fields will default to current"
                 " time in UTC.  When disabled, default to local time"),
    "language" : _("Requires a D-RATS restart"),
    "allow_remote_forms" : _("Allow remote stations to pull forms"),
    "allow_remote_files" : _("Allow remote stations to pull files"),
    "form_default_private" : _("Default state for private flag on new forms"),
    "msg_include_reply" : _("Include the text of the original message when"
                            " replying (not recommended as it wastes"
                            " bandwidth)"),
    }

TIPS_SETTINGS = {
    "port" : _("On Windows, use something like 'COM12'") + "\n" + \
        _("On UNIX, use something like '/dev/ttyUSB0'") + "\n" + \
        _("For a network connection, use something like 'net:host:9000'"),
    "rate" : _("Serial rate shall be 38400 for IC92 handhelds, 9600 for"
               " all other D-Star radios"),
    "gpsport" : _("Serial port for an NMEA-compliant external GPS"),
    "gpsenabled" : _("If enabled, take current position from the external GPS"),
    "gpsportspeed" : _("The NMEA standard is 4800"),
    "aprssymtab" : _("The symbol table character for GPS-A beacons"),
    "aprssymbol" : _("The symbol character for GPS-A beacons"),
    "compatmode" : _("Treat incoming raw text (and garbage) as chat data"
                     " and display it on-screen"),
    "mapdir" : _("Alternate location to store cached map images"),
    "warmup_length" : _("Amount of bytes to to prefix to each packet during"
                        " a warmup cycle after a period of idle"),
    "warmup_timeout" : _("Amount of seconds between transmissions that must"
                         " pass before we send a warmup block to open the"
                         " power-save circuits on handhelds"),
    "force_delay" : _("Amount of seconds to wait between transmissions"
                      " (a positive number is a fixed delay, a negative"
                      " value means 'randomly choose between 0 and X')"),
    "delete_from" : _("Comma-separated list of callsigns that may delete"
                      " files remotely"),
    "remote_admin_passwd" : _("Password required for remote administration"
                              " tasks (blank for none)"),
    "ping_info" : _("Text string to return in response to a ping.") + "\n" + \
        _("If prefixed by a > character, interpret as a path to a text file") \
        + "\n" + \
        _("If prefixed by a ! character, interpret as a path to a script"),
    "smtp_server" : _("Hostname of outgoing SMTP server.  If this is"
                      " specified, this station will be a gateway for"
                      " email forms.  If left blank, this feature is disabled"),
    "smtp_replyto" : _("Email address to set on outgoing form email messages"),
    "smtp_tls" : _("If enabled, attempt to negotiate TLS/SSL with SMTP server"),
    "smtp_username" : _("Username for SMTP authentication.  Disabled if blank"),
    "smtp_password" : _("Password for SMTP authentication"),
    "smtp_port" : _("Default is 25.  Set to the value given by your ISP"),
    "sniff_packets" : _("Display information about packets seen that are"
                        " destined for other stations"),
    "map_tile_ttl" : _("After this many hours, a map tile will be re-fetched,"
                       " regardless of if it is already stored locally."
                       "  0 means never re-fetch.  720 hours is 30 days."),
    "msg_flush" : _("Seconds between each attempt to process forwarded"
                    " messages.  Do not set this too low!"),
    "station_msg_ttl" : _("If a station was last heard more than this many"
                          " seconds ago, do not assume you have a clear path"
                          " (ping it first)"),

    "mapurlbase" :_("Path to the online map tile server used to feed the"
                    " \"base\" map - can be changed to suit what is"
                    " available to your location"),
    "maptype" :_("Change this to select a map different from the base one"
                 " - beware to config the API Key correctly"),
    "keyformapurlcycle" :_("Insert you API key or completely empty this field"
                           " to get maps with \"API key required \"overlay"),

    "timestamp_positions" : _("For each position report received, change the"
                              " callsign to 'callsign.datestamp'."
                              "  NOTE: This will generate a LOT of map"
                              " pointers, use with caution!"),
    }

PRE_WAV = _("Specify a .WAV file to be played")
TIPS_SOUNDS = {
    "chat" : PRE_WAV + _(" when a new chat arrives"),
    "messages" : PRE_WAV + _(" when new message activity occurs"),
    "files" : PRE_WAV + _(" when new file activity occurs"),
}

CONFIG_TIPS = {
    "user" : TIPS_USER,
    "prefs" : TIPS_PREFS,
    "settings" : TIPS_SETTINGS,
    "sounds" : TIPS_SOUNDS,
}


def get_tip(section, value):
    '''
    Get tip text.

    :param section: Section for tip
    :type section: str
    :param value: Value for tip
    :param value: str
    :returns: Tip text or None
    :rtype: str
    '''

    try:
        tip = CONFIG_TIPS[section][value]
    except KeyError:
        tip = None
    return tip
