import sys
import os
import socket
import tempfile
import subprocess
import shutil
import email
import threading
import gobject
import struct
import time
import re

sys.path.insert(0, "..")

if __name__=="__main__":
    import gettext
    gettext.install("D-RATS")

from d_rats import version
from d_rats import dplatform
from d_rats import formgui
from d_rats import utils
from d_rats import signals
from d_rats.ddt2 import calc_checksum
from d_rats.ui import main_events
from d_rats import agw

FBB_BLOCK_HDR = 1
FBB_BLOCK_DAT = 2
FBB_BLOCK_EOF = 4

FBB_BLOCK_TYPES = { FBB_BLOCK_HDR : "header",
                    FBB_BLOCK_DAT : "data",
                    FBB_BLOCK_EOF : "eof",
                    }

def escaped(string):
    return string.replace("\n", r"\n").replace("\r", r"\r")

def run_lzhuf(cmd, data):
    p = dplatform.get_platform()

    cwd = tempfile.mkdtemp()

    f = file(os.path.join(cwd, "input"), "wb")
    f.write(data)
    f.close()

    kwargs = {}
    if subprocess.mswindows:
        su = subprocess.STARTUPINFO()
        su.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        su.wShowWindow = subprocess.SW_HIDE
        kwargs["startupinfo"] = su

    if os.name == "nt":
        lzhuf = "LZHUF_1.EXE"
    elif os.name == "darwin":
        raise Exception("Not supported on MacOS")
    else:
        lzhuf = "lzhuf"

    lzhuf_path = os.path.abspath(os.path.join(p.source_dir(), "libexec", lzhuf))
    shutil.copy(os.path.abspath(lzhuf_path), cwd)
    run = [lzhuf_path, cmd, "input", "output"]
    
    print "Running %s in %s" % (run, cwd)

    ret = subprocess.call(run, cwd=cwd, **kwargs)
    print "LZHUF returned %s" % ret
    if ret:
        return None

    f = file(os.path.join(cwd, "output"), "rb")
    data = f.read()
    f.close()

    return data

def run_lzhuf_decode(data):
    return run_lzhuf("d", data[2:])

def run_lzhuf_encode(data):
    lzh = run_lzhuf("e", data)
    lzh = struct.pack("<H", calc_checksum(lzh)) + lzh
    return lzh

class WinLinkMessage:
    def __init__(self, header=None):
        self.__name = ""
        self.__content = ""
        self.__usize = self.__csize = 0
        self.__id = ""
        self.__type = "P"

        if header:
            fc, self.__type, self.__id, us, cs, off = header.split()
            self.__usize = int(us)
            self.__csize = int(cs)

            if int(off) != 0:
                raise Exception("Offset support not implemented")

    def __decode_lzhuf(self, data):
        return run_lzhuf_decode(data)

    def __encode_lzhuf(self, data):
        return run_lzhuf_encode(data)

    def recv_exactly(self, s, l):
        data = ""
        while len(data) < l:
            data += s.recv(l - len(data))

        return data

    def read_from_socket(self, s):
        data = ""

        i = 0
        while True:
            print "Reading at %i" % i
            t = ord(self.recv_exactly(s, 1))

            if chr(t) == "*":
                msg = s.recv(1024)
                raise Exception("Error getting message: %s" % msg)

            if t not in FBB_BLOCK_TYPES.keys():
                i += 1
                print "Got %x (%c) while reading %i" % (t, chr(t), i)
                continue

            print "Found %s at %i" % (FBB_BLOCK_TYPES.get(t, "unknown"), i)
            size = ord(self.recv_exactly(s, 1))
            i += 2 # Account for the type and size

            if t == FBB_BLOCK_HDR:
                header = self.recv_exactly(s, size)
                self.__name, offset, foo = header.split("\0")
                print "Name is `%s' offset %s\n" % (self.__name, offset)
                i += size
            elif t == FBB_BLOCK_DAT:
                print "Reading data block %i bytes" % size
                data += self.recv_exactly(s, size)
                i += size
            elif t == FBB_BLOCK_EOF:
                cs = size
                for i in data:
                    cs += ord(i)
                if (cs % 256) != 0:
                    print "Ack! %i left from cs %i" % (cs, size)
                
                break

        print "Got data: %i bytes" % len(data)
        self.__content = self.__decode_lzhuf(data)
        if self.__content is None:
            raise Exception("Failed to decode compressed message")
        
        if len(data) != self.__csize:
            print "Compressed size %i != %i" % (len(data), self.__csize)
        if len(self.__content) != self.__usize:
            print "Uncompressed size %i != %i" % (len(self.__content),
                                                  self.__usize)

    def send_to_socket(self, s):
        data = self.__lzh_content

        # filename \0 length(0) \0
        header = self.__name + "\x00" + chr(len(data) & 0xFF) + "\x00"
        s.send(struct.pack("BB", FBB_BLOCK_HDR, len(header)) + header)

        sum = 0
        while data:
            chunk = data[:128]
            data = data[128:]

            for i in chunk:
                sum += ord(i)

            s.send(struct.pack("BB", FBB_BLOCK_DAT, len(chunk)) + chunk)

        # Checksum, mod 256, two's complement
        sum = (~sum & 0xFF) + 1
        s.send(struct.pack("BB", FBB_BLOCK_EOF, sum))

    def get_content(self):
        return self.__content

    def set_content(self, content, name="message"):
        self.__name = name
        self.__content = content
        self.__lzh_content = self.__encode_lzhuf(content)
        self.__usize = len(self.__content)
        self.__csize = len(self.__lzh_content)

    def get_id(self):
        return self.__id

    def set_id(self, id):
        self.__id = id

    def get_proposal(self):
        return "FC %s %s %i %i 0" % (self.__type, self.__id,
                                     self.__usize, self.__csize)

class WinLinkCMS:
    def __init__(self, callsign):
        self._callsign = callsign
        self.__messages = []
        self._conn = None

    def __ssid(self):
        return "[DRATS-%s-B2FHIM$]" % version.DRATS_VERSION

    def _send(self, string):
        print "  -> %s" % string
        self._conn.send(string + "\r")

    def __recv(self):
        resp = ""
        while not resp.endswith("\r"):
            resp += self._conn.recv(1)
        print "  <- %s" % escaped(resp)
        return resp

    def _recv(self):
        r = ";"
        while r.startswith(";"):
            r = self.__recv()
        return r;

    def _send_ssid(self, recv_ssid):
        try:
            sw, ver, caps = recv_ssid[1:-1].split("-")
        except Exception:
            raise Exception("Conversation error (unparsable SSID `%s')" % resp)

        self._send(self.__ssid())
        prompt = self._recv().strip()
        if not prompt.endswith(">"):
            raise Exception("Conversation error (never got prompt)")

    def __get_list(self):
        self._send("FF")

        msgs = []
        reading = True
        while reading:
            resp = self._recv()
            for l in resp.split("\r"):
                if l.startswith("FC"):
                    print "Creating message for %s" % l
                    msgs.append(WinLinkMessage(l))
                elif l.startswith("F>"):
                    reading = False
                    break
                elif l.startswith("FQ"):
                    reading = False
                    break
                elif not l:
                    pass
                else:
                    print "Invalid line: %s" % l
                    raise Exception("Conversation error (%s while listing)" % l)

        return msgs

    def get_messages(self):
        self._connect()
        self._login()
        self.__messages = self.__get_list()

        if self.__messages:
            self._send("FS %s" % ("Y" * len(self.__messages)))

            for msg in self.__messages:
                print "Getting message..."
                try:
                    msg.read_from_socket(self._conn)
                except Exception, e:
                    raise
                    #print e
                    
            self._send("FQ")

        self._disconnect()

        return len(self.__messages)

    def get_message(self, index):
        return self.__messages[index]

    def send_messages(self, messages):
        if len(messages) != 1:
            raise Exception("Sorry, batch not implemented yet")

        self._connect()
        self._login()

        cs = 0
        for msg in messages:
            p = msg.get_proposal()
            for i in p:
                cs += ord(i)
            cs += ord("\r")
            self._send(p)

        cs = ((~cs & 0xFF) + 1)
        self._send("F> %02X" % cs)
        resp = self._recv()

        if not resp.startswith("FS"):
            raise Exception("Error talking to server: %s" % resp)

        fs, accepts = resp.split()
        if len(accepts) != len(messages):
            raise Exception("Server refused some of my messages?!")

        for msg in messages:
            msg.send_to_socket(self._conn)

        resp = self._recv()
        self._disconnect()

        return 1

class WinLinkTelnet(WinLinkCMS):
    def __init__(self, callsign, server="server.winlink.org", port=8772):
        self.__server = server
        self.__port = port
        WinLinkCMS.__init__(self, callsign)

    def _connect(self):
        class sock_file:
            def __init__(self):
                self.__s = 0

            def read(self, len):
                return self.__s.recv(len)

            def write(self, buf):
                return self.__s.send(buf)

            def connect(self, spec):
                return self.__s.connect(spec)

            def close(self):
                self.__s.close()

        self._conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._conn.connect((self.__server, self.__port))

    def _disconnect(self):
        self._conn.close()

    def _login(self):
        resp = self._recv()

        resp = self._recv()
        if not resp.startswith("Callsign :"):
            raise Exception("Conversation error (never saw login)")

        self._send(self._callsign)
        resp = self._recv()
        if not resp.startswith("Password :"):
            raise Exception("Conversation error (never saw password)")

        self._send("CMSTELNET")
        resp = self._recv()

        self._send_ssid(resp)

class WinLinkRMSPacket(WinLinkCMS):
    def __init__(self, callsign, remote, agw):
        self.__remote = remote
        self.__agw = agw
        WinLinkCMS.__init__(self, callsign)

    def _connect(self):
        self._conn = agw.AGW_AX25_Connection(self.__agw, self._callsign)
        self._conn.connect(self.__remote)

    def _disconnect(self):
        self._conn.disconnect()

    def _login(self):
        resp = self._recv()
        self._send_ssid(resp)

class WinLinkThread(threading.Thread, gobject.GObject):
    __gsignals__ = {
        "mail-thread-complete" : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                                  (gobject.TYPE_BOOLEAN, gobject.TYPE_STRING)),
        "event" : signals.EVENT,
        "form-received" : signals.FORM_RECEIVED,
        "form-sent" : signals.FORM_SENT,
        }
    _signals = __gsignals__

    def _emit(self, *args):
        gobject.idle_add(self.emit, *args)

    def __init__(self, config, callsign, callssid=None, send_msgs=[]):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        gobject.GObject.__init__(self)

        if not callssid:
            callssid = callsign

        self._config = config
        self._callsign = callsign
        self._callssid = callssid
        self.__send_msgs = send_msgs

    def __create_form(self, msg):
        mail = email.message_from_string(msg.get_content())

        sender = mail.get("From", "Unknown")

        if ":" in sender:
            method, sender = sender.split(":", 1)
        
        sender = "WL2K:" + sender

        if self._callsign == self._config.get("user", "callsign"):
            box = "Inbox"
        else:
            box = "Outbox"

        template = os.path.join(self._config.form_source_dir(),
                                "email.xml")
        formfn = os.path.join(self._config.form_store_dir(),
                              box, "%s.xml" % msg.get_id())

        form = formgui.FormFile(template)
        form.set_field_value("_auto_sender", sender)
        form.set_field_value("recipient", self._callsign)
        form.set_field_value("subject", mail.get("Subject", "Unknown"))
        form.set_field_value("message", mail.get_payload())
        form.set_path_src(sender.strip())
        form.set_path_dst(self._callsign)
        form.set_path_mid(msg.get_id())
        form.add_path_element("@WL2K")
        form.add_path_element(self._config.get("user", "callsign"))
        form.save_to(formfn)

        return formfn

    def _run_incoming(self):
        wl = self.wl2k_connect()
        count = wl.get_messages()
        for i in range(0, count):
            msg = wl.get_message(i)
            formfn = self.__create_form(msg)        

            self._emit("form-received", -999, formfn)

        if count:
            result = "Queued %i messages" % count
        else:
            result = "No messages"

        return result

    def _run_outgoing(self):
        server = self._config.get("prefs", "msg_wl2k_server")
        port = self._config.getint("prefs", "msg_wl2k_port")
        wl = self.wl2k_connect()
        for mt in self.__send_msgs:

            m = re.search("Mid: (.*)\r\nSubject: (.*)\r\n", mt)
            if m:
                mid = m.groups()[0]
                subj = m.groups()[1]
            else:
                mid = time.strftime("%H%M%SDRATS")
                subj = "Message"

            wlm = WinLinkMessage()
            wlm.set_id(mid)
            wlm.set_content(mt, subj)
            print m
            print mt
            wl.send_messages([wlm])

            #self._emit("form-sent", -999, 

        return "Complete"

    def run(self):
        if self.__send_msgs:
            result = self._run_outgoing()
        else:
            result = self._run_incoming()

        self._emit("mail-thread-complete", True, result)

class WinLinkTelnetThread(WinLinkThread):
    def __init__(self, *args, **kwargs):
        WinLinkThread.__init__(self, *args, **kwargs)

    def wl2k_connect(self):
        server = self._config.get("prefs", "msg_wl2k_server")
        port = self._config.getint("prefs", "msg_wl2k_port")
        return WinLinkTelnet(self._callssid, server, port)

class WinLinkAGWThread(WinLinkThread):
    def __init__(self, *args, **kwargs):
        WinLinkThread.__init__(self, *args, **kwargs)
        self.__agwconn = None

    def set_agw_conn(self, agwconn):
        self.__agwconn = agwconn

    def wl2k_connect(self):
        remote = self._config.get("prefs", "msg_wl2k_rmscall")
        return WinLinkRMSPacket(self._callssid, remote, self.__agwconn)

def wl2k_auto_thread(ma, *args, **kwargs):
    mode = ma.config.get("settings", "msg_wl2k_mode")

    #May need for AGW
    #call = config.get("user", "callsign")
    print "WL2K Mode is: %s" % mode
    if mode == "Network":
        mt = WinLinkTelnetThread(ma.config, *args, **kwargs)
    elif mode == "RMS":
        # TEMPORARY
        port = ma.config.get("prefs", "msg_wl2k_rmsport")
        if not ma.sm.has_key(port):
            raise Exception("No such AGW port %s for WL2K" % port)

        a = ma.sm[port][0].pipe.get_agw_connection()
        #a = agw.AGWConnection("127.0.0.1", 8000, 0.5)
        mt = WinLinkAGWThread(ma.config, *args, **kwargs)
        mt.set_agw_conn(a)
    else:
        raise Exception("Unknown WL2K mode: %s" % mode)
    
    return mt

if __name__=="__main__":
    
    if True:
      #wl = WinLinkTelnet("KK7DS", "sandiego.winlink.org")
        agwc = agw.AGWConnection("127.0.0.1", 8000, 0.5)
        wl = WinLinkRMSPacket("KK7DS", "N7AAM-11", agwc)
        count = wl.get_messages()
        print "%i messages" % count
        for i in range(0, count):
            print "--Message %i--\n%s\n--End--\n\n" % (i, wl.get_message(i).get_content())
    else:
        text = "This is a test!"
        _m = """Mid: 12345_KK7DS\r
From: KK7DS\r
To: dsmith@danplanet.com\r
Subject: This is a test\r
Body: %i\r
\r
%s
""" % (len(text), text)

        m = WinLinkMessage()
        m.set_id("1234_KK7DS")
        m.set_content(_m)
        wl = WinLinkTelnet("KK7DS")
        wl.send_messages([m])

