'''AX25.'''
# This module was found in d-rats, but is not used by d-rats.

from __future__ import absolute_import
from __future__ import print_function

import logging

BSTR_POS = lambda n: n > 0 and BSTR_POS(n >> 1) + str(n & 1) or ''


class BitStuffContext:
    '''Bit Stuff Context'''

    def __init__(self):
        self.logger = logging.getLogger("BitStuffContext")
        self.outbound = b""
        self.register = 0
        self.bits = 0
        self.ones = 0

    def push(self):
        '''Push.'''
        self.outbound += self.register.to_bytes(1, byteorder="little")
        self.register = self.bits = self.ones = 0

    def _store_bit(self, bit):
        '''
        Store bit internal.

        :param bit: Bit number to store
        :type bit: int
        '''
        self.register <<= 1
        if bit:
            self.register |= 0x01
            self.ones += 1
        else:
            self.ones = 0
        self.logger.info("Register: %s", BSTR_POS(self.register))
        self.bits += 1
        if self.bits == 8:
            self.logger.info("_store_bit: Pushing")
            self.push()

    def store_bit(self, bit):
        '''
        Store bit.

        :param bit: Bit number to store
        :type bit: int
        '''
        if bit and self.ones == 5:
            self.logger.info("store_bit: stuffing")
            self._store_bit(0)
        self._store_bit(bit)

    def get_output(self):
        '''
        Get Output.

        :returns: bit stuffed data
        :rtype: bytes
        '''
        if self.bits:
            for _i in range(self.bits, 8):
                self.store_bit(0)
        return self.outbound


def bitstuff(data):
    '''
    Bit Stuff test routine.

    :param data: Data for testing
    :type data: bytes
    :returns: stuffed data
    :rtype: bytes
    '''
    ctx = BitStuffContext()

    for byte in data:
        for bit in range(0, 8):
            ctx.store_bit(byte & (1 << bit))

    return ctx.get_output()


def main():
    '''Unit Test.'''

    logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
                        datefmt="%m/%d/%Y %H:%M:%S",
                        level=logging.INFO)

    logger = logging.getLogger("Ax25 test")

    from d_rats.utils import hexprintlog

    data = b"\xFF\xFF\xFF"

    logger.info("Start:")
    hexprintlog(data)

    logger.info("Stuffed:")
    hexprintlog(bitstuff(data))

if __name__ == "__main__":
    main()
