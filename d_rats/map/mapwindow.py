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
import time

import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import GLib

from .. import map as Map
from .. import miscwidgets


# This makes pylance happy with out overriding settings
# from the invoker of the class
if not '_' in locals():
    import gettext
    _ = gettext.gettext


class MapMenuBar(Gtk.MenuBar):
    '''Menu for map.'''

    def __init__(self):
        Gtk.MenuBar.__init__(self)


class MapZoomControls(Gtk.Frame):
    '''
    Map zoom controls.

    :param map_widget: Map Widget for control
    :type map_widget: :class:`Map.Widget`
    :param zoom: Initial zoom level, Default 14
    :type zoom: int
    '''
    def __init__(self, map_widget, zoom=14):
        Gtk.Frame.__init__(self)
        zoom_label = _("Zoom") + " (%i)" % zoom
        self.set_label(zoom_label)
        self.map_widget = map_widget
        self.set_label_align(0.5, 0.5)
        self.set_size_request(150, 50)
        self.show()

        box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 3)
        box.set_border_width(3)
        box.show()

        label = Gtk.Label.new(_("Min"))
        label.show()
        box.pack_start(label, 0, 0, 0)

        # mm here the allowed zoom levels are from 2 to 17 (increased to 18)
        adj = Gtk.Adjustment.new(value=zoom,
                                 lower=2,
                                 upper=18,
                                 step_increment=1,
                                 page_increment=3,
                                 page_size=0)
        # scroll_bar = Gtk.HScrollbar(adj)
        scroll_bar = Gtk.Scrollbar.new(Gtk.Orientation.HORIZONTAL, adj)
        scroll_bar.show()
        box.pack_start(scroll_bar, 1, 1, 1)

        label = Gtk.Label.new(_("Max"))
        label.show()
        box.pack_start(label, 0, 0, 0)

        self.add(box)

        scroll_bar.connect("value-changed", self.zoom, self)


    def zoom(self, adj, frame):
        '''
        Zoom.

        :param adj: Gtk.Adjustment object
        :param frame: Frame for zoom
        '''
        print("self:", type(self))
        print("adj)", type(adj))
        print("frame", type(frame))
        self.map_widget.set_zoom(int(adj.get_value()))
        self.set_label(_("Zoom") + " (%i)" % int(adj.get_value()))


class MapMakeTrack(Gtk.CheckButton):
    '''
    Enable making a track on map

    :param map_window: Parent Map window
    :type map_window: :class:`Map.Window`
    '''
    def __init__(self, map_window):
        Gtk.CheckButton.__init__(self)
        self.set_label(_("Track center"))

        def toggle(check_button, map_window):
            map_window.tracking_enabled = check_button.get_active()

        self.connect("toggled", toggle, map_window)
        self.show()


class MapMarkerlist(Gtk.ScrolledWindow):
    '''
    Make Marker List.

    :param map_window: Parent Map window
    :type map_window: :class:`Map.Window`
    '''
    cols = [(GObject.TYPE_BOOLEAN, _("Show")),
            (GObject.TYPE_STRING, _("Station")),
            (GObject.TYPE_FLOAT, _("Latitude")),
            (GObject.TYPE_FLOAT, _("Longitude")),
            (GObject.TYPE_FLOAT, _("Distance")),
            (GObject.TYPE_FLOAT, _("Direction")),
            ]

    def __init__(self, map_window):
        Gtk.ScrolledWindow.__init__(self)
        self.map_window = map_window
        self.marker_list = miscwidgets.TreeWidget(self.cols, 1, parent=False)
        self.marker_list.toggle_cb.append(self.map_window.toggle_show)
        # self.marker_list.connect("click-on-list", self.make_marker_popup)

        # pylint: disable=protected-access
        self.marker_list._view.connect("row-activated", self.recenter_cb)

        def render_station(_col, rend, model, iter_value, _data):
            parent = model.iter_parent(iter_value)
            if not parent:
                parent = iter_value
                group = model.get_value(parent, 1)
            if group in self.map_window.colors:
                rend.set_property("foreground", self.map_window.colors[group])

        column = self.marker_list._view.get_column(1)
        column.set_expand(True)
        column.set_min_width(150)
        # r = c.get_cell_renderers()[0]
        renderer_text = Gtk.CellRendererText()
        column.set_cell_data_func(renderer_text, render_station)

        def render_coord(_col, rend, model, iter_value, cnum):
            if isinstance(rend, gi.repository.Gtk.Separator):
                return
            if model.iter_parent(iter_value):
                rend.set_property('text', "%.4f" %
                                  model.get_value(iter_value, cnum))
            else:
                rend.set_property('text', '')

        for col in [2, 3]:
            column = self.marker_list._view.get_column(col)
            # renderer_text = column.get_cell_renderers()[0]
            renderer_text = Gtk.CellRendererText()
            column.set_cell_data_func(renderer_text, render_coord, col)

        def render_dist(_col, rend, model, iter_value, cnum):
            if model.iter_parent(iter_value):
                rend.set_property('text', "%.2f" %
                                  model.get_value(iter_value, cnum))
            else:
                rend.set_property('text', '')

        for col in [4, 5]:
            column = self.marker_list._view.get_column(col)
            # renderer_text = column.get_cell_renderers()[0]
            renderer_text = Gtk.CellRendererText()
            column.set_cell_data_func(renderer_text, render_dist, col)

        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.add(self.marker_list.packable())
        self.set_size_request(-1, 150)
        self.show()


    def recenter_cb(self, view, path, column, data=None):
        '''
        Recenter Callback.

        :param view: Gtk.TreeView object that received signal
        :param path: Gtk.TreePath for the activated row
        :param column: Gtk.TreeviewColumn that was activated
        :param data: Optional data, Default None
        '''
        print("recenter_cb")
        print("self", type(self))
        print("path", type(self))
        print("column", type(column))
        print("data", type(data))
        model = view.get_model()
        if model.iter_parent(model.get_iter(path)) is None:
            return

        items = self.marker_list.get_selected()

        self.map_window.center_mark = items[1]
        self.map_window.recenter(items[2], items[3])

        self.map_window.sb_center.pop(self.map_window.STATUS_CENTER)
        self.map_window.sb_center.push(self.map_window.STATUS_CENTER,
                                       _("Center") + ": %s" %
                                       self.map_window.center_mark)


class MapControls(Gtk.Box):
    '''
    Make Controls for Map

    :param map_window: Parent Map window
    :type map_window: :class:`Map.Window`
    '''
    def __init__(self, map_window):
        Gtk.Box.__init__(self, Gtk.Orientation.VERTICAL, 2)

        zoom_control = MapZoomControls(map_window.map_widget)
        self.pack_start(zoom_control, False, False, False)
        make_track = MapMakeTrack(map_window)
        self.pack_start(make_track, False, False, False)

        self.show()


class MapBottomPanel(Gtk.Box):
    '''
    Map Bottom Panel.

    :param map_window: Parent Map window
    :type map_window: :class:`Map.Window`
    '''
    def __init__(self, map_window):
        Gtk.Box.__init__(self, Gtk.Orientation.HORIZONTAL, 2)
        marker_list = MapMarkerlist(map_window)
        self.pack_start(marker_list, True, True, True)
        controls = MapControls(map_window)
        self.pack_start(controls, False, False, False)


# We have more than 7 instance attributes
# pylint: disable=too-many-instance-attributes
class MapWindow(Gtk.ApplicationWindow):
    '''
    Map Window.

    This Creates the main map window display.

    :param application:
    :type application: :class:`Gtk.Application`
    :param config: Configuration data
    :type config: :class:`DratsConfig`
    '''

    #__gsignals__ = {
    #    "reload-sources" : (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE, ()),
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
        self.map_sources = []
        # this parameter defines the dimension of the map behind the window
        # tiles SHALL be
        #  - ODD due to the mechanism used then to calculate the
        #    offsets to keep aligned the stations markers in the map into the
        #    calculate_bound
        #  - the same for both x and y in the mapwidget creation
        tiles = 9

        self.map_widget = Map.Widget(width=tiles, height=tiles,
                                     status=self.status)
        self.map_widget.show()

        box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 2)

        self.menubar = MapMenuBar()
        self.menubar.show()

        box.pack_start(self.menubar, False, False, False)

        self.scrollw = Gtk.ScrolledWindow()
        self.scrollw.add(self.map_widget)
        self.scrollw.show()

        self.map_widget.add_events(Gdk.EventMask.POINTER_MOTION_MASK)
        self.map_widget.connect("motion-notify-event", self.mouse_move_event)
        self.scrollw.connect("button-press-event", self.mouse_click_event)

        hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 2)

        self.sb_coords = Gtk.Statusbar()
        self.sb_coords.show()
        # self.sb_coords.set_has_resize_grip(False)

        self.sb_center = Gtk.Statusbar()
        self.sb_center.show()
        # self.sb_center.set_has_resize_grip(False)

        self.sb_gps = Gtk.Statusbar()
        self.sb_gps.show()

        self.sb_prog = Gtk.ProgressBar()
        self.sb_prog.set_size_request(150, -1)
        self.sb_prog.show()

        hbox.pack_start(self.sb_coords, True, True, True)
        hbox.pack_start(self.sb_center, True, True, True)
        hbox.pack_start(self.sb_prog, False, False, False)
        hbox.pack_start(self.sb_gps, True, True, True)
        hbox.show()

        box.pack_start(self.scrollw, True, True, True)
        bottom_panel = MapBottomPanel(self)
        box.pack_start(bottom_panel, False, False, False)
        box.pack_start(hbox, False, False, False)
        box.show()

        #setup the default dimensions for the map window
        self.set_default_size(800, 600)

        self.add(box)


    def mouse_click_event(self, widget, event):
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
        print("widget", type(widget))
        print("event", type(event))
        x_axis, y_axis = event.get_coords()

        hadj = widget.get_hadjustment()
        vadj = widget.get_vadjustment()
        mx_axis = x_axis + int(hadj.get_value())
        my_axis = y_axis + int(vadj.get_value())

        # lat, lon = self.map_widget.xy2latlon(mx_axis, my_axis)

        self.logger.info("Button %i at %i,%i",
                         event.button, mx_axis, my_axis)
        # See comment below.
        # pylint: disable=protected-access
        #if event.button == 3:
        #    vals = {"lat" : lat,
        #            "lon" : lon,
        #            "x" : mx_axis,
        #            "y" : my_axis}
        #    self.logger.info("Clicked 3: %s", vals)
        #    menu = self.make_popup(vals)
        #    if menu:
        #        menu.popup(None, None, None, None, event.button, event.time)
        #elif event.type == Gdk.EventType.BUTTON_PRESS:
        #    self.logger.info("Clicked: %.4f,%.4f", lat, lon)
            # The crosshair marker has been missing since 0.3.0
            # self.set_marker(GPSPosition(station=CROSSHAIR,
            #                             lat=lat, lon=lon))
        # This is not a protected-access, it is the actual
        # python name for the type.
        #elif event.type == Gdk.EventType._2BUTTON_PRESS:
        #    self.logger.info("recenter on %.4f, %.4f", lat, lon)

        #    self.recenter(lat, lon)

    def mouse_move_event(self, _widget, event):
        '''
        Mouse Move Event.

        :param _widget: Widget that received the signal, Not used
        :type _widget: :class:`Map.Widget`
        :param event: Event that triggered this handler.
        :type event: :class:`Gdk.EventMotion`
        :returns: True to stop other handlers from being invoked
        :rtype: bool
        '''
        if not self.__last_motion:
            GLib.timeout_add(100, self._mouse_motion_handler)
        self.__last_motion = (time.time(), event.x, event.y)

    # pylint: disable=too-many-locals
    def _mouse_motion_handler(self):
        if self.__last_motion is None:
            return False

        time_motion, _x_axis, _y_axis = self.__last_motion
        if (time.time() - time_motion) < 0.5:
             # self.info_window.hide()
            return True

        # lat, lon = self.map_widget.xy2latlon(x_axis, y_axis)

        # hadj = self.scrollw.get_hadjustment()
        # vadj = self.scrollw.get_vadjustment()
        # mx_axis = x_axis - int(hadj.get_value())
        # my_axis = y_axis - int(vadj.get_value())

        # hit = False

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

        self.sb_coords.pop(self.STATUS_COORD)
        # self.sb_coords.push(self.STATUS_COORD, "%.4f, %.4f" % (lat, lon))

        self.__last_motion = None

        return False


    def recenter(self, lat, lon):
        '''
        Recenter.

        :param lat: Latitude to recenter on
        :param lon: Longitude to recenter on
        '''
        # self.map_widget.set_center(lat, lon)
        # self.map_widget.load_tiles()
        # self.refresh_marker_list()
        # self.center_on(lat, lon)
        # self.map_widget.queue_draw()

    # pylint: disable=no-self-argument
    def status(fraction, message):
        '''
        Sets a progress bar status.

        :param fraction: Amount of progress
        :type fraction: float
        :param message: Status message to display
        :type message: str
        '''

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

    @staticmethod
    def test():
        '''Test method.'''
        Gtk.main()
