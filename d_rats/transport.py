#!/usr/bin/python
#
# Copyright 2008 Dan Smith <dsmith@danplanet.com>
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

#importing printlog() wrapper
from .debug import printlog

import threading
import re
import time
import random
import traceback
import sys

from . import utils
from . import ddt2
from . import comm
from six.moves import range

class BlockQueue(object):
    def __init__(self):
        self._lock = threading.Lock()
        self._queue = []

    def enqueue(self, block):
        self._lock.acquire()
        self._queue.insert(0, block)
        self._lock.release()

    def requeue(self, block):
        self._lock.acquire()
        self._queue.append(block)
        self._lock.release()

    def dequeue(self):
        self._lock.acquire()
        try:
            b = self._queue.pop()
        except IndexError:
            b = None
        self._lock.release()

        return b

    def dequeue_all(self):
        self._lock.acquire()
        l = self._queue
        self._queue = []
        self._lock.release()

        return l

    def peek(self):
        self._lock.acquire()
        try:
            el = self._queue[0]
        except:
            el = None
        self._lock.release()
        
        return el

    def peek_all(self):
        self._lock.acquire()
        q = self._queue
        self._lock.release()

        return q

    # BE CAREFUL WITH THESE!

    def lock(self):
        self._lock.acquire()

    def unlock(self):
        self._lock.release()

class Transporter(object):
    def __init__(self, pipe, inhandler=None, authfn=None, **kwargs):
        self.inq = BlockQueue()
        self.outq = BlockQueue()
        self.pipe = pipe
        self.inbuf = b""
        self.enabled = True
        self.inhandler = inhandler
        self.compat = kwargs.get("compat", False)
        self.warmup_length = kwargs.get("warmup_length", 8)
        self.warmup_timeout = kwargs.get("warmup_timeout", 3)
        self.force_delay = kwargs.get("force_delay", 0)
        self.compat_delay = kwargs.get("compat_delay", 5)
        self.msg_fn = kwargs.get("msg_fn", None)
        self.name = kwargs.get("port_name", "")

        self.thread = threading.Thread(target=self.worker,
                                       args=(authfn,))
        self.thread.setDaemon(True)
        self.thread.start()

        self.last_xmit = 0
        self.last_recv = 0

    def __send(self, data):
        for i in range(0, 10):
            try:
                return self.pipe.write(data)
            except comm.DataPathIOError as e:
                if not self.pipe.can_reconnect:
                    break
                printlog("Transport"," : Data path IO error: %s" % e)
                try:
                    time.sleep(i)
                    printlog("Transport"," : Attempting reconnect...")
                    self.pipe.reconnect()
                except comm.DataPathNotConnectedError:
                    pass

        raise comm.DataPathIOError("Unable to reconnect")

    def __recv(self):
        data = b""
        for i in range(0, 10):
            try:
                return self.pipe.read_all_waiting()
            except comm.DataPathIOError as e:
                if not self.pipe.can_reconnect:
                    break
                printlog("Transport"," : Data path IO error: %s" % e)
                try:
                    time.sleep(i) 
                    printlog("Transport"," : Attempting reconnect...")
                    self.pipe.reconnect()
                except comm.DataPathNotConnectedError:
                    pass

        raise comm.DataPathIOError("Unable to reconnect")

    def get_input(self):
        chunk = self.__recv()
        if chunk:
            self.inbuf += chunk
            self.last_recv = time.time()

    def _handle_frame(self, frame):
        if self.inhandler:
            self.inhandler(frame)
        else:
            self.inq.enqueue(frame)

    def parse_blocks(self):
        # start processing data from the packet arrived 
        while ddt2.ENCODED_HEADER in self.inbuf and \
                ddt2.ENCODED_TRAILER in self.inbuf:
            s = self.inbuf.index(ddt2.ENCODED_HEADER)
            e = self.inbuf.index(ddt2.ENCODED_TRAILER) + \
                len(ddt2.ENCODED_TRAILER)

            if e < s:
                # Excise the extraneous end
                _tmp = self.inbuf[:e-len(ddt2.ENCODED_TRAILER)] + \
                    self.inbuf[e:]
                self.inbuf = _tmp
                continue

            block = self.inbuf[s:e]
            self.inbuf = self.inbuf[e:]

            f = ddt2.DDT2EncodedFrame()
            try:
                if f.unpack(block):
                    printlog("Transport"," : Got a block: %s" % f)
                    self._handle_frame(f)
                elif self.compat:
                    self._send_text_block(block)
                else:
                    printlog("Transport"," : Found a broken block (S:%i E:%i len(buf):%i" % (s, e, len(self.inbuf)))
                    utils.hexprintlog(block)
            except Exception as e:
                printlog("Transport"," : Failed to process block:")
                utils.log_exception()

    def _match_gps(self):
        # NMEA-style
        # Starts with $GP**[a-f0-9]{2}\r?\n?
        inbuf_str = self.inbuf.decode('utf-8', 'replace')
        m = re.search(
            r"((?:\$GP[^\*]+\*[A-f0-9]{2}\r?\n?){1,2}.{8},.{20})",
            inbuf_str)
        if m:
            return bytearray(m.group(1), 'utf-8', 'replace')

        # GPS-A style
        # Starts with $$CRC[A-Z0-9]{4},\r
        m = re.search(r"(\$\$CRC[A-z0-9]{4},[^\r]*\r)", inbuf_str)
        if m:
            return bytearray(m.group(1), 'utf-8', 'replace')
        if u"$$CRC" in inbuf_str:
            printlog("Transport"," : Didn't match:\n%s" % repr(self.inbuf))
        return None

    def _send_text_block(self, string):
        f = ddt2.DDT2RawData()
        f.seq = 0
        f.session = 1 # Chat (for now)
        f.s_station = "CQCQCQ"
        f.d_station = "CQCQCQ"
        f.data = utils.filter_to_ascii(string)
        
        self._handle_frame(f)

    def _parse_gps(self):
        result = self._match_gps()
        if result:
            new_inbuf = self.inbuf.replace(result, b"")
            if isinstance(new_inbuf, str):
                self.inbuf = bytearray(new_inbuf, 'utf-8', 'replace')
            else:
                self.inbuf = new_inbuf
            printlog("Transport"," : Found GPS string: %s" % repr(result))
            self._send_text_block(result)
        else:
            return None

    def parse_gps(self):
        while self._match_gps():
            self._parse_gps()
            
    def send_frames(self):
        delayed = False

        while True:
            f = self.outq.dequeue()
            if not f:
                break

            if self.force_delay and not delayed:
                if self.force_delay < 0:
                    # If force_delay is negative, wait between 0.5 and
                    # abs(force_delay) seconds before transmitting
                    delay = random.randint(5, abs(self.force_delay)*10)/10.0
                else:
                    # If force_delay is positive, then wait exactly that
                    # long before transmitting
                    delay = self.force_delay

                printlog("Transport"," : Waiting %.1f sec before transmitting" % delay)
                time.sleep(delay)
                delayed = True

            if ((time.time() - self.last_xmit) > self.warmup_timeout) and \
                    (self.warmup_timeout > 0):
                warmup_f = ddt2.DDT2EncodedFrame()
                warmup_f.seq = 0
                warmup_f.session = 0
                warmup_f.type = 254
                warmup_f.s_station = "!"
                warmup_f.d_station = "!"
                warmup_f.data = ("\x01" * self.warmup_length)
                warmup_f.set_compress(False)
                printlog(("Transport : Sending warm-up: %s" % warmup_f))
                self.__send(warmup_f.get_packed())

            printlog("Transport"," : Sending block: %s" % f)
            f._xmit_s = time.time()
            self.__send(f.get_packed())
            f._xmit_e = time.time()
            f.sent_event.set()
            self.last_xmit = time.time()

    def compat_is_time(self):
        return (time.time() - self.last_recv) > self.compat_delay

    def worker(self, authfn):
        if not self.pipe.is_connected():
            if self.msg_fn:
                self.msg_fn("Connecting")
                printlog("Transport"," : worker function Connecting")
    
            try:
                self.pipe.connect()
            except comm.DataPathNotConnectedError as e:
                if self.msg_fn:
                    self.msg_fn("Unable to connect (%s)" % e)
                printlog("Transport"," : Comm %s did not connect: %s" % (self.pipe, e))
                return

        if authfn and not authfn(self.pipe):
            if self.msg_fn:
                self.msg_fn("Authentication failed")
            self.enabled = False
        elif self.msg_fn:
            self.msg_fn("Connected")

        while self.enabled:
            try:
                self.get_input()
            except Exception as e:
                printlog("Transport"," : Exception while getting input: %s" % e)
                utils.log_exception()
                self.enabled = False
                break

            self.parse_blocks()
            self.parse_gps()

            if self.inbuf and self.compat_is_time():
                if self.compat:
                    self._send_text_block(self.inbuf)
                else:
                    printlog("Transport"," : ### Unconverted data: %s" % self.inbuf)
                self.inbuf = b""

            try:
                self.send_frames()
            except Exception as e:
                printlog("Transport"," : Exception while sending frames: %s" % e)
                self.enabled = False
                break

    def disable(self):
        self.inhandler = None
        self.enabled = False
        self.thread.join()
        
    def send_frame(self, frame):
        if not self.enabled:
            printlog("Transport"," : Refusing to queue block for dead transport")
            return
        self.outq.enqueue(frame)

    def recv_frame(self):
        return self.inq.dequeue()

    def flush_blocks(self, id):
        # This should really call a flush method in the blockqueue with a
        # test function
        self.outq.lock()
        for b in self.outq._queue[:]:
            if b.session == id:
                printlog(("Transport : Flushing block: %s" % b))
                try:
                    self.outq._queue.remove(b)
                except ValueError:
                    printlog("Transport"," : Block disappeared while flushing?")
        self.outq.unlock()

    def __str__(self):
        return str(self.pipe)

class TestPipe(object):
    def make_fake_data(self, src, dst):
        self.buf = b""

        for i in range(10):
            f = ddt2.DDT2EncodedFrame()
            f.s_station = src
            f.d_station = dst
            f.type = 1
            f.seq = i
            f.session = 0
            f.data = "This is a test frame to parse"

            self.buf += b"asg;sajd;jsadnkbasdl;b  as;jhd[SOB]laskjhd" + \
                b"asdkjh[EOB]a;klsd" + f.get_packed() + b"asdljhasd[EOB]" + \
                b"asdljb  alsjdljn[asdl;jhas"
            
            if i == 5:
                self.buf += b"$GPGGA,075519,4531.254,N,12259.400,W,1,3,0,0.0,M,0,M,,*55\r\nK7HIO   ,GPS Info\r"
            elif i == 7:
                self.buf += b"$$CRC6CD1,Hills-Water-Treat-Plt>APRATS,DSTAR*:@233208h4529.05N/12305.91W>Washington County ARES;Hills Water Treat Pl\r\n"

            elif i == 2:
                self.buf += \
b"""$GPGGA,023531.36,4531.4940,N,12254.9766,W,1,07,1.3,63.7,M,-21.4,M,,*64\r\n$GPRMC,023531.36,A,4531.4940,N,12254.9766,W,0.00,113.7,010808,17.4,E,A*27\rK7TAY M ,/10-13/\r"""
                

        printlog(("Transport :  Made some data: %s" % self.buf))

    
    def __init__(self, src="Sender", dst="Recvr"):
        self.make_fake_data(src, dst)

    def is_connected(self):
        return True

    def read_all_waiting(self):
        if not self.buf:
            return ""

        num = random.randint(1, 200)

        b = self.buf[:num]
        self.buf = self.buf[num:]

        return b

    def write(self, buf):
        pass

def test_simple():
    p = TestPipe()
    t = Transporter(p)
    
    f = ddt2.DDT2EncodedFrame()
    f.seq = 9
    f.type = 8
    f.session = 7
    f.d_station = "You"
    f.s_station = "Me"
    f.data = "ACK"
    t.send_frame(f)

    time.sleep(2)

    f = t.recv_frame()
    printlog(("Transport :  Received block: %s" % f))

    t.disable()

if __name__ == "__main__":
    test_simple()
