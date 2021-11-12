'''Map Window Module.'''
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

import logging

import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk

class MapWindow(Gtk.Window):
    '''
    Map Window.

    This Creates the main map window display.

    :param config: Config object
    :param args: Optional arguments
    '''

    #__gsignals__ = {
    #    "reload-sources" : (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE, ()),
    #    "user-send-chat" : signals.USER_SEND_CHAT,
    #    "get-station-list" : signals.GET_STATION_LIST,
    #    }

    #_signals = {"user-send-chat" : None,
    #            "get-station-list" : None,
    #            }

    def __init__(self, config):
        Gtk.Window.__init__(self, type=Gtk.WindowType.TOPLEVEL)

        self.logger = logging.getLogger("MapWindow")

        self.connect("destroy", Gtk.main_quit)
        self.config = config
        self.marker_list = None
        self.map_tiles = []
        self.logger.info("Testing MapWindow")

    @staticmethod
    def test():
        '''Test method.''' 
        Gtk.main()
