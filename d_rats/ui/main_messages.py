#!/usr/bin/python
'''Main Messages'''
# pylint: disable=too-many-lines
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
import time
import shutil
import random
# import glob
from glob import glob
from datetime import datetime
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Pango

# pyright: reportMissingModuleSource=false
from six.moves.configparser import ConfigParser
from six.moves.configparser import DuplicateSectionError
from six.moves.configparser import NoOptionError
from six.moves.configparser import NoSectionError
from d_rats.ui.main_common import MainWindowElement, MainWindowTab
from d_rats.ui.main_common import prompt_for_station, \
    display_error, prompt_for_string, set_toolbar_buttons
# from d_rats.ui import main_events
from d_rats import inputdialog
from d_rats import formgui
# from d_rats import emailgw
from d_rats.utils import log_exception
from d_rats import signals
from d_rats import msgrouting
# from d_rats import wl2k

_FOLDER_CACHE = {}

if not '_' in locals():
    import gettext
    _ = gettext.gettext

BASE_FOLDERS = [_("Inbox"), _("Outbox"), _("Sent"), _("Trash"), _("Drafts")]


class MainMessageException(Exception):
    '''Generic Main Message Exception.'''


class FolderError(MainMessageException):
    '''Error accessing a folder.'''


def mkmsgid(callsign):
    '''
    Generate a message id for a callsign.

    :param callsign: Callsign of station
    :rtype: str
    :returns: Message id
    :rtype: str
    '''
    r_num = random.SystemRandom().randint(0, 100000)
    return "%s.%x.%x" % (callsign, int(time.time()) - 1114880400, r_num)


class MessageFolderInfo():
    '''
    Message Folder Info.

    :param folder_path: Folder to operate on
    :type folder_path: str
    '''

    def __init__(self, folder_path):
        self._path = folder_path

        self.logger = logging.getLogger("MessageFolderInfo")
        if folder_path in _FOLDER_CACHE:
            self._config = _FOLDER_CACHE[folder_path]
        else:
            self._config = ConfigParser()
            regpath = os.path.join(self._path, ".db")
            if os.path.exists(regpath):
                self._config.read(regpath)
            self._save()
            _FOLDER_CACHE[folder_path] = self._config

    def _save(self):
        regpath = os.path.join(self._path, ".db")
        file_handle = open(regpath, "w")
        self._config.write(file_handle)
        file_handle.close()

    def name(self):
        '''
        Folder Name.

        :returns: Current Folder name
        :rtype: str
        '''
        return os.path.basename(self._path)

    def _setprop(self, filename, prop, value):
        filename = os.path.basename(filename)

        if not self._config.has_section(filename):
            self._config.add_section(filename)

        self._config.set(filename, prop, value)
        self._save()

    def _getprop(self, filename, prop):
        filename = os.path.basename(filename)

        try:
            return self._config.get(filename, prop)
        except (NoOptionError, NoSectionError):
            return _("Unknown")

    def get_msg_subject(self, filename):
        '''
        Get message subject.

        :param filename: Filename for message
        :type filename: str
        :returns: Subject of message
        :rtype: str
        '''
        return self._getprop(filename, "subject")

    def set_msg_subject(self, filename, subject):
        '''
        Set message subject.

        :param filename: Filename for message
        :type filename: str
        :param subject: Subject for message
        :type subject: str
        '''
        self._setprop(filename, "subject", subject)

    def get_msg_type(self, filename):
        '''
        Get message type.

        :param filename: Filename for message
        :type filename: str
        :returns: Message Type
        :rtype: str
        '''
        return self._getprop(filename, "type")

    def set_msg_type(self, filename, msg_type):
        '''
        Set message type.

        :param filename: Filename for message
        :type filename: str
        :param msg_type: Type of message
        :type msg_type: str
        '''
        self._setprop(filename, "type", msg_type)

    def get_msg_read(self, filename):
        '''
        Get message read status.

        :param filename: Filename for message
        :type filename: str
        :returns: True if message has been read
        :rtype: bool
        '''
        val = self._getprop(filename, "read")
        return val == "True"

    def set_msg_read(self, filename, read):
        '''
        Set message read status.

        :param filename: Filename of message
        :type filename: str
        :param read: True for message to be marked read
        :type read: bool
        '''
        self._setprop(filename, "read", str(read))

    def get_msg_sender(self, filename):
        '''
        Get the message sender.

        :param filename: Filename of message
        :type filename: str
        :returns: Sender of message
        :rtype: str
        '''
        return self._getprop(filename, "sender")

    def set_msg_sender(self, filename, sender):
        '''
        Set message sender.

        :param filename: Filename for message
        :type filename: str
        :param sender: Sender of message
        :type sender: str
        '''
        self._setprop(filename, "sender", sender)

    def get_msg_recip(self, filename):
        '''
        Get the message recipient

        :param filename: Filename for message
        :type filename: str
        :returns: Message recipient
        :rtype: str
        '''
        return self._getprop(filename, "recip")

    def set_msg_recip(self, filename, recip):
        '''
        Set the message recipient.

        :param filename: Filename for message
        :type filename: str
        :param recip: Recipient
        :type recip: str
        '''
        self._setprop(filename, "recip", recip)

    def subfolders(self):
        '''
        Get the subfolders.

        :returns: subfolders of folder
        :rtype: list of :class:`MessageFolderInfo`
        '''
        info = []

        entries = glob(os.path.join(self._path, "*"))
        for entry in sorted(entries):
            if entry in (".", ".."):
                continue
            if os.path.isdir(entry):
                info.append(MessageFolderInfo(entry))

        return info

    def files(self):
        '''
        List files.

        :returns: files in the folder.
        :rtype: list of str
        '''
        file_list = glob(os.path.join(self._path, "*"))
        return [x_file for x_file in file_list
                if os.path.isfile(x_file) and not x_file.startswith(".")]

    def get_subfolder(self, name):
        '''
        Get subfolder information.

        :param name: Subfolder name
        :type name: str
        :returns: Subfolder information
        :rtype: :class:`MessageFolderInfo`
        '''
        for folder in self.subfolders():
            if folder.name() == name:
                return folder

        return None

    def create_subfolder(self, name):
        '''
        Create a subfolder by name

        :param name: Subfolder name
        :type name: str
        :returns: subfolder information
        :rtype: :class:`MessageFolderInfo`
        '''
        path = os.path.join(self._path, name)
        try:
            os.mkdir(path)
        except OSError as err:
            if err.errno != 17:  # File or directory exists
                raise
        return MessageFolderInfo(path)

    def delete_self(self):
        '''Delete Self.'''
        try:
            os.remove(os.path.join(self._path, ".db"))
        except OSError:
            pass # Don't freak if no .db
        os.rmdir(self._path)

    def create_msg(self, name):
        '''
        Create a message.

        Store the message name in the users configuration data

        :param name: Name for message path
        :type name: str
        :returns: Path for message
        :rtype: str
        :raises: DuplicateSectionError if the section already exists
        '''
        exists = os.path.exists(os.path.join(self._path, name))
        try:
            self._config.add_section(name)
        except DuplicateSectionError as err:
            if exists:
                raise err

        return os.path.join(self._path, name)

    def delete(self, filename):
        '''
        Delete a file.

        :param filename: filename to delete
        :type filename: str
        '''
        filename = os.path.basename(filename)
        self._config.remove_section(filename)
        os.remove(os.path.join(self._path, filename))

    def rename(self, new_name):
        '''
        Rename path

        :param new_name: New name for path
        :type new_name: str
        '''
        newpath = os.path.join(os.path.dirname(self._path), new_name)
        self.logger.info("Renaming %s -> %s", self._path, newpath)
        os.rename(self._path, newpath)
        self._path = newpath

    def __str__(self):
        return self.name()


# pylint: disable=too-few-public-methods
class MessageInfo():
    '''Message information.

    :param filename: Filename of message
    :type filename: str
    :param info: Information about the message
    :type info: :class:`MessageFolderInfo`
    '''

    def __init__(self, filename, info):
        self.filename = filename
        self.info = info


class MessageFolders(MainWindowElement):
    '''
    Message Folders.

    :param wtree: Window tree
    :param config: Configuration data
    :type config: :class:`DratsConfig`
    '''

    __gsignals__ = {
        "user-selected-folder" : (GObject.SignalFlags.RUN_LAST,
                                  GObject.TYPE_NONE,
                                  (GObject.TYPE_STRING,))
        }

    # MessageFolders
    def __init__(self, wtree, config):
        MainWindowElement.__init__(self, wtree, config, "msg", _("Messages"))

        self.logger = logging.getLogger("MessageFolders")
        # pylint: disable=unbalanced-tuple-unpacking
        folderlist, = self._getw("folderlist")

        store = Gtk.TreeStore(GObject.TYPE_STRING, GObject.TYPE_OBJECT)
        folderlist.set_model(store)
        folderlist.set_headers_visible(False)
        folderlist.enable_model_drag_dest([("text/d-rats_message", 0, 0)],
                                          Gdk.DragAction.DEFAULT)
        folderlist.connect("drag-data-received", self._dragged_to)
        folderlist.connect("button_press_event", self._mouse_cb)
        folderlist.connect_after("move-cursor", self._move_cursor)

        col = Gtk.TreeViewColumn("", Gtk.CellRendererPixbuf(), pixbuf=1)
        folderlist.append_column(col)

        rnd = Gtk.CellRendererText()
        #rnd.set_property("editable", True)
        rnd.connect("edited", self._folder_rename, store)
        col = Gtk.TreeViewColumn("", rnd, text=0)
        folderlist.append_column(col)

        self.folder_pixbuf = self._config.ship_img("folder.png")

        self._ensure_default_folders()
        for folder in self.get_folders():
            self._add_folders(store, None, folder)

    def _folders_path(self):
        '''
        Folders Path.

        :returns: The folder path
        :rtype: str
        '''
        path = os.path.join(self._config.platform.config_dir(), "messages")
        if not os.path.isdir(path):
            os.makedirs(path)
        return path

    # pylint: disable=no-self-use
    def _create_folder(self, root, name):
        '''
        Create folder.

        :param root: Parent directory
        :type root: :class:`MessageFolderInfo`
        :param name: Folder name
        :type name: str
        :raises: :class:`FolderError` if folder can not be created
        :returns: Message folder info for child directory
        :rtype: :class:`MessageFolderInfo`
        '''
        # python3 can create directory and parent directories in one call.
        info = root
        for dir_element in name.split(os.sep)[:-1]:
            info = info.get_subfolder(dir_element)
            if not info:
                break

        try:
            return info.create_subfolder(os.path.basename(name))
        except OSError as err:
            if err.errno != 17:  # File or directory exists
                raise FolderError(
                    "Intermediate folder of %s does not exist %s" %
                    (name, err))

    def create_folder(self, name):
        '''
        Create a folder.

        Does not appear to be called anywhere.

        :param name: Folder name
        :type name: str
        :raises: :class:`FolderError` if folder cannot be created
        '''
        root = MessageFolderInfo(self._folders_path())
        self._create_folder(root, name)

    def get_folders(self):
        '''
        Get Folders.

        :returns: Message folders infomation
        :rtype: list of :class:`MessageFolderInfo`
        '''
        return MessageFolderInfo(self._folders_path()).subfolders()

    def get_folder(self, name):
        '''
        Get Folder by name.

        :param name: Folder name
        :type name: str
        :returns: Message folder information
        :rtype: :class:`MessageFolderInfo`
        '''
        return MessageFolderInfo(os.path.join(self._folders_path(), name))

    # pylint: disable=no-self-use
    def _get_folder_by_iter(self, store, msg_iter):
        els = []
        while msg_iter:
            els.insert(0, store.get(msg_iter, 0)[0])
            msg_iter = store.iter_parent(msg_iter)

        return os.sep.join(els)

    def select_folder(self, folder):
        '''
        Select a folder by path.

        i.e. Inbox/Subfolder
        NB: Subfolders currently not supported.

        :param folder: Folder name to select
        :type folder: str
        '''
        # pylint: disable=unbalanced-tuple-unpacking
        view, = self._getw("folderlist")
        store = view.get_model()

        msg_iter = store.get_iter_first()
        while msg_iter:
            fqname = self._get_folder_by_iter(store, msg_iter)
            if fqname == folder:
                view.set_cursor(store.get_path(msg_iter))
                self.emit("user-selected-folder", fqname)
                break

            msg_iter = store.iter_next(msg_iter)

    def _ensure_default_folders(self):
        root = MessageFolderInfo(self._folders_path())

        for folder in BASE_FOLDERS:
            try:
                info = self._create_folder(root, folder)
                self.logger.info("_ensure_default_folders %s",
                                 info.subfolders())
            # pylint: disable=broad-except
            except Exception:
                # Possibly temp diagnostic until verify the exact exception.
                self.logger.info("_ensure_default_folders broad-except",
                                 exc_info=True)
                # pass

    def _add_folders(self, store, msg_iter, root):
        msg_iter = store.append(msg_iter, (root.name(), self.folder_pixbuf))
        for info in root.subfolders():
            self._add_folders(store, msg_iter, info)

    # pylint: disable=no-self-use
    def _get_selected_folder(self, view, event):
        if event.window == view.get_bin_window():
            x_coord, y_coord = event.get_coords()
            pathinfo = view.get_path_at_pos(int(x_coord), int(y_coord))
            if pathinfo is None:
                return view.get_model(), None
            view.set_cursor_on_cell(pathinfo[0], None, None, False)

        return view.get_selection().get_selected()

    def _mh(self, _action, store, msg_iter, _view):
        action = _action.get_name()

        if action == "delete":
            info = self.get_folder(self._get_folder_by_iter(store, msg_iter))
            try:
                info.delete_self()
            except OSError as err:
                display_error("Unable to delete folder: %s" % err)
                return
            store.remove(msg_iter)
        elif action == "create":
            store.insert(msg_iter, 0, ("New Folder", self.folder_pixbuf))
            parent = self.get_folder(self._get_folder_by_iter(store, msg_iter))
            self._create_folder(parent, "New Folder")
        elif action == "rename":
            info = self.get_folder(self._get_folder_by_iter(store, msg_iter))

            new_text = prompt_for_string("Rename folder `%s' to:" % info.name(),
                                         orig=info.name())
            if not new_text:
                return
            if new_text == info.name():
                return

            try:
                info.rename(new_text)
            # pylint: disable=broad-except
            except Exception as err:
                self.logger.info("mh (rename) broad-except", exc_info=True)
                display_error("Unable to rename: %s -%s-" % (type(err), err))
                return

            store.set(msg_iter, 0, new_text)

    def _select_folder(self, view, event):
        store, msg_iter = self._get_selected_folder(view, event)
        if not msg_iter:
            return
        self.emit("user-selected-folder",
                  self._get_folder_by_iter(store, msg_iter))

    def _move_cursor(self, view, _step, _count):
        try:
            (store, msg_iter) = view.get_selection().get_selected()
        # pylint: disable=broad-except
        except Exception:
            self.logger.info("_move_cursor - Unable to find selected",
                             exc_info=True)
            return

        self.emit("user-selected-folder",
                  self._get_folder_by_iter(store, msg_iter))

    # pylint: disable=too-many-locals
    def _folder_menu(self, view, event):
        x_coord = int(event.x)
        y_coord = int(event.y)
        pthinfo = view.get_path_at_pos(x_coord, y_coord)
        if pthinfo is not None:
            path, col, _cellx, _celly = pthinfo
            view.grab_focus()
            view.set_cursor(path, col, 0)

        xml = """
<ui>
  <popup name="menu">
    <menuitem action="delete"/>
    <menuitem action="create"/>
    <menuitem action="rename"/>
  </popup>
</ui>
"""
        store, folder_iter = self._get_selected_folder(view, event)
        folder = self._get_folder_by_iter(store, folder_iter)

        can_del = bool(folder and (folder not in BASE_FOLDERS))

        action_group = Gtk.ActionGroup.new("menu")
        actions = [("delete", _("Delete"), Gtk.STOCK_DELETE, can_del),
                   ("create", _("Create"), Gtk.STOCK_NEW, True),
                   ("rename", _("Rename"), None, can_del)]

        for action, label, stock, sensitive in actions:
            new_action = Gtk.Action.new(action, label, None, stock)
            new_action.set_sensitive(sensitive)
            new_action.connect("activate", self._mh, store, folder_iter, view)
            action_group.add_action(new_action)

        uim = Gtk.UIManager()
        uim.insert_action_group(action_group, 0)
        uim.add_ui_from_string(xml)
        # pylint: disable=no-member
        uim.get_object("/menu").popup(None, None, None, None,
                                      event.button, event.time)

    def _mouse_cb(self, view, event):
        if event.button == 1:
            return self._select_folder(view, event)
        if event.button == 3:
            return self._folder_menu(view, event)
        return None

    # pylint: disable=too-many-arguments, too-many-locals
    def _dragged_to(self, view, _ctx, x_coord, y_coord, sel, _info, _ts):
        '''
        Dragged to.

        :param view: Widget getting signal
        :type view: GTK.Widget
        :param _ctx: Context value, unused
        :type: ctx: Gtk.DragContex
        :param x_coord: Horizontal coordinate of destintation
        :param y_coord: Vertical coordinate of destination
        :param sel: Selection containing the dragged data
        :type sel: Gtk.SelectionData
        :param _info: Information registered in the Gtk.TargetList, unused
        :param _ts: timestamp of when the data was requested, unused
        '''
        (path, _place) = view.get_dest_row_at_pos(x_coord, y_coord)

        text = sel.get_text()
        byte_data = sel.get_data()
        text = byte_data.decode('ISO-8859-1').split("\x01")
        msgs = text[1:]

        src_folder = text[0]
        dst_folder = self._get_folder_by_iter(view.get_model(),
                                              view.get_model().get_iter(path))

        if src_folder == dst_folder:
            return

        dst = MessageFolderInfo(os.path.join(self._folders_path(), dst_folder))
        src = MessageFolderInfo(os.path.join(self._folders_path(), src_folder))

        for record in msgs:
            fname, subj, msg_type, read, send, recp = record.split("\0")
            self.logger.info("_dragged_to Dragged %s from %s into %s",
                             fname, src_folder, dst_folder)
            self.logger.info("_dragged_to: %s %s %s %s->%s",
                             subj, msg_type, read, send, recp)

            try:
                dst.delete(os.path.basename(fname))
            # pylint: disable=broad-except
            except Exception:
                # Possibly temp diagnostic until we find the specific
                # expected exceptions.
                self.logger.info("_dragged_to: broad-exception", exc_info=True)
                # pass
            newfn = dst.create_msg(os.path.basename(fname))
            shutil.copy(fname, newfn)
            src.delete(fname)

            dst.set_msg_read(fname, read == "True")
            dst.set_msg_subject(fname, subj)
            dst.set_msg_type(fname, msg_type)
            dst.set_msg_sender(fname, send)
            dst.set_msg_recip(fname, recp)

    def _folder_rename(self, _render, path, new_text, store):
        folder_iter = store.get_iter(path)
        orig = store.get(folder_iter, 0)[0]
        if orig == new_text:
            return
        if orig in BASE_FOLDERS:
            return
        info = self.get_folder(self._get_folder_by_iter(store, folder_iter))
        try:
            info.rename(new_text)
        # pylint: disable=broad-except
        except Exception as err:
            self.logger.info("_folder_rename: broad-except", exc_info=True)
            display_error("Unable to rename: %s -%s-" % (type(err), err))
            return

        store.set(iter, 0, new_text)


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

    # pylint: disable=too-many-statements
    def __init__(self, wtree, config):
        MainWindowElement.__init__(self, wtree, config, "msg", _("Messages"))

        self.logger = logging.getLogger("MessageList")
        # pylint: disable=unbalanced-tuple-unpacking
        msglist, = self._getw("msglist")

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

        def bold_if_unread(_col, rend, model, msg_iter, cnum):
            val, read, = model.get(msg_iter, cnum, ML_COL_READ)
            if not val:
                val = ""
            if not read:
                val = val.replace("&", "&amp;")
                val = val.replace("<", "&lt;")
                val = val.replace(">", "&gt;")
                rend.set_property("markup", "<b>%s</b>" % val)

        renderer = Gtk.CellRendererText()
        renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
        col = Gtk.TreeViewColumn(_("Sender"), renderer, text=ML_COL_SEND)
        col.set_cell_data_func(renderer, bold_if_unread, ML_COL_SEND)
        col.set_sort_column_id(ML_COL_SEND)
        col.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        col.set_resizable(True)
        msglist.append_column(col)

        renderer = Gtk.CellRendererText()
        renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
        col = Gtk.TreeViewColumn(_("Recipient"), renderer, text=ML_COL_RECP)
        col.set_cell_data_func(renderer, bold_if_unread, ML_COL_RECP)
        col.set_sort_column_id(ML_COL_RECP)
        col.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        col.set_resizable(True)
        msglist.append_column(col)

        renderer = Gtk.CellRendererText()
        renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
        col = Gtk.TreeViewColumn(_("Subject"), renderer, text=ML_COL_SUBJ)
        col.set_cell_data_func(renderer, bold_if_unread, ML_COL_SUBJ)
        col.set_expand(True)
        col.set_sort_column_id(ML_COL_SUBJ)
        col.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        col.set_resizable(True)
        msglist.append_column(col)

        renderer = Gtk.CellRendererText()
        renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
        col = Gtk.TreeViewColumn(_("Type"), renderer, text=ML_COL_TYPE)
        col.set_cell_data_func(renderer, bold_if_unread, ML_COL_TYPE)
        col.set_sort_column_id(ML_COL_TYPE)
        col.set_resizable(True)
        msglist.append_column(col)

        def render_date(_col, rend, model, msg_iter, _data):
            time_stamp, read = model.get(msg_iter, ML_COL_DATE, ML_COL_READ)
            stamp = datetime.fromtimestamp(
                time_stamp).strftime("%H:%M:%S %Y-%m-%d")
            if read:
                rend.set_property("text", stamp)
            else:
                rend.set_property("markup", "<b>%s</b>" % stamp)

        renderer = Gtk.CellRendererText()
        renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
        col = Gtk.TreeViewColumn(_("Date"), renderer, text=ML_COL_DATE)
        col.set_cell_data_func(renderer, render_date)
        col.set_sort_column_id(ML_COL_DATE)
        col.set_resizable(True)
        msglist.append_column(col)

        msglist.connect("row-activated", self._open_msg)
        self.store.set_sort_column_id(ML_COL_DATE, Gtk.SortType.DESCENDING)

        self.message_pixbuf = self._config.ship_img("message.png")
        self.unread_pixbuf = self._config.ship_img("msg-markunread.png")
        self.current_info = None

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
        :param cbdata: Call back data
        :returns: response
        :rtype: Gtk.ResponseType
        '''
        if not msgrouting.msg_lock(filename):
            display_error(_("Unable to open: message in use by another task"))
            return Gtk.ResponseType.CANCEL

        parent = self._wtree.get_object("mainwindow")
        form = formgui.FormDialog(_("Form"), filename,
                                  config=self._config, parent=parent)
        form.configure(self._config)

        def form_done(dlg, response, msg_info):
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

    # pylint: disable=too-many-arguments
    def _dragged_from(self, view, _ctx, sel, _info, _ts):
        '''
        Dragged from.

        :param view: Widget getting signal
        :type view: Gtk.Widget
        :param _ctx: Context value, unused
        :type _ctx: Gtk.DragContex
        :param sel: Selection containing the dragged data
        :type sel: Gtk.SelectionData
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
        # pylint: disable=unbalanced-tuple-unpacking
        msglist, = self._getw("msglist")

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
        # pylint: disable=broad-except
        except Exception:
            # Same folder, or duplicate message id
            self.logger.info("move_message: broad-except", exc_info=True)
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
        # pylint: disable=unbalanced-tuple-unpacking
        msglist, = self._getw("msglist")

        selected = []
        (store, paths) = msglist.get_selection().get_selected_rows()
        for path in paths:
            selected.append(store[path][ML_COL_FILE])

        return selected


class MessagesTab(MainWindowTab):
    '''
    Messages Tab.

    :param wtree: Object for tree
    :param config: Configuration data
    :type config: :class:`DratsConfig`
    '''

    __gsignals__ = {
        "event" : signals.EVENT,
        "notice" : signals.NOTICE,
        "user-send-form" : signals.USER_SEND_FORM,
        "get-station-list" : signals.GET_STATION_LIST,
        "trigger-msg-router" : signals.TRIGGER_MSG_ROUTER,
        }

    _signals = __gsignals__

    def __init__(self, wtree, config):
        MainWindowTab.__init__(self, wtree, config, "msg", _("Messages"))

        self.logger = logging.getLogger("MessagesTab")
        self._init_toolbar()
        self._folders = MessageFolders(wtree, config)
        self._messages = MessageList(wtree, config)
        self._messages.connect("prompt-send-form", self._snd_msg)
        self._messages.connect("reply-form", self._rpl_msg)
        self._messages.connect("delete-form", self._del_msg)

        self._folders.connect("user-selected-folder",
                              lambda x, y: self._messages.open_folder(y))
        self._folders.select_folder(_("Inbox"))

        iport = self._wtree.get_object("main_menu_importmsg")
        iport.connect("activate", self._importmsg)

        eport = self._wtree.get_object("main_menu_exportmsg")
        eport.connect("activate", self._exportmsg)

    # pylint: disable=too-many-locals
    def _new_msg(self, _button, msgtype=None):
        types = glob(os.path.join(self._config.form_source_dir(), "*.xml"))

        forms = {}
        for file_name in types:
            forms[os.path.basename(file_name).replace(".xml", "")] = file_name

        if msgtype is None:
            parent = self._wtree.get_object("mainwindow")
            dialog = inputdialog.ChoiceDialog(forms.keys(),
                                              title=_("Choose a form"),
                                              parent=parent)
            result = dialog.run()
            msgtype = dialog.choice.get_active_text()
            dialog.destroy()
            if result != Gtk.ResponseType.OK:
                return

        current = self._messages.current_info.name()
        self._folders.select_folder(_("Drafts"))

        tstamp = time.strftime("form_%m%d%Y_%H%M%S.xml")
        newfn = self._messages.current_info.create_msg(tstamp)


        form = formgui.FormFile(forms[msgtype])
        call = self._config.get("user", "callsign")
        form.add_path_element(call)
        form.set_path_src(call)
        form.set_path_mid(mkmsgid(call))
        form.save_to(newfn)

        def close_msg_cb(response, info):
            if response == int(Gtk.ResponseType.CLOSE):
                info.delete(newfn)
            if self._messages.current_info == info:
                self._messages.refresh()
                self._folders.select_folder(current)

        self._messages.open_msg(newfn, True,
                                close_msg_cb, self._messages.current_info)

    # pylint: disable=too-many-locals
    def _rpl_msg(self, _button, file_name=None):
        def subj_reply(subj):
            if "RE:" in subj.upper():
                return subj
            return "RE: %s" % subj

        def msg_reply(msg):
            if self._config.getboolean("prefs", "msg_include_reply"):
                return "--- Original Message ---\r\n\r\n" + msg
            return ""

        save_fields = [
            ("_auto_number", "_auto_number", lambda x: str(int(x)+1)),
            ("_auto_subject", "_auto_subject", subj_reply),
            ("subject", "subject", lambda x: "RE: %s" % x),
            ("message", "message", msg_reply),
            ("_auto_sender", "_auto_recip", None),
            ]

        if not file_name:
            try:
                sel = self._messages.get_selected_messages()
            except TypeError:
                return

            if len(sel) > 1:
                self.logger.info("_rpl_msg: FIXME: Warn about multiple reply")
                return

            file_name = sel[0]

        current = self._messages.current_info.name()
        self._folders.select_folder(_("Drafts"))

        oform = formgui.FormFile(file_name)
        tmpl = os.path.join(self._config.form_source_dir(),
                            "%s.xml" % oform.ident)

        nform = formgui.FormFile(tmpl)
        nform.add_path_element(self._config.get("user", "callsign"))

        try:
            for s_field, d_field, x_field in save_fields:
                oldval = oform.get_field_value(s_field)
                if not oldval:
                    continue

                if x_field:
                    nform.set_field_value(d_field, x_field(oldval))
                else:
                    nform.set_field_value(d_field, oldval)
        # pylint: disable=broad-except
        except Exception:
            log_exception()
            self.logger.info("_rpl_msg: Failed to do reply broad-except",
                             exc_info=True)
            return

        if ";" in oform.get_path_dst():
            rpath = ";".join(reversed(oform.get_path()[:-1]))
            self.logger.info("_rpl_msg: rpath: %s (%s)",
                             rpath, oform.get_path())
            nform.set_path_dst(rpath)
        else:
            nform.set_path_dst(oform.get_path_src())

        call = self._config.get("user", "callsign")
        nform.set_path_src(call)
        nform.set_path_mid(mkmsgid(call))

        tstamp = time.strftime("form_%m%d%Y_%H%M%S.xml")
        newfn = self._messages.current_info.create_msg(tstamp)
        nform.save_to(newfn)

        def close_msg_cb(response, info):
            if self._messages.current_info == info:
                self.logger.info("_rpl_msg: Response was %i (%i)",
                                 response, Gtk.ResponseType.CANCEL)
                if response in [Gtk.ResponseType.CANCEL,
                                Gtk.ResponseType.CLOSE]:
                    info.delete(newfn)
                    self._folders.select_folder(current)
                else:
                    self._messages.refresh(newfn)

        self._messages.open_msg(newfn, True,
                                close_msg_cb, self._messages.current_info)

    def _del_msg(self, _button, file_name=None):
        if file_name:
            try:
                os.remove(file_name)
            # pylint: disable=broad-except
            except Exception:
                self.logger.info("_del_msg: Unable to delete %s: %s",
                                 file_name, 'broad-except', exc_info=True)
            self._messages.refresh()
        else:
            if self._messages.current_info.name() == _("Trash"):
                self._messages.delete_selected_messages()
            else:
                self._messages.move_selected_messages(_("Trash"))

    def _snd_msg(self, _button, file_name=None):
        if not file_name:
            try:
                sel = self._messages.get_selected_messages()
            except TypeError:
                return

            if len(sel) > 1:
                self.logger.info("_snd_msg: FIXME: Warn about multiple send")
                return

            file_name = sel[0]
        recip = self._messages.current_info.get_msg_recip(file_name)

        if not msgrouting.msg_lock(file_name):
            display_error(_("Unable to send: message in use by another task"))
            return

        stations = []
        ports = self.emit("get-station-list")
        for slist in ports.values():
            stations += slist

        if recip in stations:
            stations.remove(recip)
        stations.insert(0, recip)

        station, port = prompt_for_station(stations, self._config)
        if not station:
            if msgrouting.msg_is_locked(file_name):
                msgrouting.msg_unlock(file_name)
            return

        self.emit("user-send-form", station, port, file_name, "foo")

        if msgrouting.msg_is_locked(file_name):
            msgrouting.msg_unlock(file_name)

    def _mrk_msg(self, _button, read):
        try:
            sel = self._messages.get_selected_messages()
        except TypeError:
            return

        for file_name in sel:
            self._messages.current_info.set_msg_read(file_name, read)

        self._messages.refresh()

    def _importmsg(self, _button):
        download_dir = self._config.get("prefs", "download_dir")
        file_name = self._config.platform.gui_open_file(download_dir)
        if not file_name:
            return

        dst = os.path.join(self._config.form_store_dir(),
                           _("Inbox"),
                           time.strftime("form_%m%d%Y_%H%M%S.xml"))

        shutil.copy(file_name, dst)
        self.refresh_if_folder(_("Inbox"))

    def _exportmsg(self, _button):
        try:
            sel = self._messages.get_selected_messages()
        except TypeError:
            return

        if len(sel) > 1:
            self.logger.info("_exportmsg: FIXME: Warn about multiple send")
            return
        if sel:
            return

        file_name = sel[0]

        download_dir = self._config.get("prefs", "download_dir")
        nfn = self._config.platform.gui_save_file(download_dir, "msg.xml")
        if not nfn:
            return

        shutil.copy(file_name, nfn)

    def _sndrcv(self, _button, account=""):
        self.emit("trigger-msg-router", account)

    def _make_sndrcv_menu(self):
        menu = Gtk.Menu()

        menu_item = Gtk.MenuItem("Outbox")
        try:
            menu_item.set_tooltip_text("Send messages in the Outbox")
        except AttributeError:
            pass
        menu_item.connect("activate", self._sndrcv)
        menu_item.show()
        menu.append(menu_item)

        menu_item = Gtk.MenuItem("WL2K")
        try:
            menu_item.set_tooltip_text("Check Winlink messages")
        except AttributeError:
            pass
        menu_item.connect("activate", self._sndrcv, "@WL2K")
        menu_item.show()
        menu.append(menu_item)

        for section in self._config.options("incoming_email"):
            info = self._config.get("incoming_email", section).split(",")
            lab = "%s on %s" % (info[1], info[0])
            menu_item = Gtk.MenuItem(lab)
            try:
                menu_item.set_tooltip_text("Check for new mail on this account")
            except AttributeError:
                pass
            menu_item.connect("activate", self._sndrcv, section)
            menu_item.show()
            menu.append(menu_item)

        return menu

    def _make_new_menu(self):
        menu = Gtk.Menu()

        t_dir = self._config.form_source_dir()
        for file_i in sorted(glob(os.path.join(t_dir, "*.xml"))):
            msgtype = os.path.basename(file_i).replace(".xml", "")
            label = msgtype.replace("_", " ")
            menu_item = Gtk.MenuItem(label)
            try:
                menu_item.set_tooltip_text("Create a new %s form" % label)
            except AttributeError:
                pass
            menu_item.connect("activate", self._new_msg, msgtype)
            menu_item.show()
            menu.append(menu_item)

        return menu

    def _init_toolbar(self):
        # pylint: disable=unbalanced-tuple-unpacking
        toolbar, = self._getw("toolbar")

        set_toolbar_buttons(self._config, toolbar)

        read = lambda msg: self._mrk_msg(msg, True)
        unread = lambda msg: self._mrk_msg(msg, False)

        buttons = [("msg-new.png", _("New"), self._new_msg),
                   ("msg-send-via.png", _("Forward"), self._snd_msg),
                   ("msg-reply.png", _("Reply"), self._rpl_msg),
                   ("msg-delete.png", _("Delete"), self._del_msg),
                   ("msg-markread.png", _("Mark Read"), read),
                   ("msg-markunread.png", _("Mark Unread"), unread),
                   ("msg-sendreceive.png", _("Send/Receive"), self._sndrcv),
                   ]

        tips = {
            _("New") : _("Create a new message for sending"),
            _("Forward") : _("Manually direct a message to another station"),
            _("Reply") : _("Reply to the currently selected message"),
            _("Delete") : _("Delete the currently selected message"),
            _("Mark Read") : _("Mark the currently selected message as read"),
            _("Mark Unread") : _("Mark the currently selected message as unread"),
            _("Send/Receive") : _("Send messages in the Outbox"),
            }

        menus = {
            "msg-new.png" : self._make_new_menu(),
            "msg-sendreceive.png" : self._make_sndrcv_menu(),
            }

        count = 0
        for button_i, button_l, button_f in buttons:
            icon = Gtk.Image()
            icon.set_from_pixbuf(self._config.ship_img(button_i))
            icon.show()
            if button_i in menus:
                item = Gtk.MenuToolButton.new(icon, button_l)
                item.set_menu(menus[button_i])
                try:
                    item.set_arrow_tooltip_text("%s %s %s" % (_("More"),
                                                              button_l,
                                                              _("Options")))
                except AttributeError:
                    pass
            else:
                item = Gtk.ToolButton.new(icon, button_l)
            item.show()
            item.connect("clicked", button_f)
            if button_l in tips:
                try:
                    item.set_tooltip_text(tips[button_l])
                except AttributeError:
                    pass
            toolbar.insert(item, count)
            count += 1

    def refresh_if_folder(self, folder):
        '''
        Refresh if folder is current.

        :param folder: Folder name to refresh
        :type folder: str
        '''
        self._notice()
        if self._messages.current_info.name() == folder:
            self._messages.refresh()

    def message_sent(self, file_name):
        '''
        Mark a message sent.

        :param file_name: Filename
        :type file_name: str
        '''
        outbox = self._folders.get_folder(_("Outbox"))
        files = outbox.files()
        if file_name in files:
            sent = self._folders.get_folder(_("Sent"))
            newfn = sent.create_msg(os.path.basename(file_name))
            self.logger.info("message_sent: Moving %s -> %s",
                             file_name, newfn)
            shutil.copy(file_name, newfn)
            outbox.delete(file_name)
            self.refresh_if_folder(_("Outbox"))
            self.refresh_if_folder(_("Sent"))
        else:
            self.logger.info("message_sent: Form %s sent but not in outbox",
                             os.path.basename(file_name))

    def get_shared_messages(self, _for_station):
        '''
        Get Shared Messages for a destination.

        :param for_station:  Destination Station (Currently ignored)
        :returns: list of messages for the destination
        :rtype: List of tuple (title, stamp, filename)
        '''
        shared = _("Inbox")
        path = os.path.join(self._config.platform.config_dir(), "messages")
        if not os.path.isdir(path):
            os.makedirs(path)
        info = MessageFolderInfo(os.path.join(path, shared))

        ret = []
        for file_name in info.files():
            stamp = os.stat(file_name).st_mtime
            ffn = "%s/%s" % (shared, os.path.basename(file_name))
            form = formgui.FormFile(file_name)
            ret.append((form.get_subject_string(), stamp, ffn))

        return ret

    def selected(self):
        '''Selected.'''
        MainWindowTab.selected(self)

        make_visible = ["main_menu_importmsg", "main_menu_exportmsg"]

        for name in make_visible:
            item = self._wtree.get_object(name)
            item.set_property("visible", True)

    def deselected(self):
        '''Deselected.'''
        MainWindowTab.deselected(self)

        make_invisible = ["main_menu_importmsg", "main_menu_exportmsg"]

        for name in make_invisible:
            item = self._wtree.get_object(name)
            item.set_property("visible", False)
