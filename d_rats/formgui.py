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

import sys
import time
import os
import tempfile
import zlib
import base64

from lxml import etree
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
    '''XML escape'''
    data = {}
    for char, esc in XML_ESCAPES:
        data[char] = esc

    out = ""
    for char in string:
        out += data.get(char, char)

    return out

def xml_unescape(string):
    '''XML unescape'''

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
                printlog("Formgui", "   : XML Error: & with no ; (%s)" % err)
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
        '''Write'''
        doc = etree.fromstring(formxml)
        doc.write(outfile, pretty_print=True)


class HTMLFormWriter(FormWriter):
    '''HTML Form Writer'''

    def __init__(self, form_type, xsl_dir):
        self.xslpath = os.path.join(xsl_dir, "%s.xsl" % form_type)
        if not os.path.exists(self.xslpath):
            self.xslpath = os.path.join(xsl_dir, "default.xsl")

    def writeDoc(self, doc, outfile):
        '''Write Doc'''
        printlog("Formgui","   : Writing to %s" % outfile)
        styledoc = etree.parse(self.xslpath)
        style_sheet = etree.XSLT(styledoc)
        result = style_sheet(doc)
        result.write(outfile, pretty_print=True)

    def writeString(self, doc):
        '''Write String'''
        styledoc = etree.parse(self.xslpath)
        style_sheet = etree.XSLT(styledoc)
        result = style_sheet(doc)
        return etree.tostring(result, pretty_print=True).decode()

class FieldWidget():
    '''Field Widget'''

    def __init__(self, node):
        self.node = node
        self.caption = "Untitled Field"
        self.ident = "unknown"
        self.type = (self.__class__.__name__.replace("Widget", "")).lower()
        self.widget = None
        self.vertical = False
        self.nolabel = False

    def set_caption(self, caption):
        '''Set caption'''
        self.caption = caption

    def set_id(self, ident):
        '''Set identity'''
        self.ident = ident

    def make_container(self):
        '''make container'''
        return self.widget

    def get_widget(self):
        '''Get widget'''
        return self.make_container()

    def get_value(self):
        '''Get value'''

    def set_value(self, value):
        '''Set value'''

    def update_node(self):
        '''Update node'''
        value = xml_escape(self.get_value())
        if value:
            self.node.text = value

    def set_editable(self, editable):
        '''Set editable'''
        if self.widget:
            self.widget.set_sensitive(editable)
            self.widget.set_style(STYLE_BRIGHT_INSENSITIVE)


class TextWidget(FieldWidget):
    '''Text Widget'''

    def __init__(self, node):
        FieldWidget.__init__(self, node)

        if node.getchildren():
            text = xml_unescape(node.text.strip())
        else:
            text = ""

        self.widget = Gtk.Entry()
        self.widget.set_text(text)
        self.widget.show()

    def get_value(self):
        '''Get value'''
        return self.widget.get_text()

    def set_value(self, value):
        '''Set value'''
        self.widget.set_text(value)


class ToggleWidget(FieldWidget):
    '''Toggle Widget'''
    def __init__(self, node):
        FieldWidget.__init__(self, node)

        if node.children:
            try:
                # pylint: disable=eval-used
                status = eval(node.getContent().title())
            # pylint: disable=bare-except
            except:
                printlog("Formgui",
                         "   : Status of `%s' is invalid" % node.getContent())
                status = False
        else:
            status = False

        self.widget = Gtk.CheckButton.new_with_label(_("Yes"))
        self.widget.set_active(status)
        self.widget.show()

    def get_value(self):
        '''Get value'''
        return str(self.widget.get_active())


class MultilineWidget(FieldWidget):
    '''Multi Line Widget'''

    def __init__(self, node):
        FieldWidget.__init__(self, node)
        self.vertical = True

        if node.getchildren():
            text = xml_unescape(node.text.strip())
        else:
            text = ""

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
        '''Make container'''
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
        '''Get value'''
        return self.buffer.get_text(self.buffer.get_start_iter(),
                                    self.buffer.get_end_iter(), True)

    def set_value(self, value):
        '''Set value'''
        self.buffer.set_text(value)


class DateWidget(FieldWidget):
    '''Date Widget'''

    def __init__(self, node):
        FieldWidget.__init__(self, node)

        try:
            text = node.children.getContent().strip()
            (day, month, year) = text.split("-", 3)
        # pylint: disable=bare-except
        except:
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
        '''Get value'''
        return "%s-%s-%s" % (self.daybox.get_active_text(),
                             self.monthbox.get_active_text(),
                             self.yearbox.get_active_text())


class TimeWidget(FieldWidget):
    '''Time Widget'''
    def __init__(self, node):
        FieldWidget.__init__(self, node)

        try:
            text = node.children.getContent().strip()
            (hours, minutes, seconds) = (int(x) for x in text.split(":", 3))
        # pylint: disable=bare-except
        except:
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
        '''Get value'''
        return "%.0f:%02.0f:%02.0f" % (self.hour_a.get_value(),
                                       self.min_a.get_value(),
                                       self.sec_a.get_value())


class NumericWidget(FieldWidget):
    '''Numeric Widget'''
    def __init__(self, node):
        FieldWidget.__init__(self, node)

        try:
            min_value = float(node.prop("min"))
        # pylint: disable=bare-except
        except:
            min_value = 0

        try:
            max_value = float(node.prop("max"))
        # pylint: disable=bare-except
        except:
            max_value = 1000000.0

        try:
            initial = float(node.children.getContent())
        # pylint: disable=bare-except
        except:
            initial = 0

        self.adj = Gtk.Adjustment.new(initial, min_value, max_value, 1, 10, 0)
        self.widget = Gtk.SpinButton()
        self.widget.set_adjustment(self.adj)
        self.widget.show()

    def get_value(self):
        '''Get value'''
        return "%.0f" % self.adj.get_value()

    def set_value(self, value):
        '''Set value'''
        self.adj.set_value(float(value))


class ChoiceWidget(FieldWidget):
    '''Choice Widget'''

    def parse_choice(self, node):
        '''Parse choice'''
        if node.name != "choice":
            return

        try:
            content = xml_unescape(node.children.getContent().strip())
            self.choices.append(content)
            if node.prop("set"):
                self.default = content
        # pylint: disable=broad-except
        except Exception as err:
            printlog("Formgui",
                     "   : ChoiceWidget/parse_choice Error: %s" % err)
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
        '''Get value'''
        return self.widget.get_active_text()

    def update_node(self):
        '''Update node'''
        value = self.get_value()
        if not value:
            return

        child = self.node.children
        while child:
            if child.getContent() == value:
                if not child.hasProp("set"):
                    child.newProp("set", "y")
            else:
                child.unsetProp("set")

            child = child.next


class MultiselectWidget(FieldWidget):
    '''Multi Selection Widget'''

    def parse_choice(self, node):
        '''Parse choice'''
        if node.name != "choice":
            return

        try:
            content = xml_unescape(node.children.getContent().strip())
            self.store.append(row=(node.prop("set") == "y", content))
            self.choices.append((node.prop("set") == "y", content))
        # pylint: disable=broad-except
        except Exception as err:
            printlog("Formgui",
                     "   : MultiselectWidget/parse_choice Error: %s" % err)

    def toggle(self, _rend, path):
        '''toggle'''
        self.store[path][0] = not self.store[path][0]

    def make_selector(self):
        '''Make selector'''
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
        '''Make container'''
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
        '''Get value'''
        return ""

    def update_node(self):
        '''update_node'''
        vals = {}
        iter_value = self.store.get_iter_first()
        while iter_value:
            setval, name = self.store.get(iter_value, 0, 1)
            vals[name] = setval
            iter_value = self.store.iter_next(iter_value)

        child = self.node.children
        while child:
            choice = child.getContent().strip()
            if choice not in list(vals.keys()):
                vals[choice] = False

            if not child.hasProp("set"):
                child.newProp("set", vals[choice] and "y" or "n")
            else:
                child.setProp("set", vals[choice] and "y" or "n")

            child = child.next


class LabelWidget(FieldWidget):
    '''Label Widget'''

    def __init__(self, node):
        FieldWidget.__init__(self, node)
        self.nolabel = True

    def update_node(self):
        '''Update node'''
        # pass

    def make_container(self):
        '''Make container'''
        widget = Gtk.Label()
        widget.set_markup("<b><span color='blue'>%s</span></b>" % self.caption)
        _color = Gdk.color_parse("blue")
        # widget.modify_fg(Gtk.StateFlags.NORMAL, color)
        widget.show()

        return widget


class FormField():
    '''Form Field'''

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
        '''Set editable'''
        self.entry.set_editable(editable)

    # pylint: disable=no-self-use
    def get_caption_string(self, node):
        '''Get caption string'''
        return node.text.strip()
        # return node.getContent().strip()

    def build_entry(self, node, caption):
        '''build_entry'''
        widget_type = None
        for attrib, value in node.items():
            if attrib == 'type':
                widget_type = value
                break

        wtype = self.widget_types[widget_type]

        field = wtype(node)
        field.set_caption(caption)
        field.set_id(self.ident)

        return field

    def build_gui(self, node):
        '''build_gui'''
        self.caption = None
        self.entry = None

        children = node.getchildren()

        for child in children:
            if child.tag == "caption":
                cap_node = child
            elif child.tag == "entry":
                ent_node = child

        self.caption = self.get_caption_string(cap_node)
        self.entry = self.build_entry(ent_node, self.caption)
        self.widget = self.entry.get_widget()
        self.widget.show()

    def __init__(self, field):
        self.node = field
        for attrib, value in field.items():
            if attrib == 'id':
                self.ident = value

        self.build_gui(field)

    def get_widget(self):
        '''Get widget'''
        return self.widget

    def update_node(self):
        '''Update node'''
        self.entry.update_node()


# pylint: disable=too-many-public-methods
class FormFile():
    '''Form File'''
    def __init__(self, filename):
        self._filename = filename
        self.doc = etree.parse(self._filename)
        if not self.doc:
            raise Exception("Form file %s is empty!" % filename)

        self.fields = []
        self.xsl_dir = None
        self.process_form(self.doc)

    def configure(self, config):
        '''configure'''
        self.xsl_dir = config.form_source_dir()

    def save_to(self, filename):
        '''Save to'''
        file_handle = open(filename, "w")
        print(self.doc.serialize(), file=file_handle)
        file_handle.close()

    def export_to_string(self):
        '''Export to string'''
        form_writer = HTMLFormWriter(self.ident, self.xsl_dir)
        return form_writer.writeString(self.doc)

    def get_xml(self):
        '''Get xml'''
        return self.doc.serialize()

    def process_form(self, doc):
        '''Process Form'''
        forms = doc.xpath("//form")
        if len(forms) != 1:
            raise Exception("%i forms in document" % len(forms))

        for attrib, value in forms[0].items():
            if attrib == 'id':
                self.ident = value

        titles = doc.xpath("//form/title")
        if len(titles) != 1:
            raise Exception("%i titles in document" % len(titles))

        title = titles[0]
        self.title_text = title.text.strip()

        logos = doc.xpath("//form/logo")
        if len(logos) > 1:
            raise Exception("%i logos in document" % len(logos))
        elif len(logos) == 1:
            logo = logos[0]
            self.logo_path = logo.text.strip()
        else:
            self.logo_path = None

    # pylint: disable=no-self-use
    def __set_content(self, node, content):
        node.text = content

    def __get_xpath(self, path):
        result = self.doc.xpath(path)
        return result

    def get_path(self):
        '''Get path'''
        pathels = []
        for element in self.__get_xpath("//form/path/e"):
            pathels.append(element.getContent().strip())
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
        '''Add path element'''
        self.__add_path_element("e", element, True)

    def set_path_src(self, src):
        '''Set path source'''
        self.__add_path_element("src", src)

    def set_path_dst(self, dst):
        '''Set path destination'''
        self.__add_path_element("dst", dst)

    def set_path_mid(self, mid):
        '''Set path mid'''
        self.__add_path_element("mid", mid)

    def __get_path_element(self, name):
        els = self.__get_xpath("//form/path/%s" % name)
        if els:
            return els[0].getContent().strip()
        return ""

    def get_path_src(self):
        '''Get path source'''
        return self.__get_path_element("src")

    def get_path_dst(self):
        '''Get path destination'''
        return self.__get_path_element("dst")

    def get_path_mid(self):
        '''Get path mid'''
        return self.__get_path_element("mid")

    def get_field_value(self, field_id):
        '''Get field value'''
        els = self.__get_xpath("//form/field[@id='%s']/entry" % field_id)
        if len(els) == 1:
            return xml_unescape(els[0].getContent().strip())
        if len(els) > 1:
            raise Exception("More than one id=%s node!" % field_id)
        else:
            return None

    def get_field_caption(self, field_id):
        '''Get field caption'''
        els = self.__get_xpath("//form/field[@id='%s']/caption" % field_id)
        if len(els) == 1:
            return xml_unescape(els[0].getContent().strip())
        if len(els) > 1:
            raise Exception("More than one id=%s node!" % field_id)
        else:
            return None

    def set_field_value(self, field_id, value):
        '''Set field value'''
        els = self.__get_xpath("//form/field[@id='%s']/entry" % field_id)
        printlog("Formgui",
                 "   : Setting %s to %s (%i)" % (field_id, value, len(els)))
        if len(els) == 1:
            if els[0].prop("type") == "multiline":
                self.__set_content(els[0], value)
            else:
                self.__set_content(els[0], value.strip())

    def _try_get_fields(self, *names):
        for field in names:
            try:
                val = self.get_field_value(field)
                if val is not None:
                    return val
            # pylint: disable=broad-except
            except Exception:
                pass
        return "Unknown"

    def get_subject_string(self):
        '''Get subject string'''
        subj = self._try_get_fields("_auto_subject", "subject")
        if subj != "Unknown":
            return subj.replace("\r", "").replace("\n", "")

        return "%s#%s" % (self.get_path_src(),
                          self._try_get_fields("_auto_number"))

    def get_recipient_string(self):
        '''Get recipient string'''
        dst = self.get_path_dst()
        if dst:
            return dst
        return self._try_get_fields("_auto_recip", "recip", "recipient")

    def get_sender_string(self):
        '''Get sender string'''
        src = self.get_path_src()
        if src:
            return src
        else:
            return self._try_get_fields("_auto_sender", "sender")

    def get_attachments(self):
        '''Get attachments'''
        atts = []
        els = self.__get_xpath("//form/att")
        for el in els:
            name = el.prop("name")
            data = el.getContent()
            atts.append((name, len(data)))

        return atts

    def get_attachment(self, name):
        '''Get attachment'''
        els = self.__get_xpath("//form/att[@name='%s']" % name)
        if len(els) == 1:
            data = els[0].getContent()
            data = base64.b64decode(data)
            return zlib.decompress(data)
        raise Exception("Internal Error: %i attachments named `%s'" %
                        (len(els), name))

    def add_attachment(self, name, data):
        '''Add attachment'''
        try:
            att = self.get_attachment(name)
        # pylint: disable=broad-except
        except Exception:
            att = None

        if att is not None:
            raise Exception("Already have an attachment named `%s'" % name)

        els = self.__get_xpath("//form")
        if len(els) == 1:
            attnode = els[0].newChild(None, "att", None)
            attnode.setProp("name", name)
            data = zlib.compress(data, 9)
            data = base64.b64encode(data)
            self.__set_content(attnode, data)

    def del_attachment(self, name):
        '''Del attachment'''
        els = self.__get_xpath("//form/att[@name='%s']" % name)
        if len(els) == 1:
            els[0].unlinkNode()


class FormDialog(FormFile, Gtk.Dialog):
    '''Form Diallog'''

    def save_to(self, filename):
        '''Save to'''
        for field in self.fields:
            field.update_node()
        FormFile.save_to(self, filename)

    def process_fields(self, doc):
        '''Process fields'''
        fields = doc.xpath("//form/field")
        for field in fields:
            try:
                self.fields.append(FormField(field))
            except Exception as err:
                printlog(err)
                raise

    def export(self, outfile):
        '''export'''
        for field in self.fields:
            field.update_node()

        w = HTMLFormWriter(self.ident, self.xsl_dir)
        w.writeDoc(self.doc, outfile)

    def run_auto(self, save_file=None):
        '''Run auto'''
        if not save_file:
            save_file = self._filename

        run = self.run()
        if run != Gtk.ResponseType.CANCEL:
            self.save_to(save_file)

        return run

    def but_save(self, _widget, _data=None):
        '''but save'''
        platform = dplatform.get_platform()
        outfile = platform.gui_save_file(default_name="%s.html" % self.ident)
        if not outfile:
            return

        try:
            self.export(outfile)
        # pylint: disable=broad-except
        except Exception as err:
            ed = Gtk.MessageDialog(buttons=Gtk.ButtonsType.OK,
                                   parent=self)
            ed.text = "Unable to open file"
            ed.format_secondary_text("Unable to open %s (%s)" %
                                     (outfile, err))
            ed.run()
            ed.destroy()

    def but_printable(self, _widget, _data=None):
        '''but printable'''
        outfile = tempfile.NamedTemporaryFile(suffix=".html")
        name = outfile.name
        outfile.close()
        self.export(name)

        printlog("Formgui", "   : Exported to temporary file: %s" % name)
        dplatform.get_platform().open_html_file(name)

    # pylint: disable=no-self-use
    def calc_check(self, buffer, checkwidget):
        '''Calc check'''
        message = buffer.get_text(buffer.get_start_iter(),
                                  buffer.get_end_iter(), True)
        checkwidget.set_text("%i" % len(message.split()))

    def build_routing_widget(self):
        '''Build routing widget'''
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
        '''Build path widget'''
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
        '''Build att widget'''
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
                    raise Exception("Unable to extract attachment")
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
        '''Build toolbar'''
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
                #("msg-send.png", _("Forward"),  send_tip, send),
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
                ti = Gtk.ToolButton(img)
            else:
                icon = Gtk.Image()
                icon.set_from_pixbuf(self._config.ship_img(img))
                icon.show()
                ti = Gtk.ToolButton(icon, lab)
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
        '''Build gui'''
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
                         "   : Unable to load or display logo %s: %s" %
                         (self.logo_path, err))
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
        '''Update destination'''
        dst = self._dstbox.get_text()
        if "@" not in dst:
            dst = dst.upper()
        self.set_path_dst(dst)

    # pylint: disable=arguments-differ
    def run(self):
        '''Run'''
        # pylint: disable=no-member
        self.vbox.set_spacing(5)
        self.build_gui()
        self.set_size_request(380, 450)

        run_dialog = Gtk.Dialog.run(self)
        self.update_dst()

        return run_dialog

    def set_editable(self, editable):
        '''Set editable'''
        for field in self.fields:
            field.set_editable(editable)


def main():
    '''Main program for unit testing'''

    import gettext
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
