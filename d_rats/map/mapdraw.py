'''Map Draw Module.'''
#
# Copyright 2021-2023 John Malmberg <wb8tyw@gmail.com>
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
import os
import cairo  # type: ignore # Needed for Pylance on Microsoft Windows

import gi  # type: ignore
gi.require_version("Gdk", "3.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gdk          # type: ignore
from gi.repository import PangoCairo   # type: ignore

from .. import map as Map
from .. import utils
from ..dplatform import Platform

# This makes pylance happy with out overriding settings
# from the invoker of the class
if not '_' in locals():
    import gettext
    _ = gettext.gettext


# pylint: disable=too-few-public-methods
class LoadContext():
    '''
    Tile Context

    :param loaded_tiles: Tile that are loaded
    :param total_tiles: Total tiles
    '''

    def __init__(self, loaded_tiles, total_tiles):
        self.loaded_tiles = loaded_tiles
        self.total_tiles = total_tiles
        self.zoom = Map.ZoomControls.get_level()

    @property
    def fraction(self):
        '''
        :returns: Fraction of tiles being loaded
        :rtype: float
        '''
        return float(self.loaded_tiles) / float(self.total_tiles)


class MapDraw():
    '''
    Map Draw Handler thread.

    Drawing is done with a cairo context that is only available
    inside the draw handler.

    Putting in its own class to avoid confusion.
    This class should only be instantiated by the handler classmethod.

    :param map_widget: Calling widget context
    :type map_widget: :class:`Map.Mapwidget`
    :param cairo_ctx: Cairo context for drawing area
    :type cairo_ctx: :class:`cairo.Context`
    '''

    __broken_tile = None
    __center = None
    __center_changed = False
    __zoom_changed = False
    logger = logging.getLogger("MapDraw")

    def __init__(self, map_widget, cairo_ctx):
        self.map_widget = map_widget
        self.cairo_ctx = cairo_ctx
        self.map_visible = {}
        self.load_ctx = None
        self.sb_prog = None
        self.map_visible = None
        self.rgba_red = Gdk.RGBA()
        self.rgba_red.parse('red')

    @classmethod
    def set_center(cls, pos):
        '''
        Set Center.

        Set a flag to have the window scroll bars centered.

        :param pos: New center position
        :type pos: :class:`Map.MapPosition`
        '''
        cls.__center = pos
        cls.__center_changed = True

    @classmethod
    def set_zoom_changed(cls):
        '''
        Sets that the zoom level changed.
        '''
        cls.__zoom_changed = True

    # pylint wants a max of 15 local variables in a method.
    # pylint: disable=too-many-locals
    @classmethod
    def handler(cls, map_widget, cairo_ctx):
        '''
        Draw Handler.

        This handles a draw event to the MapWidget drawable area

        These draw events are signaled by:
        Moving the scroll bars of the parent scrolled window.

        :param map_widget: Calling widget context
        :type map_widget: :class:`Map.Mapwidget`
        :param cairo_ctx: Cairo context for drawing area
        :type cairo_ctx: :class:`cairo.Context`
        :returns: False to allow other handlers to run
        :rtype: bool
        '''
        self = MapDraw(map_widget, cairo_ctx)
        self.sb_prog = map_widget.map_window.statusbox.sb_prog
        self.map_visible = {}
        scrollw = map_widget.map_window.scrollw
        y_slider_width = scrollw.get_vscrollbar().get_preferred_width()
        x_slider_height = scrollw.get_hscrollbar().get_preferred_height()
        slider_size = max(max(y_slider_width), max(x_slider_height))
        # slider size varies because auto hide feature.
        # It appears to be 0 for systems with touch screens and no mouse
        # On my system it is 7 when a mouse is not moving a scrollbar and 14
        # for when a mouse is moving the scrollbar and I can not find
        # a way to get this size before the scrollbar is expanded.
        # So make sure that we have at least 20 pixels from the edge for the
        # the sliders.
        # For larger sliders the scale will move a bit depending on how the
        # window position was updated.
        self.map_visible['slider_size'] = max(slider_size, 20)
        hadj = scrollw.get_hadjustment()
        self.map_visible['x_start'] = int(hadj.get_value())
        h_page_size = hadj.get_page_size()
        self.map_visible['x_size'] = int(h_page_size)
        vadj = scrollw.get_vadjustment()
        self.map_visible['y_start'] = int(vadj.get_value())
        v_page_size = vadj.get_page_size()
        self.map_visible['y_size'] = int(v_page_size)

        if cls.__zoom_changed or cls.__center_changed:
            map_widget.calculate_bounds()

            # We do not know the page size of the scroll bars until we get
            # here, so self._center change is used to let us know when
            # we need to have the program adjust the scroll bars to the new
            # center.
            if cls.__center:
                display_width, display_height = Map.Tile.get_display_limits()
                hadj.set_value((display_width - h_page_size) / 2)
                vadj.set_value((display_height - v_page_size) / 2)

        self.expose_map()
        self.scale()
        self.draw_markers()
        cls.__center_changed = False
        cls.__zoom_changed = False
        return False

    def broken_tile(self):
        '''
        Broken Tile

        :returns: pixbuf object
        :rtype: :class:`GdkPixbuf.Pixbuf`
        '''
        if self.__broken_tile:
            return self.__broken_tile

        platform = Platform.get_platform()
        sys_data = platform.sys_data()
        broken_path = os.path.join(sys_data, "images", "broken_tile.png")
        # pylint: disable=no-member
        self.__broken_tile = cairo.ImageSurface.create_from_png(broken_path)
        return self.__broken_tile

    def draw_cross_marker_at(self, x_coord, y_coord):
        '''
        Draw Cross Marker at coordinates

        :param x_coord: Horizontal coordinate
        :type x_coord: float
        :param y_coord: Vertical coordinate
        :type y_coord: float
        '''
        self.cairo_ctx.save()

        self.cairo_ctx.save()
        self.cairo_ctx.set_source_rgba(self.rgba_red.red,
                                       self.rgba_red.green,
                                       self.rgba_red.blue,
                                       self.rgba_red.alpha)
        x_coord = int(x_coord)
        y_coord = int(y_coord)

        self.cairo_ctx.move_to(x_coord, y_coord - 5)
        self.cairo_ctx.line_to(x_coord, y_coord + 5)
        self.cairo_ctx.move_to(x_coord - 5, y_coord)
        self.cairo_ctx.line_to(x_coord + 5, y_coord)
        self.cairo_ctx.stroke()
        self.cairo_ctx.restore()

    def draw_image_at(self, x_coord, y_coord, pixbuf):
        '''
        Draw Image at coordinates.

        :param x_coord: Horizontal coordinate
        :type x_coord: float
        :param y_coord: Vertical coordinate
        :type y_coord: float
        :param pixbuf: Image to draw
        :type pixbuf: :class:`GdkPixbuf.Pixbuf`
        :returns: height of pixbuf
        :rtype: int
        '''
        self.cairo_ctx.save()
        half_width = pixbuf.get_width() / 2
        height = pixbuf.get_height()
        half_height = height / 2
        Gdk.cairo_set_source_pixbuf(self.cairo_ctx, pixbuf,
                                    x_coord - half_width,
                                    y_coord - half_height)
        self.cairo_ctx.paint()
        self.cairo_ctx.restore()

        return height

    # pylint wants a max of 12 branches and 50 statements for a method.
    # pylint: disable=too-many-branches, too-many-statements
    def draw_marker(self, point):
        '''
        Draw Marker.

        :param point: point to draw
        :type point: :class:`MapPoint`
        '''
        position = Map.Position(point.get_latitude(), point.get_longitude())
        try:
            x_coord, y_coord = Map.Tile.deg2display(position)
        except ZeroDivisionError:
            return

        label = point.get_name()
        if label == self.map_widget.map_window.CROSSHAIR:
            self.draw_cross_marker_at(x_coord, y_coord)
        else:
            pixbuf = point.get_icon()
            offset = 0
            if pixbuf:
                offset = self.draw_image_at(x_coord, y_coord, pixbuf)
            self.draw_text_marker_at(x_coord, y_coord, offset, label)

    def draw_markers(self):
        '''
        Draw Markers.
        '''
        if self.__zoom_changed or self.__center_changed:
            # At this point we know we have to recreate the list
            # list of visible points when ever the zoom or center changes.
            self.map_widget.map_window.update_points_visible()

        for point in self.map_widget.map_window.points_visible:
            self.draw_marker(point)

    def draw_text_marker_at(self, x_coord, y_coord, icon_height, text):
        '''
        Draw Text Marker At Location on Map.

        :param x_coord: X position for tile
        :type x_coord: float
        :param y_coord: y position for tile
        :type y_coord: float
        :param icon_height: icon height
        :type icon_height: int
        :param text: Text for marker
        :type text: str
        '''
        color = "yellow"
        # setting the size for the text marker
        y_offset = 0
        if icon_height:
            # Position text just below icon
            y_offset = icon_height / 2 + 1
        zoom = Map.ZoomControls.get_level()
        if zoom < 12:
            size = 'size="x-small"'
        elif zoom < 14:
            size = 'size="small"'
        else:
            size = ''
        text = utils.filter_to_ascii(text)

        pango_layout = self.map_widget.create_pango_layout("")
        markup = '<span %s background="%s">%s</span>' % (size, color, text)
        pango_layout.set_markup(markup)
        width, height = pango_layout.get_pixel_size()
        self.cairo_ctx.save()
        # make sure to center the text under the point
        if not y_offset:
            # If no icon center text over position
            y_offset = -height / 2
        self.cairo_ctx.move_to(x_coord - width/2, y_coord + y_offset)
        PangoCairo.show_layout(self.cairo_ctx, pango_layout)
        self.cairo_ctx.stroke()
        self.cairo_ctx.restore()

    def draw_tile(self, path, x_coord, y_coord):
        '''
        Draw Tile.

        :param path: Path for tile
        :type path: str
        :param x_coord: X Axis for tile
        :type x_coord: float
        :param y_coord: Y Axis for tile
        :type x_coord: float
        '''
        if path:
            try:
                # pylint: disable=no-member
                surface = cairo.ImageSurface.create_from_png(path)
                self.load_ctx.loaded_tiles += 1
            except cairo.Error as err:
                surface = self.broken_tile()
                # Debugging information
                # pylint: disable=no-member
                if err.status != cairo.Status.FILE_NOT_FOUND:
                    # The file not found is because we have a bad tile cached.
                    # This is to prevent excessive reties for non-existent
                    # map tiles.  Anything else should be logged for more
                    # analysis.
                    self.logger.debug("draw_tile: path %s", path, exc_info=True)

                # this is the case  when some jpg tile file cannot be loaded -
                # typically this was due to html content saved as jpg
                # (due to an un-trapped http error), or due to corrupted
                # jpg (e.g. d-rats was closed before completing file save )
                if os.path.exists(path):
                    self.logger.info(
                        "draw_tile Deleting the broken tile to force future"
                        "download %s", path)
                    os.remove(path)
        else:
            surface = self.broken_tile()

        self.cairo_ctx.save()
        self.cairo_ctx.set_source_rgba(0.0, 0.0, 0.0)
        self.cairo_ctx.set_source_surface(surface, x_coord, y_coord)
        self.cairo_ctx.paint()
        self.cairo_ctx.restore()

    def expose_map(self):
        '''
        Expose the Map.
        '''
        width, height = Map.Tile.get_display_tile_limits()
        self.load_ctx = LoadContext(0, (width * height))
        center = Map.Tile.center
        delta_w, delta_h = Map.Tile.get_display_center()

        tilesize = Map.Tile.get_tilesize()
        self.map_widget.map_tiles = []
        for i in range(0, width):
            for j in range(0, height):
                tile = center + (i - delta_w, j - delta_h)
                if not tile.is_local():
                    message = _("Retrieving")
                else:
                    message = _("Loading")
                tile_path = tile.get_local_tile_path()
                if tile_path:
                    self.draw_tile(tile_path,
                                   tilesize * i,
                                   tilesize * j)
                else:
                    self.draw_tile(None,
                                   tilesize * i,
                                   tilesize * j)
                    tile.threaded_fetch(self.map_widget)
                self.progress(message)
                self.map_widget.map_tiles.append(tile)

    # pylint: disable=too-many-locals
    def scale(self):
        '''
        Draw the scale ladder on the Map.

        :param cairo_ctx: Cairo context for drawing area
        :type cairo_ctx: :class:`cairo.Context`
        :param pixels: Tile size in pixels, default=128
        :type pixels: int
        '''
        pango_layout = self.map_widget.map_scale_pango_layout()
        pango_width, pango_height = pango_layout.get_pixel_size()

        pixels = Map.Tile.get_tilesize() / 2
        self.cairo_ctx.save()

        self.cairo_ctx.set_source_rgba(0.0, 0.0, 0.0) # default for black

        visible = self.map_visible
        # place scale ending at 10% of pixels from the bottom right.
        # taking into account what the scrollbar might be temporarily covering
        pixel_offset = int(pixels / 10) + visible['slider_size']
        offset_from_bottom = pixel_offset + pango_height
        offset_from_right = pixel_offset + pixels
        if pango_width > pixels:
            offset_from_right = pixel_offset + pango_width

        self.cairo_ctx.new_path()

        scale_x = visible['x_start'] + visible['x_size'] - offset_from_right
        scale_y = visible['y_start'] + visible['y_size'] - offset_from_bottom

        # scale_tick size is 10 % of tile_size
        scale_tick = int(pixels / 10)
        # text offset is 10% of the text size
        text_offset = int(pango_height / 10)

        # Scale left end
        self.cairo_ctx.move_to(scale_x, scale_y - scale_tick)
        self.cairo_ctx.line_to(scale_x, scale_y)
        # scale bar
        self.cairo_ctx.line_to(scale_x + pixels, scale_y)
        # Scale right end
        self.cairo_ctx.line_to(scale_x + pixels, scale_y - scale_tick)
        # scale middle
        self.cairo_ctx.move_to(scale_x + (pixels/2), scale_y)
        self.cairo_ctx.line_to(scale_x + (pixels/2), scale_y - scale_tick)

        # Show scale text
        self.cairo_ctx.move_to(scale_x, scale_y + text_offset)
        PangoCairo.show_layout(self.cairo_ctx, pango_layout)
        self.cairo_ctx.stroke()
        self.cairo_ctx.restore()

    def progress(self, message):
        '''
        Sets a progress bar status.

        :param message: Status message to display
        :type message: str
        '''
        fraction = self.load_ctx.fraction
        progress_text = message
        if fraction > 0.0:
            progress_text += " %.0f%%" % (fraction * 100.0)
        self.sb_prog.set_fraction(fraction)
        self.sb_prog.set_text(progress_text)
