# pylint: disable=too-many-lines
'''QST.'''
#
# Copyright 2008 Dan Smith <dsmith@danplanet.com>
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

import datetime
import json
import logging
import re
import threading
import urllib

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import GLib
from gi.repository import GObject

if not '_' in locals():
    import gettext
    _ = gettext.gettext

from .filenamebox import FilenameBox
from .miscwidgets import make_choice
from .miscwidgets import make_pixbuf_choice

from .dplatform import Platform
from . import inputdialog
from . import cap
from . import gps
from .utils import combo_select, get_icon

QST_LOGGER = logging.getLogger("QST")

try:
    import feedparser
    HAVE_FEEDPARSER = True
except ImportError:
    QST_LOGGER.info("FeedParser not available")
    HAVE_FEEDPARSER = False

try:
    from hashlib import md5
except ImportError:
    QST_LOGGER.info("Installing hashlib replacement hack")
    from .utils import ExternalHash as md5


# pylint: disable=too-many-locals
def do_dprs_calculator(initial=""):
    '''
    Do DPRS Calculator.

    :param initial: initial string, default ""
    :type initial: str
    :returns: DPRS string with Checksum
    :rtype: str
    '''
    def ev_sym_changed(iconsel, oversel, icons):
        oversel.set_sensitive(icons[iconsel.get_active()][1][0] == "\\")

    dialog = inputdialog.FieldDialog(title=_("DPRS message"))
    msg = Gtk.Entry()
    msg.set_max_length(13)

    overlays = [chr(x) for x in range(ord(" "), ord("_"))]

    cur = initial
    logger = logging.getLogger("QST_Do_DPRS_Calculator")

    if cur and len(cur) >2 and cur[-3] == "*" and cur[3] == " ":
        msg.set_text(cur[4:-3])
        dsym = cur[:2]
        deficn = gps.DPRS_TO_APRS.get(dsym, "/#")
        defovr = cur[2]
        if defovr not in overlays:
            logger.info("Overlay %s not in list", defovr)
            defovr = " "
    else:
        deficn = "/#"
        defovr = " "

    icons = []
    for sym in sorted(gps.DPRS_TO_APRS.values()):
        icon = get_icon(sym)
        if icon:
            icons.append((icon, sym))
    iconsel = make_pixbuf_choice(icons, deficn)

    oversel = make_choice(overlays, False, defovr)
    iconsel.connect("changed", ev_sym_changed, oversel, icons)
    ev_sym_changed(iconsel, oversel, icons)

    dialog.add_field(_("Message"), msg)
    dialog.add_field(_("Icon"), iconsel)
    dialog.add_field(_("Overlay"), oversel)

    result = dialog.run()
    aicon = icons[iconsel.get_active()][1]
    mstr = msg.get_text().upper()
    over = oversel.get_active_text()
    dialog.destroy()
    if result != Gtk.ResponseType.OK:
        return None

    dicon = gps.APRS_TO_DPRS[aicon]

    # pylint: disable=import-outside-toplevel
    from . import mainapp # Hack to force import of mainapp
    callsign = mainapp.get_mainapp().config.get("user", "callsign")
    string = "%s%s %s" % (dicon, over, mstr)

    check = gps.dprs_checksum(callsign, string)

    return string + check


class QSTText(GObject.GObject):
    '''
    QST Text.

    :param config: Configuration object
    :type config: :class:`DratsConfig`
    :param content: QST Content
    :type content: str
    :param key: Name for QST
    :type key: str
    '''

    __gsignals__ = {
        "qst-fired" : (GObject.SignalFlags.RUN_LAST,
                       GObject.TYPE_NONE,
                       (GObject.TYPE_STRING, GObject.TYPE_STRING)),
        }

    def __init__(self, config, content, key):
        GObject.GObject.__init__(self)


        self.config = config
        self.prefix = "[QST] "
        self.text = content
        self.raw = False
        self.key = key

    def do_qst(self):
        '''
        Do QST.

        :returns: QST String
        :rtype: str
        '''
        return self.text

    def fire(self):
        '''Fire a QST.'''
        val = self.do_qst()
        self.emit("qst-fired", self.prefix + val, self.key)


class QSTExec(QSTText):
    '''
    QST Exec.

    :param config: Configuration object
    :type config: :class:`DratsConfig`
    :param content: QST Content
    :type content: str
    :param key: Name for QST
    :type key: str
    '''

    def __init__(self, config, content, key):
        QSTText.__init__(self, config, content, key)
        self.logger = logging.getLogger("QSTExec")

    def do_qst(self):
        '''
        do QST

        :returns: QST String
        :rtype: str
        '''
        size_limit = self.config.getint("settings", "qst_size_limit")
        pform = Platform.get_platform()
        status, output = pform.run_sync(self.text)
        if status:
            self.logger.info("Command failed with status %i", status)

        return output[:size_limit]


class QSTFile(QSTText):
    '''
    QST File.

    :param config: Configuration object
    :type config: :class:`DratsConfig`
    :param content: QST Content
    :type content: str
    :param key: Name for QST
    :type key: str
    '''

    def __init__(self, config, content, key):
        QSTText.__init__(self, config, content, key)
        self.logger = logging.getLogger("QSTFile")

    def do_qst(self):
        '''
        do QST.

        :returns: QST String or None
        :rtype: str
        '''
        size_limit = self.config.getint("settings", "qst_size_limit")
        try:
            # pylint: disable=consider-using-width
            file_handle = open(self.text)
        except (PermissionError, FileNotFoundError) as err:
            self.logger.info("Unable to open file `%s': %s", self.text, err)
            return None

        text = file_handle.read()
        file_handle.close()

        return text[:size_limit]


class QSTGPS(QSTText):
    '''
    QST GPS.

    :param config: Configuration object
    :type config: :class:`DratsConfig`
    :param content: QST Content
    :type content: str
    :param key: Name for QST
    :type key: str
    '''

    def __init__(self, config, content, key):
        QSTText.__init__(self, config, content, key)
        self.logger = logging.getLogger("QSTGPS")

        self.prefix = ""
        self.raw = True
        # pylint: disable=import-outside-toplevel
        from . import mainapp #hack
        self.mainapp = mainapp.get_mainapp()
        self.fix = None

    def set_fix(self, fix):
        '''
        Set Fix.

        :param fix: Fix to add.
        :type fix: :class:`GPSPosition`
        '''
        self.fix = fix

    def do_qst(self):
        '''
        do QST

        :returns: QST String
        :rtype: str
        '''
        if not self.fix:
            # from . import mainapp #hack
            fix = self.mainapp.get_position()
        else:
            fix = self.fix

        fix.set_station(fix.station, self.text[:20])

        if fix.valid:
            return fix.to_nmea_gga()
        return None


class QSTGPSA(QSTGPS):
    '''QST GPSA.'''

    def do_qst(self):
        '''
        do QST.

        :returns: QST String
        :rtype: str
        '''
        if not self.fix:
            # from . import mainapp #hack
            fix = self.mainapp.get_position()
        else:
            fix = self.fix

        if not "::" in self.text:
            # add "/" that was removed from gps.py to send message
            # and not in Weather WXGPS-A
            self.text = ("/"+self.text)
            fix.set_station(fix.station, self.text[:200])
            self.text = self.text[1:]

        if fix.valid:
            return fix.to_aprs(symtab=self.config.get("settings", "aprssymtab"),
                               symbol=self.config.get("settings", "aprssymbol"))
        return None


class QSTWX(QSTGPS):
    '''
    QST WX.

    :param config: Configuration object
    :type config: :class:`DratsConfig`
    :param content: QST Content
    :type content: str
    :param key: Name for QST
    :type key: str
    '''
    def __init__(self, config, content, key):
        QSTGPS.__init__(self, config, content, key)
        self.logger = logging.getLogger("QST")

    def do_qst(self):
        '''
        do QST.

        :returns: QST String
        :rtype: str
        '''
#  This is working on python but not on Windows
#        linecache.checkcache(self.text)
#        wx = linecache.getline(self.text, 2).strip()
# /* from here
        # pylint: disable=consider-using-width
        file_handle = open(self.text)
       # f = NetFile(self.text)
        wx_line = file_handle.readline()
        wx_line = file_handle.readline().rstrip()
        file_handle.close()
#*/ to here is working on Windows and python

        if not self.fix:
            fix = self.mainapp.get_position()
        else:
            fix = self.fix

        if not "::" in self.text:
            fix.set_station(fix.station, wx_line[:200])

        if fix.valid:
            return fix.to_aprs(symtab="/",
                               symbol="_")
#       WX symbol will be used for WXGPS-A.
#       return fix.to_aprs(symtab=self.config.get("settings", "aprssymtab"),
#                          symbol=self.config.get("settings", "aprssymbol")
        self.logger.info("do_qst: "
                         "GPS position is not valid, so not sent")
        return None


class QSTThreadedText(QSTText):
    '''
    QST Threaded Text.

    :param config: Configuration object
    :type config: :class:`DratsConfig`
    :param content: QST Content
    :type content: str
    :param key: Name for QST
    :type key: str
    '''

    def __init__(self, config, content, key):
        QSTText.__init__(self, config, content, key)
        self.logger = logging.getLogger("QSTThreadedText")

        self.thread = None

    def threaded_fire(self):
        '''Threaded Fire.'''

        msg = self.do_qst()
        self.thread = None

        if not msg:
            self.logger.info("Skipping QST because no data was returned")
            return

        GLib.idle_add(self.emit, "qst-fired",
                      "%s%s" % (self.prefix, msg), self.key)

    def fire(self):
        '''Fire.'''
        if self.thread:
            self.logger.info("QST thread still running, not starting another")
            return

        # This is a race, but probably pretty safe :)
        self.thread = threading.Thread(target=self.threaded_fire)
        # pylint: disable=deprecated-method
        self.thread.setDaemon(True)
        self.thread.start()
        self.logger.info("Started a thread for QST data...")


class QSTRSS(QSTThreadedText):
    '''
    QST RSS.

    :param config: Configuration object
    :type config: :class:`DratsConfig`
    :param content: QST Content
    :type content: str
    :param key: Name for QST
    :type key: str
    '''

    def __init__(self, config, content, key):
        QSTThreadedText.__init__(self, config, content, key)
        self.logger = logging.getLogger("QSTRSS")

        self.last_id = ""

    def do_qst(self):
        '''
        Do QST.

        :returns: QST String
        :rtype: str
        '''
        rss = feedparser.parse(self.text)

        try:
            entry = rss.entries[-1]
        except IndexError:
            self.logger.info("RSS feed had no entries")
            return None

        try:
            ident = entry.id
        except AttributeError:
            # Not all feeds will have an id (I guess)
            ident = md5(entry.description)

        if ident != self.last_id:
            self.last_id = ident
            text = str(entry.description)

            text = re.sub("<[^>]*?>", "", text)
            text = text[:8192]

            return text
        return None


class QSTCAP(QSTThreadedText):
    '''
    QST CAP.

    :param config: Configuration object
    :type config: :class:`DratsConfig`
    :param content: QST Content
    :type content: str
    :param key: Name for QST
    :type key: str
    '''

    def __init__(self, config, content, key):
        QSTThreadedText.__init__(self, config, content, key)
        self.logger = logging.getLogger("QSTCAP")

        self.last_date = None

    def determine_starting_item(self):
        '''Determine Starting Item.'''

        cap_obj = cap.CAPParserURL(self.text)
        if cap_obj.events:
            lastev = cap_obj.events[-1]
            delta = datetime.timedelta(seconds=1)
            self.last_date = (lastev.effective - delta)
        else:
            self.last_date = datetime.datetime.now()

    def do_qst(self):
        '''
        do QST.

        :returns: QST String
        :rtype: str
        '''
        if self.last_date is None:
            self.determine_starting_item()

        self.logger.info("Last date is %s", self.last_date)

        cap_obj = cap.CAPParserURL(self.text)
        newev = cap_obj.events_effective_after(self.last_date)
        if not newev:
            return None

        try:
            self.last_date = newev[-1].effective
        except IndexError:
            self.logger.info("CAP feed had no entries")
            return None

        q_str = ""

        for i in newev:
            self.logger.info("Sending CAP that is effective %s", i.effective)
            q_str += "\r\n-----\r\n%s\r\n-----\r\n" % i.report()

        return q_str


class QSTWeatherWU(QSTThreadedText):
    '''
    QST Weather WU.

    :param config: Configuration object
    :type config: :class:`DratsConfig`
    :param content: QST Content
    :type content: str
    :param key: Name for QST
    :type key: str
    '''

    def __init__(self, config, content, key):
        QSTThreadedText.__init__(self, config, content, key)
        self.logger = logging.getLogger("QST_Weather_WU")
        self.logger.info("QSTWeatherWU class retired")


class QSTOpenWeather(QSTThreadedText):
    '''
    QST Open Weather.

    :param config: Configuration object
    :type config: :class:`DratsConfig`
    :param content: QST Content
    :type content: str
    :param key: Name for QST
    :type key: str
    '''

    def __init__(self, config, content, key):
        QSTThreadedText.__init__(self, config, content, key)
        self.logger = logging.getLogger("QSTOpenWeather")

    # pylint: disable=too-many-statements
    def do_qst(self):
        '''
        Do QST.

        :returns: Qst text
        :rtype: str
        '''
        weath = ""
        # _obs = wu.WUObservation()
        owuri = self.config.get("settings", "qst_owuri")
        owappid = self.config.get("settings", "qst_owappid")

        try:
            t_qst, s_qst = self.text.split("/", 2)
        except ValueError as err:
            self.logger.info("Unable to split weather QST %s: %s",
                             self.text, err)
            return None

#---to be restore when forecasts are done
     #   try:
        if t_qst == _("Current"):
            url = owuri +"weather?"+ \
                urllib.parse.urlencode({'q': s_qst, 'appid': owappid})
            self.logger.info("URL=%s", url)
            # pylint: disable=consider-using-with
            url_read = urllib.request.urlopen(url).read()
            data_json = json.loads(url_read)
            self.logger.info(data_json)

            # Check the value of "cod" key is equal to "404",
            # means city is found otherwise, city is not found
            if data_json["cod"] != "404":

                wname = str(data_json['name'])
                wcountry = str(data_json['sys']['country'])
                wlat = str(data_json['coord']['lat'])
                wlon = str(data_json['coord']['lon'])
                wdesc = str(data_json['weather'][0]['description'])
                wtmin = float(data_json['main']['temp_min'])
                wtemp = float(data_json['main']['temp'])
                wtmax = float(data_json['main']['temp_max'])
                whumidity = int(data_json['main']['humidity'])
                wpressure = int(data_json['main']['pressure'])
                wwindspeed = float(data_json['wind']['speed'])

                weath = ("\nCurrent weather at %s - %s lat: %s Lon: %s \n" %
                         (wname, wcountry, wlat, wlon))
                weath = weath + str("Conditions: %s\n" % wdesc)
                weath = weath + str("Current Temperature: %.2f C (%.2f F) \n" %
                                    ((wtemp - 273.0), (wtemp*9/5- 459.67)))
                weath = weath + str("Minimum Temperature: %.2f C (%.2f F) \n" %
                                    ((wtmin - 273.0), (wtmin*9/5- 459.67)))
                weath = weath + str("Maximum Temperature: %.2f C (%.2f F) \n" %
                                    ((wtmax - 273.0), (wtmax*9/5- 459.67)))
                weath = weath + str("Humidity: %d %% \n" % whumidity)
                weath = weath + str("Pressure: %d hpa \n" %  wpressure)
                # weath = weath + str("Wind Gust:%s km/hr\n" %
                #                     float(data_json['wind']['gust']))
                weath = weath + str("Wind Speed: %.2f km/hr\n" % wwindspeed)

                self.logger.info("Weather %s", weath)

                return weath
            self.logger.info("weather forecast: %s city not found", s_qst)
            return None

        if t_qst == _("Forecast"):
            url = owuri + "forecast?" + \
                urllib.parse.urlencode({'q': s_qst, 'appid': owappid,
                                        'mode': "json"})
            self.logger.info("Forecast: %s ", url)
            url_read = urllib.request.urlopen(url).read()
            data_json = json.loads(url_read)
            self.logger.info(data_json)

            # Check the value of "cod" key is equal to "404",
            # means city is found otherwise, city is not found
            if data_json["cod"] != "404":

                wname = str(data_json['city']['name'])
                wcountry = str(data_json['city']['country'])
                wlat = str(data_json['city']['coord']['lat'])
                wlon = str(data_json['city']['coord']['lon'])

                weath = ("\nForecast weather for %s - %s lat: %s Lon: %s \n" %
                         (wname, wcountry, wlat, wlon))

                # set date to start iterating through
                current_date = ''
                # Iterates through the array of dictionaries named list in
                # json_data
                for item in data_json['list']:

                    # Time of the weather data received, partitioned into
                    # 3 hour blocks
                    wtime = item['dt_txt']

                    # Split the time into date and hour [2018-04-15 06:00:00]
                    next_date, hour = wtime.split(' ')

                    # Stores the current date and prints it once
                    if current_date != next_date:
                        current_date = next_date
                        year, month, day = current_date.split('-')
                        date = {'y': year, 'm': month, 'd': day}
                        weath = weath + ('\n{d}/{m}/{y}'.format(**date))
                        # Grabs the first 2 integers from our HH:MM:SS string
                        # to get the hours
                    hour = int(hour[:2])

                    # Sets the AM (ante meridiem) or PM (post meridiem) period
                    if hour < 12:
                        if hour == 0:
                            hour = 12
                        meridiem = 'AM'
                    else:
                        if hour > 12:
                            hour -= 12
                        meridiem = 'PM'

                    # Weather condition
                    description = item['weather'][0]['description']
                    wtemp = item['main']['temp']
                    wtmin = item['main']['temp_min']
                    wtmax = item['main']['temp_max']
                    whumidity = item['main']['humidity']
                    wpressure = item['main']['pressure']
                    wwindspeed = item['wind']['speed']

                    # prepare string with weather conditions
                    # Timestamp as [HH:MM AM/PM]
                    weath = weath + ('\n%i:00 %s ' % (hour, meridiem))
                    # Weather forecast and temperatures
                    weath = weath + ("Weather condition: %s \n" % description)
                    weath = weath + ("Avg Temp: %.2f C (%.2f F) \n" %
                                     ((wtemp - 273.15), (wtemp * 9/5 - 459.67)))
                    weath = weath + ("Min Temp: %.2f C (%.2f F) \n" %
                                     ((wtmin - 273.0), (wtmin*9/5- 459.67)))
                    weath = weath + ("Max Temp: %.2f C (%.2f F) \n" %
                                     ((wtmax - 273.0), (wtmax*9/5- 459.67)))
                    weath = weath + ("Humidity: %d %%  " % whumidity)
                    weath = weath + ("Pressure: %d hpa  " %  wpressure)
                    # weath = weath + str("Wind Gust:%s km/hr\n" %
                    #                     float(data_json['wind']['gust']))
                    weath = weath + str("Wind Speed: %.2f km/hr\n" % wwindspeed)

                self.logger.info("forecast: %s", weath)
                return weath

            self.logger.info("weather forecast: %s city not found", s_qst)
            return None

        self.logger.info("Unknown Weather type %s", t_qst)
        return None

#---to be restore when forecasts are done
    #    except SomeException as err:
    #        self.logger.info("do_qst: Error getting weather: %s" % err))
    #        return None

        # Code not reachable
        # return weath
        # return str(obs)


class QSTStation(QSTGPSA):
    '''
    QST Station.

    :param config: Configuration object
    :type config: :class:`DratsConfig`
    :param content: QST Content
    :type content: str
    :param key: Name for QST
    :type key: str
    '''

    def __init__(self, config, content, key):
        QSTGPSA.__init__(self, config, content, key)
        self.logger = logging.getLogger("QSTStation")

    @staticmethod
    def get_source(name):
        '''
        Get Map Source for name.

        :param name: Name of map source
        :type name: str
        :returns: The map source for name or None
        :rtype: :class:`MapSource`
        '''
        # pylint: disable=import-outside-toplevel
        from . import mainapp # Hack to force mainapp load
        sources = mainapp.get_mainapp().map.get_map_sources()

        for source in sources:
            if source.get_name() == name:
                return source

        return None

    @staticmethod
    def get_station(source, station):
        '''
        Get Station from source.

        :param source: Source to look up station in
        :param station: Station to look up
        :type station: src
        :returns: Point for station or None
        :rtype: :class:`MapStation`
        '''
        for point in source.get_points():
            if point.get_name() == station:
                return point

        return None

    def do_qst(self):
        '''
        Do QST.

        :returns: QST test
        :rtype: str
        '''
        try:
            (group, station) = self.text.split("::", 1)
        except ValueError as err:
            self.logger.info("QSTStation Error: %s", err)
            return None

        source = self.get_source(group)
        if source is None:
            self.logger.info("Unknown group %s", group)
            return None

        point = self.get_station(source, station)
        if point is None:
            self.logger.info("Unknown station %s in group %s",
                             station, group)
            return None

        self.fix = gps.GPSPosition(point.get_latitude(),
                                   point.get_longitude(),
                                   point.get_name())
        self.fix.set_station(self.fix.station,
                             "VIA %s" % self.config.get("user", "callsign"))

        self.logger.info("Sending position for %s/%s: %s",
                         group, station, self.fix)

        return QSTGPSA.do_qst(self)


class QSTEditWidget(Gtk.Box):
    '''
    QST Edit Widget.

    :param orientation: Orientation for the Gtk Box.
    :type orientation: :class:`Gtk.Orientation`,
                       default Gtk.Orientation.VERTICAL
    :param spacing: the number of pixels between children
    :type: spacing: int
    '''

    def __init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=0):
        Gtk.Box.__init__(self)
        self.set_orientation(orientation)
        self.set_spacing(spacing)
        self._id = None

    def to_qst(self):
        '''
        To QST.

        :returns: Returns the QST text
        :rtype: str
        '''

    def from_qst(self, content):
        '''
        From QST.

        :param content: Content from QST
        :type content: str
        '''

    # pylint: disable=arguments-differ
    def __str__(self):
        return "Unknown"

    def reset(self):
        '''Reset'''

    def to_human(self):
        '''
        To Human.

        :returns: Human readable QST
        :rtype: str
        '''


class QSTTextEditWidget(QSTEditWidget):
    '''QST Text Edit Widget.'''

    label_text = _("Enter a message:")

    def __init__(self):
        QSTEditWidget.__init__(self, spacing=2)

        lab = Gtk.Label.new(self.label_text)
        lab.show()
        self.pack_start(lab, 0, 0, 0)

        self.__tb = Gtk.TextBuffer()

        text_view = Gtk.TextView.new_with_buffer(self.__tb)
        text_view.show()

        self.pack_start(text_view, 1, 1, 1)

    def __str__(self):
        return self.__tb.get_text(self.__tb.get_start_iter(),
                                  self.__tb.get_end_iter(), True)

    def reset(self):
        '''Reset text to blank.'''
        self.__tb.set_text("")

    def to_qst(self):
        '''
        To QST.

        :returns: Returns the QST text
        :rtype: str
        '''
        return str(self)

    def from_qst(self, content):
        '''
        From QST.

        :param content: Content from QST
        :type content: str
        '''
        self.__tb.set_text(content)

    def to_human(self):
        '''
        To Human.

        :returns: Human readable QST
        :rtype: str
        '''
        return str(self)


class QSTFileEditWidget(QSTEditWidget):
    '''QST File Edit Widget.'''

    label_text = _("Choose a text file.  "
                   "The contents will be used when the QST is sent.")

    def __init__(self):
        QSTEditWidget.__init__(self, spacing=2)

        lab = Gtk.Label.new(self.label_text)
        lab.set_line_wrap(True)
        lab.show()
        self.pack_start(lab, 1, 1, 1)

        self.__fn = FilenameBox(save=False)
        self.__fn.show()
        self.pack_start(self.__fn, 0, 0, 0)

    def __str__(self):
        return "Read: %s" % self.__fn.get_filename()

    def reset(self):
        '''Reset Filename to blank.'''
        self.__fn.set_filename("")

    def to_qst(self):
        '''
        To QST

        :returns: Returns the QST text
        :rtype: str
        '''
        return self.__fn.get_filename()

    def from_qst(self, content):
        '''
        From QST

        :param content: Content from QST
        :type content: str
        '''
        self.__fn.set_filename(content)

    def to_human(self):
        '''
        To Human.

        :returns: Human readable QST
        :rtype: str
        '''
        return self.__fn.get_filename()


class QSTWXFileEditWidget(QSTEditWidget):
    '''QST WX File Edit Widget.'''

    label_text = _("Choose a APRS text file.  "
                   "The contents will be used when the WXGPS-A is sent.")

    def __init__(self):
        QSTEditWidget.__init__(self, spacing=2)
        lab = Gtk.Label(self.label_text)
        lab.set_line_wrap(True)
        lab.show()
        self.pack_start(lab, 1, 1, 1)

        self.__fn = FilenameBox(save=False)
        self.__fn.show()
        self.pack_start(self.__fn, 0, 0, 0)

    def __str__(self):
        return "Read: %s" % self.__fn.get_filename()

    def reset(self):
        '''Reset.'''
        self.__fn.set_filename("")

    def to_qst(self):
        '''
        To QST.

        :returns: Returns the QST text
        :rtype: str
        '''
        return self.__fn.get_filename()

    def from_qst(self, content):
        '''
        From QST.

        :param content: Content from QST
        :type content: str
        '''
        self.__fn.set_filename(content)

    def to_human(self):
        '''
        To Human.

        :returns: Human readable QST
        :rtype: str
        '''
        return self.__fn.get_filename()


class QSTExecEditWidget(QSTFileEditWidget):
    '''QST Exec Edit Widget.'''

    label_text = _("Choose a script to execute.  "
                   "The output will be used when the QST is sent")

    def __str__(self):
        return "Run: %s" % self.__fn.get_filename()


class QSTGPSEditWidget(QSTEditWidget):
    '''QST GPS Edit Widget.'''

    msg_limit = 20
    type = "GPS"

    def __init__(self, config):
        QSTEditWidget.__init__(self, spacing=2)

        lab = Gtk.Label.new(_("Enter your GPS message:"))
        lab.set_line_wrap(True)
        lab.show()
        self.pack_start(lab, 1, 1, 1)

        hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 2)
        hbox.show()
        self.pack_start(hbox, 0, 0, 0)

        self.__msg = Gtk.Entry()
        self.__msg.set_max_length(self.msg_limit)
        self.__msg.show()
        hbox.pack_start(self.__msg, 1, 1, 1)

        dprs = Gtk.Button.new_with_label("DPRS")

        if not isinstance(self, QSTGPSAEditWidget):
            dprs.show()
            self.__msg.set_text(config.get("settings", "default_gps_comment"))
        else:
            self.__msg.set_text("ON D-RATS")

        dprs.connect("clicked", self.prompt_for_dprs)
        hbox.pack_start(dprs, 0, 0, 0)

    def prompt_for_dprs(self, _button):
        '''
        Prompt For DPRS

        :param _button: Unused.
        '''
        dprs = do_dprs_calculator(self.__msg.get_text())
        if dprs is None:
            return
        self.__msg.set_text(dprs)

    def __str__(self):
        return "Message: %s" % self.__msg.get_text()

    def reset(self):
        '''Reset the text to blank.'''
        self.__msg.set_text("")

    def to_qst(self):
        '''
        To QST.

        :returns: Returns the QST text
        :rtype: str
        '''
        return self.__msg.get_text()

    def from_qst(self, content):
        '''
        From QST.

        :param content: Content from QST
        :type content: str
        '''
        self.__msg.set_text(content)

    def to_human(self):
        '''
        To Human.

        :returns: Human readable QST
        :rtype: str
        '''
        return self.__msg.get_text()


class QSTGPSAEditWidget(QSTGPSEditWidget):
    '''QST GPSA Edit.'''

    msg_limit = 200
    type = "GPS-A"


class QSTWXEditWidget(QSTGPSEditWidget):
    '''QST WX Edit Widget.'''

    msg_limit = 200
    type = "WX"


class QSTRSSEditWidget(QSTEditWidget):
    '''QST RSS Edit Widget.'''

    label_string = _("Enter the URL of an RSS feed:")

    def __init__(self):
        QSTEditWidget.__init__(self, spacing=2)
        lab = Gtk.Label.new(self.label_string)
        lab.show()
        self.pack_start(lab, 1, 1, 1)

        self.__url = Gtk.Entry()
        self.__url.set_text("http://")
        self.__url.show()
        self.pack_start(self.__url, 0, 0, 0)

    def __str__(self):
        return "Source: %s" % self.__url.get_text()

    def to_qst(self):
        '''
        To QST.

        :returns: Returns the QST text
        :rtype: str
        '''
        return self.__url.get_text()

    def from_qst(self, content):
        '''
        From QST.

        :param content: Content from QST
        :type content: str
        '''
        self.__url.set_text(content)

    def reset(self):
        '''Reset text to blank.'''
        self.__url.set_text("")

    def to_human(self):
        '''
        To Human.

        :returns: Human readable QST
        :rtype: str
        '''
        return self.__url.get_text()


class QSTCAPEditWidget(QSTRSSEditWidget):
    '''QST CAP Edit Widget.'''

    label_string = _("Enter the URL of a CAP feed:")


class QSTStationEditWidget(QSTEditWidget):
    '''QST Station Edit Widget.'''

    def __init__(self):
        QSTEditWidget.__init__(self, spacing=2)

        lab = Gtk.Label.new(_("Choose a station whose position will be sent"))
        lab.show()

        self.pack_start(lab, 1, 1, 1)

        hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 10)

        # This is really ugly, but to fix it requires more work
        # pylint: disable=import-outside-toplevel
        from . import mainapp
        self.__sources = mainapp.get_mainapp().map.get_map_sources()
        sources = [x.get_name() for x in self.__sources]
        self.__group = make_choice(sources, False, _("Stations"))
        self.__group.show()
        hbox.pack_start(self.__group, 0, 0, 0)

        self.__station = make_choice([], False)
        self.__station.show()
        hbox.pack_start(self.__station, 0, 0, 0)

        self.__group.connect("changed", self.ev_group_sel, self.__station)
        self.ev_group_sel(self.__group, self.__station)

        hbox.show()
        self.pack_start(hbox, 0, 0, 0)

    def ev_group_sel(self, group, station):
        '''
        EV Group Selection.

        :param group: Group to select.
        :type group: str
        :param station: Station to get mode of
        :type station: :class:`MapStation`
        '''
        group = group.get_active_text()

        if not self.__sources:
            return

        source = None
        for source in self.__sources:
            if source.get_name() == group:
                break

        if not source or source.get_name() != group:
            return

        marks = [x.get_name() for x in source.get_points()]

        store = station.get_model()
        store.clear()
        for i in sorted(marks):
            station.append_text(i)
        if marks:
            station.set_active(0)

    def to_qst(self):
        '''
        To QST.

        :returns: Returns the QST text
        :rtype: str
        '''
        if not self.__group.get_active_text():
            return None
        if not self.__station.get_active_text():
            return None
        return "%s::%s" % (self.__group.get_active_text(),
                           self.__station.get_active_text())

    def to_human(self):
        '''
        To Human.

        :returns: Human readable QST
        :rtype: str
        '''
        return "%s::%s" % (self.__group.get_active_text(),
                           self.__station.get_active_text())


class QSTWUEditWidget(QSTEditWidget):
    '''QST WU Edit Widget.'''

    label_text = _("Enter an Open Weather station name:")

    def __init__(self):
        QSTEditWidget.__init__(self, spacing=2)

        lab = Gtk.Label.new(self.label_text)
        lab.show()
        self.logger = logging.getLogger("QSTWUEditWidget")

        self.pack_start(lab, 1, 1, 1)

        hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 2)
        hbox.show()
        self.pack_start(hbox, 0, 0, 0)

        self.__station = Gtk.Entry()
        self.__station.show()
        hbox.pack_start(self.__station, 0, 0, 0)

        types = [_("Current"), _("Forecast")]
        self.__type = make_choice(types, False, types[0])
        self.__type.show()
        hbox.pack_start(self.__type, 0, 0, 0)

    def to_qst(self):
        '''
        To QST.

        :returns: Returns the QST text
        :rtype: str
        '''
        return "%s/%s" % (self.__type.get_active_text(),
                          self.__station.get_text())

    def from_qst(self, content):
        '''
        From QST.

        :param content: Content from QST
        :type content: str
        '''
        try:
            t_qst, s_qst = content.split("/", 2)
        except ValueError:
            self.logger.info("Unable to split `%s'", content)
            t_qst = _("Current")
            s_qst = _("UNKNOWN")

        combo_select(self.__type, t_qst)
        self.__station.set_text(s_qst)

    def to_human(self):
        '''
        To Human.

        :returns: Human readable QST
        :rtype: str
        '''
        return self.to_qst()


# pylint: disable=too-many-instance-attributes, too-few-public-methods
class QSTEditDialog(Gtk.Dialog):
    '''
    QST Edit Dialog.

    :param config: Configuration object
    :type config: :class:`DratsConfig`
    :param ident: Identification for dialog
    :type ident: str
    :param parent: Parent widget
    :type parent: :class:`Gtk.Widget`
    '''

    def __init__(self, config, ident, parent=None):
        self.logger = logging.getLogger("QSTEditDialog")

        self.logger.info("defining qst types")
        self._types = {
            _("Text") : QSTTextEditWidget(),
            _("File") : QSTFileEditWidget(),
            _("Exec") : QSTExecEditWidget(),
            _("GPS")  : QSTGPSEditWidget(config),
            _("GPS-A"): QSTGPSAEditWidget(config),
            _("WXGPS-A"): QSTWXFileEditWidget(),
            _("RSS")  : QSTRSSEditWidget(),
            _("CAP")  : QSTCAPEditWidget(),
            _("Station") : QSTStationEditWidget(),
            _("OpenWeather") : QSTWUEditWidget(),
            }

        Gtk.Dialog.__init__(self, parent=parent)
        self.add_button(_("OK"), Gtk.ResponseType.OK)
        self.add_button(_("CANCEL"), Gtk.ResponseType.CANCEL)
        self._ident = ident
        self._config = config

        self.__current = None

        self.set_size_request(400, 150)

        self.vbox.pack_start(self._make_controls(), 0, 0, 0)

        for i in self._types.values():
            i.set_size_request(-1, 80)
            self.vbox.pack_start(i, 0, 0, 0)

        if self._config.has_section(self._ident):
            combo_select(self._type, self._config.get(self._ident, "type"))
            config_freq = self._config.get(self._ident, "freq")
            self._freq.get_child().set_text(config_freq)
            self._select_type(self._type)
            self.__current.from_qst(self._config.get(self._ident, "content"))
            combo_select(self._port, self._config.get(self._ident, "port"))
        else:
            self._select_type(self._type)

    def _select_type(self, box):
        wtype = box.get_active_text()

        if self.__current:
            self.__current.hide()
        self.__current = self._types[wtype]
        self.__current.show()

    def _make_controls(self):
        hbox = Gtk.Box.new(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)

        self._type = make_choice(list(self._types.keys()),
                                 False, default=_("Text"))
        self._type.set_size_request(100, -1)
        self._type.show()
        self._type.connect("changed", self._select_type)
        hbox.pack_start(self._type, 0, 0, 0)

        lab = Gtk.Label.new(_("every"))
        lab.show()
        hbox.pack_start(lab, 0, 0, 0)

        intervals = ["1", "3", "5", "10", "15", "20", "30", "60",
                     "120", "180", "240", ":00", ":15", ":30", ":45"]
        self._freq = make_choice(intervals, True, default="60")
        self._freq.set_size_request(75, -1)
        self._freq.show()
        hbox.pack_start(self._freq, 0, 0, 0)

        lab = Gtk.Label.new(_("minutes on port"))
        lab.show()
        hbox.pack_start(lab, 0, 0, 0)

        self._port = make_choice([_("Current"), _("All")], False,
                                 default="Current")
        self._port.show()
        hbox.pack_start(self._port, 0, 0, 0)

        hbox.show()
        return hbox

    def save(self):
        '''save.'''
        if not self._config.has_section(self._ident):
            self._config.add_section(self._ident)
            self._config.set(self._ident, "enabled", "True")

        self._config.set(self._ident, "freq", self._freq.get_active_text())
        self._config.set(self._ident, "content", self.__current.to_qst())
        self._config.set(self._ident, "type", self._type.get_active_text())
        self._config.set(self._ident, "port", self._port.get_active_text())


def get_qst_class(type_string):
    '''
    Get qst class.

    :param type_string: Type String for class
    :type type_string: str
    :returns: The QST class
    :rtype: :class:`QSTText`
    '''
    classes = {
        _("Text")    : QSTText,
        _("Exec")    : QSTExec,
        _("File")    : QSTFile,
        _("GPS")     : QSTGPS,
        _("GPS-A")   : QSTGPSA,
        _("WXGPS-A") : QSTWX,
        _("Station") : QSTStation,
        _("RSS")     : QSTRSS,
        _("CAP")     : QSTCAP,
        _("Weather (WU)") : QSTWeatherWU, #legacy class
        _("OpenWeather") : QSTOpenWeather,
        }

    if not HAVE_FEEDPARSER:
    # the  HAVE_FEEDPARSER variable is setup at d-rats launch when it checks
    # if feedparser can be imported.  For any reason feedparser import could
    # fail also if the module is compiled
    # (as it happens in my case on Windows10)
        del classes[_("RSS")]

    return classes.get(type_string, None)
