#
'''Misc Widgets.'''
# pylint: disable=too-many-lines
# Copyright 2008 Dan Smith <dsmith@danplanet.com>
# Copyright 2021-2022 John. E. Malmberg - Python3 Conversion
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
import os

from six.moves import range # type:ignore

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GObject
from gi.repository import Pango

from . import dplatform


class MiscWidgetsException(Exception):
    '''Generic Misc Widgets Exception.'''


class KeyedListWidgetException(MiscWidgetsException):
    '''Generic KeyedList Widget Exception.'''


class KeyedListWidgetMakeViewError(KeyedListWidgetException):
    '''Keyed List Widget Make View Error'''


class ListWidgetException(MiscWidgetsException):
    '''Generic List Widget Exception.'''


class TreeWidgetException(ListWidgetException):
    '''Generic Tree Widget Exception.'''


class MakeViewColumnError(ListWidgetException):
    '''List Widget Make View Column Error.'''


class ListWidgetAddItemException(ListWidgetException):
    '''List Widget Add Item Exception.'''


class AddItemColumnError(ListWidgetAddItemException):
    '''List Widget Add Item Column Error.'''


class AddItemParentError(ListWidgetAddItemException):
    '''Tree Widget Add Item Parent Error.'''


class DelItemError(ListWidgetException):
    '''Tree Widget Del Item Error.'''


class GetItemError(ListWidgetException):
    '''Tree Widget Get Item Error.'''


class SetItemError(ListWidgetException):
    '''Tree Widget Set Item Error.'''


class LatLongEntryException(MiscWidgetsException):
    '''Generic LatLongEntry Exception.'''


class LatLongEntryValueError(LatLongEntryException):
    '''LatLongEntry Value Error.'''


class LatLongEntryParseDMSError(LatLongEntryException):
    '''LatLongEntry Parse DMS Error.'''


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
        Gtk.Box.__init__(self, True, 0)

        self.logger = logging.getLogger("KeyedListWidget")
        self.columns = columns

        types = tuple([x for x, y in columns])

        self.__store = Gtk.ListStore(*types)
        self.__view = Gtk.TreeView.new_with_model(self.__store)
        self.__view.set_hexpand(True)

        self.pack_start(self.__view, 1, 1, 1)

        self.__toggle_connected = False

        self._make_view()
        self.__view.show()

    def _toggle(self, _rend, path, colnum):
        '''
        Internal Toggle callback.

        :param _rend: unused
        :type _rend: :class:`Gtk.CellRenderer`
        :param path: The event location
        :type path: str
        :param colnum,: Colum to toggle
        :type colnum: int
        '''
        if self.__toggle_connected:
            # pylint: disable=unsubscriptable-object
            self.__store[path][colnum] = not self.__store[path][colnum]
            iter_val = self.__store.get_iter(path)
            ident, = self.__store.get(iter_val, 0)
            # pylint: disable=unsubscriptable-object
            self.emit("item-toggled", ident, self.__store[path][colnum])

    def _edited(self, _rend, path, new, colnum):
        iter_val = self.__store.get_iter(path)
        key = self.__store.get(iter_val, 0)
        self.__store.set(iter_val, colnum, new)
        self.emit("item-set", key)

    def _mouse(self, _view, event):
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
        :param values: Values to set for item
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
        :returns: Item or None
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

    def has_item(self, key):
        '''
        Has Item.

        :param key
        :returns: True if key is present
        :rtype: bool
        '''
        return self.get_item(key) is not None

    def get_selected(self):
        '''
        Get Selected.

        :returns: Selected item
        '''
        try:
            (store, iter_val) = self.__view.get_selection().get_selected()
            return store.get(iter_val, 0)[0]
        # pylint: disable=broad-except
        except Exception:
            self.logger.info("get_selected:"
                             " Unable to find selected: broad-exception",
                             exc_info=True)
            return None

    def select_item(self, key):
        '''
        Select Item.

        :param key: Key to select
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
        '''
        keys = []
        iter_val = self.__store.get_iter_first()
        while iter_val:
            key, = self.__store.get(iter_val, 0)
            keys.append(key)
            iter_val = self.__store.iter_next(iter_val)

        return keys

    # pylint: disable=arguments-differ
    def connect(self, signame, handler, *args):
        '''
        Connect.

        :param signame: Signal name
        :type str:
        :param handler: Handler function
        :type handler: function
        :param args: Arguments for signal
        '''
        if signame == "item-toggled":
            self.__toggle_connected = True

        Gtk.Box.connect(self, signame, handler, *args)

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
        #rend = col.get_cell_renderers()[0]
        rend = Gtk.CellRendererText()
        rend.set_property("ellipsize",
                          ellipsize and Pango.EllipsizeMode.END \
                              or Pango.EllipsizeMode.NONE)

    def set_expander(self, column):
        '''
        Set Expander.

        :param colum: Column
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
        def render_password(_foo, rend, model, iter_val, _data):
            val = model.get(iter_val, column+1)[0]
            rend.set_property("text", "*" * len(val))

        col = self.__view.get_column(column)
        #rnd = col.get_cell_renderers()[0]
        rnd = Gtk.CellRendererText()
        col.set_cell_data_func(rnd, render_password)


class ListWidget(Gtk.Box):
    '''
    List Widget Box.

    :param columns: Columns for Widget
    :type: list of tuple of (type, str)
    :param parent: Is parent, default True
    :type parent: bool
    '''
    __gsignals__ = {
        "click-on-list" : (GObject.SignalFlags.RUN_LAST,
                           GObject.TYPE_NONE,
                           (Gtk.TreeView, Gdk.Event)),
        "item-toggled" : (GObject.SignalFlags.RUN_LAST,
                          GObject.TYPE_NONE,
                          (GObject.TYPE_PYOBJECT,)),
        }

    store_type = Gtk.ListStore

    def __init__(self, columns, parent=True):
        Gtk.Box.__init__(self)
        self.logger = logging.getLogger("ListWidget")
        col_types = tuple([x for x, y in columns])
        self._ncols = len(col_types)

        self._store = self.store_type(*col_types)
        self._view = None
        self.make_view(columns)

        self._view.show()
        if parent:
            self.pack_start(self._view, 1, 1, 1)

        self.toggle_cb = []

    def mouse_cb(self, view, event_button):
        '''
        Mouse Callback.

        :param view: view object
        :type view: :class:`Gtk.ListwWidget`
        :param event: Mouse button event
        :type event: :class:`Gdk.EventButton`
        '''
        event = Gdk.Event.new(event_button.type)
        # https://lazka.github.io/pgi-docs/Gdk-3.0/classes/Event.html
        # on 11-Sep-2021 states that the event button is Gdk.EventButton type.
        # It appears that it needs to be the button member of Gdk.EventButton.
        event.button = event_button.button
        self.emit("click-on-list", view, event)

    def _toggle(self, _render, path, column):
        '''
        Internal Toggle callback.

        :param _render: unused
        :type _render: :class:`Gtk.CellRenderer`
        :param path: The event location
        :type path: str
        :param column: Colum to toggle
        :type column: int
        '''
        # pylint: disable=unsubscriptable-object
        self._store[path][column] = not self._store[path][column]
        iter_val = self._store.get_iter(path)
        vals = tuple(self._store.get(iter_val, *tuple(range(self._ncols))))
        for callback in self.toggle_cb:
            callback(*vals)
        self.emit("item-toggled", vals)

    def make_view(self, columns):
        '''
        Make View.

        :param columns: column data
        :type columns: list
        :raises: :class:`MakeViewColumnError` if unknown column type
        '''
        self._view = Gtk.TreeView.new_with_model(self._store)

        for col_type, col in columns:
            if col.startswith("__"):
                continue

            index = columns.index((col_type, col))

            if col_type in [GObject.TYPE_STRING,
                            GObject.TYPE_INT,
                            GObject.TYPE_FLOAT]:
                rend = Gtk.CellRendererText()
                column = Gtk.TreeViewColumn(col, rend, text=index)
                column.set_resizable(True)
                rend.set_property("ellipsize", Pango.EllipsizeMode.END)

            elif col_type == GObject.TYPE_BOOLEAN:
                rend = Gtk.CellRendererToggle()
                rend.connect("toggled", self._toggle, index)
                column = Gtk.TreeViewColumn(col, rend, active=index)
            else:
                raise MakeViewColumnError("Unknown column type (%i)" % index)

            column.set_sort_column_id(index)
            self._view.append_column(column)

        self._view.connect("button_press_event", self.mouse_cb)

    def packable(self):
        '''
        Packable object if a TreeView.

        :returns: packable object or None
        :rtype: :class:`Gtk.TreeView`
        '''
        return self._view

    def add_item(self, *vals):
        '''
        Add Item.

        :param vals: Values to add
        :type vals: tuple
        :raises: :class:`AddItemColumnError` if not enough values
        '''
        if len(vals) != self._ncols:
            raise AddItemColumnError("Need %i columns" % self._ncols)

        _iter_val = self._store.append(vals)

    def _remove_item(self, model, _path, iter_val, match):
        # print statement to be removed once the types are identified.
        # print("listwidget._remove_item", type(model), type(_path),
        #      type(iter_val), type(match))
        vals = model.get(iter_val, *tuple(range(0, self._ncols)))
        if vals == match:
            model.remove(iter_val)

    # WB8TYW: I can not find a caller of this method.
    def remove_item(self, *vals):
        '''
        Remove Item.

        :param vals: Items to remove
        :raises: :class:`DelItemError` if not enough vals
        '''
        self.logger.info("remove_item %s", vals)
        if len(vals) != self._ncols:
            raise DelItemError("Need %i columns" % self._ncols)

    def remove_selected(self):
        '''Remove Selected.'''
        try:
            (lst, iter_val) = self._view.get_selection().get_selected()
            lst.remove(iter_val)
        # pylint: disable=broad-except
        except Exception:
            self.logger.info("remove_selected: Unable to remove:"
                             "broad-exception", exc_info=True)

    def get_selected(self, take_default=False):
        '''
        Get Selected.

        :param take_default: Default False
        :type take_default: bool
        :returns: Selected value
        '''
        (lst, iter_val) = self._view.get_selection().get_selected()
        if not iter_val and take_default:
            iter_val = lst.get_iter_first()

        return lst.get(iter_val, *tuple(range(self._ncols)))

    def move_selected(self, delta):
        '''
        Move Selected.

        :param delta: Delta to move
        :returns: True if move successful
        :rtype: bool
        '''
        # print statement to be removed once the types are identified.
        # print("listwidget.move_selected", type(delta))
        (lst, iter_val) = self._view.get_selection().get_selected()

        pos = int(lst.get_path(iter_val)[0])

        try:
            target = None

            if delta > 0 and pos > 0:
                target = lst.get_iter(pos-1)
            elif delta < 0:
                target = lst.get_iter(pos+1)
        # pylint: disable=broad-except
        except Exception:
            self.logger.info("move_selected: broad-exception", exc_info=True)
            return False

        if target:
            return lst.swap(iter_val, target)
        return False

    def _get_value(self, model, _path, iter_val, lst):
        # print statement to be removed once the types are identified.
        # print("listwidget.get_value", type(model), type(_path),
        #       type(iter_val), type(lst))
        lst.append(model.get(iter_val, *tuple(range(0, self._ncols))))

    def get_values(self):
        '''
        Get Values.

        :returns: List of values
        :rtype: list
        '''
        lst = []

        self._store.foreach(self._get_value, lst)

        return lst

    def set_values(self, lst):
        '''
        Set Values.

        :param lst: List of values
        :type lst: List
        '''
        self._store.clear()

        for i in lst:
            self.add_item(*i)


class TreeWidget(ListWidget):
    '''
    Tree Widget.

    :param columns: Columns for Widget
    :type: list of tuple of (type, str)
    :param key: column number to use as a key
    :type key: int
    :param parent: Is a parent, default True
    :type parent: true
    '''

    store_type = Gtk.TreeStore

    def __init__(self, columns, key, parent=True):
        ListWidget.__init__(self, columns, parent)
        self.logger = logging.getLogger("TreeWidget")
        self._key = key

    def _toggle(self, _render, path, column):
        '''
        Internal Toggle callback.

        :param _render: unused
        :type _render: :class:`Gtk.CellRenderer`
        :param path: The event location
        :type path: str
        :param column: Colum to toggle
        :type column: int
        '''
        # pylint: disable=unsubscriptable-object
        self._store[path][column] = not self._store[path][column]
        iter_val = self._store.get_iter(path)
        vals = tuple(self._store.get(iter_val, *tuple(range(self._ncols))))

        piter = self._store.iter_parent(iter_val)
        if piter:
            parent = self._store.get(piter, self._key)[0]
        else:
            parent = None

        for callback in self.toggle_cb:
            callback(parent, *vals)

    def _add_item(self, piter, *vals):
        '''
        Add item internal.

        :param piter: Parent to append row to
        :type piter: :class:`Gtk.TreeIter`
        :param vals: Values to add
        :type vals: tuple
        '''
        values = []
        indx = 0
        for val in vals:
            values.append(val)
            indx += 1

        _iter_val = self._store.append(piter, values)

    def _iter_of(self, key, iter_val=None):
        '''
        internal iter_of.

        :param key: key to lookup
        :type key: str
        :param iter_val: Parent of row
        :type iter_val: :class:`Gtk.TreeIter`
        :returns: iter_val of row or None
        :rtype: :class:`Gtk.TreeIter`
        '''
        if not iter_val:
            iter_val = self._store.get_iter_first()

        while iter_val is not None:
            found_id = self._store.get(iter_val, self._key)[0]
            if found_id == key:
                return iter_val

            iter_val = self._store.iter_next(iter_val)

        return None

    # pylint: disable=arguments-differ
    def add_item(self, parent, *vals):
        '''
        Add Item.

        :param parent: Parent of item
        :type parent: str
        :param vals: Optional vals for item
        :type vals: tuple
        :raises: :class:`AddItemColumnError` if not enough columns
        :raises: :class:`AddItemParentError` if parent not found
        '''
        if len(vals) != self._ncols:
            raise AddItemColumnError("Need %i columns" % self._ncols)

        if not parent:
            self._add_item(None, *vals)
        else:
            iter_val = self._iter_of(parent)
            # pylint: disable=raising-format-tuple
            if iter_val:
                self._add_item(iter_val, *vals)
            else:
                raise AddItemParentError("Parent not found: %s", parent)

    def _set_values(self, parent, vals):
        '''
        Set values internal.

        :param parent: Parent of row, or None.
        :type parent: :class:`Gtk.TreeIter`
        :param vals: Values to set
        '''
        if isinstance(vals, dict):
            for key, val in vals.copy().items():
                iter_val = self._store.append(parent)
                self._store.set(iter_val, self._key, key)
                self._set_values(iter_val, val)
        elif isinstance(vals, list):
            for indx in vals:
                self._set_values(parent, indx)
        elif isinstance(vals, tuple):
            self._add_item(parent, *vals)
        else:
            self.logger.info("_set_values: Unknown type: %s", vals)

    # pylint: disable=arguments-differ
    def set_values(self, vals):
        '''
        Set Values.

        :param vals: Values to set
        :type vals: dict
        '''
        self._store.clear()
        self._set_values(self._store.get_iter_first(), vals)

    def _get_values(self, iter_val, onlyone=False):
        '''
        Get Values internal.

        :param iter_val: Row data to retrieve
        :type iter_val: :class:`Gtk.TreeIter`
        :param onlyone: Flag to get only one value
        :type onlyone: bool
        :returns: values
        :rtype: list
        '''
        values = []
        while iter_val:
            if self._store.iter_has_child(iter_val):
                values.append((self._store.get(iter_val,
                                               *tuple(range(self._ncols))),
                               self._get_values(
                                   self._store.iter_children(iter_val))))
            else:
                values.append(self._store.get(iter_val,
                                              *tuple(range(self._ncols))))

            if onlyone:
                break
            iter_val = self._store.iter_next(iter_val)

        return values

    # pylint: disable=arguments-differ
    def get_values(self, parent=None):
        '''
        Get Values.

        :param parent: Parent object, default None
        :type parent: str
        :returns: values
        :rtype: list
        '''
        if parent:
            iter_val = self._iter_of(parent)
        else:
            iter_val = self._store.get_iter_first()

        return self._get_values(iter_val, parent is not None)

    def clear(self):
        '''Clear.'''
        self._store.clear()

    def del_item(self, parent, key):
        '''
        Del Item.

        :param parent: parent of object
        :type parent: str
        :param key: key of item to delete
        :raises: :class:`DelItemError` if item is not found
        '''
        iter_val = self._iter_of(key,
                                 self._store.iter_children(
                                     self._iter_of(parent)))
        if iter_val:
            self._store.remove(iter_val)
        else:
            raise DelItemError("Item not found")

    def get_item(self, parent, key):
        '''
        Set Item.

        :param parent: Parent of object
        :type parent: str
        :param key: Key for item
        :raises: :class:`GetItemError` when item not found
        :returns: Returned item
        '''
        iter_val = self._iter_of(key,
                                 self._store.iter_children(
                                     self._iter_of(parent)))

        if iter_val:
            return self._store.get(iter_val, *(tuple(range(0, self._ncols))))
        raise GetItemError("Item not found")

    def set_item(self, parent, *vals):
        '''
        Set Item.

        :param parent: Parent of item
        :type parent: str
        :param vals: Optional vals
        :raises: :class:`SetItemError` if item is not found
        '''
        iter_val = self._iter_of(vals[self._key],
                                 self._store.iter_children(
                                     self._iter_of(parent)))

        if iter_val:
            args = []
            i = 0

            for val in vals:
                args.append(i)
                args.append(val)
                i += 1

            self._store.set(iter_val, *(tuple(args)))
        else:
            raise SetItemError("Item not found")


class ProgressDialog(Gtk.Window):
    '''
    Progress Dialog Window.

    :param title: Title for window
    :type title: str
    :param parent: Is a parent Window
    :type parent: bool
    '''

    def __init__(self, title, parent=None):
        Gtk.Window.__init__(self, type=Gtk.WindowType.TOPLEVEL)
        self.set_modal(True)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_title(title)
        if parent:
            self.set_transient_for(parent)

        self.set_resizable(False)

        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 2)

        self.label = Gtk.Label.new("")
        self.label.set_size_request(100, 50)
        self.label.show()

        self.pbar = Gtk.ProgressBar()
        self.pbar.show()

        vbox.pack_start(self.label, 0, 0, 0)
        vbox.pack_start(self.pbar, 0, 0, 0)

        vbox.show()

        self.add(vbox)

    def set_text(self, text):
        '''
        Set Text.

        :parm text: Text to set
        :type text: str
        '''
        self.label.set_text(text)
        self.queue_draw()

        while Gtk.events_pending():
            Gtk.main_iteration_do(False)

    def set_fraction(self, frac):
        '''
        Set Fraction.

        :param frac: Fraction to set
        :type frac: float
        '''
        self.pbar.set_fraction(frac)
        self.queue_draw()

        while Gtk.events_pending():
            Gtk.main_iteration_do(False)


class LatLonEntry(Gtk.Entry):
    '''
    Latitude Longitude Entry.

    :param args: Optional gtkEntry arguments
    '''
    def __init__(self, *args):
        Gtk.Entry.__init__(self, *args)

        self.logger = logging.getLogger("LatLonEntry")
        self.connect("changed", self.format)

    # pylint: disable=no-self-use
    def format(self, entry):
        '''
        Format entry text.

        :param entry: Entry Object
        '''
        string = entry.get_text()
        if string is None:
            return

        deg = u"\u00b0"

        while " " in string:
            if "." in string:
                break
            elif deg not in string:
                string = string.replace(" ", deg)
            elif "'" not in string:
                string = string.replace(" ", "'")
            elif '"' not in string:
                string = string.replace(" ", '"')
            else:
                string = string.replace(" ", "")

        entry.set_text(string)

    # pylint: disable=no-self-use
    def parse_dd(self, string):
        '''
        Parse Decimal Degree string.

        :param string: text with decimal Degrees
        :type: string: str
        :returns: Numeric coordinate value
        :rtype: float
        '''
        return float(string)

    # pylint: disable=no-self-use
    def parse_dm(self, string):
        '''
        Parse Degrees Minutes string.

        :param string: Text with Degrees and Minutes
        :type string: str
        :returns: Degrees and minutes
        :rtype: float
        '''
        string = string.strip()
        string = string.replace('  ', ' ')

        (_degrees, _minutes) = string.split(' ', 2)

        degrees = int(_degrees)
        minutes = float(_minutes)

        return degrees + (minutes / 60.0)

    # pylint: disable=no-self-use
    def parse_dms(self, string):
        '''
        Parse Degrees Minutes Seconds from string.

        :param string: Text with Degrees Minutes and Seconds
        :type string: str
        :raises: :class:`LatLongEntryParseDMSError` on parsing error.
        :returns: Degrees Minutes and Seconds
        :rtype: float
        '''
        string = string.replace(u"\u00b0", " ")
        string = string.replace('"', ' ')
        string = string.replace("'", ' ')
        string = string.replace('  ', ' ')
        string = string.strip()

        items = string.split(' ')

        if len(items) > 3:
            raise LatLongEntryParseDMSError("Invalid format")
        elif len(items) == 3:
            deg = items[0]
            mns = items[1]
            sec = items[2]
        elif len(items) == 2:
            deg = items[0]
            mns = items[1]
            sec = 0
        elif len(items) == 1:
            deg = items[0]
            mns = 0
            sec = 0
        else:
            deg = 0
            mns = 0
            sec = 0

        degrees = int(deg)
        minutes = int(mns)
        seconds = float(sec)

        return degrees + (minutes / 60.0) + (seconds / 3600.0)

    def value(self):
        '''
        Coordinate Value.

        :raises: :class:`LatLongEntryValueError` for invalid values.
        :returns: Coordinate value from widget
        :rtype: float
        '''
        string = self.get_text()

        try:
            return self.parse_dd(string)
        except ValueError:
            try:
                return self.parse_dm(string)
            except ValueError:
                try:
                    return self.parse_dms(string)
                except LatLongEntryParseDMSError:
                    pass

        raise LatLongEntryValueError("Invalid format")

    def validate(self):
        '''
        Validate.

        :Returns: True if validates
        :rtype: bool
        '''
        try:
            self.value()
            return True
        except LatLongEntryValueError:
            return False


class YesNoDialog(Gtk.Dialog):
    '''
    Yes No Dialog.

     Does not appear to be currently used.

    :param title: Dialog title, Default ''
    :type title: str
    :param parent: Parent widget, default None
    :type parent: :class:`Gtk.Widget`
    :param buttons: list of button tuples, Default None
    :type buttons: list of (:class:`Gtk.Widget`, response)
    '''

    def __init__(self, title="", parent=None, buttons=None):
        Gtk.Dialog.__init__(self, parent=parent)
        self.set_title(title)
        if buttons:
            for button, response in buttons:
                self.add_button(button, response)

        self._label = Gtk.Label.new("")
        self._label.show()

        self.vbox.pack_start(self._label, 1, 1, 1)

    def set_text(self, text):
        '''
        Set Text.

        :param text: Text to set
        :type text: str
        '''
        self._label.set_text(text)


def make_choice(options, editable=True, default=None):
    '''
    Make Choice.

    :param options: options
    :param editable: Default True
    :type editable: bool
    :param default: Default None
    :returns: selection dialog
    :rtype: :class:`Gtk.ComboBox.Text`
    '''
    logger = logging.getLogger("make_choice")
    if editable:
        sel = Gtk.ComboBoxText.new_with_entry()
    else:
        sel = Gtk.ComboBoxText.new()

    for opt in options:
        sel.append_text(opt)

    if default:
        try:
            idx = options.index(default)
            sel.set_active(idx)
        # pylint: disable=broad-except
        except Exception:
            logger.info("broad-exception suppressed", exc_info=True)
            # pass

    return sel


class FilenameBox(Gtk.Box):
    '''
    File Name Box.

    :params find_dir: Find directory, default False
    :type find_dir: bool
    :param types: types, default []
    :type types: list
    '''
    __gsignals__ = {
        "filename-changed" : (GObject.SignalFlags.RUN_LAST,
                              GObject.TYPE_NONE, ()),
        }

    def __init__(self, find_dir=False, types=None):
        Gtk.Box.__init__(self, Gtk.Orientation.HORIZONTAL, 0)

        if types:
            self.types = types
        else:
            self.types = []

        self.filename = Gtk.Entry()
        self.filename.show()
        self.pack_start(self.filename, 1, 1, 1)

        browse = Gtk.Button.new_with_label("...")
        browse.show()
        self.pack_start(browse, 0, 0, 0)

        self.filename.connect("changed", self.do_changed)
        browse.connect("clicked", self.do_browse, find_dir)

    def do_browse(self, _dummy, directory):
        '''
        Do Browse.

        :param _dummy: unused
        :param directory: Is a directory
        :type directory: bool
        '''
        if self.filename.get_text():
            start = os.path.dirname(self.filename.get_text())
        else:
            start = None

        if directory:
            fname = dplatform.get_platform().gui_select_dir(start)
        else:
            fname = dplatform.get_platform().gui_save_file(start)
        if fname:
            self.filename.set_text(fname)

    def do_changed(self, _dummy):
        '''
        Do Changed.

        :param _dummy: Unused
        '''
        self.emit("filename_changed")

    def set_filename(self, fname):
        '''
        Set Filename.

        :param fname: File name
        :type fname: str
        '''
        self.filename.set_text(fname)

    def get_filename(self):
        '''
        Get Filename.

        :returns: Filename
        :rtype: str
        '''
        return self.filename.get_text()

    def set_mutable(self, mutable):
        '''
        Set Mutable.

        :param mutable: Set mutable property
        :type mutable: bool
        '''
        self.filename.set_sensitive(mutable)


def make_pixbuf_choice(options, default=None):
    '''
    Make Pixbuf Choice.

    :param options: Options
    :param default: Default is None
    :returns: GtkBox object
    :rtype: :class:`Gtk.Box`
    '''
    store = Gtk.ListStore(GdkPixbuf.Pixbuf, GObject.TYPE_STRING)
    box = Gtk.ComboBox.new_with_model(store)

    cell = Gtk.CellRendererPixbuf()
    box.pack_start(cell, True)
    box.add_attribute(cell, "pixbuf", 0)

    cell = Gtk.CellRendererText()
    box.pack_start(cell, True)
    box.add_attribute(cell, "text", 1)

    _default = None
    for pic, value in options:
        iter_val = store.append()
        store.set(iter_val, 0, pic, 1, value)
        if default == value:
            _default = options.index((pic, value))

    if _default:
        box.set_active(_default)

    return box


def test():
    '''Unit Test'''

    logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
                        datefmt="%m/%d/%Y %H:%M:%S",
                        level=logging.INFO)
    logger = logging.getLogger("MiscWidgets")

    win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
    win.connect("destroy", Gtk.main_quit)

    lst = ListWidget([(GObject.TYPE_STRING, "Foo"),
                      (GObject.TYPE_BOOLEAN, "Bar")])

    lst.add_item("Test1", True)
    lst.set_values([("Test2", True), ("Test3", False)])

    lst.show()
    win.add(lst)
    win.show()

    win1 = ProgressDialog("ProgessBar")
    win1.set_fraction(0.25)
    win1.show()

    win2 = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
    lle = LatLonEntry()
    lle.show()
    win2.add(lle)
    win2.show()

    win3 = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
    lst = TreeWidget([(GObject.TYPE_STRING, "Id"),
                      (GObject.TYPE_STRING, "Value"),
                      (GObject.TYPE_FLOAT, "latitude")],
                     1)
    # lst.add_item("Foo", "Bar", "Baz", 0)
    lst.set_values({"Fruit" : [("Apple", "Red", 0), ("Orange", "Orange", 0)],
                    "Pizza" : [("Cheese", "Simple", 0), ("Pepperoni", "Yummy", 0)]})
    lst.add_item("Fruit", "Bananna", "Yellow", 3)
    lst.show()
    win3.add(lst)
    win3.show()

    def print_val(entry):
        if entry.validate():
            logger.info("Valid: %s", entry.value())
        else:
            logger.info("Invalid")
    lle.connect("activate", print_val)

    lle.set_text("45 13 12")

    try:
        Gtk.main()
    except KeyboardInterrupt:
        pass

    logger.info(lst.get_values())

if __name__ == "__main__":
    test()
