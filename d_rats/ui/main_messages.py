#!/usr/bin/python
'''Main Messages'''
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

import logging
import os
import time
import shutil
import random

from glob import glob

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from d_rats.ui.main_common import MainWindowTab
from d_rats.ui.main_common import prompt_for_station
from d_rats.ui.main_common import display_error
from d_rats.ui.main_common import set_toolbar_buttons
from d_rats.ui.message_folder_info import MessageFolderInfo
from d_rats.ui.message_folders import MessageFolders
from d_rats.ui.message_list import MessageList

from d_rats import inputdialog
from d_rats import formgui
from d_rats import signals
from d_rats import msgrouting


if not '_' in locals():
    import gettext
    _ = gettext.gettext


def mkmsgid(callsign):
    '''
    Generate a message id for a callsign.

    :param callsign: Callsign of station
    :rtype: str
    :returns: Message id
    :rtype: str
    '''
    r_num = random.SystemRandom().randint(0, 100000)
    return "%s.%x.%x" % (callsign, int(time.time()) - 1114880400, r_num)


class MessagesTab(MainWindowTab):
    '''
    Messages Tab.

    :param wtree: Object for tree
    :type wtree: :class:`Gtk.GtkNotebook`
    :param config: Configuration data
    :type config: :class:`DratsConfig`
    :param window: Mainwindow window widget
    :type: window: :class:`Gtk.ApplicationWindow`
    '''

    __gsignals__ = {
        "event" : signals.EVENT,
        "notice" : signals.NOTICE,
        "user-send-form" : signals.USER_SEND_FORM,
        "get-station-list" : signals.GET_STATION_LIST,
        "trigger-msg-router" : signals.TRIGGER_MSG_ROUTER,
        }

    _signals = __gsignals__

    def __init__(self, wtree, config, window):
        MainWindowTab.__init__(self, wtree, config, window=window, prefix="msg")

        self.logger = logging.getLogger("MessagesTab")
        self._init_toolbar()
        self._folders = MessageFolders(wtree, config)
        self._messages = MessageList(wtree, config)
        self._messages.connect("prompt-send-form", self._snd_msg)
        self._messages.connect("reply-form", self._rpl_msg)
        self._messages.connect("delete-form", self._del_msg)

        self._folders.connect("user-selected-folder",
                              lambda x, y: self._messages.open_folder(y))
        self._folders.select_folder(_("Inbox"))

        iport = self._wtree.get_object("main_menu_importmsg")
        iport.connect("activate", self._importmsg)

        eport = self._wtree.get_object("main_menu_exportmsg")
        eport.connect("activate", self._exportmsg)

    def _new_msg(self, _button, msg_type=None):
        '''
        New Message clicked handler.

        :param _button: Widget that was signaled, unused
        :type _button: :class:`Gtk.MenuToolButton`
        :param file_name: Filename for message, default None
        :type file_name: str
        '''
        types = glob(os.path.join(self._config.form_source_dir(), "*.xml"))

        forms = {}
        for file_name in types:
            forms[os.path.basename(file_name).replace(".xml", "")] = file_name

        if msg_type is None:
            parent = self._wtree.get_object("mainwindow")
            dialog = inputdialog.ChoiceDialog(forms.keys(),
                                              title=_("Choose a form"),
                                              parent=parent)
            result = dialog.run()
            msg_type = dialog.choice.get_active_text()
            dialog.destroy()
            if result != Gtk.ResponseType.OK:
                return

        current = self._messages.current_info.name()
        self._folders.select_folder(_("Drafts"))

        tstamp = time.strftime("form_%m%d%Y_%H%M%S.xml")
        newfn = self._messages.current_info.create_msg(tstamp)


        form = formgui.FormFile(forms[msg_type])
        call = self._config.get("user", "callsign")
        form.add_path_element(call)
        form.set_path_src(call)
        form.set_path_mid(mkmsgid(call))
        form.save_to(newfn)

        def close_msg_cb(response, info):
            if response == int(Gtk.ResponseType.CLOSE):
                info.delete(newfn)
            if self._messages.current_info == info:
                self._messages.refresh()
                self._folders.select_folder(current)

        self._messages.open_msg(newfn, True,
                                close_msg_cb, self._messages.current_info)

    def _set_rpl_msg_fields(self, old_form, new_form):
        '''
        Set Reply Message Fields.

        :param old_form: Incoming form for message
        :type old_form: :class:`formgui.FormFile`
        :param new_form: Reply message form
        :type new_form: :class:`formgui.FormFile`
        '''
        def subj_reply(subj):
            if "RE:" in subj.upper():
                return subj
            return "RE: %s" % subj

        def msg_reply(msg):
            if self._config.getboolean("prefs", "msg_include_reply"):
                return "--- Original Message ---\r\n\r\n" + msg
            return ""

        save_fields = [
            ("_auto_number", "_auto_number", lambda x: str(int(x)+1)),
            ("_auto_subject", "_auto_subject", subj_reply),
            ("subject", "subject", lambda x: "RE: %s" % x),
            ("message", "message", msg_reply),
            ("_auto_sender", "_auto_recip", None),
            ]

        for s_field, d_field, x_field in save_fields:
            old_val = old_form.get_field_value(s_field)
            if not old_val:
                continue

            if x_field:
                new_form.set_field_value(d_field, x_field(old_val))
            else:
                new_form.set_field_value(d_field, old_val)

    def _rpl_msg(self, _button, file_name=None):
        '''
        Reply to Message reply-form and clicked handler.

        :param _button: Widget that was signaled, unused
        :type _button: :class:`MessageList`, :class:`Gtk.MenuToolButton`
        :param file_name: Filename for message, default None
        :type file_name: str
        '''
        if not file_name:
            try:
                sel = self._messages.get_selected_messages()
            except TypeError:
                return

            if len(sel) > 1:
                self.logger.info("_rpl_msg: FIXME: Warn about multiple reply")
                return

            file_name = sel[0]

        current = self._messages.current_info.name()
        self._folders.select_folder(_("Drafts"))

        old_form = formgui.FormFile(file_name)
        tmpl = os.path.join(self._config.form_source_dir(),
                            "%s.xml" % old_form.ident)

        new_form = formgui.FormFile(tmpl)
        new_form.add_path_element(self._config.get("user", "callsign"))

        try:
            self._set_rpl_msg_fields(old_form, new_form)

        except formgui.FormguiFileMultipleIds:
            self.logger.info("_rpl_msg: Failed to do reply",
                             exc_info=True, stack_info=True)
            return

        if ";" in old_form.get_path_dst():
            rpath = ";".join(reversed(old_form.get_path()[:-1]))
            self.logger.info("_rpl_msg: rpath: %s (%s)",
                             rpath, old_form.get_path())
            new_form.set_path_dst(rpath)
        else:
            new_form.set_path_dst(old_form.get_path_src())

        call = self._config.get("user", "callsign")
        new_form.set_path_src(call)
        new_form.set_path_mid(mkmsgid(call))

        tstamp = time.strftime("form_%m%d%Y_%H%M%S.xml")
        newfn = self._messages.current_info.create_msg(tstamp)
        new_form.save_to(newfn)

        def close_msg_cb(response, info):
            if self._messages.current_info == info:
                self.logger.info("_rpl_msg: Response was %i (%i)",
                                 response, Gtk.ResponseType.CANCEL)
                if response in [Gtk.ResponseType.CANCEL,
                                Gtk.ResponseType.CLOSE]:
                    info.delete(newfn)
                    self._folders.select_folder(current)
                else:
                    self._messages.refresh(newfn)

        self._messages.open_msg(newfn, True,
                                close_msg_cb, self._messages.current_info)

    def _del_msg(self, _button, file_name=None):
        '''
        Delete Message delete-form and clicked handler.

        :param _button: Widget that was signaled, unused
        :type _button: :class:`MessageList`, :class:`Gtk.MenuToolButton`
        :param file_name: Filename for message, default None
        :type file_name: str
        '''
        if file_name:
            try:
                os.remove(file_name)
            except OSError as err:
                self.logger.info("_del_msg: Unable to delete %s: %s",
                                 file_name, err)
            self._messages.refresh()
        else:
            if self._messages.current_info.name() == _("Trash"):
                self._messages.delete_selected_messages()
            else:
                self._messages.move_selected_messages(_("Trash"))

    def _snd_msg(self, _button, file_name=None):
        '''
        Send Message prompt-send-form and clicked handler.

        :param _button: Widget that was signaled, unused
        :type _button: :class:`MessageList`, :class:`Gtk.MenuToolButton`
        :param file_name: Filename for message, default None
        :type file_name: str
        '''
        if not file_name:
            try:
                sel = self._messages.get_selected_messages()
            except TypeError:
                return

            if len(sel) > 1:
                self.logger.info("_snd_msg: FIXME: Warn about multiple send")
                return

            file_name = sel[0]
        recip = self._messages.current_info.get_msg_recip(file_name)

        if not msgrouting.msg_lock(file_name):
            display_error(_("Unable to send: message in use by another task"))
            return

        stations = []
        ports = self.emit("get-station-list")
        for slist in ports.values():
            stations += slist

        if recip in stations:
            stations.remove(recip)
        stations.insert(0, recip)

        station, port = prompt_for_station(stations, self._config)
        if not station:
            if msgrouting.msg_is_locked(file_name):
                msgrouting.msg_unlock(file_name)
            return

        self.emit("user-send-form", station, port, file_name, "foo")

        if msgrouting.msg_is_locked(file_name):
            msgrouting.msg_unlock(file_name)

    def _mrk_msg(self, _button, read):
        '''
        Mark Message clicked handler.

        :param _button: Widget that was signaled, unused
        :type _button: :class:`Gtk.MenuToolButton`
        :param read: Flag to mark read
        :type read: bool
        '''
        try:
            sel = self._messages.get_selected_messages()
        except TypeError:
            return

        for file_name in sel:
            self._messages.current_info.set_msg_read(file_name, read)

        self._messages.refresh()

    def _importmsg(self, _button):
        '''
        Import Message activate handler.

        :param _button: Widget that was signaled, unused
        :type _button: :class:`Gtk.GtkImageMenuItem`
        '''
        download_dir = self._config.get("prefs", "download_dir")
        file_name = self._config.platform.gui_open_file(download_dir)
        if not file_name:
            return

        dst = os.path.join(self._config.form_store_dir(),
                           _("Inbox"),
                           time.strftime("form_%m%d%Y_%H%M%S.xml"))

        shutil.copy(file_name, dst)
        self.refresh_if_folder(_("Inbox"))

    def _exportmsg(self, _button):
        '''
        Export Message activate handler.

        :param _button: Widget that was signaled, unused
        :type _button: :class:`Gtk.GtkImageMenuItem`
        '''
        try:
            sel = self._messages.get_selected_messages()
        except TypeError:
            return

        if len(sel) > 1:
            self.logger.info("_exportmsg: FIXME: Warn about multiple send")
            return
        if sel:
            return

        file_name = sel[0]

        download_dir = self._config.get("prefs", "download_dir")
        nfn = self._config.platform.gui_save_file(download_dir, "msg.xml")
        if not nfn:
            return

        shutil.copy(file_name, nfn)

    def _sndrcv(self, _button, account=""):
        '''
        Send Receive activate and clicked handler.

        :param _button: Widget that was signaled
        :type _button: :class:`Gtk.MenuItem`, :class:`Gtk.MenuToolButton`
        :param account: Account name, default ""
        :type account: str
        '''
        self.emit("trigger-msg-router", account)

    def _make_sndrcv_menu(self):
        menu = Gtk.Menu()

        menu_item = Gtk.MenuItem("Outbox")
        try:
            menu_item.set_tooltip_text("Send messages in the Outbox")
        except AttributeError:
            pass
        menu_item.connect("activate", self._sndrcv)
        menu_item.show()
        menu.append(menu_item)

        menu_item = Gtk.MenuItem("WL2K")
        try:
            menu_item.set_tooltip_text("Check Winlink messages")
        except AttributeError:
            pass
        menu_item.connect("activate", self._sndrcv, "@WL2K")
        menu_item.show()
        menu.append(menu_item)

        for section in self._config.options("incoming_email"):
            info = self._config.get("incoming_email", section).split(",")
            lab = "%s on %s" % (info[1], info[0])
            menu_item = Gtk.MenuItem(lab)
            try:
                menu_item.set_tooltip_text("Check for new mail on this account")
            except AttributeError:
                pass
            menu_item.connect("activate", self._sndrcv, section)
            menu_item.show()
            menu.append(menu_item)

        return menu

    def _make_new_menu(self):
        menu = Gtk.Menu()

        t_dir = self._config.form_source_dir()
        for file_i in sorted(glob(os.path.join(t_dir, "*.xml"))):
            msg_type = os.path.basename(file_i).replace(".xml", "")
            label = msg_type.replace("_", " ")
            menu_item = Gtk.MenuItem(label)
            try:
                menu_item.set_tooltip_text("Create a new %s form" % label)
            except AttributeError:
                pass
            menu_item.connect("activate", self._new_msg, msg_type)
            menu_item.show()
            menu.append(menu_item)

        return menu

    def _init_toolbar(self):
        toolbar = self._get_widget("toolbar")

        set_toolbar_buttons(self._config, toolbar)

        read = lambda msg: self._mrk_msg(msg, True)
        unread = lambda msg: self._mrk_msg(msg, False)

        buttons = [("msg-new.png", _("New"), self._new_msg),
                   ("msg-send-via.png", _("Forward"), self._snd_msg),
                   ("msg-reply.png", _("Reply"), self._rpl_msg),
                   ("msg-delete.png", _("Delete"), self._del_msg),
                   ("msg-markread.png", _("Mark Read"), read),
                   ("msg-markunread.png", _("Mark Unread"), unread),
                   ("msg-sendreceive.png", _("Send/Receive"), self._sndrcv),
                   ]

        tips = {
            _("New") : _("Create a new message for sending"),
            _("Forward") : _("Manually direct a message to another station"),
            _("Reply") : _("Reply to the currently selected message"),
            _("Delete") : _("Delete the currently selected message"),
            _("Mark Read") : _("Mark the currently selected message as read"),
            _("Mark Unread") : _("Mark the currently selected message as unread"),
            _("Send/Receive") : _("Send messages in the Outbox"),
            }

        menus = {
            "msg-new.png" : self._make_new_menu(),
            "msg-sendreceive.png" : self._make_sndrcv_menu(),
            }

        count = 0
        for button_i, button_l, button_f in buttons:
            icon = Gtk.Image()
            icon.set_from_pixbuf(self._config.ship_img(button_i))
            icon.show()
            if button_i in menus:
                item = Gtk.MenuToolButton.new(icon, button_l)
                item.set_menu(menus[button_i])
                try:
                    item.set_arrow_tooltip_text("%s %s %s" % (_("More"),
                                                              button_l,
                                                              _("Options")))
                except AttributeError:
                    pass
            else:
                item = Gtk.ToolButton.new(icon, button_l)
            item.show()
            item.connect("clicked", button_f)
            if button_l in tips:
                try:
                    item.set_tooltip_text(tips[button_l])
                except AttributeError:
                    pass
            toolbar.insert(item, count)
            count += 1

    def refresh_if_folder(self, folder):
        '''
        Refresh if folder is current.

        :param folder: Folder name to refresh
        :type folder: str
        '''
        self._notice()
        if self._messages.current_info.name() == folder:
            self._messages.refresh()

    def message_sent(self, file_name):
        '''
        Mark a message sent.

        :param file_name: Filename
        :type file_name: str
        '''
        outbox = self._folders.get_folder(_("Outbox"))
        files = outbox.files()
        if file_name in files:
            sent = self._folders.get_folder(_("Sent"))
            newfn = sent.create_msg(os.path.basename(file_name))
            self.logger.info("message_sent: Moving %s -> %s",
                             file_name, newfn)
            shutil.copy(file_name, newfn)
            outbox.delete(file_name)
            self.refresh_if_folder(_("Outbox"))
            self.refresh_if_folder(_("Sent"))
        else:
            self.logger.info("message_sent: Form %s sent but not in outbox",
                             os.path.basename(file_name))

    def get_shared_messages(self, _for_station):
        '''
        Get Shared Messages for a destination.

        :param for_station: Destination Station (Currently ignored)
        :type for_station: str
        :returns: list of message tuple of title, stamp, filename for
                  the destination
        :rtype: list[tuple[str, int, str]]
        '''
        shared = _("Inbox")
        path = os.path.join(self._config.platform.config_dir(), "messages")
        if not os.path.isdir(path):
            os.makedirs(path)
        info = MessageFolderInfo(os.path.join(path, shared))

        ret = []
        for file_name in info.files():
            stamp = os.stat(file_name).st_mtime
            ffn = "%s/%s" % (shared, os.path.basename(file_name))
            form = formgui.FormFile(file_name)
            ret.append((form.get_subject_string(), stamp, ffn))

        return ret

    def selected(self):
        '''Selected.'''
        MainWindowTab.selected(self)

        make_visible = ["main_menu_importmsg", "main_menu_exportmsg"]

        for name in make_visible:
            item = self._wtree.get_object(name)
            item.set_property("visible", True)

    def deselected(self):
        '''Deselected.'''
        MainWindowTab.deselected(self)

        make_invisible = ["main_menu_importmsg", "main_menu_exportmsg"]

        for name in make_invisible:
            item = self._wtree.get_object(name)
            item.set_property("visible", False)
