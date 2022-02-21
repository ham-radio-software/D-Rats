'''Map Marker Popup Menu Model Module.'''
#
# Copyright 2021 John Malmberg <wb8tyw@gmail.com>
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

# import logging

import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gio
from gi.repository import GLib


# This makes pylance happy with out overriding settings
# from the invoker of the class
if not '_' in locals():
    import gettext
    _ = gettext.gettext


class MarkerPopupModel(Gio.Menu):
    '''
    Creates the Popup Menu for Markers.
    '''

    def __init__(self):
        Gio.Menu.__init__(self)

        self.append(_("Edit"), 'win.edit_marker')
        self.append(_("Delete"), 'win.delete_marker')
        self.append(_("Center on this"), 'win.center_marker')
        group_var = GLib.Variant.new_string("")
        ident_var = GLib.Variant.new_string("")
        params = GLib.Variant.new_tuple(group_var, ident_var)
        self.action_center = Gio.SimpleAction.new_stateful(name='center_marker',
                                                           parameter_type=None,
                                                           state=params)
        self.action_delete = Gio.SimpleAction.new_stateful(name='delete_marker',
                                                           parameter_type=None,
                                                           state=params)
        self.action_edit = Gio.SimpleAction.new_stateful(name='edit_marker',
                                                         parameter_type=None,
                                                         state=params)

    def add_actions(self, window):
        '''
        Add menu actions to the window.

        :param window: The map window
        :type window: :class:`Map.MapWindow`
        '''
        self.action_center.connect('activate', window.marker_center_handler)
        window.add_action(self.action_center)

        self.action_delete.connect('activate', window.marker_delete_handler)
        window.add_action(self.action_delete)

        self.action_edit.connect('activate', window.marker_edit_handler)
        window.add_action(self.action_edit)

    def change_state(self, group, ident):
        '''
        Update state to current selection.

        :param group: Group name for marker
        :type group: str
        :param ident: Identity of marker
        :type ident: str
        '''
        group_var = GLib.Variant.new_string(group)
        ident_var = GLib.Variant.new_string(ident)
        params = GLib.Variant.new_tuple(group_var, ident_var)
        self.action_center.change_state(params)
        self.action_delete.change_state(params)
        self.action_edit.change_state(params)
