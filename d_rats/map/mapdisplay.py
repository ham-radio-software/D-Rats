#!/usr/bin/python
'''Map Display Unit Test for GTK3'''
#
# Copyright 2021-2022 John Malmberg <wb8tyw@gmail.com>
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

gi.require_version('Gtk', '3.0')
from gi.repository import Gio
from gi.repository import Gtk

from d_rats.dplatform import get_platform
from d_rats import config
from d_rats import map_sources

import d_rats.map as Map


# This makes pylance happy with out overriding settings
# from the invoker of the class
if not '_' in locals():
    import gettext
    _ = gettext.gettext


class MapDisplay(Gtk.Application):
    '''
    Map Display application.

    :param cmd_args: Parsed command line arguments
    :type cmd_args: Namespace
    '''

    def __init__(self, cmd_args):
        Gtk.Application.__init__(self,
                                 application_id='localhost.d-rats.map',
                                 flags=Gio.ApplicationFlags.NON_UNIQUE)

        # Each class should have their own logger.
        self.logger = logging.getLogger("mapdisplay")

        self.config = config.DratsConfig(None)
        self.cmd_args = cmd_args
        get_platform(cmd_args.config)

        maptype = self.config.get("settings", "maptype")
        if maptype == "cycle":
            mapurl = self.config.get("settings", "mapurlcycle")
            mapkey = self.config.get("settings", "keyformapurlcycle")
        elif maptype == "landscape":
            mapurl = self.config.get("settings", "mapurllandscape")
            mapkey = self.config.get("settings", "keyformapurllandscape")
        elif maptype == "outdoors":
            mapurl = self.config.get("settings", "mapurloutdoors")
            mapkey = self.config.get("settings", "keyformapurloutdoors")
        else:
            mapurl = self.config.get("settings", "mapurlbase")
            mapkey = None

        Map.Tile.set_connected(True)

        lifetime = self.config.getint("settings", "map_tile_ttl") * 3000
        Map.Tile.set_tile_lifetime(lifetime)
        mapdir = self.config.get("settings", "mapdir")

        map_path = os.path.join(mapdir, maptype)

        Map.Tile.set_map_info(map_path, mapurl, mapkey)
        Map.Tile.set_proxy = self.config.get("settings", "http_proxy") or None
        self.map_window = None
        self.stations_overlay = None

    # pylint: disable=arguments-differ
    def do_activate(self):
        '''
        Do Activation.

        Emits a :class:`Gio.Application` signal to the application.
        '''
        map_window = Map.Window(self, self.config)
        self.map_window = map_window  # Temporary
        map_window.set_title("D-RATS Test Map Window - map in use: %s" %
                             self.config.get("settings", "maptype"))

        map_window.set_center(self.cmd_args.latitude,
                              self.cmd_args.longitude)
        map_window.set_zoom(14)
        Gtk.Application.do_activate(self)

        self.load_map_overlays()
        # Have map exit on close for test.
        map_window.exiting = True
        map_window.show()

    def load_map_overlays(self):
        '''Load Map Overlays.'''
        self.stations_overlay = None

        # self.map.clear_map_sources()

        # wb8tyw - The USGS has changed their URL and API
        # We need to recode that class to the new API.
        # The Map code also needs to be fixed to use lxml.
        source_types = [map_sources.MapFileSource,
                        map_sources.MapUSGSRiverSource,
                        map_sources.MapNBDCBuoySource]

        for stype in source_types:
            try:
                sources = stype.enumerate(self.config)
            except (TypeError, ValueError):
                # ValueError from lxml conversion needed.
                self.logger.info("_load_map_overlays not working.  "
                                 "USGS changed URls/APIs.",
                                 exc_info=True)
                sources = []

            for sname in sources:
                source = stype.open_source_by_name(self.config, sname)
                self.map_window.add_map_source(source)
                if sname == _("Stations"):
                    self.stations_overlay = source

        if not self.stations_overlay:
            fname = os.path.join(self.config.platform.config_dir(),
                                 "static_locations",
                                 _("Stations") + ".csv")
            try:
                # python 3 can be set to not raise this error
                os.makedirs(os.path.dirname(fname))
            except OSError as err:
                if err.errno != 17:  # File or directory exists
                    raise
            open(fname, "w").close()
            self.stations_overlay = map_sources.MapFileSource(_("Stations"),
                                                              "Static Overlay",
                                                              fname)


def main():
    '''Main function for unit testing.'''

    import argparse

    gettext.install("D-RATS")
    lang = gettext.translation("D-RATS",
                               localedir="locale",
                               fallback=True)
    lang.install()
    # pylint: disable=global-statement
    global _
    _ = lang.gettext

    # pylint: disable=too-few-public-methods
    class LoglevelAction(argparse.Action):
        '''
        Custom Log Level action.

        This allows entering a log level command line argument
        as either a known log level name or a number.
        '''

        def __init__(self, option_strings, dest, nargs=None, **kwargs):
            if nargs is not None:
                raise ValueError("nargs is not allowed")
            argparse.Action.__init__(self, option_strings, dest, **kwargs)

        def __call__(self, parser, namespace, values, option_strings=None):
            level = values.upper()
            level_name = logging.getLevelName(level)
            # Contrary to documentation, the above returns for me
            # an int if given a name or number of a known named level and
            # str if given a number for a level with out a name.
            if isinstance(level_name, int):
                level_name = level
            elif level_name.startswith('Level '):
                level_name = int(level)
            setattr(namespace, self.dest, level_name)

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description=_('MAP DISPLAY TEST'))
    parser.add_argument('-c', '--config',
                        default=get_platform().config_dir(),
                        help=_("USE ALTERNATE CONFIGURATION DIRECTORY"))

    # While loglevel actually returns an int, it needs to be set to the
    # default type of str for the action routine to handle both named and
    # numbered levels.
    parser.add_argument('--loglevel',
                        action=LoglevelAction,
                        default='INFO',
                        help=_('LOGLEVEL TO TEST WITH'))

    # Default latitude and longitude
    parser.add_argument('--latitude',
                        type=float,
                        default=45.525012,
                        help=_('INITIAL LATITUDE'))
    parser.add_argument('--longitude',
                        type=float,
                        default=-122.916434,
                        help=_('INITIAL LONGITUDE'))

    args = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
        datefmt="%m/%d/%Y %H:%M:%S",
        level=args.loglevel)

    # WB8TYW: DratsConfig takes an unused argument.

    #zoom = 14
    # if len(sys.argv) == 3:
        # logger.warning('Processing DMS codes not implemented!')
        # zoom = 15
        # x_coord = gps.parse_dms(sys.argv[1])
        # y_coord = gps.parse_dms(sys.argv[2])
    # else:
        # logger.warning('processing default case not implemented.')
        # m.set_marker(GPSPosition(station="KI4IFW_H",
        #                          lat=45.520, lon=-122.916434))
        # m.set_marker(GPSPosition(station="KE7FTE",
        #                          lat=45.5363, lon=-122.9105))
        # m.set_marker(GPSPosition(station="KA7VQH",
        #                          lat=45.4846, lon=-122.8278))
        # m.set_marker(GPSPosition(station="N7QQU",
        #                          lat=45.5625, lon=-122.8645))
        # m.del_marker("N7QQU")

    # logger.info('Executing Unit test function.')

    # map_window = Map.Window(conf)
    # map_window.set_center(x_coord, y_coord)
    # map_window.set_zoom(zoom)

    # map_window.show()

    # Map.Window.test()
    map_display = MapDisplay(cmd_args=args)
    map_display.run(None)

if __name__ == "__main__":
    main()
