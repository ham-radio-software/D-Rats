'''Python Setup Module.'''
# Copyright 2008 Dan Smith <dsmith@danplanet.com>
# review 2015-2020 Maurizio Andreotti  <iz2lxi@yahoo.it>
# Copyright 2022 John. E. Malmberg - Python3 Conversion
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


from __future__ import absolute_import
from __future__ import print_function

import os
import sys

from d_rats.version import DRATS_VERSION

def win32_build():
    '''Microsoft Windows Build.'''
    from distutils.core import setup
    # pylint: disable=import-error, unused-import
    import py2exe # type: ignore

    try:
        # if this doesn't work, try import modulefinder
        import py2exe.mf as modulefinder # type: ignore
        import win32com  # type: ignore
        for path in win32com.__path__[1:]:
            modulefinder.AddPackagePath("win32com", path)
        for extra in ["win32com.shell"]: #,"win32com.mapi"
            __import__(extra)
            modules = sys.modules[extra]
            for path in modules.__path__[1:]:
                modulefinder.AddPackagePath(extra, path)
    except ImportError:
        # no build path setup, no worries.
        pass

    opts = {
        "py2exe" : {
            "includes" : "pango,atk,gobject,cairo,pangocairo" \
                         ",win32gui,win32com,win32com.shell" \
                         ",email.iterators,email.generator,gio" \
                         ",simplejson,six,xmlrpclib" \
                         ",SimpleXMLRPCServer,SocketServer" \
                         ",BaseHTTPServer",
            'dll_excludes': [
                'API-MS-Win-Core-Debug-L1-1-0.dll',
                'API-MS-Win-Core-DelayLoad-L1-1-0.dll',
                'API-MS-Win-Core-ErrorHandling-L1-1-0.dll',
                'API-MS-Win-Core-File-L1-1-0.dll',
                'API-MS-Win-Core-Handle-L1-1-0.dll',
                'API-MS-Win-Core-Heap-L1-1-0.dll',
                'API-MS-Win-Core-Interlocked-L1-1-0.dll',
                'API-MS-Win-Core-IO-L1-1-0.dll',
                'API-MS-Win-Core-LibraryLoader-L1-1-0.dll',
                'API-MS-Win-Core-Localization-L1-1-0.dll',
                'API-MS-Win-Core-LocalRegistry-L1-1-0.dll',
                'API-MS-Win-Core-Memory-L1-1-0.dll',
                'API-MS-Win-Core-Misc-L1-1-0.dll',
                'API-MS-Win-Core-ProcessEnvironment-L1-1-0.dll',
                'API-MS-Win-Core-ProcessThreads-L1-1-0.dll',
                'API-MS-Win-Core-Profile-L1-1-0.dll',
                'API-MS-Win-Core-String-L1-1-0.dll',
                'API-MS-Win-Core-Synch-L1-1-0.dll',
                'API-MS-Win-Core-SysInfo-L1-1-0.dll',
                'DNSAPI.DLL',
                'MSIMG32.DLL',
                'MSWSOCK.dll',
                'NSI.DLL',
                'USP10.DLL'
                ],
            "compressed" : 1,
            "optimize" : 2,
            "bundle_files" : 3,
            # "skip_archive" : True,
            # "packages" : ""
            }
        }

# Missing modules according to py3exe output
#
# 'BeautifulSoup', 'FCNTL', 'Image', 'PIL', 'System', 'System.IO.Ports',
# 'TERMIOS', '_scproxy', '_speedups', '_sysconfigdata', 'clr',
# 'django.utils.simplejson', 'django.utils.six.moves.urllib.parse', 'dl',
# 'email.MIMEBase', 'email.MIMEMultipart', 'email.MIMEText', 'email.Message',
# 'feedparser', 'gdk', 'importlib.find_loader', 'importlib.reload',
# 'importlib.util', 'ossaudiodev', 'pytz', 'simplejson._speedups', 'unix',
# 'urllib.parse', 'glib.GError', 'glib.IOChannel', 'glib.IO_ERR',
# 'glib.IO_FLAG_APPEND', 'glib.IO_FLAG_GET_MASK', 'glib.IO_FLAG_IS_READABLE',
# 'glib.IO_FLAG_IS_SEEKABLE', 'glib.IO_FLAG_IS_WRITEABLE',
# 'glib.IO_FLAG_MASK', 'glib.IO_FLAG_NONBLOCK', 'glib.IO_FLAG_SET_MASK',
# 'glib.IO_HUP', 'glib.IO_IN', 'glib.IO_NVAL', 'glib.IO_OUT', 'glib.IO_PRI',
# 'glib.IO_STATUS_AGAIN', 'glib.IO_STATUS_EOF', 'glib.IO_STATUS_ERROR',
# 'glib.IO_STATUS_NORMAL', 'glib.Idle', 'glib.MainContext',
# 'glib.MainLoop', 'glib.OPTION_ERROR', 'glib.OPTION_ERROR_BAD_VALUE',
# 'glib.OPTION_ERROR_FAILED', 'glib.OPTION_ERROR_UNKNOWN_OPTION',
# 'glib.OPTION_FLAG_FILENAME', 'glib.OPTION_FLAG_HIDDEN',
# 'glib.OPTION_FLAG_IN_MAIN', 'glib.OPTION_FLAG_NOALIAS',
# 'glib.OPTION_FLAG_NO_ARG', 'glib.OPTION_FLAG_OPTIONAL_ARG',
# 'glib.OPTION_FLAG_REVERSE', 'glib.OPTION_REMAINING', 'glib.OptionContext',
# 'glib.OptionGroup', 'glib.PRIORITY_DEFAULT', 'glib.PRIORITY_DEFAULT_IDLE',
# 'glib.PRIORITY_HIGH', 'glib.PRIORITY_HIGH_IDLE', 'glib.PRIORITY_LOW',
# 'glib.Pid', 'glib.PollFD', 'glib.SPAWN_CHILD_INHERITS_STDIN',
# 'glib.SPAWN_DO_NOT_REAP_CHILD', 'glib.SPAWN_FILE_AND_ARGV_ZERO',
# 'glib.SPAWN_LEAVE_DESCRIPTORS_OPEN', 'glib.SPAWN_SEARCH_PATH',
# 'glib.SPAWN_STDERR_TO_DEV_NULL', 'glib.SPAWN_STDOUT_TO_DEV_NULL',
# 'glib.Source', 'glib.Timeout', 'glib.child_watch_add',
# 'glib.filename_display_basename', 'glib.filename_display_name',
# 'glib.filename_from_utf8', 'glib.get_application_name',
# 'glib.get_current_time', 'glib.get_prgname', 'glib.glib_version',
# 'glib.idle_add', 'glib.io_add_watch', 'glib.main_context_default',
# 'glib.main_depth', 'glib.markup_escape_text', 'glib.set_application_name',
# 'glib.set_prgname', 'glib.source_remove', 'glib.spawn_async',
# 'glib.timeout_add', 'glib.timeout_add_seconds',
# 'glib.uri_list_extract_uris', 'gtk.Assistant']
#
    setup(
        windows=[{'script' : "d-rats.py",
                  'icon_resources': [(0x0004, 'd-rats2.ico')]},
                 {'script' : 'd-rats_repeater.py'}],
        # adapt the following line for your system
        data_files=["C:\\GTK\\bin\\jpeg62.dll"],
        options=opts)

def macos_build():
    '''Mac OS Build.'''
    from setuptools import setup
    import shutil

    # pylint: disable=invalid-name
    APP = ['d-rats-%s.py' % DRATS_VERSION]
    shutil.copy("d-rats", APP[0])
    # pylint: disable=invalid-name
    DATA_FILES = [('../Frameworks',
                   ['/opt/local/lib/libpangox-1.0.0.2203.1.dylib']),
                  ('../Resources/pango/1.6.0/modules',
                   ['/opt/local/lib/pango/1.6.0/modules/pango-basic-atsui.so']),
                  ('../Resources',
                   ['images', 'ui']),
                  ]
    # pylint: disable=invalid-name
    OPTIONS = {'argv_emulation': True, "includes" : "gtk,atk,pangocairo,cairo"}

    setup(
        app=APP,
        data_files=DATA_FILES,
        options={'py2app': OPTIONS},
        setup_requires=['py2app'],
        )

def default_build():
    '''Default Build.'''
    from distutils.core import setup
    from glob import glob

    desktop_files = glob("share/*.desktop")
    form_files = glob("forms/*.x?l")
    image_files = glob("images/*")
    image_files.append("d-rats2.ico")
    image_files.append("share/d-rats2.xpm")
    ui_files = glob("ui/*")
    _locale_files = glob("locale/*/LC_MESSAGES/D-RATS.mo")
    _man_files = glob("share/*.1")

    os.system("make -C libexec")

    man_files = []
    for fname in _man_files:
        os.system("gzip -c %s > %s" % (fname, fname + ".gz"))
        man_files.append(fname + ".gz")

    locale_files = []
    for fname in _locale_files:
        locale_files.append(("/usr/share/d-rats/%s" % os.path.dirname(fname),
                             [fname]))

    print(("LOC: %s" % str(ui_files)))

    setup(
        name="d-rats",
        description="D-RATS",
        long_description="A communications tool for D-STAR",
        author="Dan Smith, KK7DS until v0.3.3, then Maurizio Andreotti IZ2LXI ",
        author_email="iz2lxi@yahoo.it",
        packages=["d_rats", "d_rats.map", "d_rats.ui", "d_rats.sessions"],
        version=DRATS_VERSION,
        scripts=["d-rats.py", "d-rats_repeater.py"],
        data_files=[('/usr/share/applications', desktop_files),
                    ('/usr/share/icons', ["share/d-rats2.xpm"]),
                    ('/usr/share/d-rats/forms', form_files),
                    ('/usr/share/d-rats/images', image_files),
                    ('/usr/share/d-rats/ui', ui_files),
                    ('/usr/share/d-rats/libexec', ["libexec/lzhuf"]),
                    ('/usr/share/man/man1', man_files),
                    ('/usr/share/doc/d-rats', ['COPYING']),
                    ] + locale_files)

if sys.platform == "darwin":
    macos_build()
elif sys.platform == "win32":
    win32_build()
else:
    default_build()
