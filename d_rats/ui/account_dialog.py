#!/usr/bin/python
'''Account Dialog'''
#
# Copyright 2009 Dan Smith <dsmith@danplanet.com>
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

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from d_rats import miscwidgets
from d_rats import inputdialog


if not '_' in locals():
    import gettext
    _ = gettext.gettext


# This needs some improvement
# Should have a check to see if the config of the mail accounts has changed.
# also this is currently is apparently only used for querying if a remote
# d-rats station has undelivered messages for this host, as most of the
# information is not passed to the RPC session.

class AccountDialog:
    '''
    Account Dialog.

    :param config: Configuration data
    :type config: :class:`DratsConfig`
    '''

    HOST = 0
    USER = 1
    PASSWORD = 2
    USE_SSL = 3
    PORT = 4

    def __init__(self, config):
        self._config = config
        self._accounts = {}
        self._default_account = None
        self._fields = [None, None, None, None, None]
        self._dialog = None
        self._disable = None
        self._account = None

    @property
    def host(self):
        '''
        :returns: Host name
        :rtype: str
        '''
        return self._fields[self.HOST].get_text()

    @property
    def username(self):
        '''
        :returns username
        :rtype: str
        '''
        return self._fields[self.USER].get_text()

    @property
    def password(self):
        '''
        :returns: password
        :rtype: str
        '''
        return self._fields[self.PASSWORD].get_text()

    @property
    def use_ssl(self):
        '''
        :returns: True if use ssl
        :rtype: bool
        '''
        return bool(self._fields[self.USE_SSL].get_active())

    @property
    def port(self):
        '''
        :returns: Port number
        :rtype: int
        '''
        return int(self._fields[self.PORT].get_value())

    def _get_accounts(self):
        '''Get Dictionary of Accounts.'''

        for section in self._config.options("incoming_email"):
            info = self._config.get("incoming_email", section).split(",")
            key = "%s on %s" % (info[1], info[0])
            if not self._default_account:
                self._default_account = key
            self._accounts[key] = info

        wl2k_call = self._config.get("user", "callsign")
        wl2k_ssid = self._config.get("prefs", "msg_wl2k_ssid").strip()
        if wl2k_ssid:
            wl2k_call = "%s-%s" % (wl2k_call, wl2k_ssid)

        self._accounts["Other"] = ["", "", "", "", "", "110"]
        if not self._default_account:
            self._default_account = "Other"
        self._accounts["WL2K"] = ["@WL2K", wl2k_call, "", "", "", "0"]

    def _choose_account(self, box):
        '''
        Box Changed handler.

        :param box: ComboBoxText widget.
        :type box: :class:`Gtk.ComboBoxText`
        '''
        info = self._accounts[box.get_active_text()]
        for i in self._fields:
            i.set_sensitive(not info[0])
        self._fields[self.HOST].set_text(info[0])
        self._fields[self.USER].set_text(info[1])
        self._fields[self.PASSWORD].set_text(info[2])
        self._fields[self.USE_SSL].set_active(info[4] == "True")
        self._fields[self.PORT].set_value(int(info[5]))

    def _set_fields(self):
        '''
        Set Fields Internal.

        The field widgets need to be recreated fro each dialog run.
        '''
        if not self._accounts:
            self._get_accounts()

        account_list = list(self._accounts.keys())
        self._account = miscwidgets.make_choice(account_list, False,
                                                self._default_account)
        self._fields[self.HOST] = Gtk.Entry()
        self._fields[self.USER] = Gtk.Entry()
        self._fields[self.PASSWORD] = Gtk.Entry()
        self._fields[self.USE_SSL] = Gtk.CheckButton()
        self._fields[self.PORT] = Gtk.SpinButton()
        self._fields[self.PORT].set_adjustment(
            Gtk.Adjustment.new(110, 1, 65535, 1, 0, 0))
        self._fields[self.PORT].set_digits(0)

        self._fields[self.PASSWORD].set_visibility(False)

        self._account.connect("changed", self._choose_account)


    def _get_dialog(self):
        self._set_fields()

        self._dialog = inputdialog.FieldDialog(title=_("Select account"))
        self._dialog.add_field(_("Account"), self._account)
        self._dialog.add_field(_("Server"), self._fields[self.HOST])
        self._dialog.add_field(_("Username"), self._fields[self.USER])
        self._dialog.add_field(_("Password"), self._fields[self.PASSWORD])
        self._dialog.add_field(_("Use SSL"), self._fields[self.USE_SSL])
        self._dialog.add_field(_("Port"), self._fields[self.PORT])
        return self._dialog

    def prompt_for_account(self):
        '''
        Prompt for account.

        '''
        dialog = self._get_dialog()
        result = dialog.run()
        self._dialog = None
        dialog.destroy()
        if result == Gtk.ResponseType.OK:
            return True
        return False
