#!/usr/bin/python
#
# Copyright 2009 Dan Smith <dsmith@danplanet.com>
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

#importing printlog() wrapper
from ..debug import printlog

import re

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import GObject

from d_rats import inputdialog, miscwidgets
from d_rats import signals

STATION_REGEX = "^[A-Z0-9- /_]+$"

def ask_for_confirmation(question, parent=None):
    d = Gtk.MessageDialog(buttons=Gtk.ButtonsType.YES_NO,
                          parent=parent,
                          message_format=question)
    r = d.run()
    d.destroy()

    return r == Gtk.ResponseType.YES

def display_error(message, parent=None):
    d = Gtk.MessageDialog(buttons=Gtk.ButtonsType.OK,
                          parent=parent,
                          message_format=message)
    r = d.run()
    d.destroy()

    return r == Gtk.ResponseType.OK

def prompt_for_station(_station_list, config, parent=None):
    station_list = [str(x) for x in _station_list]
    port_list = []
    for i in config.options("ports"):
        enb, port, _rate, _sniff, _raw, name = config.get("ports", i).split(",")
        if enb == "True":
            port_list.append(name)

    defsta = defprt = ""
    if station_list:
        defsta = str(station_list[0])
    if port_list:
        defprt = port_list[0]

    port_list.sort()
    station_list.sort()

    station = miscwidgets.make_choice(station_list, True, defsta)
    port = miscwidgets.make_choice(port_list, False, defprt)

    d = inputdialog.FieldDialog(title=_("Enter destination"), parent=parent)
    d.add_field(_("Station"), station)
    d.add_field(_("Port"), port)
    station.get_child().set_activates_default(True)

    while True:
        res = d.run()
        if res != Gtk.ResponseType.OK:
            break
        s = station.get_active_text().upper()
        if "@" in s:
            display_error(_("You must enter a station callsign.  " +
                            "You cannot use an email address here"), d)
            continue
        elif not re.match(STATION_REGEX, s):
            display_error(_("Invalid character in callsign"), d)
            continue
        break

    p = port.get_active_text()
    d.destroy()
    if res == Gtk.ResponseType.OK:
        return s, p
    else:
        return None, None

def prompt_for_string(message, parent=None, orig=""):
    d = Gtk.MessageDialog(buttons=Gtk.ButtonsType.OK_CANCEL,
                          parent=parent,
                          message_format=message)
    e = Gtk.Entry()
    e.set_text(orig)
    e.show()
    d.vbox.pack_start(e, 1, 1, 1)

    r = d.run()
    d.destroy()

    if r == Gtk.RESPONSE_OK:
        return e.get_text()
    else:
        return None

def set_toolbar_buttons(config, tb):
    tbsize = config.get("prefs", "toolbar_button_size")
    if tbsize == _("Default"):
        tb.unset_style()
        tb.unset_icon_size()
    elif tbsize == _("Small"):
        tb.set_style(Gtk.ToolbarStyle.ICONS)
        tb.set_icon_size(Gtk.IconSize.SMALL_TOOLBAR)
    elif tbsize == _("Large"):
        tb.set_style(Gtk.ToolbarStyle.BOTH)
        tb.set_icon_size(Gtk.IconSize.LARGE_TOOLBAR)

class MainWindowElement(GObject.GObject):
    def __init__(self, wtree, config, prefix):
        self._prefix = prefix
        self._wtree = wtree
        self._config = config

        GObject.GObject.__init__(self)

    def _getw(self, *names):
        widgets = []

        for _name in names:
            name = "%s_%s" % (self._prefix, _name)
            widgets.append(self._wtree.get_object(name))

        return tuple(widgets)

    def reconfigure(self):
        pass

class MainWindowTab(MainWindowElement):
    def __init__(self, wtree, config, prefix):
        MainWindowElement.__init__(self, wtree, config, prefix)
        self._prefix = prefix
        self._notebook = wtree.get_object('main_tabs')
        self._menutab = wtree.get_object("tab_label_%s" % prefix)
        if self._menutab:
            self._tablabel = self._notebook.get_menu_label(self._menutab)
        else:
            self._tablabel = None
        self._selected = False

    def reconfigure(self):
        pass

    def selected(self):
        self._selected = True
        self._unnotice()

    def deselected(self):
        self._selected = False

    def _notice(self):
        self.emit("notice")
        if self._selected:
            return

        text = self._tablabel.get_text()
        self._tablabel.set_markup("<span color='blue'>%s</span>" % text)

    def _unnotice(self):
        text = self._tablabel.get_text()
        self._tablabel.set_markup(text)

