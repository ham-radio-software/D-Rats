#!/usr/bin/python
#
# Copyright 2008 Dan Smith <dsmith@danplanet.com>
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
import pygtk
import gobject
import time
import datetime
import copy
import re
import threading

from commands import getstatusoutput as run
from miscwidgets import make_choice, KeyedListWidget
import miscwidgets
import mainapp
import dplatform
import inputdialog
import cap
import wu
import mapdisplay
import gps
from utils import NetFile, combo_select, get_icon

try:
    import feedparser
    HAVE_FEEDPARSER = True
except ImportError, e:
    print("Qst       : FeedParser not available")
    HAVE_FEEDPARSER = False

try:
    from hashlib import md5
except ImportError:
    print("Qst       : Installing hashlib replacement hack")
    from utils import ExternalHash as md5

def do_dprs_calculator(initial=""):
    def ev_sym_changed(iconsel, oversel, icons):
        oversel.set_sensitive(icons[iconsel.get_active()][1][0] == "\\")

    d = inputdialog.FieldDialog(title=_("DPRS message"))
    msg = gtk.Entry(13)

    overlays = [chr(x) for x in range(ord(" "), ord("_"))]

    cur = initial
    if cur and cur[-3] == "*" and cur[3] == " ":
        msg.set_text(cur[4:-3])
        dsym = cur[:2]
        deficn = gps.DPRS_TO_APRS.get(dsym, "/#")
        defovr = cur[2]
        if defovr not in overlays:
            print("Qst       : Overlay %s not in list" % defovr)
            defovr = " "
    else:
        deficn = "/#"
        defovr = " "

    icons = []
    for sym in sorted(gps.DPRS_TO_APRS.values()):
        icon = get_icon(sym)
        if icon:
            icons.append((icon, sym))
    iconsel = miscwidgets.make_pixbuf_choice(icons, deficn)

    oversel = miscwidgets.make_choice(overlays, False, defovr)
    iconsel.connect("changed", ev_sym_changed, oversel, icons)
    ev_sym_changed(iconsel, oversel, icons)

    d.add_field(_("Message"), msg)
    d.add_field(_("Icon"), iconsel)
    d.add_field(_("Overlay"), oversel)

    r = d.run()
    aicon = icons[iconsel.get_active()][1]
    mstr = msg.get_text().upper()
    over = oversel.get_active_text()
    d.destroy()
    if r != gtk.RESPONSE_OK:
        return

    dicon = gps.APRS_TO_DPRS[aicon]

    callsign = mainapp.get_mainapp().config.get("user", "callsign")
    string = "%s%s %s" % (dicon, over, mstr)

    check = gps.DPRS_checksum(callsign, string)

    return string + check

class QSTText(gobject.GObject):
    __gsignals__ = {
        "qst-fired" : (gobject.SIGNAL_RUN_LAST,
                 gobject.TYPE_NONE,
                 (gobject.TYPE_STRING,)),
        }

    def __init__(self, config, content):
        gobject.GObject.__init__(self)

        self.config = config
        self.prefix = "[QST] "
        self.text = content
        self.raw = False

    def do_qst(self):
        return self.text

    def fire(self):
        val = self.do_qst()
        self.emit("qst-fired", self.prefix + val)

class QSTExec(QSTText):
    def do_qst(self):
        size_limit = self.config.getint("settings", "qst_size_limit")
        pform = dplatform.get_platform()
        s, o = pform.run_sync(self.text)
        if s:
            print("Qst       : Command failed with status %i" % s)

        return o[:size_limit]

class QSTFile(QSTText):
    def do_qst(self):
        size_limit = self.config.getint("settings", "qst_size_limit")
        try:
            f = NetFile(self.text)
        except:
            print("Qst       : Unable to open file `%s'" % self.text)
            return

        text = f.read()
        f.close()

        return text[:size_limit]

class QSTGPS(QSTText):
    def __init__(self, config, content):
        QSTText.__init__(self, config, content)

        self.prefix = ""
        self.raw = True
        self.mainapp = mainapp.get_mainapp()
        self.fix = None

    def set_fix(self, fix):
        self.fix = fix

    def do_qst(self):
        if not self.fix:
            fix = self.mainapp.get_position()
        else:
            fix = self.fix

        fix.set_station(fix.station, self.text[:20])

        if fix.valid:
            return fix.to_NMEA_GGA()
        else:
            return None

class QSTGPSA(QSTGPS):
    def do_qst(self):
        if not self.fix:
            fix = self.mainapp.get_position()
        else:
            fix = self.fix

        if not "::" in self.text:
            fix.set_station(fix.station, self.text[:20])

        if fix.valid:
            return fix.to_APRS(symtab=self.config.get("settings", "aprssymtab"),
                               symbol=self.config.get("settings", "aprssymbol"))
        else:
            return None

class QSTThreadedText(QSTText):
    def __init__(self, *a, **k):
        QSTText.__init__(self, *a, **k)

        self.thread = None

    def threaded_fire(self):
        msg = self.do_qst()
        self.thread = None

        if not msg:
            print("Qst       : Skipping QST because no data was returned")
            return

        gobject.idle_add(self.emit, "qst-fired", "%s%s" % (self.prefix, msg))

    def fire(self):
        if self.thread:
            print("Qst       : QST thread still running, not starting another")
            return

        # This is a race, but probably pretty safe :)
        self.thread = threading.Thread(target=self.threaded_fire)
        self.thread.setDaemon(True)
        self.thread.start()
        print("Qst       : Started a thread for QST data...")

class QSTRSS(QSTThreadedText):
    def __init__(self, config, content):
        QSTThreadedText.__init__(self, config, content)

        self.last_id = ""

    def do_qst(self):
        rss = feedparser.parse(self.text)

        try:
            entry = rss.entries[-1]
        except IndexError:
            print("Qst       : RSS feed had no entries")
            return None

        try:
            id = entry.id
        except AttributeError:
            # Not all feeds will have an id (I guess)
            id = md5(entry.description)

        if id != self.last_id:
            self.last_id = id
            text = str(entry.description)

            text = re.sub("<[^>]*?>", "", text)
            text = text[:8192]

            return text
        else:
            return None

class QSTCAP(QSTThreadedText):
    def __init__(self, *args, **kwargs):
        QSTThreadedText.__init__(self, *args, **kwargs)

        self.last_date = None

    def determine_starting_item(self):
        cp = cap.CAPParserURL(self.text)
        if cp.events:
            lastev = cp.events[-1]
            delta = datetime.timedelta(seconds=1)
            self.last_date = (lastev.effective - delta)
        else:
            self.last_date = datetime.datetime.now()

    def do_qst(self):
        if self.last_date is None:
            self.determine_starting_item()

        print("Qst       : Last date is %s" % self.last_date)

        cp = cap.CAPParserURL(self.text)
        newev = cp.events_effective_after(self.last_date)
        if not newev:
            return None

        try:
            self.last_date = newev[-1].effective
        except IndexError:
            print("Qst       : CAP feed had no entries")
            return None

        str = ""

        for i in newev:
            print("Qst       : Sending CAP that is effective %s" % i.effective)
            str += "\r\n-----\r\n%s\r\n-----\r\n" % i.report()

        return str        

class QSTWeatherWU(QSTThreadedText):
    #todo susbtitute with a configurable url
    pbase = "http://api.wunderground.com/weatherstation/WXCurrentObXML.asp?ID="
    abase = "http://api.wunderground.com/auto/wui/geo/WXCurrentObXML/index.xml?query="
    def do_qst(self):
        obs = wu.WUObservation()
        
        try:
            t, s = self.text.split("/", 2)
        except Exception, e:
            print("Qst       : Unable to split weather QST %s: %s" % (self.text, e))
            return None

        try:
            if t == _("Airport"):
                base = self.abase
            elif t == _("Personal"):
                base = self.pbase
            else:
                print("Qst       : Unknown QSTWeatherWU type %s" % t)
                return None

            print("Qst       : Getting %s%s for %s/%s" % ( base, self.text, t, s))
            obs.from_uri(base + s)
        except Exception, e:
            print("Qst       : Error getting weather: %s" % e)
            return None

        return str(obs)

class QSTStation(QSTGPSA):
    def get_source(self, name):
        import mainapp
        app = mainapp.get_mainapp() # Hack for this difficult case
        sources = app.map.get_map_sources()

        for source in sources:
            if source.get_name() == name:
                return source

        return None

    def get_station(self, source, station):
        for point in source.get_points():
            if point.get_name() == station:
                return point

        return None

    def do_qst(self):

        try:
            (group, station) = self.text.split("::", 1)
        except Exception, e:
            print("Qst       : QSTStation Error: %s" % e)
            return None

        source = self.get_source(group)
        if source is None:
            print("Qst       : Unknown group %s" % group)
            return

        point = self.get_station(source, station)
        if point is None:
            print("Qst       : Unknown station %s in group %s" % (station, group))
            return

        self.fix = gps.GPSPosition(point.get_latitude(),
                                   point.get_longitude(),
                                   point.get_name())
        self.fix.set_station(self.fix.station,
                             "VIA %s" % self.config.get("user", "callsign"))

        print("Qst       : Sending position for %s/%s: %s" % (group, station, self.fix))

        return QSTGPSA.do_qst(self)

class QSTEditWidget(gtk.VBox):
    def __init__(self, *a, **k):
        gtk.VBox.__init__(self, *a, **k)

        self._id = None

    def to_qst(self):
        pass

    def from_qst(self, content):
        pass

    def __str__(self):
        return "Unknown"

    def reset(self):
        pass

    def to_human(self):
        pass

class QSTTextEditWidget(QSTEditWidget):
    label_text = _("Enter a message:")

    def __init__(self):
        QSTEditWidget.__init__(self, False, 2)

        lab = gtk.Label(self.label_text)
        lab.show()
        self.pack_start(lab, 0, 0, 0)

        self.__tb = gtk.TextBuffer()
        
        ta = gtk.TextView(self.__tb)
        ta.show()

        self.pack_start(ta, 1, 1, 1)

    def __str__(self):
        return self.__tb.get_text(self.__tb.get_start_iter(),
                                  self.__tb.get_end_iter())

    def reset(self):
        self.__tb.set_text("")
    
    def to_qst(self):
        return str(self)

    def from_qst(self, content):
        self.__tb.set_text(content)

    def to_human(self):
        return str(self)

class QSTFileEditWidget(QSTEditWidget):
    label_text = _("Choose a text file.  The contents will be used when the QST is sent.")

    def __init__(self):
        QSTEditWidget.__init__(self, False, 2)
        
        lab = gtk.Label(self.label_text)
        lab.set_line_wrap(True)
        lab.show()
        self.pack_start(lab, 1, 1, 1)
        
        self.__fn = miscwidgets.FilenameBox()
        self.__fn.show()
        self.pack_start(self.__fn, 0, 0, 0)

    def __str__(self):
        return "Read: %s" % self.__fn.get_filename()

    def reset(self):
        self.__fn.set_filename("")

    def to_qst(self):
        return self.__fn.get_filename()

    def from_qst(self, content):
        self.__fn.set_filename(content)

    def to_human(self):
        return self.__fn.get_filename()

class QSTExecEditWidget(QSTFileEditWidget):
    label_text = _("Choose a script to execute.  The output will be used when the QST is sent")

    def __str__(self):
        return "Run: %s" % self.__fn.get_filename()

class QSTGPSEditWidget(QSTEditWidget):
    msg_limit = 20
    type = "GPS"

    def prompt_for_DPRS(self, button):
        dprs = do_dprs_calculator(self.__msg.get_text())
        if dprs is None:
            return
        else:
            self.__msg.set_text(dprs)

    def __init__(self, config):
        QSTEditWidget.__init__(self, False, 2)

        lab = gtk.Label(_("Enter your GPS message:"))
        lab.set_line_wrap(True)
        lab.show()
        self.pack_start(lab, 1, 1, 1)

        hbox = gtk.HBox(False, 2)
        hbox.show()
        self.pack_start(hbox, 0, 0, 0)

        self.__msg = gtk.Entry(self.msg_limit)
        self.__msg.show()
        hbox.pack_start(self.__msg, 1, 1, 1)

        dprs = gtk.Button("DPRS")

        if not isinstance(self, QSTGPSAEditWidget):
            dprs.show()
            self.__msg.set_text(config.get("settings", "default_gps_comment"))
        else:
            self.__msg.set_text("ON D-RATS")

        dprs.connect("clicked", self.prompt_for_DPRS)
        hbox.pack_start(dprs, 0, 0, 0)
        
    def __str__(self):
        return "Message: %s" % self.__msg.get_text()

    def reset(self):
        self.__msg.set_text("")

    def to_qst(self):
        return self.__msg.get_text()

    def from_qst(self, content):
        self.__msg.set_text(content)

    def to_human(self):
        return self.__msg.get_text()

class QSTGPSAEditWidget(QSTGPSEditWidget):
    msg_limit = 20
    type = "GPS-A"

class QSTRSSEditWidget(QSTEditWidget):
    label_string = _("Enter the URL of an RSS feed:")

    def __init__(self):
        QSTEditWidget.__init__(self, False, 2)

        lab = gtk.Label(self.label_string)
        lab.show()
        self.pack_start(lab, 1, 1, 1)

        self.__url = gtk.Entry()
        self.__url.set_text("http://")
        self.__url.show()
        self.pack_start(self.__url, 0, 0, 0)

    def __str__(self):
        return "Source: %s" % self.__url.get_text()

    def to_qst(self):
        return self.__url.get_text()

    def from_qst(self, content):
        self.__url.set_text(content)

    def reset(self):
        self.__url.set_text("")

    def to_human(self):
        return self.__url.get_text()

class QSTCAPEditWidget(QSTRSSEditWidget):
    label_string = _("Enter the URL of a CAP feed:")

class QSTStationEditWidget(QSTEditWidget):
    def ev_group_sel(self, group, station):
        group = group.get_active_text()

        if not self.__sources:
            return

        for src in self.__sources:
            if src.get_name() == group:
                break

        if src.get_name() != group:
            return

        marks = [x.get_name() for x in src.get_points()]
    
        store = station.get_model()
        store.clear()
        for i in sorted(marks):
            station.append_text(i)
        if len(marks):
            station.set_active(0)

    def __init__(self):
        QSTEditWidget.__init__(self, False, 2)

        lab = gtk.Label(_("Choose a station whose position will be sent"))
        lab.show()
        self.pack_start(lab, 1, 1, 1)

        hbox = gtk.HBox(False, 10)

        # This is really ugly, but to fix it requires more work
        self.__sources = mainapp.get_mainapp().map.get_map_sources()
        sources = [x.get_name() for x in self.__sources]
        self.__group = miscwidgets.make_choice(sources,
                                               False,
                                               _("Stations"))
        self.__group.show()
        hbox.pack_start(self.__group, 0, 0, 0)

        self.__station = miscwidgets.make_choice([], False)
        self.__station.show()
        hbox.pack_start(self.__station, 0, 0, 0)

        self.__group.connect("changed", self.ev_group_sel, self.__station)
        self.ev_group_sel(self.__group, self.__station)

        hbox.show()
        self.pack_start(hbox, 0, 0, 0)

    def to_qst(self):
        if not self.__group.get_active_text():
            return None
        elif not self.__station.get_active_text():
            return None
        else:
            return "%s::%s" % (self.__group.get_active_text(),
                               self.__station.get_active_text())

    def to_human(self):
        return "%s::%s" % (self.__group.get_active_text(),
                           self.__station.get_active_text())

class QSTWUEditWidget(QSTEditWidget):
    label_text = _("Enter a WeatherUnderground station ID:")

    def __init__(self):
        QSTEditWidget.__init__(self)

        lab = gtk.Label(self.label_text)
        lab.show()
        self.pack_start(lab, 1, 1, 1)

        hbox = gtk.HBox(False, 2)
        hbox.show()
        self.pack_start(hbox, 0, 0, 0)
        
        self.__station = gtk.Entry()
        self.__station.show()
        hbox.pack_start(self.__station, 0, 0, 0)

        types = [_("Airport"), _("Personal")]
        self.__type = miscwidgets.make_choice(types, False, types[0])
        self.__type.show()
        hbox.pack_start(self.__type, 0, 0, 0)

    def to_qst(self):
        return "%s/%s" % (self.__type.get_active_text(),
                          self.__station.get_text())

    def from_qst(self, content):
        try:
            t, s = content.split("/", 2)
        except:
            print("Qst       : Unable to split `%s'" % content)
            t = _("Airport")
            s = _("UNKNOWN")

        combo_select(self.__type, t)
        self.__station.set_text(s)        

    def to_human(self):
        return self.to_qst()

class QSTEditDialog(gtk.Dialog):
    def _select_type(self, box):
        wtype = box.get_active_text()

        if self.__current:
            self.__current.hide()
        self.__current = self._types[wtype]
        self.__current.show()

    def _make_controls(self):
        hbox = gtk.HBox(False, 2)

        self._type = make_choice(self._types.keys(), False, default=_("Text"))
        self._type.set_size_request(100, -1)
        self._type.show()
        self._type.connect("changed", self._select_type)
        hbox.pack_start(self._type, 0, 0, 0)

        intervals = ["1", "5", "10", "20", "30", "60", ":30", ":15"]
        self._freq = make_choice(intervals, True, default="60")
        self._freq.set_size_request(75, -1)
        self._freq.show()
        hbox.pack_start(self._freq, 0, 0, 0)

        hbox.show()
        return hbox

    def __init__(self, config, ident, parent=None):
        self._types = {
            _("Text") : QSTTextEditWidget(),
            _("File") : QSTFileEditWidget(),
            _("Exec") : QSTExecEditWidget(),
            _("GPS")  : QSTGPSEditWidget(config),
            _("GPS-A"): QSTGPSAEditWidget(config),
            _("RSS")  : QSTRSSEditWidget(),
            _("CAP")  : QSTCAPEditWidget(),
            _("Station") : QSTStationEditWidget(),
            _("Weather (WU)") : QSTWUEditWidget(),
            }

        gtk.Dialog.__init__(self,
                            parent=parent,
                            buttons=(gtk.STOCK_OK, gtk.RESPONSE_OK,
                                     gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL))
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
            self._freq.child.set_text(self._config.get(self._ident, "freq"))
            self._select_type(self._type)
            self.__current.from_qst(self._config.get(self._ident, "content"))
        else:
            self._select_type(self._type)

    def save(self):
        if not self._config.has_section(self._ident):
            self._config.add_section(self._ident)
            self._config.set(self._ident, "enabled", "True")

        self._config.set(self._ident, "freq", self._freq.get_active_text())
        self._config.set(self._ident, "content", self.__current.to_qst())
        self._config.set(self._ident, "type", self._type.get_active_text())

def get_qst_class(typestr):
    classes = {
        _("Text")    : QSTText,
        _("Exec")    : QSTExec,
        _("File")    : QSTFile,
        _("GPS")     : QSTGPS,
        _("GPS-A")   : QSTGPSA,
        _("Station") : QSTStation,
        _("RSS")     : QSTRSS,
        _("CAP")     : QSTCAP,
        _("Weather (WU)") : QSTWeatherWU,
        }

    if not HAVE_FEEDPARSER:
        del classes[_("RSS")]

    return classes.get(typestr, None)
