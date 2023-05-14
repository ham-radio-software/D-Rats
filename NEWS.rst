For the python 2 version see the changelog file.

.. towncrier release notes start

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
