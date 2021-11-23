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

import gi
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk
gi.require_version("PangoCairo", "1.0")
from gi.repository import PangoCairo


# This makes pylance happy with out overriding settings
# from the invoker of the class
if not '_' in locals():
    import gettext
    _ = gettext.gettext


class MapDraw():
    '''
    Map Draw Handler thread.

    Drawing is done with a cairo context that is only available
    inside the draw handler.

    Putting in its own class to avoid confusion.
    '''

    def __init__(self):
        self.map_widget = None
        self.cairo_ctx = None
        self.map_visible = {}

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
        cls.map_widget = map_widget
        cls.cairo_ctx = cairo_ctx
        cls.map_visible = {}
        scrollw = map_widget.mapwindow.scrollw
        cls.map_visible['x_start'] = scrollw.get_hadjustment().get_value()
        cls.map_visible['x_size'] = scrollw.get_hadjustment().get_page_size()
        cls.map_visible['y_start'] = scrollw.get_vadjustment().get_value()
        cls.map_visible['y_size'] = scrollw.get_vadjustment().get_page_size()

        print("draw_handler", type(map_widget), type(cairo_ctx))
        cls.scale(cls)
            # map_widget.expose_map(cairo_ctx)
            # self.expose_map(cairo_ctx)
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

    def expose_map(self):
        '''
        Expose the Map.

        :param cairo_ctx: Cairo context for drawing area
        :type cairo_ctx: :class:`cairo.Context`
        '''
        print("expose_map", type(self.cairo_ctx))
        if not self.map_widget.map_tiles:
            # Draw map tiles if needed
            # Draw scale if needed.
            pass

    def scale(self, pixels=128):
        '''
        Draw the scale ladder on the Map.

        :param cairo_ctx: Cairo Context
        :param pixels: Optional pixels, default=128
        '''
        # Need to find out about magic number 128 for pixels.
        print("Map.MapDraw.scale")

        # rect = Gdk.Rectangle(x-pixels,y-shift-tick,x,y)
        # self.window.invalidate_rect(rect, True)

        dist = self.map_widget.map_distance_with_units(pixels)

        color = Gdk.RGBA()
        color.parse('black')
        self.cairo_ctx.save()

        self.cairo_ctx.set_source_rgba(color.red,
                                       color.green,
                                       color.blue,
                                       color.alpha)

        self.cairo_ctx.new_path()
        visible = self.map_visible
        scale_x = visible['x_start'] + visible['x_size'] - 200
        scale_y = visible['y_start'] + visible['y_size'] - 40

        print("self axis", visible, scale_x, scale_y)
        # x_axis = 600
        # y_axis = 320
        scale_tick = 5 # int(pixels / 25)
        text_offset = scale_tick * 2

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
        pango_layout = self.map_widget.create_pango_layout("")
        pango_layout.set_markup("%s" % dist)
        PangoCairo.show_layout(self.cairo_ctx, pango_layout)
        self.cairo_ctx.stroke()
        self.cairo_ctx.restore()
