'''Map Window Module.'''
# pylint: disable=too-many-lines
#
# Copyright 2021-2022 John Malmberg <wb8tyw@gmail.com>
# Portions derived from works:
# Copyright 2009 Dan Smith <dsmith@danplanet.com>
# review 2019 Maurizio Andreotti  <iz2lxi@yahoo.it>
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
from __future__ import unicode_literals

import logging
import shutil
import tempfile
import time

import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GObject

from .. import dplatform
from .. import inputdialog
from .. import map_sources
from .. import miscwidgets
from .. import signals
from .. import map_source_editor
from ..gps import GPSPosition
from .. import map as Map
from ..ui.main_common import ask_for_confirmation

# This makes pylance happy with out overriding settings
# from the invoker of the class
if not '_' in locals():
    import gettext
    _ = gettext.gettext


# We have more than 7 instance attributes and more than 20 public methods
# pylint: disable=too-many-instance-attributes, too-many-public-methods
class MapWindow(Gtk.ApplicationWindow):
    '''
    Map Window.

    This Creates the main map window display.

    :param application:
    :type application: :class:`Gtk.Application`
    :param config: Configuration data
    :type config: :class:`DratsConfig`
    '''

    __gsignals__ = {
        "reload-sources" : (GObject.SignalFlags.RUN_LAST,
                            GObject.TYPE_NONE, ()),
        "user-send-chat" : signals.USER_SEND_CHAT,
        "get-station-list" : signals.GET_STATION_LIST
        }

    _signals = {"user-send-chat" : None,
                "get-station-list" : None
                }

    CROSSHAIR = "+"
    STATUS_COORD = 0
    STATUS_CENTER = 1
    STATUS_GPS = 2

    def __init__(self, application, config):
        Gtk.ApplicationWindow.__init__(self, application=application)

        self.logger = logging.getLogger("MapWindow")

        self.connect("destroy", self.ev_destroy)
        self.connect("delete_event", self.ev_delete)

        self.config = config
        # self.map_tiles = []
        self.logger.info("init MapWindow")

        self.center_mark = None
        self.tracking_enabled = False
        self.__last_motion = None
        self._newcenter = None
        self.map_sources = []
        self.points_visible = []
        self.colors = {}
        self.exiting = False
        # this parameter defines the dimension of the map behind the window
        # tiles SHALL be
        #  - ODD due to the mechanism used then to calculate the
        #    offsets to keep aligned the stations markers in the map into the
        #    calculate_bound
        #  - the same for both x and y in the mapwidget creation
        tiles = 9

        box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 2)

        self.menubar = self._make_menu()
        self.menubar.show()

        box.pack_start(self.menubar, False, False, False)

        self.map_widget = Map.Widget(width=tiles, height=tiles,
                                     window=self)
        self.map_widget.show()
        Map.Tile.set_map_widget(self.map_widget)

        self.scrollw = Gtk.ScrolledWindow()
        self.scrollw.add(self.map_widget)
        self.scrollw.show()

        self.map_widget.add_events(Gdk.EventMask.POINTER_MOTION_MASK)
        self.scrollw.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.map_widget.connect("motion-notify-event", self._mouse_move_event)
        self.scrollw.connect("button-press-event", self._mouse_click_event)
        # self.scrollw.connect("scroll-event", self.map_widget.scroll_event)
        hadj = self.scrollw.get_hadjustment()
        vadj = self.scrollw.get_vadjustment()
        hadj.connect("value-changed", self.map_widget.value_x_event)
        vadj.connect("value-changed", self.map_widget.value_y_event)

        self.statusbox = Map.StatusBox()
        bottom_panel = Map.BottomPanel(self)
        self.mapcontrols = bottom_panel.controls
        self.marker_list = bottom_panel.marker_list
        box.pack_start(self.scrollw, True, True, True)
        box.pack_start(bottom_panel, False, False, False)
        box.pack_start(self.statusbox, False, False, False)
        box.show()

        #setup the default dimensions for the map window
        self.set_default_size(800, 600)

        self.add(box)
        Map.PopupModel.add_actions(self)
        self.marker_model = Map.MarkerPopupModel()
        self.marker_model.add_actions(self)
        self.marker_menu = Gtk.Menu.new_from_model(self.marker_model)
        self.marker_menu.attach_to_widget(self)

        # create the INFO WINDOW which is shown over the map clicking
        # the left mouse button
        self.info_window = Gtk.Window(type=Gtk.WindowType.POPUP)
        self.info_window.set_type_hint(Gdk.WindowTypeHint.MENU)
        self.info_window.set_decorated(False)
        self.info_window.set_name("map_info_window")
        # modify_bg deprecated for override_background_color
        # override_background_color deprecated, use Gtk.StyleProvider and
        # a CSS style class or modifying drawing through the draw signal with
        # Cairo.
        # self.info_window.modify_bg(Gtk.StateType.NORMAL,
        #                           Gdk.color_parse("yellow"))

    def add_map_source(self, source):
        '''
        Add Map Source.

        :param source: A map source
        :type source: :class:`MapSource`
        '''
        self.map_sources.append(source)
        self.marker_list.add_item(None,
                                  source.get_visible(), source.get_name(),
                                  0.0, 0.0, 0.0, 0.0)
        for point in source.get_points():
            self.add_point(source, point)


        ##source.connect("point-updated", self.update_point)
        source.connect("point-added", self.add_point)
        source.connect("point-deleted", self.del_point)
        source.connect("point-updated", self.maybe_recenter_on_updated_point)

    def add_point(self, source, point):
        '''
        Add Point.

        :param source: Map source
        :type source: :class:`MapSource`
        :param point: Point to update
        :type point: :class:`MapPoint`
        '''
        # (_lat, _lon) = self.map.get_center()
        center = GPSPosition(self.map_widget.position.latitude,
                             self.map_widget.position.longitude)
        this = GPSPosition(point.get_latitude(), point.get_longitude())

        self.marker_list.add_item(source.get_name(),
                                  point.get_visible(), point.get_name(),
                                  point.get_latitude(),
                                  point.get_longitude(),
                                  center.distance_from(this),
                                  center.bearing_to(this))
        self.add_point_visible(point)
        self.map_widget.queue_draw()

    def add_point_visible(self, point):
        '''
        Add Point Visible.

        :param point: Point to add
        :type point: :class:`MapPoint`
        :returns: True if point is visible
        '''
        if point in self.points_visible:
            self.points_visible.remove(point)

        if self.map_widget.point_is_visible(point):
            if point.get_visible():
                self.points_visible.append(point)
                return True
            return False
        return False

    # Inherited from Parent and called by mainapp
    # def connect(self, signal name, function):

    # called by mainapp
    def clear_map_sources(self):
        '''Clean Map Sources.'''
        self.marker_list.clear()
        self.map_sources = []
        self.points_visible = []
        self.update_points_visible()
        self.map_widget.queue_draw()

    def del_point(self, source, point):
        '''
        Delete Point.

        :param source: Map source
        :type source: :class:`MapSource`
        :param point: Point to update
        :type point: :class:`MapPoint`
        '''
        self.marker_list.del_item(source.get_name(), point.get_name())

        if point in self.points_visible:
            self.points_visible.remove(point)

        self.map_widget.queue_draw()

    @staticmethod
    def ev_destroy(widget, _data=None):
        '''
        Event Destroy

        Signaled when all holders of a reference to a widget should release
        the reference that they hold.

        May result in finalization of the widget if all references are released
        Any return value usage not documented in Gtk 3
        :param widget: Widget
        :type widget: :class:`Map.MapWindow`
        :param _data: data (unused)
        :returns: True to stop other handlers for this signal from running
        :rtype: bool
        '''
        if not widget.exiting:
            widget.hide()  # Probably redundant
            return True
        return False

    @staticmethod
    def ev_delete(widget, _event, _data=None):
        '''
        Event Delete.  Intercepts the closing of a window so that it
        can be hidden and re-used.

        Hides this object
        :param widget: Widget (unused)
        :type widget: :class:`Map.MapWindow`
        :param _event: event (unused)
        :type _event: :class:`Gtk.Event`
        :param _data: data (unused)
        :returns: True to stop other handlers for this signal from running
        :rtype: bool
        '''
        if not widget.exiting:
            widget.hide()
            return True
        return False

    # called my mainapp
    def get_map_source(self, name):
        '''
        Get Map source.

        :param name: Map Source Name
        :type station: str
        :returns: maps for a station
        :rtype: :class:`MapFileSource`
        '''
        for source in self.get_map_sources():
            if source.get_name() == name:
                return source
        return None

    # Called by mainapp and qst.py
    def get_map_sources(self):
        '''
        Get Map Sources.

        :returns: Map sources
        :rtype: list of :class:`MapFileSource`
        '''
        return self.map_sources

    def get_visible_bounds(self):
        '''
        Get Visible Bounds.

        :returns: tuple with bounds
        :rtype: tuple
        '''
        hadj = self.scrollw.get_hadjustment()
        vadj = self.scrollw.get_vadjustment()

        return (int(hadj.get_value()), int(vadj.get_value()),
                int(hadj.get_value() + hadj.get_page_size()),
                int(vadj.get_value() + vadj.get_page_size()))

    def item_clearcache_handler(self, _action, _value):
        '''
        Clear Cache Handler.

        :param _action: Action that was invoked, Unused
        :type _action: :class:`GioSimpleAction`
        :param _value: Value for action, Unused
        '''
        base_dir = Map.Tile.get_base_dir()
        dialog = Gtk.MessageDialog(buttons=Gtk.ButtonsType.YES_NO)
        dialog.set_property("text",
                            _("Are you sure you want to delete all"
                              "your map files in \n %s\n?") % base_dir)
        run_status = dialog.run()
        dialog.destroy()

        if run_status == Gtk.ResponseType.YES:
            base_dir = Map.Tile.get_base_dir()
            shutil.rmtree(base_dir, True)
            self.map_widget.queue_draw()

    def item_editsources_handler(self, _action, _value):
        '''
        Edit Sources Handler.

        :param _action: Action that was invoked
        :type _action: :class:`GioSimpleAction`
        :param _value: Value for action, Unused
        '''
        srced = map_source_editor.MapSourcesEditor(self.config)
        srced.run()
        srced.destroy()
        self.emit("reload-sources")

    def item_printable_handler(self, _action, _value):
        '''
        Printable Item Handler.

        :param _action: Action that was invoked, Unused
        :type _action: :class:`GioSimpleAction`
        :param _value: Value for action, Unused
        '''
        self.printable_map()

    def item_printablevis_handler(self, _action, _value):
        '''
        Printable Visible Item Handler.

        :param _action: Action that was invoked, Unused
        :type _action: :class:`GioSimpleAction`
        :param _value: Value for action, Unused
        '''
        self.printable_map(self.get_visible_bounds())

    def item_refresh_handler(self, _action, _value):
        '''
        Refresh Item Handler.

        :param _action: Action that was invoked, Unused
        :type _action: :class:`GioSimpleAction`
        :param _value: Value for action, Unused
        '''
        self.map_widget.queue_draw()

    def item_save_handler(self, _action, _value):
        '''
        Save Item Handler.

        :param _action: Action that was invoked, Unused
        :type _action: :class:`GioSimpleAction`
        :param _value: Value for action, Unused
        '''
        self.save_map()

    def item_savevis_handler(self, _action, _value):
        '''
        Save Visible Item Handler.

        :param _action: Action that was invoked, Unused
        :type _action: :class:`GioSimpleAction`
        :param _value: Value for action, Unused
        '''
        self.save_map(self.get_visible_bounds())

    def make_marker_popup(self, widget, view, event):
        '''
        Make Marker Popup.

        :param widget: Widget with marker data
        :type widget: :class:`Map.MapMarkerList`
        :param view: View for popup
        :type view: :class:`Gtk.Treeview`
        :param event: Mouse click event
        :type event: :class:`Gdk.Event`
        '''
        if event.button.button != 3:
            return

        if event.window == view.get_bin_window():
            x_axis, y_axis = event.get_coords()
            pathinfo = view.get_path_at_pos(int(x_axis), int(y_axis))
            if pathinfo is None:
                return
            view.set_cursor_on_cell(pathinfo[0], None, None, False)

        (store, iter_value) = view.get_selection().get_selected()
        try:
            ident, = store.get(iter_value, 1)
            group, = store.get(store.iter_parent(iter_value), 1)
        except TypeError:
            ident = "i"
            group = "g"

        self.marker_model.change_state(group, ident)
        self.marker_menu.popup_at_widget(widget, Gdk.Gravity.STATIC,
                                         Gdk.Gravity.STATIC, None)

    def marker_center_handler(self, action, _value):
        '''
        Marker Center Handler.

        :param action: Action that was invoked
        :type action: :class:`GioSimpleAction`
        :param _value: Value for action, Unused
        :type _value: :class:`Gio.VariantType`
        '''
        print("self", type(self))
        state = action.get_state()
        group_var = state.get_child_value(0)
        ident_var = state.get_child_value(1)
        print("group_var", type(group_var))
        print("ident_var", type(ident_var))
        group = group_var.get_string()
        ident = ident_var.get_string()
        print("group", group)
        print("ident", ident)

    def marker_delete_handler(self, action, _value):
        '''
        Marker Delete Handler.

        :param action: Action that was invoked
        :type action: :class:`GioSimpleAction`
        :param _value: Value for action, Unused
        :type _value: :class:`Gio.VariantType`
        '''
        print("self", type(self))
        state = action.get_state()
        group_var = state.get_child_value(0)
        ident_var = state.get_child_value(1)
        print("group_var", type(group_var))
        print("ident_var", type(ident_var))
        group = group_var.get_string()
        ident = ident_var.get_string()
        print("group", group)
        print("ident", ident)

    def marker_edit_handler(self, action, _value):
        '''
        Marker Edit Handler.

        :param action: Action that was invoked
        :type action: :class:`GioSimpleAction`
        :param value: Value for action, Unused
        :type value: :class:`Gio.VariantType`
        '''
        print("self", type(self))
        state = action.get_state()
        group_var = state.get_child_value(0)
        ident_var = state.get_child_value(1)
        print("group_var", type(group_var))
        print("ident_var", type(ident_var))
        group = group_var.get_string()
        ident = ident_var.get_string()
        print("group", group)
        print("ident", ident)

    def _make_menu(self):
        '''
        Menu for map.

        :returns: Menu for map
        :rtype: :class:`Gtk.Menubar`
        '''
        model = Map.MenuModel()
        model.add_actions(self)
        menubar = Gtk.MenuBar.new_from_model(model)
        return menubar

    def maybe_recenter_on_updated_point(self, source, point):
        '''
        Maybe Recenter on Updated Point.

        :param source: Map source
        :type source: :class:`MapSource`
        :param point: Point to update
        :type point: :class:`MapPoint`
        '''
        if point.get_name() == self.center_mark and self.tracking_enabled:
            self.logger.into("maybe_recenter_on_updated_point: Center updated")
            position = Map.Position(point.get_latitude(),
                                    point.get_longitude())
            self.recenter(position)
        self.update_point(source, point)

    def _mouse_click_event(self, widget, event):
        '''
        Mouse Click Event.

        :param widget: Widget clicked on
        :type widget: :class:`Gtk.ScrolledWindow`
        :param event: Event that triggered this handler
        :type event: :class:`Gdk.EventButton`
        :returns: True to stop other handlers from processing the event.
        :rtype: bool
        '''
        x_axis, y_axis = event.get_coords()

        hadj = widget.get_hadjustment()
        vadj = widget.get_vadjustment()
        mx_axis = x_axis + int(hadj.get_value())
        my_axis = y_axis + int(vadj.get_value())

        position = Map.Tile.display2deg(mx_axis, my_axis)

        self.logger.info("Button %i at %i,%i",
                         event.button, mx_axis, my_axis)
        # Need to test for _2BUTTON_PRESS before testing
        # for a normal button press.
        # This is not a protected-access, it is the actual
        # python name for the type.
        # pylint: disable=protected-access
        self._newcenter = position
        if event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS:
            self.logger.info("recenter on %.s", position)
            self.recenter(position)
        elif event.button == 3:
            vals = {"lat" : position.latitude,
                    "lon" : position.longitude,
                    "x" : mx_axis,
                    "y" : my_axis}
            self.logger.info("Clicked 3: %s", vals)
            popup_model = Map.PopupModel(position)
            popup_menu = Gtk.Menu.new_from_model(popup_model)
            popup_menu.attach_to_widget(self)
            popup_menu.popup_at_pointer()
        # elif event.type == Gdk.EventType.BUTTON_PRESS:
            #self.logger.info("Clicked: %s", position)
            # This was found commented out:
            # original code:
            # The crosshair marker has been missing since 0.3.0
            # self.set_marker(GPSPosition(station=self.CROSSHAIR,
            #                             lat=position.latitude,
            #                             lon=position.longitude))
            # end of original code

    def _mouse_move_event(self, _widget, event):
        '''
        Mouse Move Event.

        :param _widget: Widget that received the signal, Not used
        :type _widget: :class:`map.MapWidget`
        :param event: Event that triggered this handler.
        :type event: :class:`Gdk.EventMotion`
        :returns: True to stop other handlers from being invoked
        :rtype: bool
        '''
        if not self.__last_motion:
            GLib.timeout_add(5, self._mouse_motion_handler)
        self.__last_motion = (time.time(), event.x, event.y)

    # pylint: disable=too-many-locals
    def _mouse_motion_handler(self):
        if self.__last_motion is None:
            return False

        time_motion, x_axis, y_axis = self.__last_motion
        if (time.time() - time_motion) < 0.5:
            self.info_window.hide()
            return True

        position = Map.Tile.display2deg(x_axis, y_axis)
        hadj = self.scrollw.get_hadjustment()
        vadj = self.scrollw.get_vadjustment()
        mx_axis = x_axis - int(hadj.get_value())
        my_axis = y_axis - int(vadj.get_value())

        hit = False
        for source in self.map_sources:
            if not source.get_visible():
                continue
            for point in source.get_points():
                if not point.get_visible():
                    continue
                try:
                    pos = Map.Position(point.get_latitude(),
                                       point.get_longitude())
                    point_x, point_y = Map.Tile.deg2display(pos)
                except ZeroDivisionError:
                    print("ZeroDivisionError")
                    continue

                dx_axis = abs(x_axis - point_x)
                dy_axis = abs(y_axis - point_y)

                if dx_axis >= 20 or dy_axis >= 20:
                    continue

                hit = True

                date = time.ctime(point.get_timestamp())

                # span is temp hack until we get css implemented.
                text = '<span background="yellow">' + \
                       "<b>Station:</b> %s" % point.get_name() + \
                       "\n<b>Latitude:</b> %.5f" % point.get_latitude() + \
                       "\n<b>Longitude:</b> %.5f"% point.get_longitude() + \
                       "\n<b>Last update:</b> %s" % date

                text += "\n<b>Info</b>: %s" % point.get_comment()
                text += "</span>"
                label = Gtk.Label()
                label.set_markup(text)
                label.show()
                for child in self.info_window.get_children():
                    self.info_window.remove(child)
                self.info_window.add(label)

                posx, posy = self.get_position()
                posx += mx_axis + 10
                posy += my_axis - 10

                self.info_window.move(int(posx), int(posy))
                self.info_window.show()
                break

        if not hit:
            self.info_window.hide()

        self.statusbox.sb_coords.pop(self.STATUS_COORD)
        self.statusbox.sb_coords.push(self.STATUS_COORD,
                                      str(position))
        self.__last_motion = None

        return False

    def popup_center_handler(self, _action, _value):
        '''
        Popup Center Handler.

        :param _action: Action that was invoked, Unused
        :type _action: :class:`GioSimpleAction`
        :param _value: Value for action, Unused
        '''
        if self._newcenter:
            self.recenter(self._newcenter)
            self._newcenter = None
            return
        self.logger.info("popup center handler - no new position set")

    def popup_newmarker_handler(self, _action, _value):
        '''
        Popup New Marker Handler.

        :param _action: Action that was invoked, Unused
        :type _action: :class:`GioSimpleAction`
        :param _value: Value for action, Unused
        '''
        self.set_mark_at()

    def popup_broadcast_handler(self, _action, _value):
        '''
        Popup Broadcast Handler.

        :param _action: Action that was invoked, Unused
        :type _action: :class:`GioSimpleAction`
        :param _value: Value for action, Unused
        '''
        self.prompt_to_send_loc()

    def printable_map(self, bounds=None):
        '''
        Printable Map.

        :param bounds: Bounds to save, Default None
        :type bounds: tuple of 4 elements
        '''
        GLib.timeout_add(1000, self.printable_map_handler, bounds)

    def printable_map_handler(self, bounds):
        '''
        Printable Map Handler.

        :param bounds: Bounds to save
        :type bounds: tuple of 4 elements
        :returns: False to prevent timer retriggering
        :rtype: bool
        '''
        platform = dplatform.get_platform()

        file_handle = tempfile.NamedTemporaryFile()
        fname = file_handle.name
        file_handle.close()

        map_file = "%s.png" % fname
        html_file = "%s.html" % fname

        time_stamp = time.strftime("%H:%M:%S %d-%b-%Y")

        station_map = _("Station map")
        generated_at = _("Generated at")

        html = """
<html>
<body>
<h2>D-RATS %s</h2>
<h5>%s %s</h5>
<img src="file://%s"/>
</body>
</html>
""" % (station_map, generated_at, time_stamp, map_file)

        self.map_widget.export_to(map_file, bounds)

        file_handle = open(html_file, "w")
        file_handle.write(html)
        file_handle.close()

        platform.open_html_file(html_file)
        return False

    # Called by mainapp not sure if inherited
    # def queue_draw(self):

    def prompt_to_send_loc(self):
        '''
        Prompt to send location.
        '''
        dialog = inputdialog.FieldDialog(title=_("Broadcast Location"))

        callsign_e = Gtk.Entry()
        callsign_e.set_max_length(8)
        dialog.add_field(_("Callsign"), callsign_e)
        desc_e = Gtk.Entry()
        desc_e.set_max_length(20)
        dialog.add_field(_("Description"), desc_e)
        dialog.add_field(_("Latitude"), miscwidgets.LatLonEntry())
        dialog.add_field(_("Longitude"), miscwidgets.LatLonEntry())
        if self._newcenter:
            lat = self._newcenter.latitude
            lon = self._newcenter.longitude
            dialog.get_field(_("Latitude")).set_text("%.4f" % lat)
            dialog.get_field(_("Longitude")).set_text("%.4f" % lon)

        while dialog.run() == Gtk.ResponseType.OK:
            # pylint: disable=broad-except
            try:
                call = dialog.get_field(_("Callsign")).get_text()
                desc = dialog.get_field(_("Description")).get_text()
                lat = dialog.get_field(_("Latitude")).get_text()
                lon = dialog.get_field(_("Longitude")).get_text()

                fix = GPSPosition(lat=lat, lon=lon, station=call)
                fix.comment = desc

                for port in self.emit("get-station-list").keys():
                    self.emit("user-send-chat",
                              "CQCQCQ", port,
                              fix.to_NMEA_GGA(), True)

                break
            except AttributeError:
                # This happens when unit testing because mainapp has not
                # been setup so nothing is returned for get-station-list
                self.logger.info('prompt_to_send_log: failed to send',
                                 exc_info=True)
            except Exception as err:
                # Eventually this handler should be removed.
                print("Mapdiplay.MapWindow.prompt_to_send_loc",
                      " Broad Exception (%s) %s" % (type(err), err))
                # utils.log_exception()
                except_dialog = Gtk.MessageDialog(buttons=Gtk.ButtonsType.OK,
                                                  parent=dialog)
                except_dialog.set_property("text",
                                           _("Invalid value") + ": %s" % err)
                except_dialog.run()
                except_dialog.destroy()

        dialog.destroy()

    def prompt_to_set_marker(self, point, group=None):
        '''
        Prompt to set marker.

        :param point: Point to set marker on
        :param group: Optional group
        :returns: Tuple of (point, group) or (None, None)
        '''
        # def do_address(_button, latw, lonw, namew):
        #    dlg = geocode_ui.AddressAssistant()
        #    run_status = dlg.run()
        #    if run_status == Gtk.ResponseType.OK:
        #        if not namew.get_text():
        #            namew.set_text(dlg.place)
        #        latw.set_text("%.5f" % dlg.lat)
        #        lonw.set_text("%.5f" % dlg.lon)

        dialog = Map.MarkerEditDialog()

        sources = []
        for src in self.map_sources:
            if src.get_mutable():
                sources.append(src.get_name())

        dialog.set_groups(sources, group)
        dialog.set_point(point)
        run_status = dialog.run()
        if run_status == Gtk.ResponseType.OK:
            point = dialog.get_point()
            group = dialog.get_group()
        dialog.destroy()

        if run_status == Gtk.ResponseType.OK:
            return point, group
        return None, None

    def recenter(self, position):
        '''
        Recenter Map to position.

        :param position: position for new center of map
        :type position: :class:`map.MapPosition`
        '''
        self.map_widget.set_center(position)

    def save_map(self, bounds=None):
        '''
        Save Map.

        :param bounds: Bounds to save, Default None
        :type bounds: tuple of 4 elements
        '''
        platform = dplatform.get_platform()
        fname = platform.gui_save_file(default_name="map_%s.png" % \
                                       time.strftime("%m%d%Y%_H%M%S"))
        if not fname:
            return

        if not fname.endswith(".png"):
            fname += ".png"

        GLib.timeout_add(1000, self.save_map_handler, fname, bounds)

    def save_map_handler(self, fname, bounds):
        '''
        Save Map Handler.

        :param fname: Filename to save to
        :type fname: str
        :param bounds: Bounds to save
        :type bounds: tuple of 4 elements
        :returns: False to prevent timer retriggering
        :rtype: bool
        '''
        self.map_widget.export_to(fname, bounds)
        return False

    # Called my mainapp, inherited
    # def show(self)

    # called by mainapp
    def set_center(self, latitude, longitude):
        '''
        Set Map Center.

        :param latitude: Latitude of new center
        :type longitude: float
        :param Longitude: Longitude of new center
        :type Longitude: float
        '''
        position = Map.Position(latitude, longitude)
        self.map_widget.set_center(position)

    # Called by mainapp
    @staticmethod
    def set_base_dir(base_dir, map_url, map_key):
        '''
        Set Base Directory.

        :param base_dir: Base directory
        :type base_dir: str
        :param map_url: URL of Map
        :type map_url: str
        :param map_key: Map access key
        :type map_key: str
        '''
        Map.Tile.set_map_info(base_dir, map_url, map_key)

    # Called by mainap
    @staticmethod
    def set_connected(connected):
        '''
        Set Connected.

        :param connected: New connected state
        :type connected: bool
        '''
        Map.Tile.set_connected(connected)

    def set_mark_at(self):
        '''
        Set Mark at.
        '''
        if not self._newcenter:
            # This should not ever happen
            self.logger.info("Set Mark at - no new position set")
            return

        pos = map_sources.MapStation("STATION",
                                     self._newcenter.latitude,
                                     self._newcenter.longitude)
        self._newcenter = None
        pos.set_icon_from_aprs_sym("\\<")
        point, group = self.prompt_to_set_marker(pos)
        if not point:
            return

        for source in self.map_sources:
            self.logger.info("set_mark_at: %s,%s",
                             source.get_name(), group)
            if source.get_name() == group:
                self.logger.info("set_mark_at: Adding new point %s to %s",
                                 point.get_name(),
                                 source.get_name())
                source.add_point(point)
                source.save()
                return
        # No matching group
        query = "%s %s %s" % (_("Group"), group,
                              _("does not exist.  Do you want to create it?"))
        if not ask_for_confirmation(query):
            return

        src = map_sources.MapFileSource.open_source_by_name(self.config,
                                                            group,
                                                            True)
        src.add_point(point)
        src.save()
        self.add_map_source(src)

    # Called by mainapp
    @staticmethod
    def set_proxy(proxy):
        '''
        Set Proxy.

        :param proxy: Proxy to use
        :type proxy: str
        '''
        Map.Tile.set_proxy(proxy)

    # Called by mainap
    @staticmethod
    def set_tile_lifetime(lifetime):
        '''
        Set tile Lifetime.

        :param lifetime: Cache lifetime in seconds
        :param lifetime: int
        '''
        Map.Tile.set_tile_lifetime(lifetime)

    # public method used by mainap inherited from parent
    # def set_title(self, str)

    # Called by mainapp
    def set_zoom(self, zoom):
        '''
        Set zoom level.

        :param zoom: zoom level from 2 to 18
        :type zoom: int
        '''
        self.mapcontrols.zoom_control.level = zoom

    def toggle_show(self, group, *vals):
        '''
        Toggle Show.

        :param group: Group to show
        :type group: str
        :param vals: Optional values
        :type vals: tuple
        '''
        if group:
            station = vals[1]
        else:
            group = vals[1]
            station = None

        for src in self.map_sources:
            if group != src.get_name():
                continue

            if station:
                try:
                    point = src.get_point_by_name(station)
                except KeyError:
                    continue

                point.set_visible(vals[0])
                self.add_point_visible(point)
            else:
                src.set_visible(vals[0])
                for point in src.get_points():
                    point.set_visible(vals[0])
                    self.update_point(src, point)

            src.save()
            break
        self.map_widget.queue_draw()

    # Called from Mainapp
    def update_gps_status(self, gps_status):
        '''
        Update GPS Status.

        :param gps_status: GPS status
        :type gps_status: str
        '''
        self.statusbox.sb_gps.pop(self.STATUS_GPS)
        self.statusbox.sb_gps.push(self.STATUS_GPS, gps_status)

    def update_point(self, source, point):
        '''
        Update Point.

        :param source: Map source
        :type source: :class:`MapSource`
        :param point: Point to update
        :type point: :class:`MapPoint`
        '''
        center = GPSPosition(self.map_widget.position.latitude,
                             self.map_widget.position.longitude)
        this = GPSPosition(point.get_latitude(), point.get_longitude())

        try:
            self.marker_list.set_item(source.get_name(),
                                      point.get_visible(),
                                      point.get_name(),
                                      point.get_latitude(),
                                      point.get_longitude(),
                                      center.distance_from(this),
                                      center.bearing_to(this))
        except miscwidgets.SetItemError as err:
            if str(err) == "Item not found":
                # this is evil
                self.logger.info("Adding point instead of updating")
                self.add_point(source, point)
            else:
                self.logger.info("update_point failed", exc_into=True)

        self.add_point_visible(point)
        # These are now called by the Draw event, so do not queue_draw.

    def update_points_visible(self):
        '''Update Points Visible.'''
        for src in self.map_sources:
            for point in src.get_points():
                self.update_point(src, point)
        # These are now called by the Draw event, so do not queue_draw.
