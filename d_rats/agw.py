'''AGW'''
from __future__ import absolute_import
from __future__ import print_function

import struct
import sys
import socket
import threading


from . import utils
# importing printlog() wrapper
from .debug import printlog


class AgwException(Exception):
    '''Generic AGW Exception.'''


class AgwPayloadLenError(AgwException):
    '''AGW Payload Length Error.'''


class InvalidCallsignError(AgwException):
    '''Invalid Call Sign'''


# pylint: disable=too-many-instance-attributes
class AGWFrame:
    '''AGW Frame.'''
    kind = 0

    def __init__(self):
        self.port = 0
        self.res1 = self.res2 = self.res3 = 0
        self.res4 = self.res5 = self.res6 = 0
        self.pid = 0
        self.call_from = "".ljust(10)
        self.call_to = "".ljust(10)
        self.len = 0
        self.payload = ""

    def packed(self):
        '''
        Packed.

        :returns: Packed data with payload
        '''
        packed_data = struct.pack("BBBBBBBB10s10sII",
                                  self.port,
                                  self.res1, self.res2, self.res3,
                                  self.kind,
                                  self.res4,
                                  self.pid,
                                  self.res5,
                                  self.call_from, self.call_to,
                                  self.len,
                                  self.res6)

        return packed_data + self.payload

    def unpack(self, data):
        '''
        Unpack into payload.

        :param data: Data for unpacking
        :raises: AgwPayloadError if payload length does not match
        '''
        self.port,\
            self.res1, self.res2, self.res3, \
            self.kind, \
            self.res4, \
            self.pid, \
            self.res5, \
            self.call_from, self.call_to, \
            self.len, \
            self.res6 = struct.unpack("BBBBBBBB10s10sII", data[:36])

        self.payload = data[36:]
        if len(self.payload) != self.len:
            raise AgwPayloadLenError("Expecting payload of %i, got %i" % \
                                    (self.len, len(self.payload)))

    def set_payload(self, data):
        '''
        Set payload.

        :param data: Data for sending
        '''
        self.payload = data
        self.len = len(self.payload)

    def get_payload(self):
        '''
        Get payload.

        :returns: Payload
        '''
        return self.payload

    def set_from(self, call):
        '''
        Set from.

        :param call: Call for from
        '''
        self.call_from = call[:9].ljust(9, '\0') + '\0'

    def get_from(self):
        '''
        Get from.

        :returns: Call from
        '''
        return self.call_from

    def set_to(self, call):
        '''
        Set to.

        :param call: Call for to
        '''
        self.call_to = call[:10].ljust(9, '\0') + '\0'

    def get_to(self):
        '''
        Get to.

        :returns: Call to send to
        '''
        return self.call_to

    def __str__(self):
        return "%s -> %s [%s]: %s" % (self.call_from, self.call_to,
                                      chr(self.kind),
                                      utils.filter_to_ascii(self.payload))


# pylint: disable=invalid-name
class AGWFrame_k(AGWFrame):
    '''AGW Frame k.'''
    kind = ord("k")


# pylint: disable=invalid-name
class AGWFrame_K(AGWFrame):
    '''AGW Frame K.'''
    kind = ord('K')


# pylint: disable=invalid-name
class AGWFrame_C(AGWFrame):
    '''AGW Frame C.'''
    kind = ord('C')


# pylint: disable=invalid-name
class AGWFrame_d(AGWFrame):
    '''AGW Frame d.'''
    kind = ord('d')


# pylint: disable=invalid-name
class AGWFrame_D(AGWFrame):
    '''AGW Frame D.'''
    kind = ord('D')


# pylint: disable=invalid-name
class AGWFrame_X(AGWFrame):
    '''AGW Frame X.'''
    kind = ord('X')


# pylint: disable=invalid-name
class AGWFrame_x(AGWFrame):
    '''AGW Frame x.'''
    kind = ord('x')


AGW_FRAMES = {
    "k" : AGWFrame_k,
    "K" : AGWFrame_K,
    "C" : AGWFrame_C,
    "d" : AGWFrame_d,
    "D" : AGWFrame_D,
    "X" : AGWFrame_X,
    "x" : AGWFrame_x,
}


class AGWConnection:
    '''
    AGW Connection.

    :param addr: AGW address
    :param port: AGW port
    :param timeout: Timeout in seconds, default 0
    '''

    def __init__(self, addr, port, timeout=0):
        self.__lock = threading.Lock()

        self._s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if timeout:
            self._s.settimeout(timeout)
        self._s.connect((addr, port))
        self._buf = ""
        self._framebuf = {}
        for key in AGW_FRAMES:
            self._framebuf[ord(key)] = []

    # pylint: disable=no-self-use
    def _detect_frame(self, data):
        kind = data[4]
        return AGW_FRAMES[kind]()

    def send_frame(self, frame):
        '''
        Send frame.

        :param frame: Frame to send
        '''
        self._s.send(frame.packed())

    def __recv_frame(self):
        try:
            frame_bytes = self._s.recv(1)
        except socket.timeout:
            return None

        if not frame_bytes: # Socket closed
            self.close()

        self._buf += frame_bytes
        if len(self._buf) >= 36:
            frame = self._detect_frame(self._buf)
            try:
                frame.unpack(self._buf)
                self._buf = ""
            # pylint: disable=broad-except
            except Exception as err:
                printlog("Agw",
                         "       : AGWConnection/__recv_frame error (%s)" %
                         err)
                return None
            return frame

        return None

    def recv_frame_type(self, kind, poll=False):
        '''
        Receive frame type.

        :param kind: Kind of frame
        :param poll: Poll for frame, default false
        :returns: Frame data or None.
        '''
        while True:
            buffered = self._framebuf.get(ord(kind), [])
            if buffered:
                return buffered.pop()

            self.__lock.acquire()
            frame = self.__recv_frame()
            self.__lock.release()
            if frame:
                printlog("Agw",
                         "       : Got %s frame while waiting for %s" %
                         (chr(frame.kind), kind))
                self._framebuf[frame.kind].insert(0, frame)
            elif not poll:
                return None
        return None

    def close(self):
        '''Close.'''
        self._s.close()

    def enable_raw(self):
        '''Enable raw.'''
        k_frame = AGWFrame_k()
        self.send_frame(k_frame)


# pylint: disable=invalid-name
class AGW_AX25_Connection:
    '''
    AGW AX25 Connection.

    :param agw: AGW object
    :param mycall: My callsign
    '''

    def __init__(self, agw, mycall):
        self._agw = agw
        self._mycall = mycall
        self._inbuf = ""

        x_frame = AGWFrame_X()
        x_frame.set_from(mycall)
        self._agw.send_frame(x_frame)

        _frame = self._agw.recv_frame_type("X", True)

    def connect(self, tocall):
        '''
        Connect.

        :param tocall: Call sign to connect to
        '''
        c_frame = AGWFrame_C()
        c_frame.set_from(self._mycall)
        c_frame.set_to(tocall)
        self._agw.send_frame(c_frame)

        frame = self._agw.recv_frame_type("C", True)
        printlog("Agw", "       : %s" % frame.get_payload())

    def disconnect(self):
        '''Disconnect.'''
        d_frame = AGWFrame_d()
        d_frame.set_from(self._mycall)
        self._agw.send_frame(d_frame)

        frame = self._agw.recv_frame_type("d", True)
        printlog("Agw", "       : %s" % frame.get_payload())

    def send(self, data):
        '''
        Send.

        :param data: Data to send
        '''
        d_frame = AGWFrame_D()
        d_frame.set_payload(data)
        self._agw.send_frame(d_frame)

    def recv(self, length=0):
        '''
        Receive.

        :param length: Number of bytes to read, default 0
        :returns: Buffer of data read
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
        '''
        return self.recv().replace("\r", "\n")


def agw_recv_frame(sock):
    '''
    AGW Recv Frame.

    :param sock: Socket for connection
    '''
    data = ""
    while True:
        data += sock.recv(1)
        if len(data) >= 36:
            frame = AGWFrame_K()
            try:
                frame.unpack(data)
                data = ""
            # pylint: disable=broad-except
            except Exception as err:
                printlog("Agw",
                         "      : agw_recv_frame failed unpack %s" % err)
                continue
            printlog("Agw",
                     "      : %s -> %s [%s]" %
                     (frame.get_from(), frame.get_to(), chr(frame.kind)))
            utils.hexprintlog(frame.get_payload())


def test_raw_recv(sock):
    '''
    Test Raw Recv.

    :param sock: Socket for connection
    '''
    frame = AGWFrame_k()

    sock.send(frame.packed())
    while True:
        agw_recv_frame(sock)


def test_connect(sock):
    '''
    Test Connect.

    :param sock: Socket for test connection.
    '''
    x_frame = AGWFrame_X()
    x_frame.set_from("KK7DS")
    sock.send(x_frame.packed())
    agw_recv_frame(sock)

    c_frame = AGWFrame_C()
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
    printlog("Agw", "      : %s" % axc.recv_text())

    while True:
        printlog("Agw", "       : packet> ")
        line = sys.stdin.readline().strip()
        if line:
            axc.send(line + "\r")
        received = True
        while received:
            received = axc.recv_text()
            printlog("Agw", "      : %s" % received)

    axc.disconnect()


def ssid(call):
    '''
    Split call into call sign and ID number

    :param call: Callsign in CCCCCC-N format
    :returns: Tuple of callsign and ID number
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
    :returns: Encoded Station ID
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
    :param dcall: Destination
    :param spath: List of source and optional digi-peaters
    :param data: Data to transmit
    '''
    call, sid = ssid(dcall)

    # Encode the call by grabbing each character and shifting
    # left one bit
    dst = "".join([chr(ord(x) << 1) for x in call])
    dst += encode_ssid(sid)

    src = ""
    for scall in spath:
        call, sid = ssid(scall)
        src += "".join([chr(ord(x) << 1) for x in call])
        src += encode_ssid(sid, spath[-1] == scall)

    data_frame = struct.pack("B7s%isBB" % len(src),
                             0x00,    # Space for flag (?)
                             dst,     # Dest Call
                             src,     # Source Path
                             0x3E,    # Info
                             0xF0)    # PID: No layer 3
    data_frame += data

    utils.hexprintlog(data_frame)

    frame = AGWFrame_K()
    frame.set_payload(data_frame)
    conn.send_frame(frame)


def receive_data(conn, blocking=False):
    '''
    Receive Data.

    :param conn: Connection object
    :param blocking: Block for data read, default False
    :returns: Received data
    '''
    frame = conn.recv_frame_type("K", blocking)
    if frame:
        return frame.get_payload()
    return ""


def test(conn):
    '''
    Test function.

    :param conn:  AGW connection
    '''
    frame = AGWFrame_K()

    conn.send_frame(frame)


def main():
    '''Unit Test.'''
    #s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #s.connect(("127.0.0.1", 8000))
    #test_raw_recv(s)
    #test_connect(s)

    agw = AGWConnection("127.0.0.1", 8000, 0.5)
    agw.enable_raw()

    #test_class_connect()
    #test_ui()
    transmit_data(agw, "CQ", ["KK7DS", "KK7DS-3"], "foo")

if __name__ == "__main__":
    main()
