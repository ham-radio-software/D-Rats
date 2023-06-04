'''D-Rats Platform for Unix.'''
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
import subprocess

from .dplatform_generic import PlatformGeneric

if '_' not in locals():
    import gettext
    _ = gettext.gettext


class UnixPlatform(PlatformGeneric):
    '''
    Unix Platform.

    :param basepath: Path to store the configuration file,
                     default "~/.d-rats-ev"
    :type basepath: str
    '''
    logger = logging.getLogger("UnixPlatform")

    def __init__(self, basepath):
        self.set_config_dir(basepath)
        PlatformGeneric.__init__(self, basepath)

    def set_config_dir(self, basepath):
        '''
        Set the base directory.

        :param basepath: Base directory
        :type basepath: str
        '''
        if not basepath:
            basepath = os.path.abspath(os.path.join(self.default_dir(),
                                                    ".d-rats-ev"))
        if not os.path.isdir(basepath):
            os.makedirs(basepath, exist_ok=True)
        self._base = basepath

    def default_dir(self):
        '''
        Default Directory.

        :returns: Default directory path
        :rtype: str
        '''
        return os.path.abspath(os.getenv("HOME"))

    @staticmethod
    def filter_filename(filename):
        '''
        Filter Filename.

        :param filename: Source filename
        :type filename: str
        :returns: filename adjusted for platform
        :rtype: str
        '''
        return filename.replace("/", "")

    def list_serial_ports(self):
        '''
        List Serial Ports.

        :returns: The serial ports
        :rtype: list of str
        '''
        return sorted(glob.glob("/dev/ttyS*") + glob.glob("/dev/ttyUSB*"))

    def os_version_string(self):
        '''
        OS Version String.

        :returns: a version string for the OS
        :rtype: str
        '''
        # There should be a more portable way to get the version string.
        try:
            issue = open("/etc/issue.net", "r")
            ver = issue.read().strip()
            issue.close()
            ver = "%s - %s" % (os.uname()[0], ver)
        except IOError as err:
            if err.errno == 2:  # No such file or directory
                # Linux use of this file seems to be deprecated.
                pass
            ver = " ".join(os.uname())
        return ver

    @staticmethod
    def run_sync(command):
        '''
        Run Sync.

        :param command: Command to run.
        :type command: str
        :returns: Command status and output
        :rtype: tuple[int, str]
        '''
        return subprocess.getstatusoutput(command)
