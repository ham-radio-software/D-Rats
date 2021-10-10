#!/usr/bin/python
'''Map Display Unit Test for GTK3'''
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

import gettext
import logging
# import cairo
# import gi
# gi.require_version("Gtk", "3.0")

# from gi.repository import Gtk
# from gi.repository import Gdk
# from gi.repository import GdkPixbuf
# from gi.repository import GObject
# from gi.repository import GLib
# gi.require_version("PangoCairo", "1.0")
# from gi.repository import PangoCairo

_ = gettext.gettext


def main():
    '''Main function for unit testing.'''

    import sys
    # printlog("Mapdisplay", ": __Executing __main__ section")
    # from . import gps
    # from . import config

    lang = gettext.translation("D-RATS",
                               localedir="./locale",
                               languages=["en"],
                               fallback=True)
    lang.install()

    # WB8TYW: DratsConfig takes an unused argument.
    # conf = config.DratsConfig(None)

    # mapurl = conf.get("settings", "mapurlbase")
    # mapkey = ""

    # set_connected(True)
    # set_tile_lifetime(conf.getint("settings", "map_tile_ttl") * 3600)


    # set_base_dir(os.path.join(conf.get("settings", "mapdir"),
    #                          conf.get("settings", "maptype")), mapurl, mapkey)
    # proxy = conf.get("settings", "http_proxy") or None
    # set_proxy(proxy)

    # We should use a package to parse configuration options here
    # for now this will be need to be edited as needed.

    # This logging config must be done before logging anything.
    # Default is "WARNING" is tracked.

    # Eventually this logging should be used for both stdout/file and for the
    # logging to the D-rats event window.
    # A handler will be used to route messages to the D-RATS event window.

    logging.basicConfig(level=logging.INFO)

    # Each class should have their own logger.
    logger = logging.getLogger("mapdisplay3")

    if len(sys.argv) == 3:
        logger.warning('Processsing DMS coords not implemented')
        # map_window = MapWindow(conf)
        # map_window.set_center(gps.parse_dms(sys.argv[1]),
        #                       gps.parse_dms(sys.argv[2]))
        # map_window.set_zoom(15)
    else:
        logger.warning('processing default case not implemented.')
        # map_window = MapWindow(config)
        # map_window.set_center(45.525012, -122.916434)
        # map_window.set_zoom(14)

        # m.set_marker(GPSPosition(station="KI4IFW_H",
        #                          lat=45.520, lon=-122.916434))
        # m.set_marker(GPSPosition(station="KE7FTE",
        #                          lat=45.5363, lon=-122.9105))
        # m.set_marker(GPSPosition(station="KA7VQH",
        #                          lat=45.4846, lon=-122.8278))
        # m.set_marker(GPSPosition(station="N7QQU",
        #                          lat=45.5625, lon=-122.8645))
        # m.del_marker("N7QQU")

    logger.info('Exectuting Unit test function.')

    # map_window.connect("destroy", Gtk.main_quit)
    # map_window.show()

    # try:
    # Gtk.main()
    # pylint: disable=bare-except
    # except:
    #    pass

if __name__ == "__main__":
    main()
