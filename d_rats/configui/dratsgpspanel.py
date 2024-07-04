# File configui/dratsgpspanel.py

'''D-Rats GPS Panel Module.'''

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

from serial import Serial
from ..aprs_dprs import AprsDprsCodes
from ..aprs_icons import APRSicons
from .dratspanel import DratsPanel
from .dratspanel import disable_with_toggle
from .dratsconfigwidget import DratsConfigWidget

from ..geocode_ui import AddressAssistant
from ..dplatform import Platform


class DratsGPSPanel(DratsPanel):
    '''
    D-rats GPS Panel.

    :param dialog: D-Rats Config UI Dialog
    :type dialog: :class:`config.DratsConfigUI`
   '''
    logger = logging.getLogger("DratsGPSPanel")

    # pylint: disable=too-many-locals, too-many-statements
    def __init__(self, dialog=None):
        DratsPanel.__init__(self)

        lon = DratsConfigWidget(section="user", name="longitude")
        lat = DratsConfigWidget(section="user", name="latitude")
        if AddressAssistant.have_geocode():
            # Geo IP lookup is an optional feature
            geo = AddressAssistant.button(_("Lookup"), lat, lon, dialog)
            self.make_view(_("From Address"), geo)

        lat.add_coords()
        self.make_view(_("Latitude"), lat)

        lon.add_coords()
        self.make_view(_("Longitude"), lon)

        alt = DratsConfigWidget(section="user", name="altitude")
        alt.add_numeric(0, 29028, 1)
        self.make_view(_("Altitude"), alt)

        ports = Platform.get_platform().list_serial_ports()

        val = DratsConfigWidget(section="settings", name="gpsenabled")
        val.add_bool()
        self.make_view(_("Use External GPS"), val)

        port = DratsConfigWidget(section="settings", name="gpsport")
        port.add_combo(ports, True, 120)
        rate = DratsConfigWidget(section="settings", name="gpsportspeed")
        baudrates = [str(baudrate) for baudrate in list(Serial.BAUDRATES)]
        rate.add_combo(baudrates, False)
        self.make_view(_("External GPS"), port, rate)
        disable_with_toggle(val.child_widget, port.child_widget)
        disable_with_toggle(val.child_widget, rate.child_widget)

        def gpsa_symbol(_button, val1, val2, aprs_icon):
            '''
            GPS APRS symbol information.

            :param _button: Button widget, unused
            :type _button: :class:`Gtk.Button`
            :param val1: APRS Table Configuration Widget
            :type val1: :class:`DratsConfigWidget`
            :param val2: APRS Symbol Configuration Widget
            :type val1: :class:`DratsConfigWidget`
            :param aprs_icon: Aprs Icon to update
            :type aprs_icon: :class:`Gtk.Image`
            '''
            aprs_table = val1.child_widget.get_text()
            aprs_symbol = val2.child_widget.get_text()
            code = aprs_table + aprs_symbol
            aprs = APRSicons.aprs_selection(code=code)
            if aprs is not None:
                self.config.set("settings", "aprssymtab", aprs[0])
                self.config.set("settings", "aprssymbol", aprs[1])
                val1.child_widget.set_text(aprs[0])
                val2.child_widget.set_text(aprs[1])
                pixbuf = APRSicons.get_icon(code=aprs)
                aprs_icon.set_from_pixbuf(pixbuf)

        val1 = DratsConfigWidget("settings", "aprssymtab")
        val1.add_text(1)
        val1.set_sensitive(False)
        val2 = DratsConfigWidget("settings", "aprssymbol")
        val2.add_text(1)
        val2.set_sensitive(False)
        aprs_icon = Gtk.Image.new()
        aprs_table = val1.child_widget.get_text()
        aprs_symbol = val2.child_widget.get_text()
        aprs_code = aprs_table + aprs_symbol
        pixbuf = APRSicons.get_icon(code=aprs_code)
        aprs_icon.set_from_pixbuf(pixbuf)
        aprs_button = Gtk.Button.new_with_label(_("Edit"))
        aprs_button.connect("clicked", gpsa_symbol, val1, val2, aprs_icon)

        self.make_view(_("GPS-A Symbol"),
                       aprs_button,
                       aprs_icon,
                       Gtk.Label.new(_("Table:")), val1,
                       Gtk.Label.new(_("Symbol:")), val2)

        def gps_comment_from_dprs(_button, val, dprs_icon):
            '''
            GPS Comment from DPRS button clicked handler.

            :param _button: Button widget, unused
            :type _button: :class:`Gtk.Button`
            :param val: GPS Enabled Configuration Widget
            :type val: :class:`DratsConfigWidget`
            :param dprs_icon: Aprs Icon to update
            :type dprs_icon: :class:`Gtk.Image`
            '''
            dprs = APRSicons.dprs_selection(
                callsign=self.config.get("user", "callsign"),
                initial=self.config.get("settings", "default_gps_comment"))
            self.logger.debug("Setting GPS comment to DPRS: %s ", dprs)
            if dprs is not None:
                self.config.set("settings", "default_gps_comment", dprs)
                val.child_widget.set_text(dprs)
                dprs_info = APRSicons.parse_dprs_message(text=dprs)
                if 'code' in dprs_info:
                    dprs_code = dprs_info['code']
                    if 'overlay' in dprs_info:
                        dprs_code = dprs_info['code'] + dprs_info['overlay']
                    aprs_code = AprsDprsCodes.dprs_to_aprs(
                        code=dprs_code,
                        default=AprsDprsCodes.APRS_FALLBACK_CODE)
                    pixbuf = APRSicons.get_icon(code=aprs_code)
                    dprs_icon.set_from_pixbuf(pixbuf)

        val = DratsConfigWidget(section="settings", name="default_gps_comment")
        val.add_text(20)
        val.set_sensitive(False)
        dprs_comment = self.config.get("settings", "default_gps_comment")
        dprs_info = APRSicons.parse_dprs_message(text=dprs_comment)
        if 'code' in dprs_info:
            dprs_code = dprs_info['code']
            if 'overlay' in dprs_info:
                dprs_code = dprs_info['code'] + dprs_info['overlay']
        else:
            dprs_code = '  '
        aprs_code = AprsDprsCodes.dprs_to_aprs(
            code=dprs_code,
            default=AprsDprsCodes.APRS_FALLBACK_CODE)
        pixbuf = APRSicons.get_icon(code=aprs_code)
        dprs_icon = Gtk.Image.new()
        dprs_icon.set_from_pixbuf(pixbuf)
        dprs_button = Gtk.Button.new_with_label(_("Edit"))
        dprs_button.connect("clicked", gps_comment_from_dprs, val, dprs_icon)
        self.make_view(_("Default GPS comment"), dprs_button, dprs_icon, val)
