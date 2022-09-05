#!/usr/bin/python
'''Map Source Editor.'''
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

from __future__ import absolute_import
from __future__ import print_function

import logging
import os
import shutil
# from glob import glob

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import GObject

if not '_' in locals():
    import gettext
    _ = gettext.gettext

from . import map_sources
from . import miscwidgets
from . import utils


class MapSourceEditorException(Exception):
    '''Generic Map Source Editor Exception.'''


class EditorInitCancel(MapSourceEditorException):
    '''Editor Init Cancel.'''


class GladeFileOpenError(MapSourceEditorException):
    '''Glade File Open Error.'''


class MapSourcesEditor():
    '''
    Map Sourced Editor.

    :param config: Configuration data
    :type config: :class:`DratsConfig`
    '''

    def __init__(self, config):
        self.logger = logging.getLogger("MapSourcesEditor")
        filename = config.ship_obj_fn("ui/mainwindow.glade")
        if not os.path.exists(filename):
            self.logger.info("Could not open %s", filename)
            raise GladeFileOpenError("Unable to load UI file")
        wtree = Gtk.Builder()
        wtree.add_from_file(filename)
        wtree.set_translation_domain("D-RATS")
        #wtree = Gtk.glade.XML(fn, "srcs_dialog", "D-RATS")

        self.__config = config
        self.__dialog = wtree.get_object("srcs_dialog")
        self.__view = wtree.get_object("srcs_view")
        addbtn = wtree.get_object("srcs_add")
        editbtn = wtree.get_object("srcs_edit")
        delbtn = wtree.get_object("srcs_delete")

        self._setup_view()
        typesel = self._setup_typesel(wtree)

        addbtn.connect("clicked", self._add, typesel)
        editbtn.connect("clicked", self._edit)
        delbtn.connect("clicked", self._rem)

        for stype, (edclass, srcclass) in SOURCE_TYPES.items():
            for key in srcclass.enumerate(self.__config):
                try:
                    src = srcclass.open_source_by_name(self.__config, key)
                    sed = edclass(self.__config, src)
                    self.__store.append((stype,
                                         sed.get_source().get_name(),
                                         sed))
                # pylint: disable=broad-except
                except Exception:
                    utils.log_exception()
                    self.logger.info("Failed to open source %s:%s; %s",
                                     stype, key,
                                     "broad-exception", exc_info=True)

    def _add(self, _button, typesel):
        '''
        Add Source.

        :param _button: Button pressed, unused
        :type _button: :class:Gtk.Button`
        :param typesel: Map type selected
        :type typesel: :class:`Gtk.ComboBoxText`
        '''
        text = typesel.get_active_text()

        try:
            element_type, _st = SOURCE_TYPES[text]
            element = element_type(self.__config)
        except EditorInitCancel:
            return

        response = element.run()
        if response == Gtk.ResponseType.OK:
            element.save()
            self.__store.append((text, element.get_source().get_name(), element))
        element.destroy()

    def _rem(self, _button):
        '''
        Remove Source.

        :param _button: Button pressed, unused
        :type _button: :class:`Gtk.Button`
        '''
        # self.__view is a Gtk.TreeView
        (model, sel_iter) = self.__view.get_selection().get_selected()
        # model is Gtk.ListStore
        # sel_iter is Gtk.TreeIter
        # self.__store is Gtk.ListStore
        element, = self.__store.get(sel_iter, 2)
        element.delete()

        model.remove(sel_iter)

    def _edit(self, _button):
        '''
        Edit Source.

        :param _button: Button pressed, unused
        :type _button: :class:`Gtk.Button
        '''
        (_model, sel_iter) = self.__view.get_selection().get_selected()

        element, = self.__store.get(sel_iter, 2)
        element.run()
        element.save()
        element.destroy()

    def _setup_view(self):
        self.__store = Gtk.ListStore(GObject.TYPE_STRING,
                                     GObject.TYPE_STRING,
                                     GObject.TYPE_PYOBJECT)
        self.__view.set_model(self.__store)

        col = Gtk.TreeViewColumn(_("Type"), Gtk.CellRendererText(), text=0)
        self.__view.append_column(col)

        col = Gtk.TreeViewColumn(_("Name"), Gtk.CellRendererText(), text=1)
        self.__view.append_column(col)

    # pylint: disable=no-self-use
    def _setup_typesel(self, wtree):
        choice = miscwidgets.make_choice(list(SOURCE_TYPES.keys()),
                                         False,
                                         "Static")
        choice.show()
        box = wtree.get_object("srcs_ctrlbox")
        box.pack_end(choice, 1, 1, 1)

        return choice

    def run(self):
        '''
        Run.

        :returns: Result from dialog.run
        :rtype: int
        '''
        return self.__dialog.run()

    def destroy(self):
        '''Destroy.'''
        self.__dialog.destroy()


class MapSourceEditor():
    '''
    Map Source Editor.

    :param config: Configuration data
    :type config: :class:`DratsConfig`
    :param source: Map source,
    :type source: :class:`MapSource`
    '''

    def __init__(self, config, source):
        self.logger = logging.getLogger("MapSourceEditor")
        self._config = config
        self.__source = source

        filename = config.ship_obj_fn("ui/mainwindow.glade")
        if not os.path.exists(filename):
            self.logger.info("Could not open %s", filename)
            raise GladeFileOpenError("Unable to load UI file")
        self._wtree = Gtk.Builder()
        self._wtree.add_from_file(filename)
        #self._wtree = Gtk.glade.XML(fn, "src_dialog", "D-RATS")

        self._src_dialog = self._wtree.get_object("src_dialog")
        self._name = self._wtree.get_object("src_name")

        self._name.set_text(source.get_name())

    def get_source(self):
        '''
        Get Source.

        :returns: Map Source
        :rtype: :class:`MapSource`
        '''
        return self.__source

    def get_name(self):
        '''
        Name.

        :returns: Name of MapSource
        :rtype: str
        '''
        return self._name.get_text()

    def name_editable(self, editable):
        '''
        Name Editable.

        :param editable: Enable to be editable
        :type editable: bool
        '''
        self._name.set_sensitive(editable)

    def run(self):
        '''
        Run.

        :returns: Result from dialog.run()
        '''
        return self._src_dialog.run()

    def destroy(self):
        '''Destroy.'''
        self._src_dialog.hide()

    def delete(self):
        '''Delete.'''
        #pass

    def save(self):
        '''Save.'''
        # pass


class StaticMapSourceEditor(MapSourceEditor):
    '''
    Static Map Source Editor.

    :param config: Configuration data
    :type config: :class:`DratsConfig`
    :param source: Map source,
                   default from static_locations in configuration data
    :type source: :class:`MapSource`
    '''

    def __init__(self, config, source=None):
        if not source:
            filename = config.platform.gui_open_file()
            if not filename:
                raise EditorInitCancel()

            new_fn = os.path.join(config.platform.config_file("static_locations"),
                                  os.path.basename(filename))
            shutil.copy(filename, new_fn)
            filename = new_fn

            source = map_sources.MapFileSource(os.path.basename(new_fn),
                                               "Static Source",
                                               new_fn)

        MapSourceEditor.__init__(self, config, source)

        label = Gtk.Label.new("Nothing to edit here")
        label.show()

        box = self._wtree.get_object("src_vbox")
        box.pack_start(label, 1, 1, 1)

        self.name_editable(False)

    def delete(self):
        os.remove(self.get_source().get_filename())

    def save(self):
        self.get_source().save()


class RiverMapSourceEditor(MapSourceEditor):
    '''
    River Map Source Editor.

    :param config: Configuration data
    :type config: :class:`DratsConfig`
    :param source: Map source,
                   default "Rivers", "NWIS Rivers"
    :type source: :class:`MapSource`
    '''
    def __init__(self, config, source=None):
        self.logger = logging.getLogger("RiverMapSourceEditor")
        if not source:
            source = map_sources.MapUSGSRiverSource("Rivers", "NWIS Rivers")
            name_editable = True
        else:
            name_editable = False
        self.__source = source

        MapSourceEditor.__init__(self, config, source)

        box = self._wtree.get_object("src_vbox")

        hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 2)
        hbox.show()

        label = Gtk.Label.new(_("Sites (comma separated)"))
        label.show()
        hbox.pack_start(label, 0, 0, 0)

        self.__sites = Gtk.Entry()
        self.__sites.show()
        _sites = [str(x) for x in source.get_sites()]
        self.__sites.set_text(",".join(_sites))
        self._new_sites = ",".join(_sites)
        hbox.pack_start(self.__sites, 1, 1, 1)

        box.pack_start(hbox, 1, 1, 1)

        self.name_editable(name_editable)
        # self.__sites.connect("changed", self.entry_changed)
        self._src_dialog.connect("response", self.entry_changed)

    def entry_changed(self, _widget, _response_id):
        '''
        Text Entry Changed Response.

        :param widget: Text entry widget
        :type widget: :class:`Gtk.Dialog`
        :param response_id: Response Id
        :type response_id: int
        '''
        self._new_sites = self.__sites.get_text()

    def delete(self):
        '''Delete.'''
        ident = self.get_source().packed_name()
        try:
            self._config.remove_option("rivers", ident)
            self._config.remove_option("rivers", "%s.label" % ident)
        # pylint: disable=broad-except
        except Exception:
            utils.log_exception()
            self.logger.info("Error deleting rivers/%s broad-except",
                             ident, exc_info=True)

    def save(self):
        '''Save.'''
        if not self._config.has_section("rivers"):
            self._config.add_section("rivers")
        self.get_source().set_name(self.get_name())
        ident = self.get_source().packed_name()
        self._config.set("rivers", ident, self._new_sites)
        self._config.set("rivers", "%s.label" % ident,
                         self.get_source().get_name())


class BuoyMapSourceEditor(MapSourceEditor):
    '''
    Buoy Map Source Editor.

    :param config: Configuration data
    :type config: :class:`DratsConfig`
    :param source: Map source,
                   default "Buoys", "NBDC Rivers"
    :type source: :class:`MapSource`
    '''

    def __init__(self, config, source=None):
        self.logger = logging.getLogger("BuoyMapSourceEditor")
        if not source:
            source = map_sources.MapNBDCBuoySource("Buoys", "NBDC Rivers")
            name_editable = True
        else:
            name_editable = False

        MapSourceEditor.__init__(self, config, source)

        box = self._wtree.get_object("src_vbox")

        hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 2)
        hbox.show()

        label = Gtk.Label.new(_("Buoys (comma separated)"))
        label.show()
        hbox.pack_start(label, 0, 0, 0)

        self.__sites = Gtk.Entry()
        self.__sites.show()
        _sites = [str(x) for x in source.get_buoys()]
        self.__sites.set_text(",".join(_sites))
        hbox.pack_start(self.__sites, 1, 1, 1)

        box.pack_start(hbox, 1, 1, 1)

        self.name_editable(name_editable)

    def delete(self):
        '''Delete.'''
        ident = self.get_source().packed_name()
        try:
            self._config.remove_option("buoys", ident)
            self._config.remove_option("buoys", "%s.label" % ident)
        # pylint: disable=broad-except
        except Exception:
            utils.log_exception()
            self.logger.info("Error deleting buoys/%s: broad-exception",
                             ident, exc_info=True)


    def save(self):
        '''Save.'''
        if not self._config.has_section("buoys"):
            self._config.add_section("buoys")
        self.get_source().set_name(self.get_name())
        ident = self.get_source().packed_name()
        self._config.set("buoys", ident, self.__sites.get_text())
        self._config.set("buoys", "%s.label" % ident,
                         self.get_source().get_name())


SOURCE_TYPES = {
    "Static" : (StaticMapSourceEditor, map_sources.MapFileSource),
    "NWIS River" : (RiverMapSourceEditor, map_sources.MapUSGSRiverSource),
    "NBDC Buoy" : (BuoyMapSourceEditor, map_sources.MapNBDCBuoySource),
    }
