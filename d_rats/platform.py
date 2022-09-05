#!/usr/bin/python
#
# Copyright 2008 Dan Smith <dsmith@danplanet.com>
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

#importing printlog() wrapper
from .debug import printlog


import os
import sys
import glob
try:
    # pylint: disable=import-error
    import commands
except ModuleNotFoundError:
    pass
import subprocess
import six.moves.urllib.request, six.moves.urllib.parse, six.moves.urllib.error
from six.moves import range

def find_me():
    return sys.modules["d_rats.platform"].__file__

class Platform(object):
    # pylint: disable-msg=R0201

    def __init__(self, basepath):
        self._base = basepath
        self._source_dir = os.path.abspath(".")
        self._connected = True

    def __str__(self):
        l = ["Platform %s:" % str(self.__class__.__name__)]
        l.append("  base:       %s" % self.config_dir())
        l.append("  source_dir: %s" % self.source_dir())
        l.append("  OS version: %s" % self.os_version_string())

        return os.linesep.join(l)

    def config_dir(self):
        return self._base

    def source_dir(self):
        return self._source_dir

    def log_dir(self):
        logdir = os.path.join(self.config_dir(), "logs")
        if not os.path.isdir(logdir):
            os.mkdir(logdir)

        return logdir

    def filter_filename(self, filename):
        return filename

    def log_file(self, filename):
        filename = self.filter_filename(filename + ".txt").replace(" ", "_")
        return os.path.join(self.log_dir(), filename)

    def config_file(self, filename):
        return os.path.join(self.config_dir(),
                            self.filter_filename(filename))

    def open_text_file(self, path):
        raise NotImplementedError("The base class can't do that")

    def open_html_file(self, path):
        raise NotImplementedError("The base class can't do that")

    def list_serial_ports(self):
        return []

    def default_dir(self):
        return "."

    def gui_open_file(self, start_dir=None):
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        dlg = Gtk.FileChooserDialog.new("Select a file to open",
                                        None,
                                        Gtk.FileChooserAction.OPEN,
                                        (Gtk.ButtonsType.CANCEL,
                                         Gtk.ResponseType.CANCEL,
                                         _("Open"), Gtk.ResponseType.OK))
        if start_dir and os.path.isdir(start_dir):
            dlg.set_current_folder(start_dir)

        res = dlg.run()
        fname = dlg.get_filename()
        dlg.destroy()

        if res == Gtk.ResponseType.OK:
            return fname
        else:
            return None

    def gui_save_file(self, start_dir=None, default_name=None):
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        dlg = Gtk.FileChooserDialog.new("Save file as",
                                        None,
                                        Gtk.FileChooserAction.SAVE,
                                        (Gtk.ButtonsType.CANCEL,
                                         Gtk.ResponseType.CANCEL,
                                         _("Save"), Gtk.ResponseType.OK))
        if start_dir and os.path.isdir(start_dir):
            dlg.set_current_folder(start_dir)

        if default_name:
            dlg.set_current_name(default_name)

        res = dlg.run()
        fname = dlg.get_filename()
        dlg.destroy()

        if res == Gtk.ResponseType.OK:
            return fname
        else:
            return None

    def gui_select_dir(self, start_dir=None):
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        dlg = Gtk.FileChooserDialog.new("Choose folder",
                                        None,
                                        Gtk.FileChooserAction.SELECT_FOLDER,
                                        (Gtk.ButtonsType.CANCEL,
                                         Gtk.ResponseType.CANCEL,
                                         _("Save"), Gtk.ResponseType.OK))
        if start_dir and os.path.isdir(start_dir):
            dlg.set_current_folder(start_dir)

        res = dlg.run()
        fname = dlg.get_filename()
        dlg.destroy()

        if res == Gtk.ResponseType.OK and os.path.isdir(fname):
            return fname
        else:
            return None

    def os_version_string(self):
        return "Unknown Operating System"

    def run_sync(self, command):
        pipe = subprocess.Popen(command, stdout=subprocess.PIPE)
        data = pipe.stdout.read()

        return 0, data

    def retrieve_url(self, url):
        if self._connected:
            return six.moves.urllib.request.urlretrieve(url)

        raise Exception("Not connected")

    def set_connected(self, connected):
        self._connected = connected

    def play_sound(self, soundfile):
        printlog("Platform","  : Sound is unsupported on this platform!")

class UnixPlatform(Platform):
    def __init__(self, basepath):
        if not basepath:
            basepath = os.path.abspath(os.path.join(self.default_dir(),
                                                    ".d-rats"))
        
        if not os.path.isdir(basepath):
            os.mkdir(basepath)

        Platform.__init__(self, basepath)

    def source_dir(self):
        if "site-packages" in find_me():
            return "/usr/share/d-rats"
        elif "dist-packages" in find_me():
            return "/usr/share/d-rats"
        elif "pymodules" in find_me():
            return "/usr/share/d-rats"
        elif "pyshared" in find_me():
            return "/usr/share/d-rats"
        elif "/usr/share/d-rats" in find_me():
            return "/usr/share/d-rats"
        else:
            return self._source_dir

    def default_dir(self):
        return os.path.abspath(os.getenv("HOME"))

    def filter_filename(self, filename):
        return filename.replace("/", "")

    def _unix_doublefork_run(self, *args):
        pid1 = os.fork()
        if pid1 == 0:
            pid2 = os.fork()
            if pid2 == 0:
                printlog("Platform","  : Exec'ing %s" % str(args))
                os.execlp(args[0], *args)
            else:
                sys.exit(0)
        else:
            os.waitpid(pid1, 0)
            printlog("Platform","  : Exec child exited")

    def open_text_file(self, path):
        self._unix_doublefork_run("gedit", path)

    def open_html_file(self, path):
        self._unix_doublefork_run("firefox", path)

    def list_serial_ports(self):
        return sorted(glob.glob("/dev/ttyS*") + glob.glob("/dev/ttyUSB*"))

    def os_version_string(self):
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
        return commands.getstatusoutput(command)

    def play_sound(self, soundfile):
        import ossaudiodev
        import sndhdr

        try:
            (t, r, c, f, b) = sndhdr.what(soundfile)
        except Exception as e:
            printlog("Platform","  : Unable to determine sound header of %s: %s" % (soundfile, e))
            return

        if t != "wav":
            printlog("Platform","  : Unable to play non-wav file %s" % soundfile)
            return

        if b != 16:
            printlog("Platform","  : Unable to support strange non-16-bit audio (%i)" % b)
            return

        dev = None
        try:
            dev = ossaudiodev.open("w")
            dev.setfmt(ossaudiodev.AFMT_S16_LE)
            dev.channels(c)
            dev.speed(r)

            f = open(soundfile, "rb")
            dev.write(f.read())
            f.close()

            dev.close()
        except Exception as e:
            printlog("Platform","  : Error playing sound %s: %s" % (soundfile, e))
        
        if dev:
            dev.close()

class MacOSXPlatform(UnixPlatform):
    def __init__(self, basepath):
        # We need to make sure DISPLAY is set
        if "DISPLAY" not in os.environ:
            printlog("Platform","  : Forcing DISPLAY for MacOS")
            os.environ["DISPLAY"] = ":0"

        os.environ["PANGO_RC_FILE"] = "../Resources/etc/pango/pangorc"

        UnixPlatform.__init__(self, basepath)

    def open_html_file(self, path):
        self._unix_doublefork_run("open", path)

    def open_text_file(self, path):
        macos_textedit = "/Applications/TextEdit.app/Contents/MacOS/TextEdit"
        self._unix_doublefork_run(macos_textedit, path)

    def list_serial_ports(self):
        keyspan = glob.glob("/dev/cu.KeySerial*")
        prolific = glob.glob("/dev/tty.usbserial*")

        return sorted(keyspan + prolific)

    def os_version_string(self):
        return "MacOS X"

    def source_dir(self):
        app_res = os.path.join(os.path.dirname(find_me()),
                               "..", # d-rats
                               "..", # Resources
                               "..", # Contents
                               "Resources")
        if os.path.isdir(app_res):
            return app_res
        else:
            return self._source_dir

class Win32Platform(Platform):
    def __init__(self, basepath=None):
        if not basepath:
            appdata = os.getenv("APPDATA")
            if not appdata:
                appdata = "C:\\"
            basepath = os.path.abspath(os.path.join(appdata, "D-RATS"))

        if not os.path.isdir(basepath):
            os.mkdir(basepath)

        Platform.__init__(self, basepath)

    def default_dir(self):
        return os.path.abspath(os.path.join(os.getenv("USERPROFILE"),
                                            "Desktop"))

    def filter_filename(self, filename):
        for char in "/\\:*?\"<>|":
            filename = filename.replace(char, "")

        return filename

    def open_text_file(self, path):
        subprocess.Popen(["notepad", path])
        return

    def open_html_file(self, path):
        subprocess.Popen(["explorer", path])
    
    def list_serial_ports(self):
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
            except Exception:
                pass

        return ports

    def gui_open_file(self, start_dir=None):
        # pylint: disable-msg=W0703,W0613
        # pylint: disable=import-error
        import win32gui

        try:
            fname, _, _ = win32gui.GetOpenFileNameW()
        except Exception as e:
            printlog("Platform","  : Failed to get filename: %s" % e)
            return None

        return str(fname)

    def gui_save_file(self, start_dir=None, default_name=None):
        # pylint: disable-msg=W0703,W0613
        # pylint: disable=import-error
        import win32gui

        try:
            fname, _, _ = win32gui.GetSaveFileNameW(File=default_name)
        except Exception as e:
            printlog("Platform","  : Failed to get filename: %s" % e)
            return None

        return str(fname)

    def gui_select_dir(self, start_dir=None):
        # pylint: disable-msg=W0703,W0613
        # pylint: disable=import-error
        from win32com.shell import shell

        try:
            pidl, _, _ = shell.SHBrowseForFolder()
            fname = shell.SHGetPathFromIDList(pidl)
        except Exception as e:
            printlog("Platform","  : Failed to get directory: %s" % e)
            return None

        return str(fname)

    def os_version_string(self):
        # pylint: disable=import-error
        import win32api

        vers = { 4: "Windows 2000",
                 5: "Windows XP",
                 6: "Windows Vista",
                 7: "Windows 7",
                 }

        (pform, _, build, _, _) = win32api.GetVersionEx()

        return vers.get(pform, "Win32 (Unknown %i:%i)" % (pform, build))

    def play_sound(self, soundfile):
        # pylint: disable=import-error
        import winsound

        winsound.PlaySound(soundfile, winsound.SND_FILENAME)

def _get_platform(basepath):
    if os.name == "nt":
        return Win32Platform(basepath)
    elif sys.platform == "darwin":
        return MacOSXPlatform(basepath)
    else:
        return UnixPlatform(basepath)

PLATFORM = None
def get_platform(basepath=None):
    #pylint: disable-msg=W0602

    global PLATFORM

    if not PLATFORM:
        PLATFORM = _get_platform(basepath)

    return PLATFORM

if __name__ == "__main__":
    def do_test():
        __pform = get_platform()

        printlog("Platform","  : Config dir: %s" % __pform.config_dir())
        printlog("Platform","  : Default dir: %s" % __pform.default_dir())
        printlog("Platform","  : Log file (foo): %s" % __pform.log_file("foo"))
        printlog("Platform","  : Serial ports: %s" % __pform.list_serial_ports())
        printlog("Platform","  : OS Version: %s" % __pform.os_version_string())
        #__pform.open_text_file("d-rats.py")

        #print "Open file: %s" % __pform.gui_open_file()
        #print "Save file: %s" % __pform.gui_save_file(default_name="Foo.txt")
        #print "Open folder: %s" % __pform.gui_select_dir("/tmp")

    do_test()
