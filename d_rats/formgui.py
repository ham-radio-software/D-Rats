#
'''Form GUI'''
# pylint wants only 1000 lines per module
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

import base64
from configparser import NoOptionError
import logging
import os
import sys
import tempfile
import time
import zlib

from lxml import etree


import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
# from gi.repository import Gdk
from gi.repository import GObject

if not '_' in locals():
    import gettext
    _ = gettext.gettext


MODULE_LOGGER = logging.getLogger("Formgui")

from .miscwidgets import make_choice, KeyedListWidget
from .utils import run_or_error
from .ui.main_common import ask_for_confirmation
from . import dplatform
from . import spell

# Not currently used
# TEST = """
# <xml>
#  <form id="testform">
#    <title>Test Form</title>
#    <field id="foo">
#      <caption>Name</caption>
#      <entry type="text">Foobar</entry>
#    </field>
#    <field id="bar">
#      <entry type="multiline"/>
#    </field>
#    <field id="baz">
#      <caption>Is this person okay?</caption>
#      <entry type="toggle">True</entry>
#    </field>
#  </form>
# </xml>
# """

XML_ESCAPES = [("<", "&lt;"),
               (">", "&gt;"),
               ("&", "&amp;"),
               ('"', "&quot;"),
               ("'", "&apos;")]

RESPONSE_SEND = -900
RESPONSE_SAVE = -901
RESPONSE_REPLY = -902
RESPONSE_DELETE = -903
RESPONSE_SEND_VIA = -904


class FormguiException(Exception):
    '''Generic Formgui Exception.'''


class FormguiFileException(FormguiException):
    '''Formgui File Exception.'''


class FormguiFileNotValid(FormguiFileException):
    '''Form file is not valid Exception.'''


class FormguiFileMultipleForms(FormguiFileException):
    '''Form file has multiple forms Exception.'''


class FormguiFileMultipleTitles(FormguiFileException):
    '''Form file has multiple titles Exception.'''


class FormguiFileMultipleLogos(FormguiFileException):
    '''Form file has multiple logos Exception.'''


class FormguiFileMultipleIds(FormguiFileException):
    '''Form file has multiple Ids Exception.'''


class FormguiFileMultipleAtts(FormguiFileException):
    '''Form file has multiple Attachment Exception.'''


class FormguiFileDuplicateAtt(FormguiFileException):
    '''Duplicate Attachment Exception.'''


class FormguiFileInvalidAtt(FormguiFileException):
    '''Invalid Attachment Exception.'''


# wb8tyw: Style is deprecated in favor of Gtk.StyleContext.
# At startup, the sets are empty.   Need to figure out what this is used for.
# style = Gtk.Style()
# accessing these members triggers GTK "CRITICAL stack overflow protection"
# for style_index in [style.fg, style.bg, style.base]:
#    print('-Debug Style Dump-----')
#    print(style_index)
#    print('-------')
#    if Gtk.StateFlags.NORMAL in style_index:
#        if Gtk.stateFlags.INSENSITIVE in style_index:
#            style_index[Gtk.StateFlags.INSENSITIVE] = \
#                style_index[Gtk.StateFlags.NORMAL]
# STYLE_BRIGHT_INSENSITIVE = style
# del style
# del style_index


def xml_escape(string):
    '''
    XML escape.

    :param string: String to add XML escapes
    :type: str
    :returns: String with data escaped to add to XML element
    :rtype: str
    '''
    data = {}
    for char, esc in XML_ESCAPES:
        data[char] = esc

    out = ""
    for char in string:
        out += data.get(char, char)

    return out


def xml_unescape(string):
    '''
    XML unescape.

    :param string: string containing XML
    :type string: str
    :returns: string with excapes replaced with original text
    :rtype: str
    '''
    data = {}
    for char, esc in XML_ESCAPES:
        data[esc] = char

    out = ""
    string_index = 0
    while string_index < len(string):
        if string[string_index] != "&":
            out += string[string_index]
            string_index += 1
        else:
            try:
                semi = string[string_index:].index(";") + string_index + 1
            except (ValueError, IndexError):
                MODULE_LOGGER.info("XML Error: & with no ;")
                string_index += 1
                continue

            esc = string[string_index:semi]

            if not esc:
                MODULE_LOGGER.info("No escape: %i:%i", string_index, semi)
                string_index += 1
                continue

            if string[string_index:semi] in data:
                out += data[esc]
            else:
                MODULE_LOGGER.info("XML Error: No such escape: `%s'", esc)
            string_index += len(esc)
    return out


# pylint wants at least 2 public methods
# pylint: disable=too-few-public-methods
class FormWriter():
    '''Form Writer.'''

    @staticmethod
    def write(formxml, outfile):
        '''
        Write.

        :param formxml: String with form in XML
        :type formxml: str
        :param outfile: File to write out
        :type outfile: str
        '''
        doc = etree.fromstring(formxml)
        doc.write(outfile, pretty_print=True)


class HTMLFormWriter(FormWriter):
    '''
    HTML Form Writer.

    :param form_type: String for type of form
    :type form_type: str
    :param xsl_dir: Directory path for xsl file
    :type xsl_dir: str
    '''

    def __init__(self, form_type, xsl_dir):
        self.logger = logging.getLogger("HTMLFormwriter")
        self.xslpath = os.path.join(xsl_dir, "%s.xsl" % form_type)
        if not os.path.exists(self.xslpath):
            self.xslpath = os.path.join(xsl_dir, "default.xsl")

    def write_doc(self, doc, outfile):
        '''
        Write Document.

        :param doc: Form document
        :type doc: :class:`ElementTree`
        :param outfile: File name to write
        :type outfile: str
        '''
        self.logger.info("Writing to %s", outfile)
        styledoc = etree.parse(self.xslpath)
        style_sheet = etree.XSLT(styledoc)
        result = style_sheet(doc)
        result.write(outfile, pretty_print=True)

    def write_string(self, doc):
        '''
        Write String.

        :param doc: Form Document
        :type doc: :class:`ElementTree`
        :returns: element written as a string
        :rtype: str
        '''
        styledoc = etree.parse(self.xslpath)
        style_sheet = etree.XSLT(styledoc)
        result = style_sheet(doc)
        return etree.tostring(result, pretty_print=True).decode()


# pylint wants only 7 instance attributes
# pylint: disable=too-many-instance-attributes
class FieldWidget():
    '''
    Field Widget.

    :param node: Form data elements
    :type node: :class:ElementTree
    :param config: Configuration data
    :type config: :class:`DratsConfig`
    '''

    def __init__(self, node, config):

        self.logger = logging.getLogger("ToggleWidget")
        self.node = node
        self.config = config
        self.caption = "Untitled Field"
        self.ident = "unknown"
        self.type = (self.__class__.__name__.replace("Widget", "")).lower()
        self.widget = None
        self.vertical = False
        self.nolabel = False

    def set_caption(self, caption):
        '''
        Set caption.

        :param caption: Caption to set
        :type caption: str
        '''
        self.caption = caption

    def set_id(self, ident):
        '''
        Set identity.

        :param ident: Identity of widget
        :type ident: str
        '''
        self.ident = ident

    def make_container(self):
        '''
        Make Container.

        :returns: widget object
        :rtype: :class:`Gtk.Widget`
        '''
        return self.widget

    def get_widget(self):
        '''
        Get widget.

        :returns: Widget of container
        :rtype: :class:`Gtk.Widget`
        '''
        return self.make_container()

    def get_value(self):
        '''
        Get value template

        :returns: None
        :rtype: None
        '''
        self.logger.info("get_value: template called")

    def set_value(self, value):
        '''
        Set value.

        :param value: Not used
        :type value: str
        '''

    def update_node(self):
        '''Update node.'''
        value = xml_escape(self.get_value())
        if value:
            self.node.text = value

    def set_editable(self, editable):
        '''
        Set editable.

        :param editable: Boolean for editable status
        :type editable: bool
        '''
        if self.widget:
            self.widget.set_sensitive(editable)
            # Gtk 3 ignors set_style, have to learn a bit on
            # how to use css to replace this function.
            # style_context = self.widget.get_style_context()
            # self.widget.set_style(STYLE_BRIGHT_INSENSITIVE)


class TextWidget(FieldWidget):
    '''
    Text Widget.

    :param node: Form data for text
    :type node: :class:`ElementTree`
    :param config: Configuration data
    :type config: :class:`DratsConfig`
    '''

    def __init__(self, node, config):
        FieldWidget.__init__(self, node, config)

        text = ""
        # if node.text and node.getchildren():
        if node.text:
            text = xml_unescape(node.text.strip())

        self.widget = Gtk.Entry()
        self.widget.set_text(text)
        self.widget.show()

    def get_value(self):
        '''
        Get value.

        :returns: text
        :rtype: str
        '''
        return self.widget.get_text()

    def set_value(self, value):
        '''
        Set value.

        :param value: Text to set
        :type value: str
        '''
        self.widget.set_text(value)


class ToggleWidget(FieldWidget):
    '''
    Toggle Widget.

    :param node: Form data for toggling
    :type node: :class:`ElementTree`
    :param config: Configuration data
    :type config: :class:`DratsConfig`
    '''

    def __init__(self, node, config):
        FieldWidget.__init__(self, node, config)

        self.logger = logging.getLogger("ToggleWidget")
        status = False
        if node.text:
            text = node.text.strip().lower()
            if text in ['true', '1', 'yes', 'on', 'y']:
                status = True

        self.widget = Gtk.CheckButton.new_with_label(_("Yes"))
        self.widget.set_active(status)
        self.widget.show()

    def get_value(self):
        '''
        Get value.

        :returns: Boolean state in text
        :rtype: str
        '''
        return str(self.widget.get_active())


class MultilineWidget(FieldWidget):
    '''
    Multi Line Widget

    :param node: Form multiline text data
    :type node: :class:`ElementTree`
    :param config: Configuration data
    :type config: :class:`DratsConfig`
    '''

    def __init__(self, node, config):
        FieldWidget.__init__(self, node, config)
        self.vertical = True

        text = ""
        if node.text:
            text = xml_unescape(node.text.strip())

        self.buffer = Gtk.TextBuffer()
        self.buffer.set_text(text)
        self.widget = Gtk.TextView.new_with_buffer(self.buffer)
        self.widget.show()
        self.widget.set_size_request(175, 200)
        self.widget.set_wrap_mode(Gtk.WrapMode.WORD)

        try:
            if self.config.getboolean("prefs", "check_spelling"):
                spell.prepare_TextBuffer(self.buffer)
        except AttributeError:
            pass

    def make_container(self):
        '''
        Make container

        :returns: Scrolled Window Widget
        :rtype: :class:`GtkScrolledWindow`
        '''
        scrollw = Gtk.ScrolledWindow()
        scrollw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrollw.add(self.widget)
        return scrollw

        # vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 2)
        # label = Gtk.Label.new(self.caption)
        # vbox.pack_start(label, 0, 0, 0)
        # vbox.pack_start(scrollw, 0, 0, 0)

        # label.show()
        # vbox.show()
        # scrollw.show()

        # return vbox

    def get_value(self):
        '''
        Get value.

        :returns: Multiple lines of text
        :rtype: str
        '''
        return self.buffer.get_text(self.buffer.get_start_iter(),
                                    self.buffer.get_end_iter(), True)

    def set_value(self, value):
        '''
        Set value.

        :param value: Multiple lines of text
        :type text: str
        '''
        self.buffer.set_text(value)


class DateWidget(FieldWidget):
    '''
    Date Widget.

    :param node: Form data for date
    :type node: :class:`ElementTree`
    :param config: Configuration data
    :type config: :class:`DratsConfig`
    '''

    def __init__(self, node, config):
        FieldWidget.__init__(self, node, config)
        self.logger = logging.getLogger("DateWidget")
        text = node.text
        if text:
            try:
                (day, month, year) = text.split("-", 3)
            except ValueError:
                text = None
        if not text:
            year = time.strftime("%Y")
            month = time.strftime("%b")
            day = time.strftime("%d")

        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        days = [str("%02i" % xday) for xday in range(1, 32)]
        years = [str(xyear) for xyear in range(int(year)-2, int(year)+2)]

        self.monthbox = make_choice(months, False, month)
        self.daybox = make_choice(days, False, day)
        self.yearbox = make_choice(years, False, year)

        self.widget = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 2)
        self.widget.pack_start(self.monthbox, 0, 0, 0)
        self.widget.pack_start(self.daybox, 0, 0, 0)
        self.widget.pack_start(self.yearbox, 0, 0, 0)

        self.monthbox.show()
        self.daybox.show()
        self.yearbox.show()

        self.widget.show()

    def get_value(self):
        '''
        Get value.

        :returns: Text date
        :rtype: str
        '''
        return "%s-%s-%s" % (self.daybox.get_active_text(),
                             self.monthbox.get_active_text(),
                             self.yearbox.get_active_text())


# pylint wants only 7 instance attributes
# pylint: disable=too-many-instance-attributes
class TimeWidget(FieldWidget):
    '''
    Time Widget.

    :param node: Form data for time
    :type node: :class:`ElementTree`
    :param config: Configuration data
    :type config: :class:`DratsConfig`
    '''

    def __init__(self, node, config):
        FieldWidget.__init__(self, node, config)
        self.logger = logging.getLogger("TimeWidget")
        text = ''
        if node.text:
            text = node.text.strip()
        try:
            (hours, minutes, seconds) = (int(x) for x in text.split(":", 3))
        except ValueError:
            try:
                if self.config.getboolean("prefs", "useutc"):
                    current_time = time.gmtime()
                else:
                    current_time = time.localtime()
            except AttributeError:
                current_time = time.localtime()

            hours = int(time.strftime("%H", current_time))
            minutes = int(time.strftime("%M", current_time))
            seconds = int(time.strftime("%S", current_time))

        self.hour_a = Gtk.Adjustment.new(hours, 0, 23, 1, 0, 0)
        self.min_a = Gtk.Adjustment.new(minutes, 0, 59, 1, 10, 0)
        self.sec_a = Gtk.Adjustment.new(seconds, 0, 59, 1, 10, 0)

        self.hour = Gtk.SpinButton()
        self.hour.set_adjustment(self.hour_a)
        self.min = Gtk.SpinButton()
        self.min.set_adjustment(self.min_a)
        self.sec = Gtk.SpinButton()
        self.sec.set_adjustment(self.sec_a)

        self.widget = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 2)
        self.widget.pack_start(self.hour, 0, 0, 0)
        self.widget.pack_start(self.min, 0, 0, 0)
        self.widget.pack_start(self.sec, 0, 0, 0)

        self.hour.show()
        self.min.show()
        self.sec.show()
        self.widget.show()

    def get_value(self):
        '''
        Get value.

        :returns: Time value in string format
        :rtype: str
        '''
        return "%.0f:%02.0f:%02.0f" % (self.hour_a.get_value(),
                                       self.min_a.get_value(),
                                       self.sec_a.get_value())


class NumericWidget(FieldWidget):
    '''
    Numeric Widget.

    :param node: Form data for numeric data
    :type: node: :class:`ElementTree`
    :param config: Configuration data
    :type config: :class:`DratsConfig`
    '''
    def __init__(self, node, config):
        FieldWidget.__init__(self, node, config)

        self.logger = logging.getLogger("NumericWidget")
        limit = {}
        limit['min'] = 0
        limit['max'] = 1000000.0
        initial = 0
        found_count = 0
        for attrib, value in node.items():
            if found_count >= 2:
                break
            if attrib in ('min', 'max'):
                found_count += 1
                try:
                    limit[attrib] = float(value)
                except ValueError:
                    self.logger.debug("__init__ %s was %s.",
                                      attrib, value, exc_info=True)
        if node.text:
            text = node.text.strip()
            try:
                initial = float(text)
            except ValueError:
                self.logger.debug("__init__ initial", exc_info=True)

        self.adj = Gtk.Adjustment.new(initial, limit['min'], limit['max'],
                                      1, 10, 0)
        self.widget = Gtk.SpinButton()
        self.widget.set_adjustment(self.adj)
        self.widget.show()

    def get_value(self):
        '''
        Get value.

        :returns: floating point value as text
        :rtype: str
        '''
        return "%.0f" % self.adj.get_value()

    def set_value(self, value):
        '''
        Set value.

        :param value: Value to set
        '''
        self.adj.set_value(float(value))


class ChoiceWidget(FieldWidget):
    '''
    Choice Widget

    :param node: Form data for a choice
    :type node: :class:`ElementTree`
    :param config: Configuration data
    :type config: :class:`DratsConfig`
    '''

    def __init__(self, node, config):
        FieldWidget.__init__(self, node, config)

        self.logger = logging.getLogger("ChoiceWidget")
        self.choices = []
        self.default = None

        children = node.getchildren()

        for child in children:
            self.parse_choice(child)

        self.widget = make_choice(self.choices, False, self.default)
        self.widget.show()

    def parse_choice(self, node):
        '''
        Parse choice.

        :param node: Node of form data
        :type node: :class:`ElementTree`
        '''
        if node.tag != "choice":
            return

        if node.text:
            content = xml_unescape(node.text.strip())
            self.choices.append(content)
            for attrib, _value in node.items():
                if attrib == 'set':
                    self.default = content
                    break

    def get_value(self):
        '''
        Get value.

        :returns: value text
        :rtype: str
        '''
        return self.widget.get_active_text()

    def update_node(self):
        '''Update node.'''
        value = self.get_value()
        if not value:
            return

        children = self.node.getchildren()
        for child in children:
            if etree.tostring(child) == value:
                if not child.hasProp("set"):
                    child.newProp("set", "y")
            else:
                child.unsetProp("set")


class MultiselectWidget(FieldWidget):
    '''
    Multi Selection Widget

    :param node: Field data node
    :type node: :class:`ElementTree`
    :param config: Configuration data
    :type config: :class:`DratsConfig`
    '''

    def __init__(self, node, config):
        FieldWidget.__init__(self, node, config)

        self.logger = logging.getLogger("MultiselectWidget")
        self.choices = []
        self.widget = self.make_selector()
        self.widget.show()

        children = node.getchildren()
        for child in children:
            self.parse_choice(child)

    def parse_choice(self, node):
        '''
        Parse choice.

        :param node: node data
        :type node: :class:`ElementTree`
        '''
        if node.tag != "choice":
            return

        do_set = False
        for attrib, value in node.items():
            if attrib == 'set':
                do_set = value == 'y'

        if node.text:
            content = xml_unescape(node.text.strip())
            self.store.append(row=(do_set, content))
            self.choices.append((do_set, content))

    def toggle(self, _rend, path):
        '''
        Toggle handler for CellRenderer.

        :param _rend: not used
        :type _rend: :class:`Gtk.CellrenderToggle`
        :param path: Path to toggle a boolean state
        :type path: str
        '''
        path_row = self.store.get_iter(path)
        if path_row:
            old = self.store.get_value(path_row, 0)
            self.store.set_value(path_row, 0, not old)

    def make_selector(self):
        '''
        Make selector.

        :returns: Selection widget
        :rtype: :class:`Gtk.TreeView`
        '''
        self.store = Gtk.ListStore(GObject.TYPE_BOOLEAN,
                                   GObject.TYPE_STRING)
        self.view = Gtk.TreeView.new_with_model(self.store)

        rend = Gtk.CellRendererToggle()
        rend.connect("toggled", self.toggle)
        col = Gtk.TreeViewColumn("", rend, active=0)
        self.view.append_column(col)

        rend = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn("", rend, text=1)
        self.view.append_column(col)

        self.view.show()
        self.view.set_headers_visible(False)

        return self.view

    def make_container(self):
        '''
        Make container

        :returns: Container widget
        :rtype: :class:`Gtk.Box`
        '''
        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 2)

        scrollw = Gtk.ScrolledWindow()
        scrollw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrollw.add(self.widget)

        if self.caption:
            label = Gtk.Label.new(self.caption)
            vbox.pack_start(label, 0, 0, 0)
            label.show()
        vbox.pack_start(scrollw, 0, 0, 0)

        vbox.show()
        scrollw.show()
        return vbox

    def get_value(self):
        '''
        Get value

        :returns: empty string
        :rtype: str
        '''
        return ""

    def update_node(self):
        '''Update node.'''
        vals = {}
        iter_value = self.store.get_iter_first()
        while iter_value:
            setval, name = self.store.get(iter_value, 0, 1)
            vals[name] = setval
            iter_value = self.store.iter_next(iter_value)

        children = self.node.getchildren()
        for child in children:
            choice = etree.tostring(child).strip()
            if choice not in list(vals.keys()):
                vals[choice] = False

            if not child.hasProp("set"):
                child.newProp("set", vals[choice] and "y" or "n")
            else:
                child.setProp("set", vals[choice] and "y" or "n")


class LabelWidget(FieldWidget):
    '''
    Label Widget.

    :param node: Element Tree
    :type node: :class:`etree._ElementTree`
    :param config: Configuration data
    :type config: :class:`DratsConfig`
    '''

    def __init__(self, node, config):
        FieldWidget.__init__(self, node, config)
        self.nolabel = True

    def update_node(self):
        '''Update node.'''

    def make_container(self):
        '''
        Make container.

        :returns: Label
        :rtype: :class:`Gtk.Label`
        '''
        widget = Gtk.Label()
        widget.set_markup("<b><span color='blue'>%s</span></b>" % self.caption)
        # _color = Gdk.color_parse("blue")
        # widget.modify_fg(Gtk.StateFlags.NORMAL, color)
        widget.show()

        return widget


class FormField():
    '''
    Form Field.

    :param field: Field
    :type field: :class:`etree._Element`
    :param config: Configuration data
    :type config: :class:`DratsConfig`
    '''
    widget_types = {
        "text" : TextWidget,
        "multiline" : MultilineWidget,
        "toggle" : ToggleWidget,
        "date" : DateWidget,
        "time" : TimeWidget,
        "numeric" : NumericWidget,
        "choice" : ChoiceWidget,
        "multiselect" : MultiselectWidget,
        "label" : LabelWidget,
    }

    def __init__(self, field, config):
        self.node = field
        self.config = config
        for attrib, value in field.items():
            if attrib == 'id':
                self.ident = value

        self.build_gui()

    def set_editable(self, editable):
        '''
        Set editable.

        :param editable: Editable state
        :type editable: bool
        '''
        self.entry.set_editable(editable)

    @staticmethod
    def get_caption_string(node):
        '''
        Get caption string/

        :param node: Element
        :type node: :class:`etree._Element`
        :returns: Caption or "".
        :rtype: str
        '''
        if node.text:
            return node.text.strip()
        return ""

    def build_entry(self, node, caption):
        '''
        Build entry.

        :param node: Element for entry
        :type node: :class:`etree._Element`
        :param caption: Caption for entry
        :type caption: str
        :returns: Field widget
        :rtype: :class:`Gtk.Widget`
        '''
        widget_type = None
        for attrib, value in node.items():
            if attrib == 'type':
                widget_type = value
                break

        wtype = self.widget_types[widget_type]

        field = wtype(node, config=self.config)
        field.text = node.text
        field.set_caption(caption)
        field.set_id(self.ident)
        return field

    def build_gui(self, _editable=True):
        '''
        Build GUI.

        :param _editable: Not used
        :type _editable: bool
        '''
        self.caption = None
        self.entry = None

        children = self.node.getchildren()

        for child in children:
            if child.tag == "caption":
                cap_node = child
            elif child.tag == "entry":
                ent_node = child

        self.caption = self.get_caption_string(cap_node)
        self.entry = self.build_entry(ent_node, self.caption)
        self.widget = self.entry.get_widget()
        if self.entry.text:
            if hasattr(self.widget, 'set_text'):
                self.widget.set_text(self.entry.text)
            elif hasattr(self.widget, 'get_buffer'):
                buffer = self.widget.get_buffer()
                buffer.set_text(self.entry.text)
            elif hasattr(self.widget, 'get_children'):
                for child in self.widget.get_children():
                    if hasattr(child, 'set_text'):
                        child.set_text(self.entry.text)
                        break
                    if hasattr(child, 'get_buffer'):
                        buffer = child.get_buffer()
                        buffer.set_text(self.entry.text)
                        break

        self.widget.show()

    def get_widget(self):
        '''
        Get widget.

        :returns: Gtk Object
        :rtype: :class:`Gtk.Widget`
        '''
        return self.widget

    def update_node(self):
        '''Update node.'''
        self.entry.update_node()


# pylint wants only 7 instance attributes
# pylint wants only 20 public methods
# pylint: disable=too-many-public-methods, too-many-instance-attributes
class FormFile():
    '''
    Form File.

    :param filename: File name for form
    :type filename: str
    :raises: FormguiFormFileEmpty exception
    '''
    def __init__(self, filename):
        self.logger = logging.getLogger("FormFile")
        self._filename = filename
        try:
            self.doc = etree.parse(self._filename)
        except etree.XMLSyntaxError as err:
            raise FormguiFileNotValid("Form file %s is not valid! (%s)" %
                                      (filename, err))

        self.fields = []
        self.xsl_dir = 'forms'
        self.process_form(self.doc)

    def configure(self, config):
        '''
        Configure the form source directory.

        :param config: Configuration data
        :type config: :class:`DratsConfig`
        '''
        self.xsl_dir = config.form_source_dir()

    def save_to(self, filename):
        '''
        Save to file.

        :param filename: File name to save to
        :type filename: str
        '''
        self.doc.write(filename)

    def export_to_string(self):
        '''
        Export to string.

        :returns: result of writing the string
        :rtype: str
        '''
        form_writer = HTMLFormWriter(self.ident, self.xsl_dir)
        return form_writer.write_string(self.doc)

    def get_xml(self):
        '''
        Get xml.

        :returns: XML serialized into a string
        :rtype: str
        '''
        root = self.doc.getroot()
        return etree.tostring(root)

    def process_form(self, doc):
        '''
        Process Form.

        :param doc: ElementTree document
        :type doc: :class:`etree._ElementTree`
        :raises: FormguiFileMultipleForms if more than one form in file
        :raises: FormguiFileMultipleTitles if more than one title in file
        :raises: FormguiFileMultipleLogos if more than one logo in file
        '''
        forms = doc.xpath("//form")
        if len(forms) != 1:
            raise FormguiFileMultipleForms("%i forms in document" % len(forms))

        for attrib, value in forms[0].items():
            if attrib == 'id':
                self.ident = value

        titles = doc.xpath("//form/title")
        if len(titles) != 1:
            raise FormguiFileMultipleTitles("%i titles in document" %
                                            len(titles))

        if titles[0].text:
            self.title_text = titles[0].text.strip()
        else:
            self.title_text = ""

        logos = doc.xpath("//form/logo")
        if len(logos) > 1:
            raise FormguiFileMultipleLogos("%i logos in document" % len(logos))
        if logos and logos[0].text:
            self.logo_path = logos[0].text.strip()
        else:
            self.logo_path = None

    @staticmethod
    def __set_content(node, content):
        node.text = content

    def __get_xpath(self, path):
        result = self.doc.xpath(path)
        return result

    def get_path(self):
        '''
        Get path.

        :returns: List of x paths
        :rtype: list[str]
        '''
        pathels = []
        for element in self.__get_xpath("//form/path/e"):
            if element.text:
                text = element.text.strip()
                if text:
                    pathels.append(text)
        return pathels

    def __get_path(self):
        els = self.__get_xpath("//form/path")
        if not els:
            form = self.doc.xpath("//form")
            return etree.SubElement(form[0], "path")
        return els[0]

    def __add_path_element(self, name, element, append=False):
        path = self.__get_path()

        if append:
            child = etree.SubElement(path, name)
            self.__set_content(child, element)
            return

        els = self.__get_xpath("//form/path/%s" % name)
        if not els:
            child = etree.SubElement(path, name)
            self.__set_content(child, element)
            return

        self.__set_content(els[0], element)

    def add_path_element(self, element):
        '''
        Add path element.

        :param element: Element to add
        :type element: :class:`etree._Element`
        '''
        self.__add_path_element("e", element, True)

    def set_path_src(self, src):
        '''
        Set path source.

        :param src: source
        :type element: :class:`etree._Element`
        '''
        self.__add_path_element("src", src)

    def set_path_dst(self, dst):
        '''
        Set path destination.

        :param dst: Add destination to
        :type dst: :class:`etree._Element`
        '''
        self.__add_path_element("dst", dst)

    def set_path_mid(self, mid):
        '''
        Set path mid.

        :param mid: mid
        :type mid: :class:`etree._Element`
        '''
        self.__add_path_element("mid", mid)

    def __get_path_element(self, name):
        els = self.__get_xpath("//form/path/%s" % name)
        if els and els[0].text:
            return els[0].text.strip()
        return ""

    def get_path_src(self):
        '''
        Get path source.

        :returns: Path source
        :rtype: str
        '''
        return self.__get_path_element("src")

    def get_path_dst(self):
        '''
        Get path destination.

        :returns: Destination element
        :rtype: str
        '''
        return self.__get_path_element("dst")

    def get_path_mid(self):
        '''
        Get path mid.

        :returns: mid element
        :rtype: str
        '''
        return self.__get_path_element("mid")

    def get_field_value(self, field_id):
        '''
        Get field value.

        :param field_id: Field ID
        :type field_id: str
        :returns: field x path or None
        :rtype: str
        :raises: FormguiFileMultipleIds when multiple IDs are in a form
        '''
        els = self.__get_xpath("//form/field[@id='%s']/entry" % field_id)
        if len(els) > 1:
            raise FormguiFileMultipleIds("More than one id=%s node!" %
                                         field_id)
        if els and els[0].text:
            return xml_unescape(els[0].text.strip())
        return None

    def get_field_caption(self, field_id):
        '''
        Get field caption.

        :param field_id: Field ID
        :type field_id: str
        :returns: Field caption or None
        :rtype: str
        :raises: FormguiFileMultipleIds when multiple IDs are in a form
        '''
        els = self.__get_xpath("//form/field[@id='%s']/caption" % field_id)
        if len(els) > 1:
            raise FormguiFileMultipleIds("More than one id=%s node!" %
                                         field_id)
        if els[0].text:
            return xml_unescape(els[0].text.strip())
        return None

    def set_field_value(self, field_id, value):
        '''
        Set field value.

        :param field_id: Field id to set value on
        :type field_id: str
        :param value: Value to set
        :type value: str
        '''
        els = self.__get_xpath("//form/field[@id='%s']/entry" % field_id)
        self.logger.info("Setting %s to %s (%i)", field_id, value, len(els))
        if len(els) == 1:
            multiline = False
            for attrib, _val in els[0].items():
                if attrib == 'type':
                    multiline = value == 'multiline'
                    break
            if multiline:
                self.__set_content(els[0], value)
            else:
                self.__set_content(els[0], value.strip())

    def _try_get_fields(self, *names):
        for field in names:
            try:
                val = self.get_field_value(field)
                if val is not None:
                    return val
            except AttributeError:
                pass

        return "Unknown"

    def get_subject_string(self):
        '''
        Get subject string.

        :returns: Subject string
        :rtype: str
        '''
        subj = self._try_get_fields("_auto_subject", "subject")
        if subj != "Unknown":
            return subj.replace("\r", "").replace("\n", "")

        return "%s#%s" % (self.get_path_src(),
                          self._try_get_fields("_auto_number"))

    def get_recipient_string(self):
        '''
        Get recipient string.

        :returns: Recipient string
        :rtype: str
        '''
        dst = self.get_path_dst()
        if dst:
            return dst
        return self._try_get_fields("_auto_recip", "recip", "recipient")

    def get_sender_string(self):
        '''
        Get sender string.

        :returns: Sender string
        :rtype: str
        '''
        src = self.get_path_src()
        if src:
            return src
        return self._try_get_fields("_auto_sender", "sender")

    def get_attachments(self):
        '''
        Get attachments.

        :returns: list of attachment tuples
        :rtype: list[tuple[str, int]]
        '''
        atts = []
        els = self.__get_xpath("//form/att")
        for element in els:
            name = None
            for attrib, value in els[0].items():
                if attrib == 'name':
                    name = value
                    break
            data = etree.tostring(element)
            atts.append((name, len(data)))

        return atts

    def get_attachment(self, name):
        '''
        Get attachment.

        :param name: Name of attachment
        :type name: str
        :returns: Attachment data
        :rtype: bytes
        :raises: :class:`FormguiFileMultipleAtts` if more than one attachment
        '''
        els = self.__get_xpath("//form/att[@name='%s']" % name)
        if len(els) == 1:
            data = etree.tostring(els[0])
            data = base64.b64decode(data)
            return zlib.decompress(data)

        raise FormguiFileMultipleAtts(
            "Internal Error: %i attachments named `%s'" % (len(els), name))

    def add_attachment(self, name, data):
        '''
        Add attachment.

        :param name: Name of attachment
        :type name: str
        :param data: data of attachment
        :type data: bytes
        :raises: :class:`FormguiFileDuplicateAtt` if duplicate attachments
        '''
        try:
            att = self.get_attachment(name)
        except FormguiFileMultipleAtts:
            self.logger.debug("add_attachment", exc_info=True)
            att = None

        if att is not None:
            raise FormguiFileDuplicateAtt(
                "Already have an attachment named `%s'" % name)

        els = self.__get_xpath("//form")
        if len(els) == 1:
            attnode = etree.Element('att')
            els[0].append(attnode)
            attnode.set('name', name)
            data = zlib.compress(data, 9)
            data = base64.b64encode(data)
            self.__set_content(attnode, data)

    def del_attachment(self, name):
        '''
        Del attachment.

        :param name: Name of attachment
        :type name: str
        '''
        els = self.__get_xpath("//form/att[@name='%s']" % name)
        if len(els) == 1:
            els[0].unlinkNode()


class FormDialog(FormFile, Gtk.Dialog):
    '''
    Form Dialog.

    :param title: form title
    :type title: str
    :param filename: Filename for form
    :type filename: str
    :param parent: parent widget, Default None
    :type parent: :class:`GtkWindow`
    :param config: Configuration data
    :type config: :class:`DratsConfig`
    '''

    def __init__(self, title, filename, parent=None, config=None):
        self.config = config
        self.logger = logging.getLogger("FormDialog")
        Gtk.Dialog.__init__(self, parent=parent)
        FormFile.__init__(self, filename)

        self.process_fields(self.doc)
        self.title_text = title
        self.set_title(self.title_text)
        self.attbox = None
        self._srcbox = None
        self._dstbox = None

        try:
            x_pos = self.config.getint("state", "form_%s_x" % self.ident)
            y_pos = self.config.getint("state", "form_%s_y" % self.ident)
        except NoOptionError:
            self.logger.info("Unable to get form_%s_* from config",
                             self.ident)
            x_pos = 300
            y_pos = 500

        self.set_default_size(x_pos, y_pos)

    def save_to(self, filename):
        '''
        Save To.

        :param filename: Filename to save to
        :type filename: str
        '''
        for field in self.fields:
            field.update_node()
        FormFile.save_to(self, filename)

    def process_fields(self, doc):
        '''
        Process fields.

        :param doc: XML ElementTree
        :type doc: :class:`etree._ElementTree`
        '''
        fields = doc.xpath("//form/field")
        for field in fields:
            self.fields.append(FormField(field, config=self.config))

    def export(self, outfile):
        '''
        Export to file.

        :param outfile: Output file.
        :type outfile: str
        '''
        for field in self.fields:
            field.update_node()

        form_writer = HTMLFormWriter(self.ident, self.xsl_dir)
        form_writer.write_doc(self.doc, outfile)

    def run_auto(self, save_file=None):
        '''
        Run auto.

        :param save_file: Filename to save, Default None
        :type save_file: str
        :returns: True if response was not Cancel
        :rtype: bool
        '''
        if not save_file:
            save_file = self._filename

        run = self.run()
        if run != Gtk.ResponseType.CANCEL:
            self.save_to(save_file)

        return run

    def but_save(self, _button, _data=None):
        '''
        Button save.

        Not finding anything that references this.

        :param _button: Not used
        :type _button: :class:`GtkButton`
        :param _data: Not used
        '''
        self.logger.info("but_save: what is callign this?",
                         stack_info=True)
        platform = dplatform.get_platform()
        outfile = platform.gui_save_file(default_name="%s.html" % self.ident)
        if not outfile:
            return

        try:
            self.export(outfile)
        except OSError as err:
            self.logger.info("button_save: %s", err)

            err_dialog = Gtk.MessageDialog(buttons=Gtk.ButtonsType.OK,
                                           parent=self)
            err_dialog.text = "Unable to open file"
            err_dialog.format_secondary_text("Unable to open %s (%s)" %
                                             (outfile, err))
            err_dialog.run()
            err_dialog.destroy()

    def button_printable(self, _button, _data=None):
        '''
        Button printable.

        :param _button: Not used
        :type _button: :class:`Gtk.Button`
        :param _data: Not used
        '''
        outfile = tempfile.NamedTemporaryFile(suffix=".html")
        name = outfile.name
        outfile.close()
        self.export(name)

        self.logger.info("button_printable: Exported to temporary file: %s",
                         name)
        dplatform.get_platform().open_html_file(name)

    @staticmethod
    def calc_check(buffer, checkwidget):
        '''
        Calc check changed handler.

        Check widget creation does not appear to have been implemented,
        so this method does not appear to be called.

        :param buffer: Buffer to check
        :type buffer: :class:`Gtk.Editable`
        :param checkwidget: Widget to use for check
        :type: checkwidget: :class:`Gtk.Editable`
        '''
        message = buffer.get_text(buffer.get_start_iter(),
                                  buffer.get_end_iter(), True)
        checkwidget.set_text("%i" % len(message.split()))

    # pylint wants only 15 local variables
    # pylint: disable=too-many-locals
    def build_routing_widget(self):
        '''
        Build routing widget.

        :returns: Gtk.Expander object
        :rtype: :class:`Gtk.Expander`
        '''
        grid = Gtk.Grid.new()

        src_label = Gtk.Label.new(_("Source Callsign"))
        src_label.show()

        srcbox = Gtk.Entry()
        srcbox.set_text(self.get_path_src())
        srcbox.set_editable(False)
        srcbox.show()
        self._srcbox = srcbox

        dst_label = Gtk.Label.new(_("Destination Callsign"))
        dst_label.show()

        dstbox = Gtk.Entry()
        dstbox.set_text(self.get_path_dst())
        dstbox.show()
        self._dstbox = dstbox

        grid.attach(src_label, 0, 0, 1, 1)

        grid.attach_next_to(srcbox, src_label, Gtk.PositionType.RIGHT, 1, 1)

        grid.attach_next_to(dst_label, srcbox, Gtk.PositionType.RIGHT, 1, 1)

        grid.attach_next_to(dstbox, dst_label, Gtk.PositionType.RIGHT, 1, 1)

        expander = Gtk.Expander()
        expander.set_label(_("Routing Information"))
        expander.add(grid)
        grid.show()
        expander.set_expanded(True)
        expander.show()
        return expander

    def build_path_widget(self):
        '''
        Build path widget.

        :returns Gtk.Expander object
        :rtype: :class:`Gtk.Expander`
        '''
        pathels = self.get_path()

        pathbox = Gtk.Entry()
        pathbox.set_text(";".join(pathels))
        pathbox.set_property("editable", False)
        pathbox.show()

        expander = Gtk.Expander.new(_("Path"))
        expander.add(pathbox)
        expander.show()

        return expander

    # pylint wants only 15 local variables
    # pylint wants only 50 statements
    # pylint: disable=too-many-locals, too-many-statements
    def build_att_widget(self):
        '''
        Build attachment widget.

        :returns: Gtk.Expander object
        :rtype: :class:`Gtk.Expander`
        '''
        hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 2)

        cols = [(GObject.TYPE_STRING, "KEY"),
                (GObject.TYPE_STRING, _("Name")),
                (GObject.TYPE_INT, _("Size (bytes)"))]
        self.attbox = KeyedListWidget(cols)
        self.attbox.set_resizable(0, True)
        self.attbox.set_expander(0)
        self.attbox.show()
        scrollw = Gtk.ScrolledWindow()
        scrollw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrollw.add(self.attbox)
        scrollw.show()

        hbox.pack_start(scrollw, 1, 1, 1)

        def item_set(_box, key):
            '''
            Item Set Handler for KeyedListWidget.

            :param _box: Widget that was signaled
            :type _box: :class:`KeyedListWidget`
            :param key: Key that was set
            :type key: str
            '''
            natt = len(self.attbox.get_keys())
            self.logger.info("Item %s set: %i", key, natt)
            if natt:
                msg = _("Attachments") + " (%i)" % natt
                attexp.set_label("<span color='blue'>%s</span>" % msg)
            else:
                attexp.set_label(_("Attachments"))

        self.attbox.connect("item-set", item_set)

        bbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 2)
        bbox.show()
        hbox.pack_start(bbox, 0, 0, 0)

        @run_or_error
        def button_add(_button):
            '''
            Add button handler.

            :param _button: Button widget
            :type _button: :class:`GtkWidget`
            '''
            fname = dplatform.get_platform().gui_open_file()
            if fname:
                name = os.path.basename(fname)
                file_handle = open(fname, "rb")
                data = file_handle.read()
                file_handle.close()
                self.add_attachment(name, data)
                self.attbox.set_item(name, name, len(data))

        add = Gtk.Button.new_with_label(_("Add"))
        add.connect("clicked", button_add)
        add.show()
        bbox.pack_start(add, 0, 0, 0)

        @run_or_error
        def button_remove(_button):
            '''
            Remove button handler.

            :param _button: Button activated, Unused
            :type _button: :class:`Gtk.Button`
            '''
            name = self.attbox.get_selected()
            self.del_attachment(name)
            self.attbox.del_item(name)
            item_set(None, name)

        rem = Gtk.Button.new_with_label(_("Remove"))
        rem.connect("clicked", button_remove)
        rem.show()
        bbox.pack_start(rem, 0, 0, 0)

        @run_or_error
        def button_save(_buttton):
            '''
            Button Save Handler.

            :param _button: Button that was pressed, Unused
            :type _button: :class:`Gtk.Widget`
            '''
            name = self.attbox.get_selected()
            if not name:
                return
            fname = dplatform.get_platform().gui_save_file(default_name=name)
            if fname:
                file_handle = open(fname, "wb")
                data = self.get_attachment(name)
                if not data:
                    raise FormguiFileInvalidAtt("Unable to extract attachment")
                file_handle.write(data)
                file_handle.close()

        sav = Gtk.Button.new_with_label(_("Save"))
        sav.connect("clicked", button_save)
        sav.show()
        bbox.pack_start(sav, 0, 0, 0)

        attexp = Gtk.Expander.new(_("Attachments"))
        attexp.set_use_markup(True)
        hbox.show()
        attexp.add(hbox)
        attexp.show()

        atts = self.get_attachments()
        for name, size in atts:
            self.attbox.set_item(name, name, size)

        return attexp

    # pylint wants only 15 local variables
    # pylint: disable=too-many-locals
    def build_toolbar(self, editable):
        '''
        Build toolbar.

        :param editable: Editable State
        :type editable: bool
        :returns: GtkToolbar object
        :rtype: :class:`Gtk.Toolbar`
        '''
        toolbar = Gtk.Toolbar()

        def close(_widget, _event):
            '''
            Close delete event handler.

            :param _widget: widget signaled, Unused
            :type _widget: :class:`Gtk.Widget`
            :param _event: Event that signaled this handler, Unused
            :type _event: :class:`Gtk.Event`
            :returns: True to stop other handlers from processing this signal
            :rtype: bool
            '''
            self.logger.info("build_toolbar Closing")
            if editable:
                dialog = ask_for_confirmation("Close without saving?", self)
                if not dialog:
                    return True
            width, height = self.get_size()
            self.config.set("state", "form_%s_x" % self.ident, str(width))
            self.config.set("state", "form_%s_y" % self.ident, str(height))
            self.response(Gtk.ResponseType.CLOSE)
            return False

        def save(_button):
            '''
            Save button handler.

            :param _button: button clicked, Unused
            :type _button: :class:`Gtk.Button`
            '''
            self.response(RESPONSE_SAVE)

        def send(_button):
            '''
            Send button handler.

            :param _button: button clicked, Unused
            :type _button: :class:`Gtk.Button`
            '''
            self.response(RESPONSE_SEND)

        def svia(_button):
            '''
            Send via button handler.

            :param _button: button clicked, Unused
            :type _button: :class:`Gtk.Button`
            '''
            self.response(RESPONSE_SEND_VIA)

        def reply(_button):
            '''
            Reply button handler.

            :param _button: button clicked, Unused
            :type _button: :class:`Gtk.Button`
            '''
            self.response(RESPONSE_REPLY)

        def delete(_button):
            '''
            Delete button handler.

            :param _button: button clicked, Unused
            :type _button: :class:`Gtk.Button`
            '''
            self.response(RESPONSE_DELETE)

        # We have to get in the way of the RESPONSE_DELETE_EVENT signal
        # to be able to catch the save
        # Only documentation I can find is:
        # https://stackoverflow.com/questions/49551027/
        # avoiding-closing-a-gtk-dialog
        def reject_delete_response(dialog, response):
            '''
            Reject delete response handler

            :param dialog: Dialog being signaled
            :type dialog: :class:`Gtk.Dialog`
            :param response: Response code
            :type response: :class:`Gtk.ResponseType`
            '''
            if response == Gtk.ResponseType.DELETE_EVENT:
                dialog.stop_emission_by_name("response")

        send_tip = _("Place this message in the Outbox for sending")
        svia_tip = _("Place this message in the Outbox and send it directly "
                     "to a specific station for relay")
        save_tip = _("Save changes to this message")
        prnt_tip = _("View the printable version of this form")
        rply_tip = _("Compose a reply to this message")
        dele_tip = _("Delete this message")

        # pylint: disable=fixme
        # FIX-ME: This should be consistent and use a null string for
        # images instead of putting a label string in the image field.
        if editable:
            buttons = [
                (_("Save"), "", save_tip, save),
                ("msg-send.png", _("Send"), send_tip, send),
                ("msg-send-via.png", _("Send via"), svia_tip, svia),
                (_("Print"), "", prnt_tip, self.button_printable),
                ]
        else:
            buttons = [
                ("msg-reply.png", _("Reply"), rply_tip, reply),
                # ("msg-send.png", _("Forward"),  send_tip, send),
                ("msg-send-via.png", _("Forward via"), svia_tip, svia),
                (_("Print"), "", prnt_tip, self.button_printable),
                (_("Delete"), "", dele_tip, delete),
                ]

        # self.connect("destroy", close)
        self.connect("delete-event", close)
        self.connect("response", reject_delete_response)

        button_index = 0
        for img, lab, tip, func in buttons:
            if not lab:
                tool_button = Gtk.ToolButton.new(None, img)
            else:
                icon = Gtk.Image()
                icon.set_from_pixbuf(self.config.ship_img(img))
                icon.show()
                tool_button = Gtk.ToolButton.new(icon, lab)
            tool_button.show()
            try:
                tool_button.set_tooltip_text(tip)
            except AttributeError:
                pass
            tool_button.connect("clicked", func)
            toolbar.insert(tool_button, button_index)
            button_index += 1

        toolbar.show()
        return toolbar

    # pylint wants only 15 local variables
    # pylint wants only 12 branches
    # pylint: disable=too-many-branches, too-many-locals
    def build_gui(self, editable=True):
        '''
        Build gui.

        :param editable: Editable State, default True.
        :type editable: bool
        '''
        self.vbox.pack_start(self.build_toolbar(editable), 0, 0, 0)

        tlabel = Gtk.Label()
        tlabel.set_markup("<big><b>%s</b></big>" % self.title_text)
        tlabel.show()

        if self.logo_path:
            image = Gtk.Image()
            try:
                base = self.config.get("settings", "form_logo_dir")
                self.logger.info("Logo path: %s",
                                 os.path.join(base, self.logo_path))
                image.set_from_file(os.path.join(base, self.logo_path))
                self.vbox.pack_start(image, 0, 0, 0)
                image.show()
            except (OSError, NoOptionError) as err:
                self.logger.info("Unable to load or display logo %s: %s",
                                 self.logo_path, err)
        self.vbox.pack_start(tlabel, 0, 0, 0)

        self.vbox.pack_start(self.build_routing_widget(), 0, 0, 0)

        field_grid = Gtk.Grid.new()

        row = 0
        col = 0
        scrollw = Gtk.ScrolledWindow()
        scrollw.set_policy(Gtk.PolicyType.NEVER,
                           Gtk.PolicyType.AUTOMATIC)
        scrollw.add(field_grid)
        field_grid.show()
        scrollw.show()
        self.vbox.pack_start(scrollw, 1, 1, 1)

        msg_field = None
        chk_field = None

        prev_widget = None
        for field in self.fields:
            if field.ident == "_auto_check":
                chk_field = field
            elif field.ident == "_auto_message":
                msg_field = field
            # pylint: disable=fixme
            elif field.ident == "_auto_senderX": # FIXME
                if not field.entry.widget.get_text():
                    call = self.config.get("user", "callsign")
                    field.entry.widget.set_text(call)
                field.entry.widget.set_property("editable", False)
            elif field.ident == "_auto_position":
                if not field.entry.widget.get_text():
                    self.logger.info("import . mainapp")
                    from . import mainapp # Dirty hack
                    pos = mainapp.get_mainapp().get_position()
                    field.entry.widget.set_text(pos.coordinates())

            label = Gtk.Label.new(field.caption)
            label.show()
            widget = field.get_widget()
            if field.entry.vertical:
                if prev_widget:
                    field_grid.attach_next_to(label, prev_widget,
                                              Gtk.PositionType.BOTTOM, col, 1)
                else:
                    field_grid.attach(label, col, row, 1, col)
                row += 1
                widget.set_hexpand(True)
                widget.set_vexpand(True)
                field_grid.attach_next_to(widget, label,
                                          Gtk.PositionType.BOTTOM, col, 1)
                prev_widget = widget
            elif field.entry.nolabel:
                widget.set_hexpand(True)
                widget.set_vexpand(True)
                if prev_widget:
                    field_grid.attach_next_to(widget, prev_widget,
                                              Gtk.PositionType.BOTTOM, col, 1)
                else:
                    field_grid.attach(widget, col, row, 1, 1)
                prev_widget = widget
            else:
                if prev_widget:
                    field_grid.attach_next_to(label, prev_widget,
                                              Gtk.PositionType.BOTTOM, 1, 1)
                else:
                    field_grid.attach(label, col, row, 1, 1)
                prev_widget = label
                widget.set_hexpand(True)
                field_grid.attach_next_to(widget, label,
                                          Gtk.PositionType.RIGHT, 1, 1)
                col += 1
            row += 1
            col += 1

        self.vbox.pack_start(self.build_att_widget(), 0, 0, 0)
        self.vbox.pack_start(self.build_path_widget(), 0, 0, 0)

        if msg_field and chk_field:
            msg_widget = msg_field.entry.buffer
            chk_widget = chk_field.entry.widget

            msg_widget.connect("changed", self.calc_check, chk_widget)

        self.set_editable(editable)

    def update_dst(self):
        '''Update Destination.'''
        dst = self._dstbox.get_text()
        if "@" not in dst:
            dst = dst.upper()
        self.set_path_dst(dst)

    # Renamed from run to prevent conflict with the parent Gtk.Dialog class
    def run_dialog(self):
        '''
        Run the dialog.

        :returns: Dialog result
        :rtype: :class:`Gtk.ResponseType`
        '''
        # pylint does not know how to check no-member for GTK methods.
        # pylint: disable=no-member
        self.vbox.set_spacing(5)
        self.build_gui()
        self.set_size_request(380, 450)

        run_dialog = Gtk.Dialog.run(self)
        self.update_dst()

        return run_dialog

    def set_editable(self, editable):
        '''
        Set Fields Editable state.

        :param editable: State to set
        :type editable: bool
        '''
        for field in self.fields:
            field.set_editable(editable)


def main():
    '''Main program for unit testing.'''

    logging.basicConfig(level=logging.INFO)

    logger = logging.getLogger("FormguiTest")
    current_info = None

    from . import config
    config_data = config.DratsConfig(None)

    def form_done(_dlg, response, info):
        act = "unknown"
        if response == RESPONSE_SEND:
            act = "Send"
        elif response == RESPONSE_SAVE:
            act = "Save"
        elif response == RESPONSE_REPLY:
            act = "Reply"
        elif response == RESPONSE_DELETE:
            act = "Delete"
        elif response == RESPONSE_SEND_VIA:
            act = "Send-Via"
        logger.info("response: %d = %s", response, act)
        logger.info("info: %s", info)

    form = FormDialog("Form", sys.argv[1], config=config_data)

    form.connect("response", form_done, current_info)
    form.run_dialog()
    form.destroy()

if __name__ == "__main__":
    main()
