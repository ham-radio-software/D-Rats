'''D-Rats Platform Win32.'''
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
import mimetypes
import os

# There has been some problems with various Windows Python
# implementations in the past.  Having these modules may make
# D-Rats harder to use.  There are some hacks like manually
# editing configuration files to allow testing.
# The type: ignore is needed for pylance not handling cross-platform checks
try:
    import win32api # type: ignore
except ImportError:
    pass
try:
    import pywintypes # type: ignore
except ImportError:
    pass
try:
    from win32com.shell import shell # type: ignore
except ImportError:
    pass
try:
    import win32con # type: ignore
except ImportError:
    pass
try:
    import win32file # type: ignore
except ImportError:
    pass
try:
    import win32gui # type: ignore
except ImportError:
    pass
HAVE_AUDIO = False
try:
    import winsound # type: ignore
    HAVE_AUDIO = True
except ImportError:
    pass


if '_' not in locals():
    import gettext
    _ = gettext.gettext


from .dplatform_generic import PlatformGeneric

class Win32Platform(PlatformGeneric):
    '''
    Win32 Platform.

    :param basepath, default is "%APPDATA%\\D-RATS-EV"
    :type basepath: str
    '''
    logger = logging.getLogger("Win32Platform")

    def __init__(self, basepath=None):
        self.set_config_dir(basepath)
        PlatformGeneric.__init__(self, basepath)

    def set_config_dir(self, basepath):
        '''
        Set the base directory.

        :param basepath: Base directory
        :type basepath: str
        '''
        if not basepath:
            appdata = os.getenv("APPDATA")
            if not appdata:
                appdata = "C:\\"
            basepath = os.path.abspath(os.path.join(appdata, "D-RATS-EV"))

        if not os.path.isdir(basepath):
            os.makedirs(basepath, exist_ok=True)
        self._base = basepath

    def default_dir(self):
        '''
        Default Directory.

        :returns: default directory
        :rtype: str
        '''
        return os.path.abspath(
            os.path.join(os.getenv("USERPROFILE"), "Desktop"))

    def filter_filename(self, filename):
        '''
        Filter Filename.

        :param filename: filename to use
        :type filename: str
        :returns: filename filtered for platform.
        :rtype: str
        '''
        for char in "/\\:*?\"<>|":
            filename = filename.replace(char, "")

        return filename

    def list_serial_ports(self):
        '''
        List Serial Ports.

        :returns: List of serial ports
        :rtype: list[str]
        '''
        ports = []
        try:
            for i in range(1, 257):
                try:
                    portname = "COM%i" % i
                    mode = win32con.GENERIC_READ  # type: ignore
                    mode |= win32con.GENERIC_WRITE  # type: ignore
                    port = win32file.CreateFile(  # type: ignore
                        portname,
                        mode,
                        win32con.FILE_SHARE_READ,  # type: ignore
                        None,
                        win32con.OPEN_EXISTING,  # type: ignore
                        0,
                        None)
                    ports.append(portname)
                    win32file.CloseHandle(port)  # type: ignore
                    port = None

                except pywintypes.error as err:  # type: ignore
                    # Error code 5 Apparently if the serial port is in use.
                    if err.args[0] not in [2, 5]:
                        self.logger.info("list_serial_ports", exc_info=True)
        except NameError:
            self.logger.info("Unable to look up serial ports, "
                             "win32con or other python package missing!")
        return ports

    @staticmethod
    def _mime_to_filter(mime_types):
        '''
        Mime types to Microsoft Fitering.

        :param mime_types: A list of wanted mime types
        :type mime_type: list[str]
        :returns: Microsoft file filter string
        :rtype: str
        '''
        if not mime_types:
            return None
        filter=''
        for mime_type in mime_types:
            exts = mimetypes.guess_all_extensions(mime_type, strict=True)
            ext_str = ''
            for ext in exts:
                ext_str = '*' + ext + ';'
            if ext_str:
                new_filter = mime_type + '\\0' + ext_str + '\\0'
                filter += new_filter
        if filter:
            return filter
        return None

    def gui_open_file(self, mime_types=None, start_dir=None):
        '''
        GUI open file.

        :param mime_types: Optional Mime types to filter
        :type mime_types: list[str]
        :param start_dir: Directory to start in, default None
        :type start_dir: str
        :returns: Filename to open or none.
        :rtype: str
        '''
        win_filter = self._mime_to_filter(mime_types=mime_types)
        try:
            fname, _filter, __flags = \
                win32gui.GetOpenFileNameW(Filter=win_filter)  # type: ignore
            return str(fname)
        except pywintypes.error as err:  # type: ignore
            self.logger.info("gui_open_file: Failed to get filename: %s", err)
        except NameError:
            self.logger.info("Cannot open file, "
                             "win32gui or other python packages missing!")
        return None


    def gui_save_file(self, mime_types=None, start_dir=None, default_name=None):
        '''
        GUI Save File.

        :param mime_types: Optional Mime types to filter
        :type mime_types: list[str]
        :param start_dir: directory to start in, default None
        :type default_name: str
        :returns: filename to save to or None
        :rtype: str
        '''
        win_filter = self._mime_to_filter(mime_types)
        try:
            fname, _filter, _flags = \
                win32gui.GetSaveFileNameW(File=default_name,
                                          Filter=win_filter)  # type: ignore
            return str(fname)
        except pywintypes.error as err:  # type: ignore
            self.logger.info("gui_save_file: Failed to get filename: %s", err)
        except NameError:
            self.logger.info("Cannot open file, "
                             "win32gui or other python packages missing!")
        return None

    def gui_select_dir(self, start_dir=None):
        '''
        GUI Select Dir.

        :param start_dir: directory to start in, default None
        :type start_dir: str
        :returns: selected directory or None
        :rtype: str
        '''
        pidl = None
        try:
            try:
                err = "No error detected"
                pidl, _display_name, _ilmage_list = \
                    shell.SHBrowseForFolder()  # type: ignore
            except pywintypes.com_error:  # type: ignore
                pass
            if not pidl:
                self.logger.info("gui_select_dir: failed to get directory: %s",
                                 err)
                return None
            fname = shell.SHGetPathFromIDList(pidl)  # type: ignore
            if not isinstance(fname, str):
                fname = fname.decode('utf-8', 'replace')
            return str(fname)
        except NameError:
            self.logger.info("Cannot open file, "
                             "win32com or other python packages missing!")
        return None

    def os_version_string(self):
        '''
        Os Version String.

        :returns: Platform version string
        :rtype: str
        '''
        vers = {"11.0": "Windows 11",
                "10.0": "Windows 10",
                "6.2": "Windows 8->10",
                "6.1": "Windows 7",
                "6.0": "Windows Vista",
                "5.2": "Windows XP 64-Bit",
                "5.1": "Windows XP",
                "5.0": "Windows 2000",
               }
        (major_version, minor_version, _build_number, _platform_id, _version) \
            = win32api.GetVersionEx() # type: ignore
        try:
            return vers.get(str(major_version) + "." + str(minor_version),
                            "Win32 (Unknown %i.%i)" %
                            (major_version, minor_version)) + \
                            " " + str(win32api.GetVersionEx()) # type: ignore
        except NameError:
            self.logger.info("Cannot Get Windows Version, "
                             "win32api or other python packages missing!")
        return "Windows Unknown."

    @staticmethod
    def have_sound():
        '''
        Do we have sound support?

        :returns: Status of sound support
        :rytpe: bool
        '''
        return HAVE_AUDIO

    def play_sound(self, soundfile):
        '''
        Play Sound.

        :param soundfile: file to play sound from
        :type soundfile: str
        '''
        if not HAVE_AUDIO:
            self.logger.info("play_sound: "
                             "winsound not installed!")

        winsound.PlaySound(soundfile,              # type: ignore
                           winsound.SND_FILENAME)  # type: ignore
