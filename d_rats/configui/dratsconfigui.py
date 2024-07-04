# File: configui/dratsconfigui

'''D-Rats Configuration Module.'''

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


import logging
import configparser

import gi  # type: ignore # Needed for pylance on Windows.
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk        # type: ignore
from gi.repository import GObject    # type: ignore

if not '_' in locals():
    import gettext
    _ = gettext.gettext

from .dratsappearancepanel import DratsAppearancePanel
from .dratschatpanel import DratsChatPanel
from ..dratsconfig import DratsConfig
from .dratsemailaccesspanel import DratsEmailAccessPanel
from .dratsgpspanel import DratsGPSPanel
from .dratsgpsexportpanel import DratsGPSExportPanel
from .dratsinemailpanel import DratsInEmailPanel
from .dratsmappanel import DratsMapPanel
from .dratsmessagepanel import DratsMessagePanel
from .dratsnetworkpanel import DratsNetworkPanel
from .dratsoutemailpanel import DratsOutEmailPanel
from .dratspathspanel import DratsPathsPanel
from .dratsprefspanel import DratsPrefsPanel
from .dratsradiopanel import DratsRadioPanel
from .dratssoundpanel import DratsSoundPanel
from .dratstcpincomingpanel import DratsTCPIncomingPanel
from .dratstcpoutgoingpanel import DratsTCPOutgoingPanel
from .dratstransferspanel import DratsTransfersPanel

from .config_tips import get_tip


class DratsConfigUI(Gtk.Dialog):
    '''
    D-Rats Configuration UI.

    :param config: Configuration data, default DratsConfig()
    :type config: :class:`DratsConfig`
    :param parent: Parent object, default None
    :type parent: :class:`Gtk.Widget`
    '''
    logger = logging.getLogger("DratsConfigUI")
    config = DratsConfig()

    def __init__(self, config=None, parent=None):
        if config:
            self._set_config(config)
        Gtk.Dialog.__init__(self, parent=parent)
        self.set_title(_("Config"))
        self.add_button(_("Save"), Gtk.ResponseType.OK)
        self.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        self.panels = {}
        # self.tips = Gtk.Tooltips()
        self.build_ui()
        self.set_default_size(800, 400)

    @classmethod
    def _set_config(cls, config):
        cls.config = config

    @staticmethod
    def show_config(parent=None):
        '''
        Show.

        :returns: True if the result is ok.
        :rtype: bool
        '''
        drats_ui = DratsConfigUI(parent=parent)
        # pylint: disable=no-member
        result = drats_ui.run()
        print("Config.py:DratsConfigUI.show_config %s" % result)
        if result == Gtk.ResponseType.OK:
            print("Config.py:DratsConfigUI.show_config - saving")
            drats_ui.save()
            DratsConfig().save()
        drats_ui.destroy()

        return result == Gtk.ResponseType.OK

    def mouse_event(self, view, event):
        '''
        Mouse Event.

        :param view: View object
        :type view: :class:`Gtk.TreeView`
        :param event: Mouse event
        :type event: :class:`Gtk.EventButton`
        '''
        x_coord, y_coord = event.get_coords()
        path = view.get_path_at_pos(int(x_coord), int(y_coord))
        if path:
            view.set_cursor_on_cell(path[0], None, None, False)

        (store, iter_val) = view.get_selection().get_selected()
        selected, = store.get(iter_val, 0)

        for value in self.panels.values():
            value.hide()
        self.panels[selected].show()

    def move_cursor(self, view, _step, _direction):
        '''
        Move Cursor.

        :param view: View to move cursor on
        :type view: :class:`Gtk.TreeView`
        :param _step: Granularity of the move, unused
        :type _step: :class:`GtkMovementStep`
        :param _direction: Direction of move, unused
        :type _direction: int
        '''
        (store, _iter) = view.get_selection().get_selected()
        selected, = store.get(iter, 0)

        for value in self.panels.values():
            value.hide()
        self.panels[selected].show()

    def build_ui(self):
        '''Build UI.'''
        hbox = Gtk.Box.new(orientation=Gtk.Orientation.HORIZONTAL,
                           spacing=2)

        self.__store = Gtk.TreeStore(GObject.TYPE_STRING, GObject.TYPE_STRING)
        self.__tree = Gtk.TreeView.new_with_model(self.__store)

        hbox.pack_start(self.__tree, 0, 0, 0)
        self.__tree.set_size_request(150, -1)
        self.__tree.set_headers_visible(False)
        rend = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn(None, rend, text=1)
        self.__tree.append_column(col)
        self.__tree.show()
        self.__tree.connect("button_press_event", self.mouse_event)
        self.__tree.connect_after("move-cursor", self.move_cursor)

        def add_panel(panel, section, label, parent=None, dialog=None):
            '''
            Add Config Panels.

            :param panel: Panel Class
            :type panel: :class:`dratspanel.DratsPanel`
            :param section: Section internal name
            :type section: str
            :param label: Section Label to be displayed
            :type label: str
            :param parent: Parent Widget
            :type parent: :class:`Gtk.TreeIter`
            :param dialog: D-Rats Config UI Dialog
            :type dialog: :class:`config.DratsConfigUI`
            :returns: :obj:`GtkTreeiter` for inserted row
            :rtype: :class:`GtkTreeiter`
            '''
            new_panel = panel(dialog=dialog)
            new_panel.show()
            scroll_w = Gtk.ScrolledWindow()
            scroll_w.set_policy(Gtk.PolicyType.AUTOMATIC,
                                Gtk.PolicyType.AUTOMATIC)
            scroll_w.add(new_panel)
            hbox.pack_start(scroll_w, 1, 1, 1)

            self.panels[section] = scroll_w

            for val in new_panel.vals:
                val.set_tooltip_text(get_tip(val.vsec, val.vname))
                # pylint# disable=bare-except
                #except:
                #    self.logger.info("Could not add tool tip %s to %s type %s",
                #                     get_tip(val.vsec, val.vname),
                #                     val.vname,
                #                     type(val),
                #                     exc_info=True)

            return self.__store.append(parent, row=(section, label))

        prefs = add_panel(panel=DratsPrefsPanel,
                          section="prefs", label=_("Preferences"))
        add_panel(panel=DratsPathsPanel, section="paths", label=_("Paths"),
                  parent=prefs, dialog=self)
        add_panel(panel=DratsMapPanel, section="maps", label=_("Maps"),
                  parent=prefs, dialog=self)
        add_panel(panel=DratsGPSPanel, section="gps", label=_("GPS config"),
                  parent=prefs, dialog=self)
        add_panel(panel=DratsGPSExportPanel, section="gpsexport",
                  label=_("Export GPS messages"), parent=prefs, dialog=self)
        add_panel(panel=DratsAppearancePanel, section="appearance",
                  label=_("Appearance"), parent=prefs)
        add_panel(panel=DratsChatPanel, section="chat", label=_("Chat"),
                  parent=prefs)
        add_panel(panel=DratsSoundPanel, section="sounds", label=_("Sounds"),
                  parent=prefs)

        add_panel(panel=DratsMessagePanel, section="messages",
                  label=_("Messages"))

        radio = add_panel(panel=DratsRadioPanel, section="radio",
                          label=_("Radio"))
        add_panel(panel=DratsTransfersPanel, section="transfers",
                  label=_("Transfers"), parent=radio)

        network = add_panel(panel=DratsNetworkPanel, section="network",
                            label=_("Network"))
        add_panel(panel=DratsTCPIncomingPanel, section="tcpin",
                  label=_("TCP Gateway"), parent=network)
        add_panel(panel=DratsTCPOutgoingPanel, section="tcpout",
                  label=_("TCP Forwarding"), parent=network)
        add_panel(panel=DratsOutEmailPanel, section="smtp",
                  label=_("Outgoing Email"), parent=network)
        add_panel(panel=DratsInEmailPanel, section="email",
                  label=_("Email Accounts"), parent=network)
        add_panel(panel=DratsEmailAccessPanel, section="email_ac",
                  label=_("Email Access"), parent=network)

        self.panels["prefs"].show()

        hbox.show()
        # pylint: disable=no-member
        self.vbox.pack_start(hbox, 1, 1, 1)

        self.__tree.expand_all()

    def save(self):
        '''Save.'''
        for widget in self.config.widgets:
            widget.save()


def main():
    '''Main package for testing.'''
    # pylint: disable=import-outside-toplevel
    import sys
    sys.path.insert(0, ".")

    logging.basicConfig(level=logging.INFO)

    # Each class should have their own logger.
    logger = logging.getLogger("config_test")

    logger.info("sys.path=%s", sys.path)
    # mm: fn = "/home/dan/.d-rats/d-rats.config"
    filename = "d-rats.config"

    parser = configparser.ConfigParser()
    parser.read(filename)
    parser.widgets = []

    config = DratsConfigUI(config=parser)
    # pylint: disable=no-member
    if config.run() == Gtk.ResponseType.OK:
        config.save()
        logger.info("run config was saved ")
    else:
        logger.info("run config was not saved.")

if __name__ == "__main__":
    main()
