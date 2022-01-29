'''Map Marker List Module.'''
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
from gi.repository import GObject

from .. import miscwidgets
from .. import map as Map

# This makes pylance happy with out overriding settings
# from the invoker of the class
if not '_' in locals():
    import gettext
    _ = gettext.gettext


class MapMarkerList(miscwidgets.TreeWidget):
    '''
    Map Marker List.
    :param map_window: Parent Map window
    :type map_window: :class:`map.MapWindow`
    '''
    columns = [(GObject.TYPE_BOOLEAN, _("Show")),
               (GObject.TYPE_STRING, _("Station")),
               (GObject.TYPE_FLOAT, _("Latitude")),
               (GObject.TYPE_FLOAT, _("Longitude")),
               (GObject.TYPE_FLOAT, _("Distance")),
               (GObject.TYPE_FLOAT, _("Direction"))]

    def __init__(self, map_window):
        miscwidgets.TreeWidget.__init__(self, self.columns, 1, parent=False)
        self.map_window = map_window
        self.toggle_cb.append(self.map_window.toggle_show)
        self.connect("click-on-list", self.map_window.make_marker_popup)

        self._view.connect("row-activated", self.recenter_cb)
        def render_station(_col, rend, model, iter_value, _data):
            '''
            Render Station.

            :param _col: cell layout
            :type _col: :class:`Gtk.TreeViewColumn`
            :param rend: Cell renderer
            :type rend: :class:`Gtk.CellRenderer`
            :param model: Storage Model
            :type model: :class:`Gtk.TreeStore`
            :param iter_value: Row to set the value for
            :type iter_value: :class:`Gtk.TreeIter`
            :param _data: Unused
            :type _data: NoneType
            '''
            parent = model.iter_parent(iter_value)
            if not parent:
                parent = iter_value
            group = model.get_value(parent, 1)
            if group in self.map_window.colors:
                rend.set_property("foreground", self.map_window.colors[group])

        column = self._view.get_column(1)
        column.set_expand(True)
        column.set_min_width(150)
        renderer = column.get_cells()[0]
        column.set_cell_data_func(renderer, render_station, None)

        def render_coord(_col, rend, model, iter_value, cnum):
            '''
            Render Station.

            :param _col: cell layout
            :type _col: :class:`Gtk.TreeViewColumn`
            :param rend: Cell renderer
            :type rend: :class:`Gtk.CellRenderer`
            :param model: Storage Model
            :type model: :class:`Gtk.TreeStore`
            :param iter_value: Row to set the value for
            :type iter_value: :class:`Gtk.TreeIter`
            :param cnum: Column to render
            :type cnum: int
            '''
            if isinstance(rend, gi.repository.Gtk.Separator):
                return
            if model.iter_parent(iter_value):
                rend.set_property('text', "%.4f" %
                                  model.get_value(iter_value, cnum))
            else:
                rend.set_property('text', '')

        for col in [2, 3]:
            column = self._view.get_column(col)
            renderer = column.get_cells()[0]
            column.set_cell_data_func(renderer, render_coord, col)

        def render_dist(_col, rend, model, iter_value, cnum):
            '''
            Render Station.

            :param _col: cell layout
            :type _col: :class:`Gtk.TreeViewColumn`
            :param rend: Cell renderer
            :type rend: :class:`Gtk.CellRenderer`
            :param model: Storage Model
            :type model: :class:`Gtk.TreeStore`
            :param iter_value: Row to set the value for
            :type iter_value: :class:`Gtk.TreeIter`
            :param cnum: Column to render
            :type cnum: int
            '''
            if model.iter_parent(iter_value):
                rend.set_property('text', "%.2f" %
                                  model.get_value(iter_value, cnum))
            else:
                rend.set_property('text', '')

        for col in [4, 5]:
            column = self._view.get_column(col)
            renderer = column.get_cells()[0]
            column.set_cell_data_func(renderer, render_dist, col)

    def recenter_cb(self, view, path, _column, _data=None):
        '''
        Recenter Callback.

        :param view: View object that received signal
        :type view: :class:`Gtk.Treeview`
        :param path: TreePath for the activated row
        :type path: :class:`Gtk.TreePath`
        :param _column: Column that was activated, unused.
        :type _column: :class:`Gtk.TreeViewColumn`
        :param _data: Optional data, Default None, Unused
        '''
        model = view.get_model()
        if model.iter_parent(model.get_iter(path)) is None:
            return

        items = self.get_selected()

        self.map_window.center_mark = items[1]
        position = Map.Position(items[2], items[3])
        self.map_window.recenter(position)

        self.map_window.statusbox.sb_center.pop(self.map_window.STATUS_CENTER)
        self.map_window.statusbox.sb_center.push(self.map_window.STATUS_CENTER,
                                                 _("Center") + ": %s" %
                                                 self.map_window.center_mark)

def main():
    '''Unit Test'''

    logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
                        datefmt="%m/%d/%Y %H:%M:%S",
                        level=logging.INFO)
    logger = logging.getLogger("MapMarkerListTest")

    class TestWindow(Gtk.Window):
        '''test window.'''

        def __init__(self):
            Gtk.Window.__init__(self, type=Gtk.WindowType.TOPLEVEL)
            self.colors = {}

        def toggle_show(self, group, *vals):
            '''
            Toggle Show.

            :param group: Group to show
            :param vals: Optional values
            '''
            print("toggle_show")
            print("self:", type(self))
            print("group:", type(group))
            print("vals:", type(vals))

        def make_marker_popup(self, widget, view, event):
            '''
            Make Marker Popup.

            :param widget: Widget with marker data
            :type widget: :class:`Map.MapMarkerList`
            :param view: View for popup
            :type view: :class:`Gtk.Treeview`
            :param event: Mouse click event
            :type event: :class:`Gdk.Event`
            '''
            print("make_marker_popup", type(self), type(widget), type(view),
                  type(event))

    window = TestWindow()
    window.connect("destroy", Gtk.main_quit)

    marker_list = MapMarkerList(window)
    scrollw = Gtk.ScrolledWindow()
    scrollw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    scrollw.add(marker_list.packable())
    scrollw.set_size_request(-1, 150)
    scrollw.show()
    window.add(scrollw)
    window.show()

    marker_list.add_item(None, True, "TESTCALL", 0, 0, 0, 0)
    marker_list.add_item(None, False, "N0CALL", 1, 2, 3, 4)
    try:
        Gtk.main()
    except KeyboardInterrupt:
        pass

    logger.info(marker_list.get_values())

if __name__ == "__main__":
    main()
