# File: configui/dratsappearancepanel.py

'''D-Rats Appearance Panel Module.'''

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
from ..spell import get_spell


class DratsAppearancePanel(DratsPanel):
    '''
    D-Rats Appearance Panel.

    :param dialog: D-Rats Config UI Dialog
    :type dialog: :class:`config.DratsConfigUI`
    '''
    logger = logging.getLogger("DratsAppearancePanel")

    # pylint: disable=unused-argument
    def __init__(self, dialog=None):
        DratsPanel.__init__(self)

        val = DratsConfigWidget(section="prefs", name="noticere")
        val.add_text()
        self.make_view(_("Notice RegEx"), val)

        val = DratsConfigWidget(section="prefs", name="ignorere")
        val.add_text()
        self.make_view(_("Ignore RegEx"), val)

        colors = ["Incoming", "Outgoing", "Notice",
                  "Ignore", "Callsign", "Broken"]

        # Mark these strings so they get picked up and become available
        # to the _(i) below
        _trans_colors = [_("Incoming Color"), _("Outgoing Color"),
                         _("Notice Color"), _("Ignore Color"),
                         _("Callsign Color"), _("Broken Color")]

        for i in colors:
            low = i.lower()
            val = DratsConfigWidget(section="prefs", name="%scolor" % low)
            val.add_color()
            self.make_view(_("%s Color" % i), val)

        sizes = [_("Default"), _("Large"), _("Small")]
        val = DratsConfigWidget(section="prefs", name="toolbar_button_size")
        val.add_combo(sizes, False)
        self.make_view(_("Toolbar buttons"), val)

        val = DratsConfigWidget(section="prefs", name="check_spelling")
        val.add_bool()
        self.make_view(_("Check spelling"), val)
        sp_val = get_spell()
        val.child_widget.set_sensitive(sp_val.test())

        val = DratsConfigWidget(section="prefs", name="confirm_exit")
        val.add_bool()
        self.make_view(_("Confirm exit"), val)

        val = DratsConfigWidget(section="settings", name="expire_stations")
        val.add_numeric(0, 9999, 1)
        cap = Gtk.Label.new(_("minutes"))
        self.make_view(_("Expire stations after"), val, cap)
