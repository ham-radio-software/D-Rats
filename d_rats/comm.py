'''Comm Module.'''
# pylint want a max of 1000 lines per module.
# pylint: disable=too-many-lines
from __future__ import absolute_import
from __future__ import print_function

import logging
import socket
import time
import struct
import select

# Needed for python2+python3 support
import sys

import serial

from . import utils
from . import agw
from .dratsexception import DataPathIOError
from .dratsexception import DataPathNotConnectedError


ASCII_XON = 17 # chr(17)
ASCII_XOFF = 19 # chr(19)

FEND = 0xC0
FESC = 0xDB
TFEND = 0xDC
TFESC = 0xDD

TNC_DEBUG = False


def kiss_escape_frame(frame):
    '''
    KISS escape frame.

    :param frame: Frame of data
    :type frame: bytes
    :returns: Buffer with frame escaped
    :rtype: bytearray
    '''
    escaped = bytearray()

    for byte in frame:
        if byte == FEND:
            escaped.append(FESC)
            escaped.append(TFEND)
        elif byte == FESC:
            escaped.append(FESC)
            escaped.append(TFESC)
        else:
            escaped.append(byte)

    return escaped


def kiss_send_frame(frame, port=0):
    '''
    KISS Send frame.

    :param frame: Frame to send
    :type frame: bytes
    :param port: Port to send frame from
    :type port: int
    :returns: Buffer to send
    :rtype: bytes
    '''
    cmd = (port & 0x0F) << 4

    frame = kiss_escape_frame(frame)
    buf = struct.pack("BB", FEND, cmd) + frame + struct.pack("B", FEND)

    if TNC_DEBUG:
        logger = logging.getLogger("comm:kiss_send_frame")
        logger.info("[TNC] Sending:")
        utils.hexprintlog(buf)

    return buf


def kiss_buf_has_frame(buf):
    '''
    Kiss Buffer has frame?

    :param buf: Kiss buffer
    :type buf: bytes
    :returns: True if this is a KISS frame
    :rtype: bool
    '''
    return buf.count(FEND) >= 2


# pylint wants only 12 branches per method/function
# pylint: disable=too-many-branches
def kiss_recv_frame(buf):
    '''
    KISS Receive frame.

    :param buf: Raw buffer for frame
    :type buf: bytes
    :returns: Data fame with escapes processed.
    :rtype: tuple of (bytearray, bytearray)
    '''
    data = bytearray()
    out_buf = bytearray()
    if not buf:
        return data, out_buf

    inframe = False

    logger = logging.getLogger("comm:kiss_recv_frame")
    escaped_char = 0
    for byte in buf:
        if byte == FEND:
            if not inframe:
                inframe = True
            else:
                data += out_buf[1:-2]
                # fcs = out_buf[-2:] currently not checking.
                out_buf = b""
                inframe = False
        elif byte == FESC:
            pass # Ignore this and wait for the next character
        elif escaped_char == FESC:
            if byte == TFEND:
                out_buf.append(FEND)
            elif byte == TFESC:
                out_buf.append(FESC)
            else:
                logger.info("[TNC] Bad escape of 0x%x", byte)
                break
        elif inframe:
            out_buf.append(byte)
        else:
            logger.info("[TNC] Out-of-frame garbage: 0x%x", byte)
        escaped_char = byte

    if TNC_DEBUG:
        logger.info("[TNC] Data:")
        utils.hexprintlog(data)

    if not inframe and out_buf:
        # There was not a partial frame started at the end of the data
        logger.info("[TNC] Dumping non-frame data trailer")
        utils.hexprintlog(out_buf)
        out_buf = b""

    return data, out_buf


# Serial port standards require:

# DTR signal must be enabled when an application has the port opened.
# (Except for some printers that do not comply with the standard and
#  use DTR/DSR incorrectly for flow control.)

# The DTR signal enable tells the other device that your application is
# alive, so it data from it is valid.

# The DTR signal must be disabled when no application is using a port.

# RTS signal must be enabled before sending any data.

# python pySerial versions have changed what they set these signals to by
# default, so we can not trust that the defaults meet what the standards
# require.

# For cables that do not not contain the CTS/RTS signals, those signals
# should always be jumpered at the connector if the connector has those pins.

# For cables that do not contain the DSR/DTR signals, those signals should
# always be jumpered at the connector if the connector has those pins.

# if you do not make sure that these are done for compliance with the standard
# you can waste a lot of time trying to find out why things are not working.

# Also note at least one TNC vendor has the wrong wiring on their serial port,
# so it needs a special cable to work when connected to a system that expects
# standard compliant signaling.

# pylint wants only 7 instance attributes
# pylint: disable=too-many-ancestors, too-many-instance-attributes
class TNCSerial(serial.Serial):
    '''
    TNC Serial.

    :param tncport: Optional tnc port number
    :type tncport: str
    :param port: Path to serial port, Default None
    :type port: str
    :param baudrate: Baud rate, Default 9600
    :type baudrate: int
    :param timeout: Read timeout in seconds, Default None
    :type timeout: float
    :param write_timeout: Write timeout in seconds, Default None
    :type write_timeout: float
    :param xonxoff: Use xon/xoff flow control, Default False
    :type xonxoff: bool
    :param rtscts: Use RTS/CTS flow control, default False
    :type rtscts: bool
    :param dsr_control: Use DSR to control connections
    :type dsr_control: bool
    '''

    logger = logging.getLogger("TNCSerial")

    def __init__(self, **kwargs):
        if "tncport" in kwargs:
            self.__tncport = kwargs["tncport"]
            del kwargs["tncport"]
        else:
            self.__tncport = 0
        self.use_dsr = False
        if "dsr_control" in kwargs:
            self.use_dsr = kwargs["dsr_control"]
            del kwargs["dsr_control"]
        self.dsr_seen = False

        serial.Serial.__init__(self, **kwargs)
        self.dtr = True
        self.rts = True

        self.name = "Unknown"
        if "port" in kwargs:
            self.name = kwargs["port"]
        self.__buffer = b""
        # self.__tstamp = 0

    def reconnect(self):
        '''
        Reconnect.

        Does nothing currently.
        '''
        self.dsr_seen = False

    def write(self, data):
        '''
        Write.

        :param data: Data to write
        :type data: bytes
        :raises: :class:`DataPathNotConnectedError` on disconnect.
        '''
        if self.use_dsr and not self.dsr:
            raise DataPathNotConnectedError("Serial port disconnected %s" %
                                            self.name)
        if self.dsr:
            if not self.dsr_seen:
                self.logger.info("Serial port Connection Confirmed %s",
                                 self.name)
            self.dsr_seen = True
        serial.Serial.write(self, kiss_send_frame(data, self.__tncport))

    # parent has size=1
    # pylint: disable=signature-differs
    def read(self, size):
        '''
        Read.

        :param size: Number of bytes to read
        :type size: int
        :returns: Read frame data
        :rtype: bytes
        :raises: :class:`DataPathNotConnectedError` on disconnect
        '''
        if self.use_dsr and not self.dsr:
            raise DataPathNotConnectedError("Serial port disconnected %s" %
                                            self.name)
        if self.dsr:
            if not self.dsr_seen:
                self.logger.info("Serial port Connection Confirmed %s",
                                 self.name)
            self.dsr_seen = True
        read_buffer = serial.Serial.read(self, 1024)
        framedata = b""
        self.__buffer += read_buffer

        if kiss_buf_has_frame(self.__buffer):
            framedata, self.__buffer = kiss_recv_frame(self.__buffer)
        elif self.__buffer:
            self.logger.info("read: [TNC] read_buffer (%i b)",
                             len(read_buffer))
            utils.hexprintlog(read_buffer)
            self.logger.info("read: [TNC] Buffer partially-filled (%i b)",
                             len(self.__buffer))
            utils.hexprintlog(self.__buffer)

        return framedata


class SWFSerial(serial.Serial):
    '''
    SWF Serial.

    :param port: Path to serial port, Default None
    :type port: str
    :param baudrate: Baud rate, Default 9600
    :type baudrate: int
    :param timeout: Read timeout in seconds, Default None
    :type timeout: float
    :param write_timeout: Write timeout in seconds, Default None
    :type write_timeout: float
    :param xonxoff: Use xon/xoff flow control, Default False
    :type xonxoff: bool
    :param rtscts: Use RTS/CTS flow control, default False
    :type rtscts: bool
    :param dsr_control: Use DSR to control connections
    :type dsr_control: bool
    '''

    __swf_debug = False
    logger = logging.getLogger("SWFSerial")

    def __init__(self, **kwargs):
        self.logger.info("Software XON/XOFF control initialized")
        serial.Serial.__init__(self, **kwargs)
        self.dtr = True
        self.rts = True

        self.name = "Unknown"
        if "port" in kwargs:
            self.name = kwargs["port"]
        self.state = True
        self.xoff_limit = 15
        self.use_dsr = False
        if "dsr_control" in kwargs:
            self.use_dsr = kwargs["dsr_control"]
            del kwargs["dsr_control"]
        self.dsr_seen = False

    def reconnect(self):
        '''Reconnect.'''
        self.dtr = False
        self.rts = False
        self.close()
        self.dsr_seen = False
        time.sleep(0.5)
        self.open()
        self.dtr = True
        self.rts = True

    def is_xon(self):
        '''
        Is in xon state?

        :returns: True if data transmissions are allowed
        :rtype: bool
        :raises: :class:`DataPathNotConnectedError` on serial port disconnect
        '''
        if self.use_dsr and not self.dsr:
            raise DataPathNotConnectedError("Serial port disconnected %s" %
                                            self.name)
        if self.dsr:
            if not self.dsr_seen:
                self.logger.info("Serial port Connection Confirmed %s",
                                 self.name)
            self.dsr_seen = True
        time.sleep(0.01)
        if self.in_waiting == 0:
            return self.state
        char = serial.Serial.read(self, 1)
        if char == ASCII_XOFF:
            if self.__swf_debug:
                self.logger.info("is_xon: ************* Got XOFF")
            self.state = False
        elif char == ASCII_XON:
            if self.__swf_debug:
                self.logger.info("is_xon ------------- Got XON")
            self.state = True
        elif len(char) == 1:
            self.logger.info("is_xon: Aiee! Read a non-XOFF char: 0x%02x `%s`",
                             char, char)
            self.state = True
            self.logger.info("is_xon: Assuming IXANY behavior")

        return self.state

    def _write(self, data):
        if self.use_dsr and not self.dsr:
            raise DataPathNotConnectedError("Serial port disconnected %s" %
                                            self.name)
        if self.dsr:
            if not self.dsr_seen:
                self.logger.info("Serial port Connection Confirmed %s",
                                 self.name)
            self.dsr_seen = True
        chunk = 8
        pos = 0
        while pos < len(data):
            if self.__swf_debug:
                self.logger.info("_write: Sending %i-%i of %i",
                                 pos, pos+chunk, len(data))
            serial.Serial.write(self, data[pos:pos+chunk])
            self.flush()
            pos += chunk
            start = time.time()
            while not self.is_xon():
                if self.__swf_debug:
                    self.logger.info("_write: We're XOFF, waiting: %s",
                                     self.state)
                time.sleep(0.01)

                if (time.time() - start) > self.xoff_limit:
                    # self.logger.info(
                    #     "_write: XOFF for too long, breaking loop!")
                    # raise DataPathIOError("Write error (flow)")
                    self.logger.info("_write: XOFF for too long,"
                                     " assuming XON %s", self.name)
                    self.state = True

    def write(self, data):
        '''
        Write.

        :param data: Buffer to write
        :type data: bytes
        '''
        old_to = self.timeout
        self.timeout = 0.01

        self._write(data)

        self.timeout = old_to

    # parent has size=1
    # pylint: disable=signature-differs
    def read(self, size):
        '''
        Read.

        :param size: Number of bytes to read
        :type size: int
        :returns: data read
        :rtype: bytes
        '''
        if self.use_dsr and not self.dsr:
            raise DataPathNotConnectedError("Serial port disconnected %s" %
                                            self.name)
        if self.dsr:
            if not self.dsr_seen:
                self.logger.info("Serial port Connection Confirmed %s",
                                 self.name)
                self.dsr_seen = True
        return serial.Serial.read(self, size)


class DataPath():
    '''
    Data Path.

    :param pathspec: Path to data.
    :type pathspec: str
    :param timeout: Timeout in seconds, default 0.25
    :type timeout: float
    '''

    def __init__(self, pathspec, timeout=0.25):
        self.timeout = timeout
        self.pathspec = pathspec
        self.can_reconnect = True

    # pylint: disable=no-self-use
    def connect(self):
        '''
        Connect.

        :raises: DataPathIOError always
        '''
        raise DataPathNotConnectedError("Can't connect base class")

    # pylint: disable=no-self-use
    def disconnect(self):
        '''
        Disconnect.

        :raises: DataPathIOError always
        '''
        raise DataPathNotConnectedError("Can't disconnect base class")

    # pylint: disable=no-self-use
    def read(self, size):
        '''
        Read.

        :param size: Number of bytes to read
        :type size: int
        :raises: DataPathIOError always
        '''
        raise DataPathIOError("Can't read from base class")

    # pylint: disable=no-self-use
    def write(self, buf):
        '''
        Write.

        :param buf: Buffer to write
        :type buf: str
        :raises: DataPathIOError always
        '''
        raise DataPathIOError("Can't write to base class")

    # pylint: disable=no-self-use
    def flush(self):
        '''
        Flush.

        :raises: DataPathIOError always
        '''
        raise DataPathIOError("Can't flush the base class")

    # pylint: disable=no-self-use
    def is_connected(self):
        '''
        Is connected?

        :returns: False
        :rtype: bool
        '''
        return False

    def __str__(self):
        return "--"


class AGWDataPath(DataPath):
    '''
    AGW Data Path.

    :param pathspec: Path to AGW device
    :type pathspec: str
    :param timeout: Timeout in seconds, default 0
    :type timeout: float
    '''
    logger = logging.getLogger("AGWDataPath")

    def __init__(self, pathspec, timeout=0):
        DataPath.__init__(self, pathspec, timeout)

        _agw, self._addr, self._port = pathspec.split(":")
        self._agw = None

    def connect(self):
        '''
        Connect.

        :raises: DataPathNotConnectedError if can not connect
        '''
        try:
            self._agw = agw.AGWConnection(self._addr, int(self._port),
                                          self.timeout)
            self._agw.enable_raw()
        except (BlockingIOError, socket.error) as err:
            self.logger.info("connect: AGWPE exception on connect: %s", err)
            # pylint: disable=raise-missing-from
            raise DataPathNotConnectedError("Unable to connect to AGWPE")

    def disconnect(self):
        '''Disconnect.'''
        if self._agw:
            self._agw.close()

    def reconnect(self):
        '''Reconnect.'''
        self.disconnect()
        self.connect()

    def read(self, size):
        '''
        Read.

        :param size: Number of bytes to read, Ignored.
        :type size: int
        :returns: data read
        :rtype: bytes
        '''
        return agw.receive_data(self._agw)

    def write(self, buf):
        '''
        Write.

        :param buf: Data to transmit
        :type buf: bytes
        '''
        agw.transmit_data(self._agw, "CQ", ["SRC", "RELAY"], buf)

    def is_connected(self):
        '''
        Is Connected?

        :returns: True if connected
        :rtype: bool
        '''
        return bool(self._agw)

    def __str__(self):
        return "[AGWPE %s:%s]" % (self._addr, self._port)

    def get_agw_connection(self):
        '''
        Get AGW Connection.

        :returns: AGW gateway object
        :rtype: :class:`agw.AGWConnection`
        '''
        return self._agw

    def read_all_waiting(self):
        '''
        Read all waiting.

        :returns: received data
        :rtype: bytes
        '''
        return agw.receive_data(self._agw)


class SerialDataPath(DataPath):
    '''
    Serial Data Path.

    :param pathspec: Path to serial device
    :type pathspec: tuple of (str, int)
    :param timeout: Time out in seconds, default 0.25
    :type timeout: float
    '''
    logger = logging.getLogger("SerialDataPath")

    def __init__(self, pathspec, timeout=0.25):
        DataPath.__init__(self, pathspec, timeout)

        (self.port, self.baud) = pathspec
        self._serial = None

    def connect(self):
        '''
        Connect.

        :raises: DataPathNotConnectedError on connection failure
        '''
        try:
            self._serial = SWFSerial(port=self.port,
                                     baudrate=self.baud,
                                     timeout=self.timeout,
                                     write_timeout=self.timeout,
                                     xonxoff=0)
        except (ValueError, serial.SerialException) as err:
            # pylint: disable=raise-missing-from
            raise DataPathNotConnectedError("Unable to open serial port %s" %
                                            err)
        # pylint: disable=fixme
        # FIXME
        # The serial port needs settings for Monitoring DSR and optionally CD
        # signals.

    def disconnect(self):
        '''
        Disconnect.

        Closes the serial connection
        '''
        if self._serial:
            # Compliant Serial port protocols require that DTS be disabled
            # when the connection is closed.
            # RTS should also be disabled, but should not matter.
            self._serial.dtr = False
            self._serial.rts = False
            self._serial.close()
        self._serial = None

    # pylint: disable=no-self-use
    def reconnect(self):
        '''
        Reconnect.

        Does nothing.
        '''
        return

    def read(self, size):
        '''
        Read.

        :param size: Number of bytes to read
        :type size: int
        :returns: data read
        :rtype: bytes
        :raises: DataPathIOError on read error
        :raises: :class:`DataPathNotConnectedError` on disconnect.
        '''
        if self._serial.use_dsr and not self._serial.dsr:
            raise DataPathNotConnectedError("Serial port disconnected %s" %
                                            self)
        if self._serial.dsr:
            if not self._serial.dsr_seen:
                self.logger.info("Serial port Connection Confirmed %s", self)
            self._serial.dsr_seen = True
        try:
            data = self._serial.read(size)
        except serial.SerialException as err:
            utils.log_exception()
            # pylint: disable=raise-missing-from
            raise DataPathIOError("Failed to read from serial port %s %s" %
                                  (self, err))

        return data

    def read_all_waiting(self):
        '''
        Read All Waiting.

        :returns: Read data
        :rtype: bytes
        '''
        data = self.read(1)
        waiting = self._serial.in_waiting
        if waiting:
            data += self.read(waiting)
        return data

    def write(self, buf):
        '''
        Write.

        :param buf: Buffer to write
        :type buf: bytes
        :raises: DataPathIOError on write failure
        :raises: :class:`DataPathNotConnectedError` on disconnect.
        '''
        if self._serial.use_dsr and not self._serial.dsr:
            raise DataPathNotConnectedError("Serial port disconnected %s" %
                                            self)
        if self._serial.dsr:
            if not self._serial.dsr_seen:
                self.logger.info("Serial port Connection Confirmed %s", self)
            self._serial.dsr_seen = True
        try:
            self._serial.write(buf)
        except (serial.SerialException, serial.SerialTimeoutException) as err:
            utils.log_exception()
            # pylint: disable=raise-missing-from
            raise DataPathIOError("Failed to write to serial port %s %s" %
                                  (self, err))

    def is_connected(self):
        '''
        Is Connected?

        :returns: True if connected
        :rtype: bool
        '''
        return self._serial is not None

    def flush(self):
        '''Flush.'''
        self._serial.flush()

    def __str__(self):
        return "[SERIAL %s@%s]" % (self.port, self.baud)


class TNCDataPath(SerialDataPath):
    '''
    TNC Data Path.

    :param pathspec: Path to serial device
    :type pathspec: tuple of (str, int)
    :param timeout: Time out in seconds, default 0.25
    :type timeout: float
    '''
    logger = logging.getLogger("TNCDataPath")

    def __init__(self, pathspec, timeout=0.25):
        SerialDataPath.__init__(self, pathspec, timeout)

    def connect(self):
        '''
        Connect.

        :raises: :class:`DataPathNotConnectedError` on write error
        '''
        if ":" in self.port:
            self.port, tncport = self.port.split(":", 1)
            tncport = int(tncport)
        else:
            tncport = 0

        self._serial = TNCSerial(port=self.port,
                                 tncport=tncport,
                                 baudrate=self.baud,
                                 timeout=self.timeout,
                                 write_timeout=self.timeout*10,
                                 xonxoff=0)

    def __str__(self):
        return "[TNC %s@%s]" % (self.port, self.baud)


# pylint: disable=fixme
# FIXME: Move this
FCSTAB = [
    0x0000, 0x1189, 0x2312, 0x329b, 0x4624, 0x57ad, 0x6536, 0x74bf,
    0x8c48, 0x9dc1, 0xaf5a, 0xbed3, 0xca6c, 0xdbe5, 0xe97e, 0xf8f7,
    0x1081, 0x0108, 0x3393, 0x221a, 0x56a5, 0x472c, 0x75b7, 0x643e,
    0x9cc9, 0x8d40, 0xbfdb, 0xae52, 0xdaed, 0xcb64, 0xf9ff, 0xe876,
    0x2102, 0x308b, 0x0210, 0x1399, 0x6726, 0x76af, 0x4434, 0x55bd,
    0xad4a, 0xbcc3, 0x8e58, 0x9fd1, 0xeb6e, 0xfae7, 0xc87c, 0xd9f5,
    0x3183, 0x200a, 0x1291, 0x0318, 0x77a7, 0x662e, 0x54b5, 0x453c,
    0xbdcb, 0xac42, 0x9ed9, 0x8f50, 0xfbef, 0xea66, 0xd8fd, 0xc974,
    0x4204, 0x538d, 0x6116, 0x709f, 0x0420, 0x15a9, 0x2732, 0x36bb,
    0xce4c, 0xdfc5, 0xed5e, 0xfcd7, 0x8868, 0x99e1, 0xab7a, 0xbaf3,
    0x5285, 0x430c, 0x7197, 0x601e, 0x14a1, 0x0528, 0x37b3, 0x263a,
    0xdecd, 0xcf44, 0xfddf, 0xec56, 0x98e9, 0x8960, 0xbbfb, 0xaa72,
    0x6306, 0x728f, 0x4014, 0x519d, 0x2522, 0x34ab, 0x0630, 0x17b9,
    0xef4e, 0xfec7, 0xcc5c, 0xddd5, 0xa96a, 0xb8e3, 0x8a78, 0x9bf1,
    0x7387, 0x620e, 0x5095, 0x411c, 0x35a3, 0x242a, 0x16b1, 0x0738,
    0xffcf, 0xee46, 0xdcdd, 0xcd54, 0xb9eb, 0xa862, 0x9af9, 0x8b70,
    0x8408, 0x9581, 0xa71a, 0xb693, 0xc22c, 0xd3a5, 0xe13e, 0xf0b7,
    0x0840, 0x19c9, 0x2b52, 0x3adb, 0x4e64, 0x5fed, 0x6d76, 0x7cff,
    0x9489, 0x8500, 0xb79b, 0xa612, 0xd2ad, 0xc324, 0xf1bf, 0xe036,
    0x18c1, 0x0948, 0x3bd3, 0x2a5a, 0x5ee5, 0x4f6c, 0x7df7, 0x6c7e,
    0xa50a, 0xb483, 0x8618, 0x9791, 0xe32e, 0xf2a7, 0xc03c, 0xd1b5,
    0x2942, 0x38cb, 0x0a50, 0x1bd9, 0x6f66, 0x7eef, 0x4c74, 0x5dfd,
    0xb58b, 0xa402, 0x9699, 0x8710, 0xf3af, 0xe226, 0xd0bd, 0xc134,
    0x39c3, 0x284a, 0x1ad1, 0x0b58, 0x7fe7, 0x6e6e, 0x5cf5, 0x4d7c,
    0xc60c, 0xd785, 0xe51e, 0xf497, 0x8028, 0x91a1, 0xa33a, 0xb2b3,
    0x4a44, 0x5bcd, 0x6956, 0x78df, 0x0c60, 0x1de9, 0x2f72, 0x3efb,
    0xd68d, 0xc704, 0xf59f, 0xe416, 0x90a9, 0x8120, 0xb3bb, 0xa232,
    0x5ac5, 0x4b4c, 0x79d7, 0x685e, 0x1ce1, 0x0d68, 0x3ff3, 0x2e7a,
    0xe70e, 0xf687, 0xc41c, 0xd595, 0xa12a, 0xb0a3, 0x8238, 0x93b1,
    0x6b46, 0x7acf, 0x4854, 0x59dd, 0x2d62, 0x3ceb, 0x0e70, 0x1ff9,
    0xf78f, 0xe606, 0xd49d, 0xc514, 0xb1ab, 0xa022, 0x92b9, 0x8330,
    0x7bc7, 0x6a4e, 0x58d5, 0x495c, 0x3de3, 0x2c6a, 0x1ef1, 0x0f78
    ]


def compute_fcs(data):
    '''
    Compute Frame Check.

    :param data: data for check
    :type data: bytes
    :returns: 16 bit frame check
    :rtype: int
    '''
    fcs = 0xffff

    for byte in data:
        fcs = (fcs >> 8) ^ FCSTAB[(fcs ^ byte) & 0xff]

    return (~fcs) & 0xffff


class TNCAX25DataPath(TNCDataPath):
    '''
    TNC AX25 Data Path.

    :param pathspec: Path to TNC
    :type pathspec: str
    :param timeout: Time out in seconds, default 0.25
    :type timeout: float
    '''
    logger = logging.getLogger("TNCAX25DataPath")

    def __init__(self, pathspec, **kwargs):
        (port, rate, self.__call, self.__path) = pathspec

        self.__buffer = b""
        TNCDataPath.__init__(self, (port, rate), **kwargs)

    def __str__(self):
        return "[TNC-AX25 %s@%s>%s]" % (self.port, self.baud, self.__path)

    def write(self, buf):
        '''
        Write.

        :param buf: Buffer to write
        :type buf: bytes
        '''
        spath = [self.__call,] + self.__path.split(",")
        src = ""
        for scall in spath:
            call, sid = agw.ssid(scall)
            src += "".join([chr(ord(x) << 1) for x in call])
            src += agw.encode_ssid(sid, spath[-1] == scall)

        call, sid = agw.ssid("DRATS")
        dst = "".join([chr(ord(x) << 1) for x in call])
        dst += agw.encode_ssid(sid)
        send_dst = dst.encode('utf-8', 'replace')
        send_src = src.encode('utf-8', 'replace')

        hdr = struct.pack("!7s%isBB" % len(src),
                          send_dst,     # Dest call
                          send_src,     # Source path
                          0x03,         # Control
                          0xF0)         # PID: No layer 3

        fcs = compute_fcs(hdr + buf)
        data = hdr + buf + struct.pack("!H", fcs)

        # self.logger.info("write: Transmitting AX.25 Frame:")
        #utils.hexprintlog(data)
        TNCDataPath.write(self, data)

    def read(self, size):
        '''
        Read.

        :param size: Number of bytes to read
        :type size: int
        :returns: bytes of data read
        :rtype: bytes
        '''
        while len(self.__buffer) < size:
            chunk = TNCDataPath.read(self, 1)
            if not chunk:
                break
            self.__buffer += chunk
        data = self.__buffer[:size]
        self.__buffer = self.__buffer[size:]
        return data


class SocketDataPath(DataPath):
    '''
    Socket Data Path.

    :param pathspec: Communication path
    :type pathspec: tuple of (str, int) or :class:`socket.socket`
    :param timeout: Timeout in seconds, default 0.25
    :type timeout: float
    '''
    logger = logging.getLogger("SocketDataPath")

    def __init__(self, pathspec, timeout=0.25):
        DataPath.__init__(self, pathspec, timeout)
        self._socket = None
        self._name = None
        self._pathspec = pathspec

        if isinstance(pathspec, socket.socket):
            self._socket = pathspec
            self._socket.settimeout(self.timeout)
            self.can_reconnect = False
            self.host = "(incoming)"
            self.port = 0
        elif len(pathspec) == 2:
            (self.host, self.port) = pathspec
            self.call = self.passwd = "UNKNOWN"
            self._name = "%s:%i" % (self.host, self.port)
        else:
            (self.host, self.port, self.call, self.passwd) = pathspec
            self._name = "%s:%i-%s" % (self.host, self.port, self.call)

    def reconnect(self):
        '''Reconnect.'''
        if not self.can_reconnect:
            return
        self.disconnect()
        time.sleep(0.5)
        self.connect()

    def do_auth(self):
        '''Do Authorization.'''

        def readline(sock, timeout=30):
            start_time = time.time()

            line = b""
            while (b"\n" not in line) and \
                    ((time.time() - start_time) < timeout):
                try:
                    data = sock.recv(32)
                    if not data:
                        break
                except socket.timeout:
                    continue

                line += data

            return line.strip()

        def getline(sock, timeout=30):
            '''
            Get a line.

            :param sock: Socket to use
            :type sock: int
            :param timeout: Timeout in seconds, default 30.
            :type timeout: float
            :returns: Tuple of code and line
            :rtype: tuple[int, str]
            :raises: :class:`DataPathNotConnectedError` on write error
            '''
            line = readline(sock, timeout)
            # python3 line is a bytes object
            if isinstance(line, str):
                text_line = line
            else:
                text_line = line.decode('utf-8', 'replace')

            try:
                code, string = text_line.split(" ", 1)
                code = int(code)
            except ValueError:
                self.logger.info("getline: Error parsing line '%s'", line)
                # pylint: disable=raise-missing-from
                raise DataPathNotConnectedError("Conversation error")
            return code, string

        try:
            count, line = getline(self._socket)
        except DataPathNotConnectedError:
            self.logger.info(
                "getline: Assuming an old-school ratflector for now")
            return

        if count == 100:
            self.logger.info("getline: Host does not require authentication")
            return
        if count != 101:
            raise DataPathNotConnectedError("Unknown response code %i" % count)

        self.logger.info("getline: Doing authentication")
        self.logger.info("getline: Sending username: %s", self.call)
        out_data = "USER %s\r\n" % self.call
        self._socket.send(out_data.encode('utf-8', 'replace'))

        count, line = getline(self._socket)
        if count == 200:
            self.logger.info("getline: Host did not require a password")
        elif count != 102:
            raise DataPathNotConnectedError("User rejected username")

        self.logger.info("getline: Sending password: %s",
                         "*" * len(self.passwd))
        out_data = "PASS %s\r\n" % self.passwd
        self._socket.send(out_data.encode('utf-8', 'replace'))

        count, line = getline(self._socket)
        self.logger.info("getline : Host responded: %i %s", count, line)
        if count != 200:
            raise DataPathNotConnectedError("Authentication failed: %s" % line)

    def connect(self):
        '''
        Connect.

        :raises: :class:`DataPathNotConnectedError` on write error
        '''
        try:
            self.logger.info("connection to %s %s", self.host, self.port)
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.connect((self.host, self.port))
            self._socket.settimeout(self.timeout)
            if isinstance(self._pathspec, socket.socket):
                addr, port = self._socket.getpeername()
                self._name = "%s:%i" % (addr, port)

        # On Windows, ConnectionError not based on OSError
        except (ConnectionError, OSError) as err:
            self.logger.debug("Socket failed to connect", exc_info=True)
            self._socket = None
            # pylint: disable=raise-missing-from
            raise DataPathNotConnectedError("Unable to connect (%s)" % err)
        if self.passwd is not None:
            self.do_auth()

    def disconnect(self):
        '''Disconnect Socket.'''
        if self._socket:
            self._socket.close()
        self._socket = None

    def read(self, size):
        '''
        Read.

        :param size: Number of bytes to read
        :type size: int
        :returns: bytes of data read
        :rtype: bytes
        :raises: :class:`DataPathIOError` on write error
        :raises: :class:`DataPathNotConnectedError` on socket disconnect
        '''
        data = b''
        end = time.time() + self.timeout

        if not self._socket:
            raise DataPathNotConnectedError("Socket closed")

        self._socket.setblocking(True)
        self._socket.settimeout(self.timeout)

        while len(data) < size:

            try:
                # x = time.time()
                inp = self._socket.recv(size - len(data))
            except socket.timeout:
                if time.time() > end:
                    break
                continue
            # On Windows, ConnectionError not based on OSError
            except (ConnectionError, OSError) as err:
                self.logger.debug("read: error", exc_info=True)
                # pylint: disable=raise-missing-from
                raise DataPathIOError("Socket error: %s" % err)

            if inp == b'':
                raise DataPathIOError("Socket disconnected")

            end = time.time() + self.timeout
            data += inp

        return data

    def read_all_waiting(self):
        '''
        Read All Waiting.

        :returns: Read data
        :rtype: bytes
        :raises: :class:`DataPathIOError` on write error
        '''
        if not self._socket:
            raise DataPathNotConnectedError("Socket disconnected")

        self._socket.setblocking(False)

        rfds, _wfds, _xfds = select.select([self._socket], [], [], self.timeout)
        if not rfds:
            return b''

        data = b''
        while True:
            try:
                data_read = self._socket.recv(4096)
            # On Windows, ConnectionError not based on OSError
            except (ConnectionError, OSError):
                break
            if not data_read:
                raise DataPathIOError("Socket disconnected")
            data += data_read

        return data

    def write(self, buf):
        '''
        Write.

        :param buf: Buffer to write
        :type buf: bytes
        :raises: :class:`DataPathIOError` on write error
        '''
        ba_buf = buf
        if sys.version_info[0] > 2 and isinstance(buf, str):
            # python3 hack
            ba_buf = buf.encode('utf-8', 'replace')
        try:
            self._socket.sendall(ba_buf)
        except ConnectionResetError:
            # pylint: disable=raise-missing-from
            raise DataPathIOError("Socket write failed - Connection Reset")
        # On Windows, ConnectionError not based on OSError
        except (ConnectionError, OSError) as err:
            self.logger.info("write: Socket write failed %s", err)
            # pylint: disable=raise-missing-from
            raise DataPathIOError("Socket write failed")

    def is_connected(self):
        '''
        Is Connected?

        :returns: True if connected
        :rtype: bool
        '''
        return self._socket is not None

    def flush(self):
        '''
        Flush.

        Place holder method, does nothing.
        '''

    def __str__(self):
        name = ""
        if self._name:
            name = self._name
        try:
            if self._socket:
                _addr, _port = self._socket.getpeername()
                return "[NET %s]" % name
        except (ConnectionError, OSError):
            pass
        return "[NET %s closed]" % name
