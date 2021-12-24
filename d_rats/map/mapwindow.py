'''Map Window Module.'''
#
# Copyright 2021 John Malmberg <wb8tyw@gmail.com>
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
from .. import map_source_editor
from .. import map as Map

# This makes pylance happy with out overriding settings
# from the invoker of the class
if not '_' in locals():
    import gettext
    _ = gettext.gettext


# We have more than 7 instance attributes
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
                            GObject.TYPE_NONE, ())
    }
    #    "user-send-chat" : signals.USER_SEND_CHAT,
    #    "get-station-list" : signals.GET_STATION_LIST,
    #    }

    #_signals = {"user-send-chat" : None,
    #            "get-station-list" : None,
    #            }

    STATUS_COORD = 0
    STATUS_CENTER = 1
    STATUS_GPS = 2

    def __init__(self, application, config):
        Gtk.ApplicationWindow.__init__(self, application=application)

        self.logger = logging.getLogger("MapWindow")

        # self.connect("destroy", Gtk.main_quit)
        self.config = config
        # self.marker_list = None
        # self.map_tiles = []
        self.logger.info("Testing MapWindow")

        self.center_mark = None
        self.tracking_enabled = False
        self.__last_motion = None
        self.__temp_frac = 0.0
        self.map_sources = []
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
        box.pack_start(self.scrollw, True, True, True)
        box.pack_start(bottom_panel, False, False, False)
        box.pack_start(self.statusbox, False, False, False)
        box.show()

        #setup the default dimensions for the map window
        self.set_default_size(800, 600)

        self.add(box)
        Map.PopupModel.add_actions(self)

    def add_map_source(self, maps):
        '''
        Add Map Source.

        :param maps: Maps
        :type maps: list
        '''
        print("add_map_source %s" % maps, type(maps), type(self))

    # Inherited from Parent and called by mainapp
    # def connect(self, signal name, function):

    # called my mainapp
    def get_map_source(self, station):
        '''
        Get Map source.

        :param station: Station information
        :type station: str?
        :returns: maps for a station
        :rtype: list?
        '''
        print("get_map_source %s" % station, type(station), type(self))

    # Called by mainapp and qst.py
    def get_map_sources(self):
        '''
        Get Map Sources.

        :returns: Map sources
        :rtype: list
        '''
        print("get_map_sources", type(self))
        return []

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

    def item_editsources_handler(self, action, _value):
        '''
        Edit Sources Handler.

        :param action: Action that was invoked
        :type action: :class:`GioSimpleAction`
        :param _value: Value for action, Unused
        '''
        print("Edit Sources handler", type(self))
        print('Action: %s\n value: %s' % (action, _value))
        srced = map_source_editor.MapSourcesEditor(self.config)
        print('srced', type(srced))
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

    def _mouse_click_event(self, widget, event):
        '''
        Mouse Click Event.

        :param widget: Widget clicked on
        :type widget: :class:`Gtk.ScrolledWindow`
        :param event: Event that triggered this handler
        :type event: :class:`Gtk.EventMotion`
        :returns: True to stop other handlers from processing the event.
        :rtype: bool
        '''
        print("mouse_click_event")
        print("widget", type("widget"), widget)
        x_axis, y_axis = event.get_coords()

        hadj = widget.get_hadjustment()
        vadj = widget.get_vadjustment()
        mx_axis = x_axis + int(hadj.get_value())
        my_axis = y_axis + int(vadj.get_value())

        position = self.map_widget.xy2latlon(mx_axis, my_axis)

        self.logger.info("Button %i at %i,%i",
                         event.button, mx_axis, my_axis)
        # Need to test for _2BUTTON_PRESS before testing
        # for a normal button press.
        # This is not a protected-access, it is the actual
        # python name for the type.
        # pylint: disable=protected-access
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
            # Map.PopupModel.add_actions(self)
            # self.grab_focus()
            popup_menu.popup_at_pointer()
        # elif event.type == Gdk.EventType.BUTTON_PRESS:
            #self.logger.info("Clicked: %s", position)
            # The crosshair marker has been missing since 0.3.0
            # self.set_marker(GPSPosition(station=CROSSHAIR,
            #                             lat=position.latitude,
            #                             lon=position.longitude))

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
            GLib.timeout_add(10, self._mouse_motion_handler)
        self.__last_motion = (time.time(), event.x, event.y)

    # pylint: disable=too-many-locals
    def _mouse_motion_handler(self):
        if self.__last_motion is None:
            return False

        time_motion, x_axis, y_axis = self.__last_motion
        if (time.time() - time_motion) < 0.5:
             # self.info_window.hide()
            return True

        position = self.map_widget.xy2latlon(x_axis, y_axis)

        # hadj = self.scrollw.get_hadjustment()
        # vadj = self.scrollw.get_vadjustment()
        # mx_axis = x_axis - int(hadj.get_value())
        # my_axis = y_axis - int(vadj.get_value())

        #hit = False

        for source in self.map_sources:
            if not source.get_visible():
                continue
            for point in source.get_points():
                if not point.get_visible():
                    continue
                # try:
                #    _x, _y = self.map_widget.latlon2xy(point.get_latitude(),
                #                                       point.get_longitude())
                # except ZeroDivisionError:
                #    continue

                # dx_axis = abs(x_axis - _x)
                # dy_axis = abs(y_axis - _y)

                # if dx_axis < 20 and dy_axis < 20:
                #    hit = True

                #    date = time.ctime(point.get_timestamp())

                #    text = "<b>Station:</b> %s" % point.get_name() + \
                #        "\n<b>Latitude:</b> %.5f" % point.get_latitude() + \
                #        "\n<b>Longitude:</b> %.5f"% point.get_longitude() + \
                #        "\n<b>Last update:</b> %s" % date

                #    text += "\n<b>Info</b>: %s" % point.get_comment()

                #    label = Gtk.Label()
                #    label.set_markup(text)
                #    label.show()
                    # for child in self.info_window.get_children():
                    #     self.info_window.remove(child)
                    # self.info_window.add(label)

                    # posx, posy = self.get_position()
                    # posx += mx_axis + 10
                    # posy += my_axis - 10

                    # self.info_window.move(int(posx), int(posy))
                    # self.info_window.show()

                    # break

        # if not hit:
            # self.info_window.hide()

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
        print("self", type(self))
        print("action", type(_action))
        print("value", type(_value))

    def popup_newmarker_handler(self, _action, _value):
        '''
        Popup New Marker Handler.

        :param _action: Action that was invoked, Unused
        :type _action: :class:`GioSimpleAction`
        :param _value: Value for action, Unused
        '''
        print("self", type(self))
        print("action", type(_action))
        print("value", type(_value))

    def popup_broadcast_handler(self, _action, _value):
        '''
        Popup Broadcast Handler.

        :param _action: Action that was invoked, Unused
        :type _action: :class:`GioSimpleAction`
        :param _value: Value for action, Unused
        '''
        print("self", type(self))
        print("action", type(_action))
        print("value", type(_value))

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

    def recenter(self, position):
        '''
        Recenter Map to position.

        :param position: position for new center of map
        :type position: :class:`map.MapPosition`
        '''
        self.map_widget.set_center(position)
        # self.map_widget.load_tiles()
        # self.refresh_marker_list()

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
        print("set_center", type(self), latitude, longitude)
        position = Map.Position(latitude, longitude)
        self.map_widget.set_center(position)

    # Called by mainapp
    def set_base_dir(self, base_dir, map_url, map_key):
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
        self.logger.info("BASE_DIR configured to %s", base_dir)
        self.logger.info("MAP_URL configured to: %s", map_url)
        self.logger.debug("MAP_URL_KEY configured to: %s", map_key)

    # Called by mainap
    @staticmethod
    def set_connected(connected):
        '''
        Set Connected.

        :param connected: New connected state
        :type connected: bool
        '''
        Map.Tile.set_connected(connected)

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
        :param vals: Optional values
        '''
        print("toggle_show")
        print("self:", type(self))
        print("group:", type(group))
        print("vals:", type(vals))
        #if group:
        #    station = vals[1]
        #else:
        #    group = vals[1]
        #    station = None

        # for src in self.map_sources:
        #    if group != src.get_name():
        #        continue

        #    if station:
        #        try:
        #            point = src.get_point_by_name(station)
        #        except KeyError:
        #            continue

        #        point.set_visible(vals[0])
        #        self.add_point_visible(point)
        #    else:
        #        src.set_visible(vals[0])
        #        for point in src.get_points():
        #            point.set_visible(vals[0])
        #            self.update_point(src, point)

        #    src.save()
        #    break
        # self.map_widget.queue_draw()

    # Called from Mainapp
    def update_gps_status(self, gps_status):
        '''
        Update GPS Status.

        :param gps_status: GPS status
        :type gps_status: str
        '''

        self.statusbox.sb_gps.pop(self.STATUS_GPS)
        self.statusbox.sb_gps.push(self.STATUS_GPS, gps_status)