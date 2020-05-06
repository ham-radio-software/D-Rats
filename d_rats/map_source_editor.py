#!/usr/bin/python
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
import os
import shutil
from glob import glob

import gtk
import gobject

from . import map_sources
from . import miscwidgets
from . import utils

class EditorInitCancel(Exception):
    pass

class MapSourcesEditor(object):
    def _add(self, button, typesel):
        t = typesel.get_active_text()

        try:
            et, st = SOURCE_TYPES[t]
            e = et(self.__config)
        except EditorInitCancel:
            return

        r = e.run()
        if r == gtk.RESPONSE_OK:
            e.save()
            self.__store.append((t, e.get_source().get_name(), e))
        e.destroy()

    def _rem(self, button):
        (model, iter) = self.__view.get_selection().get_selected()

        e, = self.__store.get(iter, 2)
        e.delete()

        model.remove(iter)

    def _edit(self, button):
        (model, iter) = self.__view.get_selection().get_selected()

        e, = self.__store.get(iter, 2)
        e.run()
        e.save()
        e.destroy()

    def _setup_view(self):
        self.__store = gtk.ListStore(gobject.TYPE_STRING,
                                     gobject.TYPE_STRING,
                                     gobject.TYPE_PYOBJECT)
        self.__view.set_model(self.__store)

        c = gtk.TreeViewColumn(_("Type"), gtk.CellRendererText(), text=0)
        self.__view.append_column(c)

        c = gtk.TreeViewColumn(_("Name"), gtk.CellRendererText(), text=1)
        self.__view.append_column(c)

    def _setup_typesel(self, wtree):
        choice = miscwidgets.make_choice(list(SOURCE_TYPES.keys()),
                                         False,
                                         "Static")
        choice.show()
        box = wtree.get_widget("srcs_ctrlbox")
        box.pack_end(choice, 1, 1, 1)

        return choice

    def __init__(self, config):
        fn = config.ship_obj_fn("ui/mainwindow.glade")
        if not os.path.exists(fn):
            print(fn)
            raise Exception("Unable to load UI file")
        wtree = gtk.glade.XML(fn, "srcs_dialog", "D-RATS")

        self.__config = config
        self.__dialog = wtree.get_widget("srcs_dialog")
        self.__view = wtree.get_widget("srcs_view")
        addbtn = wtree.get_widget("srcs_add")
        editbtn = wtree.get_widget("srcs_edit")
        delbtn = wtree.get_widget("srcs_delete")

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
                except Exception as e:
                    utils.log_exception()
                    print("Failed to open source %s:%s" % (stype, key))

    def run(self):
        return self.__dialog.run()

    def destroy(self):
        self.__dialog.destroy()

class MapSourceEditor(object):
    def __init__(self, config, source):
        self._config = config
        self.__source = source

        fn = config.ship_obj_fn("ui/mainwindow.glade")
        if not os.path.exists(fn):
            print(fn)
            raise Exception("Unable to load UI file")
        self._wtree = gtk.glade.XML(fn, "src_dialog", "D-RATS")

        self.__dialog = self._wtree.get_widget("src_dialog")
        self._name = self._wtree.get_widget("src_name")

        self._name.set_text(source.get_name())

    def get_source(self):
        return self.__source

    def get_name(self):
        return self._name.get_text()

    def name_editable(self, editable):
        self._name.set_sensitive(editable)

    def run(self):
        return self.__dialog.run()

    def destroy(self):
        self.__dialog.hide()

    def delete(self):
        pass

    def save(self):
        pass

class StaticMapSourceEditor(MapSourceEditor):
    def __init__(self, config, source=None):
        if not source:
            fn = config.platform.gui_open_file()
            if not fn:
                raise EditorInitCancel()

            nfn = os.path.join(config.platform.config_file("static_locations"),
                               os.path.basename(fn))
            shutil.copy(fn, nfn)
            fn = nfn

            source = map_sources.MapFileSource(os.path.basename(nfn),
                                               "Static Source",
                                               nfn)

        MapSourceEditor.__init__(self, config, source)

        label = gtk.Label("Nothing to edit here")
        label.show()

        box = self._wtree.get_widget("src_vbox")
        box.pack_start(label, 1, 1, 1)

        self.name_editable(False)

    def delete(self):
        os.remove(self.get_source().get_filename())

    def save(self):
        self.get_source().save()

class RiverMapSourceEditor(MapSourceEditor):
    def __init__(self, config, source=None):
        if not source:
            source = map_sources.MapUSGSRiverSource("Rivers", "NWIS Rivers")
            name_editable = True
        else:
            name_editable = False

        MapSourceEditor.__init__(self, config, source)

        box = self._wtree.get_widget("src_vbox")
        
        hbox = gtk.HBox(False, 2)
        hbox.show()

        label = gtk.Label(_("Sites (comma separated)"))
        label.show()
        hbox.pack_start(label, 0, 0, 0)

        self.__sites = gtk.Entry()
        self.__sites.show()
        _sites = [str(x) for x in source.get_sites()]
        self.__sites.set_text(",".join(_sites))
        hbox.pack_start(self.__sites, 1, 1, 1)

        box.pack_start(hbox, 1, 1, 1)

        self.name_editable(name_editable)

    def delete(self):
        id = self.get_source().packed_name()
        try:
            self._config.remove_option("rivers", id)
            self._config.remove_option("rivers", "%s.label" % id)
        except Exception as e:
            log_exception()
            print("Error deleting rivers/%s: %s" % (id, e))

    def save(self):
        if not self._config.has_section("rivers"):
            self._config.add_section("rivers")
        self.get_source().set_name(self.get_name())
        id = self.get_source().packed_name()
        self._config.set("rivers", id, self.__sites.get_text())
        self._config.set("rivers", "%s.label" % id,
                         self.get_source().get_name())

class BuoyMapSourceEditor(MapSourceEditor):
    def __init__(self, config, source=None):
        if not source:
            source = map_sources.MapNBDCBuoySource("Buoys", "NBDC Rivers")
            name_editable = True
        else:
            name_editable = False

        MapSourceEditor.__init__(self, config, source)

        box = self._wtree.get_widget("src_vbox")
        
        hbox = gtk.HBox(False, 2)
        hbox.show()

        label = gtk.Label(_("Buoys (comma separated)"))
        label.show()
        hbox.pack_start(label, 0, 0, 0)

        self.__sites = gtk.Entry()
        self.__sites.show()
        _sites = [str(x) for x in source.get_buoys()]
        self.__sites.set_text(",".join(_sites))
        hbox.pack_start(self.__sites, 1, 1, 1)

        box.pack_start(hbox, 1, 1, 1)

        self.name_editable(name_editable)

    def delete(self):
        id = self.get_source().packed_name()
        try:
            self._config.remove_option("buoys", id)
            self._config.remove_option("buoys", "%s.label" % id)
        except Exception as e:
            log_exception()
            print("Error deleting buoys/%s: %s" % (id, e))


    def save(self):
        if not self._config.has_section("buoys"):
            self._config.add_section("buoys")
        self.get_source().set_name(self.get_name())
        id = self.get_source().packed_name()
        self._config.set("buoys", id, self.__sites.get_text())
        self._config.set("buoys", "%s.label" % id,
                         self.get_source().get_name())


SOURCE_TYPES = {
    "Static" : (StaticMapSourceEditor, map_sources.MapFileSource),
    "NWIS River" : (RiverMapSourceEditor, map_sources.MapUSGSRiverSource),
    "NBDC Buoy" : (BuoyMapSourceEditor, map_sources.MapNBDCBuoySource),
    }

