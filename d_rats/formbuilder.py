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

import gtk
import gobject

import os
import glob
import tempfile
import shutil

from miscwidgets import make_choice
from formgui import FormDialog,FormFile,xml_escape,xml_unescape
import formgui
import mainapp
from d_rats import platform

class FormElementEditor(gtk.Dialog):
    def make_entry_editor(self, id):
        entry = gtk.Entry()
        entry.show()

        f = gtk.Frame("Initial value:")
        f.add(entry)
        
        self.entries[id] = entry

        return f

    def make_null_editor(self, id):
        return gtk.Label("(There are no options for this type)")

    def make_toggle_editor(self, id):
        cb = gtk.CheckButton("True")
        cb.show()

        f = gtk.Frame("Default value")
        f.add(cb)

        self.entries[id] = cb

        return f

    def make_choice_editor(self, id, single=True):
        self._choice_buffer = gtk.TextBuffer()
        entry = gtk.TextView(self._choice_buffer)
        entry.show()

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        sw.add(entry)
        sw.show()

        if single:
            f = gtk.Frame("Options (one per line, first is default)")
        else:
            f = gtk.Frame("Options (one per line)")
        f.add(sw)

        self.entries[id] = entry

        return f

    def type_changed(self, box, data=None):
        sel = box.get_active_text()

        print "Selected: %s" % sel

        for t,w in self.vals.items():
            if t == sel:
                w.show()
            else:
                w.hide()

    def __init__(self):
        gtk.Dialog.__init__(self,
                            title="Edit form element",
                            buttons=(gtk.STOCK_OK, gtk.RESPONSE_OK,
                                     gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL))

        self.entries = {}

        self.set_default_size(150,150)

        self.vals = {
            "text"      : self.make_entry_editor("text"),
            "multiline" : self.make_entry_editor("multiline"),
            "date"      : self.make_null_editor("date"),
            "time"      : self.make_null_editor("time"),
            "numeric"   : self.make_entry_editor("numeric"),
            "toggle"    : self.make_toggle_editor("toggle"),
            "choice"    : self.make_choice_editor("choice"),
            "multiselect": self.make_choice_editor("multiselect", False),
            "label"     : self.make_null_editor("label"),
            }

        self.type_sel = make_choice(self.vals.keys(), False, "text")
        self.type_sel.connect("changed", self.type_changed, None)
        self.type_sel.show()
        self.vals["text"].show()
        
        self.ts_frame = gtk.Frame("Field Type")
        self.ts_frame.show()
        self.ts_frame.add(self.type_sel)

        self.vbox.pack_start(self.ts_frame, 0,0,0)

        for t,w in self.vals.items():
            self.vbox.pack_start(w, 1,1,1)

    def get_initial_value(self):
        sel = self.type_sel.get_active_text()

        if sel in ("text", "multiline", "numeric"):
            return self.entries[sel].get_text()
        elif sel in ("choice",):
            b = self.entries[sel].get_buffer()
            i = b.get_iter_at_line(1)
            i.backward_chars(1)
            return b.get_text(b.get_start_iter(), i)
        elif sel in ("toggle"):
            return str(self.entries[sel].get_active())
        else:
            return ""

    def set_initial_value(self, val):
        sel = self.type_sel.get_active_text()

        if sel in ("text", "multiline", "numeric"):
            return self.entries[sel].set_text(val)
        elif sel in ("toggle"):
            try:
                b = eval(val)
            except:
                b = False
            self.entries[sel].set_active(b)

    def get_options(self):
        sel = self.type_sel.get_active_text()
        if sel == "choice":
            b = self.entries[sel].get_buffer()
            t = b.get_text(b.get_start_iter(), b.get_end_iter())
            return str(t.split("\n"))
        elif sel == "multiselect":
            b = self.entries[sel].get_buffer()
            t = b.get_text(b.get_start_iter(), b.get_end_iter())
            opts = t.split("\n")
            return str([(False, x) for x in opts])
        else:
            return ""
        
    def set_options(self, val):
        sel = self.type_sel.get_active_text()
        if sel == "choice":
            try:
                l = eval(val)
            except:
                return

            b = self.entries[sel].get_buffer()
            b.set_text("\n".join(l))
        elif sel == "multiselect":
            try:
                l = eval(val)
            except:
                return

            b = self.entries[sel].get_buffer()
            b.set_text("\n".join([y for x,y in l]))

    def get_type(self):
        return self.type_sel.get_active_text()

    def set_type(self, type):
        self.type_sel.set_active(self.vals.keys().index(type))

class FormBuilderGUI(gtk.Dialog):

    def reorder(self, up):

        try:
            (list, iter) = self.view.get_selection().get_selected()
            pos = int(list.get_path(iter)[0])

            if up:
                target = list.get_iter(pos - 1)
            else:
                target = list.get_iter(pos + 1)

            if target:
                list.swap(iter, target)
        except:
            return

    def but_move_up(self, widget, data=None):
        self.reorder(True)

    def but_move_down(self, widget, data=None):
        self.reorder(False)

    def but_add(self, widget, data=None):
        d = FormElementEditor()
        r = d.run()
        if r == gtk.RESPONSE_CANCEL:
            d.destroy()
            return

        iv = d.get_initial_value()

        print "Type: %s" % d.get_type()
        print "Initial: %s" % iv
        print "Opts: %s" % d.get_options()

        iter = self.store.append()
        self.store.set(iter,
                       self.col_id, "foo",
                       self.col_type, d.get_type(),
                       self.col_cap, "Untitled",
                       self.col_value, iv,
                       self.col_opts, d.get_options(),
                       self.col_inst, "")

        d.destroy()

    def but_delete(self, widget, data=None):
        try:
            (list, iter) = self.view.get_selection().get_selected()
            list.remove(iter)
        except:
            return

    def but_edit(self, widget, data=None):
        try:
            (list, iter) = self.view.get_selection().get_selected()
            (t, v, o) = list.get(iter,
                                 self.col_type,
                                 self.col_value,
                                 self.col_opts)
        except:
            return
        
        d = FormElementEditor()
        d.set_type(t)
        d.set_initial_value(v)
        d.set_options(o)
        r = d.run()
        if r == gtk.RESPONSE_OK:
            list.set(iter,
                     self.col_type, d.get_type(),
                     self.col_value, d.get_initial_value(),
                     self.col_opts, d.get_options())

        d.destroy()

    def ev_edited(self, r, path, new_text, colnum):
        iter = self.store.get_iter(path)

        self.store.set(iter, colnum, new_text)

    def build_display(self):
        self.col_id    = 0
        self.col_type  = 1
        self.col_cap   = 2
        self.col_value = 3
        self.col_opts  = 4
        self.col_inst  = 5

        self.store = gtk.ListStore(gobject.TYPE_STRING,
                                   gobject.TYPE_STRING,
                                   gobject.TYPE_STRING,
                                   gobject.TYPE_STRING,
                                   gobject.TYPE_STRING,
                                   gobject.TYPE_STRING)

        self.view = gtk.TreeView(self.store)
        self.view.set_rules_hint(True)
        self.view.show()

        l = [(self.col_id, "ID", True),
             (self.col_type, "Type", False),
             (self.col_cap, "Caption", True),
             (self.col_value, "Initial Value", False)]


        for i in l:
            (col, cap, ed) = i
            r = gtk.CellRendererText()
            r.set_property("editable", ed)
            if ed:
                r.connect("edited", self.ev_edited, col)

            c = gtk.TreeViewColumn(cap, r, text=col)
            c.set_resizable(True)
            c.set_sort_column_id(col)

            self.view.append_column(c)

        sw = gtk.ScrolledWindow()
        sw.add(self.view)
        sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        sw.show()

        return sw

    def make_field_xml(self, model, path, iter, _):
        (id, type, cap, val, opts, inst) = model.get(iter,
                                                     self.col_id,
                                                     self.col_type,
                                                     self.col_cap,
                                                     self.col_value,
                                                     self.col_opts,
                                                     self.col_inst)

        if val:
            val = xml_escape(val)
        print "\n\nField type: %s" % type
        cap_xml = "<caption>%s</caption>" % cap
        if type not in ["choice", "multiselect"] and val:
            ent_xml = "<entry type='%s'>%s</entry>" % (type, val)
        elif type == "choice":
            try:
                print "Opts: %s" % opts
                l = eval(opts)

                ent_xml = "<entry type='%s'>" % type
                for c in l:
                    if c == val:
                        set = " set='y'"
                    else:
                        set = ""

                    ent_xml += "<choice%s>%s</choice>" % (set, c)

                ent_xml += "</entry>"
            except Exception, e:
                print "Exception parsing choice list: %s" % e
                ent_xml = "<!-- Invalid list: %s -->" % opts

        elif type == "multiselect":
            try:
                l = eval(opts)

                ent_xml = "<entry type='%s'>" % type
                for v, c in l:
                    setval = v and "y" or "n"
                    ent_xml += "<choice set='%s'>%s</choice>" % (setval, c)
                ent_xml += "</entry>"
            except Exception, e:
                print "Exception parsing choice list: %s" % e
                ent_xml = "<!-- Invalid list: %s -->" % opts
        else:
            ent_xml = "<entry type='%s'/>" % type
        
        field_xml = "<field id='%s'>\n%s\n%s\n</field>\n" % (id,
                                                             cap_xml,
                                                             ent_xml)
        
        print "Field XML: %s\n\n" % field_xml

        self.xml += field_xml

    def get_form_xml(self):
        id = self.props["ID"].get_text()
        title = self.props["Title"].get_text()
        logo = self.props["Logo"].get_active_text()

        self.xml = "<xml>\n<form id='%s'>\n<title>%s</title>\n" % (id,title)
        if logo:
            self.xml += "<logo>%s</logo>" % logo
        self.store.foreach(self.make_field_xml, None)
        self.xml += "</form>\n</xml>\n"
        
        return self.xml

    def build_buttons(self):
        box = gtk.VBox(True, 2)

        l = [("Move Up", self.but_move_up),
             ("Add", self.but_add),
             ("Edit", self.but_edit),
             ("Delete", self.but_delete),
             ("Move Down", self.but_move_down),
             ]

        for i in l:
            (cap, func) = i
            b = gtk.Button(cap)
            b.connect("clicked", func, None)
            box.pack_start(b, 0,0,0)
            b.show()

        box.show()

        return box

    def make_field(self, caption, choices=None):
        box = gtk.HBox(False, 2)
        
        l = gtk.Label(caption)
        l.set_size_request(45, -1)
        l.show()

        if choices is not None:
            e = make_choice(choices, True)
        else:
            e = gtk.Entry()
        e.show()

        self.props[caption] = e

        box.pack_start(l, 0,0,0)
        box.pack_start(e, 1,1,1)
        box.show()

        return box

    def build_formprops(self):
        self.props = {}
        
        frame = gtk.Frame("Form Properties")

        path = mainapp.get_mainapp().config.get("settings", "form_logo_dir")
        logos = []
        for fn in glob.glob(os.path.join(path, "*.*")):
            logos.append(fn.replace(path, "")[1:])

        box = gtk.VBox(False, 2)
        for i in ["Title", "ID"]:
            f = self.make_field(i)
            box.pack_start(f, 0,0,0)
            f.show()

        f = self.make_field("Logo", logos)
        box.pack_start(f, 0, 0, 0)
        f.show()

        box.show()

        frame.add(box)
        frame.show()

        return frame

    def build_fieldeditor(self):
        frame = gtk.Frame("Form Elements")

        box = gtk.HBox(False, 2)
        box.pack_start(self.build_display(), 1,1,1)
        box.pack_start(self.build_buttons(), 0,0,0)
        box.show()

        frame.add(box)
        frame.show()

        return frame

    def show_preview(self, widget, data=None):
        fd, n = tempfile.mkstemp()

        f = file(n, "w")
        f.write(self.get_form_xml())
        f.close()
        os.close(fd)

        d = FormDialog("Preview of form",
                       n,
                       parent=self)
        config = mainapp.get_mainapp().config
        d.configure(config)
        d.run()
        d.destroy()
        os.remove(n)

    def load_field(self, widget):
        iter = self.store.append()
        print "Type: %s" % widget.type
        if widget.type in ["choice", "multiselect"]:
            opts = widget.choices
            print "Opts for %s: %s" % (widget.type, opts)
        else:
            opts = None
        self.store.set(iter,
                       self.col_id, widget.id,
                       self.col_type, widget.type,
                       self.col_cap, widget.caption,
                       self.col_value, widget.get_value(),
                       self.col_opts, opts)

    def load_from_file(self, filename):
        form = FormDialog("", filename)
        self.props["ID"].set_text(form.id)
        self.props["Title"].set_text(form.title_text)
        self.props["Logo"].child.set_text(form.logo_path or "")

        for f in form.fields:
            w = f.entry
            self.load_field(w)

        del form

    def __init__(self):
        gtk.Dialog.__init__(self,
                            title="Form builder",
                            buttons=(gtk.STOCK_SAVE, gtk.RESPONSE_OK,
                                     gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL))


        self.vbox.pack_start(self.build_formprops(), 0,0,0)
        self.vbox.pack_start(self.build_fieldeditor(), 1,1,1)

        preview = gtk.Button("Preview")
        preview.connect("clicked", self.show_preview, None)
        preview.show()

        self.action_area.pack_start(preview, 0,0,0)

class FormManagerGUI(object):

    def add_form(self, filename):
        try:
            form = FormFile(filename)
            id = form.id
            title = form.title_text
            del form
        except Exception, e:
            import utils
            utils.log_exception()
            id = "broken"
            title = "Broken Form - Delete me"

        iter = self.store.get_iter_first()
        while iter:
            form_id, = self.store.get(iter, self.col_id)
            print "Checking %s against %s" % (form_id, id)
            if form_id == id:
                raise Exception("Cannot add duplicate form `%s'" % form_id)
            iter = self.store.iter_next(iter)

        iter = self.store.append()
        self.store.set(iter,
                       self.col_id, id,
                       self.col_title, title,
                       self.col_file, filename)

        return id

    def but_new(self, widget, data=None):
        d = FormBuilderGUI()
        r = d.run()
        if r != gtk.RESPONSE_CANCEL:
            id = d.props["ID"].get_text()
            xml = d.get_form_xml()
            f = file(os.path.join(self.dir, "%s.xml" % id), "w")
            f.write(xml)
            f.close()
            self.add_form(f.name)

        d.destroy()

    def but_edit(self, widget, data=None):
        try:
            (list, iter) = self.view.get_selection().get_selected()
            (filename, _id) = list.get(iter, self.col_file, self.col_id)
        except:
            return
        
        d = FormBuilderGUI()
        d.load_from_file(filename)
        r = d.run()
        if r != gtk.RESPONSE_CANCEL:
            id = d.props["ID"].get_text()
            xml = d.get_form_xml()
            f = file(os.path.join(self.dir, "%s.xml" % id), "w")
            f.write(xml)
            f.close()
            if id != _id:
                # FIXME: Delete old file
                self.add_form(f.name)

        d.destroy()

    def but_delete(self, widget, data=None):
        try:
            (list, iter) = self.view.get_selection().get_selected()
            (file, ) = list.get(iter, self.col_file)

            list.remove(iter)
            os.remove(file)
        except:
            return

    def but_close(self, widget, data=None):
        self.window.destroy()

    def but_import(self, widget, data=None):
        p = platform.get_platform()
        fn = p.gui_open_file()
        if not fn:
            return

        try:
            form_id = self.add_form(fn)
        except Exception, e:
            d = gtk.MessageDialog(buttons=gtk.BUTTONS_OK)
            d.set_markup("<big><b>Unable to add form</b></big>")
            d.format_secondary_text(str(e))
            d.run()
            d.destroy()

        shutil.copy(fn, os.path.join(self.dir, "%s.xml" % form_id))

    def but_export(self, widget, data=None):
        try:
            (list, iter) = self.view.get_selection().get_selected()
            (filename, _id) = list.get(iter, self.col_file, self.col_id)
        except:
            return

        p = platform.get_platform()
        fn = p.gui_save_file(default_name="%s.xml" % _id)
        if fn:
            shutil.copy(filename, fn)

    def make_list(self):
        self.col_id = 0
        self.col_title = 1
        self.col_file = 2

        self.store = gtk.ListStore(gobject.TYPE_STRING,
                                   gobject.TYPE_STRING,
                                   gobject.TYPE_STRING)
        self.view = gtk.TreeView(self.store)
        self.view.set_rules_hint(True)
        self.view.show()

        l = [(self.col_id, "ID"),
             (self.col_title, "Title")]

        for col,cap in l:
            r = gtk.CellRendererText()
            c = gtk.TreeViewColumn(cap, r, text=col)
            c.set_sort_column_id(col)

            self.view.append_column(c)

        sw = gtk.ScrolledWindow()
        sw.add(self.view)
        sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        sw.show()

        return sw

    def make_buttons(self):

        l = [("New", self.but_new),
             ("Edit", self.but_edit),
             ("Delete", self.but_delete),
             ("Close", self.but_close),
             ("Import", self.but_import),
             ("Export", self.but_export),
             ]

        hbox = gtk.HBox(True, 2)

        for cap,func in l:
            b = gtk.Button(cap)
            b.connect("clicked", func, None)
            b.show()
            hbox.add(b)
            
        hbox.show()

        return hbox

    def __init__(self, dir):
        self.dir = dir

        vbox = gtk.VBox(False, 2)

        vbox.pack_start(self.make_list(), 1,1,1)
        vbox.pack_start(self.make_buttons(), 0,0,0)

        files = glob.glob(os.path.join(dir, "*.xml"))
        for f in files:
            self.add_form(f)

        vbox.show()

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title("Form Manager")
        self.window.set_default_size(275,300)

        self.window.add(vbox)

        self.window.show()

if __name__=="__main__":
    m = FormManagerGUI("Form_Templates")

    gtk.main()
