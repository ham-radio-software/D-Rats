from __future__ import absolute_import
from __future__ import print_function
#importing printlog() wrapper
from .debug import printlog

import struct
from . import utils
import sys
import socket
import threading

class AGWFrame:
    kind = 0

    def __init__(self):
        self.port = 0
        self.res1 = self.res2 = self.res3 = 0
        self.res4 = self.res5 = self.res6 = 0
        self.pid = 0;
        self.call_from = "".ljust(10)
        self.call_to = "".ljust(10)
        self.len = 0
        self.payload = ""

    def packed(self):
        p = struct.pack("BBBBBBBB10s10sII",
                        self.port,
                        self.res1, self.res2, self.res3,
                        self.kind,
                        self.res4,
                        self.pid,
                        self.res5,
                        self.call_from, self.call_to,
                        self.len,
                        self.res6);

        return p + self.payload;

    def unpack(self, data):
        self.port,\
            self.res1, self.res2, self.res3, \
            self.kind, \
            self.res4, \
            self.pid, \
            self.res5, \
            self.call_from, self.call_to, \
            self.len, \
            self.res6 = struct.unpack("BBBBBBBB10s10sII", data[:36]);

        self.payload = data[36:]
        if len(self.payload) != self.len:
            raise Exception("Expecting payload of %i, got %i" % \
                                (self.len, len(self.payload)))

    def set_payload(self, data):
        self.payload = data
        self.len = len(self.payload)

    def get_payload(self):
        return self.payload

    def set_from(self, call):
        self.call_from = call[:9].ljust(9, '\0') + '\0'

    def get_from(self):
        return self.call_from

    def set_to(self, call):
        self.call_to = call[:10].ljust(9, '\0') + '\0'

    def get_to(self):
        return self.call_to

    def __str__(self):
        return "%s -> %s [%s]: %s" % (self.call_from, self.call_to,
                                      chr(self.kind),
                                      utils.filter_to_ascii(self.payload))

class AGWFrame_k(AGWFrame):
    kind = ord("k")

class AGWFrame_K(AGWFrame):
    kind = ord('K')

class AGWFrame_C(AGWFrame):
    kind = ord('C')

class AGWFrame_d(AGWFrame):
    kind = ord('d')

class AGWFrame_D(AGWFrame):
    kind = ord('D')

class AGWFrame_X(AGWFrame):
    kind = ord('X')

class AGWFrame_x(AGWFrame):
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
    def __init__(self, addr, port, timeout=0):
        self.__lock = threading.Lock()

        self._s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if timeout:
            self._s.settimeout(timeout)
        self._s.connect((addr, port))
        self._buf = ""
        self._framebuf = {}
        for i in AGW_FRAMES.keys():
            self._framebuf[ord(i)] = []

    def _detect_frame(self, data):
        kind = data[4]
        return AGW_FRAMES[kind]()

    def send_frame(self, f):
        self._s.send(f.packed())

    def __recv_frame(self):
        try:
            c = self._s.recv(1)
        except socket.timeout:
            return None
        
        if len(c) == 0: # Socket closed
            self.close()

        self._buf += c
        if len(self._buf) >= 36:
            f = self._detect_frame(self._buf)
            try:
                f.unpack(self._buf)
                self._buf = ""
            except Exception as e:
                return None
            return f

        return None

    def recv_frame_type(self, kind, poll=False):
        while True:
            buffered = self._framebuf.get(ord(kind), [])
            if buffered:
                return buffered.pop()

            self.__lock.acquire()
            f = self.__recv_frame()
            self.__lock.release()
            if f:
                printlog("Agw","       : Got %s frame while waiting for %s" % (chr(f.kind), kind))
                self._framebuf[f.kind].insert(0, f)
            elif not poll:
                return None
        
    def close(self):
        self._s.close()

    def enable_raw(self):
        kf = AGWFrame_k()
        self.send_frame(kf)

class AGW_AX25_Connection:
    def __init__(self, agw, mycall):
        self._agw = agw
        self._mycall = mycall
        self._inbuf = ""

        xf = AGWFrame_X()
        xf.set_from(mycall)
        self._agw.send_frame(xf)

        f = self._agw.recv_frame_type("X", True)

    def connect(self, tocall):
        cf = AGWFrame_C()
        cf.set_from(self._mycall)
        cf.set_to(tocall)
        self._agw.send_frame(cf)

        f = self._agw.recv_frame_type("C", True)
        printlog("Agw","       : %s" % f.get_payload())

    def disconnect(self):
        df = AGWFrame_d()
        df.set_from(self._mycall)
        self._agw.send_frame(df)

        f = self._agw.recv_frame_type("d", True)
        printlog("Agw","       : %s" % f.get_payload())

    def send(self, data):
        df = AGWFrame_D()
        df.set_payload(data)
        self._agw.send_frame(df)

    def recv(self, length=0):
        def consume(count):
            b = self._inbuf[:count]
            self._inbuf = self._inbuf[count:]
            return b

        if length and length < len(self._inbuf):
            return consume(length)

        f = self._agw.recv_frame_type("D")
        if f:
            self._inbuf += f.get_payload()

        if not length:
            return consume(len(self._inbuf))
        else:
            return consume(length)

    def recv_text(self):
        return self.recv().replace("\r", "\n")

def agw_recv_frame(s):
    data = ""
    while True:
        data += s.recv(1)
        if len(data) >= 36:
            f = AGWFrame_K()
            try:
                f.unpack(data)
                data = ""
            except Exception as e:
                #printlog("Failed: %s" % e)
                continue
            printlog("Agw","      : %s -> %s [%s]" % (f.get_from(), f.get_to(), chr(f.kind)))
            utils.hexprintlog(f.get_payload())
            return

def test_raw_recv(s):
    f = AGWFrame_k()

    s.send(f.packed())
    while True:
        agw_recv_frame(s)

def test_connect(s):
    xf = AGWFrame_X()
    xf.set_from("KK7DS")
    s.send(xf.packed())
    agw_recv_frame(s)

    cf = AGWFrame_C()
    cf.set_from("KK7DS")
    cf.set_to("PSVNOD")
    s.send(cf.packed())
    agw_recv_frame(s)

    while True:
        agw_recv_frame(s)

def test_class_connect():
    agw = AGWConnection("127.0.0.1", 8000, 0.5)
    axc = AGW_AX25_Connection(agw, "KK7DS")
    axc.connect("N7AAM-11")
    printlog("Agw","      : %s" % axc.recv_text())

    while True:
        printlog("Agw","       : packet> ")
        l = sys.stdin.readline().strip()
        if len(l) > 0:
            axc.send(l + "\r")
        r = True
        while r:
            r = axc.recv_text()
            printlog("Agw","      : %s" % r)

    axc.disconnect()

def ssid(call):
    if "-" in call:
        try:
            c, s = call.split("-", 1)
        except Exception as e:
            raise Exception("Callsign `%s' not in CCCCCC-N format" % call)
    else:
        c = call
        s = 0

    if len(c) > 6:
        raise Exception("Callsign `%s' is too long" % c)

    c = c.ljust(6)

    try:
        s = int(s)
    except Exception as e:
        raise Exception("Invalid SSID `%s'" % s)

    if s < 0 or s > 7:
        raise Exception("Invalid SSID `%i'" % s)

    return c, s

def encode_ssid(s, last=False):
    if last:
        l = 0x61
    else:
        l = 0x60
    return chr((s << 1) | l)


# conn is the AGWConnection
# dcall is the destination
# spath is a list of either the source, or source + digis
# data is the data to transmit
def transmit_data(conn, dcall, spath, data):
    c, s = ssid(dcall)

    # Encode the call by grabbing each character and shifting
    # left one bit
    dst = "".join([chr(ord(x) << 1) for x in c])
    dst += encode_ssid(s)

    src = ""
    for scall in spath:
        c, s = ssid(scall)
        src += "".join([chr(ord(x) << 1) for x in c])
        src += encode_ssid(s, spath[-1] == scall)
    
    d = struct.pack("B7s%isBB" % len(src),
                    0x00,    # Space for flag (?)
                    dst,     # Dest Call
                    src,     # Source Path
                    0x3E,    # Info
                    0xF0)    # PID: No layer 3
    d += data

    utils.hexprintlog(d)

    f = AGWFrame_K()
    f.set_payload(d)
    conn.send_frame(f)
    
def receive_data(conn, blocking=False):
    f = conn.recv_frame_type("K", blocking)
    if f:
        return f.get_payload()
    else:
        return ""

def test(conn):
    f = AGWFrame_K()
    
    conn.send_frame(f)

if __name__ == "__main__":

    #s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #s.connect(("127.0.0.1", 8000))
    #test_raw_recv(s)
    #test_connect(s)

    agw = AGWConnection("127.0.0.1", 8000, 0.5)
    agw.enable_raw()

    #test_class_connect()
    #test_ui()
    transmit_data(agw, "CQ", ["KK7DS", "KK7DS-3"], "foo")
