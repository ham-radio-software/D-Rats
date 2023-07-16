'''Keyed List Widget.'''
# Copyright 2008 Dan Smith <dsmith@danplanet.com>
# Copyright 2021-2023 John. E. Malmberg - Python3 Conversion
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

import logging

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import GObject
from gi.repository import Pango


class KeyedListWidgetMakeViewError(Exception):
    '''Keyed List Widget Make View Error'''


class KeyedListWidget(Gtk.Box):
    '''
    Keyed List Widget.

    :param columns: Columns for widget
    :type columns: int
    '''

    __gsignals__ = {
        "item-selected" : (GObject.SignalFlags.RUN_LAST,
                           GObject.TYPE_NONE,
                           (GObject.TYPE_STRING,)),
        "item-toggled" : (GObject.SignalFlags.RUN_LAST,
                          GObject.TYPE_BOOLEAN,
                          (GObject.TYPE_STRING, GObject.TYPE_BOOLEAN)),
        "item-set" : (GObject.SignalFlags.RUN_LAST,
                      GObject.TYPE_NONE,
                      (GObject.TYPE_STRING,)),
        }

    def __init__(self, columns):
        Gtk.Box.__init__(self,
                         orientation=Gtk.Orientation.HORIZONTAL,
                         spacing=2)

        self.logger = logging.getLogger("KeyedListWidget")
        self.columns = columns

        types = tuple(x for x, _y in columns)

        self.__store = Gtk.ListStore(*types)
        self.__view = Gtk.TreeView.new_with_model(self.__store)
        self.__view.set_hexpand(True)

        self.pack_start(self.__view, 1, 1, 1)

        self.__toggle_connected = False

        self._make_view()
        self.__view.show()

    def _toggle(self, _rend, path, colnum):
        '''
        Internal Toggle handler.

        :param _rend: Render object, Unused
        :type _rend: :class:`Gtk.CellRenderer`
        :param path: The event location
        :type path: str
        :param colnum,: Column number to toggle
        :type colnum: int
        '''
        if self.__toggle_connected:
            iter_val = self.__store.get_iter(path)
            ident, value = self.__store.get(iter_val, 0, colnum)
            self.__store.set_value(iter_val, colnum, not value)
            self.emit("item-toggled", ident, not value)

    def _edited(self, _rend, path, new, colnum):
        '''
        Edited Handler.

        :param _rend: Render Widget, Unused
        :type _rend: :class:`Gtk.CellRendererText`
        :param path: Path identifying the edited cell
        :type path: str
        :param new: New text
        :type new: str
        :param colnum: Column number
        :type colnum: int
        '''
        iter_val = self.__store.get_iter(path)
        key = self.__store.get(iter_val, 0)
        self.__store.set(iter_val, colnum, new)
        self.emit("item-set", key)

    def _mouse(self, _view, event):
        '''
        Mouse Button Handler.

        :param _view: view object, Unused
        :type _view: :class:`Gtk.TreeView`
        :param event: Button Event
        :type event: :class:`Gdk.EventButton`
        '''
        x_coord, y_coord = event.get_coords()
        path = self.__view.get_path_at_pos(int(x_coord), int(y_coord))
        if path:
            self.__view.set_cursor_on_cell(path[0], None, None, False)

        sel = self.get_selected()
        if sel:
            self.emit("item-selected", sel)

    def _make_view(self):
        colnum = -1

        # In order to get the column width correct for the boolean
        # column options, we need to know how may pixels per character
        # are currently being used.
        layout = self.create_pango_layout("12345")
        width, _height = layout.get_pixel_size()
        pix_char = width / 5
        for data_type, caption in self.columns:
            colnum += 1
            if colnum == 0:
                continue # Key column

            if data_type in [GObject.TYPE_STRING,
                             GObject.TYPE_INT,
                             GObject.TYPE_FLOAT]:
                rend = Gtk.CellRendererText()
                rend.set_property("ellipsize", Pango.EllipsizeMode.END)
                column = Gtk.TreeViewColumn(caption, rend, text=colnum)
                column.set_expand(True)
            elif data_type in [GObject.TYPE_BOOLEAN]:
                rend = Gtk.CellRendererToggle()
                rend.connect("toggled", self._toggle, colnum)
                column = Gtk.TreeViewColumn(caption, rend, active=colnum)
                column.set_fixed_width((len(caption) + 1) * pix_char)
            else:
                raise KeyedListWidgetMakeViewError("Unsupported type %s" %
                                                   data_type)

            column.set_sort_column_id(colnum)
            self.__view.append_column(column)

        self.__view.connect("button_press_event", self._mouse)

    def set_item(self, key, *values):
        '''
        Set Item.

        :param key: Key for item
        :type key: any
        :param values: Values to set for item
        :type values: tuple
        '''
        iter_val = self.__store.get_iter_first()
        while iter_val:
            ident, = self.__store.get(iter_val, 0)
            if ident == key:
                self.__store.insert_after(iter_val, row=(ident,)+values)
                self.__store.remove(iter_val)
                return
            iter_val = self.__store.iter_next(iter_val)

        self.__store.append(row=(key,) + values)

        self.emit("item-set", key)

    def get_item(self, key):
        '''
        Get Item.

        :param key: key for item
        :type key: any
        :returns: Item or None
        :rtype: any
        '''
        iter_val = self.__store.get_iter_first()
        while iter_val:
            vals = self.__store.get(iter_val, *tuple(range(len(self.columns))))
            if vals[0] == key:
                return vals
            iter_val = self.__store.iter_next(iter_val)

        return None

    def del_item(self, key):
        '''
        Delete Item.

        :param key: Key for item to delete
        :type key: any
        :returns: True if item is deleted
        :rtype: bool
        '''
        iter_val = self.__store.get_iter_first()
        while iter:
            ident, = self.__store.get(iter_val, 0)
            if ident == key:
                self.__store.remove(iter_val)
                return True

            iter_val = self.__store.iter_next(iter_val)

        return False

    # WB8TYW: I can not find a caller of this method.
    def has_item(self, key):
        '''
        Has Item.

        :param key: Key to look up
        :type key: any
        :returns: True if key is present
        :rtype: bool
        '''
        return self.get_item(key) is not None

    def get_selected(self):
        '''
        Get Selected.

        :returns: Selected item
        :rtype: any
        '''
        try:
            (store, iter_val) = self.__view.get_selection().get_selected()
            return store.get(iter_val, 0)[0]
        except TypeError:
            self.logger.debug("get_selected: Nothing was selected")
            return None

    # WB8TYW: I can not find a caller of this method.
    def select_item(self, key):
        '''
        Select Item.

        :param key: Key to select
        :type key: any
        :returns: True if item selected
        :rtype: bool
        '''
        if key is None:
            sel = self.__view.get_selection()
            sel.unselect_all()
            return True

        iter_val = self.__store.get_iter_first()
        while iter_val:
            if self.__store.get(iter_val, 0)[0] == key:
                selection = self.__view.get_selection()
                path = self.__store.get_path(iter_val)
                selection.select_path(path)
                return True
            iter_val = self.__store.iter_next(iter_val)

        return False

    def get_keys(self):
        '''
        Get Keys.

        :returns: keys
        :rtype: any
        '''
        keys = []
        iter_val = self.__store.get_iter_first()
        while iter_val:
            key, = self.__store.get(iter_val, 0)
            keys.append(key)
            iter_val = self.__store.iter_next(iter_val)

        return keys

    # pylint can not detect this for GTK routines.
    # pylint: disable=arguments-differ
    def connect(self, detailed_signal, handler, *args):
        '''
        Connect.

        :param detailed_signal: Signal name
        :type str:
        :param handler: Handler function
        :type handler: function
        :param args: Optional arguments for signal
        :type args: tuple
        '''
        if detailed_signal == "item-toggled":
            self.__toggle_connected = True

        Gtk.Box.connect(self, detailed_signal, handler, *args)

    def set_editable(self, column, _is_editable):
        '''
        Set Editable.

        :param column: Set column to change
        :type column: int
        :param _is_editable: Not used
        :type _is_editable: bool
        '''
        _col = self.__view.get_column(column)
        # rend = col.get_cell_renderers()[0]
        rend = Gtk.CellRendererText()
        rend.set_property("editable", True)
        rend.connect("edited", self._edited, column + 1)

    def set_sort_column(self, column, _value=None):
        '''
        Set Sort Column.
        :param column: Column to sort on
        :type column: int
        :param _value: Unused
        '''
        self.__view.get_model().set_sort_column_id(column,
                                                   Gtk.SortType.ASCENDING)

    def set_resizable(self, column, resizable, ellipsize=False):
        '''
        Set Resizable and Ellipse Mode.

        :param column: Column
        :type column: int
        :param resizable: Resizable setting
        :type resizable: bool
        :param ellipsize: Ellipsize Mode, True for Omit characters at end.
                          Default false
        :type ellipsize: bool
        '''
        col = self.__view.get_column(column)
        col.set_resizable(resizable)
        rend = Gtk.CellRendererText()
        rend.set_property("ellipsize",
                          ellipsize and Pango.EllipsizeMode.END \
                              or Pango.EllipsizeMode.NONE)

    def set_expander(self, column):
        '''
        Set Expander.

        :param column: Column
        :type column: int
        '''
        col = self.__view.get_column(column)
        self.__view.set_expander_column(col)

    def set_password(self, column):
        '''
        Set Password.

        :param column: Column
        :type column: int
        '''
        def render_password(_cell_layout, cell, tree_model,
                            tree_iter, data):
            '''
            Render password callback.

            :param _cell_layout:, Gtk.Cell Layout, unused
            :type _cell_layout: :class:`Gtk.CellLayout`
            :param cell: Cell renderer to be set
            :type cell: :class:`Gtk.CellRenderer`
            :param tree_model: The model
            :type tree_model: :class:`Gtk.TreeModel`
            :param tree_iter: A :class:`Gtk.TreeIter` indicating the row
            :type tree_iter: :class:`Gtk.TreeIter`
            :param data: Column Number
            :type _data: int
            '''
            value = tree_model.get(tree_iter, data + 1)[0]
            cell.set_property("text", "*" * len(value))

        view_column = self.__view.get_column(column)
        renderer = Gtk.CellRendererText()
        view_column.set_cell_data_func(renderer, render_password, column)


def test():
    '''Unit Test'''

    logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
                        datefmt="%m/%d/%Y %H:%M:%S",
                        level=logging.INFO)
    logger = logging.getLogger("KeyDistWidgets Test")

    window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
    window.connect("destroy", Gtk.main_quit)

    keyed_list = KeyedListWidget([(GObject.TYPE_STRING, "_ID"),
                                  (GObject.TYPE_STRING, "Name"),
                                  (GObject.TYPE_BOOLEAN, "Info")])

    keyed_list.set_resizable(0, True)

    keyed_list.set_item("Test1", "Test1", True)
    keyed_list.set_item("Test2", "Test2", True)
    keyed_list.set_item("Test3", "Test2", False)

    keyed_list.show()
    window.add(keyed_list)
    window.show()

    try:
        Gtk.main()
    except KeyboardInterrupt:
        pass

    for key in keyed_list.get_keys():
        logger.info(keyed_list.get_item(key))

if __name__ == "__main__":
    test()
