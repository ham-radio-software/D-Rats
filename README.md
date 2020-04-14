-----------------------
D-RATS
-----------------------
D-RATS is a communications tool for D-STAR amateur radio low-speed data (DV mode). It provides: Multi-user chat capabilities; File transfers Structured data transport (forms); and Position tracking and mapping.

-----------------------
Copyright note
-----------------------
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

-----------------------
Original Author
-----------------------
Dan Smith (KK7DS)

-----------------------
Maintainer 
-----------------------
Maurizio Andreotti IZ2LXI

-----------------------
Introduction
-----------------------
D-Rats is a study version of the D-Rats 0.3.3. originally developed and 
Copyrighted by 2008 Dan Smith <dsmith@danplanet.com> and later reviewed in 2015, 2019 and 2020 by me, Maurizio Andreotti

The idea here is to read the source, add some comments and eventually do some modifications.

-----------------------
Supported systems
-----------------------
This program ONLY work with older Linux distributions that still include Python2, GTK2, etc.
Support for this program on newer distros is NOT possible until major porting work is completed.

On Ms Windows the program works only when compiled on Windows XP 32 bit and distributed keeping some of the DLLs related to GDI and Networking of that version. 

-----------------------
Release notes
-----------------------
2020 (14th April) version 0.3.6 candidate 2
 - Map: changed background color from red to yellow for station markers
 - Get version: - looked into OS getversion and partially modified the output to cover Win 7 and 10/8 ids  
 - renamed platform module to dplatform as platform 

2020 (7th April) version 0.3.6 candidate 1 
 - fix "get position" / "get all positions"
 - investigate and fix some warnings 

2019-10 version 0.3.5
 - fix maps to use Thunderforest maps with API key
 - reorganized gps preferences
 
2015-6-3  version 0.3.4alfa
 - erlarged the map window to resizable format (from 4:3 to 16:9/resizable)
 - added other sources of maps
 - added client to output gps fixes as JSON to D-Rats-D-Rats-WebMap-server
   
Sprig 2014, 
- started  studiyng the original python program, 
- adding comments and print in the original code as per best understanding
- studing how to compile the program on windows

========================================
READY TO RUN -- EXECUTION ON WINDOWS
========================================

To install the new version of D-Rats on Windows download the distrubution version (file in .rar format) 
uncompress it in a folder of your choice and just run d-rats.exe

AT THE MOMENT THERE IS A "BUILT VERSION" IN THE RAR FILE, BUT THERE ARE SOME KNOWN ISSUES WITH LIBRARIES NOT INCLUDED,  SO IT IS POSSIBLE THAT IT WILL NOT WORK ON YOUR SYSTEM. PLEASE REPORT ME THE PROBLEMS YOU HAVE.  YOUR HELP CAN BE USEFUL TO SORT THIS OUT.

The windows executable can be downlodaded from here:
      - https://iz2lxi.jimdofree.com/


Note that at runtime he eventual errors are logged into a file located either at:
- d-rats.exe location as d-rats.log
- C:\Users\<username>\AppData\Roaming\D-RATS-EV\debug.log


========================================
DEVELOPMENT ENVIRONMENT
========================================
-----------------------
Developing on Linux
-----------------------

Note: the source code of d-rats is quite dated, so use python 2.7

Common libraries
 - gtk http://www.gtk.org/download/
 - gtk glade module
 - gobject

 - apt-get install:
    - python-gtk2
    - python-glade2
    - python-serial
    - python-libxml2
    - python-libxslt1

 - easy_install:
    - simplejson
    - feedparser
    - libxml2

ans also these libraries required by to export the gps positions in JSON:
    - flask
    - gevent:
          from http://www.gevent.org/ or
          > easy_install gevent
          
    - gevent-socketio
          > easy_install gevent-socketio
         
    - greenlet
        > easy_install gevent-socketio

-----------------------
Developing on Ms-Windows 10/ 7 /.../xp .. XP!!
-----------------------
*** important NOTE: THE ONLY KNOWN WINDOWS INSTALLATION ABLE TO CREATE A WORKING COMPILED VERSION ON WINDOWS IS ... WINDOWS XP.
THIS IS BECAUSE THE LIBRAIRES ORIGINALLY NEEDED DOES NOT WORK CORRECTLY WITH THE MORE RECENT DLLs RELATED TO NETWORK OF THE OPERATING SYSTEM ***

Note: the source code of d-rats is quite dated, so use python 2.7 compiled 32 bit and 32 bit libraries
(i did a try installing the 64 bit version of python, but wasn't able to find all the libraries needed at 64 bit)

*INSTALL PYTHON*
 - Python 2.7.X 32 bit:                         http://www.python.it/download/

*INSTALL GTK2 & PYGTK*
 - gtk+-bundle_2.24.10-20120208_win32.zip       http://www.gtk.org/download/win32.php
 - pygtk-all-in-one-2.24.0.win32-py2.7.msi      http://ftp.gnome.org/pub/GNOME/binaries/win32/pygtk/2.24/
 - gtk glade module:                            http://sourceforge.net/projects/gladewin32/
  
*INSTALL ASPELL*
from http://aspell.net/win32/:
  Aspell-0-50-3-3-Setup.exe -                   http://ftp.gnu.org/gnu/aspell/w32/Aspell-0-50-3-3-Setup.exe
  Aspell-en-0.50-2-3.exe - (English) -          http://ftp.gnu.org/gnu/aspell/w32/Aspell-en-0.50-2-3.exe
  Aspell-it-0.50-2-3.exe - (Italian)
  
      NOTE: in order to install the right dll for spell-checking refer to: 
      http://www.d-rats.com/documentation/4-howtos/34-installing-spelling-support/

*PYTHON LIBRARIES via installers*
 procure and install:
- gevent-1.0b4.win32-py2.7.exe
- libxml2-python-2.7.7.win32-py2.7.exe  http://users.skynet.be/sbi/libxml-python/binaries/libxml2-python-2.7.7.win32-py2.7.exe 
- pyserial-2.7.win32.exe                https://pypi.python.org/pypi/pyserial
- ppy2exe-0.6.9.win32-py2.7.exe         http://www.py2exe.org/
- pywin32-219.win32-py2.7.exe           http://sourceforge.net/projects/pywin32/files/pywin32/

*PYTHON LIBRARIES via PIP INSTALL*
Some libraries will be installable via 
  c:\python2.7\scripts> pip install "library-name"
   
   --list to be completed -- 
   
*PYTHON LIBRARIES via EASY INSTALL + source-code.tar.gz*
Some libraries need to be installed after getting the source code in tar.gz file.
 c:\python2.7\scripts> pip install> easy-install "path-to-source-code.tar.gz"

- BeautifulSoup-3.2.2.tar.gz
- netifaces-0.10.9.tar.gz
- feedparser-5.1.3.tar.gz               https://pypi.python.org/pypi/feedparser
- Flask-0.10.1.tar.gz
- itsdangerous-0.24.tar.gz
- MarkupSafe-0.23.tar.gz
- simplejson-3.6.5.tar.gz               https://pypi.python.org/pypi/simplejson/
- gobject

- greenlet-0.4.5-py2.7-win32.egg
- jinja2-master.zip

-----------------------
SETTING THE PATH VARIABLE ON MS-WINDOWS

It seems that nasty things happen if you dont have the right order in the path variable. 
especially if you install locall Python and the various libraries, you will easily end up in with a malfunctioning system

Typical User variable path:
C:\Program Files\Intel\WiFi\bin\;C:\Program Files\Common Files\Intel\WirelessCommon

Typical System variable path:
C:\Windows\system32;C:\Program Files\Common Files\Microsoft Shared\Windows Live;C:\Program Files (x86)\Common Files\Microsoft Shared\Windows Live;
C:\Windows;C:\Windows\System32\Wbem;C:\Windows\System32\WindowsPowerShell\v1.0\;C:\Program Files (x86)\Windows Live\Shared;
C:\Program Files\ThinkPad\Bluetooth Software\;C:\Program Files\ThinkPad\Bluetooth Software\syswow64;C:\Program Files\Microsoft\Web Platform Installer;
C:\Python27;C:\Python27\Scripts;C:\Program Files (x86)\Common Files;C:\Python27;C:\Python27\Scripts;c:\gtk\bin

-----------------------
EXECUTE THE D-RATS APPLICATION on Windows

To execute the d-rats application:

    C:\cd d-rats-3.3.4\:> python d-rats.py
   

-----------------------
D-RATS CONFIGURATION AND LOG FILES

the D-Rats stores its configuration in the user home folder
 - on linux this is here:
     /home/users/ [USERNAME] / ...

 - on windows this is here:
    C:\Users\ [USERNAME] \AppData\Roaming\D-RATS

-----------------------
COMPILING ON MS-WINDOWS XP
-----------------------
NOTE: D-Rats sources can be compiled on any windows platform but, when copied to other PC it will work *NOT* reliably with known issues related to:
- GTK windows layout and events
- Networking (eg. for map tiles and Ratflects connectivity )

To get a compiled version it needs to have Windows XP with a certain version of network Dlls, if updated will just not work properly.

To compile for MS Windows: launch the "distXP.bat", this will create the "dist" folder within the source code 

*DLLs to be removed from Dist folder* 
These Dlls shall be deleted from the "dist" folder in order to have a working networking
- dnsapi.dll
- imm32.dll
- netapi32.dll
- ws2_32.dll
- wsock32.dll


========================================
OTHER NOTES TO BE ORGANIZED 
========================================
ERRORS IN FILES TAB

if you happen to see "strange" files appearing into the files tabs, together with un-working d-rats,
then this is most probably happening because of a bad order in the PATH variable of your windows pc.

i.e. have you put the aspell path at the beginning of the PATH instead of at its end?

========================================
INTERNATIONALIZATION - LABEL TRANSLATIONS
the labels dictionaries are translated using the gettext module using the dictionaties located into the 
"locales".

the dictionaries are compiled in ".mo" but can be reversed to ".po" to be edited (e.g. with tool ("poedit"):

With installed poedit you can use:

START -> RUN (cmd)

/program files/poedit/bin/msgunfmt ab_AB.mo > ab_AB.po

 

========================================
RS-MS1A INTEGRATION
    *** NOT YET STUDIED HOW TO DO THIS ***

Sample text messages received by
[09:38:45] [com6] CQCQCQ: $$Msg,IZ2LXI,,0011DCtest transmission

=======================================
D-RATS Locally cached Maps
are based on open streetmap tiles.
more infos:
http://wiki.openstreetmap.org/wiki/Tiles

In the preferences it is now possible to indicate a different map server where to get the map tiles:

    Openstreetmap:    (standard)
    http://tile.openstreetmap.org

-    Mapquest:
    http://otile1.mqcdn.com/tiles/1.0.0/osm/
    http://otile2.mqcdn.com/tiles/1.0.0/osm/
    http://otile3.mqcdn.com/tiles/1.0.0/osm/
    http://otile4.mqcdn.com/tiles/1.0.0/osm/
           
    CycleMap
    http://a.tile.thunderforest.com/cycle


NOTE: The D-Rats Mapdownloader application has been discontinued -- please use one of
the exisitng opensource tools to download the maps tiles to use offline in D-Rats .

You can use JTileDownloader
http://wiki.openstreetmap.org/index.php/JTileDownloader

The map site URL are:

         Base map:     Openstreetmap
         cycle map:    OpenCycleMap

When downloaded just move the tile folders under the right map folder in D.Rats, e.g:

         Base map:     C:\Users\<username>\AppData\Roaming\D-RATS\maps\base
         Cycle map:    C:\Users\<username>\AppData\Roaming\D-RATS\maps\cycle

   
=======================================
D-RATS Web MapServer

created the interface towards a separate program "WebMap Server extension"

serving a map.html page where d-rats will output the gps positions of the radios listened


 
   
