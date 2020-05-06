from __future__ import absolute_import
from __future__ import print_function
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
import random
from six.moves import range

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

    f = open(os.path.join(cwd, "input"), "wb")
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
    
    print(("wl2k       : Running %s in %s" % (run, cwd)))

    ret = subprocess.call(run, cwd=cwd, **kwargs)
    print(("wl2k       : LZHUF returned %s" % ret))
    if ret:
        return None

    f = open(os.path.join(cwd, "output"), "rb")
    data = f.read()
    f.close()

    return data

def run_lzhuf_decode(data):
    return run_lzhuf("d", data[2:])

def run_lzhuf_encode(data):
    lzh = run_lzhuf("e", data)
    lzh = struct.pack("<H", calc_checksum(lzh)) + lzh
    return lzh

class WinLinkAttachment:
    def __init__(self, name, content):
        self.__name = name
        self.__content = content

    def get_name(self):
        return self.__name

    def get_content(self):
        return self.__content
    
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

    def encode_message(self, src, dst, name, body, attachments):
        msgid = time.strftime("D%H%M%S") + src
        
        msg = "Mid: %s\r\n" % msgid[:12] + \
            "Subject: %s\r\n" % name + \
            "From: %s\r\n" % src
        for _dst in dst:
            msg += "To: %s\r\n" % _dst

        msg += "Body: %i\r\n" % len(body) + \
            "Date: %s\r\n" % time.strftime("%Y/%m/%d %H:%M", time.gmtime())

        for attachment in attachments:
            msg += "File: %i %s\r\n" % (len(attachment.get_content()),
                                        attachment.get_name())

        msg += "\r\n" + body + "\r\n"

        for attachment in attachments:
            msg += attachment.get_content() + "\r\n"

        if attachments:
            msg += "\r\n\x00"

        self.set_content(msg, name)

    def create_form(self, config, callsign):
        mail = email.message_from_string(self.__content)
	
        sender = mail.get("From", "Unknown")

        if ":" in sender:
            method, sender = sender.split(":", 1)
        
        sender = "WL2K:" + sender

        body = mail.get("Body", "0")

        try:
            body_length = int(body)
        except ValueError:
            raise Exception("Error parsing Body header length `%s'" % value)

        body_start = self.__content.index("\r\n\r\n") + 4
        rest = self.__content[body_start + body_length:]
        message = self.__content[body_start:body_start + body_length]

        if callsign == config.get("user", "callsign"):
            box = "Inbox"
        else:
            box = "Outbox"

        template = os.path.join(config.form_source_dir(),
                                "email.xml")
        formfn = os.path.join(config.form_store_dir(),
                              box, "%s.xml" % self.get_id())

        form = formgui.FormFile(template)
        form.set_field_value("_auto_sender", sender)
        form.set_field_value("recipient", callsign)
        form.set_field_value("subject", mail.get("Subject", "Unknown"))
        form.set_field_value("message", message)

        files = mail.get_all("File")
        if files:
            for att in files:
                length, name = att.split(" ", 1)
                filedata = rest[2:int(length)+2] # Length includes leading CRLF
                print("File %s %i (%i)" % (name, len(filedata), int(length)))
                rest = rest[int(length)+2:]
                form.add_attachment(name, filedata)

        form.set_path_src(sender.strip())
        form.set_path_dst(callsign)
        form.set_path_mid(self.get_id())
        form.add_path_element("@WL2K")
        form.add_path_element(config.get("user", "callsign"))
        form.save_to(formfn)

        return formfn

    def recv_exactly(self, s, l):
        data = ""
        while len(data) < l:
            data += s.recv(l - len(data))

        return data

    def read_from_socket(self, s):
        data = ""

        i = 0
        while True:
            print(("wl2k       : Reading at %i" % i))
            t = ord(self.recv_exactly(s, 1))

            if chr(t) == "*":
                msg = s.recv(1024)
                raise Exception("Error getting message: %s" % msg)

            if t not in list(FBB_BLOCK_TYPES.keys()):
                i += 1
                print(("wl2k       : Got %x (%c) while reading %i" % (t, chr(t), i)))
                continue

            print(("wl2k       : Found %s at %i" % (FBB_BLOCK_TYPES.get(t, "unknown"), i)))
            size = ord(self.recv_exactly(s, 1))
            i += 2 # Account for the type and size

            if t == FBB_BLOCK_HDR:
                header = self.recv_exactly(s, size)
                self.__name, offset, foo = header.split("\0")
                print(("wl2k       : Name is `%s' offset %s\n" % (self.__name, offset)))
                i += size
            elif t == FBB_BLOCK_DAT:
                print(("wl2k       : Reading data block %i bytes" % size))
                data += self.recv_exactly(s, size)
                i += size
            elif t == FBB_BLOCK_EOF:
                cs = size
                for i in data:
                    cs += ord(i)
                if (cs % 256) != 0:
                    print(("wl2k       : Ack! %i left from cs %i" % (cs, size)))
                
                break

        print(("wl2k       : Got data: %i bytes" % len(data)))
        self.__content = self.__decode_lzhuf(data)
        if self.__content is None:
            raise Exception("Failed to decode compressed message")
        
        if len(data) != self.__csize:
            print(("wl2k       : Compressed size %i != %i" % (len(data), self.__csize)))
        if len(self.__content) != self.__usize:
            print(("wl2k       : Uncompressed size %i != %i" % (len(self.__content), self.__usize)))

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
        print(("wl2k       :  -> %s" % string))
        self._conn.send(string + "\r")

    def __recv(self):
        resp = ""
        while not resp.endswith("\r"):
            resp += self._conn.recv(1)
        print(("wl2k       :  <- %s" % escaped(resp)))
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
                    print(("wl2k       : Creating message for %s" % l))
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
                    print(("wl2k       : Invalid line: %s" % l))
                    raise Exception("Conversation error (%s while listing)" % l)

        return msgs

    def get_messages(self):
        self._connect()
        self._login()
        self.__messages = self.__get_list()

        if self.__messages:
            self._send("FS %s" % ("Y" * len(self.__messages)))

            for msg in self.__messages:
                print("wl2k       : Getting message...")
                try:
                    msg.read_from_socket(self._conn)
                except Exception as e:
                    raise

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
    def __init__(self, callsign, server="server.winlink.org", port=8772, passwd=""):
        self.__server = server
        self.__port = port
        self.__passwd = passwd
        WinLinkCMS.__init__(self, callsign)

    def __ssid(self):
        return "[DRATS-%s-B2FHIM$]" % version.DRATS_VERSION

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

        try:
            sw, ver, caps = resp[1:-1].split("-")
        except Exception:
            raise Exception("Conversation error (unparsable SSID `%s')" % resp)

        resp = self._recv().strip()
        if not resp.endswith(">"):
            raise Exception("Conversation error (never got prompt)")

        if len(self.__passwd) > 0:
            self._send("FF")

            resp = self._recv().strip()
            if not resp.startswith("Login ["):
                raise Exception("Conversation error (never saw challenge)")

            chall = resp[7:-2]

            resp = self._recv().strip()
            if not resp.endswith(">"):
                raise Exception("Conversation error (never got prompt)")

            passwd = "_" + self.__passwd

            rem = 6
            todo = 3
            cresp = ""
            while rem > 0:
                ch = random.randint(0,255)

                if ch > 127 and rem > todo:
                    cresp += chr(random.randint(33, 126))
                else:
                    todo -= 1
                    cresp += passwd[int(chall[todo])]
                rem -= 1

            self._send(cresp)

            resp = self._recv()
            if not resp.startswith("Hello "):
                raise Exception("Conversation error (never saw hello)")

            resp = self._recv().strip()
            if not resp.endswith(">"):
                raise Exception("Conversation error (never got prompt)")

        self._send(self.__ssid())

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

    def _run_incoming(self):
        wl = self.wl2k_connect()
        count = wl.get_messages()
        for i in range(0, count):
            msg = wl.get_message(i)
            formfn = msg.create_form(self._config, self._callsign)

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

            m = re.search("Mid: (.*)\r\nSubject: (.*)\r\n", mt.get_content())
            if m:
                mid = m.groups()[0]
                subj = m.groups()[1]
            else:
                mid = time.strftime("%H%M%SDRATS")
                subj = "Message"

            wlm = WinLinkMessage()
            wlm.set_id(mid)
            wlm.set_content(mt.get_content(), subj)
            print(("wl2k       : m  : %s" % m))
            print(("wl2k       : mt : %s" % mt))
            wl.send_messages([wlm])

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
        passwd = self._config.get("prefs", "msg_wl2k_password")
        return WinLinkTelnet(self._callssid, server, port, passwd)

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
    print(("wl2k       : WL2K Mode is: %s" % mode))
    if mode == "Network":
        mt = WinLinkTelnetThread(ma.config, *args, **kwargs)
    elif mode == "RMS":
        # TEMPORARY
        port = ma.config.get("prefs", "msg_wl2k_rmsport")
        if port not in ma.sm:
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
        print(("wl2k       : %i messages" % count))
        for i in range(0, count):
            print(("wl2k       : --Message %i--\n%s\n--End--\n\n" % (i, wl.get_message(i).get_content())))
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
        m.set_content(_m.get_content())
        wl = WinLinkTelnet("KK7DS")
        wl.send_messages([m])

