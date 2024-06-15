'''Test Message Mouse Popup Menu Model.'''
#
# Copyright 2022-2024 John Malmberg <wb8tyw@gmail.com>
# Portions derived from works:
# Copyright 2009 Dan Smith <dsmith@danplanet.com>
# review 2019 Maurizio Andreotti  <iz2lxi@yahoo.it>
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
from __future__ import unicode_literals

import logging
import os

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import Gio
from gi.repository import GObject

from d_rats.dratsconfig import DratsConfig
from d_rats.ui.main_common import prompt_for_string
from d_rats.ui.message_folder_info import MessageFolderInfo
from d_rats.ui.message_popup_model import MessagePopupModel

# This makes pylance happy with out overriding settings
# from the invoker of the class
if not '_' in locals():
    import gettext
    _ = gettext.gettext


class TestMsgModelWindow():
    '''
    Test Application Window holding class.

    :param application: MainApp application
    :type: application: :class:`MainApp`
    '''
    config = DratsConfig()

    def __init__(self, application):

        self.logger = logging.getLogger("TestMsgModelWindow")
        self.logger.info("__init__ called")

        scrolled_window = Gtk.ScrolledWindow()

        self.store = Gtk.TreeStore(GObject.TYPE_STRING, GObject.TYPE_OBJECT)
        folder_list = Gtk.TreeView.new_with_model(self.store)
        folder_list.show()

        scrolled_window.add(folder_list)

        folder_list.connect("button_press_event", self._mouse_cb)

        col = Gtk.TreeViewColumn("", Gtk.CellRendererPixbuf(), pixbuf=1)
        folder_list.append_column(col)

        rnd = Gtk.CellRendererText()
        # rnd.set_property("editable", True)
        rnd.connect("edited", self._folder_rename, self.store)
        col = Gtk.TreeViewColumn("", rnd, text=0)
        folder_list.append_column(col)

        self.folder_pixbuf = self.config.ship_img("folder.png")

        # self._ensure_default_folders()
        for folder in self.get_folders():
            self.logger.info("Adding folder %s", folder)
            self._add_folders(self.store, None, folder)

        self.window = Gtk.ApplicationWindow(application=application,
                                            type=Gtk.WindowType.TOPLEVEL)
        self.window.set_title("Test Msg Menu")
        self.window.set_default_size(275, 300)

        self.folder_model = MessagePopupModel(self)
        self.folder_menu = Gtk.Menu.new_from_model(self.folder_model)
        self.folder_menu.attach_to_widget(folder_list)

        scrolled_window.show()
        self.window.add(scrolled_window)

        self.window.show()

    def _add_folders(self, store, msg_iter, root):
        msg_iter = store.append(msg_iter, (root.name(), self.folder_pixbuf))
        for info in root.subfolders():
            self._add_folders(store, msg_iter, info)

    def _folders_path(self):
        '''
        Folders Path.

        :returns: The folder path
        :rtype: str
        '''
        path = os.path.join(self.config.platform.config_dir(), "messages")
        if not os.path.isdir(path):
            os.makedirs(path)
        self.logger.info("_folders_path %s", path)
        return path

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
        self.logger.info("folder_rename_edited: %s %s %s", path, new_text,
                         type(store))
        # folder_iter = store.get_iter(path)
        # orig = store.get(folder_iter, 0)[0]
        # if orig == new_text:
        #    return
        # if orig in BASE_FOLDERS:
        #    return
        # info = self.get_folder(self._get_folder_by_iter(store, folder_iter))
        # try:
        #    info.rename(new_text)
        # except OSError as err:
        #    self.logger.info("Unable to rename: %s", err)
        #    return

        # store.set(iter, 0, new_text)

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

        if action_name == "delete":
            self.logger.info("action delete:")
            info = self.get_folder(self.folder_model.folder_name)
            # try:
            #     info.delete_self()
            # except OSError as err:
            #     self.logger.info("Unable to delete folder: %s", err)
            #     return
            # store.remove(msg_iter)
        elif action_name == "create":
            self.logger.info("action create:")
            # parent = self.get_folder(self.folder_model.folder_name)
            # store.insert(msg_iter, 0, ("New Folder", self.folder_pixbuf))

            # self._create_folder(parent, "New Folder")
        elif action_name == "rename":
            self.logger.info("action rename:")
            info = self.get_folder(self.folder_model.folder_name)

            new_text = prompt_for_string("Rename folder `%s' to:" % info.name(),
                                         orig=info.name())
            if not new_text:
                return
            if new_text == info.name():
                return

            # try:
            #     info.rename(new_text)
            # except OSError as err:
            #     self.logger.info("Unable to rename: %s", err)
            #    return

            # store.set(msg_iter, 0, new_text)

    def _select_folder(self, view, event):
        _store, _msg_iter = self._get_selected_folder(view, event)

    def _folder_menu(self, view, event):
        '''
        Folder Menu for mouse_cb handler.

        :param view: Treeview Widget clicked on.
        :type view: :class:`Gtk.TreeView`
        :param event: Button press event
        :type event: :class:`Gtk.EventButton`
        '''
        x_coord, y_coord = event.get_coords()
        self.logger.info("folder_menu:  %s event:%s x: %s y:%s",
                         type(view), type(event), event.x, event.y)

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

        :param view: Treeview Widget clicked on.
        :type view: :class:`Gtk.TreeView`
        :param event: Button press event
        :type event: :class:`Gtk.EventButton`
        '''
        self.logger.info("mouse_cb: %i", event.button)
        if event.button == 1:
            return self._select_folder(view, event)
        if event.button == 3:
            return self._folder_menu(view, event)
        return None

# Pylint wants at least two public methods in a class
# pylint: disable=too-few-public-methods
class TestMsgModel(Gtk.Application):
    '''
    Test application.
    '''

    def __init__(self):
        Gtk.Application.__init__(self,
                                 application_id='localhost.d-rats.test_mm',
                                 flags=Gio.ApplicationFlags.NON_UNIQUE)

        logging.basicConfig(level=logging.INFO)

    # pylint can not detect this for GTK classes.
    # pylint: disable=arguments-differ
    def do_activate(self):
        '''
        Do Activation.

        Emits a :class:`Gio.Application` signal to the application.
        '''
        _test_window = TestMsgModelWindow(self)
        Gtk.Application.do_activate(self)


def main():
    '''UI Message Model Menu Unit test'''

    test_message_model_gui = TestMsgModel()
    test_message_model_gui.run(None)


if __name__ == "__main__":
    main()
