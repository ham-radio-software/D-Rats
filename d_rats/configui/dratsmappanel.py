# File: configui/dratsmappanel.py

'''D-Rats MAP Panel Module.'''

# Copyright 2009 Dan Smith <dsmith@danplanet.com>
# review 2015-2020 Maurizio Andreotti  <iz2lxi@yahoo.it>
# Copyright 2021-2024 John. E. Malmberg - Python3 Conversion
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

import logging

import gi  # type: ignore # Needed for pylance on Windows.
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk        # type: ignore

if not '_' in locals():
    import gettext
    _ = gettext.gettext

from .dratspanel import DratsPanel
from .dratsconfigwidget import DratsConfigWidget


class DratsMapPanel(DratsPanel):
    '''
    D-Rats MAP Panel.

    :param dialog: D-Rats Config UI Dialog, unused
    :type dialog: :class:`config.DratsConfigUI`

    '''
    logger = logging.getLogger("DratsMapPanel")

    # pylint: disable=unused-argument
    def __init__(self, dialog=None):
        DratsPanel.__init__(self)

        #asking which map to use
        val = DratsConfigWidget(section="settings", name="maptype")
        val.add_combo(["base", "cycle", "outdoors", "landscape"])
        self.make_view(_("Map to use"), val)

        val = DratsConfigWidget(section="settings",
                                name="mapurlbase",
                                have_revert=True)
        val.add_text()
        self.make_view(_("BaseMap server url"), val)

        # open cycle
        val = DratsConfigWidget(section="settings",
                                name="mapurlcycle",
                                have_revert=True)
        val.add_text()
        self.make_view(_("OpenCycleMap server url"), val)

        val = DratsConfigWidget(section="settings",
                                name="keyformapurlcycle",
                                have_revert=True)
        val.add_text()
        self.make_view(_("Key string to append to CycleMap url"), val)

        #landscape
        val = DratsConfigWidget(section="settings",
                                name="mapurllandscape",
                                have_revert=True)
        val.add_text()
        self.make_view(_("Landscape server url"), val)

        val = DratsConfigWidget(section="settings",
                                name="keyformapurllandscape",
                                have_revert=True)
        val.add_text()
        self.make_view(_("Key string to append to landscape url"), val)

        #outdoors
        val = DratsConfigWidget(section="settings",
                                name="mapurloutdoors",
                                have_revert=True)
        val.add_text()
        self.make_view(_("Outdoors server url"), val)

        val = DratsConfigWidget(section="settings",
                                name="keyformapurloutdoors",
                                have_revert=True)
        val.add_text()
        self.make_view(_("Key string to append to outdoors url"), val)

        val = DratsConfigWidget(section="settings",
                                name="map_tile_ttl")
        val.add_numeric(0, 9999999999999, 1)
        self.make_view(_("Freshen map after"), val, Gtk.Label.new(_("hours")))

        val = DratsConfigWidget(section="settings",
                                name="timestamp_positions")
        val.add_bool()
        self.make_view(_("Report position timestamps on map"), val)
