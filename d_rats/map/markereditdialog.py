'''Map Marker Dialog Module.'''
#
# Copyright 2021-2023 John Malmberg <wb8tyw@gmail.com>
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

from ..aprs_dprs import AprsDprsCodes
from ..aprs_icons import APRSicons
from ..geocode_ui import AddressAssistant
from .. import inputdialog
from ..latlonentry import LatLonEntry
from .. import map_sources
from .. import miscwidgets

# This makes pylance happy with out overriding settings
# from the invoker of the class
if not '_' in locals():
    import gettext
    _ = gettext.gettext

# Pylint wants only 7 instance attributes
# pylint: disable=too-many-instance-attributes
class MarkerEditDialog(inputdialog.FieldDialog):
    '''Marker Edit Dialog.'''

    logger = logging.getLogger("MarkerEditDialog")

    def __init__(self):
        inputdialog.FieldDialog.__init__(self, title=_("Add Marker"))
        self.icons = []
        aprs_dict = AprsDprsCodes.get_aprs_to_dprs()
        for code in sorted(aprs_dict):
            pixbuf = APRSicons.get_icon(code=code)
            if pixbuf:
                self.icons.append((pixbuf, code))

        self.address_assist = AddressAssistant()
        lookup_button = Gtk.Button.new_with_label(_("By Address"))
        self.add_field(_("Group"), miscwidgets.make_choice([], True))
        self.name_entry = Gtk.Entry()
        self.add_field(_("Name"), self.name_entry)
        self.lat_entry = LatLonEntry()
        self.add_field(_("Latitude"), self.lat_entry)
        self.lon_entry = LatLonEntry()
        self.add_field(_("Longitude"), self.lon_entry)
        if self.address_assist.geocoders:
            lookup_button = Gtk.Button.new_with_label(_("By Address"))
            lookup_button.connect("clicked", self.do_address)
            self.add_field(_("Lookup"), lookup_button)
        self.add_field(_("Comment"), Gtk.Entry())
        aprs_button = Gtk.Button.new_with_label(_("Edit"))
        self.aprs_image = Gtk.Image.new()
        self.aprs_label = Gtk.Label.new()
        aprs_button.connect("clicked", self.aprs_symbol)
        self.add_field(_("Edit APRS"), aprs_button)
        self.add_field(_("Icon"), self.aprs_image)
        self.add_field(_("APRS Code"), self.aprs_label)
        self._point = None

    def do_address(self, _button):
        '''
        Do Address Lookup Handler.

        :param _button: Button widget, unused
        :type _button: :class:`Gtk.Button`
        '''
        run_status = self.address_assist.run()
        if run_status == Gtk.ResponseType.OK:
            self.name_entry.set_text(self.address_assist.place)
            self.lat_entry.set_text("%.5f" % self.address_assist.lat)
            self.lon_entry.set_text("%.5f" % self.address_assist.lon)

    def aprs_symbol(self, _button):
        '''
        APRS symbol information button Handler.

        :param _button: Button widget, unused
        :type _button: :class:`Gtk.Button`
        '''
        aprs_code = self.aprs_label.get_text()
        aprs = APRSicons.aprs_selection(code=aprs_code)
        if aprs is not None:
            self.aprs_label.set_text(aprs)
            pixbuf = APRSicons.get_icon(code=aprs)
            self.aprs_image.set_from_pixbuf(pixbuf)

    def set_groups(self, groups, group=None):
        '''
        Set Groups.

        :param groups: Groups to retrieve
        :param group: Optional group text to set, default None
        :type group: str
        '''
        grpsel = self.get_field(_("Group"))
        for grp in groups:
            grpsel.append_text(grp)

        if group is not None:
            group_entry = grpsel.get_child()
            group_entry.set_text(group)
            grpsel.set_sensitive(False)
        else:
            group_entry = grpsel.get_child()
            group_entry.set_text(_("Misc"))

    # pylint: disable=arguments-differ
    def get_group(self):
        '''
        Get Group name for marker.

        :returns: Group name for marker
        :rtype: str
        '''
        group_entry = self.get_field(_("Group")).get_child()
        return group_entry.get_text()

    def set_point(self, point):
        '''
        Set Point.

        :param point: point object
        '''
        self.get_field(_("Name")).set_text(point.get_name())
        self.get_field(_("Latitude")).set_text("%.4f" % point.get_latitude())
        self.get_field(_("Longitude")).set_text("%.4f" % point.get_longitude())
        self.get_field(_("Comment")).set_text(point.get_comment())

        iconsel = self.get_field(_("Edit APRS"))
        if isinstance(point, map_sources.MapStation):
            aprs_code = point.get_aprs_code()
            self.get_field(_("APRS Code")).set_text(aprs_code)
            pixbuf = APRSicons.get_icon(code=aprs_code)
            self.get_field(_("Icon")).set_from_pixbuf(pixbuf)
            iconsel.set_sensitive(True)
        else:
            iconsel.set_sensitive(False)

        self._point = point

    def get_point(self):
        '''
        Get Point.

        :returns: point object
        '''
        name = self.get_field(_("Name")).get_text()
        lat = self.get_field(_("Latitude")).value()
        lon = self.get_field(_("Longitude")).value()
        comment = self.get_field(_("Comment")).get_text()
        aprs_code = self.get_field(_("APRS Code")).get_text()

        self._point.set_name(name)
        self._point.set_latitude(lat)
        self._point.set_longitude(lon)
        self._point.set_comment(comment)

        if isinstance(self._point, map_sources.MapStation):
            self._point.set_pixbuf_from_aprs_code(aprs_code)

        return self._point
