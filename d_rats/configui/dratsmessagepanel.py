# File: configui/dratsmessagepanel.py

'''D-Rats Message Panel Module.'''

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
from .dratspanel import disable_by_combo
from .dratspanel import disable_with_toggle
from .dratsconfigwidget import DratsConfigWidget

class DratsMessagePanel(DratsPanel):
    '''
    D-Rats Message Panel.

    :param dialog: D-Rats Config UI Dialog
    :type dialog: :class:`config.DratsConfigUI`
    '''
    logger = logging.getLogger("DratsMessagePanel")

    # pylint wants a max of 15 local variables
    # pylint wants a max of 50 statements
    # pylint: disable=too-many-locals, too-many-statements, unused-argument
    def __init__(self, dialog=None):
        DratsPanel.__init__(self)

        vala = DratsConfigWidget(section="settings", name="msg_forward")
        vala.add_bool()
        self.make_view(_("Automatically forward messages"), vala)

        val = DratsConfigWidget(section="settings", name="msg_flush")
        val.add_numeric(15, 9999, 1)
        lab = Gtk.Label.new(_("seconds"))
        self.make_view(_("Queue flush interval"), val, lab)
        disable_with_toggle(vala.child_widget, val.child_widget)

        val = DratsConfigWidget(section="settings", name="station_msg_ttl")
        val.add_numeric(0, 99999, 1)
        lab = Gtk.Label.new(_("seconds"))
        self.make_view(_("Station TTL"), val, lab)
        disable_with_toggle(vala.child_widget, val.child_widget)

        val = DratsConfigWidget(section="prefs", name="msg_include_reply")
        val.add_bool()
        self.make_view(_("Include original in reply"), val)

        val = DratsConfigWidget(section="prefs", name="msg_allow_pop3")
        val.add_bool()
        self.make_view(_("Allow POP3 Gateway"), val)

        vala = DratsConfigWidget(section="prefs", name="msg_allow_wl2k")
        vala.add_bool()
        self.make_view(_("Allow WL2K Gateway"), vala)

        wlm = DratsConfigWidget(section="settings", name="msg_wl2k_mode")
        wlm.add_combo(["Network", "RMS"], False)
        self.make_view(_("WL2K Connection"), wlm)

        wl2k_servers = [x + ".winlink.org" for x in ["server",
                                                     "perth",
                                                     "halifax",
                                                     "sandiego",
                                                     "wien"]]
        srv = DratsConfigWidget(section="prefs", name="msg_wl2k_server")
        srv.add_combo(wl2k_servers, True)
        prt = DratsConfigWidget(section="prefs", name="msg_wl2k_port")
        prt.add_numeric(1, 65535, 1)
        lab = Gtk.Label.new(_("Port"))
        pwd = DratsConfigWidget(section="prefs", name="msg_wl2k_password")
        pwd.add_pass()
        ptab = Gtk.Label.new(_("Password"))
        self.make_view(_("WL2K Network Server"), srv, lab, prt, ptab, pwd)

        rms = DratsConfigWidget(section="prefs", name="msg_wl2k_rmscall")
        rms.add_upper_text(10)

        lab = Gtk.Label.new(_(" on port "))

        ports = []
        if self.config.has_section("ports"):
            for port in self.config.options("ports"):
                spec = self.config.get("ports", port).split(",")
                if "agwpe" in spec[1]:
                    ports.append(spec[-1])

        rpt = DratsConfigWidget(section="prefs", name="msg_wl2k_rmsport")
        rpt.add_combo(ports, False)
        self.make_view(_("WL2K RMS Station"), rms, lab, rpt)

        net_map = {
            "Network" : [srv.child_widget, prt.child_widget, pwd.child_widget],
            "RMS"     : [rms.child_widget, rpt.child_widget],
            }
        disable_by_combo(wlm.child_widget, net_map)
        disable_with_toggle(vala.child_widget, wlm.child_widget)

        ssids = [""] + [str(x) for x in range(1, 11)]
        val = DratsConfigWidget(section="prefs", name="msg_wl2k_ssid")
        val.add_combo(ssids, True)
        self.make_view(_("My Winlink SSID"), val)

        p3s = DratsConfigWidget(section="settings", name="msg_pop3_server")
        p3s.add_bool()
        lab = Gtk.Label.new(_("on port"))
        p3p = DratsConfigWidget(section="settings", name="msg_pop3_port")
        p3p.add_numeric(1, 65535, 1)
        self.make_view(_("POP3 Server"), p3s, lab, p3p)
        disable_with_toggle(p3s.child_widget, p3p.child_widget)

        sms = DratsConfigWidget(section="settings", name="msg_smtp_server")
        sms.add_bool()
        lab = Gtk.Label.new(_("on port"))
        smp = DratsConfigWidget(section="settings", name="msg_smtp_port")
        smp.add_numeric(1, 65535, 1)
        self.make_view(_("SMTP Server"), sms, lab, smp)
        disable_with_toggle(sms.child_widget, smp.child_widget)
