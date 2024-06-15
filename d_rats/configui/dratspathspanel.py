# configui/dratspathspanel.py

'''D-Rats Paths Panel Module.'''

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


class DratsPathsPanel(DratsPanel):
    '''
    D-Rats Paths Panel.

    :param dialog: D-Rats Config UI Dialog, Unused
    :type dialog: :class:`config.DratsConfigUI`

    '''
    logger = logging.getLogger("DratsPathsPanel")

    # pylint: disable=unused-argument
    def __init__(self, dialog=None):
        DratsPanel.__init__(self)

        val = DratsConfigWidget(section="prefs",
                                name="download_dir",
                                have_revert=True)
        val.add_path()
        self.make_view(_("File Transfer Path"), val)

        val = DratsConfigWidget(section="settings",
                                name="mapdir",
                                have_revert=True)
        val.add_path()
        self.make_view(_("Base Map Storage Path"), val)

        val = DratsConfigWidget(section="settings",
                                name="form_logo_dir",
                                have_revert=True)
        val.add_path()
        self.make_view(_("Form Logo Path"), val)
