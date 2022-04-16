#!/usr/bin/python
'''Email Gateway.'''
#
# Copyright 2008 Dan Smith <dsmith@danplanet.com>
# Copyright 2021-2022 John. E. Malmberg - Python3 Conversion
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

import logging
import os
import threading
import poplib
import re
import random
import time

import email
from email.utils import parseaddr

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GObject
from gi.repository import GLib

from . import dplatform
from . import formgui
from .ui import main_events
from . import signals
from . import utils
from . import msgrouting


if not '_' in locals():
    import gettext
    _ = gettext.gettext


class EmailGatewayException(Exception):
    '''Generic Email Gateway Exception.'''


class NoUsablePartError(EmailGatewayException):
    '''No usable part error.'''


class BadAccountSettingsError(EmailGatewayException):
    '''Bad Email account settings.'''


class UnsupportedActionError(EmailGatewayException):
    '''Unsupported action.'''


# pylint wants only 15 local variables
# pylint: disable=too-many-branches, too-many-locals
def create_form_from_mail(config, mail, tmpfn):
    '''
    Create form from mail.

    :param config: Config object
    :type config: :class:`DratsConfig`
    :param mail: Mail message
    :type message: :class:`EmailMessage`
    :param tmpfn: Temporary filename
    :type tmpfn: str
    :returns: Form containing message
    :rtype: :class:`formgui.FormFile`
    :raises: :class:`NoUsablePartError` if unable to parse form
    '''
    logger = logging.getLogger("emailgw:create_form_from_mail")

    subject = mail.get("Subject", "[no subject]")
    # Note: example.com, example.org, and example.net are the only domains
    # that should every be used as placeholders or samples for mail that
    # should not get delivered.
    # Use of any other domain allows that program to be used in a
    # distributed denial of service attack
    sender = mail.get("From", "Unknown <devnull@example.com>")

    xml = None
    body = b""

    if mail.is_multipart():
        html = None
        for part in mail.walk():
            if part.get_content_maintype() == "multipart":
                continue
            elif part.get_content_type() == "d-rats/form_xml":
                xml = str(part.get_payload())
                break # A form payload trumps all
            elif part.get_content_type() == "text/plain":
                body += part.get_payload(decode=True)
            elif part.get_content_type() == "text/html":
                html = part.get_payload(decode=True)
        if not body:
            body = html
    else:
        body = mail.get_payload(decode=True)

    if not body and not xml:
        raise NoUsablePartError("Unable to find a usable part")

    messageid = mail.get("Message-ID", time.strftime("%m%d%Y%H%M%S"))
    if not msgrouting.msg_lock(tmpfn):
        logger.info("AIEE: Unable to lock incoming email message file!")

    if xml:
        file_handle = open(tmpfn, "w")
        file_handle.write(xml)
        file_handle.close()
        form = formgui.FormFile(tmpfn)
        recip = form.get_recipient_string()
        if "%" in recip:
            recip, _addr = recip.split("%", 1)
            recip = recip.upper()
    else:
        logger.info("Email from %s: %s", sender, subject)

        recip, addr = parseaddr(mail.get("To", "UNKNOWN"))
        if not recip:
            recip = addr

        efn = os.path.join(config.form_source_dir(), "email.xml")
        form = formgui.FormFile(efn)
        form.set_field_value("_auto_sender", sender)
        form.set_field_value("recipient", recip)
        form.set_field_value("subject", "EMAIL: %s" % subject)
        form.set_field_value("message", utils.filter_to_ascii(body))
        form.set_path_src(sender.strip())
        form.set_path_dst(recip.strip())
        form.set_path_mid(messageid)

    form.save_to(tmpfn)

    return form


# pylint wants only 7 instance attributes
# pylint: disable=too-many-instance-attributes
class MailThread(threading.Thread, GObject.GObject):
    '''
    Mail Thread.

    :param config: Config object
    :type config: :class:`DratsConfig`
    :param host: Email host
    :type host: str
    :param user: User account
    :type user: str
    :param password: Password for account
    :type password: str
    :param port: Email port, default 110
    :type port: int
    :param ssl: Use ssl, default False
    :type ssl: bool
    '''

    __gsignals__ = {
        "user-send-chat" : signals.USER_SEND_CHAT,
        "user-send-form" : signals.USER_SEND_FORM,
        "form-received" : signals.FORM_RECEIVED,
        "get-station-list" : signals.GET_STATION_LIST,
        "event" : signals.EVENT,
        "mail-thread-complete" : (GObject.SignalFlags.RUN_LAST,
                                  GObject.TYPE_NONE,
                                  (GObject.TYPE_BOOLEAN, GObject.TYPE_STRING)),
        }

    _signals = __gsignals__

    # pylint: disable=too-many-arguments
    def __init__(self, config, host, user, pasw, port=110, ssl=False):
        threading.Thread.__init__(self)
        GObject.GObject.__init__(self)
        self.logger = logging.getLogger("MailThread")
        self.setDaemon(True)

        self.username = user
        self.password = pasw
        self.server = host
        self.port = port
        self.use_ssl = ssl

        self.config = config

        self._coerce_call = None

    def _emit(self, signal, *args):
        GLib.idle_add(self.emit, signal, *args)

    def message(self, message):
        '''
        Log a Message.

        :param message: Message to log
        :type message: :class:`EmailMessage`
        '''
        self.logger.info("[MAIL %s@%s] %s",
                         self.username, self.server, message)

    def create_form_from_mail(self, mail):
        '''
        Create form from mail.

        :param mail: Mail message
        :type message: :class:`EmailMessage`
        '''
        ident = self.config.get("user", "callsign") + \
            time.strftime("%m%d%Y%H%M%S") + \
            mail.get("Message-id", str(random.randint(0, 1000)))
        mid = dplatform.get_platform().filter_filename(ident)
        ffn = os.path.join(self.config.form_store_dir(),
                           _("Inbox"),
                           "%s.xml" % mid)
        try:
            form = create_form_from_mail(self.config, mail, ffn)
        except NoUsablePartError as err:
            self.logger.info("create_form_from_mail: "
                             "Failed to create form from mail: %s", err)
            return

        if self._coerce_call:
            self.logger.info("create_form_from_mail: "
                             "Coercing to %s", self._coerce_call)
            form.set_path_dst(self._coerce_call)
        else:
            self.logger.info("create_from_from_email: Not coercing")

        form.add_path_element("EMAIL")
        form.add_path_element(self.config.get("user", "callsign"))
        form.save_to(ffn)

        self._emit("form-received", -999, ffn)

    def fetch_mails(self):
        '''
        Fetch mails.

        :returns: List of mesages
        :rtype: list[:class:`EmailMessage`]
        '''
        self.message("Querying %s:%i" % (self.server, self.port))

        if self.use_ssl:
            server = poplib.POP3_SSL(self.server, self.port)
        else:
            server = poplib.POP3(self.server, self.port)

        server.user(self.username)
        server.pass_(self.password)

        num = len(server.list()[1])

        messages = []

        for i in range(num):
            self.message("Fetching %i/%i" % (i+1, num))
            result = server.retr(i+1)
            message = email.message_from_bytes(b"\r\n".join(result[1]))
            messages.append(message)
            server.dele(i+1)

        server.quit()

        return messages

    def run(self):
        self.message("One-shot thread starting")
        mails = None

        if not self.config.getboolean("state", "connected_inet"):
            result = "Not connected to the Internet"
        else:
            try:
                mails = self.fetch_mails()
            except (poplib.error_proto, ConnectionError, OSError) as err:
                result = "Failed (%s)" % (err)

            if mails:
                for mail in mails:
                    self.create_form_from_mail(mail)
                event = main_events.Event(None,
                                          _("Received %i messages") % \
                                          len(mails))
                self._emit("event", event)

                result = "Queued %i messages" % len(mails)
            elif mails is not None:
                result = "No messages"

        self.message("Thread ended [ %s ]" % result)

        self._emit("mail-thread-complete", mails is not None, result)


class CoercedMailThread(MailThread):
    '''
    Coerce Mail Thread.

    :param args: MailThread arguments
    '''

    def __init__(self, *args):
        call = str(args[-1])
        args = args[:-1]
        MailThread.__init__(self, *args)
        self.logger = logging.getLogger("CoercedMailThread")
        self._coerce_call = call


class AccountMailThread(MailThread):
    '''
    Account Mail Thread.

    :param config: Config object
    :type config: :class:`DratsConfig`
    :param account: Account name
    :type account: str
    :raises: :class:`BadAccountSettingsError` if unable to parse account
             settings
    :raises: :class:`UnsupportedActionError` if an unsupported transfer is
             requested
    '''

    def __init__(self, config, account):
        settings = config.get("incoming_email", account)

        try:
            host, user, pasw, poll, ssl, port, action, enb = \
                settings.split(",", 7)
        except ValueError:
            raise BadAccountSettingsError(
                "Unable to parse account settings for `%s'" %
                account)

        actions = {
            _("Form") : self.create_form_from_mail,
            _("Chat") : self.do_chat_from_mail,
            }

        try:
            self.__action = actions[action]
        except KeyError:
            raise UnsupportedActionError("Unsupported action `%s' for %s@%s" %
                                         (action, user, host))

        ssl = ssl == "True"
        if not port:
            port = 995 if ssl else 110
        else:
            port = int(port)

        self._poll = int(poll)

        self.event = threading.Event()
        self.enabled = enb == "True"

        MailThread.__init__(self, config, host, user, pasw, port, ssl)
        self.logger = logging.getLogger("AccountMailThread")

    def do_chat_from_mail(self, mail):
        '''
        Do Chat from mail.

        :param mail: mail message
        :type mail: :class:`EmailMessage`
        '''
        if mail.is_multipart():
            body = None
            for part in mail.walk():
                html = None
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True)
                    break
                elif part.get_content_type() == "text/html":
                    html = part.get_payload(decode=True)
            if not body:
                body = html
        else:
            body = mail.get_payload()

        text = "Message from %s (%s):\r\n%s" % (\
            mail.get("From", "Unknown Sender"),
            mail.get("Subject", ""),
            body)

        for port in self.emit("get-station-list").keys():
            self._emit("user-send-chat", "CQCQCQ", port, text, False)

        event = main_events.Event(None,
                                  "Mail received from %s and sent via chat" % \
                                      mail.get("From", "Unknown Sender"))
        self._emit("event", event)

    def run(self):
        '''Run account mail thread.'''
        # Removing the connection check as it was always failing,
        # need to sort the scope of the variable
        # if self.config.getboolean("state", "connected_inet"):
        mails = []
        try:
            mails = self.fetch_mails()
        except (poplib.error_proto, ConnectionError, OSError) as err:
            self.message("Failed to retrieve messages: %s" % err)
        for mail in mails:
            self.__action(mail)
            if mails:
                event = main_events.Event(None,
                                          "Received %i email(s)" % len(mails))
                self._emit("event", event)
        # else:
        #     self.message("Not connected")


class PeriodicAccountMailThread(AccountMailThread):
    '''
    Periodic Account Mail Thread.

    :param config: Config object
    :type config: :class:`DratsConfig`
    :param account: Account name
    :type account: str
    :raises: :class:`BadAccountSettingsError` if unable to parse account
             settings
    :raises: :class:`UnsupportedActionError` if an unsupported transfer is
             requested
    '''

    def __init__(self, config, account):
        AccountMailThread.__init__(self, config, account)
        self.logger = logging.getLogger("PeriodicAccountMailThread")

    def run(self):
        '''Run periodic thread.'''
        self.message("Periodic thread starting")

        while self.enabled:
            AccountMailThread.run(self)
            self.event.wait(self._poll * 60)
            self.event.clear()

        self.message("Thread ending")

    def trigger(self):
        '''Trigger.'''
        self.event.set()

    def stop(self):
        '''Stop.'''
        self.enabled = False
        self.trigger()


def __validate_access(config, callsign, emailaddr, types):
    '''
    Validate Access internal.

    :param config: D-Rats configuration
    :type config: :class:`DratsConfig`
    :param callsign: call sign of outgoing message
    :type callsign: str
    :param emailaddr: Email address to send to
    :type emailaddr: str
    :param types: Types of access
    :type types: list[str]
    :returns: True if message is validated
    :rtype: bool
    '''
    logger = logging.getLogger("emailgw:validate_access")
    rules = config.options("email_access")

    for rule in rules:
        rulespec = config.get("email_access", rule)
        call, access, filter_rule = rulespec.split(",", 2)

        if call in [callsign, "*"] and re.search(filter_rule, emailaddr):
            # print "%s -> %s matches %s,%s,%s" % (callsign, emailaddr,
            #                                      call, access, filter)
            # print "Access types allowed: %s" % types
            return access in types
        # else:
            # print "%s -> %s does not match %s,%s,%s" % (callsign, emailaddr,
            #                                             call, access, filter)

    logger.info("No match found")

    return False


def validate_outgoing(config, callsign, emailaddr):
    '''
    Validate Outgoing message.

    :param config: config object
    :type config: :class:`DratsConfig`
    :param callsign: call sign of outgoing message
    :type callsign: str
    :param emailaddr: Email address to send to
    :type emailaddr: str
    :returns: True if message is validated
    :rtype: bool
    '''
    return __validate_access(config, callsign, emailaddr, ["Both", "Outgoing"])


def validate_incoming(config, callsign, emailaddr):
    '''
    Validate Incoming message.

    :param config: Config object
    :type config: :class:`DratsConfig`
    :param callsign: Call sign message is from
    :type callsign: str
    :param emailaddr: E-mail address of message
    :type emailaddr: str
    :returns: True if message is validated
    :rtype: bool
    '''
    return __validate_access(config, callsign, emailaddr, ["Both", "Incoming"])


def main():
    '''Unit test for emailgw.'''

    class Fakeout():
        '''Fake Object.'''

        form_source_dir = "forms"
        form_store_dir = "."

        def reg_form(self, *args):
            '''Reg Form dummy function.'''

        def list_add_form(self, *args, **kwargs):
            '''List add form dummy function.'''

        @staticmethod
        def get_stamp():
            '''Returns "FOO".'''
            return "FOO"

        # pylint: disable=fixme
        # Todo: This is just to get this unit test to not crash
        # Really need parameters for a test gateway as an option.
        # pylint: disable=no-self-use
        def getboolean(self, _section, _param):
            '''Get Boolean dummy function, returns False.'''
            return False


    # You may need to edit this based on if you actually have an agwpe
    # driver installed, or the port is in use.
    logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
                        datefmt="%m/%d/%Y %H:%M:%S",
                        level=logging.INFO)

    lang = gettext.translation("D-RATS",
                               localedir="./locale",
                               languages=["en"],
                               fallback=True)
    lang.install()

    #(self, config, host, user, pasw, port=110, ssl=False)
    mail_thread = MailThread(Fakeout(), "localhost", "foo", "bar")
    mail_thread.run()


if __name__ == "__main__":
    main()
