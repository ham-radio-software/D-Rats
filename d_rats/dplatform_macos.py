'''D-Rats Platform Mac OS.'''
#
# Copyright 2009 Dan Smith <dsmith@danplanet.com>
# review 2015 Maurizio Andreotti  <iz2lxi@yahoo.it>
# Copyright 2021-2023 John. E. Malmberg - Python3 Conversion
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
import glob
import os

from .dplatform_unix import UnixPlatform

if '_' not in locals():
    import gettext
    _ = gettext.gettext


class MacOSXPlatform(UnixPlatform):
    '''
    Mac OSX Platform.

    :param basepath: path to the configuration directory
    :type basepath: str
    '''

    def __init__(self, basepath):
        self.logger = logging.getLogger("MacOSXPlatform")
        # We need to make sure DISPLAY is set
        if "DISPLAY" not in os.environ:
            self.logger.info("Forcing DISPLAY for MacOS")
            os.environ["DISPLAY"] = ":0"

        os.environ["PANGO_RC_FILE"] = "../Resources/etc/pango/pangorc"

        UnixPlatform.__init__(self, basepath)

    def open_html_file(self, path):
        '''
        Open HTML File.

        :param path: file to open
        :type path: str
        '''
        self._unix_doublefork_run("open", path)

    def open_text_file(self, path):
        '''
        Open Text File for edit.

        :param path: Path to textfile
        :type path: str
        '''
        macos_textedit = "/Applications/TextEdit.app/Contents/MacOS/TextEdit"
        self._unix_doublefork_run(macos_textedit, path)

    def list_serial_ports(self):
        '''
        List Serial Ports.

        :returns: serial port names
        :rtype: list[str]
        '''
        keyspan = glob.glob("/dev/cu.KeySerial*")
        prolific = glob.glob("/dev/tty.usbserial*")

        return sorted(keyspan + prolific)

    def os_version_string(self):
        '''
        OS Version String.

        :returns: "MacOS X"
        :rtype: str
        '''
        return "MacOS X"

    def sys_data(self):
        '''
        The system application data directory.

        The system application data directory is used to locate the
        built in constant data for an application, and this will be
        assumed to be a read only directory after installation is complete.

        For most projects the packaging procedure and install will have
        a will have a parameter with "prefix" in its name to set this
        directory.

        :returns: Directory for built in application data.
        :rtype: str
        '''
        # See the Unix platform class for more details
        # Since many developers do not have MacOSX this needs
        # some diagnostics if it does not work.
        if self._sys_data:
            return self._sys_data
        if '/lib/' in __file__:
            my_prefix = __file__.split('/lib/')
            my_share = os.path.join(my_prefix[0], 'share', 'd-rats')
            if os.path.exists(my_share):
                # Using standard location or a VENV
                self._sys_data = my_share
                return self._sys_data
            mac_prefix = '../Resources'
            if os.path.exists(os.path.join('mac_prefix', 'ui')):
                self._sys_data = mac_prefix
                return self._sys_data
            self.logger.debug('Cannot find d-rats internal data files'
                              'Looked in %s and %s.',
                              my_share, mac_prefix)
        self._sys_data = self._base_dir
        return self._sys_data
