#!/usr/bin/python
'''ReqObject.'''
#
# Copyright 2008 Dan Smith <dsmith@danplanet.com>
# Copyright 2021 John. E. Malmberg - Python3 Conversion
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

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import GObject

from .keyedlistwidget import KeyedListWidget

if not '_' in locals():
    import gettext
    _ = gettext.gettext


class RequestRemoteObjectUI(Gtk.Dialog):
    '''
    Request Remote Object UI.

    :param _rpcsession: Unused
    :param _station: Unused
    :param _parent: parent widget, default None
    '''
    logger = logging.getLogger("RequestRemoteObjectUI")

    def __init__(self, _rpcsession, _station, parent=None):
        Gtk.Dialog.__init__(self, parent=parent)

        self.set_title(_("Request remote object"))
        self.add_button(_("Retrieve"), Gtk.ResponseType.OK)
        self.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        self.__list = KeyedListWidget(
            [(GObject.TYPE_STRING, "_ID"),
             (GObject.TYPE_STRING, "Name"),
             (GObject.TYPE_STRING, "Info")])
        self.__list.set_resizable(0, True)
        self.__list.show()

        scrollw = Gtk.ScrolledWindow()
        scrollw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrollw.add(self.__list)
        scrollw.show()

        self.vbox.pack_start(scrollw, 1, 1, 1)

        self.set_default_size(400, 400)

    def set_objects(self, objlist):
        '''
        Set Objects.

        :param objlist: objects to set
        :type objlist: list
        '''
        for name, info in objlist:
            self.__list.set_item(name, name, info)

    def get_selected_item(self):
        '''
        Get Selected Item.

        :returns: Selected item
        '''
        try:
            return self.__list.get_item(self.__list.get_selected())[1]
        # pylint: disable=broad-except
        except Exception:
            self.logger.info("get_selected_item: Unable to get selected item"
                             " broad-exception", exc_info=True)
            return None
