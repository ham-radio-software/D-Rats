'''List Widget.'''
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
from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import Pango


class ListWidgetException(Exception):
    '''Generic List Widget Exception.'''


class TreeWidgetException(ListWidgetException):
    '''Generic Tree Widget Exception.'''


class MakeViewColumnError(ListWidgetException):
    '''List Widget Make View Column Error.'''


class AddItemColumnError(ListWidgetException):
    '''List Widget Add Item Column Error.'''


class DelItemError(ListWidgetException):
    '''List Widget Del Item Error.'''


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
    logger = logging.getLogger("ListWidget")

    def __init__(self, columns, parent=True):
        Gtk.Box.__init__(self)
        col_types = tuple(x for x, y in columns)
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
        :param column: Column to toggle
        :type column: int
        '''
        iter_val = self._store.get_iter(path)
        value = self._store.get_value(iter_val, column)
        self._store.set_value(iter_val, column, not value)
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

    # WB8TYW: I can not find a caller of this method.
    def _remove_item(self, model, _path, iter_val, match):
        # print statement to be removed once the types are identified.
        # print("ListWidget._remove_item", type(model), type(_path),
        #      type(iter_val), type(match))
        vals = model.get(iter_val, *tuple(range(0, self._ncols)))
        if vals == match:
            model.remove(iter_val)

    # WB8TYW: I can not find a caller of this method.
    def remove_item(self, *vals):
        '''
        Remove Item, No operation.

        :param vals: Items to remove
        :type vals: tuple
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
        :rtype: any
        '''
        (lst, iter_val) = self._view.get_selection().get_selected()
        if not iter_val and take_default:
            iter_val = lst.get_iter_first()

        return lst.get(iter_val, *tuple(range(self._ncols)))

    def move_selected(self, delta):
        '''
        Move Selected.

        :param delta: Delta to move
        :type delta: int
        :returns: True if move successful
        :rtype: bool
        '''
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
        # print("ListWidget.get_value", type(model), type(_path),
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

def test():
    '''Unit Test'''

    logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
                        datefmt="%m/%d/%Y %H:%M:%S",
                        level=logging.INFO)
    logger = logging.getLogger("ListWidget Test")

    window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
    window.connect("destroy", Gtk.main_quit)

    list_widget = ListWidget([(GObject.TYPE_STRING, "Foo"),
                            (GObject.TYPE_BOOLEAN, "Bar")])

    list_widget.add_item("Test1", True)
    list_widget.set_values([("Test2", True), ("Test3", False)])

    list_widget.show()
    window.add(list_widget)
    window.show()

    try:
        Gtk.main()
    except KeyboardInterrupt:
        pass

    logger.info(list_widget.get_values())

if __name__ == "__main__":
    test()
