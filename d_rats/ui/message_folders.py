#!/usr/bin/python
'''Main Messages Message Folders.'''
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

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject

from d_rats.ui.main_common import MainWindowElement
from d_rats.ui.main_common import display_error
from d_rats.ui.main_common import prompt_for_string
from d_rats.ui.message_folder_info import MessageFolderInfo
from d_rats.ui.message_popup_model import MessagePopupModel


if not '_' in locals():
    import gettext
    _ = gettext.gettext

BASE_FOLDERS = [_("Inbox"), _("Outbox"), _("Sent"), _("Trash"), _("Drafts")]


class MainMessageException(Exception):
    '''Generic Main Message Exception.'''


class FolderError(MainMessageException):
    '''Error accessing a folder.'''


class MessageFolders(MainWindowElement):
    '''
    Message Folders.

    :param wtree: Window tree
    :type wtree: :class:`Gtk.GtkNotebook`
    :param config: Configuration data
    :type config: :class:`DratsConfig`
    :param window: Mainwindow window widget
    :type: window: :class:`Gtk.ApplicationWindow`
    '''

    __gsignals__ = {
        "user-selected-folder" : (GObject.SignalFlags.RUN_LAST,
                                  GObject.TYPE_NONE,
                                  (GObject.TYPE_STRING,))
        }

    def __init__(self, wtree, config, window):
        MainWindowElement.__init__(self, wtree, config, prefix="msg")

        self.logger = logging.getLogger("MessageFolders")
        folderlist = self._get_widget("folderlist")
        self.window = window

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
        self.folderlist = folderlist

        rnd = Gtk.CellRendererText()
        # rnd.set_property("editable", True)
        rnd.connect("edited", self._folder_rename, store)
        col = Gtk.TreeViewColumn("", rnd, text=0)
        folderlist.append_column(col)

        self.folder_model = MessagePopupModel(self)
        self.folder_menu = Gtk.Menu.new_from_model(self.folder_model)
        self.folder_menu.attach_to_widget(self.folderlist)

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

    @staticmethod
    def _create_folder(root, name):
        '''
        Create folder.

        :param root: Parent directory
        :type root: :class:`MessageFolderInfo`
        :param name: Folder name
        :type name: str
        :returns: Message folder info for child directory
        :rtype: :class:`MessageFolderInfo`
        :raises: :class:`FolderError` if folder can not be created
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

        :returns: Message folders information
        :rtype: list[:class:`MessageFolderInfo`]
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

    @staticmethod
    def _get_folder_by_iter(store, msg_iter):
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
        view = self._get_widget("folderlist")
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
                self.logger.debug("_ensure_default_folders %s",
                                  info.subfolders())
            except FolderError:
                pass

    def _add_folders(self, store, msg_iter, root):
        msg_iter = store.append(msg_iter, (root.name(), self.folder_pixbuf))
        for info in root.subfolders():
            self._add_folders(store, msg_iter, info)

    @staticmethod
    def _get_selected_folder(view, event):
        if event.window == view.get_bin_window():
            x_coord, y_coord = event.get_coords()
            pathinfo = view.get_path_at_pos(int(x_coord), int(y_coord))
            if pathinfo is None:
                return view.get_model(), None
            view.set_cursor_on_cell(pathinfo[0], None, None, False)

        return view.get_selection().get_selected()

    def popup_menu_handler(self, action, _value):
        '''
        Menu activate handler.

        :param action: Action that was signaled
        :type action: :class:`Gtk.Action`
        :param _value: Value for action, Unused
        :type _value: :class:`Gio.VariantType`
        '''
        action_name = action.get_name()
        folder_iter = self.folder_model.folder_iter
        folder_name = self.folder_model.folder_name
        folder_store = self.folder_model.folder_store
        folder_info = self.get_folder(folder_name)

        if action_name == "delete":
            try:
                folder_info.delete_self()
            except OSError as err:
                display_error("Unable to delete folder: %s" % err)
                return
            folder_store.remove(folder_iter)
        elif action_name == "create":
            new_folder = _("New Folder")
            folder_store.insert(folder_iter, 0,
                                (new_folder, self.folder_pixbuf))
            self._create_folder(folder_info, new_folder)
        elif action_name == "rename":
            old_name = folder_info.name()
            new_name = prompt_for_string("Rename folder `%s' to:" % old_name,
                                         orig=old_name)
            if not new_name or new_name == old_name:
                self.logger.debug("action rename: old: %s, new: %s",
                                  old_name, new_name)
                return

            try:
                folder_info.rename(new_name)
            except OSError as err:
                display_error("Unable to rename: %s" % err)
                return

            folder_store.set(folder_iter, 0, new_name)

    def _select_folder(self, view, event):
        store, msg_iter = self._get_selected_folder(view, event)
        if not msg_iter:
            return
        self.emit("user-selected-folder",
                  self._get_folder_by_iter(store, msg_iter))

    def _move_cursor(self, view, _step, _direction):
        '''
        Move cursor move-cursor handler.

        :param view: TreeView widget
        :type view: :class:`Gtk.TreeView`
        :param _step: The granularity of the move
        :type _step: :class:`Gtk.MovementStep`
        :param _direction:  Direction to move
        :type _direction: int
        '''
        (store, msg_iter) = view.get_selection().get_selected()
        self.emit("user-selected-folder",
                  self._get_folder_by_iter(store, msg_iter))

    def _folder_menu(self, view, event):
        '''
        Folder Menu for mouse_cb handler.

        :param view: Treeview Widget clicked on.
        :type view: :class:`Gtk.TreeView`
        :param event: Button press event
        :type event: :class:`Gtk.EventButton`
        '''
        x_coord, y_coord = event.get_coords()
        path_info = view.get_path_at_pos(x_coord, y_coord)
        if path_info is not None:
            path, col, _cellx, _celly = path_info

            view.grab_focus()
            view.set_cursor(path, col, 0)

        store, folder_iter = self._get_selected_folder(view, event)
        folder = self._get_folder_by_iter(store, folder_iter)

        self.folder_model.change_state(folder, store, folder_iter)
        self.folder_menu.popup_at_pointer()

    def _mouse_cb(self, view, event):
        '''
        Mouse Callback button_press_event Handler.

        :param view: Mouse button widget
        :type view: :class:`Gtk.TreeView`
        :param event: Button press event
        :type event: :class:`Gtk.EventButton`
        '''
        if event.button == 1:
            return self._select_folder(view, event)
        if event.button == 3:
            return self._folder_menu(view, event)
        return None

    def _dragged_to_helper(self, src, dst, src_folder, dst_folder, msgs):
        for record in msgs:
            fname, subj, msg_type, read, send, recp = record.split("\0")
            self.logger.debug("_dragged_to Dragged %s from %s into %s",
                              fname, src_folder, dst_folder)
            self.logger.debug("_dragged_to: %s %s %s %s->%s",
                              subj, msg_type, read, send, recp)

            try:
                # Make sure that destination does not exist
                dst.delete(os.path.basename(fname))
            except FileNotFoundError:
                pass
            newfn = dst.create_msg(os.path.basename(fname))
            shutil.copy(fname, newfn)
            src.delete(fname)

            dst.set_msg_read(fname, read == "True")
            dst.set_msg_subject(fname, subj)
            dst.set_msg_type(fname, msg_type)
            dst.set_msg_sender(fname, send)
            dst.set_msg_recip(fname, recp)

    def _dragged_to(self, view, _ctx, x_coord, y_coord, sel, _info, _ts):
        '''
        Dragged to - drag-data-received Handler.

        :param view: Widget getting signal
        :type view: :class:`Gtk.TreeView`
        :param _ctx: Context value, unused
        :type: ctx: :class:`Gtk.DragContext`
        :param x_coord: Horizontal coordinate of destination
        :param y_coord: Vertical coordinate of destination
        :param sel: Selection containing the dragged data
        :type sel: :class:`Gtk.SelectionData`
        :param _info: Information registered in the Gtk.TargetList, unused
        :type _info: int
        :param _ts: timestamp of when the data was requested, unused
        :type _ts: int
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

        self._dragged_to_helper(src, dst, dst_folder, src_folder, msgs)

    def _folder_rename(self, _render, path, new_text, store):
        '''
        Folder rename edited handler.

        :param _render: Rendering widget
        :type _render: :class:`Gtk.CellRendererText`
        :param path: Path identifying edited cell
        :type path: str
        :param new_text: New text
        :type new_text: str
        :param store: TreeStore for data
        :type store: :class:`Gtk.TreeStore`
        '''
        folder_iter = store.get_iter(path)
        orig = store.get(folder_iter, 0)[0]
        if orig == new_text:
            return
        if orig in BASE_FOLDERS:
            return
        info = self.get_folder(self._get_folder_by_iter(store, folder_iter))
        try:
            info.rename(new_text)
        except OSError as err:
            display_error("Unable to rename: %s" % err)
            return

        store.set(iter, 0, new_text)
