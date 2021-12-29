#!/usr/bin/python
'''Geocode UI.'''
#
# Copyright 2009 Dan Smith <dsmith@danplanet.com>
# Copyright 2021 John Malmberg - Python 3 Conversion
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


import logging
try:
    from urllib2 import URLError # type: ignore
except ModuleNotFoundError:
    from urllib.error import URLError
try:
    from geopy import geocoders
except ModuleNotFoundError:
    pass
# python2 compatibility
except ImportError:
    pass

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject

# importing printlog() wrapper
# from .debug import printlog
from . import miscwidgets

# setup of d-rats user_agent
from . import version

if __name__ == "__main__":
    import gettext
    # pylint: disable=invalid-name
    lang = gettext.translation("D-RATS",
                               localedir="./locale",
                               fallback=True)
    lang.install()
    _ = lang.gettext


# pylint: disable=too-many-instance-attributes
class AddressAssistant(Gtk.Assistant):
    '''Address Assistant for Geocode Query.'''

    def __init__(self):
        Gtk.Assistant.__init__(self)

        self.logger = logging.getLogger("Geocode_ui_AddressAssistant")
        try:
            self.geocoders = geocoders
        except NameError:
            self.geocoders = None
            self.logger.info("No geopy module available.")

        self.response = None

        self.vals = {}

        self.place = self.lat = self.lon = None

        self.entry_page = self.make_address_entry_page()
        self.append_page(self.entry_page)
        self.set_page_title(self.entry_page, _("Locate an address"))
        self.set_page_type(self.entry_page, Gtk.AssistantPageType.CONTENT)

        self.sel_page = self.make_address_selection()
        self.append_page(self.sel_page)
        self.set_page_title(self.sel_page, _("Locations found"))
        self.set_page_type(self.sel_page, Gtk.AssistantPageType.CONTENT)

        self.conf_page = self.make_address_confirm_page()
        self.append_page(self.conf_page)
        self.set_page_title(self.conf_page, _("Confirm address"))
        self.set_page_type(self.conf_page, Gtk.AssistantPageType.CONFIRM)

        self.connect("prepare", self.prepare_page)
        self.set_size_request(500, 300)

        self.connect("cancel", self.exit, Gtk.ResponseType.CANCEL)
        self.connect("apply", self.exit, Gtk.ResponseType.OK)

    def make_address_entry_page(self):
        '''
        Make Address Entry Page.

        :returns: Gtk.Box with page
        '''
        def complete_cb(label, page):
            self.set_page_complete(page, len(label.get_text()) > 1)

        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)

        lab = Gtk.Label.new(
            _("Enter an address, postal code, or intersection") + ":")
        lab.show()
        vbox.pack_start(lab, 1, 1, 1)

        ent = Gtk.Entry()
        ent.connect("changed", complete_cb, vbox)
        ent.show()
        vbox.pack_start(ent, 0, 0, 0)

        self.vals["_address"] = ent

        vbox.show()
        return vbox

    def make_address_selection(self):
        '''
        Make Address Selection.

        :returns: listbox
        '''
        cols = [(GObject.TYPE_STRING, _("Address")),
                (GObject.TYPE_FLOAT, _("Latitude")),
                (GObject.TYPE_FLOAT, _("Longitude"))]
        listbox = miscwidgets.ListWidget(cols)

        self.vals["AddressList"] = listbox

        listbox.show()
        return listbox

    def make_address_confirm_page(self):
        '''
        Make Address Confirm Page.

        :returns: Gtk.Box object with page
        '''
        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)

        def make_kv(key, value):
            hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 2)

            lab = Gtk.Label.new(key)
            lab.set_size_request(100, -1)
            lab.show()
            hbox.pack_start(lab, 0, 0, 0)

            lab = Gtk.Label.new(value)
            lab.show()
            hbox.pack_start(lab, 0, 0, 0)

            self.vals[key] = lab

            hbox.show()
            return hbox

        vbox.pack_start(make_kv(_("Address"), ""), 0, 0, 0)
        vbox.pack_start(make_kv(_("Latitude"), ""), 0, 0, 0)
        vbox.pack_start(make_kv(_("Longitude"), ""), 0, 0, 0)

        vbox.show()
        return vbox

    def prepare_sel(self, _assistant, page):
        '''
        Prepare sel.

        :param _assistant: Unused
        :param page: Gtk.Box object with page
        '''
        address = self.vals["_address"].get_text()
        if not address:
            return

        agent = version.DRATS_NAME + '/' + version.DRATS_VERSION
        service = self.geocoders.Nominatim(user_agent=agent)
        try:
            places = service.geocode(address, exactly_one=False)
            self.set_page_complete(page, True)
        except URLError:
            self.logger.info("Did not find `%s'", address, exc_info=True)
            places = []
            lat = lon = 0
            self.set_page_complete(page, False)

        i = 0
        self.vals["AddressList"].set_values([])
        for place, (lat, lon) in places:
            i += 1
            self.vals["AddressList"].add_item(place, lat, lon)

        if i == -1:
            page.hide()
            self.set_current_page(self.get_current_page() + 1)

    def prepare_conf(self, _assistant, page):
        '''
        Prepare conf.

        :param _assistant: Unused
        :param _page: Gtk.Box object with page
        '''
        self.place, self.lat, self.lon = \
            self.vals["AddressList"].get_selected(True)

        self.vals[_("Address")].set_text(self.place)
        self.vals[_("Latitude")].set_text("%.5f" % self.lat)
        self.vals[_("Longitude")].set_text("%.5f" % self.lon)

        self.set_page_complete(page, True)

    def prepare_page(self, assistant, page):
        '''
        Prepare Page.

        :param _assistant: Unused
        :param page: Gtk.Box object with page
        '''
        if page == self.sel_page:
            self.logger.info("Sel")
            self.prepare_sel(assistant, page)
            return
        if page == self.conf_page:
            self.logger.info("Conf")
            self.prepare_conf(assistant, page)
            return
        if page == self.entry_page:
            self.logger.info("Ent")
            self.sel_page.show()
        else:
            self.logger.info("I dunno")

    def exit(self, _, response):
        '''
        Exit.

        :param _: Unused
        :param response: Response to exit with'''
        self.response = response
        Gtk.main_quit()

    def run(self):
        '''Run.'''
        self.show()
        self.set_modal(True)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        Gtk.main()
        self.hide()

        return self.response


def main():
    '''Main program for unit testing.'''

    logging.basicConfig(level=logging.INFO)

    # Each class should have their own logger.
    logger = logging.getLogger("geocode_ui_test")

    import sys
    logger.info("sys.path=%s", sys.path)

    assist = AddressAssistant()
    if assist.geocoders:
        assist.show()
        Gtk.main()


if __name__ == "__main__":
    main()
