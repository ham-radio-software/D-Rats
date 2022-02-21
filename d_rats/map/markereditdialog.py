'''Map Marker Dialog Module.'''
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

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from .. import map_sources
from .. import inputdialog
from .. import miscwidgets
from .. import utils
from ..gps import DPRS_TO_APRS
from ..geocode_ui import AddressAssistant

# This makes pylance happy with out overriding settings
# from the invoker of the class
if not '_' in locals():
    import gettext
    _ = gettext.gettext

class MarkerEditDialog(inputdialog.FieldDialog):
    '''Marker Edit Dialog.'''

    def __init__(self):
        inputdialog.FieldDialog.__init__(self, title=_("Add Marker"))
        self.logger = logging.getLogger("MarkerEditDialog")
        self.logger.info("class init")

        self.icons = []
        self.logger.info("Before sorting DPRS_TO_APRS")
        for sym in sorted(DPRS_TO_APRS.values()):
            icon = utils.get_icon(sym)
            if icon:
                self.icons.append((icon, sym))

        self.address_assist = AddressAssistant()
        lookup_button = Gtk.Button.new_with_label(_("By Address"))
        self.add_field(_("Group"), miscwidgets.make_choice([], True))
        self.name_entry = Gtk.Entry()
        self.add_field(_("Name"), self.name_entry)
        self.lat_entry = miscwidgets.LatLonEntry()
        self.add_field(_("Latitude"), self.lat_entry)
        self.lon_entry = miscwidgets.LatLonEntry()
        self.add_field(_("Longitude"), self.lon_entry)
        if self.address_assist.geocoders:
            lookup_button = Gtk.Button.new_with_label(_("By Address"))
            lookup_button.connect("clicked", self.do_address)
            self.add_field(_("Lookup"), lookup_button)
        self.add_field(_("Comment"), Gtk.Entry())
        self.add_field(_("Icon"), miscwidgets.make_pixbuf_choice(self.icons))

        self._point = None
        self.logger.info("init done")

    def do_address(self, _button):
        '''
        Do Address Lookup.

        :param _button: Button widget, unused
        :type _button: :class:`Gtk.Button`
        '''
        run_status = self.address_assist.run()
        if run_status == Gtk.ResponseType.OK:
            self.name_entry.set_text(self.address_assist.place)
            self.lat_entry.set_text("%.5f" % self.address_assist.lat)
            self.lon_entry.set_text("%.5f" % self.address_assist.lon)

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

        iconsel = self.get_field(_("Icon"))
        if isinstance(point, map_sources.MapStation):
            symlist = [y for x, y in self.icons]
            try:
                iidx = symlist.index(point.get_aprs_symbol())
                iconsel.set_active(iidx)
            except ValueError:
                self.logger.info("set_point: No such symbol `%s'",
                                 point.get_aprs_symbol())
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
        idx = self.get_field(_("Icon")).get_active()

        self._point.set_name(name)
        self._point.set_latitude(lat)
        self._point.set_longitude(lon)
        self._point.set_comment(comment)

        if isinstance(self._point, map_sources.MapStation):
            self._point.set_icon_from_aprs_sym(self.icons[idx][1])

        return self._point
