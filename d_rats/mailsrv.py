#!/usr/bin/python
'''Mail Server.'''
#
# Copyright 2010 Dan Smith <dsmith@danplanet.com>
# Copyright 2022 John. E. Malmberg - Python3 Conversion
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
import os
from glob import glob

import threading
import smtpd
import asyncore
import email
import random
import time
import re
from socketserver import StreamRequestHandler
from socketserver import TCPServer

#if __name__ == "__main__":
#    import gettext
#    lang = gettext.translation("D-RATS",
#                               localedir="./locale",
#                               languages=["en"],
#                               fallback=True)
#    lang.install()

from d_rats import utils
from d_rats import msgrouting
from d_rats import emailgw


def mkmsgid(callsign):
    '''
    Make Message ID.

    :param callsign: callsign
    :type callsign: str
    :returns: Message ID string
    :rtype: str
    '''
    rand_num = random.SystemRandom().randint(0, 100000)
    return "%s.%x.%x" % (callsign, int(time.time()) - 1114880400, rand_num)


class TCPServerThread(threading.Thread):
    '''
    TCP Server Thread.

    :param config: D-Rats configuration
    :type config: :class:`DratsConfig`
    :param server: Type of server
    :type server: :class:`TCPServer`
    :param server_address: Server address and port
    :type server_address: tuple[str, int]
    :param RequestHandlerClass: Message handler
    :type RequestHandlerClass: :class:`POP3Handler`
    '''

    name = "[UNNAMEDSERVER]"

    def __init__(self, config, server, server_address, RequestHandlerClass):
        self.__server = server(server_address, RequestHandlerClass)
        self.__server.set_config(config)
        threading.Thread.__init__(self)
        self.setDaemon(True)

    def run(self):
        '''Run Server.'''
        self.__server.serve_forever()
        print("%s Exiting" % self.name)

    def stop(self):
        '''Stop Server.'''
        self.__server.shutdown()
        print("%s Shutdown" % self.name)


class POP3Exception(Exception):
    '''POP3 Exception.'''


class POP3TemplateMethod(Exception):
    '''Template Method should not be called.'''


class POP3Exit(Exception):
    '''POP3 Exit Exception.'''


class EmailSenderError(Exception):
    '''Email Sender Exception.'''


class POP3Handler(StreamRequestHandler):
    '''
    POP3 Handler.

    :param request: Incoming request
    :type request: :class:`socket.socket`
    :param client_address: Remote address
    :type Remote address: tuple[str, int]
    :param server: Base server
    :type server: :class:`DratsPOP3Server`
    '''

    def __init__(self, request, client_address, server):
        StreamRequestHandler.__init__(self, request, client_address, server)
        self.state = None
        self._user = None
        self.__msgcache = []

    def _say(self, what, error=False):
        '''
        Say internal.

        :param what: What to say
        :type what: str
        :param error: True if error, default False
        :type error: false
        '''
        if error:
            code = "-ERR"
        else:
            code = "+OK"

        self.wfile.write(code + " %s\r\n" % what)
        print("[POP3] %s %s" % (code, what))

    def _handle_user(self, args):
        '''
        Handle user internal.

        :param args: username
        :type args: str
        :returns: True
        :rtype: bool
        '''
        self._say("username %s accepted" % args)
        self._user = args
        return True

    def _handle_pass(self, _args):
        '''
        _handle Password internal.

        :param args: Unused
        :returns: True
        :rtype: bool
        '''
        self._say("password accepted")
        return True

    # pylance wants a template method to have a possibility
    # of returning or it marks code incorrectly as unreachable.
    def get_message(self, index):
        '''
        Get Message.

        :param index: Index of message
        :type index: int
        :returns: Filename of message
        :rtype: str
        '''
        if self.__msgcache:
            return self.__msgcache[index]
        raise POP3TemplateMethod('%s called template '
                                 'get_message(%s) called' %
                                 (type(self), index))

    def del_message(self, index):
        '''
        Delete Message.

        :param index: Index of message to be deleted
        :type index: int
        '''
        if index < 0:
            self.__msgcache[index] = None
            return
        raise POP3TemplateMethod('%s called template '
                                 'del_message(%s) called' %
                                 (type(self), index))

    def get_messages(self, username):
        '''
        Get Messages.

        :param username: Username to get messages for
        :type username: str
        :returns: Empty list
        :rtype: list
        '''
        if self.__msgcache:
            return self.__msgcache
        raise POP3TemplateMethod('%s called template '
                                 'get_messages(%s) called' %
                                 (type(self), username))

    def _handle_list(self, args):
        '''
        Handle List internal.

        :param args: arguments, unused?
        :type args: unknown
        :returns: True
        :rtype: bool
        '''
        self._handle_stat(args)
        msgs = self.get_messages(self._user)
        index = 1
        for msg in msgs:
            print("%i %i" % (index, len(str(msg))))
            self.wfile.write("%i %i \r\n" % (index, len(str(msg))))
            index += 1
        self.wfile.write(".\r\n")
        return True

    def _handle_stat(self, _args):
        '''
        Handle Stat internal.

        :param args: unused
        :returns: False
        :rtype: bool
        '''
        msgs = self.get_messages(self._user)
        size = 0
        for i in msgs:
            size += len(str(i))
        self._say("%i %i" % (len(msgs), size))
        return False

    def _handle_retr(self, args):
        try:
            index = int(args)
        except ValueError:
            utils.log_exception()
            raise POP3Exception("Invalid message number")

        msg = self.get_message(index - 1)
        mstr = str(msg)

        self._say("OK %i octets" % len(mstr))
        self.wfile.write(mstr + "\r\n.\r\n")

    def _handle_top(self, args):
        msg_number, lines = args.split(" ", 1)

        msg_number = int(msg_number) - 1
        lines = int(lines)

        msg = self.get_message(msg_number)
        self._say("top of message follows")
        self.wfile.write("\r\n".join(str(msg).split("\r\n")[:lines]))
        self.wfile.write("\r\n.\r\n")

    def _handle_dele(self, args):
        '''
        Handle Delete Internal.

        :param args: arguments
        :type args: unknown
        '''
        try:
            index = int(args)
        except ValueError:
            utils.log_exception()
            raise POP3Exception("Invalid message number")

        self.del_message(index-1)
        self._say("Deleted")

    def _handle(self):
        '''Handle Internal.'''
        dispatch = {
            "USER" : (("",), self._handle_user),
            "PASS" : (("USER",), self._handle_pass),
            "LIST" : (("PASS", "LIST", "STAT"), self._handle_list),
            "STAT" : (("PASS", "LIST", "STAT"), self._handle_stat),
            "RETR" : (("LIST", "STAT"), self._handle_retr),
            "TOP"  : (("LIST", "STAT"), self._handle_top),
            "DELE" : (("LIST", "STAT"), self._handle_dele),
            }

        data = self.rfile.readline().strip()
        if not data:
            raise POP3Exception("Conversation error")

        try:
            cmd, args = data.split(" ", 1)
        except ValueError:
            cmd = data
            args = ""

        cmd = cmd.upper()

        print("[POP3] %s %s" % (cmd, args))

        if cmd == "QUIT":
            raise POP3Exit("Goodbye")

        if cmd not in list(dispatch.keys()):
            self._say("Unsupported command `%s'" % cmd, True)
            return

        states, handler = dispatch[cmd]

        if self.state not in states:
            raise POP3Exception("Can't get there from here")

        if handler(args):
            self.state = cmd

    def handle(self):
        '''Handle.'''
        self.state = ""

        self._say("D-RATS waiting")

        while True:
            # pylint: disable=broad-except
            try:
                self._handle()
            except POP3Exit as err:
                self._say(err)
                break
            except POP3Exception as err:
                self._say(err, True)
                break
            except Exception:
                utils.log_exception()
                self._say("Internal error", True)
                break


class DratsPOP3Handler(POP3Handler):
    '''
    D-Rats POP3 Handler.

    :param config: D-Rats configuration
    :type config: :class:`DratsConfig`
    :param args: Arguments for pop3 handler
    '''

    def __init__(self, config, *args):
        self.__config = config
        print("DRATS handler")
        self.__msgcache = []
        POP3Handler.__init__(self, *args)

    def get_messages(self, username):
        '''
        Get messages for a user.

        :param user: user to look up callsign
        :type user: str
        :returns: list of mesage filenames
        :rtype: list of str
        '''
        if self.__msgcache:
            return self.__msgcache

        if username.upper() == self.__config.get("user", "callsign"):
            dir_name = os.path.join(self.__config.form_store_dir(), "Inbox")
            allmsg = True
        else:
            dir_name = os.path.join(self.__config.form_store_dir(), "Outbox")
            allmsg = False

        files = glob(os.path.join(dir_name, "*.xml"))

        for filename in files:
            msg = msgrouting.form_to_email(self.__config, filename)
            if not allmsg and msg["To"] != username.upper():
                continue

            name, addr = email.utils.parseaddr(msg["From"])
            if addr == "DO_NOT_REPLY@d-rats.com":
                addr = "%s@d-rats.com" % name.upper()
                msg.replace_header("From", addr)
                del msg["Reply-To"]

            name, addr = email.utils.parseaddr(msg["To"])
            if not name and "@" not in addr:
                msg.replace_header("To", "%s@d-rats.com" % addr.upper())

            msg["X-DRATS-Source"] = filename
            self.__msgcache.append(msg)

        return self.__msgcache

    def get_message(self, index):
        '''
        Get Message.

        :param index: Index of message
        :type index: int
        :returns: Filename of message
        :rtype: str
        '''
        return self.__msgcache[index]

    def del_message(self, index):
        '''
        Delete Message.

        :param index: Index of message to be deleted
        :type index: int
        '''
        msg = self.__msgcache[index]
        self.__msgcache[index] = None
        filename = msg["X-DRATS-Source"]

        if os.path.exists(filename):
            msgrouting.move_to_folder(self.__config, filename, "Trash")
        else:
            raise POP3Exception("Already deleted")


class DratsPOP3Server(TCPServer):
    '''
    D-RATS POP3 Server.

    :param server_address: Server address and port
    :type server_address: tuple[str, int]
    :param RequestHandlerClass: Message handler
    :type RequestHandlerClass: :class:`POP3Handler`
    :param bind_and_activate: Default True
    :type bind_and_activate: bool
    '''

    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass,
                 bind_and_activate=True):
        TCPServer.__init__(self, server_address, RequestHandlerClass,
                           bind_and_activate)
        self.__config = None

    # Not finding a direct caller of this but this
    # may be an overridden TCPServer method
    def finish_request(self, request, client_address):
        '''
        Finish Request.

        :param request: request
        :type request: :class:`socket.socket`
        :param client_address: client address
        :type client_address: unknown
        '''
        self.RequestHandlerClass(self.__config,
                                 request, client_address, self)

    def set_config(self, config):
        '''
        Set D-rats config for the object.

        :param config: D-Rats configuration
        :type config: :class:`DratsConfig`
        '''
        self.__config = config


# pylint: disable=invalid-name
class DRATS_POP3ServerThread(TCPServerThread):
    '''
    D-RATS POP3 Server Thread.

    :param config: D-Rats configuration
    :type config: :class:`DratsConfig`
    '''

    name = "[POP3]"

    def __init__(self, config):
        port = config.getint("settings", "msg_pop3_port")
        print("[POP3] Starting server on port %i" % port)
        TCPServerThread.__init__(self, config, DratsPOP3Server,
                                 ("0.0.0.0", port), DratsPOP3Handler)
        self.setDaemon(True)


class DratsSMTPServer(smtpd.SMTPServer):
    '''
    D-RATS SMTP Server.

    :param config: D-Rats configuration
    :type config: :class:`DratsConfig`
    '''

    def __init__(self, config):
        self.__config = config
        port = config.getint("settings", "msg_smtp_port")
        smtpd.SMTPServer.__init__(self, ("0.0.0.0", port), None)

    def process_message(self, peer, mailfrom, rcpttos, data, **kwargs):
        '''
        Process Message.

        :param peer: Peer to send to
        :type peer: unknown
        :param mailfrom: Sender information
        :type mailfrom: str
        :param rcpttos: Receiver information
        :type rcpttos: str
        :param data: Message data
        :type data: Unknown
        :raises: :class:`EmailSenderError` if sender is invalid
        '''
        msg = email.message_from_string(data)
        if "@" in mailfrom:
            sender, _other = mailfrom.split("@", 1)
        else:
            sender = mailfrom
        sender = sender.upper()

        if not re.match("[A-Z0-9]+", sender):
            raise EmailSenderError("Sender must be alphanumeric string")

        recip = rcpttos[0]
        if recip.lower().endswith("@d-rats.com"):
            recip, _host = recip.upper().split("@", 1)

        print("Sender is %s" % sender)
        print("Recip  is %s" % recip)

        mid = mkmsgid(self.__config.get("user", "callsign"))
        ffn = os.path.join(self.__config.form_store_dir(),
                           "Outbox", "%s.xml" % mid)
        print("Storing mail at %s" % ffn)

        form = emailgw.create_form_from_mail(self.__config, msg, ffn)
        form.set_path_src(sender)
        form.set_path_dst(recip)
        form.save_to(ffn)
        if msgrouting.msg_is_locked(ffn):
            msgrouting.msg_unlock(ffn)


# pylint: disable=invalid-name
class DRATS_SMTPServerThread(threading.Thread):
    '''D-Rats SMTP Server Thread.'''

    def __init__(self, config):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.__config = config
        self.__server = None

    def run(self):
        '''Run SMTP Server.'''
        print("[SMTP] Starting server")
        self.__server = DratsSMTPServer(self.__config)
        asyncore.loop(timeout=1)
        print("[SMTP] Stopped")

    def stop(self):
        '''Stop SMTP Server.'''
        if self.__server:
            self.__server.close()
        self.join()


def main():
    '''Main program for unit testing.'''

    pop3s = DratsPOP3Server(("localhost", 9090), DratsPOP3Handler)
    pop3s.set_config(None)
    pop3s.serve_forever()

if __name__ == "__main__":
    main()
