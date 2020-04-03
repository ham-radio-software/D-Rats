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

import os
import time
from glob import glob
from datetime import datetime

import gobject
import gtk

from d_rats.ui.main_common import MainWindowElement, MainWindowTab
from d_rats.ui.main_common import ask_for_confirmation, set_toolbar_buttons
from d_rats.sessions import rpc
from d_rats.ui import main_events
from d_rats import image
from d_rats import utils
from d_rats import signals
from d_rats import inputdialog

THROB_IMAGE = "throbber.gif"
REMOTE_HINT = _("Enter remote callsign")

class FileView(object):
    def __init__(self, view, path, config):
        self._view = view
        self._path = path

        self._store = gtk.ListStore(gobject.TYPE_OBJECT,
                                    gobject.TYPE_STRING,
                                    gobject.TYPE_INT,
                                    gobject.TYPE_INT)
        self._store.set_sort_column_id(1, gtk.SORT_ASCENDING)
        view.set_model(self._store)

        self._file_icon = config.ship_img("file.png")

        self.outstanding = {}

    def get_path(self):
        return self._path

    def set_path(self, path):
        self._path = path

    def refresh(self):
        pass

    def get_selected_filename(self):
        (model, iter) = self._view.get_selection().get_selected()
        if not iter:
            return None
        return model.get(iter, 1)[0]

    def add_explicit(self, name, size, stamp):
        self._store.append((self._file_icon, name, size, stamp))

    def get_view(self):
        return self._view

class LocalFileView(FileView):
    def refresh(self):
        self._store.clear()
        files = glob(os.path.join(self._path, "*"))
        for file in files:
            if os.path.isdir(file):
                continue
            print "Adding local file `%s'" % file
            try:
                stat = os.stat(file)
                ts = stat.st_mtime
                sz = stat.st_size
                nm = os.path.basename(file)
                self._store.append((self._file_icon, nm, sz, ts))
            except Exception, e:
                print "Failed to add local file: %s" % e

class RemoteFileView(FileView):
    def _file_list_cb(self, job, state, result):
        if state != "complete":
            print "Incomplete job"
            return

        unit_decoder = { "B" : 0,
                         "KB": 10,
                         "MB": 20 }

        # FIXME: This might need to be in the idle loop
        for k,v in result.items():
            if "B (" in v:
                size, units, date, _time = v.split(" ")
                try:
                    size = int(size)
                    size <<= unit_decoder[units]
                    stamp = "%s %s" % (date, _time)
                    ts = time.mktime(time.strptime(stamp,
                                                   "(%Y-%m-%d %H:%M:%S)"))
                except Exception, e:
                    print "Unable to parse file info: %s" % e
                    ts = time.time()
                    size = 0

                self._store.append((self._file_icon, k, size, ts))
            else:
                self._store.append((self._file_icon, k, 0, 0))

    def refresh(self):
        self._store.clear()
        
        job = rpc.RPCFileListJob(self.get_path(), "File list request")
        job.connect("state-change", self._file_list_cb)

        return job

class FilesTab(MainWindowTab):
    __gsignals__ = {
        "event" : signals.EVENT,
        "notice" : signals.NOTICE,
        "submit-rpc-job" : signals.SUBMIT_RPC_JOB,
        "user-send-file" : signals.USER_SEND_FILE,
        "get-station-list" : signals.GET_STATION_LIST,
        "status" : signals.STATUS,
        }

    _signals = __gsignals__

    def _emit(self, *args):
        gobject.idle_add(self.emit, *args)

    def _stop_throb(self):
        throbber, = self._getw("remote_throb")
        pix = self._config.ship_img(THROB_IMAGE)
        throbber.set_from_pixbuf(pix)        

    def _end_list_job(self, job, state, *args):
        if not self._remote:
            return

        if self._remote.get_path() != job.get_dest():
            return

        self._stop_throb()

        if state == "complete" and self._remote:
            self._remote.get_view().set_sensitive(True)
            self.emit("status", "Connected to %s" % job.get_dest())
        else:
            self._disconnect(None, None)

    def _disconnect(self, button, rfview):
        if self._remote:
            view = self._remote.get_view()
            view.set_sensitive(False)
            view.get_model().clear()
        self._remote = None
        ssel, psel = self._get_ssel()
        ssel.set_sensitive(True)
        psel.set_sensitive(True)
        self._stop_throb()
        self.emit("status", "Disconnected")

    def _connect_remote(self, button, rfview):

        view, = self._getw("remote_list")
        ssel, psel = self._get_ssel()
        sta = ssel.get_active_text().upper()
        prt = psel.get_active_text()

        if not sta or sta.upper() == REMOTE_HINT.upper():
            return

        if not self._remote or self._remote.get_path() != sta:
            self._remote = RemoteFileView(view, sta, self._config)

        throbber, = self._getw("remote_throb")
        img = self._config.ship_obj_fn(os.path.join("images", THROB_IMAGE))
        anim = gtk.gdk.PixbufAnimation(img)
        throbber.set_from_animation(anim)

        job = self._remote.refresh()
        if job:
            self.emit("status", "Connecting to %s" % job.get_dest())
            ssel.set_sensitive(False)
            psel.set_sensitive(False)
            job.connect("state-change", self._end_list_job)

            self.emit("submit-rpc-job", job, prt)

    def _refresh_local(self, *args):
        self._local.refresh()

    def refresh_local(self):
        self._notice()
        self._refresh_local()

    def _del(self, button, fileview):
        fname = self._local.get_selected_filename()
        if not fname:
            return

        question = _("Really delete %s?") % fname
        mainwin = self._wtree.get_widget("mainwindow")
        if not ask_for_confirmation(question, mainwin):
            return

        fn = os.path.join(self._config.get("prefs", "download_dir"), fname)
        os.remove(fn)
        self._local.refresh()

    def _upload(self, button, lfview):
        fname = self._local.get_selected_filename()
        if not fname:
            return

        fn = os.path.join(self._config.get("prefs", "download_dir"), fname)

        fnl = fn.lower()
        if fnl.endswith(".jpg") or \
                fnl.endswith(".jpeg") or \
                fnl.endswith(".png") or \
                fnl.endswith(".gif"):
            fn = image.send_image(fn)
            if not fn:
                return

        ssel, psel = self._get_ssel()
        port = psel.get_active_text()

        if self._remote:
            station = self._remote.get_path()
            self._remote.outstanding[fname] = os.stat(fn).st_size
        else:
            station = ssel.get_active_text().upper()

        if not station or station.upper() == REMOTE_HINT.upper():
            return

        self.emit("user-send-file", station, port, fn, fname)

    def _download(self, button, rfview):
        if not self._remote:
            return

        station = self._remote.get_path()
        fn = self._remote.get_selected_filename()

        ssel, psel = self._get_ssel()
        port = psel.get_active_text()

        def log_failure(job, state, result):
            rc = result.get("rc", "Timeout")
            if rc != "OK":
                event = main_events.Event(None, "%s: %s" % (job.get_dest(), rc))
                self._emit("event", event)

        job = rpc.RPCPullFileJob(station, "Request file %s" % fn)
        job.connect("state-change", log_failure)
        job.set_file(fn)

        self.emit("submit-rpc-job", job, port)
        # FIXME: Need an event here

    def _delete(self, button, rfview):
        station = self._remote.get_path()

        d = inputdialog.TextInputDialog()
        d.label.set_text(_("Password for %s (blank if none):" % station))
        d.text.set_visibility(False)
        if d.run() != gtk.RESPONSE_OK:
            return
        passwd = d.text.get_text()
        d.destroy()

        fn = self._remote.get_selected_filename()

        ssel, psel = self._get_ssel()
        port = psel.get_active_text()

        def log_failure(job, state, result):
            rc = result.get("rc", "Timeout")
            event = main_events.Event(None, "%s: %s" % (job.get_dest(), rc))

            job = self._remote.refresh()
            self._emit("submit-rpc-job", job, port)
            self._emit("event", event)

        job = rpc.RPCDeleteFileJob(station, "Delete file %s" % fn)
        job.connect("state-change", log_failure)
        job.set_file(fn)
        job.set_pass(passwd)

        self.emit("submit-rpc-job", job, port)

    def _init_toolbar(self):
        def populate_tb(tb, buttons):
            c = 0
            for i, l, f, d in buttons:
                icon = gtk.Image()
                icon.set_from_pixbuf(i)
                icon.show()
                item = gtk.ToolButton(icon, l)
                item.connect("clicked", f, d)
                try:
                    item.set_tooltip_text(l)
                except AttributeError:
                    pass
                item.show()
                tb.insert(item, c)
                c += 1

        refresh = self._config.ship_img("files-refresh.png")
        connect = self._config.ship_img("connect.png")
        disconnect = self._config.ship_img("disconnect.png")
        delete = self._config.ship_img("msg-delete.png")
        dnload = self._config.ship_img("download.png")
        upload = self._config.ship_img("upload.png")

        ltb, = self._getw("local_toolbar")
        set_toolbar_buttons(self._config, ltb)
        lbuttons = \
            [(refresh, _("Refresh"), self._refresh_local, self._local),
             (delete, _("Delete"), self._del, self._local),
             (upload, _("Upload"), self._upload, self._local),
             ]

        populate_tb(ltb, lbuttons)

        rtb, = self._getw("remote_toolbar")
        set_toolbar_buttons(self._config, rtb)
        rbuttons = \
            [(connect, _("Connect"), self._connect_remote, self._remote),
             (disconnect, _("Disconnect"), self._disconnect, self._remote),
             (dnload, _("Download"), self._download, self._remote),
             (delete, _("Delete"), self._delete, self._remote),
             ]
        
        populate_tb(rtb, rbuttons)

    def _setup_file_view(self, view):
        def render_date(col, rend, model, iter):
            ts, = model.get(iter, 3)
            stamp = datetime.fromtimestamp(ts).strftime("%H:%M:%S %Y-%m-%d")
            rend.set_property("text", stamp)

        def render_size(col, rend, model, iter):
            sz, = model.get(iter, 2)
            if sz < 1024:
                s = "%i B" % sz
            else:
                s = "%.1f KB" % (sz / 1024.0)
            rend.set_property("text", s)

        col = gtk.TreeViewColumn("", gtk.CellRendererPixbuf(), pixbuf=0)
        view.append_column(col)

        col = gtk.TreeViewColumn(_("Filename"), gtk.CellRendererText(), text=1)
        col.set_sort_column_id(1)
        view.append_column(col)

        r = gtk.CellRendererText()
        col = gtk.TreeViewColumn(_("Size"), r, text=2)
        col.set_sort_column_id(2)
        col.set_cell_data_func(r, render_size)
        view.append_column(col)

        r = gtk.CellRendererText()
        col = gtk.TreeViewColumn(_("Date"), r, text=3)
        col.set_sort_column_id(2)
        col.set_cell_data_func(r, render_date)
        view.append_column(col)

    def _refresh_calls(self, stations, ports):
        activeport = ports.get_active()
        if activeport == -1:
            activeport = 0

        stationlist = self.emit("get-station-list")
        _ports = []
        _stations = []

        sstore = stations.get_model()
        sstore.clear()

        pstore = ports.get_model()
        pstore.clear()

        if stationlist:
            for port, stations in stationlist.items():
                _ports.append(port)
                for station in stations:
                    _stations.append(str(station))

            for station in sorted(_stations):
                sstore.append((station,))

            for port in sorted(_ports):
                pstore.append((port,))

        ports.set_active(activeport)

        return self.__selected

    def _get_ssel(self):
        return self._getw("sel_station", "sel_port")

    def __init__(self, wtree, config):
        MainWindowTab.__init__(self, wtree, config, "files")

        lview, rview = self._getw("local_list", "remote_list")

        self._setup_file_view(lview)
        self._setup_file_view(rview)

        stations, = self._getw("sel_station")
        utils.set_entry_hint(stations.child, REMOTE_HINT)

        ddir = self._config.get("prefs", "download_dir")

        self._local = LocalFileView(lview, None, self._config)

        self._remote = None
        rview.set_sensitive(False)

        self._init_toolbar()
        self._stop_throb()

        self.__selected = False

        self.reconfigure()

    def file_sent(self, _fn):
        fn = os.path.basename(_fn)
        if self._remote and self._remote.outstanding.has_key(fn):
            size = self._remote.outstanding[fn]
            del self._remote.outstanding[fn]
            self._remote.add_explicit(fn, size, time.time())

    def reconfigure(self):
        self._local.set_path(self._config.get("prefs", "download_dir"))
        self._local.refresh()

    def selected(self):
        MainWindowTab.selected(self)
        self.__selected = True
        ssel, psel = self._get_ssel()
        self._refresh_calls(ssel, psel)
        gobject.timeout_add(1000, self._refresh_calls, ssel, psel)

    def deselected(self):
        MainWindowTab.deselected(self)
        self.__selected = False
