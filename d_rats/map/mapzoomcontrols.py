'''Map Zoom Controls Module.'''
#
# Copyright 2021 John Malmberg <wb8tyw@gmail.com>
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

# import logging
import time

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import GLib

from .. import map as Map

# This makes pylance happy with out overriding settings
# from the invoker of the class
if not '_' in locals():
    import gettext
    _ = gettext.gettext


class MapZoomControls(Gtk.Frame):
    '''
    Map zoom controls.

    :param map_widget: Map Widget for control
    :type map_widget: :class:`Map.Widget`
    :param zoom: Initial zoom level, Default 14
    :type zoom: int
    '''

    # mm here the allowed zoom levels are from 2 to 17 (increased to 18)
    ZOOM_MIN = 2
    ZOOM_MAX = 18
    ZOOM_DEFAULT = 14

    __level = ZOOM_DEFAULT

    def __init__(self, map_widget, zoom=None):
        Gtk.Frame.__init__(self)
        self.__level = self.sanitize_level(zoom)
        Map.Tile.set_zoom(self.__level)
        zoom_label = _("Zoom") + " (%i)" % self.__level
        self.set_label(zoom_label)
        self.map_widget = map_widget
        self.__last_zoom = None
        self.set_label_align(0.5, 0.5)
        self.set_size_request(150, 50)
        self.show()

        box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 3)
        box.set_border_width(3)
        box.show()

        label = Gtk.Label.new(str(self.ZOOM_MIN))
        label.show()
        box.pack_start(label, False, False, False)

        adj = Gtk.Adjustment.new(value=self.__level,
                                 lower=self.ZOOM_MIN,
                                 upper=self.ZOOM_MAX,
                                 step_increment=1,
                                 page_increment=3,
                                 page_size=0)

        self.scroll_bar = Gtk.Scrollbar.new(Gtk.Orientation.HORIZONTAL, adj)
        self.scroll_bar.show()
        box.pack_start(self.scroll_bar, True, True, True)

        label = Gtk.Label.new(str(self.ZOOM_MAX))
        label.show()
        box.pack_start(label, False, False, False)

        self.add(box)

        self.scroll_bar.connect("value-changed", self.zoom_event)

    def sanitize_level(self, level):
        '''
        Sanitize zoom level by making sure it is range.

        :param level: Requested zoom level
        :type level: int
        :returns: Zoom level that is in range
        :rtype: int
        '''
        if not level:
            level = self.ZOOM_DEFAULT
        elif level < self.ZOOM_MIN:
            level = self.ZOOM_MIN
        elif level > self.ZOOM_MAX:
            level = self.ZOOM_MAX
        return level

    @classmethod
    def get_level(cls):
        '''
        Get level of zoom.

        :returns: Current Zoom level
        :rtype: int
        '''
        return cls.__level

    @property
    def level(self):
        '''
        :returns: Zoom level
        :rtype: int
        '''
        return self.__level

    @level.setter
    def level(self, level):
        '''
        :param level: New zoom level
        :type level: int
        '''
        new_level = self.sanitize_level(level)
        if new_level != self.__level:
            self.__level = new_level
            self.scroll_bar.set_value(new_level)

    def zoom_event(self, adj):
        '''
        Zoom Event.

        This is event is signaled when current value of the
        zoom scroll_bar is changed, either by a user moving the
        control, or the program setting the value.

        :param adj: Zoom adjustment
        :type adj: :class:`Gtk.ScrollBar`
        '''
        if not self.__last_zoom:
            GLib.timeout_add(100, self.zoom_handler)
        zoom_value = int(adj.get_value())
        self.__last_zoom = (time.time(), zoom_value)
        self.set_label(_("Zoom") + " (%i)" % zoom_value)

    def zoom_handler(self):
        '''
        Zoom Handler.

        Delayed check of the zoom value changing.
        The zoom control is very sensitive, so we want to wait
        until the all motion of the handler has stopped.

        :returns: True to continue waiting for stable value
        :rtype: bool
        '''
        if self.__last_zoom is None:
            # Nothing to do, so stop polling.
            return False

        time_zoom, zoom_value = self.__last_zoom
        if (time.time() - time_zoom) < 0.5:
            # Waiting for slider to stop moving
            return True
        self.__last_zoom = None
        self.__level = zoom_value
        Map.Tile.set_zoom(zoom_value)
        # This should signal a map redraw event
        self.map_widget.queue_draw()
        return False
