# File: configui/dratsradiopanel.py

'''D-Rats Radio Panel Module.'''

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
import os

import gi  # type: ignore # Needed for pylance on Windows.
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk        # type: ignore
from gi.repository import GObject    # type: ignore

if not '_' in locals():
    import gettext
    _ = gettext.gettext

from .dratspanel import DratsPanel
from .dratslistconfigwidget import DratsListConfigWidget
from ..dplatform import Platform
from ..utils import combo_select


def load_portspec(wtree, portspec, info, name):
    '''
    Load in a port specification.

    :param wtree: Gtk Builder object
    :type wtree: :class:`Gtk.Builder`
    :param portspec: Port specification object
    :type portspec: str
    :param info: Port information
    :type info: str
    :param name: Port name
    :type name: str
    '''
    name_widget = wtree.get_object("name")
    name_widget.set_text(name)
    name_widget.set_sensitive(False)

    tsel = wtree.get_object("type")
    if portspec.startswith("net:"):
        tsel.set_active(1)
        _net, host, port = portspec.split(":")
        wtree.get_object("net_host").set_text(host)
        wtree.get_object("net_port").set_value(int(port))
        wtree.get_object("net_pass").set_text(info)
    elif portspec.startswith("tnc"):
        tsel.set_active(2)
        if len(portspec.split(":")) == 3:
            _tnc, port, tncport = portspec.split(":", 2)
            path = ""
        else:
            _tnc, port, tncport, path = portspec.split(":", 3)
        wtree.get_object("tnc_port").get_child().set_text(port)
        wtree.get_object("tnc_tncport").set_value(int(tncport))
        combo_select(wtree.get_object("tnc_rate"), info)
        wtree.get_object("tnc_ax25path").set_text(path.replace(";", ","))
        if portspec.startswith("tnc-ax25"):
            wtree.get_object("tnc_ax25").set_active(True)
    elif portspec.startswith("agwpe:"):
        tsel.set_active(4)
        _agw, addr, port = portspec.split(":")
        wtree.get_object("agw_addr").set_text(addr)
        wtree.get_object("agw_port").set_value(int(port))
    else:
        tsel.set_active(0)
        wtree.get_object("serial_port").get_child().set_text(portspec)
        combo_select(wtree.get_object("serial_rate"), info)


# pylint wants a max of 15 local variables
# pylint wants a max of 12 branches
# pylint wants a max of 50 statements
# pylint: disable=too-many-locals,too-many-branches,too-many-statements
def prompt_for_port(portspec=None, info=None, pname=None):
    '''
    Prompt for port.

    :param portspec: portspec object, default None
    :type portspec: str
    :param info: Port information, default None
    :type info: str
    :param pname: Port name, default None
    :type pname: str
    :returns: portspec or (None, None, None)
    :rtype: tuple[str, str, str]
    '''
    wtree = Gtk.Builder()
    platform = Platform.get_platform()
    path = os.path.join(platform.sys_data(),
                        "ui/addport.glade")
    wtree.add_from_file(path)

    ports = platform.list_serial_ports()

    sportsel = wtree.get_object("serial_port")
    tportsel = wtree.get_object("tnc_port")
    sportlst = sportsel.get_model()
    tportlst = tportsel.get_model()
    sportlst.clear()
    tportlst.clear()

    for port in ports:
        sportlst.append((port, ""))
        tportlst.append((port, ""))

    if ports:
        sportsel.set_active(0)
        tportsel.set_active(0)

    sratesel = wtree.get_object("serial_rate")
    tratesel = wtree.get_object("tnc_rate")
    tprotsel = wtree.get_object("tnc_ax25")
    tnc_path = wtree.get_object("tnc_ax25path")
    tprotsel.connect("toggled",
                     lambda b: tnc_path.set_sensitive(b.get_active()))

    sratesel.set_active(3)
    tratesel.set_active(3)

    netaddr = wtree.get_object("net_host")
    netport = wtree.get_object("net_port")
    netpass = wtree.get_object("net_pass")

    agwaddr = wtree.get_object("agw_addr")
    agwport = wtree.get_object("agw_port")
    agwport.set_value(8000)

    menutabs = []
    for _i in range(5):
        menutabs.append({})

    menutabs[0]['descrip'] = _("A D-STAR radio connected to a serial port")
    menutabs[1]['descrip'] = _("A network link to a ratflector instance")
    menutabs[2]['descrip'] = _("A KISS-mode TNC connected to a serial port")
    menutabs[3]['descrip'] = _("A locally-attached dongle")
    menutabs[4]['descrip'] = _("A TNC attached to an AGWPE server")

    def chg_type(tsel, tabs, desc):
        '''
        Change type handler.

        :param tsel: Port type selection
        :type tsel: :class:`Gtk.ComboBoxText
        :param tabs: Menu tab widget
        :type tabs: :class:`Gtk.Notebook`
        :param desc: Description widget
        :type desc: :class:`Gtk.Label`
        '''
        active = tsel.get_active()
        if active < 0:
            active = 0
            tsel.set_active(0)
        logger = logging.getLogger("Configure_prompt_for_port_chg_type")
        logger.info("Changed to %s", tsel.get_active_text())

        tabs.set_current_page(active)

        desc.set_markup("<span fgcolor='blue'>%s</span>" %
                        menutabs[active]['descrip'])

    name = wtree.get_object("name")
    desc = wtree.get_object("typedesc")
    ttncport = wtree.get_object("tnc_tncport")
    tabs = wtree.get_object("editors")
    tabs.set_show_tabs(False)
    tsel = wtree.get_object("type")
    tsel.set_active(0)
    tsel.connect("changed", chg_type, tabs, desc)

    if portspec:
        load_portspec(wtree, portspec, info, pname)
    elif pname is False:
        name.set_sensitive(False)

    add_port = wtree.get_object("addport")

    chg_type(tsel, tabs, desc)
    run_result = add_port.run()

    active = tsel.get_active()
    if active == 0:
        portspec = sportsel.get_active_text(), sratesel.get_active_text()
    elif active == 1:
        portspec = "net:%s:%i" % (netaddr.get_text(), netport.get_value()), \
            netpass.get_text()
    elif active == 2:
        if tprotsel.get_active():
            digi_path = tnc_path.get_text().replace(",", ";")
            portspec = "tnc-ax25:%s:%i:%s" % (tportsel.get_active_text(),
                                              ttncport.get_value(),
                                              digi_path), \
                                              tratesel.get_active_text()
        else:
            portspec = "tnc:%s:%i" % (tportsel.get_active_text(),
                                      ttncport.get_value()), \
                                      tratesel.get_active_text()
    elif active == 3:
        portspec = "dongle:", ""
    elif active == 4:
        portspec = "agwpe:%s:%i" % (agwaddr.get_text(), agwport.get_value()), ""

    portspec = (name.get_text(),) + portspec
    add_port.destroy()

    if run_result == Gtk.ResponseType.APPLY:
        return portspec
    return None, None, None


class DratsRadioPanel(DratsPanel):
    '''
    D-Rats Radio Panel.

    :param dialog: D-Rats Config UI Dialog
    :type dialog: :class:`config.DratsConfigUI`
    '''

    INITIAL_ROWS = 3
    logger = logging.getLogger("DratsRadioPanel")

    # pylint: disable=unused-argument
    def __init__(self, dialog=None):
        DratsPanel.__init__(self)

        cols = [(GObject.TYPE_STRING, "ID"),
                (GObject.TYPE_BOOLEAN, _("Enabled")),
                (GObject.TYPE_STRING, _("Port")),
                (GObject.TYPE_STRING, _("Settings")),
                (GObject.TYPE_BOOLEAN, _("Sniff")),
                (GObject.TYPE_BOOLEAN, _("Raw Text")),
                (GObject.TYPE_STRING, _("Name"))]

        _lab = Gtk.Label.new(_("Configure data paths below."
                               "  This may include any number of"
                               " serial-attached radios and"
                               " network-attached proxies."))

        port_config_list = DratsListConfigWidget(section="ports")

        def make_key(vals):
            return vals[5]

        list_widget = port_config_list.add_list(cols, make_key)
        add = Gtk.Button.new_with_label(_("Add"))
        add.connect("clicked", self.but_add, list_widget)
        self.mod = Gtk.Button.new_with_label(_("Edit"))
        self.mod.set_sensitive(False)
        self.mod.connect("clicked", self.but_mod, list_widget)
        self.rem = Gtk.Button.new_with_label(_("Remove"))
        self.rem.set_sensitive(False)
        self.rem.connect("clicked", self.but_rem, list_widget)
        list_widget.treeview.connect("cursor-changed", self.cursor_changed)

        port_config_list.set_sort_column(6)

        self.make_view(_("Paths"), port_config_list, add, self.mod, self.rem)

        list_widget.set_resizable(1, False)

    def make_view(self, title, *widgets):
        '''
        Make View.

        :param _title: Title of view, Unused
        :type _title: str
        :param widgets: Widgets to place in view
        :type widgets: tuple[:class:`Gtk.Widget`]
        '''
        # self.attach(widgets[0], 0, 2, 0, 1)
        widgets[0].show()
        widget_height = max(widgets[0].get_preferred_height())
        self.attach(widgets[0], 0, 0, 3, widget_height)

        if len(widgets) > 1:
            box = Gtk.Box.new(orientation=Gtk.Orientation.HORIZONTAL,
                              spacing=2)
            box.set_homogeneous(True)

            for i in widgets[1:]:
                box.pack_start(i, 0, 0, 0)
                i.show()

            box.show()
            box_height = max(box.get_preferred_height())
            # self.attach(box, 0, 2, 1, 2, yoptions=Gtk.AttachOptions.SHRINK)
            self.attach_next_to(box, widgets[0], Gtk.PositionType.BOTTOM,
                                1, box_height)

    def cursor_changed(self, _tree_view):
        '''
        Cursor Changed Handler.

        Triggered when the cursor for the row get changed.
        :param _tree_view: List box with data, Unused
        :type _tree_view: `:class:Gtk.TreeView`
        '''
        self.logger.info("cursor_changed tree_view: %s",
                         type(_tree_view))
        self.mod.set_sensitive(True)
        self.rem.set_sensitive(True)

    @staticmethod
    def but_add(_button, list_widget):
        '''
        Button Add.

        :param _button: Unused
        :type _button: :class:`Gtk.Button`
        :param list_widget: list widget object
        :type list_widget: :class:`DratsListConfigWidget`
        '''
        name, port, info = prompt_for_port()
        if name:
            list_widget.set_item(name, True, port, info, False, False, name)

    def but_mod(self, _button, list_widget):
        '''
        Button Modify.

        :param _button: Unused
        :type: _button: :class:`Gtk.Button`
        :param list_widget: list widget object
        :type list_widget: :class:`DratsListConfigWidget`
        '''
        values = list_widget.get_item(list_widget.get_selected())
        self.logger.info("Values: %s", str(values))
        name, port, info = prompt_for_port(values[2], values[3], values[6])
        if name:
            list_widget.set_item(values[6], values[1], port, info, values[4],
                                 values[5], values[6])

    @staticmethod
    def but_rem(_button, list_widget):
        '''
        Button remove.

        :param _button: Unused
        :type _button: :class:`Gtk.Button`
        :param list_widget: list widget object
        :type list_widget: :class:`DratsListConfigWidget`
        '''
        list_widget.del_item(list_widget.get_selected())
