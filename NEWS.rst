For the python 2 version see the changelog file.

.. towncrier release notes start

D_Rats.Version 0.4.2 (2023-11-28)
=================================

Bugfixes
--------

- Changed to use Python csv module for csv file. (#119)
- User's default html and text viewer applications will now be used. (#129)
- D-Rats Repeater should not try to run a GUI console when not possible. (#176)
- Fix version fallback when running from GitHub archive. (#187)
- Fixed sound on Linux and enabled it for Mac OS. (#191)
- Optional Lookup of longitude and Latitude by address now available
  in the GPS configuration dialog. (#199)
- Add version reporting to d-rats_repeater. (#200)
- Fix password validation for Ratflectors. (#201)
- Add --version qualifier to d-rats.py (#204)
- Fix Shebang on internationalization_test.py #209 (#209)
- Fix NMEA to decimal degree conversions. (#211)
- Fix Form save/send/print not working. (#215)
- Fix loading of translations.
  Updated About Dialog.
  Moved icons into images folder for icons and images and moved *.ico into it. (#218)
- Fix crash in adding e-mail accounts. (#224)
- Fixed crash on removing attachments from a message. (#226)
- Fix message attachment extraction (#228)
- Fix D-Rats flooding of the console log with invalid DPRS symbol messages.
  Fix config dialog for selecting APRS and DPRS icons. (#230)
- Use the locale environment variables for default locale. (#236)
- Added APRS Overlay support. (#237)
- Fix d-rats_repeater device entry. (#243)
- version.py version lookup fails if git is not installed. (#245)
- Fix build_pot.sh to also rebuild the binary message databases. (#249)
- Do not run D-rats client or repeater with privileges (#250)
- Fix formatting error in d-rats Repater code. (#251)
- Use serial driver XON/XOFF Handling (#253)
- File transfer was creating directory with remote station name in
  the current working directory. (#257)
- Fix sending image resize dialog. (#265)


D_Rats.Version 0.4.1 (2023-05-13)
=================================

Bugfixes
--------

- Make sure parent directories are created. (#149)
- Fix crash on invalid integer data in config file. (#167)
- Fix crash in new message creation. (#170)
- Fix finding files for installed d-rats packages. (#174)
- Generate PKG-INFO for python packages (#180)

D_Rats.Version 0.4.0 (2023-03-26)
=================================

Features
--------

- Now using 'python -m build' to build python packages. (#113)
- The d_rats-repeater now supports all the radio types as the D-rats program. (#116)
- Per current python conventions, towncrier is used for creating a News.rst
  file that replaces the changelog file. (#117)


Bugfixes
--------

- Required attribution use of OpenWeather (TM) data added. (#107)
- When running D-Rats from source, it no longer requires your
  default directory to be the source directory. (#108)
- Clients will attempt to reconnect to internet ratflector when
  they detect a disconnection. (#109)
- Some platform D-RATS program can not exchange files with programs running on
  other platforms.  D-Rats was incorrectly sending the file size in
  native-endian format instead of network-endian format.

  D-RAts is now sending the file size in little-endian format instead of
  network-endian format to be compatible with the majority of existing
  D-rats programs in use.

  Users of D-Rats on big-endian platforms need to upgrade to this version
  of d-rats. (#111)
- Serial port warmup timeout in d-rats_repeater is now working. (#114)
- The lzhuf program will now build on Mac OSX platforms and
  probably other platforms that it did not build on before.

  This version of the program will only work on little-endian
  systems. (#115)
- D-rats can now be installed in a python virtual environment.
  Fixed the paths for where system data is stored and looked for
  to match Python and general conventions. (#118)
- The lzhuf source and binary have been moved into their own
  repository and must be installed separately for the functionality
  needed for winlink. (#152)


Misc
----

- #110, #112
