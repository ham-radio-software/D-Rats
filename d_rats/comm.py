from __future__ import absolute_import
from __future__ import print_function
#importing printlog() wrapper
from .debug import printlog

import serial
import socket
import time
import struct
import select

from . import utils
from . import agw

class DataPathError(Exception):
    pass

class DataPathNotConnectedError(DataPathError):
    pass

class DataPathIOError(DataPathError):
    pass

ASCII_XON = chr(17)
ASCII_XOFF = chr(19)

FEND  = 0xC0
FESC  = 0xDB
TFEND = 0xDC
TFESC = 0xDD

TNC_DEBUG = True

def kiss_escape_frame(frame):
    escaped = ""

    for char in frame:
        if ord(char) == FEND:
            escaped += chr(FESC)
            escaped += chr(TFEND)
        elif ord(char) == FESC:
            escaped += chr(FESC)
            escaped += chr(TFESC)
        else:
            escaped += char

    return escaped

def kiss_send_frame(frame, port=0):
    cmd = (port & 0x0F) << 4

    frame = kiss_escape_frame(frame)
    buf = struct.pack("BB", FEND, cmd) + frame + struct.pack("B", FEND)

    if TNC_DEBUG:
        printlog("Comm","        : [TNC] Sending:")
        utils.hexprintlog(buf)

    return buf

def kiss_buf_has_frame(buf):
    return buf.count(chr(FEND)) >=2

def kiss_recv_frame(buf):
    if not buf:
        return "", ""

    data = ""
    inframe = False

    _buf = ""
    _lst = "0" # Make sure we don't choke trying to ord() this
    for char in buf:
        if ord(char) == FEND:
            if not inframe:
                inframe = True
            else:
                data += _buf[1:]
                _buf = ""
                inframe = False
        elif ord(char) == FESC:
            pass # Ignore this and wait for the next character
        elif ord(_lst) == FESC:
            if ord(char) == TFEND:
                _buf += chr(FEND)
            elif ord(char) == TFESC:
                _buf += chr(FESC)
            else:
                printlog("Comm","        : [TNC] Bad escape of 0x%x" % ord(char))
                break
        elif inframe:
            _buf += char
        else:
            printlog("Comm","        : [TNC] Out-of-frame garbage: 0x%x" % ord(char))
        _lst = char

    if TNC_DEBUG:
        printlog("Comm","        : [TNC] Data:")
        utils.hexprintlog(data)

    if not inframe and _buf:
        # There was not a partial frame started at the end of the data
        printlog("Comm","        : [TNC] Dumping non-frame data trailer")
        utils.hexprintlog(_buf)
        _buf = ""

    return data, _buf

class TNCSerial(serial.Serial):
    def __init__(self, **kwargs):
        if "tncport" in list(kwargs.keys()):
            self.__tncport = kwargs["tncport"]
            del kwargs["tncport"]
        else:
            self.__tncport = 0
        serial.Serial.__init__(self, **kwargs)

        self.__buffer = ""
        self.__tstamp = 0

    def reconnect(self):
        pass

    def write(self, data):
        serial.Serial.write(self, kiss_send_frame(data, self.__tncport))

    def read(self, size):
        if self.__buffer:
            printlog("Comm","        : Buffer is %i before read" % len(self.__buffer))
        self.__buffer += serial.Serial.read(self, 1024)

        framedata = ""
        if kiss_buf_has_frame(self.__buffer):
            framedata, self.__buffer = kiss_recv_frame(self.__buffer)
        elif len(self.__buffer) > 0:
            printlog("Comm","     : [TNC] Buffer partially-filled (%i b)" % len(self.__buffer))

        return framedata


class SWFSerial(serial.Serial):
    __swf_debug = False

    def __init__(self, **kwargs):
        printlog("Comm","        : Software XON/XOFF control initialized")
        try:
            serial.Serial.__init__(self, **kwargs)
        except TypeError as e:
            if "writeTimeout" in kwargs:
                del kwargs["writeTimeout"]
                serial.Serial.__init__(self, **kwargs)
            else:
                printlog("Comm      : Unknown TypeError from Serial.__init__: %s" % e)
                raise e

        self.state = True
        self.xoff_limit = 15

    def reconnect(self):
        self.close()
        time.sleep(0.5)
        self.open()

    def is_xon(self):
        time.sleep(0.01)
        if serial.Serial.inWaiting(self) == 0:
            return self.state
        char = serial.Serial.read(self, 1)
        if char == ASCII_XOFF:
            if self.__swf_debug:
                printlog("Comm      : ************* Got XOFF")
            self.state = False
        elif char == ASCII_XON:
            if self.__swf_debug:
                printlog("Comm","        : ------------- Got XON")
            self.state = True
        elif len(char) == 1:
            printlog("Comm","        : Aiee! Read a non-XOFF char: 0x%02x `%s`" % (ord(char), char))
            self.state = True
            printlog("Comm","        : Assuming IXANY behavior")

        return self.state

    def _write(self, data):
        chunk = 8
        pos = 0
        while pos < len(data):
            if self.__swf_debug:
                printlog("Comm","        : Sending %i-%i of %i" % (pos, pos+chunk, len(data)))
            serial.Serial.write(self, data[pos:pos+chunk])
            self.flush()
            pos += chunk
            start = time.time()
            while not self.is_xon():
                if self.__swf_debug:
                    printlog(("Comm      : We're XOFF, waiting: %s" % self.state))
                time.sleep(0.01)
                
                if (time.time() - start) > self.xoff_limit:
                    #printlog("XOFF for too long, breaking loop!")
                    #raise DataPathIOError("Write error (flow)")
                    printlog("Comm","        : XOFF for too long, assuming XON")
                    self.state = True

    def write(self, data):
        old_to = self.timeout
        self.timeout = 0.01

        self._write(data)

        self.timeout = old_to

    def read(self, len):
        return serial.Serial.read(self, len)


class DataPath(object):
    def __init__(self, pathspec, timeout=0.25):
        self.timeout = timeout
        self.pathspec = pathspec
        self.can_reconnect = True

    def connect(self):
        raise DataPathNotConnectedError("Can't connect base class")

    def disconnect(self):
        raise DataPathNotConnectedError("Can't disconnect base class")

    def read(self, count):
        raise DataPathIOError("Can't read from base class")

    def write(self, buf):
        raise DataPathIOError("Can't write to base class")

    def flush(self, buf):
        raise DataPathIOError("Can't flush the base class")

    def is_connected(self):
        return False

    def __str__(self):
        return "--"

class AGWDataPath(DataPath):
    def __init__(self, pathspec, timeout=0):
        DataPath.__init__(self, pathspec, timeout)

        _agw, self._addr, self._port = pathspec.split(":")
        self._agw = None

    def connect(self):
        try:
            self._agw = agw.AGWConnection(self._addr, int(self._port), self.timeout)
            self._agw.enable_raw()
        except Exception as e:
            printlog("Comm","        : AGWPE exception on connect: %s" % e)
            raise DataPathNotConnectedError("Unable to connect to AGWPE")

    def disconnect(self):
        if self._agw:
            self._agw.close()

    def reconnect(self):
        self.disconnect()
        self.connect()

    def read(self, count):
        return agw.receive_data(self._agw)

    def write(self, buf):
        agw.transmit_data(self._agw, "CQ", ["SRC", "RELAY"], buf)

    def is_connected(self):
        return bool(self._agw)

    def __str__(self):
        return "[AGWPE %s:%s]" % (self._addr, self._port)

    def get_agw_connection(self):
        return self._agw

    def read_all_waiting(self):
        return agw.receive_data(self._agw)

class SerialDataPath(DataPath):
    def __init__(self, pathspec, timeout=0.25):
        DataPath.__init__(self, pathspec, timeout)

        (self.port, self.baud) = pathspec
        self._serial = None

    def connect(self):
        try:
            self._serial = SWFSerial(port=self.port,
                                     baudrate=self.baud,
                                     timeout=self.timeout,
                                     writeTimeout=self.timeout,
                                     xonxoff=0)
        except Exception as e:
            printlog("Comm","        : Serial exception on connect: %s" % e)
            raise DataPathNotConnectedError("Unable to open serial port")

    def disconnect(self):
        if self._serial:
            self._serial.close()
        self._serial = None

    def reconnect(self):
        return

    def read(self, count):
        try:
            data = self._serial.read(count)
        except Exception as e:
            printlog("Comm","        : Serial read exception: %s" % e)
            utils.log_exception()
            raise DataPathIOError("Failed to read from serial port")

        return data

    def read_all_waiting(self):
        data = self.read(1)
        data += self.read(self._serial.inWaiting())
        return data

    def write(self, buf):
        try:
            self._serial.write(buf)
        except Exception as e:
            printlog("Comm","        : Serial write exception: %s" % e)
            utils.log_exception()
            raise DataPathIOError("Failed to write to serial port")

    def is_connected(self):
        return self._serial != None

    def flush(self):
        self._serial.flush()

    def __str__(self):
        return "[SERIAL %s@%s]" % (self.port, self.baud)

class TNCDataPath(SerialDataPath):
    def connect(self):
        if ":" in self.port:
            self.port, tncport = self.port.split(":", 1)
            tncport = int(tncport)
        else:
            tncport = 0

        try:
            self._serial = TNCSerial(port=self.port,
                                     tncport=tncport,
                                     baudrate=self.baud,
                                     timeout=self.timeout,
                                     writeTimeout=self.timeout*10,
                                     xonxoff=0)
        except Exception as e:
            printlog(("Comm      : TNC exception on connect: %s" % e))
            utils.log_exception()
            raise DataPathNotConnectedError("Unable to open serial port")

    def __str__(self):
        return "[TNC %s@%s]" % (self.port, self.baud)

# FIXME: Move this
fcstab = [
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
    fcs = 0xffff

    for byte in data:
        fcs = (fcs >> 8 ) ^ fcstab[(fcs ^ ord(byte)) & 0xff]
    
    return (~fcs) & 0xffff

class TNCAX25DataPath(TNCDataPath):
    def __init__(self, pathspec, **kwargs):
        (port, rate, self.__call, self.__path) = pathspec

        self.__buffer = ""
        TNCDataPath.__init__(self, (port, rate), **kwargs)

    def __str__(self):
        return "[TNC-AX25 %s@%s>%s]" % (self.port, self.baud, self.__path)

    def write(self, buf):
        spath = [self.__call,] + self.__path.split(",")
        src = ""
        for scall in spath:
            c, s = agw.ssid(scall)
            src += "".join([chr(ord(x) << 1) for x in c])
            src += agw.encode_ssid(s, spath[-1] == scall)
        

        c, s = agw.ssid("DRATS")
        dst = "".join([chr(ord(x) << 1) for x in c])
        dst += agw.encode_ssid(s)

        hdr = struct.pack("7s%isBB" % len(src),
                          dst,     # Dest call
                          src,     # Source path
                          0x03,    # Control
                          0xF0)    # PID: No layer 3

        fcs = compute_fcs(hdr + buf)
        data = hdr + buf + struct.pack(">H", fcs)

        #printlog("Transmitting AX.25 Frame:")
        #utils.hexprintlog(data)
        TNCDataPath.write(self, data)

    def read(self, count):
        while len(self.__buffer) < count:
            chunk = TNCDataPath.read(self, 1)
            if not chunk:
                break
            self.__buffer += chunk
            
        data = self.__buffer[:count]
        self.__buffer = self.__buffer[count:]
        return data

class SocketDataPath(DataPath):
    def __init__(self, pathspec, timeout=0.25):
        DataPath.__init__(self, pathspec, timeout)

        self._socket = None

        if isinstance(pathspec, socket.socket):
            self._socket = pathspec
            self._socket.settimeout(self.timeout)
            self.can_reconnect = False
            self.host = "(incoming)"
            self.port = 0
        elif len(pathspec) == 2:
            (self.host, self.port) = pathspec
            self.call = self.passwd = "UNKNOWN"
        else:
            (self.host, self.port, self.call, self.passwd) = pathspec

    def reconnect(self):
        if not self.can_reconnect:
            return
        self.disconnect()
        time.sleep(0.5)
        self.connect()

    def do_auth(self):
        def readline(_s, to=30):
            t = time.time()

            line = ""
            while ("\n" not in line) and ((time.time() - t) < to):
                try:
                    _d = _s.recv(32)
                    if not _d:
                        break
                except socket.timeout:
                    continue

                line += _d
                
            return line.strip()

        def getline(_s, to=30):
            line = readline(_s, to)

            try:
                code, string = line.split(" ", 1)
                code = int(code)
            except Exception as e:
                printlog("Comm","        : Error parsing line '%s': %s" %
                         (line, e))
                raise DataPathNotConnectedError("Conversation error")

            return code, string

        try:
            c, l = getline(self._socket)
        except DataPathNotConnectedError:
            printlog("Comm","        : Assuming an old-school ratflector for now")
            return

        if c == 100:
            printlog("Comm","      : Host does not require authentication")
            return
        elif c != 101:
            raise DataPathNotConnectedError("Unknown response code %i" % c)

        printlog("Comm","      : Doing authentication")
        printlog("Comm","      : Sending username: %s" % self.call)
        self._socket.send("USER %s\r\n" % self.call)

        c, l = getline(self._socket)
        if c == 200:
            printlog("Comm","      : Host did not require a password")
        elif c != 102:
            raise DataPathNotConnectedError("User rejected username")

        printlog("Comm","      : Sending password: %s" % ("*" * len(self.passwd)))
        self._socket.send("PASS %s\r\n" % self.passwd)

        c, l = getline(self._socket)
        printlog("Comm","      : Host responded: %i %s" % (c, l))
        if c != 200:
            raise DataPathNotConnectedError("Authentication failed: %s" % l)

    def connect(self):
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.connect((self.host, self.port))
            self._socket.settimeout(self.timeout)
        except Exception as e:
            printlog("Comm","      : Socket connect failed: %s" % e)
            self._socket = None
            raise DataPathNotConnectedError("Unable to connect (%s)" % e)

        if self.passwd is not None:
            self.do_auth()

    def disconnect(self):
        if self._socket:
            self._socket.close()
        self._socket = None

    def read(self, count):
        data = b''
        end = time.time() + self.timeout

        if not self._socket:
            raise DataPathIOError("Socket closed")

        self._socket.setblocking(True)
        self._socket.settimeout(self.timeout)

        while len(data) < count:

            try:
                # x = time.time()
                inp = self._socket.recv(count - len(data))
            except socket.timeout:
                if time.time() > end:
                    break
                else:
                    continue
            except Exception as e:
                raise DataPathIOError("Socket error: %s" % e)

            if inp == b'':
                raise DataPathIOError("Socket disconnected")

            end = time.time() + self.timeout
            data += inp


        return data

    def read_all_waiting(self):
        if not self._socket:
            raise DataPathIOError("Socket disconnected")

        self._socket.setblocking(False)

        r, _w, _x = select.select([self._socket], [], [], self.timeout)
        if not r:
            return b''

        data = b''
        while True:
            try:
                d = self._socket.recv(4096)
            except Exception as e:
                # Best practice is to trap the specific exceptions that
                # are known to occur.
                printlog("Comm""Generic Exception %s %s" % (type(e), e))
                break
            if not d:
                raise DataPathIOError("Socket disconnected: %s")
            data += d

        return data

    def write(self, buf):
        try:
            self._socket.sendall(buf)
        except Exception as e:
            printlog("Comm","      : Socket write failed: %s" % e)
            raise DataPathIOError("Socket write failed")

        return
            
    def is_connected(self):
        return self._socket != None

    def flush(self):
        pass

    def __str__(self):
        try:
            addr, port = self._socket.getpeername()
            return "[NET %s:%i]" % (addr, port)
        except:
            return "[NET closed]"
