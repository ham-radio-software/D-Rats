'''Map Marker List Module.'''
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

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import GObject

from .. import miscwidgets


# This makes pylance happy with out overriding settings
# from the invoker of the class
if not '_' in locals():
    import gettext
    _ = gettext.gettext


class MapMarkerList(Gtk.ScrolledWindow):
    '''
    Make Marker List.

    :param map_window: Parent Map window
    :type map_window: :class:`map.MapWindow`
    '''
    cols = [(GObject.TYPE_BOOLEAN, _("Show")),
            (GObject.TYPE_STRING, _("Station")),
            (GObject.TYPE_FLOAT, _("Latitude")),
            (GObject.TYPE_FLOAT, _("Longitude")),
            (GObject.TYPE_FLOAT, _("Distance")),
            (GObject.TYPE_FLOAT, _("Direction")),
            ]

    def __init__(self, map_window):
        Gtk.ScrolledWindow.__init__(self)
        self.map_window = map_window
        self.marker_list = miscwidgets.TreeWidget(self.cols, 1, parent=False)
        self.marker_list.toggle_cb.append(self.map_window.toggle_show)
        # self.marker_list.connect("click-on-list", self.make_marker_popup)

        # pylint: disable=protected-access
        self.marker_list._view.connect("row-activated", self.recenter_cb)

        def render_station(_col, rend, model, iter_value, _data):
            parent = model.iter_parent(iter_value)
            if not parent:
                parent = iter_value
                group = model.get_value(parent, 1)
            if group in self.map_window.colors:
                rend.set_property("foreground", self.map_window.colors[group])

        column = self.marker_list._view.get_column(1)
        column.set_expand(True)
        column.set_min_width(150)
        # r = c.get_cell_renderers()[0]
        renderer_text = Gtk.CellRendererText()
        column.set_cell_data_func(renderer_text, render_station)

        def render_coord(_col, rend, model, iter_value, cnum):
            if isinstance(rend, gi.repository.Gtk.Separator):
                return
            if model.iter_parent(iter_value):
                rend.set_property('text', "%.4f" %
                                  model.get_value(iter_value, cnum))
            else:
                rend.set_property('text', '')

        for col in [2, 3]:
            column = self.marker_list._view.get_column(col)
            # renderer_text = column.get_cell_renderers()[0]
            renderer_text = Gtk.CellRendererText()
            column.set_cell_data_func(renderer_text, render_coord, col)

        def render_dist(_col, rend, model, iter_value, cnum):
            if model.iter_parent(iter_value):
                rend.set_property('text', "%.2f" %
                                  model.get_value(iter_value, cnum))
            else:
                rend.set_property('text', '')

        for col in [4, 5]:
            column = self.marker_list._view.get_column(col)
            # renderer_text = column.get_cell_renderers()[0]
            renderer_text = Gtk.CellRendererText()
            column.set_cell_data_func(renderer_text, render_dist, col)

        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.add(self.marker_list.packable())
        self.set_size_request(-1, 150)
        self.show()


    def recenter_cb(self, view, path, column, data=None):
        '''
        Recenter Callback.

        :param view: Gtk.TreeView object that received signal
        :param path: Gtk.TreePath for the activated row
        :param column: Gtk.TreeviewColumn that was activated
        :param data: Optional data, Default None
        '''
        print("recenter_cb")
        print("self", type(self))
        print("path", type(self))
        print("column", type(column))
        print("data", type(data))
        model = view.get_model()
        if model.iter_parent(model.get_iter(path)) is None:
            return

        items = self.marker_list.get_selected()

        self.map_window.center_mark = items[1]
        self.map_window.recenter(items[2], items[3])

        self.map_window.sb_center.pop(self.map_window.STATUS_CENTER)
        self.map_window.sb_center.push(self.map_window.STATUS_CENTER,
                                       _("Center") + ": %s" %
                                       self.map_window.center_mark)
