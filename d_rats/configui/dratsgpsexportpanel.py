# File: configui/dratsgpsexport.py

'''D-Rats GPS Export Panel Module.'''

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

if not '_' in locals():
    import gettext
    _ = gettext.gettext

from .dratspanel import DratsPanel
from .dratsconfigwidget import DratsConfigWidget


class DratsGPSExportPanel(DratsPanel):
    '''
    D-Rats GPS Export Panel.

    :param dialog: D-Rats Config UI Dialog
    :type dialog: :class:`config.DratsConfigUI`
    '''
    logger = logging.getLogger("DratsGPSExportConfig")

    # pylint: disable=unused-argument
    def __init__(self, dialog=None):
        DratsPanel.__init__(self)
        val = DratsConfigWidget(section="settings",
                                name="mapserver_active",
                                have_revert=True)
        val.add_bool()
        self.make_view(_("Check to enable export GPS messages as JSON string"),
                       val)

        val = DratsConfigWidget(section="settings",
                                name="mapserver_ip")
        val.add_text(12)
        self.make_view(_("IP address"), val)

        val = DratsConfigWidget(section="settings",
                                name="mapserver_port")
        val.add_text(6)
        self.make_view(_("IP port"), val)
