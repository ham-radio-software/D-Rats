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

#importing printlog() wrapper
from .debug import printlog

import gtk
import gobject

from . import miscwidgets
from .geopy import geocoders

YID = "eHRO5K_V34FXWnljF5BJYvTc.lXh.kQ0MaJpnq3BhgaX.IJrvtd6cvGgtWEPNAb7"

try:
    from gtk import Assistant as baseclass
except ImportError:
    printlog("Geocode","   : No gtk.Assistant support")
    class baseclass(gtk.MessageDialog):
        __gsignals__ = {
            "prepare" : (gobject.SIGNAL_RUN_LAST,
                         gobject.TYPE_NONE, ()),
            "cancel" : (gobject.SIGNAL_RUN_LAST,
                        gobject.TYPE_NONE, ()),
            "apply" : (gobject.SIGNAL_RUN_LAST,
                       gobject.TYPE_NONE, ()),
            }

        def __init__(self):
            gtk.MessageDialog.__init__(self, buttons=gtk.BUTTONS_OK)
            self.set_property("text", "Unsupported")
            self.format_secondary_text("The version of GTK you're using "
                                       "is too old and does not support "
                                       "the 'Assistant' class.  This is "
                                       "required for geocoding support.")

            def close(d, r):
                self.destroy()  # make the dialog go away
                gtk.main_quit() # The run method calls gtk.main()

            self.connect("response", close)

        def append_page(self, *a, **k):
            pass

        def set_page_type(self, *a, **k):
            pass

        def set_page_title(self, *a, **k):
            pass

class AddressAssistant(baseclass):
    def make_address_entry_page(self):
        def complete_cb(label, page):
            self.set_page_complete(page, len(label.get_text()) > 1)

        vbox = gtk.VBox(False, 0)

        lab = gtk.Label(_("Enter an address, postal code, or intersection") +\
                            ":")
        lab.show()
        vbox.pack_start(lab, 1, 1, 1)

        ent = gtk.Entry()
        ent.connect("changed", complete_cb, vbox)
        ent.show()
        vbox.pack_start(ent, 0, 0, 0)

        self.vals["_address"] = ent

        vbox.show()
        return vbox

    def make_address_selection(self):
        cols = [ (gobject.TYPE_STRING, _("Address")),
                 (gobject.TYPE_FLOAT, _("Latitude")),
                 (gobject.TYPE_FLOAT, _("Longitude")) ]
        listbox = miscwidgets.ListWidget(cols)

        self.vals["AddressList"] = listbox

        listbox.show()
        return listbox

    def make_address_confirm_page(self):
        vbox = gtk.VBox(False, 0)

        def make_kv(key, value):
            hbox = gtk.HBox(False, 2)
            
            lab = gtk.Label(key)
            lab.set_size_request(100, -1)
            lab.show()
            hbox.pack_start(lab, 0, 0, 0)

            lab = gtk.Label(value)
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

    def prepare_sel(self, assistant, page):
        address = self.vals["_address"].get_text()
        if not address:
            return

        try:
            g = geocoders.Yahoo(YID)
            places = g.geocode(address, exactly_one=False)
            self.set_page_complete(page, True)
        except Exception as e:
            printlog("Geocode","   : Did not find `%s': %s" % (address, e))
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
        
    def prepare_conf(self, assistant, page):
        self.place, self.lat, self.lon = self.vals["AddressList"].get_selected(True)

        self.vals[_("Address")].set_text(self.place)
        self.vals[_("Latitude")].set_text("%.5f" % self.lat)
        self.vals[_("Longitude")].set_text("%.5f" % self.lon)

        self.set_page_complete(page, True)

    def prepare_page(self, assistant, page):
        if page == self.sel_page:
            printlog("Geocode","   : Sel")
            return self.prepare_sel(assistant, page)
        elif page == self.conf_page:
            printlog("Geocode","   : Conf")
            return self.prepare_conf(assistant, page)
        elif page == self.entry_page:
            printlog("Geocode","   : Ent")
            self.sel_page.show()
        else:
            printlog("Geocode","   : I dunno")

    def exit(self, _, response):
        self.response = response
        gtk.main_quit()

    def run(self):
        self.show()
        self.set_modal(True)
        self.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
        gtk.main()
        self.hide()

        return self.response

    def __init__(self):
        baseclass.__init__(self)

        self.response = None

        self.vals = {}

        self.place = self.lat = self.lon = None

        self.entry_page = self.make_address_entry_page()
        self.append_page(self.entry_page)
        self.set_page_title(self.entry_page, _("Locate an address"))
        self.set_page_type(self.entry_page, gtk.ASSISTANT_PAGE_CONTENT)

        self.sel_page = self.make_address_selection()
        self.append_page(self.sel_page)
        self.set_page_title(self.sel_page, _("Locations found"))
        self.set_page_type(self.sel_page, gtk.ASSISTANT_PAGE_CONTENT)

        self.conf_page = self.make_address_confirm_page()
        self.append_page(self.conf_page)
        self.set_page_title(self.conf_page, _("Confirm address"))
        self.set_page_type(self.conf_page, gtk.ASSISTANT_PAGE_CONFIRM)

        self.connect("prepare", self.prepare_page)
        self.set_size_request(500, 300)

        self.connect("cancel", self.exit, gtk.RESPONSE_CANCEL)
        self.connect("apply", self.exit, gtk.RESPONSE_OK)

if __name__ == "__main__":
    a = AddressAssistant()
    a.show()
    gtk.main()
