#!/usr/bin/python
'''Main Files'''
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

import logging
import os
import time
from glob import glob
from datetime import datetime

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GdkPixbuf
from gi.repository import Gtk
from gi.repository import GObject
from gi.repository import GLib

from d_rats.ui.main_common import MainWindowTab
from d_rats.ui.main_common import ask_for_confirmation, set_toolbar_buttons
from d_rats.sessions import rpc
from d_rats.ui import main_events
from d_rats import image
from d_rats import utils
from d_rats import signals
from d_rats import inputdialog


if not '_' in locals():
    import gettext
    _ = gettext.gettext


THROB_IMAGE = "throbber.gif"
REMOTE_HINT = _("Enter remote callsign")

class FileView():
    '''
    FileView

    :param view: view object
    :param path: path to view files on
    :param config: Configuration data
    :type config: :class:`DratsConfig`
    '''
    def __init__(self, view, path, config):
        self._view = view
        self._path = path

        self._store = Gtk.ListStore(GObject.TYPE_OBJECT,
                                    GObject.TYPE_STRING,
                                    GObject.TYPE_INT,
                                    GObject.TYPE_INT)
        self._store.set_sort_column_id(1, Gtk.SortType.ASCENDING)
        view.set_model(self._store)

        self._file_icon = config.ship_img("file.png")

        self.outstanding = {}

    def get_path(self):
        '''Get the Path.'''
        return self._path

    def set_path(self, path):
        '''
        Set Path

        :param path: Path to set.
        '''
        self._path = path

    def refresh(self):
        '''Refresh'''

    def get_selected_filename(self):
        '''
        Get Selected Filename.

        :returns: Filaname if a filename is selected or None
        '''
        (model, file_name_iter) = self._view.get_selection().get_selected()
        if not file_name_iter:
            return None
        return model.get(file_name_iter, 1)[0]

    def add_explicit(self, name, size, stamp):
        '''
        Add Explicit Filename.

        :param name: Name of file to add
        :param size: Size of file to add
        :param stamp: Time stamp of file.
        '''
        self._store.append((self._file_icon, name, size, stamp))

    def get_view(self):
        '''Get View'''
        return self._view


class LocalFileView(FileView):
    '''
    Local File View.

    :param view: view object
    :param path: path to view files on
    :param config: Configuration data
    :type config: :class:`DratsConfig`
    '''
    def __init__(self, view, path, config):
        FileView.__init__(self, view, path, config)
        self.logger = logging.getLogger("LocalFileV")

    def refresh(self):
        '''Refresh'''
        self._store.clear()
        files = glob(os.path.join(self._path, "*"))
        for file in files:
            if os.path.isdir(file):
                continue
            self.logger.info("refresh: Adding local file `%s'", file)
            try:
                stat = os.stat(file)
                time_stamp = stat.st_mtime
                size = stat.st_size
                name = os.path.basename(file)
                self._store.append((self._file_icon, name, size, time_stamp))
            # pylint: disable=broad-except
            except Exception:
                self.logger.info("refresh : Failed to add local file: %s",
                                 "broad-except", exc_info=True)


class RemoteFileView(FileView):
    '''
    Remote File View.

    :param view: view object
    :param path: path to view files on
    :param config: Configuration data
    :type config: :class:`DratsConfig`
    '''

    def __init__(self, view, path, config):
        FileView.__init__(self, view, path, config)
        self.logger = logging.getLogger("RemoteFileV")

    # pylint: disable=too-many-locals
    def _file_list_cb(self, job, state, result):
        if state != "complete":
            self.logger.info("_file_list_cb : Incomplete job")
            return

        unit_decoder = {u"B" : 0,
                        u"KB": 10,
                        u"MB": 20}

        # pylint: disable=fixme
        # FIXME: This might need to be in the idle loop
        for key, value in result.copy().items():
            if "B (" in value:
                size_str, units, file_date, file_time = value.split(" ")
                size = 0
                try:
                    size = int(size_str)
                except ValueError:
                    self.logger.info("_file_list_cb:"
                                     " Unable to parse file size",
                                     exc_info=True)
                try:
                    units_str = units.decode('utf-8', 'replace')
                    size <<= unit_decoder[units_str]
                except KeyError:
                    self.logger.info("_file_list_cb:"
                                     " Unable to parse file size units:",
                                     exc_info=True)
                    size = 0
                try:
                    stamp = "%s %s" % (file_date, file_time)
                    time_stamp = time.mktime(
                        time.strptime(stamp, "(%Y-%m-%d %H:%M:%S)"))
                except (OverflowError, ValueError):
                    self.logger.info("_file_list_cb:"
                                     " Unable to parse file time info: %s",
                                     exc_info=True)
                    time_stamp = time.time()

                self._store.append((self._file_icon, key, size, time_stamp))
            else:
                self._store.append((self._file_icon, key, 0, 0))

    def refresh(self):
        '''
        Refresh.

        :returns: Job information
        :rtype: :class:`RPCFileListJob`
        '''
        self._store.clear()

        job = rpc.RPCFileListJob(self.get_path(), "File list request")
        job.connect("state-change", self._file_list_cb)

        return job


class FilesTab(MainWindowTab):
    '''
    Files Tab.

    :param view: view object
    :param path: path to view files on
    :type path: str
    :param config: Configuration data
    :type config: :class:`DratsConfig`
    '''

    __gsignals__ = {
        "event" : signals.EVENT,
        "notice" : signals.NOTICE,
        "submit-rpc-job" : signals.SUBMIT_RPC_JOB,
        "user-send-file" : signals.USER_SEND_FILE,
        "get-station-list" : signals.GET_STATION_LIST,
        "status" : signals.STATUS,
        }

    _signals = __gsignals__

    def __init__(self, wtree, config):
        MainWindowTab.__init__(self, wtree, config, "files", _("Files"))
        self.logger = logging.getLogger("FilesTab")

        # pylint: disable=unbalanced-tuple-unpacking
        lview, rview = self._getw("local_list", "remote_list")

        self._setup_file_view(lview)
        self._setup_file_view(rview)

        # pylint: disable=fixme
        # TODO
        # Not sure how to make this work for GTK+ ComboBox
        # Can live with out a hint while debuging
        stations, = self._getw("sel_station")
        stn_entry = stations.get_child()
        utils.set_entry_hint(stn_entry, REMOTE_HINT)

        _ddir = self._config.get("prefs", "download_dir")

        self._local = LocalFileView(lview, None, self._config)

        self._remote = None
        rview.set_sensitive(False)

        self._init_toolbar()
        self._stop_throb()

        self.__selected = False

        self.reconfigure()

    def _emit(self, *args):
        GObject.idle_add(self.emit, *args)

    def _stop_throb(self):
        # pylint: disable=unbalanced-tuple-unpacking
        throbber, = self._getw("remote_throb")
        pix = self._config.ship_img(THROB_IMAGE)
        throbber.set_from_pixbuf(pix)

    def _end_list_job(self, job, state, *_args):
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

    def _disconnect(self, _button, _rfview):
        if self._remote:
            view = self._remote.get_view()
            view.set_sensitive(False)
            view.get_model().clear()
        self._remote = None
        # pylint: disable=unbalanced-tuple-unpacking
        ssel, psel = self._get_ssel()
        ssel.set_sensitive(True)
        psel.set_sensitive(True)
        self._stop_throb()
        self.emit("status", "Disconnected")

    def _connect_remote(self, _button, _rfview):

        # pylint: disable=unbalanced-tuple-unpacking
        view, = self._getw("remote_list")
        # pylint: disable=unbalanced-tuple-unpacking
        ssel, psel = self._get_ssel()
        sta = ssel.get_active_text().upper()
        prt = psel.get_active_text()

        if not sta or sta.upper() == REMOTE_HINT.upper():
            return

        if not self._remote or self._remote.get_path() != sta:
            self._remote = RemoteFileView(view, sta, self._config)

        # pylint: disable=unbalanced-tuple-unpacking
        throbber, = self._getw("remote_throb")
        img = self._config.ship_obj_fn(os.path.join("images", THROB_IMAGE))
        anim = GdkPixbuf.PixbufAnimation.new_from_file(img)
        throbber.set_from_animation(anim)

        job = self._remote.refresh()
        if job:
            self.emit("status", "Connecting to %s" % job.get_dest())
            ssel.set_sensitive(False)
            psel.set_sensitive(False)
            job.connect("state-change", self._end_list_job)

            self.emit("submit-rpc-job", job, prt)

    def _refresh_local(self, *_args):
        self._local.refresh()

    def refresh_local(self):
        '''Refresh Local'''
        self._notice()
        self._refresh_local()

    def _del(self, _button, _fileview):
        fname = self._local.get_selected_filename()
        if not fname:
            return

        question = _("Really delete %s?") % fname
        mainwin = self._wtree.get_object("mainwindow")
        if not ask_for_confirmation(question, mainwin):
            return

        file_name = os.path.join(self._config.get("prefs", "download_dir"),
                                 fname)
        os.remove(file_name)
        self._local.refresh()

    def _upload(self, _button, _lfview):
        fname = self._local.get_selected_filename()
        if not fname:
            return

        file_name = os.path.join(self._config.get("prefs", "download_dir"),
                                 fname)

        fnl = file_name.lower()
        if fnl.endswith(".jpg") or \
                fnl.endswith(".jpeg") or \
                fnl.endswith(".png") or \
                fnl.endswith(".gif"):
            file_name = image.send_image(file_name)
            if not file_name:
                return

        # pylint: disable=unbalanced-tuple-unpacking
        ssel, psel = self._get_ssel()
        port = psel.get_active_text()

        if self._remote:
            station = self._remote.get_path()
            self._remote.outstanding[fname] = os.stat(file_name).sit_size
        else:
            station = ssel.get_active_text().upper()

        if not station or station.upper() == REMOTE_HINT.upper():
            return

        self.emit("user-send-file", station, port, file_name, fname)

    def _download(self, _button, _rfview):
        if not self._remote:
            return

        station = self._remote.get_path()
        file_name = self._remote.get_selected_filename()

        # pylint: disable=unbalanced-tuple-unpacking
        _ssel, psel = self._get_ssel()
        port = psel.get_active_text()

        def log_failure(job, _state, result):
            result_code = result.get("rc", "Timeout")
            if result_code != "OK":
                event = main_events.Event(None, "%s: %s" % (job.get_dest(),
                                                            result_code))
                self._emit("event", event)

        job = rpc.RPCPullFileJob(station, "Request file %s" % file_name)
        job.connect("state-change", log_failure)
        job.set_file(file_name)

        self.emit("submit-rpc-job", job, port)
        # pylint: disable=fixme
        # FIXME: Need an event here

    def _delete(self, _button, _rfview):
        station = self._remote.get_path()

        dialog = inputdialog.TextInputDialog()
        dialog.label.set_text(_("Password for %s (blank if none):" % station))
        dialog.text.set_visibility(False)
        if dialog.run() != Gtk.ResponseType.OK:
            return
        passwd = dialog.text.get_text()
        dialog.destroy()

        file_name = self._remote.get_selected_filename()

        # pylint: disable=unbalanced-tuple-unpacking
        _ssel, psel = self._get_ssel()
        port = psel.get_active_text()

        def log_failure(job, _state, result):
            result_code = result.get("rc", "Timeout")
            event = main_events.Event(None, "%s: %s" % (job.get_dest(),
                                                        result_code))

            job = self._remote.refresh()
            self._emit("submit-rpc-job", job, port)
            self._emit("event", event)

        job = rpc.RPCDeleteFileJob(station, "Delete file %s" % file_name)
        job.connect("state-change", log_failure)
        job.set_file(file_name)
        job.set_pass(passwd)

        self.emit("submit-rpc-job", job, port)

    def _init_toolbar(self):
        def populate_tb(toolbar, buttons):
            count = 0
            for button_i, button_l, button_f, button_d in buttons:
                icon = Gtk.Image()
                icon.set_from_pixbuf(button_i)
                icon.show()
                item = Gtk.ToolButton.new(icon, button_l)
                item.connect("clicked", button_f, button_d)
                try:
                    item.set_tooltip_text(button_l)
                except AttributeError:
                    pass
                item.show()
                toolbar.insert(item, count)
                count += 1

        refresh = self._config.ship_img("files-refresh.png")
        connect = self._config.ship_img("connect.png")
        disconnect = self._config.ship_img("disconnect.png")
        delete = self._config.ship_img("msg-delete.png")
        dnload = self._config.ship_img("download.png")
        upload = self._config.ship_img("upload.png")

        # pylint: disable=unbalanced-tuple-unpacking
        ltb, = self._getw("local_toolbar")
        set_toolbar_buttons(self._config, ltb)
        lbuttons = \
            [(refresh, _("Refresh"), self._refresh_local, self._local),
             (delete, _("Delete"), self._del, self._local),
             (upload, _("Upload"), self._upload, self._local),
             ]

        populate_tb(ltb, lbuttons)

        # pylint: disable=unbalanced-tuple-unpacking
        rtb, = self._getw("remote_toolbar")
        set_toolbar_buttons(self._config, rtb)
        rbuttons = \
            [(connect, _("Connect"), self._connect_remote, self._remote),
             (disconnect, _("Disconnect"), self._disconnect, self._remote),
             (dnload, _("Download"), self._download, self._remote),
             (delete, _("Delete"), self._delete, self._remote),
             ]

        populate_tb(rtb, rbuttons)

    # pylint: disable=no-self-use
    def _setup_file_view(self, view):
        def render_date(_col, rend, model, file_iter, _data):
            time_stamp, = model.get(file_iter, 3)
            stamp = datetime.fromtimestamp(
                time_stamp).strftime("%H:%M:%S %Y-%m-%d")
            rend.set_property("text", stamp)

        def render_size(_col, rend, model, file_iter, _data):
            size, = model.get(file_iter, 2)
            if size < 1024:
                size_text = "%i B" % size
            else:
                size_text = "%.1f KB" % (size / 1024.0)
            rend.set_property("text", size_text)

        col = Gtk.TreeViewColumn("", Gtk.CellRendererPixbuf(), pixbuf=0)
        view.append_column(col)

        col = Gtk.TreeViewColumn(_("Filename"), Gtk.CellRendererText(), text=1)
        col.set_sort_column_id(1)
        view.append_column(col)

        renderer = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn(_("Size"), renderer, text=2)
        col.set_sort_column_id(2)
        col.set_cell_data_func(renderer, render_size)
        view.append_column(col)

        renderer = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn(_("Date"), renderer, text=3)
        col.set_sort_column_id(3)
        col.set_cell_data_func(renderer, render_date)
        view.append_column(col)

    def _refresh_calls(self, file_sel_stations, file_sel_ports):
        activeport = file_sel_ports.get_active()
        if activeport == -1:
            activeport = 0

        stationlist = self.emit("get-station-list")
        _ports = []
        _stations = []

        file_sel_stations.remove_all()

        file_sel_ports.remove_all()

        if stationlist:
            for port, stations in stationlist.copy().items():
                _ports.append(port)
                for station in stations:
                    _stations.append(str(station))

            for station in sorted(_stations):
                file_sel_stations.append_text(station)

            for port in sorted(_ports):
                file_sel_ports.append_text(port)

        file_sel_ports.set_active(activeport)

        return self.__selected

    def _get_ssel(self):
        return self._getw("sel_station", "sel_port")

    def file_sent(self, name):
        '''
        Mark a file as sent.

        :param name: File name that was sent
        :type name: str
        '''
        file_name = os.path.basename(name)
        if self._remote and file_name in self._remote.outstanding:
            size = self._remote.outstanding[file_name]
            del self._remote.outstanding[file_name]
            self._remote.add_explicit(file_name, size, time.time())

    def reconfigure(self):
        '''Reconfigure.'''
        self._local.set_path(self._config.get("prefs", "download_dir"))
        self._local.refresh()

    def selected(self):
        '''Selected.'''
        MainWindowTab.selected(self)
        self.__selected = True
        # pylint: disable=unbalanced-tuple-unpacking
        ssel, psel = self._get_ssel()
        self._refresh_calls(ssel, psel)
        GLib.timeout_add(1000, self._refresh_calls, ssel, psel)

    def deselected(self):
        '''Deselected.'''
        MainWindowTab.deselected(self)
        self.__selected = False
