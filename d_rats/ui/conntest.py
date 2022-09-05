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

#importing printlog() wrapper
from ..debug import printlog

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject

#try:
#   from gtk import Assistant as baseclass
#except ImportError:
#    printlog("ConnTest","  : No Assistant support")
#    from d_rats.geocode_ui import baseclass

if __name__ == "__main__":
    def _(string):
        return string

TEST_TYPE_FIXEDMULTI = 0
TEST_TYPE_GRADMULTI = 1

def calc_watchdog(size):
    size += 35                        # Packetization overhead
    bytes_per_sec = 950 / 8           # 950 bits per second
    sec = 10 + (size / bytes_per_sec)  # Time to transmit, plus padding

    printlog("ConnTest","  : Waiting %i seconds for send of %i" % (sec, size))

    return int(sec * 1000)

class ConnTestAssistant(Gtk.Assistant):
    __gsignals__ = {
        "ping-echo-station" : (GObject.SignalFlags.ACTION,
                               GObject.TYPE_NONE,
                               (GObject.TYPE_STRING,    # Station
                                GObject.TYPE_STRING,    # Port
                                GObject.TYPE_STRING,    # Data
                                GObject.TYPE_PYOBJECT,  # Callback
                                GObject.TYPE_PYOBJECT)),# Callback data
        }

    def make_start_page(self, station, port):
        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)

        def set_station(entry):
            self.__station = entry.get_text()
            self.set_page_complete(vbox, bool(self.__station))

        def set_type(rb, type):
            self.__type = type

            for v in self.__tests.values():
                v.hide()
            self.__tests[type].show()

        box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        slb = Gtk.Label.new(_("Remote station:"))
        slb.show()
        sta = Gtk.Entry()
        sta.set_max_length(8)
        sta.set_text(station)
        sta.set_sensitive(False)
        sta.connect("changed", set_station)
        sta.show()
        plb = Gtk.Label.new(_("Port:"))
        plb.show()
        prt = Gtk.Entry()
        prt.set_text(port)
        prt.set_sensitive(False)
        prt.show()
        box.pack_start(slb, 0, 0, 0)
        box.pack_start(sta, 0, 0, 0)
        box.pack_start(plb, 0, 0, 0)
        box.pack_start(prt, 0, 0, 0)
        box.show()
        vbox.pack_start(box, 0, 0, 0)

        frame = Gtk.Frame.new(_("Test Type"))
        frame.show()

        box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        rb1 = Gtk.RadioButton.new_with_label(None,
                                             _("Multiple fixed-size packets"))
        rb1.connect("clicked", set_type, TEST_TYPE_FIXEDMULTI)
        rb1.show()
        rb2 = Gtk.RadioButton.new_with_label_from_widget(rb1,
            _("Gradually increasing packet sizes"))
        rb2.connect("clicked", set_type, TEST_TYPE_GRADMULTI)
        rb2.show()
        box.pack_start(rb1, 0, 0, 0)
        box.pack_start(rb2, 0, 0, 0)
        box.show()

        frame.add(box)
        vbox.pack_start(frame, 0, 0, 0)

        vbox.show()
        return vbox

    def __make_grid(self, table, gridspec):
        #vals = {}
        row = 0

        def set_value(spin, scrolltype, name):
            self.__values[name] = spin.get_value()
            return False

        for l, s, i, u in gridspec:
            lab = Gtk.Label.new(l + ":")
            lab.show()
            #           w    l  t    r-l+1  b - t + 1
            # grid.attach(lab, 0, row, 0, 2)
            #              w    l  r  t    b      x opt
            table.attach(lab, 0, 1, row, row+1, Gtk.AttachOptions.SHRINK)

            adj = Gtk.Adjustment.new(s, i, u, i, 0, 0)
            val = Gtk.SpinButton()
            val.set_adjustment(adj)
            val.set_digits(0)
            val.connect("input", set_value, l)
            val.show()
            # grid.attach(val, 1, row, 2, 2)
            table.attach(val, 1, 2, row, row+1, Gtk.AttachOptions.SHRINK)

            set_value(val, None, l)

            row += 1

    def make_gradmulti_settings(self):
        # grid = Gtk.Grid()
        table = Gtk.Table.new(8, 2, False)

        rows = [
            (_("Attempts per size"), 3, 1, 10),
            (_("Increment size"), 256, 128, 1024),
            (_("Starting size"), 256, 256, 2048),
            (_("Ending size"), 1024, 256, 4096)]

        self.__make_grid(table, rows)

        return table

    def make_fixedmulti_settings(self):
        # grid = Gtk.Grid()
        table = Gtk.Table.new(2, 2, False)

        rows = [
            (_("Packet size"), 256, 128, 4096),
            (_("Number of packets"), 10, 1, 60)]

        self.__make_grid(table, rows)

        return table

    def make_settings_page(self):
        self.__tests[TEST_TYPE_FIXEDMULTI] = self.make_fixedmulti_settings()
        self.__tests[TEST_TYPE_GRADMULTI] = self.make_gradmulti_settings()

        box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        for v in self.__tests.values():
            box.pack_start(v, 1, 1, 1)

        self.__tests[TEST_TYPE_FIXEDMULTI].show()

        box.show()
        return box

    def make_stats_table(self):
        # grid = Gtk.Grid()
        table = Gtk.Table.new(3, 4, False)

        col = 0
        row = 0
        for i in ["", _("Sent"), _("Received"), _("Total")]:
            lab = Gtk.Label.new(i)
            lab.show()
            #           w    l    t  r-l+1  b - t + 1
            # grid.attach(lab, col, 0, 2, 2)
            #              w   l     r     t   b
            table.attach(lab, col, col+1, 0, 1)
            col += 1

        lab = Gtk.Label.new(_("Packets"))
        lab.show()
        # grid.attach(lab, 0, 1, 2, 2)
        table.attach(lab, 0, 1, 1, 2)

        lab = Gtk.Label.new(_("Bytes"))
        lab.show()
        # grid.attach(lab, 0, 2, 2, 4)
        table.attach(lab, 0, 1, 2, 3)
        
        self.__stats_vals = {}

        spec = [("ps", "pr", "pt"),
                ("bs", "br", "bt")]

        _row = 1
        for row in spec:
            _col = 1
            for col in row:
                lab = Gtk.Label.new()
                lab.show()
                self.__stats_vals[col] = lab
                # grid.attach(lab, _col, _row, 2, 2)
                table.attach(lab, _col, _col+1, _row, _row+1)
                _col += 1
            _row += 1

        table.show()
        return table

    def make_test_page(self):
        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)

        frame = Gtk.Frame.new(_("Status"))
        self.__test_status = Gtk.Entry()
        self.__test_status.show()
        self.__test_status.set_editable(False)
        frame.add(self.__test_status)
        frame.show()
        vbox.pack_start(frame, 0, 0, 0)

        frame = Gtk.Frame.new(_("Statistics"))
        frame.add(self.make_stats_table())
        frame.show()
        vbox.pack_start(frame, 1, 1, 1)

        hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 2)

        self.__loss = Gtk.Label.new("")
        self.__loss.show()
        hbox.pack_start(self.__loss, 0, 0, 0)

        self.__prog = Gtk.ProgressBar()
        self.__prog.set_fraction(0.0)
        self.__prog.show()
        hbox.pack_start(self.__prog, 1, 1, 1)

        hbox.show()
        vbox.pack_start(hbox, True, True, 0)

        button = Gtk.Button.new_with_label(_("Start"))
        button.connect("clicked", self.start_test)
        button.show()
        vbox.pack_start(button, 0, 0, 0)

        vbox.show()
        return vbox

    def set_test_val(self, *pairs):
        if len(pairs) % 2:
            printlog("ConnTest","  : Ack! need name=value pairs!")
            return

        for i in range(0, len(pairs), 2):
            name = pairs[i]
            val = pairs[i+1]
            self.__stats_vals[name].set_text("%i" % val)

    def set_test_status(self, status, frac, loss):
        self.__test_status.set_text(status)
        self.__prog.set_fraction(frac)
        self.__loss.set_text("%.1f %% copy" % (loss * 100.0))

    def set_test_complete(self):
        self.set_page_complete(self.__test_page, True)

    def test_fixedmulti(self, station, port, size, packets):
        self.set_test_val("pt", packets, "bt", packets * size)

        class TestContext(object):
            # pylint: disable=no-self-argument
            def __init__(ctx):
                ctx.ps = ctx.pr = 0
                ctx.cycle = 0

            # pylint: disable=no-self-argument
            def update(ctx):
                self.set_test_val("ps", ctx.ps, "bs", ctx.ps * size)
                self.set_test_val("pr", ctx.pr, "br", ctx.pr * size)

                try:
                    copy = ctx.pr / float(ctx.cycle)
                    done = ctx.pr / float(packets)
                except ZeroDivisionError:
                    return
                if ctx.complete():
                    self.set_test_complete()
                    self.set_test_status("Complete", done, copy)
                else:
                    self.set_test_status("Attempt %i of %i"  % (ctx.ps,
                                                                packets),
                                         done, copy)

            # pylint: disable=no-self-argument
            def complete(ctx):
                return ctx.cycle >= packets

            # pylint: disable=no-self-argument
            def sendping(ctx):
                ctx.ps += 1
                data = "0" * int(size)
                GObject.timeout_add(calc_watchdog(size), ctx.timecb, ctx.ps)
                self.emit("ping-echo-station",
                          station, port, data, ctx.recvcb, ctx.ps)

            # pylint: disable=no-self-argument
            def recvcb(ctx, number):
                if ctx.ps != number:
                    return

                ctx.pr += 1
                ctx.cycle += 1

                if not ctx.complete() and self.enabled:
                    ctx.sendping()
                ctx.update()

            # pylint: disable=no-self-argument
            def timecb(ctx, number):
                if ctx.ps != number:
                    return

                ctx.cycle += 1

                if not ctx.complete() and self.enabled:
                    ctx.sendping()
                ctx.update()

        ctx = TestContext()
        ctx.sendping()   
        ctx.update()

    def test_gradmulti(self, station, port, att, inc, start, end):
        ptotal = btotal = 0
        sz = start
        while sz <= end:
            ptotal += att
            btotal += (att * sz)
            sz += inc
        
        self.set_test_val("pt", ptotal, "bt", btotal)

        class TestContext(object):
            # pylint: disable=no-self-argument
            def __init__(ctx):
                ctx.bs = ctx.br = ctx.ps = ctx.pr = 0
                ctx.size = start
                ctx.cycle = 0

            # pylint: disable=no-self-argument
            def update(ctx):
                self.set_test_val("ps", ctx.ps, "bs", ctx.bs)
                self.set_test_val("pr", ctx.pr, "br", ctx.br)

                done = ctx.br / float(btotal)
                if ctx.bs != ctx.size:
                    copy = ctx.br / float(ctx.bs  - ctx.size)
                else:
                    copy = ctx.br

                if ctx.complete():
                    self.set_test_complete()
                    self.set_test_status("Complete", done, copy)
                else:
                    self.set_test_status("Attempt %i of %i at size %i" % (\
                            ((ctx.ps - 1) % att) + 1, att, ctx.size),
                                         done, copy)

            # pylint: disable=no-self-argument
            def complete(ctx):
                return ctx.cycle >= ptotal

            # pylint: disable=no-self-argument
            def sendping(ctx):
                if ctx.ps and (ctx.ps % att) == 0:
                    ctx.size += inc

                ctx.bs += ctx.size
                ctx.ps += 1

                data = "0" * int(ctx.size)
                GObject.timeout_add(calc_watchdog(ctx.size), ctx.timecb, ctx.ps)
                self.emit("ping-echo-station",
                          station, port, data, ctx.recvb, ctx.ps)

            # pylint: disable=no-self-argument
            def recvb(ctx, number):
                if ctx.ps != number:
                    return

                ctx.pr += 1
                ctx.br += ctx.size
                ctx.cycle += 1

                if not ctx.complete() and self.enabled:
                    ctx.sendping()
                ctx.update()

            # pylint: disable=no-self-argument
            def timecb(ctx, number):
                if ctx.ps != number:
                    return

                ctx.cycle += 1

                if not ctx.complete() and self.enabled:
                    ctx.sendping()
                ctx.update()

        ctx = TestContext()
        ctx.sendping()
        ctx.update()

    def start_test(self, button):
        button.set_sensitive(False)
        self.set_page_complete(self.__test_page, False)

        if self.__type == TEST_TYPE_FIXEDMULTI:
            self.test_fixedmulti(self.__station,
                                 self.__port,
                                 self.__values[_("Packet size")],
                                 self.__values[_("Number of packets")])
        elif self.__type == TEST_TYPE_GRADMULTI:
            self.test_gradmulti(self.__station,
                                self.__port,
                                self.__values[_("Attempts per size")],
                                self.__values[_("Increment size")],
                                self.__values[_("Starting size")],
                                self.__values[_("Ending size")])

    def exit(self, foo, response):
        self.response = response
        self.enabled = False
        Gtk.main_quit()

    def __init__(self, station="", port="DEFAULT"):
        super(Gtk.Assistant, self).__init__()

        self.set_title("Connectivity Test")

        self.enabled = True

        self.__station = station
        self.__port = port
        self.__type = TEST_TYPE_FIXEDMULTI

        self.__tests = {}
        self.__values = {}

        self.__start_page = self.make_start_page(station, port)
        self.append_page(self.__start_page)
        self.set_page_title(self.__start_page, _("Test Type"))
        self.set_page_type(self.__start_page, Gtk.AssistantPageType.CONTENT)
        self.set_page_complete(self.__start_page, True)

        self.__settings_page = self.make_settings_page()
        self.append_page(self.__settings_page)
        self.set_page_title(self.__settings_page, _("Test Parameters"))
        self.set_page_type(self.__settings_page, Gtk.AssistantPageType.CONTENT)
        self.set_page_complete(self.__settings_page, True)

        self.__test_page = self.make_test_page()
        self.append_page(self.__test_page)
        self.set_page_title(self.__test_page, _("Run Test"))
        self.set_page_type(self.__test_page, Gtk.AssistantPageType.CONFIRM)
        self.set_page_complete(self.__test_page, False)

        self.connect("cancel", self.exit, Gtk.ResponseType.CANCEL)
        self.connect("apply", self.exit, Gtk.ResponseType.OK)

    def run(self):
        self.show()
        self.set_modal(True)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        Gtk.main()
        self.hide()

if __name__ == "__main__":
    a = ConnTestAssistant("WB8TYW-1")
    a.show()
    Gtk.main()
