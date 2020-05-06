#!/usr/bin/python
#
# Copyright 2008 Dan Smith <dsmith@danplanet.com>
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
import gtk
import gobject

from . import miscwidgets

class RequestRemoteObjectUI(gtk.Dialog):
    def __init__(self, rpcsession, station, parent=None):
        gtk.Dialog.__init__(self,
                            title="Request remote object",
                            buttons=("Retrieve", gtk.RESPONSE_OK,
                                     gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL),
                            parent=parent)
        
        self.__list = miscwidgets.KeyedListWidget(\
            [(gobject.TYPE_STRING, "_ID"),
             (gobject.TYPE_STRING, "Name"),
             (gobject.TYPE_STRING, "Info")])
        self.__list.set_resizable(0, True)
        self.__list.show()

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.add_with_viewport(self.__list)
        sw.show()

        self.vbox.pack_start(sw, 1, 1, 1)

        self.set_default_size(400, 400)

    def set_objects(self, objlist):
        for name, info in objlist:
            self.__list.set_item(name, name, info)

    def get_selected_item(self):
        try:
            return self.__list.get_item(self.__list.get_selected())[1]
        except Exception as e:
            print(("ReqObj    : Unable to get selected item: %s" % e))
            return None
