#!/usr/bin/python
'''Transport'''
#
# Copyright 2008 Dan Smith <dsmith@danplanet.com>
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

from __future__ import absolute_import
from __future__ import print_function

import logging
import threading
import re
import time
import random

from . import utils
from . import ddt2
from .dratsexception import DataPathError
from .dratsexception import DataPathIOError
from .dratsexception import DataPathNotConnectedError

class BlockQueue():
    '''Block Queue.'''

    def __init__(self):
        self._lock = threading.Lock()
        self._queue = []

    def enqueue(self, block):
        '''
        Enqueue

        :param block: Block to queue a lock for
        :type block: :class:`DDT2Frame`
        '''
        self._lock.acquire()
        self._queue.insert(0, block)
        self._lock.release()

    def requeue(self, block):
        '''
        Requeue a lock.

        :param block: Block to return
        :type block: :class:`DDT2Frame`
        '''
        self._lock.acquire()
        self._queue.append(block)
        self._lock.release()

    def dequeue(self):
        '''
        Dequeue a block

        :returns: block dequeued
        :rtype: :class:`DDT2Frame`
        '''
        self._lock.acquire()
        if self._queue:
            block = self._queue.pop()
        else:
            block = None
        self._lock.release()

        return block

    def dequeue_all(self):
        '''
        Dequeue all locks

        :returns: Queue of locks that were released
        :rtype: list of :class:`DDT2Frame`
        '''
        self._lock.acquire()
        locks = self._queue
        self._queue = []
        self._lock.release()

        return locks

    def peek(self):
        '''
        Peek

        :returns: block
        :rtype: :class:`DDT2Frame`
        '''
        self._lock.acquire()
        if self._queue:
            element = self._queue[0]
        else:
            element = None
        self._lock.release()

        return element

    def peek_all(self):
        '''
        Peek All.

        :returns: queue of locks
        :rtype: list[:class:`DDT2Frame`]
        '''
        self._lock.acquire()
        queue = self._queue
        self._lock.release()

        return queue

    # BE CAREFUL WITH THESE!

    def lock(self):
        '''Lock.'''
        self._lock.acquire()

    def unlock(self):
        '''Unlock.'''
        self._lock.release()

# pylint wants a max of 7 instance attributes
# pylint: disable=too-many-instance-attributes
class Transporter():
    '''
    Transporter.

    :param pipe: Object for communications to a device or remote
    :type pipe: :class:`DataPath`
    :param inhandler: Optional Incoming message handler callback
    :type inhandler: function
    :param authfn: Authorization Function, Default None
    :type authfn: function
    :param compat: Compatibility mode?, default False
    :type compat: bool
    :param warmup_length: Time needed from key up to transmit in seconds,
                          Default 8
    :type warmup_length: float
    :param warmup_timeout: Time limit for warmup in seconds, default 3
    :type warmup_timeout: float
    :param force_delay: Forced delay, default 0
    :type force_delay: float
    :param compat_delay: Compatibility delay in seconds, default 5
    :type compat_delay: float
    '''

    def __init__(self, pipe, inhandler=None, authfn=None, **kwargs):
        self.logger = logging.getLogger("Transporter")
        self.inq = BlockQueue()
        self.outq = BlockQueue()
        self.pipe = pipe
        self.inbuf = b''
        self.enabled = True
        self.was_connected = False
        self.inhandler = inhandler
        self.compat = kwargs.get("compat", False)
        self.warmup_length = kwargs.get("warmup_length", 8)
        self.warmup_timeout = kwargs.get("warmup_timeout", 3)
        self.force_delay = kwargs.get("force_delay", 0)
        self.compat_delay = kwargs.get("compat_delay", 5)
        self.msg_fn = kwargs.get("msg_fn", None)
        self.name = kwargs.get("port_name", "")
        self.hexdump = False
        self.shutdown = False
        self.thread = threading.Thread(target=self.worker,
                                       args=(authfn,))
        self.thread.daemon = True
        self.thread.start()

        self.last_xmit = 0
        self.last_recv = 0

    def __send(self, data):
        for i in range(0, 10):
            try:
                if self.hexdump:
                    print("Transporter.__send/pipe", type(self.pipe))
                    utils.hexprintlog(data)
                return self.pipe.write(data)
            except DataPathIOError as err:
                if not self.pipe.can_reconnect:
                    break
                self.logger.info("__send: %s Data path IO error: %s",
                                 self.pipe, err)
                try:
                    time.sleep(i)
                    self.logger.info("__send: %s Attempting reconnect...",
                                     self.pipe)
                    self.pipe.reconnect()
                except DataPathNotConnectedError:
                    pass

        # Need to put connection info in this exception
        raise DataPathNotConnectedError("Unable to reconnect %s" % self.pipe)

    def __recv(self):
        data = b""
        for i in range(0, 10):
            try:
                return self.pipe.read_all_waiting()
            except DataPathIOError as err:
                if not self.pipe.can_reconnect:
                    break
                self.logger.info("__recv: %s Data path IO error: %s",
                                 self.pipe, err)
                try:
                    time.sleep(i)
                    self.logger.info("__recv: %s Attempting reconnect...",
                                     self.pipe)
                    self.pipe.reconnect()
                except DataPathNotConnectedError:
                    pass
        # Need to put connection info in this exception
        raise DataPathNotConnectedError("Unable to reconnect %s" % self.pipe)

    def get_input(self):
        '''Get Input.'''
        chunk = self.__recv()
        # wb8tyw, we seem to be polling get_input instead of using
        # an event based system.  If something goes wrong here, this
        # can result in a CPU bound loop.
        if chunk and self.hexdump:
            print("Transporter.get_input/pipe", type(self.pipe))
            utils.hexprintlog(chunk)
        if chunk:
            self.inbuf += chunk
            self.last_recv = time.time()

    def _handle_frame(self, frame):
        if self.inhandler:
            self.inhandler(frame)
        else:
            self.inq.enqueue(frame)

    def parse_blocks(self):
        '''Parse Blocks.'''
        # start processing data from the packet arrived
        while ddt2.ENCODED_HEADER in self.inbuf and \
                ddt2.ENCODED_TRAILER in self.inbuf:
            start = self.inbuf.index(ddt2.ENCODED_HEADER)
            end = self.inbuf.index(ddt2.ENCODED_TRAILER) + \
                  len(ddt2.ENCODED_TRAILER)

            if end < start:
                # Excise the extraneous end
                _tmp = self.inbuf[:end - len(ddt2.ENCODED_TRAILER)] + \
                    self.inbuf[end:]
                self.inbuf = _tmp
                continue

            block = self.inbuf[start:end]
            self.inbuf = self.inbuf[end:]

            frame = ddt2.DDT2EncodedFrame()
            try:
                if frame.unpack(block):
                    self.logger.debug("parse_blocks: %s Got a block: %s",
                                      self.pipe, frame)
                    self._handle_frame(frame)
                elif self.compat:
                    self._send_text_block(block)
                else:
                    self.logger.info("parse_blocks: %s Found a broken block "
                                     "(S:%i E:%i len(buf):%i",
                                     self.pipe, start, end, len(self.inbuf))
                    utils.hexprintlog(block)
            except DataPathError:
                self.logger.info("parse_blocks: %s Failed to process block",
                                 self.pipe, exc_info=True)

    def _match_gps(self):
        # NMEA-style
        # Starts with $GP**[a-f0-9]{2}\r?\n?
        inbuf_str = self.inbuf.decode('utf-8', 'replace')
        match = re.search(
            r"((?:\$GP[^\*]+\*[A-f0-9]{2}\r?\n?){1,2}.{8},.{20})",
            inbuf_str)
        if match:
            return bytearray(match.group(1), 'utf-8', 'replace')

        # GPS-A style
        # Starts with $$CRC[A-Z0-9]{4},\r
        match = re.search(r"(\$\$CRC[A-z0-9]{4},[^\r]*\r)", inbuf_str)
        if match:
            return bytearray(match.group(1), 'utf-8', 'replace')
        if u"$$CRC" in inbuf_str:
            self.logger.info("_match_gps: %s Didn't match:\n%s",
                             self.pipe, repr(self.inbuf))
        return None

    def _send_text_block(self, string):
        frame = ddt2.DDT2RawData()
        frame.seq = 0
        frame.session = 1 # Chat (for now)
        frame.s_station = "CQCQCQ"
        frame.d_station = "CQCQCQ"
        if isinstance(string, str):
            self.logger.info("_send_text_block: %s Called with str data!",
                             self.pipe)
            ascii_data = utils.filter_to_ascii(string)
        else:
            ascii_data = utils.filter_to_ascii_bytes(string)
        frame.data = ascii_data

        self._handle_frame(frame)

    def _parse_gps(self):
        result = self._match_gps()
        if result:
            new_inbuf = self.inbuf.replace(result, b"")
            if isinstance(new_inbuf, str):
                self.inbuf = bytearray(new_inbuf, 'utf-8', 'replace')
            else:
                self.inbuf = new_inbuf
            self.logger.info("_parse_gps: %s Found GPS string: %s",
                             self.pipe, repr(result))
            self._send_text_block(result)

    def parse_gps(self):
        '''Parse GPS.'''
        while self._match_gps():
            self._parse_gps()

    def send_frames(self):
        '''Send Frames.'''
        delayed = False

        while True:
            frame = self.outq.dequeue()
            if not frame:
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

                self.logger.info("send_frames: %s Waiting %.1f sec before "
                                 "transmitting", self.pipe, delay)
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
                self.logger.info("send_frames: %s Sending warm-up: %s",
                                 self.pipe, warmup_f)
                self.__send(warmup_f.get_packed())

            self.logger.debug("send_frames: %s Sending block: %s",
                              self.pipe, frame)
            # pylint: disable=protected-access
            frame._xmit_s = time.time()
            self.__send(frame.get_packed())
            # pylint: disable=protected-access
            frame._xmit_e = time.time()
            frame.sent_event.set()
            self.last_xmit = time.time()

    def compat_is_time(self):
        '''
        Compat is time.

        :returns: True if time is > self.compat_delay
        :rtype: bool
        '''
        return (time.time() - self.last_recv) > self.compat_delay


    def auth_connect(self, authfn):
        '''
        Authorized Connection.

        :param authfn: Authorization Function
        :type authfn: function
        '''
        if authfn and not authfn(self.pipe):
            if self.msg_fn:
                self.msg_fn("Authentication failed")
            self.enabled = False
        elif self.msg_fn:
            self.msg_fn("Connected")
            # We connected once:
            if self.pipe.can_reconnect:
                self.was_connected = True

    # pylint wants a max of 12 branches
    # pylint: disable=too-many-branches
    def worker(self, authfn):
        '''Thread Worker.

        :param authfn: Authorization Function
        :type authfn: function
        '''
        if not self.pipe.is_connected():
            if self.msg_fn:
                self.msg_fn("Connecting")

            try:
                self.pipe.connect()
            except DataPathNotConnectedError as err:
                if self.msg_fn:
                    self.msg_fn("Unable to connect (%s)" % err)
                self.logger.info("worker: Comm %s did not connect: %s",
                                 self.pipe, err)
                return

        self.auth_connect(authfn)

        while self.enabled:
            while self.enabled:
                if self.shutdown:
                    break
                try:
                    self.get_input()
                except DataPathError:
                    self.logger.info("worker: %s Unable to reconnect!",
                                     self.pipe)
                    self.enabled = False
                    break

                self.parse_blocks()
                self.parse_gps()

                if self.inbuf and self.compat_is_time():
                    if self.compat:
                        self._send_text_block(self.inbuf)
                    else:
                        self.logger.info("worker: %s ### Unconverted data: %s",
                                         self.pipe, self.inbuf)
                    self.inbuf = b""

                try:
                    self.send_frames()
                except DataPathError:
                    self.logger.info("worker: %s Exception while sending frames",
                                     self.pipe, exc_info=True)
                    self.enabled = False
                    break

            if self.was_connected:
                self.logger.info("__worker: %s Waiting for reconnection...",
                                 self.pipe)
                while not self.enabled:
                    # Should be a retry delay parameter
                    time.sleep(5)
                    try:
                        self.logger.debug("__worker: %s "
                                          "Attempting reconnect...", self.pipe)
                        self.pipe.reconnect()
                        self.enabled = True
                        self.auth_connect(authfn)
                    except DataPathNotConnectedError:
                        pass

    def disable(self):
        '''Disable transport.'''
        self.inhandler = None
        self.enabled = False
        self.was_connected = False
        self.shutdown = True
        self.thread.join()

    def send_frame(self, frame):
        '''
        Send Frame

        :param frame: Frame to send.
        :type frame: :class:`DDT2Frame`
        '''
        if not self.enabled:
            self.logger.info("send_frame: %s Refusing to queue block for "
                             "dead transport", self.pipe)
            return
        self.outq.enqueue(frame)

    def recv_frame(self):
        '''
        Receive a frame.

        :returns: Frame from queue
        :rtype: :class:`DDT2Frame`
        '''
        return self.inq.dequeue()

    def flush_blocks(self, ident):
        '''
        Flush blocks

        :param ident: Session id
        :type ident: int
        '''
        # This should really call a flush method in the blockqueue with a
        # test function
        self.outq.lock()
        # pylint: disable=protected-access
        for block in self.outq._queue[:]:
            if block.session == ident:
                self.logger.info("flush_block: %s %s", self.pipe, block)
                try:
                    # pylint: disable=protected-access
                    self.outq._queue.remove(block)
                except ValueError:
                    self.logger.info("flush_block: %s Block disappeared "
                                     "while flushing?", self.pipe)
        self.outq.unlock()

    def __str__(self):
        return str(self.pipe)


class TestPipe():
    '''
    Test Pipe Class.

    :param src: Optional Source station, Default "Sender"
    :type src: str
    :param dst: Optional Destination Station, Default "Recvr"
    :type dst: str
    '''
    def __init__(self, src="Sender", dst="Recvr"):
        self.logger = logging.getLogger("TestPipe")
        self.make_fake_data(src, dst)
        self.buf = None
        self._name = "TestPipe"

    def make_fake_data(self, src, dst):
        '''
        Make Fake Data.

        :param src: Source Station
        :param dst: Dest Station
        '''
        self.buf = b""

        for i in range(10):
            frame = ddt2.DDT2EncodedFrame()
            frame.s_station = src
            frame.d_station = dst
            frame.type = 1
            frame.seq = i
            frame.session = 0
            frame.data = "This is a test frame to parse"

            self.buf += b"asg;sajd;jsadnkbasdl;b  as;jhd[SOB]laskjhd" + \
                b"asdkjh[EOB]a;klsd" + frame.get_packed() + \
                b"asdljhasd[EOB]" + \
                b"asdljb  alsjdljn[asdl;jhas"

            if i == 5:
                self.buf += b"$GPGGA,075519,4531.254,N,12259.400,W" + \
                            b",1,3,0,0.0,M,0,M,,*55\r\nK7HIO   ,GPS Info\r"
            elif i == 7:
                self.buf += b"$$CRC6CD1,Hills-Water-Treat-Plt>" + \
                            b"APRATS,DSTAR*:@233208h4529.05N/12305.91W>" + \
                            b"Washington County ARES;Hills Water Treat Pl\r\n"

            elif i == 2:
                self.buf += b"$GPGGA,023531.36,4531.4940,N,12254.9766" + \
                            b",W,1,07,1.3,63.7,M,-21.4,M,,*64\r\n" + \
                            b"$GPRMC,023531.36,A,4531.4940,N,12254.9766" + \
                            b",W,0.00,113.7,010808,17.4,E,A*27\r" + \
                            b"K7TAY M ,/10-13/\r"

        self.logger.info("make_fake_data: %s", self.buf)

    @staticmethod
    def is_connected():
        '''
        Is Connected?

        :returns: True
        :rtype: bool
        '''
        return True

    def read_all_waiting(self):
        '''
        Read all waiting data.

        :returns: Array of simulated data
        :rtype: bytes
        '''
        if not self.buf:
            return b""

        num = random.randint(1, 200)

        buf = self.buf[:num]
        self.buf = self.buf[num:]

        return buf

    @staticmethod
    def write(_buf):
        '''
        Write - Does nothing

        :param _buf: buffer to write
        :type _buf: bytes
        '''

    def __str__(self):
        return self._name


def test_simple():
    '''Unit test for module'''

    logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
                        level=logging.INFO)
    logger = logging.getLogger("Transport:TestSimple")
    test_pipe = TestPipe()
    transport = Transporter(test_pipe)

    frame = ddt2.DDT2EncodedFrame()
    frame.seq = 9
    frame.type = 8
    frame.session = 7
    frame.d_station = "You"
    frame.s_station = "Me"
    frame.data = "ACK"
    transport.send_frame(frame)

    time.sleep(2)

    frame = transport.recv_frame()
    logger.info("Received block: %s", frame)

    transport.disable()

if __name__ == "__main__":
    test_simple()
