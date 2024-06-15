# File: configui/dratslistconfigwidget.py

'''D-Rats List Configuration Module.'''

# Copyright 2009 Dan Smith <dsmith@danplanet.com>
# review 2015-2020 Maurizio Andreotti  <iz2lxi@yahoo.it>
# Copyright 2021-2024 John. E. Malmberg - Python3 Conversion
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

import ast
import logging
import configparser

import gi  # type: ignore # Needed for pylance on Windows.
gi.require_version("Gtk", "3.0")
from gi.repository import GObject    # type: ignore

if not '_' in locals():
    import gettext
    _ = gettext.gettext

from .dratsconfigwidget import DratsConfigWidget
from ..keyedlistwidget import KeyedListWidget


class DratsListConfigWidget(DratsConfigWidget):
    '''
    D-Rats List Configuration Widget.

    :param section: Section of configuration file
    :type section: str
    '''
    logger = logging.getLogger("DratsListConfigWidget")

    def __init__(self, section):
        try:
            DratsConfigWidget.__init__(self, section=section)
        except configparser.NoOptionError:
            pass
        self.listw = None

    def convert_types(self, col_types, values):
        '''
        Convert Types.

        :param col_types: Column types
        :type col_types: list
        :param values: Values to convert
        :type values: list
        :returns: Converted value
        :rtype: list
        '''
        newvals = []

        i = 0
        while i < len(values):
            try:
                gtype, label = col_types[i]
                value = values[i]
            except IndexError:
                self.logger.info("No column %i for values %s", i, values)
                break

            try:
                if gtype == GObject.TYPE_INT:
                    value = int(value)
                elif gtype == GObject.TYPE_FLOAT:
                    value = float(value)
                elif gtype == GObject.TYPE_BOOLEAN:
                    value = ast.literal_eval(value)
            except ValueError:
                self.logger.info("Failed to convert %s for %s",
                                 value, label, exc_info=True)
                return []

            i += 1
            newvals.append(value)

        return newvals

    def set_sort_column(self, col):
        '''
        Set Sort Column.

        :param col: Column to sort
        :type col: int
        '''
        self.listw.set_sort_column(col)

    def add_list(self, cols, make_key=None):
        '''
        Add to list.

        :param cols: list of columns
        :type cols: list
        :param make_key: key for columns, default None
        :type make_key: function(any)
        :returns: List widget for updating
        :rtype: :class:`keyedlistwidget.KeyedListWidget`
        '''
        def item_set(_list_widget, _key):
            '''
            List Widget item-set handler.

            :param _widget: Widget signaled, unused
            :type _widget: :class:`keyedlistWidget.KeyedListWidget`
            :param _key: key for widget, unused
            :type _key: any
            '''

        list_widget = KeyedListWidget(cols)

        def item_toggled(_widget, _ident, _value):
            '''
            List Widget item-toggled handler

            :param _widget: Widget signaled, unused
            :type _widget: :class:`keyedwidget.KeyedListWidget`
            :param _ident: Identification item toggled
            :type _ident: str
            :param _value: Toggled value
            :type _value: bool
            '''
            return

        list_widget.connect("item-toggled", item_toggled)

        options = self.config.options(self.vsec)
        for option in options:
            vals = self.config.get(self.vsec, option).split(",", len(cols))
            vals = self.convert_types(cols[1:], vals)
            if not vals:
                continue

            if make_key:
                key = make_key(vals)
            else:
                key = vals[0]
            list_widget.set_item(key, *tuple(vals))

        list_widget.connect("item-set", item_set)
        list_widget.show()

        self.pack_start(list_widget, 1, 1, 1)

        self.listw = list_widget

        return list_widget

    def save(self):
        '''Save.'''
        for opt in self.config.options(self.vsec):
            self.config.remove_option(self.vsec, opt)

        count = 0

        for key in self.listw.get_keys():
            vals = self.listw.get_item(key)
            vals = [str(x) for x in vals]
            value = ",".join(vals[1:])
            label = "%s_%i" % (self.vsec, count)
            self.logger.info("Setting %s: %s", label, value)
            self.config.set(self.vsec, label, value)
            count += 1
