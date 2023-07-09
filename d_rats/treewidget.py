'''Tree Widget'''
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

from .listwidget import ListWidget
from .listwidget import ListWidgetException
from .listwidget import AddItemColumnError
from .listwidget import DelItemError


class GetItemError(ListWidgetException):
    '''Tree Widget Get Item Error.'''


class SetItemError(ListWidgetException):
    '''Tree Widget Set Item Error.'''


class AddItemParentError(ListWidgetException):
    '''Tree Widget Add Item Parent Error.'''


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
        :param column: Column number to toggle
        :type column: int
        '''
        iter_val = self._store.get_iter(path)
        value = self._store.get_value(iter_val, column)
        self._store.set_value(iter_val, column, not value)

        vals = tuple(self._store.get(iter_val, *tuple(range(self._ncols))))

        piter = self._store.iter_parent(iter_val)
        if piter:
            parent = self._store.get_value(piter, self._key)
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

    # Intentional differences in ListWidget and TreeWidget
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
            if iter_val:
                self._add_item(iter_val, *vals)
            else:
                raise AddItemParentError("Parent not found: %s" % parent)

    def _set_values(self, parent, vals):
        '''
        Set values internal.

        :param parent: Parent of row, or None.
        :type parent: :class:`Gtk.TreeIter`
        :param vals: Values to set
        :type vals: any
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

    # Intentional differences in ListWidget and TreeWidget
    # Parameter 'lst' has been renamed to 'vals'
    # pylint: disable=arguments-differ, arguments-renamed
    def set_values(self, vals):
        '''
        Set Values.

        :param vals: Values to set
        :type vals: dict
        '''
        self._store.clear()
        self._set_values(self._store.get_iter_first(), vals)

    def _get_values(self, iter_val, only_one=False):
        '''
        Get Values internal.

        :param iter_val: Row data to retrieve
        :type iter_val: :class:`Gtk.TreeIter`
        :param only_one: Flag to get only one value
        :type only_one: bool
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

            if only_one:
                break
            iter_val = self._store.iter_next(iter_val)

        return values

    # Intentional differences in ListWidget and TreeWidget
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
        :type key: any
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
        :type key: any
        :returns: Returned item
        :rtype: any
        :raises: :class:`GetItemError` when item not found
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
        :type vals: tuple
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


def test():
    '''Unit Test'''

    logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
                        datefmt="%m/%d/%Y %H:%M:%S",
                        level=logging.INFO)
    logger = logging.getLogger("MiscWidgets")

    window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
    window.connect("destroy", Gtk.main_quit)

    columns = [(GObject.TYPE_BOOLEAN, "Show"),
               (GObject.TYPE_STRING, "Station"),
               (GObject.TYPE_FLOAT, "Latitude"),
               (GObject.TYPE_FLOAT, "Longitude"),
               (GObject.TYPE_FLOAT, "Distance"),
               (GObject.TYPE_FLOAT, "Direction")]

    tree = TreeWidget(columns, 1, parent=False)

    scrollw = Gtk.ScrolledWindow()
    scrollw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    scrollw.add(tree.packable())
    scrollw.set_size_request(-1, 150)
    scrollw.show()
    window.add(scrollw)
    window.show()

    tree.add_item(None, True, "TESTCALL", 0, 0, 0, 0)
    tree.add_item(None, False, "N0CALL", 1, 2, 3, 4)

    try:
        Gtk.main()
    except KeyboardInterrupt:
        pass

    logger.info(tree.get_values())

if __name__ == "__main__":
    test()
