#!/usr/bin/python
#
# Copyright 2009 Dan Smith <dsmith@danplanet.com>
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


try:
    from urllib2 import URLError
except ModuleNotFoundError:
    from urllib.error import URLError
from geopy import geocoders

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject

#importing printlog() wrapper
from .debug import printlog
from . import miscwidgets

#setup of d-rats user_agent
from . import version

class AddressAssistant(Gtk.Assistant):
    '''Address Assistant for Geocode Query'''

    def make_address_entry_page(self):
        '''Make Address Entry Page'''
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
        '''Make Address Selection'''
        cols = [(GObject.TYPE_STRING, _("Address")),
                (GObject.TYPE_FLOAT, _("Latitude")),
                (GObject.TYPE_FLOAT, _("Longitude"))]
        listbox = miscwidgets.ListWidget(cols)

        self.vals["AddressList"] = listbox

        listbox.show()
        return listbox

    def make_address_confirm_page(self):
        '''Make Address Confirm Page'''
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
        '''Prepare sel'''
        address = self.vals["_address"].get_text()
        if not address:
            return

        try:
            agent = version.DRATS_NAME + '/' + version.DRATS_VERSION
            service = geocoders.Nominatim(user_agent = agent)
            places = service.geocode(address, exactly_one=False)
            self.set_page_complete(page, True)
        except URLError as err:
            printlog("Geocode", "   : Did not find `%s': %s" % (address, err))
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
        '''Prepare conf'''
        self.place, self.lat, self.lon = \
            self.vals["AddressList"].get_selected(True)

        self.vals[_("Address")].set_text(self.place)
        self.vals[_("Latitude")].set_text("%.5f" % self.lat)
        self.vals[_("Longitude")].set_text("%.5f" % self.lon)

        self.set_page_complete(page, True)

    def prepare_page(self, assistant, page):
        '''Prepare Page'''
        if page == self.sel_page:
            printlog("Geocode", "   : Sel")
            return self.prepare_sel(assistant, page)
        elif page == self.conf_page:
            printlog("Geocode", "   : Conf")
            return self.prepare_conf(assistant, page)
        elif page == self.entry_page:
            printlog("Geocode", "   : Ent")
            self.sel_page.show()
        else:
            printlog("Geocode", "   : I dunno")

    def exit(self, _, response):
        '''exit'''
        self.response = response
        Gtk.main_quit()

    def run(self):
        '''run'''
        self.show()
        self.set_modal(True)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        Gtk.main()
        self.hide()

        return self.response

    def __init__(self):
        Gtk.Assistant.__init__(self)

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


def main():
    '''Main program for unit testing'''

    import gettext
    lang = gettext.translation("D-RATS",
                               localedir="./locale",
                               languages=["en"],
                               fallback=True)
    lang.install()

    assist = AddressAssistant()
    assist.show()
    Gtk.main()


if __name__ == "__main__":
    main()
