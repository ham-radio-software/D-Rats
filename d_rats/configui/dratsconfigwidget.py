# File: configui/dratsconfigwidget.py

'''Drats Configuration Widget.'''

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

import gi  # type: ignore # Needed for pylance on Windows.
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk        # type: ignore
from gi.repository import Gdk        # type: ignore

from ..config_defaults import DEFAULTS
from ..dplatform import Platform
from ..dratsconfig import DratsConfig
from ..dratsexception import LatLonEntryException
from ..latlonentry import LatLonEntry
from ..miscwidgets import make_choice
from ..filenamebox import FilenameBox
from ..utils import set_entry_hint

if not '_' in locals():
    import gettext
    _ = gettext.gettext


# pylint wants a max of 7 instance attributes
# pylint# disable=too-many-instance-attributes
class DratsConfigWidget(Gtk.Box):
    '''
    D-rats configuration Widget.

    :param section: Config file section
    :type section: str
    :param name: Name of configuration
    :type name: str
    :param have_revert: Flag if reverting is allowed, default False
    :type have_revert: bool
    '''

    logger = logging.getLogger("DratsConfigWidget")
    config = DratsConfig()

    def __init__(self, section, name=None, have_revert=False):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL,
                         spacing=2)

        self.do_not_expand = False

        self.vsec = section
        self.vname = name
        self.child_widget = None
        self._in_init = True
        self.latlon = None

        self.config.widgets.append(self)

        if not self.config.has_section(section):
            self.config.add_section(section)

        if name is not None:
            if not self.config.has_option(section, name):
                self._revert()
            else:
                self.value = self.config.get(section, name)
        else:
            self.value = None

        if have_revert:
            rbutton = Gtk.Button.new_with_label(_('Revert'))
            rbutton.connect("clicked", self._revert)
            rbutton.show()
            # pylint: disable=no-member
            self.pack_end(rbutton, 0, 0, 0)

    def _revert(self, _button=None):
        '''
        Revert button clicked handler.

        :param _button: Button widget, default None
        :type _button: :class:`Gtk.Button`
        '''
        try:
            self.value = DEFAULTS[self.vsec][self.vname]
        except KeyError:
            self.logger.info("DEFAULTS has no %s/%s", self.vsec, self.vname)
            self.value = ""

        # Nothing else to do if called from __init_()
        if self._in_init:
            return

        if not self.child_widget:
            self.logger.info("AAACK: No _widget in revert for %s/%s",
                             self.vsec, self.vname)
            return

        if isinstance(self.child_widget, Gtk.Entry):
            self.child_widget.set_text(str(self.value))
        elif isinstance(self.child_widget, Gtk.SpinButton):
            self.child_widget.set_value(float(self.value))
        elif isinstance(self.child_widget, Gtk.CheckButton):
            self.child_widget.set_active(self.value.upper() == "TRUE")
        elif isinstance(self.child_widget, FilenameBox):
            self.child_widget.set_filename(self.value)
        else:
            self.logger.info("AAACK: I don't know how to do a %s",
                             self.child_widget.__class__)

    def save(self):
        '''Save Configuration.'''
        # printlog("Config",
        #          "    : "Saving %s/%s: %s" %
        #          (self.vsec, self.vname, self.value))
        self.config.set(self.vsec, self.vname, self.value)

    def set_value(self, _value):
        '''
        Set value.

        :param _value: Value to set, unused
        :type _value: any
        '''

    def add_text(self, limit=0, hint=None):
        '''
        Add Text Entry Box.

        :param limit: limit value, default 0
        :type limit: int
        :param hint: Text hint, default None
        :type hint: str
        '''
        def changed(entry):
            '''
            Entry changed handler.

            :param entry: Entry widget
            :type entry: :class:`Gtk.Entry`
            '''
            if entry.get_text() == hint:
                self.value = ""
            else:
                self.value = entry.get_text()

        entry = Gtk.Entry()
        entry.set_max_length(limit)
        entry.connect("changed", changed)
        entry.set_text(self.value)
        entry.set_size_request(50, -1)
        entry.show()
        self.child_widget = entry

        if hint:
            set_entry_hint(entry, hint, bool(self.value))

        self.pack_start(entry, 1, 1, 1)

    def add_upper_text(self, limit=0):
        '''
        Add upper case text entry.

        :param limit: Limit of text, default 0
        :type limit: int
        '''
        def changed(entry):
            '''
            Entry changed handler.

            :param entry: Entry widget
            :type entry: :class:`Gtk.Entry`
            '''
            self.value = entry.get_text().upper()

        entry = Gtk.Entry()
        entry.set_max_length(limit)
        entry.connect("changed", changed)
        entry.set_text(self.value)
        entry.set_size_request(50, -1)
        entry.show()
        self.child_widget = entry

        self.pack_start(entry, 1, 1, 1)

    def add_pass(self, limit=0):
        '''
        Add a password entry.

        :param limit: Limit default 0
        :type limit: int
        '''
        def changed(entry):
            '''
            Entry changed handler.

            :param entry: Entry widget
            :type entry: :class:`Gtk.Entry`
            '''
            self.value = entry.get_text()

        entry = Gtk.Entry()
        entry.set_max_length(limit)
        entry.connect("changed", changed)
        entry.set_text(self.value)
        entry.set_visibility(False)
        entry.set_size_request(50, -1)
        entry.show()
        self.child_widget = entry

        self.pack_start(entry, 1, 1, 1)

    def add_combo(self, choices=None, editable=False, size=80):
        '''
        Add a combo box.

        :param choices: Choices, default None
        :type choices: list[str]
        :param editable: Flag for editable, default False
        :type editable: bool
        :param size: Size of combo box, default 80
        :type size: int
        '''
        def changed(combo_box):
            '''
            Combo Box changed handler.

            :param combo_box: Entry widget
            :type combo_box: :class:`Gtk.ComboBoxText`
            '''
            self.value = combo_box.get_active_text()

        if not choices:
            choices = []
        if self.value not in choices:
            choices.append(self.value)

        widget = make_choice(choices, editable, self.value)
        widget.connect("changed", changed)
        widget.set_size_request(size, -1)
        widget.show()
        self.child_widget = widget

        self.pack_start(widget, 1, 1, 1)

    def add_bool(self, label=None):
        '''
        Add boolean button.

        :param label: Label for button, default None
        :type label: str
        '''
        if label is None:
            label = _("Enabled")

        def toggled(check_button, conf_widget):
            '''
            Check Button toggled handler.

            :param check_button: Check button widget
            :type check_button: :class:`Gtk.CheckButton`
            :param conf_widget: Configuration widget
            :type conf_widget: :class:`DratsConfigWidget`
            '''
            conf_widget.value = str(check_button.get_active())

        button = Gtk.CheckButton.new_with_label(label)
        button.connect("toggled", toggled, self)
        button.set_active(self.value == "True")
        button.show()
        self.child_widget = button

        self.do_not_expand = True

        self.pack_start(button, 1, 1, 1)

    def add_coords(self):
        '''Add coordinates.'''
        def changed(entry, conf_widget):
            '''
            LatlonEntry changed handler.

            :param entry: Entry widget
            :type entry: :class:`latlonentry.LatLonEntry`
            :param conf_widget: Configuration Widgets
            :type conf_widget: :class:`DratsConfigWidget`
            '''
            try:
                conf_widget.value = "%3.6f" % entry.value()
            except (TypeError, LatLonEntryException) as err:
                # This exception happens while data is still being
                # entered, so setting it at debug level.
                self.logger.debug("Invalid Coords: %s", err)
                conf_widget.value = "0"

        entry = LatLonEntry()
        entry.connect("changed", changed, self)
        self.logger.info("Setting LatLon value: %s", self.value)
        entry.set_text(self.value)
        self.logger.info("LatLon text: %s", entry.get_text())
        entry.show()

        # Dirty ugly hack!
        self.latlon = entry

        self.pack_start(entry, 1, 1, 1)

    def add_numeric(self, min_val, max_val, increment, digits=0):
        '''
        Add numeric.

        :param min_val: Minimum value
        :type min_val: int
        :param max_val: Maximum value
        :type max_val: int
        :param increment: Increment for adjustments
        :type increment: int
        :param digits: Number of digits, default 0
        :type digits: int
        '''

        def value_changed(spin_button):
            '''
            SpinButton value-changed handler.

            :param spin_button: SpinButton object
            :type spin_button: :class:`Gtk.SpinButton`
            '''
            self.value = "%f" % spin_button.get_value()

        adj = Gtk.Adjustment.new(float(self.value), min_val, max_val,
                                 increment, increment, 0)
        button = Gtk.SpinButton()
        button.set_adjustment(adj)
        button.set_digits(digits)
        button.connect("value-changed", value_changed)
        button.show()
        self.child_widget = button

        self.pack_start(button, 1, 1, 1)

    def add_color(self):
        '''Add Color.'''
        def color_set(color_button):
            '''
            Color Button color-set handler.

            :param color_button: Color Button widget
            :type color_button: :class:`Gtk.ColorButton
            '''
            rgba = color_button.get_rgba()
            self.value = rgba.to_string()

        button = Gtk.ColorButton()
        if self.value:
            rgba = Gdk.RGBA()
            if rgba.parse(self.value):
                button.set_rgba(rgba)
        button.connect("color-set", color_set)
        button.show()

        self.pack_start(button, 1, 1, 1)

    def add_font(self):
        '''Add font.'''
        def font_set(font_button):
            '''
            FontButton font-set handler.

            :param font_button: Font Button Widget
            :type font_button: :class:`Gtk.FontButton`
            '''
            self.value = font_button.get_font()

        button = Gtk.FontButton()
        if self.value:
            button.set_font(self.value)
        button.connect("font-set", font_set)
        button.show()

        self.pack_start(button, 1, 1, 1)

    def add_path(self):
        '''Add path.'''
        def filename_changed(box):
            '''
            FilenameBox filename-changed box.

            :param box: FilenameBox widget
            :type box: :class:`filenamebox.FilenameBox`
            '''
            self.value = box.get_filename()

        fname_box = FilenameBox(find_dir=True)
        fname_box.set_filename(self.value)
        fname_box.connect("filename-changed", filename_changed)
        fname_box.show()
        self.child_widget = fname_box

        self.pack_start(fname_box, 1, 1, 1)

    def add_sound(self):
        '''Add Sound.'''
        def filename_changed(box):
            '''
            FilenameBox filename-changed box.

            :param box: FilenameBox widget
            :type box: :class:`filenamebox.FilenameBox`
            '''
            self.value = box.get_filename()

        def test_sound(_button):
            '''
            Test Sound Button clicked handler.

            :param _button: Button widget
            :type _button: :class:`Gtk.Button`
            '''
            self.logger.info("Testing playback of %s", self.value)
            platform_info = Platform.get_platform()
            platform_info.play_sound(self.value)

        fname_box = FilenameBox(find_dir=False)
        fname_box.set_filename(self.value)
        fname_box.connect("filename-changed", filename_changed)
        fname_box.show()

        button = Gtk.Button.new_with_label(_("Test"))
        button.connect("clicked", test_sound)
        button.show()

        box = Gtk.Box.new(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        box.show()
        box.pack_start(fname_box, 1, 1, 1)
        box.pack_start(button, 0, 0, 0)

        self.pack_start(box, 1, 1, 1)
