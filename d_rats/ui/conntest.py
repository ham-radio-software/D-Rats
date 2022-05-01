#!/usr/bin/python
#
# Copyright 2009 Dan Smith <dsmith@danplanet.com>
# Copyright 2021-2022 John. E. Malmberg - Python3 Conversion
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

'''Connection Test.'''

import logging
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import GLib

if not '_' in locals():
    import gettext
    _ = gettext.gettext


TEST_TYPE_FIXEDMULTI = 0
TEST_TYPE_GRADMULTI = 1

MODULE_LOGGER = logging.getLogger("ConnTest")


def calc_watchdog(size):
    '''
    Calculate Watchdog.

    :param size: Packet size
    :type size: int
    :returns: Watchdog in milliseconds
    :rtype: float
    '''
    size += 35                        # Packetization overhead
    bytes_per_sec = 950 / 8           # 950 bits per second
    sec = 10 + (size / bytes_per_sec)  # Time to transmit, plus padding

    MODULE_LOGGER.info("Waiting %i seconds for send of %i", sec, size)

    return int(sec * 1000)


# pylint wants a max of 7 instance attributes
# pylint: disable=too-many-instance-attributes
class ConnTestAssistant(Gtk.Assistant):
    '''
    Connection Test Assistant.

    :param station: Station to test, default ""
    :type station: str
    :param port: Radio port to connect to, default "DEFAULT"
    :type port: str
    '''
    __gsignals__ = {
        "ping-echo-station" : (GObject.SignalFlags.ACTION,
                               GObject.TYPE_NONE,
                               (GObject.TYPE_STRING,    # Station
                                GObject.TYPE_STRING,    # Port
                                GObject.TYPE_STRING,    # Data
                                GObject.TYPE_PYOBJECT,  # Callback
                                GObject.TYPE_PYOBJECT)),# Callback data
        }

    def __init__(self, station="", port="DEFAULT"):
        Gtk.Assistant.__init__(self)

        self.logger = logging.getLogger("ConnTestAssistant")
        self.set_title("Connectivity Test")

        self.enabled = True

        self.__station = station
        self.__port = port
        self.__type = TEST_TYPE_FIXEDMULTI

        self.__tests = {}
        self.__values = {}
        self.__stats_vals = {}
        self.response = None

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

    def make_start_page(self, station, port):
        '''
        Make Start Page.

        :returns: Gtk.Box object
        :rtype: :class:`Gtk.Box`
        '''
        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)

        def set_station(entry):
            '''
            Set station entry handler.

            :param entry: Entry widget
            :type entry: :class:`Gtk.Entry`
            '''
            self.__station = entry.get_text()
            self.set_page_complete(vbox, bool(self.__station))

        def set_type(_radio_button, test_type):
            '''
            Set type radiobutton handler.

            :param _radio_button: Radio button widget
            :type _radio_button: :class:`Gtk.RadioButton`
            :param test_type: Test Type
            :type test_type: int
            '''
            self.__type = test_type

            for value in self.__tests.values():
                value.hide()
            self.__tests[test_type].show()

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
        rb2 = Gtk.RadioButton.new_with_label_from_widget(
            rb1, _("Gradually increasing packet sizes"))
        rb2.connect("clicked", set_type, TEST_TYPE_GRADMULTI)
        rb2.show()
        box.pack_start(rb1, 0, 0, 0)
        box.pack_start(rb2, 0, 0, 0)
        box.show()

        frame.add(box)
        vbox.pack_start(frame, 0, 0, 0)

        vbox.show()
        return vbox

    def __make_grid(self, gridspec):
        row = 0

        def set_value(spin_button, name):
            '''
            Set value spinbutton handler.

            :param spin_button: SpinButton widget
            :type spin_button: :class:`Gtk.SpinButton`
            :param name: Name of spinbutton
            :type name: str
            '''
            self.__values[name] = spin_button.get_value_as_int()

        grid = Gtk.Grid()
        grid.set_column_spacing(5)

        for name, start_value, increment, max_value in gridspec:
            label = Gtk.Label.new(name + ":")
            label.show()
            spin_button = Gtk.SpinButton.new_with_range(increment,
                                                        max_value,
                                                        increment)
            spin_button.set_digits(0)
            spin_button.set_value(start_value)
            spin_button.connect("value-changed", set_value, name)
            spin_button.show()

            grid.attach(label, 0, row, 1, 1)
            grid.attach_next_to(spin_button, label, Gtk.PositionType.RIGHT,
                                1, 1)
            set_value(spin_button, name)

            row += 1
        return grid

    def make_gradmulti_settings(self):
        '''
        Make Gradmulti Settings.

        :returns: Gtk.Grid object
        :rtype: :class:`Gtk.Grid`
        '''
        rows = [
            (_("Attempts per size"), 3.0, 1.0, 10),
            (_("Increment size"), 256, 128, 1024),
            (_("Starting size"), 256, 256, 2048),
            (_("Ending size"), 1024, 256, 4096)]

        grid = self.__make_grid(rows)
        return grid

    def make_fixedmulti_settings(self):
        '''
        Make Fixedmulti Settings.

        :returns: Gtk.Grid object
        :rtype: :class:`Gtk.Grid`
        '''
        rows = [
            (_("Packet size"), 256, 128, 4096),
            (_("Number of packets"), 10, 1, 60)]

        grid = self.__make_grid(rows)

        return grid

    def make_settings_page(self):
        '''
        Make Settings Page.

        :returns: Gtk.Box object
        :rtype: :class:`Gtk.Box`
        '''
        self.__tests[TEST_TYPE_FIXEDMULTI] = self.make_fixedmulti_settings()
        self.__tests[TEST_TYPE_GRADMULTI] = self.make_gradmulti_settings()

        box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        for value in self.__tests.values():
            box.pack_start(value, 1, 1, 1)

        self.__tests[TEST_TYPE_FIXEDMULTI].show()

        box.show()
        return box

    def make_stats_table(self):
        '''
        Make Stats Table.

        :returns: Gtk.Grid object
        :rtype: :class:`Gtk.Grid`
        '''
        grid = Gtk.Grid()
        grid.set_column_spacing(10)

        grid_col = 0
        for i in ["", _("Sent"), _("Received"), _("Total")]:
            label = Gtk.Label.new(i)

            label.show()
            grid.attach(label, grid_col, 0, 1, 1)
            grid_col += 1

        label = Gtk.Label.new(_("Packets"))
        label.show()

        grid.attach(label, 0, 1, 1, 1)

        label = Gtk.Label.new(_("Bytes"))
        label.show()
        grid.attach(label, 0, 2, 1, 1)

        self.__stats_vals = {}

        spec = [("ps", "pr", "pt"),
                ("bs", "br", "bt")]

        grid_row = 1
        for row in spec:
            grid_col = 1
            for col in row:
                label = Gtk.Label.new()
                label.show()
                self.__stats_vals[col] = label
                grid.attach(label, grid_col, grid_row, 1, 1)
                grid_col += 1
            grid_row += 1

        grid.show()
        return grid

    def make_test_page(self):
        '''
        Make Test Page.

        :returns: Gtk.Box object
        :rtype: :class:`Gtk.Box`
        '''
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
        '''
        Set Test Value.

        :param pairs: list of name value pairs
        :type pairs: list[tuple[str, str]]
        '''
        if len(pairs) % 2:
            self.logger.info("Ack! need name=value pairs!")
            return

        for i in range(0, len(pairs), 2):
            name = pairs[i]
            val = pairs[i+1]
            self.__stats_vals[name].set_text("%i" % val)

    def set_test_status(self, status, frac, loss):
        '''
        Set Test Status.

        :param status: Status of test
        :type status: str
        :param frac: fraction data
        :type: frac: float
        :param loss: Data loss
        :type loss: float
        '''
        self.__test_status.set_text(status)
        self.__prog.set_fraction(frac)
        self.__loss.set_text("%.1f %% copy" % (loss * 100.0))

    def set_test_complete(self):
        '''Set test complete.'''
        self.set_page_complete(self.__test_page, True)

    def test_fixedmulti(self, station, port, size, packets):
        '''
        Test Fixedmulti.

        :param station: Station to test
        :type station: str
        :param port: Radio Port
        :type port: str
        :param size: Size of transmission
        :type size: int
        :param packets: Packets to send
        :type packets: int
        '''
        self.set_test_val("pt", packets, "bt", packets * size)

        parent = self

        class TestContext():
            '''Test Context.'''

            def __init__(self):
                self.packets_sent = self.packets_recv = 0
                self.cycle = 0

            def update(self):
                '''Update.'''
                parent.set_test_val("ps", self.packets_sent,
                                    "bs", self.packets_sent * size)
                parent.set_test_val("pr", self.packets_recv,
                                    "br", self.packets_recv * size)

                try:
                    copy = self.packets_recv / float(self.cycle)
                    done = self.packets_recv / float(packets)
                except ZeroDivisionError:
                    return
                if self.complete():
                    parent.set_test_complete()
                    parent.set_test_status("Complete", done, copy)
                else:
                    parent.set_test_status("Attempt %i of %i"  %
                                           (self.packets_sent, packets),
                                           done, copy)

            def complete(self):
                '''
                Complete.

                :returns: True if test is complete
                :rtype: bool
                '''
                return self.cycle >= packets

            def sendping(self):
                '''Send Ping.'''
                self.packets_sent += 1
                data = "0" * int(size)
                GLib.timeout_add(calc_watchdog(size), self.timecb,
                                 self.packets_sent)
                parent.emit("ping-echo-station",
                            station, port, data, self.recvcb,
                            self.packets_sent)

            def recvcb(self, number):
                '''
                Receive Callback.

                :param number: Context PS Number
                :type number: int
                '''
                if self.packets_sent != number:
                    return

                self.packets_recv += 1
                self.cycle += 1

                if not self.complete() and parent.enabled:
                    self.sendping()
                self.update()

            def timecb(self, number):
                '''
                Time Callback.

                :param number: Context ps number
                :type number: int
                '''
                if self.packets_sent != number:
                    return

                self.cycle += 1

                if not self.complete() and parent.enabled:
                    self.sendping()
                self.update()

        ctx = TestContext()
        ctx.sendping()
        ctx.update()

    # pylint wants up to only 5 arguments
    # pylint: disable=too-many-arguments
    def test_gradmulti(self, station, port, att, inc, start, end):
        '''
        Test Gradmulti.

        :param station: Station to test
        :type station: str
        :param port: Radio Port
        :type port: str
        :param att: Attempt value
        :type att: int
        :param inc: Increment
        :type inc: int
        :param start: Start Value
        :type start: int
        :param end: End value
        :type end: int
        '''
        ptotal = btotal = 0
        size = start
        while size <= end:
            ptotal += att
            btotal += (att * size)
            size += inc

        self.set_test_val("pt", ptotal, "bt", btotal)

        parent = self

        class TestContext():
            '''Test Context.'''

            def __init__(self):
                self.bytes_sent = 0
                self.bytes_recv = 0
                self.packets_sent = 0
                self.packets_recv = 0
                self.size = start
                self.cycle = 0

            def update(self):
                '''Update.'''
                parent.set_test_val("ps", self.packets_sent,
                                    "bs", self.bytes_sent)
                parent.set_test_val("pr", self.packets_recv,
                                    "br", self.bytes_recv)

                done = self.bytes_recv / float(btotal)
                if self.bytes_sent != self.size:
                    copy = self.bytes_recv / float(self.bytes_sent  - self.size)
                else:
                    copy = self.bytes_recv

                if self.complete():
                    parent.set_test_complete()
                    parent.set_test_status("Complete", done, copy)
                else:
                    parent.set_test_status("Attempt %i of %i at size %i" %
                                           (((self.packets_sent - 1) % att) + 1,
                                            att, self.size),
                                           done, copy)

            def complete(self):
                '''
                Complete.

                :returns: True if complete
                :rtype: bool
                '''
                return self.cycle >= ptotal

            def sendping(self):
                '''Send Ping.'''
                if self.packets_sent and (self.packets_sent % att) == 0:
                    self.size += inc

                self.bytes_sent += self.size
                self.packets_sent += 1

                data = "0" * int(self.size)
                GLib.timeout_add(calc_watchdog(self.size), self.timecb,
                                 self.packets_sent)
                parent.emit("ping-echo-station",
                            station, port, data, self.recvb, self.packets_sent)

            def recvb(self, number):
                '''
                Receive Callback.

                :param number: Context ps number
                :type number: int
                '''
                if self.packets_sent != number:
                    return

                self.packets_recv += 1
                self.bytes_recv += ctx.size
                self.cycle += 1

                if not self.complete() and parent.enabled:
                    self.sendping()
                self.update()

            def timecb(self, number):
                '''
                Time Callback.

                :param number: Context ps number
                :type number: int
                '''
                if self.packets_sent != number:
                    return

                self.cycle += 1

                if not self.complete() and parent.enabled:
                    self.sendping()
                self.update()

        ctx = TestContext()
        ctx.sendping()
        ctx.update()

    def start_test(self, button):
        '''
        Start Test Handler.

        :param button: Button object
        :type button: :class:`Gtk.Button`
        '''
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

    def exit(self, _assistant, response):
        '''
        Exit Assistant Handler.

        :param _assistant: Assistant widget, unused
        :type _assistant: :class:`Gtk.Assistant`
        :param response: Exit response code
        :type response: :class:`Gtk.ResponseType`
        '''
        self.response = response
        self.enabled = False
        Gtk.main_quit()

    def run(self):
        '''Run.'''
        self.show()
        self.set_modal(True)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        Gtk.main()
        self.hide()


def main():
    '''Unit Test.'''
    assist = ConnTestAssistant("WB8TYW-1")
    assist.show()
    Gtk.main()


if __name__ == "__main__":
    main()
