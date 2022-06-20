#!/usr/bin/python
'''Main Common.'''
#
# Copyright 2009 Dan Smith <dsmith@danplanet.com>
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

import re

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import GObject

from d_rats import inputdialog, miscwidgets

STATION_REGEX = "^[A-Z0-9- /_]+$"

if not '_' in locals():
    import gettext
    _ = gettext.gettext


def ask_for_confirmation(question, parent=None):
    '''
    Ask for Confirmation.

    :param question: Question for user.
    :type question: str
    :param parent: Parent widget, default None
    :type parent: :class:`Gtk.Widget`
    :returns: True if confirmation is selected.
    :rtype: bool
    '''
    dialog = Gtk.MessageDialog(buttons=Gtk.ButtonsType.YES_NO,
                               parent=parent,
                               message_format=question)
    run_status = dialog.run()
    dialog.destroy()

    return run_status == Gtk.ResponseType.YES


def display_error(message, parent=None):
    '''
    Display Error.

    :param message: Message to display
    :type message: str
    :param parent: Parent widget, default None
    :type parent: :class:`Gtk.Widget`
    :returns: True if user clicks OK button
    :rtype: bool
    '''
    dialog = Gtk.MessageDialog(buttons=Gtk.ButtonsType.OK,
                               parent=parent,
                               message_format=message)
    run_status = dialog.run()
    dialog.destroy()

    return run_status == Gtk.ResponseType.OK


# pylint wants a maximum of 15 local variables
# pylint: disable=too-many-locals
def prompt_for_station(station_list, config, parent=None):
    '''
    Prompt for Station.

    :param station_list: List of station objects
    :type station_list: list[:class:`station_status.Station]`
    :param config: Configuration data
    :type config: :class:`DratsConfig`
    :param parent: Parent widget, default None
    :type parent: :class:`Gtk.Widget`
    :returns: station_text and port_text
    :rtype: tuple[str, str]
    '''
    station_string_list = [str(x) for x in station_list]
    port_list = []
    for i in config.options("ports"):
        enb, port, _rate, _sniff, _raw, name = config.get("ports", i).split(",")
        if enb == "True":
            port_list.append(name)

    default_stationid = defprt = ""
    if station_string_list:
        default_stationid = str(station_string_list[0])
    if port_list:
        defprt = port_list[0]

    port_list.sort()
    station_string_list.sort()

    station = miscwidgets.make_choice(station_string_list, True,
                                      default_stationid)
    port = miscwidgets.make_choice(port_list, False, defprt)

    dialog = inputdialog.FieldDialog(title=_("Enter destination"),
                                     parent=parent)
    dialog.add_field(_("Station"), station)
    dialog.add_field(_("Port"), port)
    station.get_child().set_activates_default(True)

    while True:
        res = dialog.run()
        if res != Gtk.ResponseType.OK:
            break
        station_text = station.get_active_text().upper()
        if "@" in station_text:
            display_error(_("You must enter a station callsign.  " +
                            "You cannot use an email address here"), dialog)
            continue
        elif not re.match(STATION_REGEX, station_text):
            display_error(_("Invalid character in callsign"), dialog)
            continue
        break

    port_text = port.get_active_text()
    dialog.destroy()
    if res == Gtk.ResponseType.OK:
        return station_text, port_text
    return None, None


def prompt_for_string(message, parent=None, orig=""):
    '''
    Prompt for String.

    :param message: Prompt for the message
    :type message: str
    :param parent: Parent widget, default None
    :type parent: :class:`Gtk.Widget`
    :param orig: Default or original text, default ""
    :type orig: str
    :returns: Entered text or None
    :rtype: str
    '''
    dialog = Gtk.MessageDialog(buttons=Gtk.ButtonsType.OK_CANCEL,
                               parent=parent,
                               message_format=message)
    entry = Gtk.Entry()
    entry.set_text(orig)
    entry.show()
    dialog.vbox.pack_start(entry, 1, 1, 1)

    run_status = dialog.run()
    dialog.destroy()

    if run_status == Gtk.ResponseType.OK:
        return entry.get_text()
    return None


def set_toolbar_buttons(config, toolbar):
    '''
    Set Toolbar Buttons.

    :param config: Configuration data
    :type config: :class:`DratsConfig`
    :param toolbar: Toolbar object
    :type toolbar: :class:`Gtk.Toolbar`
    '''
    tbsize = config.get("prefs", "toolbar_button_size")
    if tbsize == _("Default"):
        toolbar.unset_style()
        toolbar.unset_icon_size()
    elif tbsize == _("Small"):
        toolbar.set_style(Gtk.ToolbarStyle.ICONS)
        toolbar.set_icon_size(Gtk.IconSize.SMALL_TOOLBAR)
    elif tbsize == _("Large"):
        toolbar.set_style(Gtk.ToolbarStyle.BOTH)
        toolbar.set_icon_size(Gtk.IconSize.LARGE_TOOLBAR)


class MainWindowElement(GObject.GObject):
    '''
    Main Window Element.

    :param wtree: Widget for a tree of widget objects
    :type wtree: :class:`Gtk.Widget`
    :param config: Configuration data
    :type config: :class:`DratsConfig`
    :param prefix: Prefix for the widget name lookups, default None
    :type prefix: str
    '''

    def __init__(self, wtree, config, prefix=None):
        self._prefix = prefix
        if not self._prefix:
            self._prefix = ''
        self._wtree = wtree
        self._config = config

        GObject.GObject.__init__(self)

    def _get_widget(self, name):
        '''
        Get Widget Internal.

        :param name: Partial name of child widget
        :type name: str
        :returns: Widget object
        :rtype: :class:`Gtk.Widget`
        '''
        full_name = "%s_%s" % (self._prefix, name)
        return self._wtree.get_object(full_name)

    def reconfigure(self):
        '''Reconfigure.'''


class MainWindowTab(MainWindowElement):
    '''
    Main Window Tab.

    :param wtree: Window object
    :type wtree: :class:`Gtk.Widget`
    :param config: Configuration data
    :type config: :class:`DratsConfig`
    :param window: Mainwindow window widget, Default None
    :type: window: :class:`Gtk.ApplicationWindow`
    :param prefix: Prefix for lookups, Default None
    :type prefix: str
    '''

    def __init__(self, wtree, config, window=None, prefix=None):
        MainWindowElement.__init__(self, wtree, config, prefix)
        self.window = window
        self._notebook = wtree.get_object('main_tabs')
        self._menu_tab = wtree.get_object("tab_label_%s" % prefix)
        self._tab_label = None
        self._selected = None
        if self._menu_tab:
            menu_label = self._notebook.get_menu_label_text(self._menu_tab)
            # The menu_label text set is set by glade.
            # The tab_label is set for display.
            self._notebook.set_tab_label_text(self._menu_tab, menu_label)
            self._tab_label = self._notebook.get_tab_label(self._menu_tab)

    def reconfigure(self):
        '''Reconfigure.'''

    def selected(self):
        '''Selected.'''
        self._selected = True
        self._unnotice()

    def deselected(self):
        '''Deselected.'''
        self._selected = False

    def _notice(self):
        self.emit("notice")
        if self._selected:
            return

        if self._tab_label:
            text = self._tab_label.get_text()
            self._tab_label.set_markup("<span color='blue'>%s</span>" % text)

    def _unnotice(self):
        if self._tab_label:
            text = self._tab_label.get_text()
            self._tab_label.set_markup(text)
