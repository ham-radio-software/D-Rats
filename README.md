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
This version of D-Rats is a study version of the D-Rats 0.3.3. originally developed and 
Copyrighted by 2008 Dan Smith <dsmith@danplanet.com> and later reviewed in 2015, 2019 and 2020 by me, Maurizio Andreotti

The idea here is to read the source, add some comments and eventually do some modifications and share. 
Luckily there is no obligation for anybody to use it, in particular if you are happy with the one from Dan.

If this works for you I am happy, If it doesn't ... 

*** Note for awareness and understanding  ***

I picked up D.Rats code as I needed the maps feature back and after some time I released  (in 2015 and in 2019) for benefit of everybody. 

The program is pretty much the one developed by Dan more than 10 years ago based on libraries by the python community which – in many cases - are not supported anymore by anybody –  not to mention that the operating system itself changed multiple times, and each of us has a different footprint of applications installed, making each execution situation different. So there is no promise from me that it will work on your PC.

Recompiling it (even unchanged) nowdays for Windows has been challenging and implied going back to windows XP to ensure compatibility and a lot of hours of tests and investigation, I am glad it works for me and some others.  

It was difficult to get it work on my PC (Win10 and XP) with full access to logs and realtime control of what happens (e.g. clicking on some d-rats button, and looking d-rats behaviour result and logs to sort out thinkgs). 

If in your case it does not work, that is an unhappy case which I feel it will continue not working until some magic happens (in particular if there is no valuable feedback provided to understand why it failed). 

If you want to allow some investigation, but there is no obligation, it is needed to share both the debug log, the config file in use and also describe in detail the steps you did to open, configure, and use it. 

Anyhow the code is published and anybody can go look into it and sort out things.

-----------------------
Supported systems
-----------------------
This program ONLY work with older Linux distributions that still include Python2, GTK2, etc.
Support for this program on newer distros is NOT possible until major porting work is completed.

On Ms Windows the program works only when compiled on Windows XP 32 bit and distributed keeping some of the DLLs related to GDI and Networking of that version. 

-----------------------
Release notes
-----------------------
2020 version 0.3.7 beta
- Added password for Winlink2000
- Maps
  - added deletion of tiles which result defective at map rendering time (deletion will force re-download of the tiles at next map reload)
  - added map reload after a change is done in the config (this avoid closing and reopening D-rats to change map)

- Continued porting "print" to print() 

2020 (14th April) version 0.3.6 review
 - Get version: - looked into OS getversion and partially modified the output to cover Win 7 and 10/8 ids  
 - Renamed platform module to dplatform as platform 
 - Default config: 
     - base map set to http//tile.openstreetmap.de
     - default APRS icon shown changed to a valid one:  BN  *26 
     Network
     - added localhost ratflector config 
     - added k3pdr ratflector (would be useful? Also adding others?)
     Messages-->enable by default "Automatically Forward Messages".
     - Set Queue flush interval to 30 seconds.
     - Set Station TTL to 600 seconds.
     Transfers -> enable "Remote File Transfers".
     - Set Warmup Length to 16.
     - Set Warmup Timeout to 0.

 - Mapwindow: 
   - fixed markers postioning with icons 
   - fixed markers+icons display at zoom 5-18 (zoom 2-4 still to be fixed)
   - changed background color or markers from red to yellow
   - modified the �map window title � adding the map in use

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
FOR MORE INFO HAVE A WALK IN THE WIKI
https://github.com/maurizioandreotti/D-Rats/wiki/D-Rats-Evolution-wiki

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
INSTALL ON LINUX (contrib & credit Marius Petrescu)
========================================

The installation steps are quite easy (assuming one has all the neede python libs installed):

via package installer: python-glade2, python-libxml2, pythhon-libxslt1
via pip: pyserial

After this, the steps are as follows:

cd to your D-Rats source directory
issue 'python setup.py build'
issue 'python setup.py install'    (this could require a sudo)

you can now execute D-Rats from terminal,:

> d-rats.py
> d-rats-terminal

This should do it. Main scripts are in /usr/local/bin, configuration and logs will be found in the user's home directory as .d-rats-ev (a hidden directory).

  

-----------------------
D-RATS CONFIGURATION AND LOG FILES

the D-Rats stores its configuration in the user home folder
 - on linux this is here:
     /home/users/ [USERNAME] / ...

 - on windows this is here:
    C:\Users\ [USERNAME] \AppData\Roaming\D-RATS
