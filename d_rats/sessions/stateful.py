#!/usr/bin/python
'''Stateful.'''
#
# Copyright 2009 Dan Smith <dsmith@danplanet.com>
# Python3 update Copyright 2021-2022 John Malmberg <wb8tyw@qsl.net>
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
import struct
import threading
import time

from six.moves import range # type: ignore

from d_rats import transport
from d_rats.ddt2 import DDT2EncodedFrame
from d_rats.sessions import base
from d_rats.utils import hexprintlog


T_SYN = 0
T_ACK = 1
T_NAK = 2
T_DAT = 4
T_REQACK = 5


# pylint: disable=too-many-instance-attributes
class StatefulSession(base.Session):
    '''
    Stateful Session.

    :param name: Name of session
    :param kwargs: Key word arguments
    '''

    stateless = False
    type = base.T_GENERAL

    IDLE_TIMEOUT = 90

    def __init__(self, name, **kwargs):
        base.Session.__init__(self, name)
        self.logger = logging.getLogger("StatefulSession")
        self.outq = transport.BlockQueue()
        self.oob_queue = {}
        self.recv_list = []
        self.outstanding = []
        self.waiting_for_ack = []

        self.enabled = True
        self._closed = False

        self.bsize = kwargs.get("blocksize", 1024)
        self.out_limit = kwargs.get("outlimit", 8)

        self.iseq = -1
        self.oseq = 0

        self.data = transport.BlockQueue()
        self.data_waiting = threading.Condition()

        self.__attempts = 0
        self.__ack_timeout = 0
        self.__full_acks = 0

        self._rtr = 0.0 # Round trip rate (bps)
        self._xmt = 0.0 # Transmit rate (bps)
        self._xms = 0.0 # Start of last transmit of self.outstanding[]

        self._rtt_measure = {
            "bnum"  : -1,
            "start" :  0,
            "end"   :  0,
            "size"  :  0,
            }

        self.time_stamp = None
        self._xme = None
        self.event = threading.Event()
        # is _closed always opposite of enabled?
        self._closed = False
        self.hexdump = False
        self.thread = threading.Thread(target=self.worker)
        self.thread.daemon = True
        self.thread.start()

    def notify_event(self):
        '''Notify Event.'''
        self.event.set()

    def close(self, force=False):
        if self._closed:
            self.logger.info("close: Already closed! - Avoiding recursion.")
            return
        self.logger.info("close: Got close request, joining thread...")
        self._closed = True
        self.enabled = False
        self.notify_event()

        # this should just be "if self.outstanding:"
        # Free up any block listeners
        if isinstance(self.outstanding, list):
            for block in self.outstanding:
                block.sent_event.set()
                block.sent_event.clear()
                block.ackd_event.set()

        else:
            self.logger.info("close: This should be impossible to happen %s",
                             type(self.outstanding))

        self.thread.join()
        self.logger.info("close: Thread is done, continuing with close")

        base.Session.close(self, force)

    # pylint: disable=too-many-branches
    def queue_next(self):
        '''Queue next.'''
        if self.outstanding is None:
            # This is a silly race condition because the worker thread is
            # started in the init, which might run before we set our values
            # after the superclass init
            self.logger.info("queue_next: This should be impossible "
                             "to happen %s",
                             type(self.outstanding))
            return

        limit = self.out_limit
        if self.__full_acks > 0:
            limit += self.__full_acks
        elif self.__full_acks < 0:
            limit -= abs(self.__full_acks)

        # Hard limit of 4KB outstanding (should be per-path!)
        hardlimit = (1 << 12) / self.bsize

        if limit < 2:
            limit = 2
        elif limit > hardlimit:
            limit = int(hardlimit)

        count = limit - len(self.outstanding)
        self.logger.info("queue_next: New limit is %i (%i/%i), queueing %i",
                         limit, self.out_limit, hardlimit, count)
        if count < 0:
            # Need to requeue some blocks to shrink our window
            self.logger.info("queue_next: Need to requeue %i blocks "
                             "to shrink window", abs(count))
            for _i in range(abs(count)):
                self.logger.info("queue_next  : Requeuing block...")
                block = self.outstanding[-1]
                del self.outstanding[-1]
                self.outq.requeue(block)
            return
        if count > 0:
            for _i in range(count):
                block = self.outq.dequeue()
                if block:
                    if block.seq == 0 and self.outstanding:
                        self.logger.info("queue_next : ### Pausing at "
                                         "rollover boundary ###")
                        self.outq.requeue(block)
                        break

                    self.logger.info("queue_next : Queuing %i for send (%i)",
                                     block.seq, count)
                    if self.hexdump:
                        print("Stateful.recv_blocks", type(block.data))
                        hexprintlog(block.data)
                    self.outstanding.append(block)
                else:
                    break

    def is_timeout(self):
        '''
        Is timeout?

        :returns: True if timeout
        '''
        if self._xms == 0:
            return True

        pending_size = 0
        for block in self.outstanding:
            # pylint: disable=protected-access
            pending_size += block._xmit_z

        if pending_size == 0:
            return True

        if self._rtr != 0:
            rate = self._rtr
        else:
            # No measured rate yet so assume the minimum rate
            rate = 80

        timeout = (pending_size / rate) * 1.5
        if timeout < 12:
            # Don't allow small outgoing buffers to fool us into thinking
            # there is no turnaround delay
            timeout = 12

        self.logger.info("is_timeout: ## Timeout for "
                         "%i bytes @ %i bps: %.1f sec",
                         pending_size, rate, timeout)
        self.logger.info("is_timeout : ##  Remaining: %.1f sec",
                         timeout - (time.time() - self._xms))

        if self.__attempts:
            self.logger.info("is_timeout: ## Waiting for ACK, timeout in %i",
                             self.__ack_timeout - time.time())
            return (self.__ack_timeout - time.time()) <= 0
        return (timeout - (time.time() - self._xms)) <= 0

    def send_reqack(self, blocks):
        '''
        Send request Ack.

        :param blocks: List of blocks to ack
        '''
        frame = DDT2EncodedFrame()
        frame.seq = 0
        frame.type = T_REQACK
        # pylint: disable=fixme
        # FIXME: This needs to support 16-bit block numbers!
        # Older clients can not handle 16 bit block numbers!
        frame.data = b"".join([struct.pack("B", x) for x in blocks])

        self.logger.info("send_reqack: Requesting ACK of blocks %s", blocks)
        if self.hexdump:
            print("Stateful.__send_reqack", type(frame.data))
            hexprintlog(frame.data)

        self._sm.outgoing(self, frame)

    # pylint: disable=arguments-differ
    def send_blocks(self):
        '''Send blocks.'''
        if self.outstanding and not self.is_timeout():
            # Not time to try again yet
            return

        self.queue_next()

        if not self.outstanding:
            # nothing to send
            return

        if self.__attempts >= 10:
            self.logger.info("send_blocks: Too many retries, closing...")
            self.set_state(base.ST_CLSD)
            self.enabled = False
            return

        # Short circuit to just an ack for outstanding blocks, if
        # we're still waiting for an ack from remote.  Increase the timeout
        # for the ack by four seconds each time to give some backoff
        if self.waiting_for_ack:
            self.logger.info("send_blocks: Didn't get last ack, asking again")
            self.send_reqack(self.waiting_for_ack)
            if self.__full_acks > 0:
                self.__full_acks = 0
            else:
                self.__full_acks -= 1
            self.__attempts += 1
            self.__ack_timeout = time.time() + 4 + (self.__attempts * 4)
            return

        toack = []

        self._rtt_measure["start"] = time.time()
        self._rtt_measure["end"] = self._rtt_measure["size"] = 0

        self._xms = time.time()

        last_block = None
        for b_block in self.outstanding:
            if b_block.sent_event.is_set():
                self.stats["retries"] += 1
                b_block.sent_event.clear()

            self.logger.info("send_blocks: Sending %i", b_block.seq)
            self._sm.outgoing(self, b_block)
            toack.append(b_block.seq)
            time_stamp = time.time()

            if last_block:
                last_block.sent_event.wait()
                self.update_xmt(last_block)
                self.stats["sent_wire"] += len(last_block.data)

            last_block = b_block

        self.send_reqack(toack)
        self.waiting_for_ack = toack

        self.logger.info("send_blocks: Waiting for block to be sent")
        last_block.sent_event.wait()
        self._xme = time.time()
        self.update_xmt(last_block)
        self.stats["sent_wire"] += len(last_block.data)
        self.time_stamp = time.time()
        self.logger.info("send_blocks: Block sent after: %f",
                         self.time_stamp - time_stamp)

    def send_ack(self, blocks):
        '''
        Send ACK.

        :param blocks: Blocks to ack
        '''
        frame = DDT2EncodedFrame()
        frame.seq = 0
        frame.type = T_ACK
        frame.data = b"".join([struct.pack("B", x) for x in blocks])

        self.logger.info("send_ack: sending ACK for blocks %s (%s)",
                         blocks, {"" : frame.data})

        if self.hexdump:
            print("Stateful.send_ack", type(frame.data))
            hexprintlog(frame.data)
        self._sm.outgoing(self, frame)

    # pylint: disable=too-many-branches, too-many-statements
    def recv_blocks(self):
        '''Receive Blocks.'''
        blocks = self.inq.dequeue_all()
        blocks.reverse()

        def do_next(i_num):
            # pylint: disable=fixme
            # FIXME: For 16 bit blocks
            return (i_num + 1) % 256

        def enqueue(_block):
            if self.hexdump:
                print("Stateful.recv_blocks.enqueue", type(_block.data))
                hexprintlog(_block.data)
            self.data_waiting.acquire()
            self.data.enqueue(_block.data)
            self.iseq = _block.seq
            self.data_waiting.notify()
            self.data_waiting.release()

        for b_block in blocks:
            self._rtt_measure["size"] += len(b_block.get_packed())
            if self.hexdump:
                print("Stateful.recv_blocks", type(b_block.data))
                hexprintlog(b_block.data)
            if b_block.type == T_ACK:
                self.__attempts = 0
                self._rtt_measure["end"] = time.time()
                self.waiting_for_ack = False
                acked = [x for x in b_block.data]
                self.logger.info("recv_blocks: Acked blocks: %s (/%i)",
                                 acked, len(self.outstanding))
                for block in self.outstanding[:]:
                    # pylint: disable=protected-access
                    self._rtt_measure["size"] += block._xmit_z
                    if block.seq in acked:
                        block.ackd_event.set()
                        self.stats["sent_size"] += len(block.data)
                        self.outstanding.remove(block)
                    else:
                        self.logger.info("recv_blocks: Block %i outstanding, "
                                         "No ACK received",
                                         block.seq)
                if self.outstanding:
                    self.logger.info("recv_blocks: This will ACK every block")
                    if self.__full_acks >= 0:
                        self.__full_acks += 1
                    else:
                        self.__full_acks = 0
                else:
                    self.logger.info("recv_blocks: This was not a full ACK")
                    if self.__full_acks > 0:
                        self.__full_acks = 0
                    else:
                        self.__full_acks -= 1
            elif b_block.type == T_DAT:
                self.logger.info("recv_blocks: Got block %i", b_block.seq)
                # pylint: disable=fixme
                # FIXME: For 16-bit blocks
                if b_block.seq == 0 and self.iseq == 255:
                    # Reset received list, because remote will only send
                    # a block 0 following a block 255 if it has received
                    # our ack of the previous 0-255
                    self.recv_list = []

                if b_block.seq not in self.recv_list:
                    self.recv_list.append(b_block.seq)
                    self.stats["recv_size"] += len(b_block.data)
                    self.oob_queue[b_block.seq] = b_block
            elif b_block.type == T_REQACK:
                toack = []

                # pylint: disable=fixme
                # FIXME: This needs to support 16-bit block numbers!
                if self.hexdump:
                    print("Stateful.recv_blocks T_REQACK", type(b_block.data))
                    hexprintlog(b_block.data)
                for i in [x for x in b_block.data]:
                    if self.hexdump:
                        print("recv_blocks: ", type(i), i)
                    if i in self.recv_list:
                        self.logger.info("recv_blocks: Sending ACK "
                                         "for block %i", i)
                        toack.append(i)
                    else:
                        self.logger.info("recv_blocks: Sending NAK "
                                         "for block %i", i)

                self.send_ack(toack)
            else:
                self.logger.info("recv_blocks: Got unknown type: %i",
                                 b_block.type)

        if self.oob_queue:
            self.logger.info("recv_blocks: Waiting OOO blocks: %s",
                             list(self.oob_queue.keys()))
        # Process any OOO blocks, if we should
        while do_next(self.iseq) in list(self.oob_queue.keys()):
            block = self.oob_queue[do_next(self.iseq)]
            self.logger.info("recv_blocks: Queuing now in-order block %i: %s",
                             do_next(self.iseq), block)
            del self.oob_queue[do_next(self.iseq)]
            enqueue(block)

    def update_xmt(self, block):
        '''Update Transmit.'''
        self._xmt = (self._xmt + block.get_xmit_bps()) / 2.0
        self.logger.info("update_xmt: Average transmit rate: %i bps",
                         self._xmt)

    def calculate_rtt(self):
        '''Calculate Round Trip Time.'''
        rtt = self._rtt_measure["end"] - self._rtt_measure["start"]
        size = self._rtt_measure["size"]

        if size > 300:
            # Only calculate the rate if we had a reasonable amount of data
            # queued.  We can't reliably measure small quantities, so we either
            # keep the last-known rate or leave it zero so that is_timeout()
            # will use a worst-case estimation
            self._rtr = size / rtt
            self.logger.info("calculate_rtt: ## rate for session %s: %.1f bps",
                             self._id, self._rtr)
            self.logger.info("calculate_rtt: ##  %i bytes in %.1f sec",
                             size,
                             self._rtt_measure["end"] -
                             self._rtt_measure["start"])

        self._rtt_measure["start"] = self._rtt_measure["end"] = 0
        self._rtt_measure["size"] = 0
        self._rtt_measure["bnum"] = -1

    def worker(self):
        '''Worker.'''
        while self.enabled:
            self.send_blocks()
            self.recv_blocks()

            if self._rtt_measure["end"]:
                self.calculate_rtt()

            if not self.outstanding and self.outq.peek():
                self.logger.info("worker: Short-circuit")
                continue # Short circuit because we have things to send

            self.logger.info("worker: Session loop (%s:%s)",
                             self._id, self.name)

            if self.outstanding:
                self.logger.info("worker: Outstanding data, short sleep")
                self.event.wait(1)
            else:
                self.logger.info("worker: Deep sleep")
                self.event.wait(self.IDLE_TIMEOUT)
                if not self.event.is_set():
                    self.logger.info("worker: Session timed out!")
                    self.set_state(base.ST_CLSD)
                    self.enabled = False
                else:
                    self.logger.info("worker: Awoke from deep "
                                     "sleep to some data")
            self.event.clear()

    # wb8tyw: Since count is always None, what does this do?
    def _block_read_for(self, count):
        waiting = self.data.peek_all()

        if not count and not waiting:
            self.data_waiting.wait(1)
            return

        empty = bytearray()
        all_waiting = empty.join(waiting)
        if count > len(all_waiting):
            self.data_waiting.wait(1)
            return

    def _read(self, count):
        self.data_waiting.acquire()

        if count:
            self.logger.info("_read: ######## Count has a value!!!!")
            self._block_read_for(count)

        if count is None:
            buffer = self.data.dequeue_all()
            # BlockQueue.dequeue_all() returns the blocks in popable order,
            # which is newest first
            buffer.reverse()
            empty = bytearray()
            if self.hexdump:
                for b_block in buffer:
                    print("Stateful._read", type(b_block))
                    hexprintlog(b_block)
            buf = empty.join(buffer)
        else:
            buf = ""
            i = 0
            while True:
                next_data = self.data.peek() or ''
                if next_data and (len(next_data) + i) < count:
                    buf += self.data.dequeue()
                else:
                    break

        self.data_waiting.release()

        return buf

    # pylint: disable=arguments-differ
    def read(self, count=None):
        '''
        Read.

        :param count: Count to read, default=None
        :type count: int
        :returns: Data that was read
        :rtype: bytes
        '''
        # wb8tyw: Not finding any calls of this with count specified.
        while self.get_state() == base.ST_SYNC:
            self.logger.info("read: Waiting for session to open")
            self.wait_for_state_change(5)

        if self.get_state() != base.ST_OPEN:
            raise base.SessionClosedError("State is %i" % self.get_state())

        buf = self._read(count)

        if not buf and self.get_state() != base.ST_OPEN:
            raise base.SessionClosedError()

        return buf

    # pylint: disable=arguments-differ
    def write(self, buf, timeout=0):
        '''
        Write.

        :param buf: Buffer to write
        :param buf: Timeout, default=0
        '''
        while self.get_state() == base.ST_SYNC:
            self.logger.info("write: Waiting for session to open")
            self.wait_for_state_change(5)

        if self.get_state() != base.ST_OPEN:
            raise base.SessionClosedError("State is %s" % self.get_state())

        blocks = []

        while buf:
            chunk = buf[:self.bsize]
            buf = buf[self.bsize:]

            frame = DDT2EncodedFrame()
            frame.seq = self.oseq
            frame.type = T_DAT
            frame.data = chunk
            frame.sent_event.clear()

            self.outq.enqueue(frame)
            blocks.append(frame)

            self.oseq = (self.oseq + 1) % 256
            if self.hexdump:
                print("Stateful.write", type(frame.data))
                hexprintlog(frame.data)

        self.queue_next()
        self.event.set()

        while timeout is not None and \
                blocks and \
                self.get_state() != base.ST_CLSD:
            block = blocks[0]
            del blocks[0]

            self.logger.info("write: Waiting for block %i ACK to be received",
                             block.seq)
            block.sent_event.wait()
            if block.sent_event.is_set():
                self.logger.info("write: Block %i is sent, waiting for ack",
                                 block.seq)
                block.ackd_event.wait(timeout)
                if block.ackd_event.is_set() and block.sent_event.is_set():
                    self.logger.info("write: %i ACK received", block.seq)
                else:
                    self.logger.info("write: %i No ACK received "
                                     "(probably canceled)",
                                     block.seq)
                    break
            else:
                self.logger.info("write: Block %i not sent?", block.seq)
