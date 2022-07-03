'''Main Message Mouse Popup Menu Model.'''
#
# Copyright 2022 John Malmberg <wb8tyw@gmail.com>
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


import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gio


# This makes pylance happy with out overriding settings
# from the invoker of the class
if not '_' in locals():
    import gettext
    _ = gettext.gettext


class MessagePopupModel(Gio.Menu):
    '''
    Creates the Popup Menu for Mouse Click in the Message Window Tab.

    :param widget: The message folder widget
    :type widget: :class:`MessageFolders`
    '''

    BASE_FOLDERS = [_("Inbox"), _("Outbox"), _("Sent"),
                    _("Trash"), _("Drafts")]

    MENU_ACTIONS = [("delete", _("Delete"), "chat-delfilter.png"),
                    ("create", _("Create"), "chat-addfilter.png"),
                    ("rename", _("Rename"), None)]

    MENU_DELETE_ACTIONS = ["delete", "rename"]

    delete_icon = None
    new_icon = None
    folder_name = None
    folder_store = None
    folder_iter = None

    def __init__(self, widget):
        Gio.Menu.__init__(self)

        self.actions = {}
        # The actual popup menu has to be in a section.
        menu_popup = Gio.Menu()

        for action_name, label, _icon_file, in self.MENU_ACTIONS:
            # The action name needs a "win." prefix
            menu_item = Gio.MenuItem.new(label, "win.%s" % action_name)
            menu_popup.append_item(menu_item)
            action = Gio.SimpleAction(name=action_name,
                                      parameter_type=None,
                                      enabled=True)
            # This does not work, the icon does not display.
            # if _icon_file:
            #    icon_path = widget.config.ship_obj_fn(
            #        os.path.join("images", icon_file))
            #    gio_file = Gio.File.new_for_path(icon_path)
            #    file_icon = Gio.FileIcon.new(gio_file)
            #    menu_item.set_icon(file_icon)
            widget.window.add_action(action)
            action.connect('activate', widget.popup_menu_handler)
            self.actions[action_name] = action
        self.append_section(None, menu_popup)

    @classmethod
    def _menu_params(cls, folder, store, folder_iter):
        '''
        Store parameter for current menu selection

        The Gio Action handlers can only handle simple types, not anything
        as complex as the specific GTK widgets that we want to use in the
        handler.

        Taking advantage that there will only be one active instance
        of the popup menu using this model active ever, we can also
        use class storage of this method to pass the parameters.

        :param folder: Folder for menu to act on.
        :type folder: str
        :param store: Tree store widget
        :type store: :class:`Gtk.TreeStore`
        :param folder_iter: Message iterator
        :type folder_iter: :class:`Gtk.TreeIter`
        '''
        cls.folder_name = folder
        cls.folder_store = store
        cls.folder_iter = folder_iter

    def change_state(self, folder, store, folder_iter):
        '''
        Update state to current selection.

        :param folder: Folder for menu to act on.
        :type folder: str
        :param store: Tree store widget
        :type store: :class:`Gtk.TreeStore`
        :param folder_iter: Message iterator
        :type folder_iter: :class:`Gtk.TreeIter`
        '''
        self._menu_params(folder, store, folder_iter)
        no_delete = not bool(folder and (folder not in self.BASE_FOLDERS))
        for action_name, _label, _icon in self.MENU_ACTIONS:
            enable = True
            if no_delete and action_name in self.MENU_DELETE_ACTIONS:
                enable = False
            # hack to pass complex objects to the menu
            self.actions[action_name].set_enabled(enable)
