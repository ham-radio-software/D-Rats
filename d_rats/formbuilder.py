#
# pylint: disable=too-many-lines
'''Form Builder'''
# Copyright 2008 Dan Smith <dsmith@danplanet.com>
# Copyright 2021 John. E. Malmberg - Python3 Conversion
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

import ast
import os
import glob
import logging
import tempfile
import shutil

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import GObject

if not '_' in locals():
    import gettext
    _ = gettext.gettext


from d_rats import dplatform
from .miscwidgets import make_choice
from .formgui import FormDialog, FormFile, xml_escape

# py3 from . import mainapp


class FormBuilderException(Exception):
    '''Generic FormBuilder Exception.'''


class DuplicateFormError(FormBuilderException):
    '''Duplicate Form Error.'''


class FormElementEditor(Gtk.Dialog):
    '''Form Element Editor'''

    def __init__(self):
        Gtk.Dialog.__init__(self)

        self.logger = logging.getLogger("FormElementEditor")
        self.set_title(_("Edit form element"))
        self.add_button(_("OK"), Gtk.ResponseType.OK)
        self.add_button(_("CANCEL"), Gtk.ResponseType.CANCEL)
        self.entries = {}

        self.set_default_size(150, 150)

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

        self.type_sel = make_choice(list(self.vals.keys()), False, "text")
        self.type_sel.connect("changed", self.type_changed, None)
        self.type_sel.show()
        self.vals["text"].show()

        self.ts_frame = Gtk.Frame.new(_("Field Type"))
        self.ts_frame.show()
        self.ts_frame.add(self.type_sel)

        self.vbox.pack_start(self.ts_frame, 0, 0, 0)

        for _t, widget in self.vals.items():
            self.vbox.pack_start(widget, 1, 1, 1)

    def make_entry_editor(self, ident):
        '''
        Make Entry Editor

        :param ident: Identification for widget
        :type ident: str
        :returns: Entry editor widget
        :rtype: :class:`Gtk.Frame`
        '''
        entry = Gtk.Entry()
        entry.show()

        frame = Gtk.Frame.new(_("Initial value:"))
        frame.add(entry)

        self.entries[ident] = entry

        return frame

    # pylint: disable=no-self-use
    def make_null_editor(self, _ident):
        '''
        Make Null Editor.

        :param _ident: Unused
        :type _ident: str
        :returns: Label object
        :rtype: :class:`Gtk.Label`
        '''
        return Gtk.Label.new("(There are no options for this type)")

    def make_toggle_editor(self, ident):
        '''
        Make Toggle Editor.

        :param ident: Identity to give widget
        :type ident: str
        :returns: Toggle edit widget
        :rtype: :class:`Gtk.Frame`
        '''
        check_button = Gtk.CheckButton.new_with_label(_("True"))
        check_button.show()

        frame = Gtk.Frame.new(_("Default value"))
        frame.add(check_button)

        self.entries[ident] = check_button

        return frame

    def make_choice_editor(self, ident, single=True):
        '''
        Make Choice Editor

        :param ident: Identity for form
        :type ident: str
        :param single: Single option
        :type single: bool
        :returns: Choice editor widget
        :rtype: :class:`Gtk.Frame`
        '''
        self._choice_buffer = Gtk.TextBuffer()
        entry = Gtk.TextView.new_with_buffer(self._choice_buffer)
        entry.show()

        scroll_window = Gtk.ScrolledWindow()
        scroll_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll_window.add(entry)
        scroll_window.show()

        if single:
            frame = Gtk.Frame.new(_("Options (one per line, first is default)"))
        else:
            frame = Gtk.Frame.new(_("Options (one per line)"))
        frame.add(scroll_window)

        self.entries[ident] = entry

        return frame

    def type_changed(self, box, _data=None):
        '''
        Type Changed.

        :param box: Box object
        :type box: :class:`Gtk.Box`
        :param _data: Unused
        '''
        sel = box.get_active_text()

        self.logger.info("type_changed Selected: %s", sel)

        for item_t, widget in self.vals.items():
            if item_t == sel:
                widget.show()
            else:
                widget.hide()

    def get_initial_value(self):
        '''
        Get initial value.

        :returns: Initial value as a string, or empty string
        :rtype: str
        '''
        sel = self.type_sel.get_active_text()

        if sel in ("text", "multiline", "numeric"):
            return self.entries[sel].get_text()
        if sel in "choice":
            buffer = self.entries[sel].get_buffer()
            line_iter = buffer.get_iter_at_line(1)
            line_iter.backward_chars(1)
            return buffer.get_text(buffer.get_start_iter(), line_iter, True)
        if sel in "toggle":
            return str(self.entries[sel].get_active())
        return ""

    def set_initial_value(self, val):
        '''
        Set Initial Value.

        :param val: Value to set
        '''
        sel = self.type_sel.get_active_text()

        if sel in ("text", "multiline", "numeric"):
            self.entries[sel].set_text(val)
            return
        if sel in "toggle":
            try:
                b_active = ast.literal_eval(val)
            except ValueError:
                b_active = False
            self.entries[sel].set_active(b_active)

    def get_options(self):
        '''
        Get Options.

        :returns: String of options or empty string
        :rtype: str
        '''
        sel = self.type_sel.get_active_text()
        if sel == "choice":
            buffer = self.entries[sel].get_buffer()
            text = buffer.get_text(buffer.get_start_iter(),
                                   buffer.get_end_iter(), True)
            return str(text.split("\n"))
        if sel == "multiselect":
            buffer = self.entries[sel].get_buffer()
            text = buffer.get_text(buffer.get_start_iter(),
                                   buffer.get_end_iter(), True)
            opts = text.split("\n")
            return str([(False, x) for x in opts])
        return ""

    def set_options(self, val):
        '''
        Set Options.

        :param val: string containing options
        :type val: str
        '''
        sel = self.type_sel.get_active_text()
        if sel == "choice":
            try:
                val_list = ast.literal_eval(val)
            except ValueError:
                return

            buffer = self.entries[sel].get_buffer()
            buffer.set_text("\n".join(val_list))
        elif sel == "multiselect":
            try:
                val_list = ast.literal_eval(val)
            except ValueError:
                return

            buffer = self.entries[sel].get_buffer()
            buffer.set_text("\n".join([y for x, y in val_list]))

    def get_type(self):
        '''
        Get Form Type.

        :returns: Form type
        :rtype: str
        '''
        return self.type_sel.get_active_text()

    def set_type(self, form_type):
        '''
        Set Form Type.

        :param form_type: Form type
        :type form_type: str
        '''
        self.type_sel.set_active(list(self.vals.keys()).index(form_type))


# pylint: disable=too-many-instance-attributes
class FormBuilderGUI(Gtk.Dialog):
    '''
    Form Builder GUI.

    :param: config: Configuration object
    :type config: :class:`DratsConfig`
    '''

    def __init__(self, config):
        Gtk.Dialog.__init__(self)

        self.config = config
        self.logger = logging.getLogger("FormBuilderGUI")
        self.set_title(_("Form builder"))
        self.add_button(_("Save"), Gtk.ResponseType.OK)
        self.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        self.xml = None
        self.view = None
        self.col_id = None
        self.col_type = None
        self.col_cap = None
        self.col_value = None
        self.col_opts = None
        self.col_inst = None
        self.store = None

        self.vbox.pack_start(self.build_formprops(), 0, 0, 0)
        self.vbox.pack_start(self.build_fieldeditor(), 1, 1, 1)

        preview = Gtk.Button.new_with_label("Preview")
        preview.connect("clicked", self.show_preview, None)
        preview.show()

        self.action_area.pack_start(preview, 0, 0, 0)

    def reorder(self, move_up):
        '''
        Reorder

        :param move_up: True to move up, False to move down
        :type move_up: bool
        '''
        try:
            (sel_list, sel_iter) = self.view.get_selection().get_selected()
            pos = int(sel_list.get_path(sel_iter)[0])

            if move_up:
                target = sel_list.get_iter(pos - 1)
            else:
                target = sel_list.get_iter(pos + 1)

            if target:
                sel_list.swap(sel_iter, target)
        # pylint: disable=broad-except
        except Exception:
            self.logger.info("reorder broad-except", exc_info=True)
            return

    def but_move_up(self, _widget, _data=None):
        '''
        Button Move Up.

        :param _widget: Unused
        :type _widget: :class:`Gtk.Widget`
        :param _data: Unused
        '''
        self.reorder(True)

    def but_move_down(self, _widget, _data=None):
        '''
        Button Move Down.

        :param _widget: Unused
        :type _widget: :class:`Gtk.Widget`
        :param _data: Unused
        '''
        self.reorder(False)

    def but_add(self, _widget, _data=None):
        '''
        Button Add.

        :param _widget: Unused
        :type _widget: :class:`Gtk.Widget`
        :param _data: Unused
        '''
        dialog = FormElementEditor()
        result = dialog.run()
        if result == Gtk.ResponseType.CANCEL:
            dialog.destroy()
            return

        ivalue = dialog.get_initial_value()

        self.logger.info("but_add Type: %s, Initial: %s Opts: %s",
                         dialog.get_type(), ivalue, dialog.get_options())

        store_iter = self.store.append()
        self.store.set(store_iter,
                       self.col_id, "foo",
                       self.col_type, dialog.get_type(),
                       self.col_cap, "Untitled",
                       self.col_value, ivalue,
                       self.col_opts, dialog.get_options(),
                       self.col_inst, "")

        dialog.destroy()

    def but_delete(self, _widget, _data=None):
        '''
        Button Delete.

        :param _widget: Unused
        :type _widget: :class:`Gtk.Widget`
        :param _data: Unused
        '''
        try:
            (sel_list, sel_iter) = self.view.get_selection().get_selected()
            sel_list.remove(sel_iter)
        # pylint: disable=broad-except
        except Exception:
            self.logger.info("buf_delete broad-except", exc_info=True)
            return

    def but_edit(self, _widget, _data=None):
        '''
        Button Edit.

        :param _widget: Unused
        :type _widget: :class:`Gtk.Widget`
        :param _data: Unused
        '''
        try:
            (sel_list, sel_iter) = self.view.get_selection().get_selected()
            (col_t, col_v, col_o) = sel_list.get(sel_iter,
                                                 self.col_type,
                                                 self.col_value,
                                                 self.col_opts)
        # pylint: disable=broad-except
        except Exception:
            self.logger.info("buf_edit broad-exception", exc_info=True)
            return

        dialog = FormElementEditor()
        dialog.set_type(col_t)
        dialog.set_initial_value(col_v)
        dialog.set_options(col_o)
        result = dialog.run()
        if result == Gtk.ResponseType.OK:
            sel_list.set(sel_iter,
                         self.col_type, dialog.get_type(),
                         self.col_value, dialog.get_initial_value(),
                         self.col_opts, dialog.get_options())

        dialog.destroy()

    def ev_edited(self, _r, path, new_text, colnum):
        '''
        EV Edited.

        :param _r: Unused
        :param path: path data
        :param new_text: New text for edit
        :type new_text: str
        :param colnum: Column Number
        :type colnum: int
        '''
        ev_iter = self.store.get_iter(path)

        self.store.set(ev_iter, colnum, new_text)

    def build_display(self):
        '''
        Build Display

        :returns: Scrolled window display
        :rtype: :class:`Gtk.ScrolledWindow`
        '''
        self.col_id = 0
        self.col_type = 1
        self.col_cap = 2
        self.col_value = 3
        self.col_opts = 4
        self.col_inst = 5

        self.store = Gtk.ListStore(GObject.TYPE_STRING,
                                   GObject.TYPE_STRING,
                                   GObject.TYPE_STRING,
                                   GObject.TYPE_STRING,
                                   GObject.TYPE_STRING,
                                   GObject.TYPE_STRING)

        self.view = Gtk.TreeView.new_with_model(self.store)
        # Deprecated with GTK 3.14, from the documentation this is supposed
        # to be controlled by the theme.
        # self.view.set_rules_hint(True)
        self.view.show()

        col_list = [(self.col_id, _("ID"), True),
                    (self.col_type, _("Type"), False),
                    (self.col_cap, _("Caption"), True),
                    (self.col_value, _("Initial Value"), False)]


        for col_i in col_list:
            (col, cap, editable) = col_i
            renderer = Gtk.CellRendererText()
            renderer.set_property("editable", editable)
            if editable:
                renderer.connect("edited", self.ev_edited, col)

            column = Gtk.TreeViewColumn(cap, renderer, text=col)
            column.set_resizable(True)
            column.set_sort_column_id(col)

            self.view.append_column(column)

        scroll_window = Gtk.ScrolledWindow()
        scroll_window.add(self.view)
        scroll_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll_window.show()

        return scroll_window

    # pylint: disable=too-many-locals
    def make_field_xml(self, model, _path, field_iter, _):
        '''
        Make Field XML.

        :param model: model object
        :param _path: Unused
        :param field_iter: object that can iterate
        :param _: Unused parameter
        '''
        (ident, field_type, cap, val, opts, _inst) = model.get(field_iter,
                                                               self.col_id,
                                                               self.col_type,
                                                               self.col_cap,
                                                               self.col_value,
                                                               self.col_opts,
                                                               self.col_inst)

        if val:
            val = xml_escape(val)
        self.logger.info("make_field_xml Field type: %s", field_type)
        cap_xml = "<caption>%s</caption>" % cap
        if field_type not in ["choice", "multiselect"] and val:
            ent_xml = "<entry type='%s'>%s</entry>" % (field_type, val)
        elif field_type == "choice":
            try:
                self.logger.info("make_field_xml Opts: %s", opts)
                opts_list = ast.literal_eval(opts)

                ent_xml = "<entry type='%s'>" % field_type
                for c_opt in opts_list:
                    if c_opt == val:
                        c_set = " set='y'"
                    else:
                        c_set = ""

                    ent_xml += "<choice%s>%s</choice>" % (c_set, c_opt)

                ent_xml += "</entry>"
            # pylint: disable=broad-except
            except Exception:
                self.logger.info("Exception parsing choice list",
                                 exc_info=True)
                ent_xml = "<!-- Invalid list: %s -->" % opts

        elif field_type == "multiselect":
            try:
                opts_list = ast.literal_eval(opts)

                ent_xml = "<entry type='%s'>" % field_type
                for v_opt, c_opt in opts_list:
                    setval = v_opt and "y" or "n"
                    ent_xml += "<choice set='%s'>%s</choice>" % (setval, c_opt)
                ent_xml += "</entry>"
            # pylint: disable=broad-except
            except Exception:
                self.logger.info("Exception parsing choice list",
                                 exc_info=True)
                ent_xml = "<!-- Invalid list: %s -->" % opts
        else:
            ent_xml = "<entry type='%s'/>" % field_type

        field_xml = "<field id='%s'>\n%s\n%s\n</field>\n" % (ident,
                                                             cap_xml,
                                                             ent_xml)

        self.logger.info("Field XML: %s\n\n", field_xml)

        self.xml += field_xml

    def get_form_xml(self):
        '''
        Get Form XML

        :returns: XML representation of form
        :rtype: str
        '''
        ident = self.props["ID"].get_text()
        title = self.props["Title"].get_text()
        logo = self.props["Logo"].get_active_text()

        self.xml = "<xml>\n<form id='%s'>\n<title>%s</title>\n" % (ident, title)
        if logo:
            self.xml += "<logo>%s</logo>" % logo
        self.store.foreach(self.make_field_xml, None)
        self.xml += "</form>\n</xml>\n"

        return self.xml

    def build_buttons(self):
        '''
        Build Buttons

        :returns: Box object with buttons
        :rtype: :class:`Gtk.Box`
        '''
        box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 2)
        box.set_homogeneous(True)

        button_list = [(_("Move Up"), self.but_move_up),
                       (_("Add"), self.but_add),
                       (_("Edit"), self.but_edit),
                       (_("Delete"), self.but_delete),
                       (_("Move Down"), self.but_move_down),
                       ]

        for button_info in button_list:
            (cap, func) = button_info
            button = Gtk.Button.new_with_label(cap)
            button.connect("clicked", func, None)
            box.pack_start(button, 0, 0, 0)
            button.show()

        box.show()

        return box

    def make_field(self, caption, choices=None):
        '''
        Make Field

        :param caption: Caption for field
        :type caption: str
        :param choices: Optional Choices
        :returns: Box object with field.
        :rtype: :class:`Gtk.Box`
        '''
        box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 2)

        label = Gtk.Label.new(caption)
        label.set_size_request(45, -1)
        label.show()

        if choices is not None:
            entry = make_choice(choices, True)
        else:
            entry = Gtk.Entry()
        entry.show()

        self.props[caption] = entry

        box.pack_start(label, 0, 0, 0)
        box.pack_start(entry, 1, 1, 1)
        box.show()

        return box

    def build_formprops(self):
        '''
        Build Form Properties.

        :returns: Frame for form
        :rtype: :class:`Gtk.Frame`
        '''
        self.props = {}

        frame = Gtk.Frame.new(_("Form Properties"))
        # from . import mainapp # Hack to force import of mainapp
        path = self.config.get("settings", "form_logo_dir")
        logos = []
        for fname in glob.glob(os.path.join(path, "*.*")):
            logos.append(fname.replace(path, "")[1:])

        box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 2)
        for ident in ["Title", "ID"]:
            field = self.make_field(ident)
            box.pack_start(field, 0, 0, 0)
            field.show()

        field = self.make_field("Logo", logos)
        box.pack_start(field, 0, 0, 0)
        field.show()

        box.show()

        frame.add(box)
        frame.show()

        return frame

    def build_fieldeditor(self):
        '''
        Build Field Editor.

        :returns: Frame from editor.
        :rtype: :class:`Gtk.Frame`
        '''
        frame = Gtk.Frame.new(_("Form Elements"))

        box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 2)
        box.pack_start(self.build_display(), 1, 1, 1)
        box.pack_start(self.build_buttons(), 0, 0, 0)
        box.show()

        frame.add(box)
        frame.show()

        return frame

    def show_preview(self, _widget, _data=None):
        '''
        Show Preview.

        :param _widget: Unused Widget to preview
        :type _widget: :class:`Gtk.Widget`
        :param _data: Unused Optional data
        '''
        file_descriptor, name = tempfile.mkstemp()

        file_handle = open(name, "w")
        file_handle.write(self.get_form_xml())
        file_handle.close()
        os.close(file_descriptor)

        dialog = FormDialog("Preview of form",
                            name,
                            config=self.config,
                            parent=self)
        dialog.configure(self.config)
        dialog.run()
        dialog.destroy()
        os.remove(name)

    def load_field(self, widget):
        '''
        Load field

        :param widget: TextWidget to load the field from
        :type widget: :class:`Gtk.Widget`
        '''
        store_iter = self.store.append()
        if widget.type in ["choice", "multiselect"]:
            opts_list = widget.choices
            opts = str(opts_list)
        else:
            opts = None
        self.store.set(store_iter,
                       self.col_id, widget.ident,
                       self.col_type, widget.type,
                       self.col_cap, widget.caption,
                       self.col_value, widget.get_value(),
                       self.col_opts, opts)

    def load_from_file(self, filename):
        '''
        Load from file.

        :param filename: Filename to open
        :type filename: str
        '''
        form = FormDialog("", filename, config=self.config)
        self.props["ID"].set_text(form.ident)
        self.props["Title"].set_text(form.title_text)
        self.props["Logo"].get_child().set_text(form.logo_path or "")

        for field in form.fields:
            widget = field.entry
            self.load_field(widget)

        del form


class FormManagerGUI():
    '''
    Form Manager GUI.

    :param directory: Form directory
    :type directory: str
    :param config: Configuration object
    :type config: :class:`DratsConfig`
    '''

    def __init__(self, directory, config):

        self.logger = logging.getLogger("FormManagerGUI")
        self.dir = directory
        self.config = config

        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 2)

        vbox.pack_start(self.make_list(), 1, 1, 1)
        vbox.pack_start(self.make_buttons(), 0, 0, 0)

        files = glob.glob(os.path.join(directory, "*.xml"))
        for fname in files:
            self.add_form(fname)

        vbox.show()

        self.window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self.window.set_title("Form Manager")
        self.window.set_default_size(275, 300)

        self.window.add(vbox)

        self.window.show()

    def add_form(self, filename):
        '''
        Add form.

        :param filename: Filename for form
        :type filename: str
        :returns: form id
        '''
        try:
            form = FormFile(filename)
            ident = form.ident
            title = form.title_text
            del form
        # pylint: disable=broad-except
        except Exception:
            self.logger.info("add_form broad-except", exc_info=True)
            from . import utils
            utils.log_exception()
            ident = "broken"
            title = "Broken Form - Delete me"

        form_iter = self.store.get_iter_first()
        while form_iter:
            form_id, = self.store.get(form_iter, self.col_id)
            self.logger.info("add_form Checking %s against %s",
                             form_id, ident)
            if form_id == ident:
                raise DuplicateFormError("Cannot add duplicate form `%s'"
                                         % form_id)
            form_iter = self.store.iter_next(form_iter)

        form_iter = self.store.append()
        self.store.set(form_iter,
                       self.col_id, ident,
                       self.col_title, title,
                       self.col_file, filename)

        return ident

    def but_new(self, _widget, _data=None):
        '''
        Button new.

        :param _widget: Unused Widget
        :type _widget: :class:`Gtk.Widget`
        :param _data: Unused Optional data, default None
        '''
        dialog = FormBuilderGUI(config=self.config)
        result_code = dialog.run()
        if result_code != Gtk.ResponseType.CANCEL:
            ident = dialog.props["ID"].get_text()
            xml = dialog.get_form_xml()
            file_handle = open(os.path.join(self.dir, "%s.xml" % ident), "w")
            file_handle.write(xml)
            file_handle.close()
            self.add_form(file_handle.name)

        dialog.destroy()

    def but_edit(self, _widget, _data=None):
        '''
        Button edit.

        :param _widget: Unused Widget
        :param _data: Unused Optional data, default None
        '''
        try:
            (but_list, but_iter) = self.view.get_selection().get_selected()
            (filename, _id) = but_list.get(but_iter, self.col_file, self.col_id)
        # pylint: disable=broad-except
        except Exception:
            self.logger.info("buf_edit broad-except", exc_info=True)
            return

        dialog = FormBuilderGUI(config=self.config)
        dialog.load_from_file(filename)
        result_code = dialog.run()
        if result_code != Gtk.ResponseType.CANCEL:
            ident = dialog.props["ID"].get_text()
            xml = dialog.get_form_xml()
            file_handle = open(os.path.join(self.dir, "%s.xml" % ident), "w")
            file_handle.write(xml)
            file_handle.close()
            if ident != _id:
                # pylint: disable=fixme
                # FIXME: Delete old file
                self.add_form(file_handle.name)

        dialog.destroy()

    def but_delete(self, _widget, _data=None):
        '''
        Button delete.

        :param _widget: Unused Widget
        :type _widget: :class:`Gtk.Widget`
        :param _data: Unused Optional data, default None
        '''
        try:
            (sel_list, sel_iter) = self.view.get_selection().get_selected()
            (sel_file, ) = sel_list.get(sel_iter, self.col_file)

            sel_list.remove(sel_iter)
            os.remove(sel_file)
        # pylint: disable=broad-except
        except Exception:
            self.logger.info("but_delete broad-except", exc_info=True)
            return

    def but_close(self, _widget, _data=None):
        '''
        Button close.

        :param _widget: Unused Widget
        :type _widget: :class:`Gtk.Widget`
        :param _data: Unused Optional data, default None
        '''
        self.window.destroy()

    def but_import(self, _widget, _data=None):
        '''
        Button import.

        :param _widget: Unused Widget
        :type _widget: :class:`Gtk.Widget`
        :param _data: Unused Optional data, default None
        '''
        platform = dplatform.get_platform()
        fname = platform.gui_open_file()
        if not fname:
            return

        try:
            form_id = self.add_form(fname)
        # pylint: disable=broad-except
        except Exception as err:
            self.logger.info("but_import broad-except", exc_info=True)
            dialog = Gtk.MessageDialog(buttons=Gtk.ButtonsType.OK)
            dialog.set_markup("<big><b>Unable to add form</b></big>")
            dialog.format_secondary_text(str(err))
            dialog.run()
            dialog.destroy()

        shutil.copy(fname, os.path.join(self.dir, "%s.xml" % form_id))

    def but_export(self, _widget, _data=None):
        '''
        Button Export.

        :param _widget: Unused
        :param _data: Unused optional data, default None
        '''
        try:
            (but_list, but_iter) = self.view.get_selection().get_selected()
            (filename, _id) = but_list.get(but_iter, self.col_file, self.col_id)
        # pylint: disable=broad-except
        except Exception:
            self.logger.info("but_export broad-exception", exc_info=True)
            return

        platform = dplatform.get_platform()
        fname = platform.gui_save_file(default_name="%s.xml" % _id)
        if fname:
            shutil.copy(filename, fname)

    def make_list(self):
        '''
        Make List.

        :returns: Scrolled Window widget
        :rtype: :class:`Gtk.ScrolledWindow`
        '''
        self.col_id = 0
        self.col_title = 1
        self.col_file = 2

        self.store = Gtk.ListStore(GObject.TYPE_STRING,
                                   GObject.TYPE_STRING,
                                   GObject.TYPE_STRING)
        self.view = Gtk.TreeView.new_with_model(self.store)
        # Deprecated with GTK 3.14, from the documentation this is supposed
        # to be controlled by the theme.
        # self.view.set_rules_hint(True)
        self.view.show()

        col_list = [(self.col_id, _("ID")),
                    (self.col_title, _("Title"))]

        for col, cap in col_list:
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(cap, renderer, text=col)
            column.set_sort_column_id(col)

            self.view.append_column(column)

        scroll_window = Gtk.ScrolledWindow()
        scroll_window.add(self.view)
        scroll_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll_window.show()

        return scroll_window

    def make_buttons(self):
        '''
        Make buttons

        :returns: Box object
        :rtype: :class:`Gtk.Box`
        '''
        button_list = [(_("New"), self.but_new),
                       (_("Edit"), self.but_edit),
                       (_("Delete"), self.but_delete),
                       (_("Close"), self.but_close),
                       (_("Import"), self.but_import),
                       (_("Export"), self.but_export),
                       ]

        hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 2)
        hbox.set_homogeneous(True)

        for cap, func in button_list:
            button = Gtk.Button.new_with_label(cap)
            button.connect("clicked", func, None)
            button.show()
            hbox.add(button)

        hbox.show()

        return hbox


def main():
    '''Form Builder Unit test.'''

    from . import config
    conf = config.DratsConfig(None)
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("FormbuilderTest")

    form_templates = "Form_Templates"
    if not os.path.exists(form_templates):
        os.mkdir(form_templates)
    logger.info('Using %s for storage.', form_templates)
    _form_manager = FormManagerGUI(form_templates, conf)
    Gtk.main()

if __name__ == "__main__":
    main()
