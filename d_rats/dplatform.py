'''D-Rats Platform.'''
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
import os
import sys

from .dplatform_generic import PlatformGeneric

if '_' not in locals():
    import gettext
    _ = gettext.gettext


class PlatformException(Exception):
    '''Generic Platform exception.'''


class NotConnectedError(PlatformException):
    '''Not connected Error.'''


# pylint just does not understand what we are doing here
# pylint: disable=abstract-method
class Platform(PlatformGeneric):
    '''
    Platform.

    :param basepath: Configuration data directory
    :type basepath: str
    '''
    logger = logging.getLogger("Platform")
    my_class = None

    def __init__(self, basepath):
        self.set_config_dir(basepath)
        PlatformGeneric.__init__(self, basepath)

    @classmethod
    def get_platform(cls, basepath=None):
        '''
        Get platform class object instance.

        There is always only one platform class instance.

        :param basepath: Optional basepath only used for first call.
        :type basepath: str
        :returns: Platform class instance
        :rtype: :class:`Platform`
        '''
        if cls.my_class:
            return cls.my_class
        # pylint: disable=import-outside-toplevel
        if os.name == "nt":
            from .dplatform_win32 import Win32Platform
            cls.my_class = Win32Platform(basepath)
        elif sys.platform == "darwin":
            from .dplatform_macos import MacOSXPlatform
            cls.my_class = MacOSXPlatform(basepath)
        else:
            from .dplatform_unix import UnixPlatform
            cls.my_class = UnixPlatform(basepath)

        return cls.my_class


def do_test():
    '''Unit Test.'''

    logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
                        datefmt="%m/%d/%Y %H:%M:%S",
                        level=logging.INFO)

    logger = logging.getLogger("dplatform")
    pform = Platform.get_platform()

    logger.info("Config dir: %s", pform.config_dir())
    logger.info("Default dir: %s", pform.default_dir())
    logger.info("Log file (foo): %s", pform.log_file("foo"))
    logger.info("Serial ports: %s", pform.list_serial_ports())
    logger.info("OS Version: %s", pform.os_version_string())
    logger.info("Built_in_data: %s", pform.sys_data())

    if len(sys.argv) > 1:

        pform.open_text_file("d-rats.py")

        logger.info("Open file: %s", pform.gui_open_file())
        logger.info("Save file: %s",
                    pform.gui_save_file(default_name="Foo.txt"))
        logger.info("Open folder: %s", pform.gui_select_dir("/tmp"))


if __name__ == "__main__":
    do_test()
