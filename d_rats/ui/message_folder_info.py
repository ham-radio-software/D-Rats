#!/usr/bin/python
'''Main Messages Message Folder Info.'''
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

import logging
import os

from glob import glob
from configparser import ConfigParser
from configparser import DuplicateSectionError
from configparser import NoOptionError
from configparser import NoSectionError


if not '_' in locals():
    import gettext
    _ = gettext.gettext


class MessageFolderInfo():
    '''
    Message Folder Info.

    :param folder_path: Folder to operate on
    :type folder_path: str
    '''
    _folder_cache = {}

    def __init__(self, folder_path):
        self._path = folder_path

        self.logger = logging.getLogger("MessageFolderInfo")
        if folder_path in self._folder_cache:
            self._database = self._folder_cache[folder_path]
        else:
            self._database = ConfigParser()
            reg_path = os.path.join(self._path, ".db")
            if os.path.exists(reg_path):
                self._database.read(reg_path)
            self._save()
            self._folder_cache[folder_path] = self._database

    @classmethod
    def _set_folder_cache(cls, path, database):
        '''
        Set Folder Cache.

        :param path: Path to folder
        :type path: str
        :param database: Database for folder
        :type database: :class:`ConfigParser`
        '''
        cls._folder_cache[path] = database

    def _save(self):
        reg_path = os.path.join(self._path, ".db")
        file_handle = open(reg_path, "w")
        self._database.write(file_handle)
        file_handle.close()

    def name(self):
        '''
        Folder Name.

        :returns: Current Folder name
        :rtype: str
        '''
        return os.path.basename(self._path)

    def _set_prop(self, filename, prop, value):
        filename = os.path.basename(filename)

        if not self._database.has_section(filename):
            self._database.add_section(filename)

        self._database.set(filename, prop, value)
        self._save()

    def _get_prop(self, filename, prop):
        filename = os.path.basename(filename)

        try:
            return self._database.get(filename, prop)
        except (NoOptionError, NoSectionError):
            return _("Unknown")

    def get_msg_subject(self, filename):
        '''
        Get message subject.

        :param filename: Filename for message
        :type filename: str
        :returns: Subject of message
        :rtype: str
        '''
        return self._get_prop(filename, "subject")

    def set_msg_subject(self, filename, subject):
        '''
        Set message subject.

        :param filename: Filename for message
        :type filename: str
        :param subject: Subject for message
        :type subject: str
        '''
        self._set_prop(filename, "subject", subject)

    def get_msg_type(self, filename):
        '''
        Get message type.

        :param filename: Filename for message
        :type filename: str
        :returns: Message Type
        :rtype: str
        '''
        return self._get_prop(filename, "type")

    def set_msg_type(self, filename, msg_type):
        '''
        Set message type.

        :param filename: Filename for message
        :type filename: str
        :param msg_type: Type of message
        :type msg_type: str
        '''
        self._set_prop(filename, "type", msg_type)

    def get_msg_read(self, filename):
        '''
        Get message read status.

        :param filename: Filename for message
        :type filename: str
        :returns: True if message has been read
        :rtype: bool
        '''
        val = self._get_prop(filename, "read")
        return val == "True"

    def set_msg_read(self, filename, read):
        '''
        Set message read status.

        :param filename: Filename of message
        :type filename: str
        :param read: True for message to be marked read
        :type read: bool
        '''
        self._set_prop(filename, "read", str(read))

    def get_msg_sender(self, filename):
        '''
        Get the message sender.

        :param filename: Filename of message
        :type filename: str
        :returns: Sender of message
        :rtype: str
        '''
        return self._get_prop(filename, "sender")

    def set_msg_sender(self, filename, sender):
        '''
        Set message sender.

        :param filename: Filename for message
        :type filename: str
        :param sender: Sender of message
        :type sender: str
        '''
        self._set_prop(filename, "sender", sender)

    def get_msg_recip(self, filename):
        '''
        Get the message recipient

        :param filename: Filename for message
        :type filename: str
        :returns: Message recipient
        :rtype: str
        '''
        return self._get_prop(filename, "recip")

    def set_msg_recip(self, filename, recip):
        '''
        Set the message recipient.

        :param filename: Filename for message
        :type filename: str
        :param recip: Recipient
        :type recip: str
        '''
        self._set_prop(filename, "recip", recip)

    def subfolders(self):
        '''
        Get the subfolders.

        :returns: subfolders of folder
        :rtype: list[:class:`MessageFolderInfo`]
        '''
        info = []

        entries = glob(os.path.join(self._path, "*"))
        for entry in sorted(entries):
            if entry in (".", ".."):
                continue
            if os.path.isdir(entry):
                info.append(MessageFolderInfo(entry))

        return info

    def files(self):
        '''
        List files.

        :returns: files in the folder.
        :rtype: list[str]
        '''
        file_list = glob(os.path.join(self._path, "*"))
        return [x_file for x_file in file_list
                if os.path.isfile(x_file) and not x_file.startswith(".")]

    def get_subfolder(self, name):
        '''
        Get subfolder information.

        :param name: Subfolder name
        :type name: str
        :returns: Subfolder information
        :rtype: :class:`MessageFolderInfo`
        '''
        for folder in self.subfolders():
            if folder.name() == name:
                return folder

        return None

    def create_subfolder(self, name):
        '''
        Create a subfolder by name

        :param name: Subfolder name
        :type name: str
        :returns: subfolder information
        :rtype: :class:`MessageFolderInfo`
        '''
        path = os.path.join(self._path, name)
        try:
            os.mkdir(path)
        except OSError as err:
            if err.errno != 17:  # File or directory exists
                raise
        return MessageFolderInfo(path)

    def delete_self(self):
        '''Delete Self.'''
        try:
            os.remove(os.path.join(self._path, ".db"))
        except OSError:
            pass # Don't freak if no .db
        os.rmdir(self._path)

    def create_msg(self, name):
        '''
        Create a message.

        Store the message name in the users configuration data

        :param name: Name for message path
        :type name: str
        :returns: Path for message
        :rtype: str
        :raises: DuplicateSectionError if the section already exists
        '''
        exists = os.path.exists(os.path.join(self._path, name))
        try:
            self._database.add_section(name)
        except DuplicateSectionError as err:
            if exists:
                raise err

        return os.path.join(self._path, name)

    def delete(self, filename):
        '''
        Delete a file.

        :param filename: filename to delete
        :type filename: str
        '''
        filename = os.path.basename(filename)
        self._database.remove_section(filename)
        os.remove(os.path.join(self._path, filename))

    def rename(self, new_name):
        '''
        Rename path

        :param new_name: New name for path
        :type new_name: str
        '''
        new_path = os.path.join(os.path.dirname(self._path), new_name)
        self.logger.info("Renaming %s -> %s", self._path, new_path)
        os.rename(self._path, new_path)
        self._path = new_path

    def __str__(self):
        return self.name()
