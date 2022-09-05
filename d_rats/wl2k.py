'''WL2K.'''
# pylint wants only 1000 lines per module
# pylint: disable=too-many-lines
from __future__ import absolute_import
from __future__ import print_function

import logging
import os
import socket
import tempfile
import subprocess
import shutil
import email
import threading
import struct
import time
import re
import random
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GObject

# sys.path.insert(0, "..")

from d_rats import version
from d_rats import dplatform
from d_rats import formgui
from d_rats import signals
from d_rats.ddt2 import calc_checksum
from d_rats import agw
from d_rats.dratsexception import DataPathIOError
# from d_rats.dratsexception import DataPathNotConnectedError


class Wl2kAutoThreadUnknownMode(DataPathIOError):
    '''Unknown WinLink mode error.'''


class Wl2kAutoThreadNoSuchPort(DataPathIOError):
    '''No such port error.'''


class Wl2kCMSBadSSID(DataPathIOError):
    '''Error parssing SSID.'''


class Wl2kCMSNoPrompt(DataPathIOError):
    '''No prompt received error.'''


class Wl2kCMSInvalidLine(DataPathIOError):
    '''Invalid Line received error.'''


class Wl2kCMSNotImplemented(DataPathIOError):
    '''Winlink CMS Feature not implemented.'''


class Wl2kCMSServerError(DataPathIOError):
    '''Communications with server error.'''


class Wl2kCMSRefusedMessages(DataPathIOError):
    '''Server refused some some messages error.'''


class Wl2kMessageDecodeError(DataPathIOError):
    '''Error decoding message.'''


class Wl2kMessageHeaderError(DataPathIOError):
    '''Error with the Winlink Message header.'''


class Wl2kMessageOffsetNotSupported(DataPathIOError):
    '''Offset not supported in Winlink messages.'''


class Wl2kMessageSocketReadError(DataPathIOError):
    '''Error reading from the socket.'''


class Wl2kTelnetNoHello(DataPathIOError):
    '''Did not see hello message from server error.'''


class Wl2kTelnetNoChallenge(DataPathIOError):
    '''Did not see challenge message from server error.'''


class Wl2kTelnetNoPassword(DataPathIOError):
    '''Did not see password message from server error.'''


class Wl2kTelnetNoLogin(DataPathIOError):
    '''Did not see login message from server error.'''


class Wl2kClassStubMethodError(Exception):
    '''Base class stub method should not be called error.'''


FBB_BLOCK_HDR = 1
FBB_BLOCK_DAT = 2
FBB_BLOCK_EOF = 4

FBB_BLOCK_TYPES = {FBB_BLOCK_HDR : "header",
                   FBB_BLOCK_DAT : "data",
                   FBB_BLOCK_EOF : "eof",
                   }


def escaped(data):
    '''
    Escape new-lines and cariage returns in data.

    :param data: Data to escape
    :type string: bytes
    :returns: Escaped data
    :rtype: bytes
    '''
    return data.replace(b'\n', b'\\n').replace(b'\r', b'\\r')


def run_lzhuf(cmd, data):
    '''
    Run lzhuf.

    :param cmd: lzhuf command
    :type cmd: str
    :param data: Data to process
    :type data: bytes
    '''
    logger = logging.getLogger("run_lzhuf")
    platform = dplatform.get_platform()

    cwd = tempfile.mkdtemp()

    file_handle = open(os.path.join(cwd, "input"), "wb")
    file_handle.write(data)
    file_handle.close()

    kwargs = {}
    # pylint only works for platform it is run on
    # pylint: disable=no-member
    if subprocess.mswindows:
        child = subprocess.STARTUPINFO()
        child.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        child.wShowWindow = subprocess.SW_HIDE
        kwargs["startupinfo"] = child

    if os.name == "nt":
        lzhuf = "LZHUF_1.EXE"
    else:
        lzhuf = "lzhuf"

    lzhuf_path = os.path.abspath(os.path.join(platform.source_dir(),
                                              "libexec", lzhuf))
    shutil.copy(os.path.abspath(lzhuf_path), cwd)
    run = [lzhuf_path, cmd, "input", "output"]

    logger.info("Running %s in %s", run, cwd)

    ret = subprocess.call(run, cwd=cwd, **kwargs)
    logger.info("LZHUF returned %s", ret)
    if ret:
        return None

    file_handle = open(os.path.join(cwd, "output"), "rb")
    data = file_handle.read()
    file_handle.close()

    return data


def run_lzhuf_decode(data):
    '''
    Run LZHUF Decode.

    :param data: Encoded data
    :type data: bytes
    :returns: Uncompressed data
    :rtype: bytes
    '''
    return run_lzhuf("d", data[2:])


def run_lzhuf_encode(data):
    '''
    Run LZHUF Encode.

    :param data: Unencoded data
    :type data: bytes
    :returns: Compressed data
    :rtype: bytes
    '''
    lzh = run_lzhuf("e", data)
    lzh = struct.pack("<H", calc_checksum(lzh)) + lzh
    return lzh

# Called by msgrouting.py
class WinLinkAttachment:
    '''
    WinLink Attachment.

    :param name: Attachment name
    :type name: str
    :param content: Attachment content
    :type content: bytes
    '''

    def __init__(self, name, content):
        self.__name = name
        self.__content = content

    def get_name(self):
        '''
        Get Name.

        :returns: content name
        :rtype: str
        '''
        return self.__name

    def get_content(self):
        '''
        Get Content.

        :returns: content
        :rtype: bytes
        '''
        return self.__content

# Called by msgrouting.py
# pylint wants only 7 instance attributes for a class
# pylint: disable=too-many-instance-attributes
class WinLinkMessage:
    '''
    WinLink Message.

    :param header: Header for message, default None
    :type header: str
    :raises: :class:`Wl2kMessageOffsetNotSupported` if offset support requested
    '''
    def __init__(self, header=None):
        self.logger = logging.getLogger("WinLinkMessage")
        self.__name = ""
        self.__content = ""
        self.__usize = self.__csize = 0
        self.__id = ""
        self.__type = "P"
        self.__lzh_content = None

        if header:
            _fc, self.__type, self.__id, usize, csize, off = header.split()
            self.__usize = int(usize)
            self.__csize = int(csize)

            if int(off) != 0:
                raise Wl2kMessageOffsetNotSupported(
                    "Offset support not implemented")

    @staticmethod
    def __decode_lzhuf(data):
        return run_lzhuf_decode(data)

    @staticmethod
    def __encode_lzhuf(data):
        return run_lzhuf_encode(data)

    # pylint wants only 5 arguments per method
    # pylint: disable=too-many-arguments
    def encode_message(self, src, dst, name, body, attachments):
        '''
        Encode Message.

        :param src: Source of message
        :type src: str
        :param dst: Destination of message
        :type dst: str
        :param name: Name of message
        :type name: str
        :param body: body of message
        :type body: str
        :param attachment: Attachments to message
        :type attachment: list of :class:`WinLinkAttachment`
        '''
        msgid = time.strftime("D%H%M%S") + src

        msg_str = "Mid: %s\r\n" % msgid[:12] + \
                  "Subject: %s\r\n" % name + \
                  "From: %s\r\n" % src
        for _dst in dst:
            msg_str += "To: %s\r\n" % _dst

        msg_str += "Body: %i\r\n" % len(body) + \
            "Date: %s\r\n" % time.strftime("%Y/%m/%d %H:%M", time.gmtime())

        for attachment in attachments:
            msg_str += "File: %i %s\r\n" % (len(attachment.get_content()),
                                            attachment.get_name())

        msg_str += "\r\n" + body + "\r\n"

        msg = msg_str.encode('utf-8', 'replace')
        for attachment in attachments:
            msg += attachment.get_content() + b"\r\n"

        if attachments:
            msg += b"\r\n\x00"

        self.set_content(msg, name)

    # called from emailgw.py and mailsrv.py
    # pylint wants only 15 local variables per method
    # pylint: disable=too-many-locals
    def create_form(self, config, callsign):
        '''
        Create Form.

        :param config: D-Rats configuration
        :type config: :class:`DratsConfig`
        :param callsign: Callsign to send to
        :type callsign: str
        :returns: Form filename
        :rtype: str
        :raises: :class:`Wl2kMessageHeaderError` if unable to parse header
        '''
        content_str = self.__content.decode('utf-8', 'replace')
        mail = email.message_from_string(content_str)

        sender = mail.get("From", "Unknown")

        if ":" in sender:
            _method, sender = sender.split(":", 1)

        sender = "WL2K:" + sender

        body = mail.get("Body", "0")

        try:
            body_length = int(body)
        except ValueError:
            raise Wl2kMessageHeaderError(
                "Error parsing Body header length `%s'" % body)

        body_start = content_str.index("\r\n\r\n") + 4
        rest = content_str[body_start + body_length:]
        message = content_str[body_start:body_start + body_length]

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
                self.logger.info("create_form: File %s %i (%i)",
                                 name, len(filedata), int(length))
                rest = rest[int(length)+2:]
                form.add_attachment(name, filedata)

        form.set_path_src(sender.strip())
        form.set_path_dst(callsign)
        form.set_path_mid(self.get_id())
        form.add_path_element("@WL2K")
        form.add_path_element(config.get("user", "callsign"))
        form.save_to(formfn)

        return formfn

    @staticmethod
    def recv_exactly(sock, length):
        '''
        Receive Exactly.

        :param sock: Socket to receive on
        :type sock: socket.socket
        :type length: Count of data to receive
        :type length: int
        :returns: data
        :rtype: bytes
        '''
        data = ""
        while len(data) < length:
            data += sock.recv(length - len(data))

        return data

    def read_from_socket(self, sock):
        '''
        Read From Socket.

        :param sock: Socket to read from
        :type sock: socket.socket
        :raises: :class:`Wl2kMessageSocketReadError` if bad data read in
        from the socket
        :raises: :class:`Wl2kMessageDecodeError` if message can not be
        decoded
        '''
        data = b""

        i = 0
        while True:
            self.logger.info("read_from_socket: Reading at %i", i)
            block_type = ord(self.recv_exactly(sock, 1))

            if chr(block_type) == "*":
                msg = sock.recv(1024)
                raise Wl2kMessageSocketReadError("Error getting message: %s" %
                                                 msg)

            if block_type not in list(FBB_BLOCK_TYPES.keys()):
                i += 1
                self.logger.info("read_from_socket: "
                                 "Got %x (%c) while reading %i",
                                 block_type, chr(block_type), i)
                continue

            self.logger.info("read_from_socket: Found %s at %i",
                             FBB_BLOCK_TYPES.get(block_type, "unknown"), i)
            size = ord(self.recv_exactly(sock, 1))
            i += 2 # Account for the type and size

            if block_type == FBB_BLOCK_HDR:
                header = self.recv_exactly(sock, size)
                self.__name, offset, _foo = header.split("\0")
                self.logger.info("read_from_socket: Name is `%s' offset %s\n",
                                 self.__name, offset)
                i += size
            elif block_type == FBB_BLOCK_DAT:
                self.logger.info("read_from_socket: "
                                 "Reading data block %i bytes", size)
                data += self.recv_exactly(sock, size)
                i += size
            elif block_type == FBB_BLOCK_EOF:
                content_size = size
                for i in data:
                    content_size += ord(i)
                if (content_size % 256) != 0:
                    self.logger.info("read_from_socket: "
                                     "Ack! %i left from content_size %i",
                                     content_size, size)

                break

        self.logger.info("read_from_socket: Got data: %i bytes", len(data))
        self.__content = self.__decode_lzhuf(data)
        if self.__content is None:
            raise Wl2kMessageDecodeError("Failed to decode compressed message")

        if len(data) != self.__csize:
            self.logger.info("read_from_socket: Compressed size %i != %i",
                             len(data), self.__csize)
        if len(self.__content) != self.__usize:
            self.logger.info("read_from_socket: Uncompressed size %i != %i",
                             len(self.__content), self.__usize)

    def send_to_socket(self, sock):
        '''
        Send Content To Socket.

        :param sock: Socket for sending
        :type sock: socket.socket
        '''
        data = self.__lzh_content

        # filename \0 length(0) \0
        header = self.__name + "\x00" + chr(len(data) & 0xFF) + "\x00"
        sock.send(struct.pack("BB", FBB_BLOCK_HDR, len(header)) + header)

        checksum = 0
        while data:
            chunk = data[:128]
            data = data[128:]

            for i in chunk:
                checksum += ord(i)

            sock.send(struct.pack("BB", FBB_BLOCK_DAT, len(chunk)) + chunk)

        # Checksum, mod 256, two's complement
        checksum = (~checksum & 0xFF) + 1
        sock.send(struct.pack("BB", FBB_BLOCK_EOF, sum))

    def get_content(self):
        '''
        Get Content.

        :returns: content
        :rtype: bytes
        '''
        return self.__content

    def set_content(self, content, name="message"):
        '''
        Set Content.

        :param content: Content to set
        :type content: bytes
        :param name: Content name, default "message"
        :type name: str
        '''
        self.__name = name
        self.__content = content
        self.__lzh_content = self.__encode_lzhuf(content)
        self.__usize = len(self.__content)
        self.__csize = len(self.__lzh_content)

    def get_id(self):
        '''
        Get Identification.

        :returns: identification text'''
        return self.__id

    def set_id(self, ident):
        '''
        Set Identification.

        :param ident: identification text
        :type str
        '''
        self.__id = ident

    def get_proposal(self):
        '''
        Get Proposal.

        :returns: Proposal
        :rtype: bytes
        '''
        proposal_str = "FC %s %s %i %i 0" % (self.__type, self.__id,
                                            self.__usize, self.__csize)
        return proposal.encode('utf-8', 'replace')

class WinLinkCMS:
    '''
    WinLink CMS.

    :param callsign: Call sign
    :type callsign: str
    '''
    def __init__(self, callsign):
        self.logger = logging.getLogger("WinLinkCMS")
        self._callsign = callsign
        self.__messages = []
        self._conn = None

    def _connect(self):
        '''
        Connect internal.

        :raises: :class:`Wl2kClassStubMethodError`
        '''
        # Needs to exist to make pylint happy
        # Needs to possibly return to make pylance happy
        # but this method should never get called.
        if not self._conn:
            raise Wl2kClassStubMethodError(type(self))

    def _disconnect(self):
        '''
        Disconnect internal.

        :raises: :class:`Wl2kClassStubMethodError`
        '''
        # Needs to exist to make pylint/pylance happy
        # Needs to possibly return to make pylance happy
        # but this method should never get called.
        if not self._conn:
            raise Wl2kClassStubMethodError(type(self))

    def _login(self):
        '''
        Login internal.

        :raises: :class:`Wl2kClassStubMethodError`
        '''
        # Needs to exist to make pylint happy
        # Needs to possibly return to make pylance happy
        # but this method should never get called.
        if not self._conn:
            raise Wl2kClassStubMethodError(type(self))


    @staticmethod
    def ssid():
        ssid_str = "[DRATS-%s-B2FHIM$]" % version.DRATS_VERSION_NUM
        return ssid_str.encode('utf-8', 'replace')

    def _send(self, data):
        '''
        Send Internal.

        :param data: data to send
        :type data: bytes
        '''
        self.logger.info("_send:  -> %s", data)
        self._conn.send(data + b"\r")

    def __recv(self):
        '''
        Receive Internal.

        :returns: Received data
        :rtype bytes
        '''
        resp = b""
        while not resp.endswith(b"\r"):
            resp += self._conn.recv(1)
        self.logger.info("__recv:  <- %s", escaped(resp))
        return resp

    def _recv(self):
        '''
        Receive Internal.

        :returns: Received data
        :rtype: bytes
        '''
        received = b";"
        while received.startswith(b";"):
            received = self.__recv()
        return received

    def _send_ssid(self, recv_ssid):
        '''
        Send SSID Internal

        :param recv_ssid: incoming SSID
        :type recv_ssid: bytes
        :raises: :class:`Wl2kCMSBadSSID` if SSID can not be parsed
        :raises: :class:`Wl2kCMSNoPrompt` if prompt not received
        '''
        try:
            _sw, _ver, _caps = recv_ssid[1:-1].split(b"-")
        except ValueError:
            raise Wl2kCMSBadSSID(
                "Conversation error (unparsable SSID `%s')" % recv_ssid)

        self._send(self.ssid())
        prompt = self._recv().strip()
        if not prompt.endswith(b">"):
            raise Wl2kCMSNoPrompt("Conversation error (never got prompt)")

    def __get_list(self):
        '''
        Get List Internal.

        :returns: List of messages
        :rtype: list of :class:`WinLinkMessage`
        :raises: :class:`Wl2kCMSInvalidLine` if invalid line found.
        '''
        self._send(b'FF')

        msgs = []
        reading = True
        while reading:
            resp = self._recv()
            for line in resp.split(b"\r"):
                if line.startswith(b"FC"):
                    self.logger.info("__get_list: Creating message for %s",
                                     line)
                    msgs.append(WinLinkMessage(line))
                elif line.startswith(b"F>"):
                    reading = False
                    break
                elif line.startswith(b"FQ"):
                    reading = False
                    break
                elif not line:
                    pass
                else:
                    self.logger.info("__get_list: Invalid line: %s", line)
                    raise Wl2kCMSInvalidLine(
                        "Conversation error (%s while listing)" % line)

        return msgs

    def get_messages(self):
        '''
        Get Messages.

        :returns: Number of messages
        :rtype: int
        '''
        self._connect()
        self._login()
        self.__messages = self.__get_list()

        if self.__messages:
            data_str = b"FS %s" % ("Y" * len(self.__messages))
            self._send(data_str.encode('utf-8', 'replace'))

            for msg in self.__messages:
                self.logger.info("get_message: Getting message...")
                msg.read_from_socket(self._conn)

            self._send(b"FQ")

        self._disconnect()

        return len(self.__messages)

    def get_message(self, index):
        '''
        Get Message.

        :param index: Index to message
        :type index: int
        :returns: Windlink message
        :rtype: :class:`Wl2kMessage`
        '''
        return self.__messages[index]

    def send_messages(self, messages):
        '''
        Send Messages.

        :param mesages: WinLink messages
        :type message: list of :class:`Wl2kMessage`
        :returns: Number of messages sent.
        :rtype: int
        :raises: :class:`Wl2kCMSNotImplemented` if more than one message
        in list
        :raises: :class:`Wl2kCMSServerError` if error talking to server
        :raises: :class:`Wl2kCMSRefusedMessages` if server refused some
        messages
        '''
        if len(messages) != 1:
            raise Wl2kCMSNotImplemented("Sorry, batch not implemented yet")

        self._connect()
        self._login()

        cs_octet = 0
        for msg in messages:
            proposal = msg.get_proposal()
            for item in proposal:
                cs_octet += item
            cs_octet += ord("\r")
            self._send(proposal)

        cs_octet = ((~cs_octet & 0xFF) + 1)
        data_str = "F> %02X" % cs_octet
        self._send(data_str.encode('utf-8', 'replace'))
        resp = self._recv()

        if not resp.startswith(b"FS"):
            raise Wl2kCMSServerError("Error talking to server: %s" % resp)

        _fs, accepts = resp.split()
        if len(accepts) != len(messages):
            raise Wl2kCMSRefusedMessages(
                "Server refused some of my messages?!")

        for msg in messages:
            msg.send_to_socket(self._conn)

        resp = self._recv()
        self._disconnect()

        return 1


class WinLinkTelnet(WinLinkCMS):
    '''
    WinLink Telnet.

    :param callsign: callsign
    :type callsign: str
    :param server: Server name, default "server.winlink.org"
    :type server: str
    :param port: remote port, default 8772
    :type port: int
    :param passwd: password, default ""
    :type passwd: str
    '''
    def __init__(self, callsign,
                 server="server.winlink.org", port=8772, passwd=""):
        self.__server = server
        self.__port = port
        self.__passwd = passwd
        WinLinkCMS.__init__(self, callsign)
        self.logger = logging.getLogger("WinLinkTelnet")

    def _connect(self):
        '''Connect.'''
        self._conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._conn.connect((self.__server, self.__port))

    def _disconnect(self):
        self._conn.close()

    def _login(self):
        '''
        Login Internal

        :raises: :class:`Wl2kCMSBadSSID` if SSID can not be parsed
        :raises: :class:`Wl2kCMSNoPrompt` if no prompt seen
        :raises: :class:`Wl2kTelnetNoChallenge` if challenge message not seen
        :raises: :class:`Wl2kTelnetNoHello` if hello message not seen
        :raises: :class:`Wl2kTelnetNoLogin` if login message not seen
        :raises: :class:`Wl2kTelnetNoPassword` if password message not seen
        '''

        resp = self._recv()

        resp = self._recv()
        if not resp.startswith(b"Callsign :"):
            raise Wl2kTelnetNoLogin("Conversation error (never saw login)")

        self._send(self._callsign)
        resp = self._recv()
        if not resp.startswith(b"Password :"):
            raise Wl2kTelnetNoPassword("Conversation error (never saw password)")

        self._send(b"CMSTELNET")
        resp = self._recv()

        try:
            _sw, _ver, _caps = resp[1:-1].split(b"-")
        except ValueError:
            raise Wl2kCMSBadSSID(
                "Conversation error (unparsable SSID `%s')" % resp)

        resp = self._recv().strip()
        if not resp.endswith(b">"):
            raise Wl2kCMSNoPrompt("Conversation error (never got prompt)")

        if self.__passwd:
            self._send(b"FF")

            resp = self._recv().strip()
            if not resp.startswith(b"Login ["):
                raise Wl2kTelnetNoChallenge(
                    "Conversation error (never saw challenge)")

            chall = resp[7:-2]

            resp = self._recv().strip()
            if not resp.endswith(b">"):
                raise Wl2kCMSNoPrompt(
                    "Conversation error (never got prompt)")

            passwd = "_" + self.__passwd

            rem = 6
            todo = 3
            cresp_str = ""
            while rem > 0:
                octet = random.randint(0, 255)

                if octet > 127 and rem > todo:
                    cresp += chr(random.randint(33, 126))
                else:
                    todo -= 1
                    cresp += passwd[int(chall[todo])]
                rem -= 1

            self._send(cresp_str.encode('utf-8', 'replace'))

            resp = self._recv()
            if not resp.startswith(b"Hello "):
                raise Wl2kTelnetNoHello(
                    "Conversation error (never saw hello)")

            resp = self._recv().strip()
            if not resp.endswith(b">"):
                raise Wl2kCMSNoPrompt(
                    "Conversation error (never got prompt)")

        self._send(self.ssid())


class WinLinkRMSPacket(WinLinkCMS):
    '''
    WinLink RMS Packet.

    :param callsign: call sign
    :type callsign: str
    :param remote: remote RMS call
    :type remote: str
    :param agw_conn: AGWPE connection
    :type agw_conn: :class:`agw.AGWConnection`
    '''
    def __init__(self, callsign, remote, agw_conn):
        self.__remote = remote
        self.__agw = agw_conn
        WinLinkCMS.__init__(self, callsign)
        self.logger = logging.getLogger("WinLinkRMSPacket")

    def _connect(self):
        self._conn = agw.AGW_AX25_Connection(self.__agw, self._callsign)
        self._conn.connect(self.__remote)

    def _disconnect(self):
        self._conn.disconnect()

    def _login(self):
        resp = self._recv()
        self._send_ssid(resp)


# Also called by sessions/rpc.py
class WinLinkThread(threading.Thread, GObject.GObject):
    '''
    WinLink Thread.

    :param config: d-rats configuration
    :type config: :class:`DratsConfig`
    :param callsign: Call sign
    :type callsign: str
    :param callssid: Call sign with session ID, default None
    :type callssid: str
    :param send_msgs: mesages to send, default []
    :type send_msgs: list of messages
    '''

    __gsignals__ = {
        "mail-thread-complete" : (GObject.SignalFlags.RUN_LAST,
                                  GObject.TYPE_NONE,
                                  (GObject.TYPE_BOOLEAN, GObject.TYPE_STRING)),
        "event" : signals.EVENT,
        "form-received" : signals.FORM_RECEIVED,
        "form-sent" : signals.FORM_SENT,
        }
    _signals = __gsignals__

    def __init__(self, config, callsign, callssid=None, send_msgs=None):
        threading.Thread.__init__(self)
        self.logger = logging.getLogger("WinLinkThread")

        self.setDaemon(True)
        GObject.GObject.__init__(self)

        if not callssid:
            callssid = callsign

        self._config = config
        self._callsign = callsign
        self._callssid = callssid
        self._send_messages = []
        if send_msgs:
            self.__send_msgs = send_msgs

    def wl2k_connect(self):
        '''
        Winlink 2K Connect.

        :returns: Winlink connection
        :rtype: :class:`WinLinkCMS`
        :raises: :class:`Wl2kClassStubMethodError`
        '''
        # Needs to exist to make pylint happy
        # Needs to possibly return something other than None to make
        # pylint happy.
        # but this method should never get called.
        if self._callsign != 'Garbage Text':
            raise Wl2kClassStubMethodError(type(self))
        return WinLinkCMS("")

    def _emit(self, *args):
        '''
        Emit signal from thread.
        '''
        GObject.idle_add(self.emit, *args)

    def _run_incoming(self):
        '''
        Run Incoming Internal.

        :returns: status of run
        :rtype: str
        '''
        winlink = self.wl2k_connect()
        count = winlink.get_messages()
        for i in range(0, count):
            msg = winlink.get_message(i)
            formfn = msg.create_form(self._config, self._callsign)

            self._emit("form-received", -999, formfn)

        if count:
            result = "Queued %i messages" % count
        else:
            result = "No messages"

        return result

    def _run_outgoing(self):
        '''
        Run Outgoing Internal.

        :returns: "Complete" when all messages sent
        :rtype: str
        '''
        _server = self._config.get("prefs", "msg_wl2k_server") # type: ignore
        _port = self._config.getint("prefs", "msg_wl2k_port")
        winlink = self.wl2k_connect()
        for message_thread in self.__send_msgs:

            message = re.search("Mid: (.*)\r\nSubject: (.*)\r\n",
                                message_thread.get_content())
            if message:
                mid = message.groups()[0]
                subj = message.groups()[1]
            else:
                mid = time.strftime("%H%M%SDRATS")
                subj = "Message"

            wlm = WinLinkMessage()
            wlm.set_id(mid)
            wlm.set_content(message_thread.get_content(), subj)
            self.logger.info("message: %s", message)
            self.logger.info("mesage_thread : %s", message_thread)
            winlink.send_messages([wlm])

        return "Complete"

    def run(self):
        if self.__send_msgs:
            result = self._run_outgoing()
        else:
            result = self._run_incoming()

        self._emit("mail-thread-complete", True, result)


class WinLinkTelnetThread(WinLinkThread):
    '''WinLink Telnet Thread.'''

    def __init__(self, *args, **kwargs):
        WinLinkThread.__init__(self, *args, **kwargs)
        self.logger = logging.getLogger("WinLinkTelnetThread")

    def wl2k_connect(self):
        '''
        WL2K Connect.

        :returns: winlink telnet thread.
        :rtype: :class:`WinLinkTelnet`
        '''
        server = self._config.get("prefs", "msg_wl2k_server")
        port = self._config.getint("prefs", "msg_wl2k_port")
        passwd = self._config.get("prefs", "msg_wl2k_password")
        return WinLinkTelnet(self._callssid, server, port, passwd)


class WinLinkAGWThread(WinLinkThread):
    '''WinLink AGW Thread.'''

    def __init__(self, *args, **kwargs):
        WinLinkThread.__init__(self, *args, **kwargs)
        self.logger = logging.getLogger("WinLinkAGWThread")
        self.__agwconn = None

    def set_agw_conn(self, agwconn):
        '''
        Set AGW Connection.

        :param agwconn: something
        :type agwconn: something'''
        self.__agwconn = agwconn

    def wl2k_connect(self):
        '''
        Wl2k Connect.

        :returns: connection packet result.
        :rtype: :class:`WinLinkRMSPacket`
        '''
        remote = self._config.get("prefs", "msg_wl2k_rmscall")
        return WinLinkRMSPacket(self._callssid, remote, self.__agwconn)


# called by mainapp.py and msgrouting.py
def wl2k_auto_thread(mainapp, *args, **kwargs):
    '''
    W2LK Auto Thread.

    :param mainapp: Main application
    :type mainapp: :class:`MainApp`
    :returns: Telnet thread
    :rtype: :class:`WinLinkTelnetThread`
    :raises: :class:`Wl2kAutoThreadNoSuchPort` if AGW port does not exist
    :raises: :class:`Wl2kAutoThreadUnknownMode` for unknown WinLink modes
    '''
    mode = mainapp.config.get("settings", "msg_wl2k_mode")

    logger = logging.getLogger("wl2k_auto_thread")

    # May need for AGW
    # call = config.get("user", "callsign")
    logger.info("WL2K Mode is: %s", mode)
    if mode == "Network":
        message_thread = WinLinkTelnetThread(mainapp.config, *args, **kwargs)
    elif mode == "RMS":
        # TEMPORARY
        port = mainapp.config.get("prefs", "msg_wl2k_rmsport")
        if port not in mainapp.sm:
            raise Wl2kAutoThreadNoSuchPort(
                "No such AGW port %s for WL2K" % port)

        agw_conn = mainapp.sm[port][0].pipe.get_agw_connection()
        # a = agw.AGWConnection("127.0.0.1", 8000, 0.5)
        message_thread = WinLinkAGWThread(mainapp.config, *args, **kwargs)
        message_thread.set_agw_conn(agw_conn)
    else:
        raise Wl2kAutoThreadUnknownMode("Unknown WL2K mode: %s" % mode)

    return message_thread


def test_agw_server(host="127.0.0.1", port=8000):
    '''
    Test Server.

    :param host: host address to listen on, default '127.0.0.1'
    :type host : str
    :param port: Port to listen on, default 80000
    :type port: int
    '''
    logger = logging.getLogger("wl2k_test_agw_server")
    # Quick and dirty simulator for agwpe unit tests.
    logger.info("test_server: starting %s:%i", host, port)
    from time import sleep

    ssid = WinLinkCMS.ssid() + b'\r'
    conn_state = 0
    # call_from = None

    agw_conn = agw.AGWConnection(host, port, timeout=10, server=True)
    _conn = agw_conn.accept_connection()
    count = 0
    while count < 5:
        try:
            frame = agw_conn.recv_frame()
            if not frame:
                count += 1
                logger.info("test_server: no frame")
                sleep(1)
                continue

            logger.info("test_server: Received %s kind %s",
                        frame, chr(frame.kind))
            # if frame.kind == ord('X'):
            #    call_from = frame.call_from
            if frame.kind == ord('D'):
                if conn_state >= 1:
                    frame.len = 3
                    frame.payload = b"F>\r"
                    conn_state = 2

            agw_conn.send_frame(frame)
            logger.info("test_server: sending %s kind %s",
                        frame, chr(frame.kind))

            if conn_state == 0 and frame.kind == ord('C'):
                conn_state = 1
                frame.payload = ssid
                frame.len = len(ssid)
                frame.kind = ord('D')
                logger.info("test_server: sending %s kind %s payload %s",
                        frame, chr(frame.kind), frame.payload)
                agw_conn.send_frame(frame)
        except (ConnectionError, OSError):
            logger.info("test_server: failed", exc_info=True)


def main():
    '''Unit Test.'''

    logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
                        datefmt="%m/%d/%Y %H:%M:%S",
                        level=logging.INFO)

    logger = logging.getLogger("wl2k_test")

    from time import sleep
    server = threading.Thread(target=test_agw_server)
    server.start()
    sleep(2)

    # winlink = WinLinkTelnet("KK7DS", "sandiego.winlink.org")
    agwc = agw.AGWConnection("127.0.0.1", 8000, 0.5)
    winlink = WinLinkRMSPacket("KK7DS", "N7AAM-11", agwc)
    count = winlink.get_messages()
    logger.info("%i messages", count)
    for i in range(0, count):
        logger.info("--Message %i--\n%s\n--End--\n\n",
                    i, winlink.get_message(i).get_content())

    # code here commented out and appears to be currently broken.
    # text = "This is a test!"
    # body = """Mid: 12345_KK7DS\r
#From: KK7DS\r
#To: dsmith@danplanet.com\r
#Subject: This is a test\r
#Body: %i\r
#\r
#%s
#""" % (len(text), text)
#
#    message = WinLinkMessage()
#    message.set_id("1234_KK7DS")
#    # obvious bug in unreachable code here:
#    message.set_content(body.get_content())
#    winlink = WinLinkTelnet("KK7DS")
#    winlink.send_messages([m])

if __name__ == "__main__":
    main()
