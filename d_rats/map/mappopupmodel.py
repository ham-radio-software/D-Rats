'''Map Mouse Popup Menu Model Module.'''
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


# This makes pylance happy with out overriding settings
# from the invoker of the class
if not '_' in locals():
    import gettext
    _ = gettext.gettext


# pylint wants at least 2 public methods.
# pylint disable=too-few-public-methods
class MapPopupModel(Gio.Menu):
    '''
    Creates the Popup Menu for Mouse Click in the MapWidget.

    :param position: Map Position for menu title
    :type position: :class:`Map.MapPosition`
    '''

    def __init__(self, position):
        Gio.Menu.__init__(self)

        menu_popup = Gio.Menu()
        menu_popup.append(_("Center here"), 'win.center')
        menu_popup.append(_("New marker here"), 'win.newmarker')
        menu_popup.append(_("Broadcast this location"), 'win.broadcast')
        self.append_section(str(position), menu_popup)

    @staticmethod
    def add_actions(window):
        '''
        Add menu actions to the window.

        :param window: The map window
        :type window: :class:`Map.Mapwindow`
        '''

        action_center = Gio.SimpleAction(name='center',
                                         parameter_type=None,
                                         enabled=True)
        action_center.connect('activate', window.popup_center_handler)
        window.add_action(action_center)

        action_newmarker = Gio.SimpleAction(name='newmarker',
                                            parameter_type=None,
                                            enabled=True)
        action_newmarker.connect('activate', window.popup_newmarker_handler)
        window.add_action(action_newmarker)

        action_broadcast = Gio.SimpleAction(name='broadcast',
                                            parameter_type=None,
                                            enabled=True)
        action_broadcast.connect('activate', window.popup_broadcast_handler)
        window.add_action(action_broadcast)
