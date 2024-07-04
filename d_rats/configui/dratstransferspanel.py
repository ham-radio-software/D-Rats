# File: configui/dratstransferpanel.py

'''D-Rats Transfers Panel Module.'''

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


class DratsTransfersPanel(DratsPanel):
    '''
    D-Rats Transfers Panel.

    :param dialog: D-Rats Config UI Dialog
    :type dialog: :class:`config.DratsConfigUI`
    '''
    logger = logging.getLogger("DratsTransfersPanel")

    # pylint: disable=unused-argument
    def __init__(self, dialog=None):
        DratsPanel.__init__(self)

        val = DratsConfigWidget(section="settings",
                                name="ddt_block_size",
                                have_revert=True)
        val.add_numeric(32, 4096, 32)
        self.make_view(_("Block size"), val)

        val = DratsConfigWidget(section="settings",
                                name="ddt_block_outlimit",
                                have_revert=True)
        val.add_numeric(1, 32, 1)
        self.make_view(_("Pipeline blocks"), val)

        val = DratsConfigWidget(section="prefs", name="allow_remote_files")
        val.add_bool()
        self.make_view(_("Remote file transfers"), val)

        val = DratsConfigWidget(section="settings",
                                name="warmup_length",
                                have_revert=True)
        val.add_numeric(0, 64, 8)
        self.make_view(_("Warmup Length"), val)

        val = DratsConfigWidget(section="settings",
                                name="warmup_timeout",
                                have_revert=True)
        val.add_numeric(0, 16, 1)
        self.make_view(_("Warmup timeout"), val)

        val = DratsConfigWidget(section="settings",
                                name="force_delay",
                                have_revert=True)
        val.add_numeric(-32, 32, 1)
        self.make_view(_("Force transmission delay"), val)

        val = DratsConfigWidget(section="settings", name="delete_from")
        val.add_text()
        self.make_view(_("Allow file deletes from"), val)

        val = DratsConfigWidget(section="settings", name="remote_admin_passwd")
        val.add_pass()
        self.make_view(_("Remote admin password"), val)
