#
'''Form GUI'''
# pylint: disable=too-many-lines
# Copyright 2008 Dan Smith <dsmith@danplanet.com>
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

import gettext
import sys
import time
import os
import tempfile
import zlib
import base64

from lxml import etree
# pyright: reportMissingModuleSource=false
from six.moves import range
from six.moves.configparser import NoOptionError

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject

# importing printlog() wrapper
from .debug import printlog

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

_ = gettext.gettext
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


# wb8tyw: Style is deprecated in favor of Gtk.StyleContext.
# At startup, the sets are empty.   Need to figure out what this is used for.
# pylint: disable=invalid-name
style = Gtk.Style()
for style_index in [style.fg, style.bg, style.base]:
    print('-Debug Style Dump-----')
    print(style_index)
    print('-------')
    if Gtk.StateFlags.NORMAL in style_index:
        if Gtk.stateFlags.INSENSITIVE in style_index:
            style_index[Gtk.StateFlags.INSENSITIVE] = \
                style_index[Gtk.StateFlags.NORMAL]
STYLE_BRIGHT_INSENSITIVE = style
del style
del style_index


def xml_escape(string):
    '''
    XML escape.

    :param string: String to add XML escapes
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
            # pylint: disable=broad-except
            except Exception as err:
                printlog("Formgui", "   : XML Error: & with no ; (%s -%s-)" %
                         (type(err), err))
                string_index += 1
                continue

            esc = string[string_index:semi]

            if not esc:
                printlog("Formgui", "   : No escape: %i:%i" %
                         (string_index, semi))
                string_index += 1
                continue

            if string[string_index:semi] in data:
                out += data[esc]
            else:
                printlog("Formgui",
                         "   : XML Error: No such escape: `%s'" % esc)
            string_index += len(esc)
    return out


# pylint: disable=too-few-public-methods
class FormWriter():
    '''Form Writer'''

    # pylint: disable=no-self-use
    def write(self, formxml, outfile):
        '''
        Write.

        :param formxml: String with form in XML
        :param outfile: File to write out
        '''
        doc = etree.fromstring(formxml)
        doc.write(outfile, pretty_print=True)


class HTMLFormWriter(FormWriter):
    '''
    HTML Form Writer.

    :param form_type: String for type of form
    :param xsl_dir: Directory path for xsl file
    '''

    def __init__(self, form_type, xsl_dir):
        self.xslpath = os.path.join(xsl_dir, "%s.xsl" % form_type)
        if not os.path.exists(self.xslpath):
            self.xslpath = os.path.join(xsl_dir, "default.xsl")

    def writeDoc(self, doc, outfile):
        '''
        Write Document.

        :param doc: ElementTree document
        :param outfile: File name to write
        '''
        printlog("Formgui", "   : Writing to %s" % outfile)
        styledoc = etree.parse(self.xslpath)
        style_sheet = etree.XSLT(styledoc)
        result = style_sheet(doc)
        result.write(outfile, pretty_print=True)

    def writeString(self, doc):
        '''
        Write String.

        :param doc: ElementTree document
        :returns: element written as a string.
        '''
        styledoc = etree.parse(self.xslpath)
        style_sheet = etree.XSLT(styledoc)
        result = style_sheet(doc)
        return etree.tostring(result, pretty_print=True).decode()


class FieldWidget():
    '''
    Field Widget.

    :param node: Element Tree for node
    '''

    def __init__(self, node):
        self.node = node
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
        '''
        self.caption = caption

    def set_id(self, ident):
        '''
        Set identity.

        :param ident: Identity of widget
        '''
        self.ident = ident

    def make_container(self):
        '''
        Make Container.

        :returns: widget object
        '''
        return self.widget

    def get_widget(self):
        '''
        Get widget.

        :returns: Widget of container
        '''
        return self.make_container()

    # pylint: disable=no-self-use
    def get_value(self):
        '''
        Get value

        :returns: None
        '''
        return None

    def set_value(self, value):
        '''
        Set value.

        :param value: Not used
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
        '''
        if self.widget:
            self.widget.set_sensitive(editable)
            self.widget.set_style(STYLE_BRIGHT_INSENSITIVE)


class TextWidget(FieldWidget):
    '''
    Text Widget.

    :param node: ElementTree for node
    '''

    def __init__(self, node):
        FieldWidget.__init__(self, node)

        text = ""
        if node.text and node.getchildren():
            text = xml_unescape(node.text.strip())

        self.widget = Gtk.Entry()
        self.widget.set_text(text)
        self.widget.show()

    def get_value(self):
        '''
        Get value.

        :returns: text
        '''
        return self.widget.get_text()

    def set_value(self, value):
        '''
        Set value.

        :param value: Text to set
        '''
        self.widget.set_text(value)


class ToggleWidget(FieldWidget):
    '''
    Toggle Widget.

    :param node: ElementTree for node
    '''

    def __init__(self, node):
        FieldWidget.__init__(self, node)

        if node.children:
            try:
                # pylint: disable=eval-used
                status = eval(node.text.title())
            # pylint: disable=broad-except
            except Exception as err:
                printlog("Formgui   ",
                         ": ToggleWidget Status of `%s' is invalid (%s -%s-)" %
                         (node.text.title(), type(err), err))
                status = False
        else:
            status = False

        self.widget = Gtk.CheckButton.new_with_label(_("Yes"))
        self.widget.set_active(status)
        self.widget.show()

    def get_value(self):
        '''
        Get value.

        :returns: string for boolean state of widget
        '''
        return str(self.widget.get_active())


class MultilineWidget(FieldWidget):
    '''
    Multi Line Widget

    :param node: ElementTree for node
    '''

    def __init__(self, node):
        FieldWidget.__init__(self, node)
        self.vertical = True

        text = ""
        if node.text and node.getchildren():
            text = xml_unescape(node.text.strip())

        self.buffer = Gtk.TextBuffer()
        self.buffer.set_text(text)
        self.widget = Gtk.TextView.new_with_buffer(self.buffer)
        self.widget.show()
        self.widget.set_size_request(175, 200)
        self.widget.set_wrap_mode(Gtk.WrapMode.WORD)

        try:
            # The mainapp class is not initialized when the unit tests are
            # run so the config information is not available.
            from . import mainapp
            config = mainapp.get_mainapp().config
            if config.getboolean("prefs", "check_spelling"):
                spell.prepare_TextBuffer(self.buffer)
        except AttributeError:
            pass

    def make_container(self):
        '''
        Make container

        :returns: Gtk.Box object
        '''
        scrollw = Gtk.ScrolledWindow()
        scrollw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrollw.add(self.widget)
        return scrollw

        # pylint: disable=unreachable
        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 2)

        label = Gtk.Label.new(self.caption)
        vbox.pack_start(label, 0, 0, 0)
        vbox.pack_start(scrollw, 0, 0, 0)

        label.show()
        vbox.show()
        scrollw.show()

        return vbox

    def get_value(self):
        '''
        Get value.

        :returns: string containing multiple lines
        '''
        return self.buffer.get_text(self.buffer.get_start_iter(),
                                    self.buffer.get_end_iter(), True)

    def set_value(self, value):
        '''
        Set value.

        :param value: String containing multiple lines
        '''
        self.buffer.set_text(value)


class DateWidget(FieldWidget):
    '''
    Date Widget.

    :param node: ElementTree for node
    '''

    def __init__(self, node):
        FieldWidget.__init__(self, node)

        try:
            text = etree.tostring(node.children).strip()
            (day, month, year) = text.split("-", 3)
        # pylint: disable=broad-except
        except Exception as err:
            printlog("Formgui",
                     "   : Datewidget __init__ exception: %s -%s-" %
                     (type(err), err))
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

        :returns: string containing date
        '''
        return "%s-%s-%s" % (self.daybox.get_active_text(),
                             self.monthbox.get_active_text(),
                             self.yearbox.get_active_text())


class TimeWidget(FieldWidget):
    '''
    Time Widget.

    :param node: ElementTree of node
    '''

    def __init__(self, node):
        FieldWidget.__init__(self, node)

        try:
            text = etree.tostring(node.children).strip()
            (hours, minutes, seconds) = (int(x) for x in text.split(":", 3))
        # pylint: disable=broad-except
        except Exception as err:
            printlog("Formgui",
                     "   : Timewidget __init__ exception: %s -%s-" %
                     (type(err), err))
            try:
                from . import mainapp
                config = mainapp.get_mainapp().config
                if config.getboolean("prefs", "useutc"):
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
        '''
        return "%.0f:%02.0f:%02.0f" % (self.hour_a.get_value(),
                                       self.min_a.get_value(),
                                       self.sec_a.get_value())


class NumericWidget(FieldWidget):
    '''
    Numeric Widget.

    :param node: ElementTree of node
    '''
    def __init__(self, node):
        FieldWidget.__init__(self, node)

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
                except ValueError as err:
                    # Want to find out how this can happen
                    printlog("Formgui",
                             "   : NumericWidget __init__ %s was %s. (%s)" %
                             (attrib, value, err))
        try:
            initial = float(etree.tostring(node.children))
        except ValueError as err:
            # Want to find out how this can happen
            printlog("Formgui",
                     "   : NumericWidget __init__ initial. (%s)" % err)

        self.adj = Gtk.Adjustment.new(initial, limit['min'], limit['max'],
                                      1, 10, 0)
        self.widget = Gtk.SpinButton()
        self.widget.set_adjustment(self.adj)
        self.widget.show()

    def get_value(self):
        '''
        Get value.

        :returns: String containing a floating point value'''
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

    :param node: ElementTree of node
    '''

    def parse_choice(self, node):
        '''
        Parse choice.

        :param node: ElementTree of node'''
        if node.name != "choice":
            return

        try:
            content = xml_unescape(etree.tostring(node.children).strip())
            self.choices.append(content)
            for attrib, _value in node.items():
                if attrib == 'set':
                    self.default = content
                    break
        # pylint: disable=broad-except
        except Exception as err:
            printlog("Formgui",
                     "   : ChoiceWidget/parse_choice Error: %s -%s-" %
                     (type(err), err))
            # pass

    def __init__(self, node):
        FieldWidget.__init__(self, node)

        self.choices = []
        self.default = None

        child = node.children
        while child:
            if child.type == "element":
                self.parse_choice(child)

            child = child.next

        self.widget = make_choice(self.choices, False, self.default)
        self.widget.show()

    def get_value(self):
        '''
        Get value.

        :returns: value text
        '''
        return self.widget.get_active_text()

    def update_node(self):
        '''Update node.'''
        value = self.get_value()
        if not value:
            return

        child = self.node.children
        while child:
            if etree.tostring(child) == value:
                if not child.hasProp("set"):
                    child.newProp("set", "y")
            else:
                child.unsetProp("set")

            child = child.next


class MultiselectWidget(FieldWidget):
    '''
    Multi Selection Widget

    :param node: ElementTree node.
    '''

    def parse_choice(self, node):
        '''
        Parse choice.

        :param node: ElementTree
        '''
        if node.name != "choice":
            return

        do_set = False
        for attrib, value in node.items():
            if attrib == 'set':
                do_set = value == 'y'
        try:
            content = xml_unescape(etree.tostring(node.children).strip())
            self.store.append(row=(do_set, content))
            self.choices.append(do_set, content)
        # pylint: disable=broad-except
        except Exception as err:
            printlog("Formgui",
                     "   : MultiselectWidget/parse_choice Error: %s -%s-" %
                     (type(err), err))

    def toggle(self, _rend, path):
        '''
        Toggle.

        :param _rend: not used
        :param path: Path to toggle a boolean state
        '''
        #self.store[path][0] = not self.store[path][0]
        path_row = self.store.get_iter(path)
        if path_row:
            old = self.store.get_value(path_row, 0)
            self.store.set_value(path_row, 0, not old)

    def make_selector(self):
        '''
        Make selector.

        :returns: Gtk.TreeView
        '''
        self.store = Gtk.ListStore(GObject.TYPE_BOOLEAN,
                                   GObject.TYPE_STRING)
        self.view = Gtk.TreeView(self.store)

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

    def __init__(self, node):
        FieldWidget.__init__(self, node)

        self.choices = []
        self.widget = self.make_selector()
        self.widget.show()

        child = node.children
        while child:
            if child.type == "element":
                self.parse_choice(child)
            child = child.next

    def make_container(self):
        '''
        Make container

        :returns: Gtk.Box object
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

        child = self.node.children
        while child:
            choice = etree.tostring(child).strip()
            if choice not in list(vals.keys()):
                vals[choice] = False

            if not child.hasProp("set"):
                child.newProp("set", vals[choice] and "y" or "n")
            else:
                child.setProp("set", vals[choice] and "y" or "n")

            child = child.next


class LabelWidget(FieldWidget):
    '''
    Label Widget.

    :param node: Element Tree
    '''

    def __init__(self, node):
        FieldWidget.__init__(self, node)
        self.nolabel = True

    def update_node(self):
        '''Update node.'''
        # pass

    def make_container(self):
        '''
        Make container.

        :returns: Gtk.Label widget
        '''
        widget = Gtk.Label()
        widget.set_markup("<b><span color='blue'>%s</span></b>" % self.caption)
        _color = Gdk.color_parse("blue")
        # widget.modify_fg(Gtk.StateFlags.NORMAL, color)
        widget.show()

        return widget


class FormField():
    '''
    Form Field.

    :param field: Field
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

    def set_editable(self, editable):
        '''
        Set editable.

        :param editable: Boolean editable state
        '''
        self.entry.set_editable(editable)

    # pylint: disable=no-self-use
    def get_caption_string(self, node):
        '''
        Get caption string/

        :param node: ElementTree
        :returns: Caption string or "".
        '''
        if node.text:
            return node.text.strip()
        return ""

    def build_entry(self, node, caption):
        '''
        Build entry.

        :param node: ElementTree for entry
        :param caption: Caption for entry
        :returns: Field widget
        '''
        widget_type = None
        for attrib, value in node.items():
            if attrib == 'type':
                widget_type = value
                break

        wtype = self.widget_types[widget_type]

        field = wtype(node)
        field.text = node.text
        field.set_caption(caption)
        field.set_id(self.ident)
        return field

    def build_gui(self, _editable=True):
        '''
        Build GUI.

        :param _editable: Not used
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

    def __init__(self, field):
        self.node = field
        for attrib, value in field.items():
            if attrib == 'id':
                self.ident = value

        self.build_gui()

    def get_widget(self):
        '''
        Get widget.

        :returns: Gtk Object
        '''
        return self.widget

    def update_node(self):
        '''Update node.'''
        self.entry.update_node()


class FormguiFileException(Exception):
    '''Formgui File Exception'''


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


# pylint: disable=too-many-public-methods
class FormFile():
    '''
    Form File.

    :param filename: File name for form
    :raises: FormguiFormfileEmpty exception
    '''
    def __init__(self, filename):
        self._filename = filename
        try:
            self.doc = etree.parse(self._filename)
        except etree.XMLSyntaxError as err:
            raise FormguiFileNotValid("Form file %s is not valid! (%s)" %
                                      (filename, err))

        self.fields = []
        self.xsl_dir = None
        self.process_form(self.doc)

    def configure(self, config):
        '''
        Configure the form source directory.

        :param config: Config object
        '''
        self.xsl_dir = config.form_source_dir()

    def save_to(self, filename):
        '''
        Save to file.

        :param filename: File name to save to
        '''
        self.doc.write(filename)

    def export_to_string(self):
        '''
        Export to string.

        :returns: result of writing the string
        '''
        form_writer = HTMLFormWriter(self.ident, self.xsl_dir)
        return form_writer.writeString(self.doc)

    def get_xml(self):
        '''
        Get xml.

        :returns: XML serialized into a string'''
        root = self.doc.getroot()
        return root.tostring()

    def process_form(self, doc):
        '''
        Process Form.

        :param doc: ElementTree document
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

    # pylint: disable=no-self-use
    def __set_content(self, node, content):
        node.text = content

    def __get_xpath(self, path):
        result = self.doc.xpath(path)
        return result

    def get_path(self):
        '''
        Get path.

        :returns: List of x paths
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
        '''
        self.__add_path_element("e", element, True)

    def set_path_src(self, src):
        '''
        Set path source.

        :param src: Add source
        '''
        self.__add_path_element("src", src)

    def set_path_dst(self, dst):
        '''
        Set path destination.

        :param dst: Add destination to '''
        self.__add_path_element("dst", dst)

    def set_path_mid(self, mid):
        '''
        Set path mid.

        :param mid: mid
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
        '''
        return self.__get_path_element("src")

    def get_path_dst(self):
        '''
        Get path destination.

        :returns: Destination element
        '''
        return self.__get_path_element("dst")

    def get_path_mid(self):
        '''
        Get path mid.

        :returns: mid element
        '''
        return self.__get_path_element("mid")

    def get_field_value(self, field_id):
        '''
        Get field value.

        :param field_id: Field ID
        :returns: field x path or None
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
        :returns: Field caption or None
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
        :param value: Value to set
        '''
        els = self.__get_xpath("//form/field[@id='%s']/entry" % field_id)
        printlog("Formgui",
                 "   : Setting %s to %s (%i)" % (field_id, value, len(els)))
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
        '''
        dst = self.get_path_dst()
        if dst:
            return dst
        return self._try_get_fields("_auto_recip", "recip", "recipient")

    def get_sender_string(self):
        '''
        Get sender string.

        :returns: Sender string
        '''
        src = self.get_path_src()
        if src:
            return src
        return self._try_get_fields("_auto_sender", "sender")

    def get_attachments(self):
        '''
        Get attachments.

        :returns: list of attachments
        '''
        atts = []
        els = self.__get_xpath("//form/att")
        for element in els:
            print("-------- FormFile/get_attachments() ------------")
            print(etree.tostring(element).strip())
            if element.text:
                print(element.text.strip())
            else:
                print('None')
            name = None
            for attrib, value in els[0].items():
                if attrib == 'name':
                    name = value
                    break
            data = etree.tostring(element)
            atts.append((name, len(data)))

        return atts

    def get_attachment(self, name):
        '''Get attachment'''
        els = self.__get_xpath("//form/att[@name='%s']" % name)
        if els:
            print("-------- FormFile/get_attachment -name (%s) ------------" % name)
            print(etree.tostring(els[0]).strip())
            if els[0].text:
                print(els[0].text.strip())
            else:
                print('None')
        if len(els) == 1:
            data = etree.tostring(els[0])
            data = base64.b64decode(data)
            return zlib.decompress(data)

        raise FormguiFileMultipleAtts(
            "Internal Error: %i attachments named `%s'" % (len(els), name))

    def add_attachment(self, name, data):
        '''Add attachment'''
        try:
            att = self.get_attachment(name)
        # pylint: disable=broad-except
        except Exception as err:
            printlog("Formgui" "    : FormFile/add_attachment (%s -%s-)",
                     (type(err), err))
            att = None

        if att is not None:
            raise FormguiFileDuplicateAtt(
                "Already have an attachment named `%s'" % name)

        els = self.__get_xpath("//form")
        if els:
            print("-------- FormFile/add_attachment(%s) ------------" % name)
            print(etree.tostring(els[0]).strip())
            if els[0].text:
                print(els[0].text.strip())
            else:
                print('None')
        if len(els) == 1:
            # attnode = els[0].newChild(None, "att", None)
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
        '''
        els = self.__get_xpath("//form/att[@name='%s']" % name)
        if els:
            print("-------- FormFile/del_attachment(%s) ------------" % name)
            print(etree.tostring(els[0]).strip())
            if els[0].text:
                print(els[0].text.strip())
            else:
                print('None')
        if len(els) == 1:
            els[0].unlinkNode()


class FormDialog(FormFile, Gtk.Dialog):
    '''
    Form Dialog.

    :param _title: Title not used
    :param filename: Filename for form
    :param buttons: Optional buttons
    :param parent: Optional parent form
    '''
    def save_to(self, filename):
        '''Save to'''
        for field in self.fields:
            field.update_node()
        FormFile.save_to(self, filename)

    def process_fields(self, doc):
        '''
        Process fields.

        :param doc: XML ElementTree
        '''
        fields = doc.xpath("//form/field")
        for field in fields:
            try:
                self.fields.append(FormField(field))
            # pylint: disable=broad-except
            except Exception as err:
                printlog("Formgui",
                         "    : FormDialog/process_fields (%s -%s-)" %
                         (type(err), err))
                raise

    def export(self, outfile):
        '''
        Export to file.

        :param outfile: Output file.
        '''
        for field in self.fields:
            field.update_node()

        w = HTMLFormWriter(self.ident, self.xsl_dir)
        w.writeDoc(self.doc, outfile)

    def run_auto(self, save_file=None):
        '''
        Run auto.

        :param save_file: Filename to save, Default None'''
        if not save_file:
            save_file = self._filename

        run = self.run()
        if run != Gtk.ResponseType.CANCEL:
            self.save_to(save_file)

        return run

    def but_save(self, _widget, _data=None):
        '''
        Button save.

        :param _widget: Not used
        :param _data: Not used
        '''
        platform = dplatform.get_platform()
        outfile = platform.gui_save_file(default_name="%s.html" % self.ident)
        if not outfile:
            return

        try:
            self.export(outfile)
        # pylint: disable=broad-except
        except Exception as err:
            printlog("Formgui",
                     "    : FormFile/but_save (%s -%s-)" % (type(err), err))

            ed = Gtk.MessageDialog(buttons=Gtk.ButtonsType.OK,
                                   parent=self)
            ed.text = "Unable to open file"
            ed.format_secondary_text("Unable to open %s (%s)" %
                                     (outfile, err))
            ed.run()
            ed.destroy()

    def but_printable(self, _widget, _data=None):
        '''
        Button printable.

        :param _widget: Not used
        :param _data: Not used
        '''
        outfile = tempfile.NamedTemporaryFile(suffix=".html")
        name = outfile.name
        outfile.close()
        self.export(name)

        printlog("Formgui", "   : Exported to temporary file: %s" % name)
        dplatform.get_platform().open_html_file(name)

    # pylint: disable=no-self-use
    def calc_check(self, buffer, checkwidget):
        '''
        Calc check.

        :param buffer: Buffer to check
        :param checkwidget: Widget to use for check
        '''
        message = buffer.get_text(buffer.get_start_iter(),
                                  buffer.get_end_iter(), True)
        checkwidget.set_text("%i" % len(message.split()))

    def build_routing_widget(self):
        '''Build routing widget.'''
        tab = Gtk.Table.new(2, 2, False)

        lab = Gtk.Label.new(_("Source Callsign"))
        lab.show()
        tab.attach(lab, 0, 1, 0, 1, 0, 0, 2, 5)

        lab = Gtk.Label.new(_("Destination Callsign"))
        lab.show()
        tab.attach(lab, 0, 1, 1, 2, 0, 0, 2, 5)

        srcbox = Gtk.Entry()
        srcbox.set_text(self.get_path_src())
        srcbox.set_editable(False)
        srcbox.show()
        self._srcbox = srcbox
        tab.attach(srcbox, 1, 2, 0, 1,
                   Gtk.AttachOptions.EXPAND|Gtk.AttachOptions.FILL, 0)

        dstbox = Gtk.Entry()
        dstbox.set_text(self.get_path_dst())
        dstbox.show()
        self._dstbox = dstbox
        tab.attach(dstbox, 1, 2, 1, 2,
                   Gtk.AttachOptions.EXPAND|Gtk.AttachOptions.FILL, 0)

        exp = Gtk.Expander()
        exp.set_label(_("Routing Information"))
        exp.add(tab)
        tab.show()
        exp.set_expanded(True)
        exp.show()

        return exp

    def build_path_widget(self):
        '''Build path widget.'''
        pathels = self.get_path()

        pathbox = Gtk.Entry()
        pathbox.set_text(";".join(pathels))
        pathbox.set_property("editable", False)
        pathbox.show()

        expander = Gtk.Expander.new(_("Path"))
        expander.add(pathbox)
        expander.show()

        return expander

    # pylint: disable=too-many-locals, too-many-statements
    def build_att_widget(self):
        '''Build attachment widget.'''
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
        scrollw.add_with_viewport(self.attbox)
        scrollw.show()

        hbox.pack_start(scrollw, 1, 1, 1)

        def item_set(_box, key):
            natt = len(self.attbox.get_keys())
            printlog("Formgui", "   : Item %s set: %i\n" % (key, natt))
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
        def but_add(_but):
            fname = dplatform.get_platform().gui_open_file()
            if fname:
                name = os.path.basename(fname)
                file_handle = open(fname, "rb")
                data = file_handle.read()
                file_handle.close()
                self.add_attachment(name, data)
                self.attbox.set_item(name, name, len(data))

        add = Gtk.Button.new_with_label(_("Add"))
        add.connect("clicked", but_add)
        add.show()
        bbox.pack_start(add, 0, 0, 0)

        @run_or_error
        def but_rem(_but):
            name = self.attbox.get_selected()
            self.del_attachment(name)
            self.attbox.del_item(name)
            item_set(None, name)

        rem = Gtk.Button.new_with_label(_("Remove"))
        rem.connect("clicked", but_rem)
        rem.show()
        bbox.pack_start(rem, 0, 0, 0)

        @run_or_error
        def but_sav(_but):
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
        sav.connect("clicked", but_sav)
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

    # pylint: disable=too-many-locals
    def build_toolbar(self, editable):
        '''
        Build toolbar.

        :param editable: Editable State
        '''
        tb = Gtk.Toolbar()

        def close(_but, *_args):
            printlog("Formgui", "   : Closing")
            if editable:
                dialog = ask_for_confirmation("Close without saving?", self)
                if not dialog:
                    return True
            width, height = self.get_size()
            self._config.set("state", "form_%s_x" % self.ident, str(width))
            self._config.set("state", "form_%s_y" % self.ident, str(height))
            self.response(Gtk.ResponseType.CLOSE)
            return False
        def save(_but):
            self.response(RESPONSE_SAVE)
        def send(_but):
            self.response(RESPONSE_SEND)
        def svia(_but):
            self.response(RESPONSE_SEND_VIA)
        def reply(_but):
            self.response(RESPONSE_REPLY)
        def delete(_but):
            self.response(RESPONSE_DELETE)

        # We have to get in the way of the RESPONSE_DELETE_EVENT signal
        # to be able to catch the save
        # http://faq.pygtk.org/index.py?req=show&file=faq10.013.htp
        def reject_delete_response(dialog, response, *_args):
            if response == Gtk.ResponseType.DELETE_EVENT:
                dialog.emit_stop_by_name("response")

        send_tip = "Place this message in the Outbox for sending"
        svia_tip = "Place this message in the Outbox and send it directly " +\
            "to a specific station for relay"
        save_tip = "Save changes to this message"
        prnt_tip = "View the printable version of this form"
        rply_tip = "Compose a reply to this message"
        dele_tip = "Delete this message"

        # pylint: disable=fixme
        # FIX-ME: This should be consistent and use a null string for
        # images instead of putting a label string in the image field.
        if editable:
            buttons = [
                (_("Save"), "", save_tip, save),
                ("msg-send.png", _("Send"), send_tip, send),
                ("msg-send-via.png", _("Send via"), svia_tip, svia),
                (_("Print"), "", prnt_tip, self.but_printable),
                ]
        else:
            buttons = [
                ("msg-reply.png", _("Reply"), rply_tip, reply),
                # ("msg-send.png", _("Forward"),  send_tip, send),
                ("msg-send-via.png", _("Forward via"), svia_tip, svia),
                (_("Print"), "", prnt_tip, self.but_printable),
                (_("Delete"), "", dele_tip, delete),
                ]

        #self.connect("destroy", close)
        self.connect("delete-event", close)
        self.connect("response", reject_delete_response)

        button_index = 0
        for img, lab, tip, func in buttons:
            if not lab:
                ti = Gtk.ToolButton.new(None, img)
            else:
                icon = Gtk.Image()
                icon.set_from_pixbuf(self._config.ship_img(img))
                icon.show()
                ti = Gtk.ToolButton.new(icon, lab)
            ti.show()
            try:
                ti.set_tooltip_text(tip)
            except AttributeError:
                pass
            ti.connect("clicked", func)
            tb.insert(ti, button_index)
            button_index += 1

        tb.show()
        return tb

    # pylint: disable=too-many-branches, too-many-statements
    def build_gui(self, editable=True):
        '''
        Build gui.

        :param editable: Editable State, default True.
        '''
        self.vbox.pack_start(self.build_toolbar(editable), 0, 0, 0)

        tlabel = Gtk.Label()
        tlabel.set_markup("<big><b>%s</b></big>" % self.title_text)
        tlabel.show()

        if self.logo_path:
            image = Gtk.Image()
            try:
                base = self._config.get("settings", "form_logo_dir")
                printlog("Formgui",
                         "   : Logo path: %s" %
                         os.path.join(base, self.logo_path))
                image.set_from_file(os.path.join(base, self.logo_path))
                self.vbox.pack_start(image, 0, 0, 0)
                image.show()
            # pylint: disable=broad-except
            except Exception as err:
                printlog("Formgui",
                         "   : Unable to load or display logo %s: %s -%s-" %
                         (self.logo_path, type(err), err))
        self.vbox.pack_start(tlabel, 0, 0, 0)

        self.vbox.pack_start(self.build_routing_widget(), 0, 0, 0)

        #field_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 2)
        field_box = Gtk.Table.new(len(self.fields), 2, False)
        row = 0

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER,
                      Gtk.PolicyType.AUTOMATIC)
        sw.add_with_viewport(field_box)
        field_box.show()
        sw.show()
        self.vbox.pack_start(sw, 1, 1, 1)

        msg_field = None
        chk_field = None

        for field in self.fields:
            if field.ident == "_auto_check":
                chk_field = field
            elif field.ident == "_auto_message":
                msg_field = field
            # pylint: disable=fixme
            elif field.ident == "_auto_senderX": # FIXME
                if not field.entry.widget.get_text():
                    call = self._config.get("user", "callsign")
                    field.entry.widget.set_text(call)
                field.entry.widget.set_property("editable", False)
            elif field.ident == "_auto_position":
                if not field.entry.widget.get_text():
                    from . import mainapp # Dirty hack
                    pos = mainapp.get_mainapp().get_position()
                    field.entry.widget.set_text(pos.coordinates())

            label = Gtk.Label.new(field.caption)
            label.show()
            widget = field.get_widget()
            if field.entry.vertical:
                field_box.attach(label, 0, 2, row, row+1,
                                 Gtk.AttachOptions.SHRINK,
                                 Gtk.AttachOptions.SHRINK)
                row += 1
                field_box.attach(widget, 0, 2, row, row+1)
            elif field.entry.nolabel:
                field_box.attach(widget, 0, 2, row, row+1,
                                 Gtk.AttachOptions.SHRINK,
                                 Gtk.AttachOptions.SHRINK)
            else:
                field_box.attach(label, 0, 1, row, row+1,
                                 Gtk.AttachOptions.SHRINK,
                                 Gtk.AttachOptions.SHRINK, 5)
                field_box.attach(widget, 1, 2, row, row+1, yoptions=0)
            row += 1

        self.vbox.pack_start(self.build_att_widget(), 0, 0, 0)
        self.vbox.pack_start(self.build_path_widget(), 0, 0, 0)

        if msg_field and chk_field:
            mw = msg_field.entry.buffer
            cw = chk_field.entry.widget

            mw.connect("changed", self.calc_check, cw)

        self.set_editable(editable)

    def __init__(self, _title, filename, buttons=None, parent=None):
        self._buttons = (Gtk.ButtonsType.CANCEL, Gtk.ResponseType.CANCEL,
                         _("Save"), Gtk.ResponseType.OK)
        if buttons:
            self._buttons += buttons

        Gtk.Dialog.__init__(self, buttons=(), parent=parent)
        FormFile.__init__(self, filename)

        self.process_fields(self.doc)
        self.set_title(self.title_text)
        self.attbox = None
        self._srcbox = None
        self._dstbox = None

        # If this is invoked by the unit test, the mainapp class has
        # not been initialized, so does not have a config member.
        from . import mainapp
        try:
            self._config = mainapp.get_mainapp().config
        except AttributeError:
            from . import config
            self._config = config.DratsConfig(self)
            # WB8TYW: This duplication needs to be removed later.
            self.configure(self._config)
        try:
            x = self._config.getint("state", "form_%s_x" % self.ident)
            y = self._config.getint("state", "form_%s_y" % self.ident)
        except NoOptionError as err:
            printlog("Formgui",
                     "   : Unable to get form_%s_*: %s" % (self.ident, err))
            x = 300
            y = 500

        self.set_default_size(x, y)

        printlog("Formgui", "   : Form ID: %s" % self.ident)

    def update_dst(self):
        '''Update Destination.'''
        dst = self._dstbox.get_text()
        if "@" not in dst:
            dst = dst.upper()
        self.set_path_dst(dst)

    # pylint: disable=arguments-differ
    def run(self):
        '''
        Run the dialog.

        :returns: Dialog result
        '''
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

        :param editable: State to set'''
        for field in self.fields:
            field.set_editable(editable)


def main():
    '''Main program for unit testing'''

    lang = gettext.translation("D-RATS",
                               localedir="./locale",
                               languages=["en"],
                               fallback=True)
    lang.install()

    current_info = None

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
        printlog("response: %d = %s" % (response, act))
        printlog("info: %s" % info)

    form = FormDialog("Form", sys.argv[1])
    form.connect("response", form_done, current_info)
    form.run()
    form.destroy()

if __name__ == "__main__":
    main()
