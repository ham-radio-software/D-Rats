#!/usr/bin/python
'''Main Messages Message List.'''
#
# Copyright 2009 Dan Smith <dsmith@danplanet.com>
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

from __future__ import absolute_import
from __future__ import print_function

import logging
import os
import shutil

from datetime import datetime
from configparser import DuplicateSectionError

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Pango

from d_rats.ui.main_common import MainWindowElement
from d_rats.ui.main_common import display_error
from d_rats.ui.message_folder_info import MessageFolderInfo

from d_rats import formgui
from d_rats import msgrouting


if not '_' in locals():
    import gettext
    _ = gettext.gettext


class MessageInfo():
    '''
    Message information.

    :param filename: Filename of message
    :type filename: str
    :param info: Information about the folder for the message
    :type info: :class:`MessageFolderInfo`
    '''

    def __init__(self, filename, info):
        self._filename = filename
        self._info = info

    @property
    def filename(self):
        '''
        Filename Property.

        :returns: Filename
        :rtype: str
        '''
        return self._filename

    @property
    def info(self):
        '''
        Folder Information Property.

        :param info: Information about the folder for the message
        :type info: :class:`MessageFolderInfo`
        '''
        return self._info


ML_COL_ICON = 0
ML_COL_SEND = 1
ML_COL_SUBJ = 2
ML_COL_TYPE = 3
ML_COL_DATE = 4
ML_COL_FILE = 5
ML_COL_READ = 6
ML_COL_RECP = 7


class MessageList(MainWindowElement):
    '''
    Message List.

    :param wtree: Window Tree Object.
    :param config: Configuration object
    :type config: :class:`DratsConfig`
    '''

    __gsignals__ = {"prompt-send-form" : (GObject.SignalFlags.RUN_LAST,
                                          GObject.TYPE_NONE,
                                          (GObject.TYPE_STRING,)),
                    "reply-form" : (GObject.SignalFlags.RUN_LAST,
                                    GObject.TYPE_NONE,
                                    (GObject.TYPE_STRING,)),
                    "delete-form" : (GObject.SignalFlags.RUN_LAST,
                                     GObject.TYPE_NONE,
                                     (GObject.TYPE_STRING,)),
                    }

    def __init__(self, wtree, config):
        MainWindowElement.__init__(self, wtree, config, "msg")

        self.logger = logging.getLogger("MessageList")
        msglist = self._get_widget("msglist")

        self.store = Gtk.ListStore(GObject.TYPE_OBJECT,
                                   GObject.TYPE_STRING,
                                   GObject.TYPE_STRING,
                                   GObject.TYPE_STRING,
                                   GObject.TYPE_INT,
                                   GObject.TYPE_STRING,
                                   GObject.TYPE_BOOLEAN,
                                   GObject.TYPE_STRING)
        msglist.set_model(self.store)
        msglist.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)
        msglist.enable_model_drag_source(Gdk.ModifierType.BUTTON1_MASK,
                                         [("text/d-rats_message", 0, 0)],
                                         Gdk.DragAction.DEFAULT|
                                         Gdk.DragAction.MOVE)
        msglist.connect("drag-data-get", self._dragged_from)

        col = Gtk.TreeViewColumn("", Gtk.CellRendererPixbuf(), pixbuf=0)
        msglist.append_column(col)

        renderer = Gtk.CellRendererText()
        renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
        col = Gtk.TreeViewColumn(_("Sender"), renderer, text=ML_COL_SEND)
        col.set_cell_data_func(renderer, self._bold_if_unread, ML_COL_SEND)
        col.set_sort_column_id(ML_COL_SEND)
        col.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        col.set_resizable(True)
        msglist.append_column(col)

        renderer = Gtk.CellRendererText()
        renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
        col = Gtk.TreeViewColumn(_("Recipient"), renderer, text=ML_COL_RECP)
        col.set_cell_data_func(renderer, self._bold_if_unread, ML_COL_RECP)
        col.set_sort_column_id(ML_COL_RECP)
        col.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        col.set_resizable(True)
        msglist.append_column(col)

        renderer = Gtk.CellRendererText()
        renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
        col = Gtk.TreeViewColumn(_("Subject"), renderer, text=ML_COL_SUBJ)
        col.set_cell_data_func(renderer, self._bold_if_unread, ML_COL_SUBJ)
        col.set_expand(True)
        col.set_sort_column_id(ML_COL_SUBJ)
        col.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        col.set_resizable(True)
        msglist.append_column(col)

        renderer = Gtk.CellRendererText()
        renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
        col = Gtk.TreeViewColumn(_("Type"), renderer, text=ML_COL_TYPE)
        col.set_cell_data_func(renderer, self._bold_if_unread, ML_COL_TYPE)
        col.set_sort_column_id(ML_COL_TYPE)
        col.set_resizable(True)
        msglist.append_column(col)

        renderer = Gtk.CellRendererText()
        renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
        col = Gtk.TreeViewColumn(_("Date"), renderer, text=ML_COL_DATE)
        col.set_cell_data_func(renderer, self._render_date)
        col.set_sort_column_id(ML_COL_DATE)
        col.set_resizable(True)
        msglist.append_column(col)

        msglist.connect("row-activated", self._open_msg)
        self.store.set_sort_column_id(ML_COL_DATE, Gtk.SortType.DESCENDING)

        self.message_pixbuf = self._config.ship_img("message.png")
        self.unread_pixbuf = self._config.ship_img("msg-markunread.png")
        self.current_info = None

    @staticmethod
    def _bold_if_unread(_col, rend, model, msg_iter, cnum):
        val, read, = model.get(msg_iter, cnum, ML_COL_READ)
        if not val:
            val = ""
        if not read:
            val = val.replace("&", "&amp;")
            val = val.replace("<", "&lt;")
            val = val.replace(">", "&gt;")
            rend.set_property("markup", "<b>%s</b>" % val)

    def _folder_path(self, folder):
        path = os.path.join(self._config.platform.config_dir(),
                            "messages",
                            folder)
        if not os.path.isdir(path):
            return None
        return path

    def open_msg(self, filename, editable, call_back=None, cbdata=None):
        '''
        Open a message.

        :param filename: Filename for message
        :type filename: str
        :param editable: If message can be edited
        :type editable: bool
        :param call_back: Callback for message
        :type call_back: function(:class:`Gtk.ResponseType`, any)
        :param cbdata: Call back data
        :type cbdata: any
        :returns: response
        :rtype: :class:`Gtk.ResponseType`
        '''
        if not msgrouting.msg_lock(filename):
            display_error(_("Unable to open: message in use by another task"))
            return Gtk.ResponseType.CANCEL

        parent = self._wtree.get_object("mainwindow")
        form = formgui.FormDialog(_("Form"), filename,
                                  config=self._config, parent=parent)
        form.configure(self._config)

        def form_done(dlg, response, msg_info):
            '''
            Form Done response event handler.

            :param dlg: Message Info dialog
            :param dlg: :class:`formgui.FormDialog`
            :param response: response from dialog
            :type response: :class:`Gtk.ResponseType`
            :param msg_info: Message info
            :type msg_info: :class:`MessageInfo`
            '''
            saveable_actions = [formgui.RESPONSE_SAVE,
                                formgui.RESPONSE_SEND,
                                formgui.RESPONSE_SEND_VIA,
                                ]
            dlg.hide()
            dlg.update_dst()
            filename = msg_info.filename
            info = msg_info.info
            if msgrouting.msg_is_locked(filename):
                msgrouting.msg_unlock(filename)
            if response in saveable_actions:
                self.logger.info("open_msg: Saving to %s", filename)
                dlg.save_to(filename)
            else:
                self.logger.info("open_msg : Not saving")
            dlg.destroy()
            self.refresh(filename)
            if call_back:
                call_back(response, cbdata)
            if response == formgui.RESPONSE_SEND:
                self.move_message(info, filename, _("Outbox"))
            elif response == formgui.RESPONSE_SEND_VIA:
                filename = self.move_message(info, filename, _("Outbox"))
                self.emit("prompt-send-form", filename)
            elif response == formgui.RESPONSE_REPLY:
                self.emit("reply-form", filename)
            elif response == formgui.RESPONSE_DELETE:
                self.emit("delete-form", filename)

        form.build_gui(editable)
        form.show()
        msg_info = MessageInfo(filename, self.current_info)
        form.connect("response", form_done, msg_info)
        return Gtk.ResponseType.OK

    def _open_msg(self, view, path, _col):
        '''
        Open Message row-activated event handler.

        :param view: View that signaled event
        :type view: :class:`Gtk.TreeView`
        :param path: Path for the activated row
        :type path: :class:`Gtk.TreePath`
        :param _col: The column for the row
        :type _col: :class:`Gtk.TreeViewColumn`
        '''
        store = view.get_model()
        msg_iter = store.get_iter(path)
        path, = store.get(msg_iter, ML_COL_FILE)

        def close_msg_cb(response, info):
            if self.current_info == info:
                msg_iter = self.iter_from_fn(path)
                self.logger.info("_open_msg: Updating iter for close %s",
                                 msg_iter)
                if msg_iter:
                    self._update_message_info(msg_iter)
            else:
                self.logger.info("_open_msg: Not current, not updating")

        editable = "Outbox" in path or "Drafts" in path # Dirty hack
        self.open_msg(path, editable, close_msg_cb, self.current_info)
        self.current_info.set_msg_read(path, True)
        msg_iter = self.iter_from_fn(path)
        self.logger.info("_open_msg: Updating iter %s", msg_iter)
        if msg_iter:
            self._update_message_info(msg_iter)

    @staticmethod
    def _render_date(_col, rend, model, msg_iter, _data):
        time_stamp, read = model.get(msg_iter, ML_COL_DATE, ML_COL_READ)
        stamp = datetime.fromtimestamp(
            time_stamp).strftime("%H:%M:%S %Y-%m-%d")
        if read:
            rend.set_property("text", stamp)
        else:
            rend.set_property("markup", "<b>%s</b>" % stamp)

    def _dragged_from(self, view, _ctx, sel, _info, _ts):
        '''
        Dragged From drag-data-get event handler.

        :param view: Widget getting signal
        :type view: :class:`Gtk.TreeView`
        :param _ctx: Context value, unused
        :type _ctx: :class:`Gtk.DragContext`
        :param sel: Selection containing the dragged data
        :type sel: :class:`Gtk.SelectionData`
        :param _info: Information registered in the Gtk.TargetList, unused
        :param _ts: timestamp of when the data was requested, unused
        '''
        store, paths = view.get_selection().get_selected_rows()

        msgs = [os.path.dirname(store[paths[0]][ML_COL_FILE])]
        for path in paths:
            data = "%s\0%s\0%s\0%s\0%s\0%s" % (store[path][ML_COL_FILE],
                                               store[path][ML_COL_SUBJ],
                                               store[path][ML_COL_TYPE],
                                               store[path][ML_COL_READ],
                                               store[path][ML_COL_SEND],
                                               store[path][ML_COL_RECP])
            msgs.append(data)

        data = "\x01".join(msgs)
        byte_data = data.encode('ISO-8859-1')
        sel.set(sel.get_target(), 0, byte_data)
        GLib.idle_add(self.refresh)


    def _update_message_info(self, msg_iter, force=False):
        fname, = self.store.get(msg_iter, ML_COL_FILE)

        subj = self.current_info.get_msg_subject(fname)
        read = self.current_info.get_msg_read(fname)
        if subj == _("Unknown") or force:
            # Not registered, so update the registry
            form = formgui.FormFile(fname)
            self.current_info.set_msg_type(fname, form.ident)
            self.current_info.set_msg_read(fname, read)
            self.current_info.set_msg_subject(fname, form.get_subject_string())
            self.current_info.set_msg_sender(fname, form.get_sender_string())
            self.current_info.set_msg_recip(fname, form.get_recipient_string())

        time_stamp = os.stat(fname).st_ctime
        if read:
            icon = self.message_pixbuf
        else:
            icon = self.unread_pixbuf
        self.store.set(msg_iter,
                       ML_COL_ICON, icon,
                       ML_COL_SEND, self.current_info.get_msg_sender(fname),
                       ML_COL_RECP, self.current_info.get_msg_recip(fname),
                       ML_COL_SUBJ, self.current_info.get_msg_subject(fname),
                       ML_COL_TYPE, self.current_info.get_msg_type(fname),
                       ML_COL_DATE, time_stamp,
                       ML_COL_READ, read)

    def iter_from_fn(self, file_name):
        '''
        Iterate from file name.

        :param file_name: File Name to lookup
        :type file_name: str
        :returns: Iterated file name with each call
        :rtype: :class:`Gtk.TreeIter`
        '''
        fn_iter = self.store.get_iter_first()
        while fn_iter:
            _fn, = self.store.get(fn_iter, ML_COL_FILE)
            if _fn == file_name:
                break
            fn_iter = self.store.iter_next(fn_iter)

        return fn_iter

    def refresh(self, file_name=None):
        '''
        Refresh the current folder or optional filename.

        :param file_name: File name, default None
        :type file_name: str
        '''
        if file_name is None:
            self.store.clear()
            for msg in self.current_info.files():
                msg_iter = self.store.append()
                self.store.set(msg_iter, ML_COL_FILE, msg)
                self._update_message_info(msg_iter)
        else:
            msg_iter = self.iter_from_fn(file_name)
            if not msg_iter:
                msg_iter = self.store.append()
                self.store.set(msg_iter,
                               ML_COL_FILE, file_name)

            self._update_message_info(msg_iter, True)

    def open_folder(self, path):
        '''
        Open a folder by path.

        :param path: Folder to open
        :type path: str
        '''
        self.current_info = MessageFolderInfo(self._folder_path(path))
        self.refresh()

    def delete_selected_messages(self):
        '''Delete Selected Messages.'''
        msglist = self._get_widget("msglist")

        iters = []
        (store, paths) = msglist.get_selection().get_selected_rows()
        for path in paths:
            iters.append(store.get_iter(path))

        for msg_iter in iters:
            file_name, = store.get(msg_iter, ML_COL_FILE)
            store.remove(msg_iter)
            self.current_info.delete(file_name)

    def move_message(self, info, path, new_folder):
        '''
        Move message into folder.

        :param info: Message information
        :type info: :class:`MessageFolderInfo`
        :param path: Source folder
        :type path: str
        :param new_folder: Destination Folder
        :type new_folder: str
        :returns: The new folder name on success, the source folder on failure
        :rtype: str
        '''
        dest = MessageFolderInfo(self._folder_path(new_folder))
        try:
            newfn = dest.create_msg(os.path.basename(path))
        except DuplicateSectionError:
            # Same folder, or duplicate message id
            return path

        self.logger.info("move_message Moving %s -> %s", path, newfn)
        shutil.copy(path, newfn)
        info.delete(path)

        if info == self.current_info:
            self.refresh()

        return newfn

    def move_selected_messages(self, folder):
        '''
        Move selected messages into folder.

        :param folder: Destination folder
        :type folder: str
        '''
        for msg in self.get_selected_messages():
            self.move_message(self.current_info, msg, folder)

    def get_selected_messages(self):
        '''
        Get selected messages.

        :returns: List of selected messages
        :rtype: list
        '''
        msglist = self._get_widget("msglist")

        selected = []
        (store, paths) = msglist.get_selection().get_selected_rows()
        for path in paths:
            selected.append(store[path][ML_COL_FILE])

        return selected
