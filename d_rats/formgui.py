#
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

#importing printlog() wrapper
from .debug import printlog

import sys
import time
import os
import tempfile
import zlib
import base64

import libxml2
import libxslt

import gtk
import gobject
import pango

from .miscwidgets import make_choice, KeyedListWidget
from .utils import run_or_error
from .ui.main_common import ask_for_confirmation
from . import dplatform
from . import spell
from six.moves import range

test = """
<xml>
  <form id="testform">
    <title>Test Form</title>
    <field id="foo">
      <caption>Name</caption>
      <entry type="text">Foobar</entry>
    </field>
    <field id="bar">
      <entry type="multiline"/>
    </field>
    <field id="baz">
      <caption>Is this person okay?</caption>
      <entry type="toggle">True</entry>
    </field>
  </form>
</xml>

"""

xml_escapes = [("<", "&lt;"),
               (">", "&gt;"),
               ("&", "&amp;"),
               ('"', "&quot;"),
               ("'", "&apos;")]

RESPONSE_SEND     = -900
RESPONSE_SAVE     = -901
RESPONSE_REPLY    = -902
RESPONSE_DELETE   = -903
RESPONSE_SEND_VIA = -904

style = gtk.Style()
for i in [style.fg, style.bg, style.base]:
            i[gtk.STATE_INSENSITIVE] = i[gtk.STATE_NORMAL]
STYLE_BRIGHT_INSENSITIVE = style
del style
del i

def xml_escape(string):
    d = {}
    for char, esc in xml_escapes:
        d[char] = esc

    out = ""
    for i in string:
        out += d.get(i, i)

    return out

def xml_unescape(string):
    d = {}
    for char, esc in xml_escapes:
        d[esc] = char

    out = ""
    i = 0
    while i < len(string):
        if string[i] != "&":
            out += string[i]
            i += 1
        else:
            try:
                semi = string[i:].index(";") + i + 1
            except:
                printlog("Formgui","   : XML Error: & with no ;")
                i += 1
                continue

            esc = string[i:semi]

            if not esc:
                printlog("Formgui","   : No escape: %i:%i" % (i, semi))
                i += 1
                continue

            if string[i:semi] in d:
                out += d[esc]
            else:
                printlog("Formgui","   : XML Error: No such escape: `%s'" % esc)
                
            i += len(esc)

    return out

class FormWriter(object):
    def write(self, formxml, outfile):
        doc = libxml2.parseMemory(formxml, len(formxml))
        doc.saveFile(outfile)
        doc.freeDoc()

class HTMLFormWriter(FormWriter):
    def __init__(self, type, xsl_dir):
        self.xslpath = os.path.join(xsl_dir, "%s.xsl" % type)
        if not os.path.exists(self.xslpath):
            self.xslpath = os.path.join(xsl_dir, "default.xsl")
        
    def writeDoc(self, doc, outfile):
        printlog("Formgui","   : Writing to %s" % outfile)
        styledoc = libxml2.parseFile(self.xslpath)
        style = libxslt.parseStylesheetDoc(styledoc)
        result = style.applyStylesheet(doc, None)
        style.saveResultToFilename(outfile, result, 0)
        # FIXME!!
        #style.freeStylesheet()
        #styledoc.freeDoc()
        #doc.freeDoc()
        #result.freeDoc()

    def writeString(self, doc):
        styledoc = libxml2.parseFile(self.xslpath)
        style = libxslt.parseStylesheetDoc(styledoc)
        result = style.applyStylesheet(doc, None)
        return style.saveResultToString(result)

class FieldWidget(object):
    def __init__(self, node):
        self.node = node
        self.caption = "Untitled Field"
        self.id = "unknown"
        self.type = (self.__class__.__name__.replace("Widget", "")).lower()
        self.widget = None
        self.vertical = False
        self.nolabel = False

    def set_caption(self, caption):
        self.caption = caption

    def set_id(self, id):
        self.id = id

    def make_container(self):
        return self.widget

    def get_widget(self):
        return self.make_container()

    def get_value(self):
        pass

    def set_value(self, value):
        pass

    def update_node(self):
        child = self.node.children
        while child:
            if child.type == "text":
                child.unlinkNode()

            child = child.next

        value = xml_escape(self.get_value())
        if value:
            self.node.addContent(value)

    def set_editable(self, editable):
        if self.widget:
            self.widget.set_sensitive(editable)
            self.widget.set_style(STYLE_BRIGHT_INSENSITIVE)

class TextWidget(FieldWidget):
    def __init__(self, node):
        FieldWidget.__init__(self, node)

        if node.children:
            text = xml_unescape(node.getContent().strip())
        else:
            text = ""

        self.widget = gtk.Entry()
        self.widget.set_text(text)
        self.widget.show()

    def get_value(self):
        return self.widget.get_text()

    def set_value(self, value):
        self.widget.set_text(value)

class ToggleWidget(FieldWidget):
    def __init__(self, node):
        FieldWidget.__init__(self, node)

        if node.children:
            try:
                status = eval(node.getContent().title())
            except:
                printlog("Formgui","   : Status of `%s' is invalid" % node.getContent())
                status = False
        else:
            status = False

        self.widget = gtk.CheckButton("Yes")
        self.widget.set_active(status)
        self.widget.show()

    def get_value(self):
        return str(self.widget.get_active())

class MultilineWidget(FieldWidget):
    def __init__(self, node):
        FieldWidget.__init__(self, node)
        self.vertical = True

        if node.children:
            text = xml_unescape(node.children.getContent().strip())
        else:
            text = ""

        self.buffer = gtk.TextBuffer()
        self.buffer.set_text(text)
        self.widget = gtk.TextView(self.buffer)
        self.widget.show()
        self.widget.set_size_request(175, 200)
        self.widget.set_wrap_mode(gtk.WRAP_WORD)

        from . import mainapp
        config = mainapp.get_mainapp().config
        if config.getboolean("prefs", "check_spelling"):
            spell.prepare_TextBuffer(self.buffer)

    def make_container(self):

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.add(self.widget)
        return sw

        vbox = gtk.VBox(False, 2)

        label = gtk.Label(self.caption)
        vbox.pack_start(label, 0,0,0)
        vbox.pack_start(sw, 0,0,0)

        label.show()
        vbox.show()
        sw.show()

        return vbox

    def get_value(self):
        return self.buffer.get_text(self.buffer.get_start_iter(),
                                    self.buffer.get_end_iter())

    def set_value(self, value):
        self.buffer.set_text(value)

class DateWidget(FieldWidget):
    def __init__(self, node):
        FieldWidget.__init__(self, node)

        try:
            text = node.children.getContent().strip()
            (d, m, y) = text.split("-", 3)
        except:
            y = time.strftime("%Y")
            m = time.strftime("%b")
            d = time.strftime("%d")

        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        days = [str("%02i" % x) for x in range(1,32)]
        
        years = [str(x) for x in range(int(y)-2, int(y)+2)]

        self.monthbox = make_choice(months, False, m)
        self.daybox = make_choice(days, False, d)
        self.yearbox = make_choice(years, False, y)

        self.widget = gtk.HBox(False, 2)
        self.widget.pack_start(self.monthbox, 0,0,0)
        self.widget.pack_start(self.daybox, 0,0,0)
        self.widget.pack_start(self.yearbox, 0,0,0)

        self.monthbox.show()
        self.daybox.show()
        self.yearbox.show()

        self.widget.show()

    def get_value(self):
        return "%s-%s-%s" % (self.daybox.get_active_text(),
                             self.monthbox.get_active_text(),
                             self.yearbox.get_active_text())

class TimeWidget(FieldWidget):
    def __init__(self, node):
        FieldWidget.__init__(self, node)

        try:
            text = node.children.getContent().strip()
            (h, m, s) = (int(x) for x in text.split(":", 3))
        except:
            #FIXME
            #config = mainapp.get_mainapp().config
            if False and config.getboolean("prefs", "useutc"):
                t = time.gmtime()
            else:
                t = time.localtime()

            h = int(time.strftime("%H", t))
            m = int(time.strftime("%M", t))
            s = int(time.strftime("%S", t))

        self.hour_a = gtk.Adjustment(h, 0, 23, 1)
        self.min_a = gtk.Adjustment(m, 0, 59, 1, 10)
        self.sec_a = gtk.Adjustment(s, 0, 59, 1, 10)

        self.hour = gtk.SpinButton(self.hour_a)
        self.min = gtk.SpinButton(self.min_a)
        self.sec = gtk.SpinButton(self.sec_a)

        self.widget = gtk.HBox(False, 2)
        self.widget.pack_start(self.hour, 0,0,0)
        self.widget.pack_start(self.min, 0,0,0)
        self.widget.pack_start(self.sec, 0,0,0)

        self.hour.show()
        self.min.show()
        self.sec.show()
        self.widget.show()

    def get_value(self):
        return "%.0f:%02.0f:%02.0f" % (self.hour_a.get_value(),
                                       self.min_a.get_value(),
                                       self.sec_a.get_value())

class NumericWidget(FieldWidget):
    def __init__(self, node):
        FieldWidget.__init__(self, node)

        try:
            min = float(node.prop("min"))
        except:
            min = 0

        try:
            max = float(node.prop("max"))
        except:
            max = 1000000.0

        try:
            initial = float(node.children.getContent())
        except:
            initial = 0

        self.adj = gtk.Adjustment(initial, min, max, 1, 10)
        self.widget = gtk.SpinButton(self.adj)
        self.widget.show()

    def get_value(self):
        return "%.0f" % self.adj.get_value()

    def set_value(self, value):
        self.adj.set_value(float(value))

class ChoiceWidget(FieldWidget):
    def parse_choice(self, node):
        if node.name != "choice":
            return

        try:
            content = xml_unescape(node.children.getContent().strip())
            self.choices.append(content)
            if node.prop("set"):
                self.default = content
        except:
            pass

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
        return self.widget.get_active_text()

    def update_node(self):
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
    def parse_choice(self, node):
        if node.name != "choice":
            return

        try:
            content = xml_unescape(node.children.getContent().strip())
            self.store.append(row=(node.prop("set") == "y", content))
            self.choices.append((node.prop("set") == "y", content))
        except Exception as e:
            printlog("Formgui","   : Error: %s" % e)
            pass

    def toggle(self, rend, path):
        self.store[path][0] = not self.store[path][0]

    def make_selector(self):
        self.store = gtk.ListStore(gobject.TYPE_BOOLEAN,
                                   gobject.TYPE_STRING)
        self.view = gtk.TreeView(self.store)

        rend = gtk.CellRendererToggle()
        rend.connect("toggled", self.toggle)
        col = gtk.TreeViewColumn("", rend, active=0)
        self.view.append_column(col)

        rend = gtk.CellRendererText()
        col = gtk.TreeViewColumn("", rend, text=1)
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
        vbox = gtk.VBox(False, 2)

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.add(self.widget)

        if self.caption:
            label = gtk.Label(self.caption)
            vbox.pack_start(label, 0,0,0)
            label.show()
        vbox.pack_start(sw, 0,0,0)

        vbox.show()
        sw.show()

        return vbox

    def get_value(self):
        return ""

    def update_node(self):
        vals = {}
        iter = self.store.get_iter_first()
        while iter:
            setval, name = self.store.get(iter, 0, 1)
            vals[name] = setval
            iter = self.store.iter_next(iter)

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
    def __init__(self, node):
        FieldWidget.__init__(self, node)
        self.nolabel = True

    def update_node(self):
        pass

    def make_container(self):
        widget = gtk.Label()
        widget.set_markup("<b><span color='blue'>%s</span></b>" % self.caption)
        color = gtk.gdk.color_parse("blue")
        #widget.modify_fg(gtk.STATE_NORMAL, color)
        widget.show()

        return widget

class FormField(object):
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
        self.entry.set_editable(editable)

    def get_caption_string(self, node):
        return node.getContent().strip()

    def build_entry(self, node, caption):
        type = node.prop("type")

        wtype = self.widget_types[type]

        field = wtype(node)
        field.set_caption(caption)
        field.set_id(self.id)

        return field        

    def build_gui(self, node):
        self.caption = None
        self.entry = None
        
        child = node.children

        while child:
            if child.name == "caption":
                cap_node = child
            elif child.name == "entry":
                ent_node = child

            child = child.next

        self.caption = self.get_caption_string(cap_node)
        self.entry = self.build_entry(ent_node, self.caption)
        self.widget = self.entry.get_widget()
        self.widget.show()

    def __init__(self, field):
        self.node = field
        self.id = field.prop("id")
        self.build_gui(field)

    def get_widget(self):
        return self.widget

    def update_node(self):
        self.entry.update_node()

class FormFile(object):
    def __init__(self, filename):
        self._filename = filename
        f = open(self._filename)
        data = f.read()
        f.close()

        if not data:
            raise Exception("Form file %s is empty!" % filename)

        self.fields = []

        self.doc = libxml2.parseMemory(data, len(data))
        self.process_form(self.doc)

    def configure(self, config):
        self.xsl_dir = config.form_source_dir()

    def __del__(self):
        self.doc.freeDoc()

    def save_to(self, filename):
        f = open(filename, "w")
        print(self.doc.serialize(), file=f)
        f.close()

    def export_to_string(self):
        w = HTMLFormWriter(self.id, self.xsl_dir)
        return w.writeString(self.doc)
        
    def get_xml(self):
        return self.doc.serialize()

    def process_form(self, doc):
        ctx = doc.xpathNewContext()
        forms = ctx.xpathEval("//form")
        if len(forms) != 1:
            raise Exception("%i forms in document" % len(forms))

        form = forms[0]
        
        self.id = form.prop("id")

        titles = ctx.xpathEval("//form/title")
        if len(titles) != 1:
            raise Exception("%i titles in document" % len(titles))

        title = titles[0]

        self.title_text = title.children.getContent().strip()

        logos = ctx.xpathEval("//form/logo")
        if len(logos) > 1:
            raise Exception("%i logos in document" % len(logos))
        elif len(logos) == 1:
            logo = logos[0]
            self.logo_path = logo.children.getContent().strip()
        else:
            self.logo_path = None

        ctx.xpathFreeContext()

    def __set_content(self, node, content):
        child = node.children
        while child:
            if child.type == "text":
                child.unlinkNode()
            child = child.next
        node.addContent(content)

    def __get_xpath(self, path):
        ctx = self.doc.xpathNewContext()
        result = ctx.xpathEval(path)
        ctx.xpathFreeContext()
        return result

    def get_path(self):
        pathels = []
        for element in self.__get_xpath("//form/path/e"):
            pathels.append(element.getContent().strip())
        return pathels
    
    def __get_path(self):
        els = self.__get_xpath("//form/path")
        if not els:
            ctx = self.doc.xpathNewContext()
            form, = ctx.xpathEval("//form")
            ctx.xpathFreeContext()
            return form.newChild(None, "path", None)
        else:
            return els[0]

    def __add_path_element(self, name, element, append=False):
        path = self.__get_path()

        if append:
            path.newChild(None, name, element)
            return

        els = self.__get_xpath("//form/path/%s" % name)
        if not els:
            path.newChild(None, name, element)
            return

        self.__set_content(els[0], element)

    def add_path_element(self, element):
        self.__add_path_element("e", element, True)

    def set_path_src(self, src):
        self.__add_path_element("src", src)

    def set_path_dst(self, dst):
        self.__add_path_element("dst", dst)

    def set_path_mid(self, mid):
        self.__add_path_element("mid", mid)

    def __get_path_element(self, name):
        els = self.__get_xpath("//form/path/%s" % name)
        if els:
            return els[0].getContent().strip()
        else:
            return ""

    def get_path_src(self):
        return self.__get_path_element("src")

    def get_path_dst(self):
        return self.__get_path_element("dst")

    def get_path_mid(self):
        return self.__get_path_element("mid")

    def get_field_value(self, id):
        els = self.__get_xpath("//form/field[@id='%s']/entry" % id)
        if len(els) == 1:
            return xml_unescape(els[0].getContent().strip())
        elif len(els) > 1:
            raise Exception("More than one id=%s node!" % id)
        else:
            return None

    def get_field_caption(self, id):
        els = self.__get_xpath("//form/field[@id='%s']/caption" % id)
        if len(els) == 1:
            return xml_unescape(els[0].getContent().strip())
        elif len(els) > 1:
            raise Exception("More than one id=%s node!" % id)
        else:
            return None

    def set_field_value(self, id, value):
        els = self.__get_xpath("//form/field[@id='%s']/entry" % id)
        printlog("Formgui","   : Setting %s to %s (%i)" % (id, value, len(els)))
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
            except Exception as e:
                pass
        return "Unknown"

    def get_subject_string(self):
        subj = self._try_get_fields("_auto_subject", "subject")
        if subj != "Unknown":
            return subj.replace("\r", "").replace("\n", "")

        return "%s#%s" % (self.get_path_src(),
                          self._try_get_fields("_auto_number"))

    def get_recipient_string(self):
        dst = self.get_path_dst()
        if dst:
            return dst
        else:
            return self._try_get_fields("_auto_recip", "recip", "recipient")

    def get_sender_string(self):
        src = self.get_path_src()
        if src:
            return src
        else:
            return self._try_get_fields("_auto_sender", "sender")

    def get_attachments(self):
        atts = []
        els = self.__get_xpath("//form/att")
        for el in els:
            name = el.prop("name")
            data = el.getContent()
            atts.append((name, len(data)))

        return atts

    def get_attachment(self, name):
        els = self.__get_xpath("//form/att[@name='%s']" % name)
        if len(els) == 1:
            data = els[0].getContent()
            data = base64.b64decode(data)
            return zlib.decompress(data)
        else:
            raise Exception("Internal Error: %i attachments named `%s'" % \
                                (len(els), name))

    def add_attachment(self, name, data):
        try:
            att = self.get_attachment(name)
        except Exception as e:
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
        els = self.__get_xpath("//form/att[@name='%s']" % name)
        if len(els) == 1:
            els[0].unlinkNode()

class FormDialog(FormFile, gtk.Dialog):
    def save_to(self, *args):
        for f in self.fields:
            f.update_node()
        FormFile.save_to(self, *args)

    def process_fields(self, doc):
        ctx = doc.xpathNewContext()
        fields = ctx.xpathEval("//form/field")
        ctx.xpathFreeContext()
        for f in fields:
            try:
                self.fields.append(FormField(f))
            except Exception as e:
                raise
                printlog(e)

    def export(self, outfile):
        for f in self.fields:
            f.update_node()

        w = HTMLFormWriter(self.id, self.xsl_dir)
        w.writeDoc(self.doc, outfile)

    def run_auto(self, save_file=None):
        if not save_file:
            save_file = self._filename

        r = self.run()
        if r != gtk.RESPONSE_CANCEL:
            self.save_to(save_file)

        return r

    def but_save(self, widget, data=None):
        p = dplatform.get_platform()
        f = p.gui_save_file(default_name="%s.html" % self.id)
        if not f:
            return

        try:
            self.export(f)
        except Exception as e:
            ed = gtk.MessageDialog(buttons=gtk.BUTTONS_OK,
                                   parent=self)
            ed.text = "Unable to open file"
            ed.format_secondary_text("Unable to open %s (%s)" % (f, e))
            ed.run()
            ed.destroy()

    def but_printable(self, widget, data=None):
        f = tempfile.NamedTemporaryFile(suffix=".html")
        name = f.name
        f.close()
        self.export(name)

        printlog("Formgui","   : Exported to temporary file: %s" % name)
        dplatform.get_platform().open_html_file(name)

    def calc_check(self, buffer, checkwidget):
        message = buffer.get_text(buffer.get_start_iter(),
                                  buffer.get_end_iter())
        checkwidget.set_text("%i" % len(message.split()))

    def build_routing_widget(self):
        tab = gtk.Table(2, 2)

        lab = gtk.Label(_("Source Callsign"))
        lab.show()
        tab.attach(lab, 0, 1, 0, 1, 0, 0, 2, 5)

        lab = gtk.Label(_("Destination Callsign"))
        lab.show()
        tab.attach(lab, 0, 1, 1, 2, 0, 0, 2, 5)

        srcbox = gtk.Entry()
        srcbox.set_text(self.get_path_src())
        srcbox.set_editable(False)
        srcbox.show()
        self._srcbox = srcbox
        tab.attach(srcbox, 1, 2, 0, 1, gtk.EXPAND|gtk.FILL, 0)

        dstbox = gtk.Entry()
        dstbox.set_text(self.get_path_dst())
        dstbox.show()
        self._dstbox = dstbox
        tab.attach(dstbox, 1, 2, 1, 2, gtk.EXPAND|gtk.FILL, 0)

        exp = gtk.Expander()
        exp.set_label(_("Routing Information"))
        exp.add(tab)
        tab.show()
        exp.set_expanded(True)
        exp.show()

        return exp

    def build_path_widget(self):
        pathels = self.get_path()

        pathbox = gtk.Entry()
        pathbox.set_text(";".join(pathels))
        pathbox.set_property("editable", False)
        pathbox.show()

        expander = gtk.Expander("Path")
        expander.add(pathbox)
        expander.show()

        return expander

    def build_att_widget(self):
        hbox = gtk.HBox(False, 2)

        cols = [(gobject.TYPE_STRING, "KEY"),
                (gobject.TYPE_STRING, _("Name")),
                (gobject.TYPE_INT, _("Size (bytes)"))]
        self.attbox = KeyedListWidget(cols)
        self.attbox.set_resizable(0, True)
        self.attbox.set_expander(0)
        self.attbox.show()
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.add_with_viewport(self.attbox)
        sw.show()

        hbox.pack_start(sw, 1, 1, 1)

        def item_set(box, key):
            natt = len(self.attbox.get_keys())
            printlog("Formgui","   : Item %s set: %i\n" % (key, natt))
            if natt:
                msg = _("Attachments") + " (%i)" % natt
                attexp.set_label("<span color='blue'>%s</span>" % msg)
            else:
                attexp.set_label(_("Attachments"))

        self.attbox.connect("item-set", item_set)
        
        bbox = gtk.VBox(False, 2)
        bbox.show()
        hbox.pack_start(bbox, 0, 0, 0)

        @run_or_error
        def but_add(but):
            fn = dplatform.get_platform().gui_open_file()
            if fn:
                name = os.path.basename(fn)
                f = open(fn, "rb")
                data = f.read()
                f.close()
                self.add_attachment(name, data)
                self.attbox.set_item(name, name, len(data))

        add = gtk.Button(_("Add"), gtk.STOCK_ADD)
        add.connect("clicked", but_add)
        add.show()
        bbox.pack_start(add, 0, 0, 0)

        @run_or_error
        def but_rem(but):
            name = self.attbox.get_selected()
            self.del_attachment(name)
            self.attbox.del_item(name)
            item_set(None, name)

        rem = gtk.Button(_("Remove"), gtk.STOCK_REMOVE)
        rem.connect("clicked", but_rem)
        rem.show()
        bbox.pack_start(rem, 0, 0, 0)        

        @run_or_error
        def but_sav(but):
            name = self.attbox.get_selected()
            if not name:
                return
            fn = dplatform.get_platform().gui_save_file(default_name=name)
            if fn:
                f = open(fn, "wb")
                data = self.get_attachment(name)
                if not data:
                    raise Exception("Unable to extract attachment")
                f.write(data)
                f.close()

        sav = gtk.Button(_("Save"), gtk.STOCK_SAVE)
        sav.connect("clicked", but_sav)
        sav.show()
        bbox.pack_start(sav, 0, 0, 0)

        attexp = gtk.Expander(_("Attachments"))
        attexp.set_use_markup(True)
        hbox.show()
        attexp.add(hbox)
        attexp.show()


        atts = self.get_attachments()
        for name, size in atts:
            self.attbox.set_item(name, name, size)

        return attexp

    def build_toolbar(self, editable):
        tb = gtk.Toolbar()

        def close(but, *args):
            printlog("Formgui","   : Closing")
            if editable:
                d = ask_for_confirmation("Close without saving?", self)
                if not d:
                    return True
            w, h = self.get_size()
            self._config.set("state", "form_%s_x" % self.id, str(w))
            self._config.set("state", "form_%s_y" % self.id, str(h))
            self.response(gtk.RESPONSE_CLOSE)
            return False
        def save(but):
            self.response(RESPONSE_SAVE)
        def send(but):
            self.response(RESPONSE_SEND)
        def svia(but):
            self.response(RESPONSE_SEND_VIA)
        def reply(but):
            self.response(RESPONSE_REPLY)
        def delete(but):
            self.response(RESPONSE_DELETE)

        # We have to get in the way of the RESPONSE_DELETE_EVENT signal
        # to be able to catch the save
        # http://faq.pygtk.org/index.py?req=show&file=faq10.013.htp
        def reject_delete_response(dialog, response, *args):
            if response == gtk.RESPONSE_DELETE_EVENT:
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
                (gtk.STOCK_SAVE, "",            save_tip, save),
                ("msg-send.png", _("Send"),     send_tip, send),
                ("msg-send-via.png", _("Send via"), svia_tip, svia),
                (gtk.STOCK_PRINT, "",           prnt_tip, self.but_printable),
                ]
        else:
            buttons = [
                ("msg-reply.png", _("Reply"),    rply_tip, reply),
                #("msg-send.png",  _("Forward"),  send_tip, send),
                ("msg-send-via.png",  _("Forward via"), svia_tip, svia),
                (gtk.STOCK_PRINT, "",            prnt_tip, self.but_printable),
                (gtk.STOCK_DELETE, "",           dele_tip, delete),
                ]

        #self.connect("destroy", close)
        self.connect("delete-event", close)
        self.connect("response", reject_delete_response)

        i = 0
        for img, lab, tip, func in buttons:
            if not lab:
                ti = gtk.ToolButton(img)
            else:
                icon = gtk.Image()
                icon.set_from_pixbuf(self._config.ship_img(img))
                icon.show()
                ti = gtk.ToolButton(icon, lab)
            ti.show()
            try:
                ti.set_tooltip_text(tip)
            except AttributeError:
                pass
            ti.connect("clicked", func)
            tb.insert(ti, i)
            i += 1

        tb.show()
        return tb

    def build_gui(self, editable=True):
        self.vbox.pack_start(self.build_toolbar(editable), 0, 0, 0)

        tlabel = gtk.Label()
        tlabel.set_markup("<big><b>%s</b></big>" % self.title_text)
        tlabel.show()

        if self.logo_path:
            image = gtk.Image()
            try:
                base = self._config.get("settings", "form_logo_dir")
                printlog("Formgui","   : Logo path: %s" % os.path.join(base, self.logo_path))
                image.set_from_file(os.path.join(base, self.logo_path))
                self.vbox.pack_start(image, 0,0,0)
                image.show()
            except Exception as e:
                printlog("Formgui","   : Unable to load or display logo %s: %s" % (self.logo_path,
                                                                 e))
        self.vbox.pack_start(tlabel, 0,0,0)

        self.vbox.pack_start(self.build_routing_widget(), 0, 0, 0)

        #field_box = gtk.VBox(False, 2)
        field_box = gtk.Table(len(self.fields), 2)
        row = 0

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_NEVER,
                      gtk.POLICY_AUTOMATIC)
        sw.add_with_viewport(field_box)
        field_box.show()
        sw.show()
        self.vbox.pack_start(sw, 1,1,1)


        msg_field = None
        chk_field = None

        for f in self.fields:
            if f.id == "_auto_check":
                chk_field = f
            elif f.id == "_auto_message":
                msg_field = f
            elif f.id == "_auto_senderX": # FIXME
                if not f.entry.widget.get_text():
                    call = self._config.get("user", "callsign")
                    f.entry.widget.set_text(call)
                f.entry.widget.set_property("editable", False)
            elif f.id == "_auto_position":
                if not f.entry.widget.get_text():
                    from . import mainapp # Dirty hack
                    pos = mainapp.get_mainapp().get_position()
                    f.entry.widget.set_text(pos.coordinates())
            
            l = gtk.Label(f.caption)
            l.show()
            w = f.get_widget()
            if f.entry.vertical:
                field_box.attach(l, 0, 2, row, row+1, gtk.SHRINK, gtk.SHRINK)
                row += 1
                field_box.attach(w, 0, 2, row, row+1)
            elif f.entry.nolabel:
                field_box.attach(w, 0, 2, row, row+1, gtk.SHRINK, gtk.SHRINK)
            else:
                field_box.attach(l, 0, 1, row, row+1, gtk.SHRINK, gtk.SHRINK, 5)
                field_box.attach(w, 1, 2, row, row+1, yoptions=0)
            row += 1
            

        self.vbox.pack_start(self.build_att_widget(), 0, 0, 0)
        self.vbox.pack_start(self.build_path_widget(), 0, 0, 0)

        if msg_field and chk_field:
            mw = msg_field.entry.buffer
            cw = chk_field.entry.widget

            mw.connect("changed", self.calc_check, cw)

        self.set_editable(editable)

    def __init__(self, title, filename, buttons=None, parent=None):
        self._buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                         gtk.STOCK_SAVE, gtk.RESPONSE_OK)
        if buttons:
            self._buttons += buttons

        gtk.Dialog.__init__(self, buttons=(), parent=parent)
        FormFile.__init__(self, filename)

        from . import mainapp
        self._config = mainapp.get_mainapp().config

        self.process_fields(self.doc)
        self.set_title(self.title_text)

        try:
            x = self._config.getint("state", "form_%s_x" % self.id)
            y = self._config.getint("state", "form_%s_y" % self.id)
        except Exception as e:
            printlog("Formgui","   : Unable to get form_%s_*: %s" % (self.id, e))
            x = 300
            y = 500

        self.set_default_size(x, y)

        printlog("Formgui","   : Form ID: %s" % self.id)

    def update_dst(self):
        dst = self._dstbox.get_text()
        if "@" not in dst:
            dst = dst.upper()
        self.set_path_dst(dst)

    def run(self):
        self.vbox.set_spacing(5)
        self.build_gui()
        self.set_size_request(380, 450)

        r = gtk.Dialog.run(self)
        self.update_dst()

        return r

    def set_editable(self, editable):
        for field in self.fields:
            field.set_editable(editable)
        
if __name__ == "__main__":
    f = open(sys.argv[1])
    xml = f.read()
    form = Form("Form", xml)
    form.run()
    form.destroy()
    try:
        gtk.main()
    except:
        pass

    printlog(form.get_text())
