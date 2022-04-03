'''AGW Sound Card Packet.'''
from __future__ import absolute_import
from __future__ import print_function

import logging
import struct
import sys
import socket
import threading


from . import utils
from .dratsexception import DataPathIOError


class AgwException(DataPathIOError):
    '''Generic AGW Exception.'''


class AgwPayloadLenError(AgwException):
    '''AGW Payload Length Error.'''


class InvalidCallsignError(AgwException):
    '''Invalid Call Sign'''


# pylint: disable=invalid-name
global_logger = logging.getLogger("AGW")


# Number of octets in the AGW Header
AGW_HEADER_SIZE = 36
AGW_HEADER_KIND = 4


# pylint: disable=too-many-instance-attributes
class AGWFrame:
    '''
    AGW Frame.

    Note that AGW frame data is in little-endian format
    instead of network-endian format.
    '''
    # "kind" is documented as a longword.  All examples in the documentation
    # only use the low byte.  Upper 3 bytes are not defined.
    # Old d-rats showed 3rd byte as "pid", which is not
    # mentioned in the agwpe documentation, or referenced
    # inside of d-rats.
    kind = 0

    def __init__(self):
        self.logger = logging.getLogger("AGWFrame")
        self.port = 0
        self.port_pad_word1 = 0
        self.kind_pad_byte1 = 0
        self.kind_pad_byte2 = 0
        self.kind_pad_byte3 = 0
        self.call_from = b"".ljust(10)
        self.call_to = b"".ljust(10)
        self.len = 0
        self.user_pad_longword = 0
        self.payload = b""

    def packed(self):
        '''
        Packed.

        :returns: Packed little-endian data with payload
        :rtype: bytes
        '''
        self.len = len(self.payload)
        packed_data = struct.pack("<HHBBBB10s10sII",
                                  self.port,
                                  self.port_pad_word1,
                                  self.kind,
                                  self.kind_pad_byte1,
                                  self.kind_pad_byte2,
                                  self.kind_pad_byte3,
                                  self.call_from,
                                  self.call_to,
                                  self.len,
                                  self.user_pad_longword)
        return packed_data + self.payload

    def unpack(self, data):
        '''
        Unpack little-endian data into payload.

        :param data: Data for unpacking
        :type data: bytes
        :raises: AgwPayloadError if payload length does not match
        '''
        self.port,\
            self.port_pad_word1, \
            self.kind, \
            self.kind_pad_byte1, \
            self.kind_pad_byte2, \
            self.kind_pad_byte3, \
            self.call_from, \
            self.call_to, \
            self.len, \
            self.user_pad_longword = struct.unpack("<HHBBBB10s10sII",
                                                   data[:AGW_HEADER_SIZE])

        self.payload = data[AGW_HEADER_SIZE:]
        if len(self.payload) != self.len:
            raise AgwPayloadLenError("Expecting payload of %i, got %i" %
                                     (self.len, len(self.payload)))

    def set_payload(self, data):
        '''
        Set payload.

        :param data: Data for sending
        :type data: bytes
        '''
        self.payload = data
        self.len = len(self.payload)

    def get_payload(self):
        '''
        Get payload.

        :returns: Payload
        :rtype: bytes
        '''
        return self.payload

    def set_from(self, call):
        '''
        Set from.

        :param call: Call for from
        :type call: str
        '''
        call_str = call[:9].ljust(9, '\0') + '\0'
        self.call_from = call_str.encode('utf-8', 'replace')

    def get_from(self):
        '''
        Get from.

        :returns: Call from
        :rtype: str
        '''
        return self.call_from.decode('utf-8', 'replace')

    def set_to(self, call):
        '''
        Set to.

        :param call: Call for to
        :type call: str
        '''
        call_str = call[:10].ljust(9, '\0') + '\0'
        self.call_to = call_str.encode('utf-8', 'replace')

    def get_to(self):
        '''
        Get to.

        :returns: Call to send to
        :rtype: str
        '''
        return self.call_to.decode('utf-8', 'replace')

    def __str__(self):
        return "%s -> %s [%s]: %s" % \
            (self.call_from.decode('utf-8', 'replace'),
             self.call_to.decode('utf-8', 'replace'),
             chr(self.kind),
             utils.filter_to_ascii(self.payload))


class AGWFrameKindC(AGWFrame):
    '''Connect Frame.'''
    kind = ord('C')


class AGWFrameKindD(AGWFrame):
    '''Data from connected Station Frame.'''
    kind = ord('D')


class AGWFrameKindd(AGWFrame):
    '''Disconnect Frame.'''
    kind = ord('d')


class AGWFrameKindG(AGWFrame):
    '''Radio Port Frame.'''
    kind = ord('G')


class AGWFrameKindg(AGWFrame):
    '''Radio Port Capabilities Frame.'''
    kind = ord('g')


class AGWFrameKindH(AGWFrame):
    '''Monitor Heard Frame.'''
    kind = ord('H')


class AGWFrameKindK(AGWFrame):
    '''Raw AX25 Frame.'''
    kind = ord('K')


class AGWFrameKindk(AGWFrame):
    '''Toggle enable/disable AX25 Frame.'''
    kind = ord('k')


class AGWFrameKindR(AGWFrame):
    '''Version Number Frame.'''
    kind = ord('R')


class AGWFrameKindS(AGWFrame):
    '''Supervisory Frame.'''
    kind = ord('S')


class AGWFrameKindT(AGWFrame):
    '''Data transmitted Frame.'''
    kind = ord('T')


class AGWFrameKindU(AGWFrame):
    '''UNPROTO Monitor Frame.'''
    kind = ord('U')


class AGWFrameKindX(AGWFrame):
    '''Register Callsign Frame.'''
    kind = ord('X')


class AGWFrameKindx(AGWFrame):
    '''Unregister Callsign Frame.'''
    kind = ord('x')


class AGWFrameKindY(AGWFrame):
    '''How Many Frames Outstanding for a Station Query Frame.'''
    kind = ord('Y')


class AGWFrameKindy(AGWFrame):
    '''How Many Frames Outstanding for a Radio Port Query Frame.'''
    kind = ord('y')


AGW_FRAMES = {
    "C" : AGWFrameKindC, #  67
    "D" : AGWFrameKindD, #  68
    "d" : AGWFrameKindd, # 100
    "G" : AGWFrameKindG,
    "g" : AGWFrameKindg,
    "H" : AGWFrameKindH,
    "K" : AGWFrameKindK, #  75
    "k" : AGWFrameKindk, # 107
    "R" : AGWFrameKindR,
    "S" : AGWFrameKindS,
    "T" : AGWFrameKindT,
    "U" : AGWFrameKindU,
    "X" : AGWFrameKindX, # 120
    "x" : AGWFrameKindx, #  88
    "Y" : AGWFrameKindY, # 121
    "y" : AGWFrameKindy  #  89
}


class AGWConnection:
    '''
    AGW Connection.

    :param addr: AGW address
    :type addr: str
    :param port: AGW port
    :type port: int
    :param timeout: Timeout in seconds, default 0
    :type timeout: float
    :param server: Flag for a test server, default False
    :type server: bool
    '''

    def __init__(self, addr, port, timeout=0, server=False):
        self.logger = logging.getLogger("AGWConnection")
        self.__lock = threading.Lock()

        self._sock1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock = self._sock1
        if timeout:
            self._sock.settimeout(timeout)
        if server:
            self._sock1.bind((addr, port))
        else:
            self._sock.connect((addr, port))
        self._buf = b""
        self._framebuf = {}
        for key in AGW_FRAMES:
            self._framebuf[ord(key)] = []

    def accept_connection(self):
        '''
        Accepts a connection for testing

        :returns: Server socket
        :rtype: int
        '''
        self._sock1.listen()
        conn, addr = self._sock1.accept()
        self.logger.info("test: Connected by %s", addr)
        self._sock = conn
        return self._sock

    @staticmethod
    def _detect_frame(data):
        '''
        Detect Frame.

        :param data: Frame data
        :type data: bytes
        :returns: frame type
        :rtype: subclass of :class:`AGWFrame`
        '''
        kind = chr(data[AGW_HEADER_KIND])
        return AGW_FRAMES[kind]()

    def send_frame(self, frame):
        '''
        Send frame.

        :param frame: Frame to send
        :type frame: :class:`AGWFrame`
        '''
        self._sock.send(frame.packed())

    def recv_block(self, size):
        '''
        Receive a block of data.

        :param size: Size of buffer still needed
        :type size: int
        :returns: True if data received
        :rtype: bool
        '''
        needed = size
        while needed > 0:
            try:
                frame_bytes = self._sock.recv(needed)
            except (ConnectionError, OSError):
                return False

            if not frame_bytes: # Socket closed
                self.close()
                return False
            self._buf += frame_bytes
            needed = size - len(self._buf)
        return True

    def recv_frame(self):
        '''
        Receive Frame.

        :returns: Frame
        :rtype: :class:`AGWFrame`
        '''
        needed = AGW_HEADER_SIZE

        while len(self._buf) < needed:
            if not self.recv_block(needed):
                return None
            frame = self._detect_frame(self._buf)
            try:
                frame.unpack(self._buf)
                self._buf = b""
                return frame
            except AgwPayloadLenError:
                needed = AGW_HEADER_SIZE + frame.len
                continue
            except struct.error:
                self.logger.info("_recv_frame: frame_error", exc_info=True)
                # Need to clear buffer to prevent infinite loop on bad data
                self._buf = b""
                return None

        return None

    def recv_frame_type(self, kind, poll=False):
        '''
        Receive frame type.

        :param kind: Kind of frame
        :type kind: str
        :param poll: Poll for frame, default false
        :type pool: bool
        :returns: Frame with data.
        :rtype: :class:`AGWFrame`
        '''
        while True:
            buffered = self._framebuf.get(ord(kind), [])
            if buffered:
                return buffered.pop()

            self.__lock.acquire()
            frame = self.recv_frame()
            self.__lock.release()
            if frame:
                if chr(frame.kind) != kind:
                    self.logger.info("recv_frame_type: "
                                     "Got %s frame while waiting for %s",
                                     chr(frame.kind), kind)
                self._framebuf[frame.kind].insert(0, frame)
            elif not poll:
                return None

    def close(self):
        '''Close.'''
        self._sock.close()

    def enable_raw(self):
        '''Send raw frame'''
        k_frame = AGWFrameKindk()
        self.send_frame(k_frame)


# pylint: disable=invalid-name
class AGW_AX25_Connection:
    '''
    AGW AX25 Connection.

    :param agw: AGW connection object
    :type: :class:`AGWConnection`
    :param mycall: My callsign
    :type mycall: str
    '''

    def __init__(self, agw, mycall):
        self.logger = logging.getLogger("AGW_AX25_Connection")

        self._agw = agw
        self._mycall = mycall
        self._inbuf = b""

        x_frame = AGWFrameKindX()
        x_frame.set_from(mycall)
        self._agw.send_frame(x_frame)

        _frame = self._agw.recv_frame_type("X", True)

    def connect(self, tocall):
        '''
        Connect.

        :param tocall: Call sign to connect to
        :type to_call: str
        '''
        c_frame = AGWFrameKindC()
        c_frame.set_from(self._mycall)
        c_frame.set_to(tocall)
        self._agw.send_frame(c_frame)

        frame = self._agw.recv_frame_type("C", True)
        self.logger.info("connect: %s", frame.get_payload())

    def disconnect(self):
        '''Disconnect.'''
        d_frame = AGWFrameKindd()
        d_frame.set_from(self._mycall)
        self._agw.send_frame(d_frame)

        frame = self._agw.recv_frame_type("d", True)
        self.logger.info("disconnect: %s", frame.get_payload())

    def send(self, data):
        '''
        Send.

        :param data: Data to send
        :type data: bytes
        '''
        self.logger.info("send: data %s", type(data))
        d_frame = AGWFrameKindD()
        d_frame.set_payload(data)
        self._agw.send_frame(d_frame)

    def recv(self, length=0):
        '''
        Receive.

        :param length: Number of bytes to read, default 0
        :type length: int
        :returns: Buffer of data read
        :rtype: bytes
        '''
        def consume(count):
            buffer = self._inbuf[:count]
            self._inbuf = self._inbuf[count:]
            return buffer

        if length and length < len(self._inbuf):
            return consume(length)

        frame = self._agw.recv_frame_type("D")
        if frame:
            self._inbuf += frame.get_payload()

        if not length:
            return consume(len(self._inbuf))
        return consume(length)

    def recv_text(self):
        '''
        Receive Text.

        :returns: Received Text
        :rtype: str
        '''
        text_bytes = self.recv()
        text_str = text_bytes.decode('utf-8', 'replace')
        text_str = text_str.replace("\r", "\n")
        self.logger.info("recv_text: text %s", type(text_str))
        return text_str


def agw_recv_frame(sock):
    '''
    AGW Recv Frame.

    :param sock: Socket for connection
    :type sock: int
    '''
    data = b""
    while True:
        data += sock.recv(1)
        if len(data) >= AGW_HEADER_SIZE:
            frame = AGWFrameKindK()
            try:
                frame.unpack(data)
                data = b""
            except struct.error:
                global_logger.info("agw_recv_frame: failed unpack",
                                   exc_info=True)
                utils.hexprintlog(data)
                # Need to clear buffer or infinite loop of exceptions
                # on same bad data
                data = b""
                continue
            global_logger.info("agw_recv_frame: "
                               "%s -> %s [%s]",
                               frame.get_from(), frame.get_to(),
                               chr(frame.kind))
            payload = frame.get_payload()
            utils.hexprintlog(frame.get_payload())
            return frame + payload


def test_raw_recv(sock):
    '''
    Test Raw Recv.

    :param sock: Socket for connection
    '''
    frame = AGWFrameKindk()

    sock.send(frame.packed())
    while True:
        agw_recv_frame(sock)


def test_connect(sock):
    '''
    Test Connect.

    :param sock: Socket for test connection.
    '''
    x_frame = AGWFrameKindX()
    x_frame.set_from("KK7DS")
    sock.send(x_frame.packed())
    agw_recv_frame(sock)

    c_frame = AGWFrameKindC()
    c_frame.set_from("KK7DS")
    c_frame.set_to("PSVNOD")
    sock.send(c_frame.packed())
    agw_recv_frame(sock)

    while True:
        agw_recv_frame(sock)


def test_class_connect():
    '''Test Class Connect.'''
    agw = AGWConnection("127.0.0.1", 8000, 0.5)
    axc = AGW_AX25_Connection(agw, "KK7DS")
    axc.connect("N7AAM-11")
    global_logger.info("test_class_connect: %s", axc.recv_text())

    while True:
        global_logger.info("test_class_connect: packet> ")
        line = sys.stdin.readline().strip()
        if line:
            axc.send(line + "\r")
        received = True
        while received:
            received = axc.recv_text()
            global_logger.info("test_class_connect: %s", received)

    axc.disconnect()


def ssid(call):
    '''
    Split call into call sign and ID number

    :param call: Callsign in CCCCCC-N format
    :type call: str
    :returns: Tuple of callsign and ID number
    :rtype: tuple (str, int)
    :raises: InvalidCallsignError on invalid Call Sign
    '''
    if "-" in call:
        callsign, sid = call.split("-", 1)
    else:
        callsign = call
        sid = 0

    if len(callsign) > 6:
        raise InvalidCallsignError("Callsign `%s' is too long" % callsign)

    callsign = callsign.ljust(6)

    try:
        sid = int(sid)
    except ValueError:
        raise InvalidCallsignError("Invalid SSID `%s'" % sid)

    if sid < 0 or sid > 7:
        raise InvalidCallsignError("Invalid SSID `%i'" % sid)

    return callsign, sid


def encode_ssid(sid, last=False):
    '''
    Encode SSID for transmission.

    :param sid: Station ID number
    :type sid: int
    :param last: last flag, unused
    :type last: bool
    :returns: Encoded Station ID character
    :rtype: str
    '''
    if last:
        mask = 0x61
    else:
        mask = 0x60
    return chr((sid << 1) | mask)


def transmit_data(conn, dcall, spath, data):
    '''
    Transmit data.

    :param conn: AGW Connection object
    :type conn: :class:`AGWConnection`
    :param dcall: Destination
    :type dcall: str
    :param spath: List of source and optional digipeaters
    :type spath: list of str
    :param data: Data to transmit
    :type data: bytes
    '''
    global_logger.info("transmit_data:")
    call, sid = ssid(dcall)

    # Encode the call by grabbing each character and shifting
    # left one bit
    dst_str = "".join([chr(ord(x) << 1) for x in call])
    dst_str += encode_ssid(sid)
    dst = dst_str.encode('utf-8', 'replace')

    src_str = ""
    for scall in spath:
        call, sid = ssid(scall)
        src_str += "".join([chr(ord(x) << 1) for x in call])
        src_str += encode_ssid(sid, spath[-1] == scall)
        src = src_str.encode('utf-8', 'replace')

    data_frame = struct.pack("!B7s%isBB" % len(src),
                             0x00,    # Space for flag (?)
                             dst,     # Dest Call
                             src,     # Source Path
                             0x3E,    # Info
                             0xF0)    # PID: No layer 3
    data_frame += data

    utils.hexprintlog(data_frame)

    frame = AGWFrameKindK()
    frame.set_payload(data_frame)
    conn.send_frame(frame)


def receive_data(conn, blocking=False):
    '''
    Receive Data.

    :param conn: Connection object
    :type conn: :class:`AGWConnection`
    :param blocking: Block for data read, default False
    :type blocking: bool
    :returns: Received data
    :rtype: bytes
    '''
    frame = conn.recv_frame_type("K", blocking)
    if frame:
        return frame.get_payload()
    return b""


def test(conn):
    '''
    Test function.

    :param conn: AGW connection
    :type conn: :class:`AGWConnection`
    '''
    frame = AGWFrameKindK()

    conn.send_frame(frame)


def test_server(host="127.0.0.1", port=8000):
    '''
    Test Server.

    :param host: host address to listen on, default '127.0.0.1'
    :type host: str
    :param port: Port to listen on, default 80000
    :type port: int
    '''
    # Quick and dirty simulator for agwpe unit tests.
    global_logger.info("test_server: starting %s:%i", host, port)
    from time import sleep

    agw = AGWConnection(host, port, timeout=10, server=True)
    _conn = agw.accept_connection()
    count = 0
    while count < 5:
        try:
            frame = agw.recv_frame()
            if not frame:
                count += 1
                global_logger.info("test_server: no frame")
                sleep(1)
                continue
            global_logger.info("test_server: Received %s", frame)
            agw.send_frame(frame)
        except (ConnectionError, OSError):
            global_logger.info("test_server: failed", exc_info=True)


def main():
    '''Unit Test.'''

    # You may need to edit this based on if you actually have an agwpe
    # driver installed, or the port is in use.
    logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
                        datefmt="%m/%d/%Y %H:%M:%S",
                        level=logging.INFO)

    from time import sleep
    server = threading.Thread(target=test_server)
    server.start()
    sleep(2)
    # sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # sock.connect(("127.0.0.1", 8000))
    # test_raw_recv(sock)
    # test_connect(sock)

    agw = AGWConnection("127.0.0.1", 8000, 0.5)
    sleep(10)
    agw.enable_raw()
    payload = agw.recv_frame_type("k", False)

    #test_class_connect()
    #test_ui()
    transmit_data(agw, "CQ", ["KK7DS", "KK7DS-3"], b"foo")
    sleep(2)
    payload = None
    count = 0
    while count < 20:
        payload = agw.recv_frame_type("K", False)
        global_logger.info("Unit Test: Received %s", payload)
        if payload:
            break
        count += 1

if __name__ == "__main__":
    main()
