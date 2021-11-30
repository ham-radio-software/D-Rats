'''Map Draw Module.'''
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
import os
import cairo

import gi
gi.require_version("Gdk", "3.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import PangoCairo

from .. import map as Map


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
    This class should only be instanciated by the handler classmethod.

    :param map_widget: Calling widget context
    :type map_widget: :class:`Map.Mapwidget`
    :param cairo_ctx: Cairo context for drawing area
    :type cairo_ctx: :class:`cairo.Context`
    '''

    __broken_tile = None

    def __init__(self, map_widget, cairo_ctx):
        self.map_widget = map_widget
        self.cairo_ctx = cairo_ctx
        self.map_visible = {}
        self.load_ctx = None
        self.sb_prog = None
        self.map_visible = None
        self.logger = logging.getLogger("MapDraw")

    @classmethod
    def handler(cls, map_widget, cairo_ctx):
        '''
        Draw Handler.

        This handles a draw event to the MapWidget drawable area

        These draw events are signaled by:
        Moving the scrollbars of the parent scrolled window.

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
        self.map_visible['x_start'] = int(
            scrollw.get_hadjustment().get_value())
        self.map_visible['x_size'] = int(
            scrollw.get_hadjustment().get_page_size())
        self.map_visible['y_start'] = int(scrollw.get_vadjustment().get_value())
        self.map_visible['y_size'] = int(
            scrollw.get_vadjustment().get_page_size())
        map_widget.calculate_bounds()

        self.expose_map()
        self.scale()
            #if not self.map_tiles:
            #    self.load_tiles(cairo_ctx)

            # pylint: disable=invalid-name
            # gc = self.get_style().black_gc
            # self.window.draw_drawable(gc,
            #                          self.pixmap,
            #                          0, 0,
            #                          0, 0,
            #                          -1, -1)
            #self.emit("redraw-markers")
        return False

    def broken_tile(self):
        '''
        Broken Tile

        :returns: pixbuf object
        '''
        if self.__broken_tile:
            return self.__broken_tile

        module_path = os.path.abspath(__file__)
        module_dir = os.path.dirname(module_path)
        map_dir = os.path.dirname(module_dir)
        base_dir = os.path.dirname(map_dir)
        broken_path = os.path.join(base_dir, "images", "broken_tile.png")
        # pylint: disable=no-member
        self.__broken_tile = cairo.ImageSurface.create_from_png(broken_path)
        return self.__broken_tile

    def draw_tile(self, path, x_axis, y_axis):
        '''
        Draw Tile.

        :param path: Path for tile
        :type path: str
        :param x_axis: X Axis for tile
        :type x_axis: int
        :param y_axis: Y Axis for tile
        :type x_axis: int
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
                    # This is to prevent excessive reties for non-existant
                    # map tiles.  Anything else should be logged for more
                    # analysis.
                    self.logger.info("draw_tile: path %s", path, exc_info=True)

                # this is the case  when some jpg tile file cannot be loaded -
                # typically this was due to html content saved as jpg
                # (due to an un-trapped http error), or due to really corrupted
                # jpg (e.g. d-rats was closed before completing file save )
                if os.path.exists(path):
                    self.logger.info(
                        "draw_tile Deleting the broken tile to force future"
                        "download %s", path)
                    os.remove(path)
        else:
            surface = self.broken_tile()

        self.cairo_ctx.save()
        self.cairo_ctx.set_source_surface(surface, x_axis, y_axis)
        self.cairo_ctx.paint()
        self.cairo_ctx.restore()
        # Need to make sure that this returns false
        # when run by Glib.idle_add
        return False

    def expose_map(self):
        '''
        Expose the Map.
        '''
        width = self.map_widget.width
        height = self.map_widget.height
        self.load_ctx = LoadContext(0, (width * height))
        center = Map.Tile(self.map_widget.position)

        delta_h = height / 2
        delta_w = width  / 2

        tilesize = self.map_widget.tilesize
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
                    tile.threaded_fetch(self.draw_tile,
                                        tilesize * i,
                                        tilesize * j)
                self.progress(message)
                self.map_widget.map_tiles.append(tile)

        # time.sleep(10)
        #self.calculate_bounds()
        #self.emit("new-tiles-loaded")

    # pylint: disable=too-many-locals
    def scale(self):
        '''
        Draw the scale ladder on the Map.

        :param cairo_ctx: Cairo context for drawing area
        :type cairo_ctx: :class:`cairo.Context`
        :param pixels: Tile size in pixels, default=128
        :type pixels: int
        '''
        # Need to find out about magic number 128 for pixels.
        pango_layout = self.map_widget.map_scale_pango_layout()
        pango_width, pango_height = pango_layout.get_pixel_size()

        pixels = self.map_widget.pixels
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
