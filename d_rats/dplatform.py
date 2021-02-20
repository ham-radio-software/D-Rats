#!/usr/bin/python
'''D-Rats Platform'''
#
# Copyright 2009 Dan Smith <dsmith@danplanet.com>
# review 2015 Maurizio Andreotti  <iz2lxi@yahoo.it>
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
import sys
import glob
try:
    # pylint: disable=import-error
    import commands
except ModuleNotFoundError:
    pass
import subprocess
import six.moves.urllib.request
import six.moves.urllib.parse
import six.moves.urllib.error
from six.moves import range

#importing printlog() wrapper
from .debug import printlog


def find_me():
    '''Find Me'''
    return sys.modules["d_rats.dplatform"].__file__


class Platform():
    '''Platform'''

    def __init__(self, basepath):
        self._base = basepath
        self._source_dir = os.path.abspath(".")
        self._connected = True

    def __str__(self):
        text = ["Platform %s:" % str(self.__class__.__name__)]
        text.append("  base:       %s" % self.config_dir())
        text.append("  source_dir: %s" % self.source_dir())
        text.append("  OS version: %s" % self.os_version_string())

        return os.linesep.join(text)

    def config_dir(self):
        '''Config Directory'''
        return self._base

    def source_dir(self):
        '''Source Directory'''
        return self._source_dir

    def log_dir(self):
        '''Log Directory'''
        logdir = os.path.join(self.config_dir(), "logs")
        if not os.path.isdir(logdir):
            os.mkdir(logdir)

        return logdir

    # pylint: disable=no-self-use
    def filter_filename(self, filename):
        '''Filter Filename'''
        return filename

    def log_file(self, filename):
        '''Log file'''
        filename = self.filter_filename(filename + ".txt").replace(" ", "_")
        return os.path.join(self.log_dir(), filename)

    def config_file(self, filename):
        '''Config File'''
        return os.path.join(self.config_dir(),
                            self.filter_filename(filename))

    def open_text_file(self, path):
        '''Open Text File'''
        raise NotImplementedError("The base class can't do that")

    def open_html_file(self, path):
        '''Open HTML File'''
        raise NotImplementedError("The base class can't do that")

    # pylint: disable=no-self-use
    def list_serial_ports(self):
        '''List Serial Ports'''
        return []

    # pylint: disable=no-self-use
    def default_dir(self):
        '''Default Directory'''
        return "."

    # pylint: disable=no-self-use
    def gui_open_file(self, start_dir=None):
        '''GUI Open File'''
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        dlg = Gtk.FileChooserDialog(
            title="Select a file to open",
            action=Gtk.FileChooserAction.OPEN)
        dlg.add_buttons(_("Cancel"),
                        Gtk.ResponseType.CANCEL,
                        _("Open"), Gtk.ResponseType.OK)
        if start_dir and os.path.isdir(start_dir):
            dlg.set_current_folder(start_dir)

        res = dlg.run()
        fname = dlg.get_filename()
        dlg.destroy()

        if res == Gtk.ResponseType.OK:
            return fname
        return None

    # pylint: disable=no-self-use
    def gui_save_file(self, start_dir=None, default_name=None):
        '''GUI Save File'''
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        dlg = Gtk.FileChooserDialog(
            title="Save file as",
            action=Gtk.FileChooserAction.SAVE)
        dlg.add_buttons(_("Cancel"),
                        Gtk.ResponseType.CANCEL,
                        _("Save"), Gtk.ResponseType.OK)
        if start_dir and os.path.isdir(start_dir):
            dlg.set_current_folder(start_dir)

        if default_name:
            dlg.set_current_name(default_name)

        res = dlg.run()
        fname = dlg.get_filename()
        dlg.destroy()

        if res == Gtk.ResponseType.OK:
            return fname
        return None

    # pylint: disable=no-self-use
    def gui_select_dir(self, start_dir=None):
        '''Gui Select Directory'''
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        dlg = Gtk.FileChooserDialog(
            title="Choose folder",
            action=Gtk.FileChooserAction.SELECT_FOLDER)
        dlg.add_buttons(_("Cancel"),
                        Gtk.ResponseType.CANCEL,
                        _("Save"),
                        Gtk.ResponseType.OK)

        if start_dir and os.path.isdir(start_dir):
            dlg.set_current_folder(start_dir)

        res = dlg.run()
        fname = dlg.get_filename()
        dlg.destroy()

        if res == Gtk.ResponseType.OK and os.path.isdir(fname):
            return fname
        return None

    # pylint: disable=no-self-use
    def os_version_string(self):
        '''OS Version String'''
        return "Unknown Operating System"

    def run_sync(self, command):
        '''Run Sync'''
        pipe = subprocess.Popen(command, stdout=subprocess.PIPE)
        data = pipe.stdout.read()

        return 0, data

    def retrieve_url(self, url):
        '''Retrieve URL'''
        if self._connected:
            return six.moves.urllib.request.urlretrieve(url)

        raise Exception("Not connected")

    def set_connected(self, connected):
        '''Set Connected'''
        self._connected = connected

    # pylint: disable=no-self-use
    def play_sound(self, _soundfile):
        '''Play Sound'''
        printlog("dPlatform",
                 " : Sound is unsupported on this platform!")


class UnixPlatform(Platform):
    '''Unix Platform'''

    def __init__(self, basepath):
        if not basepath:
            basepath = os.path.abspath(os.path.join(self.default_dir(),
                                                    ".d-rats-ev"))

        if not os.path.isdir(basepath):
            os.mkdir(basepath)

        Platform.__init__(self, basepath)

    def source_dir(self):
        '''Source Directory'''
        if "site-packages" in find_me():
            return "/usr/share/d-rats"
        if "dist-packages" in find_me():
            return "/usr/share/d-rats"
        if "/usr/share/d-rats" in find_me():
            return "/usr/share/d-rats"
        return self._source_dir

    def default_dir(self):
        '''Default Directory'''
        return os.path.abspath(os.getenv("HOME"))

    def filter_filename(self, filename):
        '''Filter Filename'''
        return filename.replace("/", "")

    # pylint: disable=no-self-use
    def _unix_doublefork_run(self, *args):
        pid1 = os.fork()
        if pid1 == 0:
            pid2 = os.fork()
            if pid2 == 0:
                printlog("dPlatform", " : Exec'ing %s" % str(args))
                os.execlp(args[0], *args)
            else:
                sys.exit(0)
        else:
            os.waitpid(pid1, 0)
            printlog("dPlatform", " : Exec child exited")

    def open_text_file(self, path):
        '''Open Text File'''
        # pylint: disable=fixme
        # todo gedit to be moved as parameter in config
        printlog("dPlatform", " : received order to open in gedit %s s" % path)
        printlog("dPlatform",
                 " : if after this message your linux box crashes, " +
                 "please install gedit")
        self._unix_doublefork_run("gedit", path)

    def open_html_file(self, path):
        '''Open HTML file'''
        # pylint: disable=fixme
        # todo gedit to be moved as parameter in config
        printlog("dPlatform",
                 " : received order to open in firefox %s s" % path)
        printlog("dPlatform",
                 " : if after this message your linux box crashes, " +
                 "please install firefox")
        self._unix_doublefork_run("firefox", path)

    def list_serial_ports(self):
        '''List Serial Ports'''
        return sorted(glob.glob("/dev/ttyS*") + glob.glob("/dev/ttyUSB*"))

    def os_version_string(self):
        '''OS Version String'''
        # pylint: disable-msg=W0703
        try:
            issue = open("/etc/issue.net", "r")
            ver = issue.read().strip()
            issue.close()
            ver = "%s - %s" % (os.uname()[0], ver)
        except Exception:
            ver = " ".join(os.uname())
        return ver

    def run_sync(self, command):
        '''Run Sync'''
        return commands.getstatusoutput(command)

    def play_sound(self, soundfile):
        '''Play Sound'''
        import ossaudiodev
        import sndhdr

        try:
            (file_type, rate, channels, _f, bits) = sndhdr.what(soundfile)
        # pylint: disable=broad-except
        except Exception as err:
            printlog("dPlatform",
                     " : Unable to determine sound header of %s: %s" %
                     (soundfile, err))
            return

        if file_type != "wav":
            printlog("dPlatform",
                     " : Unable to play non-wav file %s" % soundfile)
            return

        if bits != 16:
            printlog("dPlatform",
                     " : Unable to support strange non-16-bit audio (%i)" %
                     bits)
            return

        dev = None
        try:
            dev = ossaudiodev.open("w")
            dev.setfmt(ossaudiodev.AFMT_S16_LE)
            dev.channels(channels)
            dev.speed(rate)

            file_handle = open(soundfile, "rb")
            dev.write(file_handle.read())
            file_handle.close()

            dev.close()
        # pylint: disable=broad-except
        except Exception as err:
            printlog("dPlatform",
                     " : Error playing sound %s: %s" % (soundfile, err))

        if dev:
            dev.close()


class MacOSXPlatform(UnixPlatform):
    '''Mac OSX Platform'''

    def __init__(self, basepath):
        # We need to make sure DISPLAY is set
        if "DISPLAY" not in os.environ:
            printlog("dPlatform", " :Forcing DISPLAY for MacOS")
            os.environ["DISPLAY"] = ":0"

        os.environ["PANGO_RC_FILE"] = "../Resources/etc/pango/pangorc"

        UnixPlatform.__init__(self, basepath)

    def open_html_file(self, path):
        '''Open HTML File'''
        self._unix_doublefork_run("open", path)

    def open_text_file(self, path):
        '''Open Text File'''
        macos_textedit = "/Applications/TextEdit.app/Contents/MacOS/TextEdit"
        self._unix_doublefork_run(macos_textedit, path)

    def list_serial_ports(self):
        '''List Serial Ports'''
        keyspan = glob.glob("/dev/cu.KeySerial*")
        prolific = glob.glob("/dev/tty.usbserial*")

        return sorted(keyspan + prolific)

    def os_version_string(self):
        '''OS Version String'''
        return "MacOS X"

    def source_dir(self):
        '''Source Directory'''
        if "site-packages" in find_me():
            return "../Resources"
        return self._source_dir


class Win32Platform(Platform):
    '''Win32 Platform'''

    def __init__(self, basepath=None):
        if not basepath:
            appdata = os.getenv("APPDATA")
            if not appdata:
                appdata = "C:\\"
            basepath = os.path.abspath(os.path.join(appdata, "D-RATS-EV"))

        if not os.path.isdir(basepath):
            os.mkdir(basepath)

        Platform.__init__(self, basepath)

    def default_dir(self):
        '''Default Directory'''
        return os.path.abspath(
            os.path.join(os.getenv("USERPROFILE"), "Desktop"))

    def filter_filename(self, filename):
        '''Filter Filename'''
        for char in "/\\:*?\"<>|":
            filename = filename.replace(char, "")

        return filename

    def open_text_file(self, path):
        '''Open Text File'''
        subprocess.Popen(["notepad", path])

    def open_html_file(self, path):
        '''Open Html File'''
        subprocess.Popen(["explorer", path])

    def list_serial_ports(self):
        '''List Serial Ports'''
        # pylint: disable=import-error
        import win32file
        import win32con

        ports = []
        for i in range(1, 257):
            try:
                portname = "COM%i" % i
                mode = win32con.GENERIC_READ | win32con.GENERIC_WRITE
                port = \
                    win32file.CreateFile(portname,
                                         mode,
                                         win32con.FILE_SHARE_READ,
                                         None,
                                         win32con.OPEN_EXISTING,
                                         0,
                                         None)
                ports.append(portname)
                win32file.CloseHandle(port)
                port = None
            # pylint: disable=broad-except
            except Exception:
                pass

        return ports

    def gui_open_file(self, start_dir=None):
        # pylint: disable=import-error
        import win32gui

        try:
            fname, _, _ = win32gui.GetOpenFileNameW()
        # pylint: disable=broad-except
        except Exception as err:
            printlog("dPlatform", " : Failed to get filename: %s" % err)
            return None

        return str(fname)

    def gui_save_file(self, start_dir=None, default_name=None):
        '''GUI Save File'''
        # pylint: disable=import-error
        import win32gui

        try:
            fname, _, _ = win32gui.GetSaveFileNameW(File=default_name)
        # pylint: disable=broad-except
        except Exception as err:
            printlog("dPlatform", " : Failed to get filename: %s" % err)
            return None

        return str(fname)

    def gui_select_dir(self, start_dir=None):
        '''GUI Select Dir'''
        # pylint: disable=import-error
        from win32com.shell import shell

        try:
            pidl, _, _ = shell.SHBrowseForFolder()
            fname = shell.SHGetPathFromIDList(pidl)
        # pylint: disable=broad-except
        except Exception as err:
            printlog("dPlatform", " : failed to get directory: %s" % err)
            return None

        return str(fname)

    def os_version_string(self):
        '''Os Version String'''
        # pylint: disable=import-error
        import win32api
        #platform: try to identify windows version
        vers = {"10.0": "Windows 10",
                "6.2": "Windows 8->10",
                "6.1": "Windows 7",
                "6.0": "Windows Vista",
                "5.2": "Windows XP 64-Bit",
                "5.1": "Windows XP",
                "5.0": "Windows 2000",
               }
        (pform, pver, _build, _, _) = win32api.GetVersionEx()
        return vers.get(str(pform) + "." + \
            str(pver), "Win32 (Unknown %i.%i)" % (pform, pver)) + \
            " " + str(win32api.GetVersionEx())

    def play_sound(self, soundfile):
        '''Play Sound'''
        # pylint: disable=import-error
        import winsound

        winsound.PlaySound(soundfile, winsound.SND_FILENAME)


def _get_platform(basepath):
    if os.name == "nt":
        return Win32Platform(basepath)
    if sys.platform == "darwin":
        return MacOSXPlatform(basepath)
    return UnixPlatform(basepath)


PLATFORM = None


def get_platform(basepath=None):
    '''Get Platform'''

    # pylint: disable=global-statement
    global PLATFORM

    if not PLATFORM:
        PLATFORM = _get_platform(basepath)

    return PLATFORM


def do_test():
    '''Unit Test'''
    __pform = get_platform()

    printlog("dPlatform", " : Config dir: %s" % __pform.config_dir())
    printlog("dPlatform", " : Default dir: %s" % __pform.default_dir())
    printlog("dPlatform", " : Log file (foo): %s" % __pform.log_file("foo"))
    printlog("dPlatform", " : Serial ports: %s" % __pform.list_serial_ports())
    printlog("dPlatform", " : OS Version: %s" % __pform.os_version_string())
 #  __pform.open_text_file("d-rats.py")

 #   printlog("dPlatform"," : Open file: %s" % __pform.gui_open_file())
 #   printlog("dPlatform"," : Save file: %s" % __pform.gui_save_file(default_name="Foo.txt"))
 #   printlog("dPlatform"," : Open folder: %s" % __pform.gui_select_dir("/tmp"))

if __name__ == "__main__":

    do_test()
